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
    "MODEL_SIZE": "medium",
    "LANGUAGE": "de", # Sprache auf Deutsch geändert für besseres Beispiel
    "WEBSOCKET_URI": "ws://localhost:8000/ws",
    "MIN_WORDS_PER_SENTENCE": 3,
    "MAX_SENTENCE_DURATION_SECONDS": 15
}

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Dedicated logger for transcriptions
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
transcription_active = True # Flag to pause/resume transcription

# --- AUDIO RECORDING THREAD ---
def record_audio():
    """Captures audio from the microphone and puts it into a queue."""
    logger.info("Starting audio recording...")
    block_size = int(CONFIG["SAMPLE_RATE"] * 0.05) # 50ms blocks
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
        transcription_logger.info(sentence) # Log transcription to file
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

    # Shared state for concurrent tasks
    confidence_history = deque(maxlen=20)
    silence_frames = 0 # Placeholder for VAD
    total_frames = 0   # Placeholder for VAD

    # --- Nested Task: Heartbeat ---
    async def heartbeat_loop(websocket):
        """Sends periodic status updates to the backend."""
        while is_recording.is_set():
            await asyncio.sleep(10) # Send heartbeat every 10 seconds
            # Note: audio_level and vad_rate are placeholders for now
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
                break # Exit if connection is closed

    # --- Nested Task: Audio Processing ---
    async def process_audio_loop(websocket):
        """Processes audio from the queue and performs transcription."""
        nonlocal total_frames # Modify the outer scope variable
        audio_buffer = []
        current_sentence_words = []
        samples_per_chunk = int(CONFIG["CHUNK_DURATION_SEC"] * CONFIG["SAMPLE_RATE"])

        while is_recording.is_set():
            if not transcription_active:
                await asyncio.sleep(0.1)
                continue

            try:
                data = audio_queue.get(timeout=1)
                audio_buffer.append(data)

                if sum(a.shape[0] for a in audio_buffer) >= samples_per_chunk:
                    full_audio_data = np.concatenate(audio_buffer, axis=0)
                    audio_buffer.clear()
                    
                    audio_data_flat = full_audio_data.flatten().astype(np.float32)
                    segments, info = model.transcribe(audio_data_flat, language=CONFIG["LANGUAGE"], word_timestamps=True)
                    
                    total_frames += 1
                    confidence_history.append(info.language_probability)

                    for segment in segments:
                        if segment.words:
                            for word in segment.words:
                                current_sentence_words.append(word.word)
                                # Check for sentence-ending punctuation
                                if word.word.strip().endswith((".", "?", "!")):
                                    full_sentence = "".join(current_sentence_words).strip()
                                    if len(full_sentence.split()) >= CONFIG["MIN_WORDS_PER_SENTENCE"]:
                                        await send_sentence(websocket, full_sentence, info, stt_client_id)
                                    current_sentence_words.clear()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in audio processing loop: {e}", exc_info=True)
                break # Exit if a critical error occurs

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

                # Run heartbeat and audio processing concurrently
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

        # Start the microphone recording in a separate thread
        threading.Thread(target=record_audio, daemon=True).start()
        
        # Run the main async service
        asyncio.run(run_transcription_service(user_session_id=args.user_session_id))

    except SystemExit:
        logger.critical("Argument parsing failed. Please provide --user-session-id.")
    except Exception as e:
        logger.critical(f"A critical error occurred during STT module startup: {e}", exc_info=True)
    finally:
        is_recording.clear()
        logger.info("Cleanup complete. STT module has shut down.")