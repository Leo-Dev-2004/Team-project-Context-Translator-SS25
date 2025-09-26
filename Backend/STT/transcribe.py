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
from pathlib import Path

# --- CONFIGURATION ---
# Using a more structured config for clarity and easier modification
class Config:
    SAMPLE_RATE = 16000
    CHANNELS = 1
    MODEL_SIZE = "medium"
    LANGUAGE = "en"
    WEBSOCKET_URI = "ws://localhost:8000/ws"
    MIN_WORDS_PER_SENTENCE = 1 # Reduced for better responsiveness
    
    # VAD (Voice Activity Detection) settings are key for responsiveness
    VAD_ENERGY_THRESHOLD = 0.004 # Energy threshold to detect speech
    VAD_SILENCE_DURATION_S = 1.0 # How long of a pause indicates end of sentence
    VAD_BUFFER_DURATION_S = 0.5 # Seconds of silence to keep before speech starts
    
    # Heartbeat settings to prevent connection timeouts during silence
    HEARTBEAT_INTERVAL_S = 30.0 # Send heartbeat every 30 seconds during silence

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
transcription_logger = logging.getLogger('TranscriptionLog')
transcription_logger.setLevel(logging.DEBUG)
log_file = Path("transcription.log")
log_file.touch()
t_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
t_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
transcription_logger.addHandler(t_handler)


class STTService:
    """
    Encapsulates the entire Speech-to-Text functionality using a robust,
    VAD-based "record-then-transcribe" architecture for real-time responsiveness.
    """
    def __init__(self, user_session_id: str):
        self.user_session_id = user_session_id
        self.stt_client_id = f"stt_instance_{uuid4()}"
        logger.info(f"Loading Whisper model '{Config.MODEL_SIZE}'...")
        self.model = WhisperModel(Config.MODEL_SIZE, device="cpu", compute_type="int8")
        logger.info("Whisper model loaded.")
        self.audio_queue = queue.Queue()
        self.is_recording = threading.Event()
        self.is_recording.set()
        logger.info(f"STTService initialized for session {self.user_session_id}")

    def _record_audio_thread(self):
        """[Thread Target] Captures audio from microphone into a thread-safe queue."""
        def callback(indata, frames, time_info, status):
            if status: logger.warning(f"Recording status: {status}")
            if self.is_recording.is_set(): self.audio_queue.put(indata.copy())
            
        try:
            with sd.InputStream(samplerate=Config.SAMPLE_RATE, channels=Config.CHANNELS, callback=callback, dtype='float32') as stream:
                logger.info(f"Recording active: {stream.samplerate}Hz, {stream.channels}ch")
                while self.is_recording.is_set(): time.sleep(0.1)
        except Exception as e:
            logger.critical(f"Audio recording error: {e}", exc_info=True)
        finally:
            logger.info("Audio recording stopped.")

    async def _send_sentence(self, websocket, sentence: str):
        """Formats and sends a transcribed sentence over the WebSocket."""
        if not sentence or not sentence.strip():
            logger.warning("STTService: Blocked empty or whitespace-only transcription from being sent.")
            return

        transcription_logger.info(sentence)
        message = {
            "id": str(uuid4()), "type": "stt.transcription", "timestamp": time.time(),
            "payload": {
                "text": sentence, "language": Config.LANGUAGE,
                "user_session_id": self.user_session_id
            },
            "origin": "stt_module", "client_id": self.stt_client_id
        }
        try:
            await websocket.send(json.dumps(message))
            logger.info(f"Sent: {sentence}")
        except Exception as e:
            logger.warning(f"Failed to send sentence, connection error: {e}")

    async def _send_heartbeat(self, websocket):
        """Sends a heartbeat keep-alive message to prevent connection timeout."""
        message = {
            "id": str(uuid4()), "type": "stt.heartbeat", "timestamp": time.time(),
            "payload": {
                "message": "keep-alive", 
                "user_session_id": self.user_session_id
            },
            "origin": "stt_module", "client_id": self.stt_client_id
        }
        try:
            await websocket.send(json.dumps(message))
            logger.debug("Sent heartbeat keep-alive message")
        except Exception as e:
            logger.warning(f"Failed to send heartbeat, connection error: {e}")

    async def _process_audio_loop(self, websocket):
        """[Async Task] Implements the VAD-based 'record-then-transcribe' logic."""
        audio_buffer = []
        is_speaking = False
        silence_start_time = None
        last_heartbeat_time = time.monotonic()
        last_activity_time = time.monotonic()  # Track last transcription or significant activity
        
        # Keep a small buffer of recent silence to catch the start of speech
        silence_buffer_size = int(Config.VAD_BUFFER_DURATION_S * Config.SAMPLE_RATE)
        silence_buffer = deque(maxlen=silence_buffer_size)

        while self.is_recording.is_set():
            current_time = time.monotonic()
            
            try:
                # Get a chunk of audio from the queue
                audio_chunk = self.audio_queue.get(timeout=1.0)
                frame_energy = np.sqrt(np.mean(np.square(audio_chunk)))
                
                if is_speaking:
                    audio_buffer.append(audio_chunk)
                    if frame_energy < Config.VAD_ENERGY_THRESHOLD:
                        if silence_start_time is None:
                            silence_start_time = time.monotonic()
                        # If silence duration is exceeded, end of sentence is detected
                        elif time.monotonic() - silence_start_time > Config.VAD_SILENCE_DURATION_S:
                            is_speaking = False
                    else:
                        silence_start_time = None # Reset silence timer if speech is detected
                else:
                    silence_buffer.extend(audio_chunk.flatten())
                    if frame_energy > Config.VAD_ENERGY_THRESHOLD:
                        logger.info("Speech detected.")
                        is_speaking = True
                        silence_start_time = None
                        last_activity_time = current_time  # Update activity time
                        # Prepend the silence buffer to capture the start of the word
                        audio_buffer = [np.array(list(silence_buffer))]
                        audio_buffer.append(audio_chunk)

                # If speech has ended, process the collected audio buffer
                if not is_speaking and audio_buffer:
                    full_utterance = np.concatenate([chunk.flatten() for chunk in audio_buffer])
                    audio_buffer.clear()
                    
                    logger.info(f"Processing utterance of duration {len(full_utterance)/Config.SAMPLE_RATE:.2f}s...")
                    segments, _ = await asyncio.to_thread(
                        self.model.transcribe, full_utterance, language=Config.LANGUAGE
                    )
                    
                    full_sentence = "".join(s.text for s in segments).strip()
                    
                    if len(full_sentence.split()) >= Config.MIN_WORDS_PER_SENTENCE:
                        await self._send_sentence(websocket, full_sentence)
                        last_activity_time = current_time  # Update activity time after sending
                    else:
                        logger.info(f"Skipping short sentence: '{full_sentence}'")

                # Send heartbeat if needed (no recent activity and sufficient time has passed)
                time_since_last_heartbeat = current_time - last_heartbeat_time
                time_since_last_activity = current_time - last_activity_time
                
                if (time_since_last_heartbeat >= Config.HEARTBEAT_INTERVAL_S and 
                    time_since_last_activity >= Config.HEARTBEAT_INTERVAL_S):
                    await self._send_heartbeat(websocket)
                    last_heartbeat_time = current_time

            except queue.Empty:
                # Check for heartbeat even when no audio data is available
                current_time = time.monotonic()
                time_since_last_heartbeat = current_time - last_heartbeat_time
                time_since_last_activity = current_time - last_activity_time
                
                if (time_since_last_heartbeat >= Config.HEARTBEAT_INTERVAL_S and 
                    time_since_last_activity >= Config.HEARTBEAT_INTERVAL_S):
                    await self._send_heartbeat(websocket)
                    last_heartbeat_time = current_time
                
                # If speech was in progress and the queue is now empty, it's the end of an utterance
                if is_speaking:
                    is_speaking = False
                continue
            except Exception as e:
                logger.error(f"Error in transcription loop: {e}", exc_info=True)
                # Reset state on error
                audio_buffer.clear()
                is_speaking = False
                await asyncio.sleep(1)

    async def run(self):
        """Main service loop that manages WebSocket connection and tasks."""
        websocket_uri = f"{Config.WEBSOCKET_URI}/{self.stt_client_id}"
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
    parser.add_argument("--user-session-id", required=True, help="The unique ID for the user session.")
    
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
        
        transcription_logger.removeHandler(t_handler)
        t_handler.close()
        logger.info("Cleanup complete. STT module has shut down.")