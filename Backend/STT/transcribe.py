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

# --- CONFIGURATION ---
CONFIG = {
    "CHUNK_DURATION_SEC": 0.5,
    "SAMPLE_RATE": 16000,
    "CHANNELS": 1,
    "MODEL_SIZE": "base",
    "LANGUAGE": "en",
    "WEBSOCKET_URI": "ws://localhost:8000/ws",
    "MIN_WORDS_PER_SENTENCE": 3,
    "MAX_SENTENCE_DURATION_SECONDS": 15,
    "TRANSCRIPTION_WINDOW_SECONDS": 5,
    "SENTENCE_COMPLETION_TIMEOUT_SEC": 1.5
}

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

transcription_logger = logging.getLogger('TranscriptionLog')
transcription_logger.setLevel(logging.INFO)
t_handler = logging.FileHandler('transcription.log', mode='w', encoding='utf-8')
t_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
transcription_logger.addHandler(t_handler)

# --- GLOBAL STATE ---
model = WhisperModel(CONFIG["MODEL_SIZE"], device="cpu", compute_type="int8")
logger.info(f"Whisper model '{CONFIG['MODEL_SIZE']}' loaded.")
audio_queue = queue.Queue()
is_recording = threading.Event()
is_recording.set()
transcription_active = True

# --- AUDIO RECORDING THREAD ---
def record_audio():
    """Captures audio from the microphone and puts it into a queue."""
    logger.info("Starting audio recording...")
    block_size = int(CONFIG["SAMPLE_RATE"] * 0.05)
    def callback(indata, frames, time_info, status):
        if status:
            logger.warning(f"Recording status: {status}")
        if is_recording.is_set():
            audio_queue.put(indata.copy())
            
    try:
        with sd.InputStream(samplerate=CONFIG["SAMPLE_RATE"], channels=CONFIG["CHANNELS"], callback=callback, blocksize=block_size) as stream:
            logger.info(f"Recording active: {stream.samplerate}Hz, {stream.channels}ch")
            while is_recording.is_set():
                time.sleep(0.1)
    except Exception as e:
        logger.critical(f"Audio recording error: {e}", exc_info=True)
    finally:
        logger.info("Audio recording stopped.")

# --- WEBSOCKET & TRANSCRIPTION LOGIC ---
async def send_sentence(websocket, sentence, info, client_id):
    """Formats and sends a transcribed sentence over the WebSocket."""
    if sentence:
        transcription_logger.info(sentence)
        message = {
            "id": str(uuid4()),
            "type": "stt.transcription",
            "timestamp": time.time(),
            "payload": {"text": sentence, "language": info.language, "confidence": info.language_probability},
            "origin": "stt_module",
            "client_id": client_id
        }
        await websocket.send(json.dumps(message))
        logger.info(f"Sent: {sentence}")

async def run_transcription_service(user_session_id: str):
    """Main service loop that manages WebSocket connection and transcription tasks."""
    stt_client_id = f"stt_instance_{uuid4()}"
    websocket_uri_with_id = f"{CONFIG['WEBSOCKET_URI']}/{stt_client_id}"
    logger.info(f"STT Client ID: {stt_client_id} | User Session ID: {user_session_id}")

    confidence_history = deque(maxlen=20)
    silence_frames = 0
    total_frames = 0

    async def heartbeat_loop(websocket):
        """Sends periodic status updates to the backend."""
        while is_recording.is_set():
            await asyncio.sleep(10)
            audio_level = np.random.rand() 
            avg_confidence = round(np.mean(confidence_history), 4) if confidence_history else None
            vad_rate = round((silence_frames / total_frames) * 100, 2) if total_frames > 0 else None
            
            heartbeat_message = {
                "id": str(uuid4()),
                "type": "stt.heartbeat",
                "timestamp": time.time(),
                "payload": {
                    "status": "running" if transcription_active else "paused",
                    "audio_level": audio_level,
                    "avg_confidence": avg_confidence,
                    "vad_rate": vad_rate
                },
                "origin": "stt_module",
                "client_id": stt_client_id
            }
            try:
                await websocket.send(json.dumps(heartbeat_message))
                logger.debug("Heartbeat sent.")
            except Exception as e:
                logger.warning(f"Heartbeat failed: {e}")
                break

    async def process_audio_loop(websocket):
        """Processes audio from the queue and performs transcription using a rolling window."""
        nonlocal total_frames, stt_client_id
        
        rolling_buffer = np.array([], dtype=np.float32)
        current_sentence_words = []
        last_word_timestamp = time.monotonic()
        
        samples_per_chunk = int(CONFIG["CHUNK_DURATION_SEC"] * CONFIG["SAMPLE_RATE"])

        logger.info(f"Audio processing configured for {CONFIG['TRANSCRIPTION_WINDOW_SECONDS']}s windows.")

        while is_recording.is_set():
            if not transcription_active:
                await asyncio.sleep(0.1)
                continue
            
            # --- Part 1: Process any new audio from the queue ---
            try:
                while not audio_queue.empty():
                    data = audio_queue.get_nowait()
                    rolling_buffer = np.concatenate((rolling_buffer, data.flatten()))

                if len(rolling_buffer) >= samples_per_chunk:
                    audio_to_process = rolling_buffer.astype(np.float32)
                    segments, info = model.transcribe(
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

            except queue.Empty:
                # This is expected when the user is not speaking.
                pass
            except Exception as e:
                logger.error(f"Error during audio transcription: {e}", exc_info=True)
                await asyncio.sleep(1)
                continue

            # --- Part 2: Check for sentence completion (runs every loop) ---
            time_since_last_word = time.monotonic() - last_word_timestamp
            sentence_is_ready = current_sentence_words and time_since_last_word > CONFIG["SENTENCE_COMPLETION_TIMEOUT_SEC"]

            if sentence_is_ready:
                full_sentence = " ".join(w.word for w in current_sentence_words).strip()
                
                if len(full_sentence.split()) >= CONFIG["MIN_WORDS_PER_SENTENCE"]:
                    class DummyInfo:
                        language = CONFIG["LANGUAGE"]
                        language_probability = 1.0
                    
                    await send_sentence(websocket, full_sentence, DummyInfo(), stt_client_id)

                # Reset for the next sentence
                current_sentence_words.clear()
                rolling_buffer = np.array([], dtype=np.float32)

            # --- Part 3: Sleep to prevent a busy-wait loop ---
            await asyncio.sleep(0.1)

    # --- Connection and Task Execution Loop ---
    while is_recording.is_set():
        try:
            async with websockets.connect(websocket_uri_with_id) as websocket:
                logger.info("WebSocket connection established with backend.")
                initial_message = {
                    "id": str(uuid4()), "type": "stt.init", "timestamp": time.time(),
                    "payload": {"message": "STT service connected", "user_session_id": user_session_id},
                    "origin": "stt_module", "client_id": stt_client_id
                }
                await websocket.send(json.dumps(initial_message))
                
                await asyncio.gather(
                    heartbeat_loop(websocket),
                    process_audio_loop(websocket)
                )

        except Exception as e:
            logger.error(f"WebSocket connection failed, retrying in 5s: {e}")
            await asyncio.sleep(5)

# --- MAIN EXECUTION BLOCK ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="STT Module for Context Translator.")
    parser.add_argument(
        "--user-session-id", type=str, required=True,
        help="The unique ID for the user session."
    )

    try:
        args = parser.parse_args()
        logger.info(f"STT module starting up with User Session ID: {args.user_session_id}")

        threading.Thread(target=record_audio, daemon=True).start()
        
        asyncio.run(run_transcription_service(user_session_id=args.user_session_id))

    except SystemExit:
        logger.critical("Argument parsing failed. Please provide --user-session-id.")
    except Exception as e:
        logger.critical(f"A critical error occurred during STT module startup: {e}", exc_info=True)
    finally:
        is_recording.clear()
        logger.info("Cleanup complete. STT module has shut down.")