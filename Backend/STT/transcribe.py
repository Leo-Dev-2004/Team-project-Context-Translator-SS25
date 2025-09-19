import asyncio
import numpy as np
import sounddevice as sd
import queue
import threading
import time
import logging
import websockets
import json
import argparse
from uuid import uuid4
from faster_whisper import WhisperModel
from collections import deque
from typing import Optional

# --- CONFIGURATION ---
# (Beibehalten, da es eine gute Praxis ist, Konfigurationen an einem Ort zu haben)
CONFIG = {
    "CHUNK_DURATION_SEC": 0.5,
    "SAMPLE_RATE": 16000,
    "CHANNELS": 1,
    "MODEL_SIZE": "medium",
    "LANGUAGE": "en",
    "WEBSOCKET_URI": "ws://localhost:8000/ws",
    "MIN_WORDS_PER_SENTENCE": 3,
    "MAX_SENTENCE_DURATION_SECONDS": 15,
    "TRANSCRIPTION_WINDOW_SECONDS": 1.5,
    "SENTENCE_COMPLETION_TIMEOUT_SEC": 0.75
}

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

transcription_logger = logging.getLogger('TranscriptionLog')
transcription_logger.setLevel(logging.INFO)
t_handler = logging.FileHandler('transcription.log', mode='w', encoding='utf-8')
t_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
transcription_logger.addHandler(t_handler)


class STTService:
    """
    Encapsulates the entire Speech-to-Text functionality, managing audio capture,
    AI transcription, and WebSocket communication in a robust, class-based structure.
    """
    def __init__(self, user_session_id: str):
        self.user_session_id = user_session_id
        self.stt_client_id = f"stt_instance_{uuid4()}"
        self.model = WhisperModel(CONFIG["MODEL_SIZE"], device="cpu", compute_type="int8")
        self.audio_queue = queue.Queue()
        self.is_recording = threading.Event()
        self.is_recording.set()
        self.last_sentences = deque(maxlen=5)
        logger.info(f"STTService initialized for session {self.user_session_id}")

    def _record_audio_thread(self):
        """[Thread Target] Captures audio and puts it into a thread-safe queue."""
        block_size = int(CONFIG["SAMPLE_RATE"] * 0.05)
        def callback(indata, frames, time_info, status):
            if status: logger.warning(f"Recording status: {status}")
            if self.is_recording.is_set(): self.audio_queue.put(indata.copy())
            
        try:
            with sd.InputStream(samplerate=CONFIG["SAMPLE_RATE"], channels=CONFIG["CHANNELS"], callback=callback, blocksize=block_size) as stream:
                logger.info(f"Recording active: {stream.samplerate}Hz, {stream.channels}ch")
                while self.is_recording.is_set(): time.sleep(0.1)
        except Exception as e:
            logger.critical(f"Audio recording error: {e}", exc_info=True)
        finally:
            logger.info("Audio recording stopped.")

    async def _send_sentence(self, websocket, sentence: str, words: list):
        """Formats and sends a transcribed sentence over the WebSocket."""
        if not sentence: return

        transcription_logger.info(sentence)
        message = {
            "id": str(uuid4()), "type": "stt.transcription", "timestamp": time.time(),
            "payload": {
                "text": sentence, "language": CONFIG["LANGUAGE"],
                "start_time": words[0].start if words else None,
                "end_time": words[-1].end if words else None,
                "user_session_id": self.user_session_id # Wichtig für die Zuordnung im Backend
            },
            "origin": "stt_module", "client_id": self.stt_client_id
        }
        try:
            await websocket.send(json.dumps(message))
            logger.info(f"Sent: {sentence}")
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Failed to send sentence, connection closed.")

    async def _process_audio_loop(self, websocket):
        """[Async Task] Processes audio from the queue and performs transcription."""
        rolling_buffer = np.array([], dtype=np.float32)
        samples_per_chunk = int(CONFIG["CHUNK_DURATION_SEC"] * CONFIG["SAMPLE_RATE"])
        current_sentence_words = []
        last_word_timestamp = time.monotonic()
        sentence_start_time = time.monotonic()

        while self.is_recording.is_set():
            try:
                # Part 1: Gather audio from the thread-safe queue
                while not self.audio_queue.empty():
                    data = self.audio_queue.get_nowait()
                    rolling_buffer = np.concatenate((rolling_buffer, data.flatten()))

                if len(rolling_buffer) < samples_per_chunk:
                    await asyncio.sleep(0.1)
                    continue

                audio_to_process = rolling_buffer.astype(np.float32)

                # --- THE CRITICAL FIX ---
                # Run the blocking, CPU-intensive transcription in a separate thread
                # so the asyncio event loop is not blocked.
                segments, info = await asyncio.to_thread(
                    self.model.transcribe,
                    audio_to_process,
                    language=CONFIG["LANGUAGE"],
                    word_timestamps=True,
                    initial_prompt=" ".join(w.word for w in current_sentence_words)
                )

                new_words_found = False
                existing_words_set = {w.word.strip().lower() for w in current_sentence_words}

                for segment in segments:
                    if not segment.words: continue
                    for word in segment.words:
                        if word.word.strip().lower() not in existing_words_set:
                            current_sentence_words.append(word)
                            existing_words_set.add(word.word.strip().lower())
                            new_words_found = True
                
                if new_words_found:
                    last_word_timestamp = time.monotonic()
                
                rolling_buffer = rolling_buffer[-samples_per_chunk:]

                # Part 2: Check for sentence completion
                elapsed_time = time.monotonic() - sentence_start_time
                time_since_last_word = time.monotonic() - last_word_timestamp
                
                is_ready_to_send = current_sentence_words and (
                    time_since_last_word > CONFIG["SENTENCE_COMPLETION_TIMEOUT_SEC"] or
                    elapsed_time > CONFIG["MAX_SENTENCE_DURATION_SECONDS"]
                )

                if is_ready_to_send:
                    full_sentence = " ".join(w.word for w in current_sentence_words).strip()
                    
                    if len(full_sentence.split()) >= CONFIG["MIN_WORDS_PER_SENTENCE"]:
                        if full_sentence not in self.last_sentences:
                            self.last_sentences.append(full_sentence)
                            await self._send_sentence(websocket, full_sentence, current_sentence_words)
                        else:
                            logger.info(f"Skipping duplicate sentence: {full_sentence}")
                    
                    # Reset for the next sentence
                    reason = "timeout" if time_since_last_word > CONFIG["SENTENCE_COMPLETION_TIMEOUT_SEC"] else "max_duration"
                    logger.info(f"Sending sentence due to: {reason} | Words: {len(current_sentence_words)}")
                    current_sentence_words.clear()
                    sentence_start_time = time.monotonic()
                    rolling_buffer = np.array([], dtype=np.float32)

            except queue.Empty:
                await asyncio.sleep(0.1) # Wait if there's no audio
            except Exception as e:
                logger.error(f"Error during audio transcription loop: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def run(self):
        """Main service loop that manages WebSocket connection and tasks."""
        websocket_uri = f"{CONFIG['WEBSOCKET_URI']}/{self.stt_client_id}"
        threading.Thread(target=self._record_audio_thread, daemon=True).start()

        while self.is_recording.is_set():
            try:
                async with websockets.connect(websocket_uri) as websocket:
                    logger.info("WebSocket connection established with backend.")
                    initial_message = {
                        "id": str(uuid4()), "type": "stt.init", "timestamp": time.time(),
                        "payload": {"message": "STT service connected", "user_session_id": self.user_session_id},
                        "origin": "stt_module", "client_id": self.stt_client_id
                    }
                    await websocket.send(json.dumps(initial_message))
                    
                    # This will run the processing loop and keep the connection alive
                    await self._process_audio_loop(websocket)

            except Exception as e:
                logger.error(f"WebSocket connection failed, retrying in 5s: {e}")
                await asyncio.sleep(5)

    def stop(self):
        """Stops the recording and shuts down the service."""
        self.is_recording.clear()
        logger.info("Shutdown signal received. Stopping STT service.")

# --- MAIN EXECUTION BLOCK ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="STT Module for Context Translator.")
    parser.add_argument("--user-session-id", type=str, required=True, help="The unique ID for the user session.")
    
    service = None
    try:
        args = parser.parse_args()
        service = STTService(user_session_id=args.user_session_id)
        asyncio.run(service.run())
    except SystemExit:
        logger.critical("Argument parsing failed. Please provide --user-session-id.")
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Shutting down.")
    except Exception as e:
        logger.critical(f"A critical error occurred: {e}", exc_info=True)
    finally:
        if service:
            service.stop()
        logger.info("Cleanup complete. STT module has shut down.")
