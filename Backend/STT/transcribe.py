import asyncio
import numpy as np
import sounddevice as sd
import queue
import threading
import time
import re
import logging
import websockets
import json
import argparse
from uuid import uuid4
from faster_whisper import WhisperModel

CONFIG = {
    "CHUNK_DURATION_SEC": 0.5,
    "SAMPLE_RATE": 16000,
    "CHANNELS": 1,
    "MODEL_SIZE": "medium",
    "LANGUAGE": "en",
    "WEBSOCKET_URI": "ws://localhost:8000/ws",
    "MIN_WORDS_PER_SENTENCE": 3,
    "MAX_SENTENCE_DURATION_SECONDS": 15
}

logger = logging.getLogger(__name__)
model = WhisperModel(CONFIG["MODEL_SIZE"], device="cpu", compute_type="int8")
audio_queue = queue.Queue()
is_recording = threading.Event()
is_recording.set()
VAD_PARAMS = dict(min_silence_duration_ms=700, max_speech_duration_s=15)

def record_audio():
    logger.info("Starting audio recording...")
    block_size = int(CONFIG["SAMPLE_RATE"] * 0.05)
    def callback(indata, frames, time_info, status):
        if status: logger.warning(f"Recording status: {status}")
        if is_recording.is_set(): audio_queue.put(indata.copy())
    try:
        with sd.InputStream(samplerate=CONFIG["SAMPLE_RATE"], channels=CONFIG["CHANNELS"], callback=callback, blocksize=block_size) as stream:
            logger.info(f"Recording active: {stream.samplerate}Hz, {stream.channels}ch")
            while is_recording.is_set(): time.sleep(0.1)
    except Exception as e:
        logger.critical(f"Audio recording error: {e}", exc_info=True)
    finally:
        logger.info("Audio recording stopped.")

async def send_sentence(websocket, sentence, info, client_id):
    if sentence:
        message = {
            "id": str(uuid4()),
            "type": "stt.transcription",
            "timestamp": time.time(),
            "payload": {"text": sentence, "language": info.language, "confidence": info.language_probability},
            "origin": "stt_module",
            "client_id": client_id
        }
        await websocket.send(json.dumps(message))

async def run_transcription_service(user_session_id: str):
    stt_client_id = f"stt_instance_{uuid4()}"
    websocket_uri_with_id = f"{CONFIG['WEBSOCKET_URI']}/{stt_client_id}"
    logger.info(f"STT Client ID: {stt_client_id} | User Session ID: {user_session_id}")

    while is_recording.is_set():
        try:
            async with websockets.connect(websocket_uri_with_id) as websocket:
                logger.info("WebSocket connection established with backend.")
                initial_message = {
                    "id": str(uuid4()),
                    "type": "stt.init",
                    "timestamp": time.time(),
                    "payload": {"message": "STT service connected", "user_session_id": user_session_id},
                    "origin": "stt_module",
                    "client_id": stt_client_id
                }
                await websocket.send(json.dumps(initial_message))
                await process_audio_loop(websocket, stt_client_id)
        except Exception as e:
            logger.error(f"WebSocket connection failed, retrying in 5s: {e}")
            await asyncio.sleep(5)

async def process_audio_loop(websocket, stt_client_id):
    audio_buffer = []
    samples_per_chunk = int(CONFIG["CHUNK_DURATION_SEC"] * CONFIG["SAMPLE_RATE"])
    global_audio_time_offset = 0.0
    current_sentence_words = []
    
    while is_recording.is_set():
        try:
            data = audio_queue.get(timeout=1)
            audio_buffer.append(data)

            if sum(a.shape[0] for a in audio_buffer) >= samples_per_chunk:
                full_audio_data = np.concatenate(audio_buffer, axis=0)
                audio_buffer.clear()
                
                audio_data_flat = full_audio_data.flatten().astype(np.float32)
                segments, info = model.transcribe(audio_data_flat, language=CONFIG["LANGUAGE"], word_timestamps=True)
                
                for segment in segments:
                    if segment.words:
                        for word in segment.words:
                            current_sentence_words.append(word.word)
                            if word.word.strip().endswith((".", "?", "!")):
                                full_sentence = "".join(current_sentence_words).strip()
                                if len(full_sentence.split()) >= CONFIG["MIN_WORDS_PER_SENTENCE"]:
                                    await send_sentence(websocket, full_sentence, info, stt_client_id)
                                    current_sentence_words.clear()
        except queue.Empty:
            continue
        except Exception as e:
            logger.error(f"Error in audio processing loop: {e}", exc_info=True)

if __name__ == "__main__":
    # KORRIGIERT: Nur ein einziges, sauberes __main__-Block
    parser = argparse.ArgumentParser(description="STT Module for Context Translator.")
    parser.add_argument(
        "--user-session-id",
        type=str,
        required=True,
        help="The unique ID for the user session to link this STT instance with a frontend."
    )

    try:
        args = parser.parse_args()
        logger.info(f"STT module starting up with User Session ID: {args.user_session_id}")

        threading.Thread(target=record_audio, daemon=True).start()
        asyncio.run(run_transcription_service(user_session_id=args.user_session_id))

    except SystemExit as e:
        logger.critical(f"Argument parsing failed, shutting down. This is expected if the required arguments are not provided.")
    except Exception as e:
        logger.critical(f"A critical error occurred during STT module startup: {e}", exc_info=True)
    finally:
        is_recording.clear()
        logger.info("Cleanup complete. STT module has shut down.")