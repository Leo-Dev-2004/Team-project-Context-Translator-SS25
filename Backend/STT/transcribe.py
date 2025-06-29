# Backend/STT/transcribe.py (MODIFIED)

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
from uuid import uuid4

from faster_whisper import WhisperModel

# --- Configuration ---
CHUNK_DURATION_SEC = 3
SAMPLE_RATE = 16000
CHANNELS = 1
MODEL_SIZE = "base"
LANGUAGE = "en"
WEBSOCKET_URI = "ws://localhost:8000/ws"

# --- Logging konfigurieren ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Globale Variablen ---
model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")

audio_queue = queue.Queue()
is_recording = threading.Event()
is_recording.set()

# --- Audioaufnahme-Funktion ---
def record_audio():
    logger.info("Starte Audioaufnahme...")
    def callback(indata, frames, time_info, status):
        if status:
            logger.warning(f"Aufnahme-Status-Meldung: {status}")
        audio_queue.put(indata.copy())

    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, callback=callback) as stream:
            logger.info(f"Aufnahme läuft mit Samplerate: {stream.samplerate}, Kanälen: {stream.channels}...")
            while is_recording.is_set():
                sd.sleep(1000)
    except Exception as e:
        logger.critical(f"Fehler bei der Audioaufnahme: {e}", exc_info=True)
    finally:
        logger.info("Audioaufnahme beendet.")

# Start the audio recording thread
threading.Thread(target=record_audio, daemon=True).start()

# --- Textbereinigungs-Funktion ---
def clean_transcription(text):
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    text = text.strip(".,?! ")
    return text if text else None

# --- Transkriptions- und Sende-Funktion an Backend über WebSocket ---
async def transcribe_and_send_to_backend():
    """
    Connects to the backend WebSocket, transcribes audio chunks, and sends the text.
    """
    audio_buffer = []
    samples_per_chunk = int(CHUNK_DURATION_SEC * SAMPLE_RATE)
    current_samples_in_buffer = 0

    stt_client_id = f"stt_instance_{uuid4()}"
    websocket_uri_with_id = f"{WEBSOCKET_URI}/{stt_client_id}"

    logger.info(f"STT Client ID: {stt_client_id}")
    logger.info(f"Versuche, eine Verbindung zum WebSocket unter {websocket_uri_with_id} herzustellen...")

    while is_recording.is_set():
        try:
            async with websockets.connect(websocket_uri_with_id) as websocket:
                logger.info("WebSocket-Verbindung zum Backend hergestellt.")

                # MODIFICATION 1: Initial message now conforms to UniversalMessage
                initial_message_payload = {
                    "message": "STT service connected" # Your original 'message' field
                }
                initial_message = {
                    "id": str(uuid4()),
                    "type": "stt.init", # Use a structured type like "stt.init"
                    "timestamp": time.time(),
                    "payload": initial_message_payload, # All specific data goes in payload
                    "origin": "stt_module", # Optional: specify origin
                    "client_id": stt_client_id
                }
                await websocket.send(json.dumps(initial_message))
                logger.info(f"Gesendet an Backend (initial): {initial_message['type']} from {initial_message['client_id']}")


                while is_recording.is_set():
                    if not audio_queue.empty():
                        data = audio_queue.get()
                        audio_buffer.append(data)
                        current_samples_in_buffer += data.shape[0]

                    if current_samples_in_buffer >= samples_per_chunk:
                        full_chunk_data = np.concatenate(audio_buffer, axis=0)
                        audio_to_transcribe = full_chunk_data[:samples_per_chunk]
                        remaining_audio = full_chunk_data[samples_per_chunk:]

                        audio_buffer = [remaining_audio] if remaining_audio.shape[0] > 0 else []
                        current_samples_in_buffer = remaining_audio.shape[0]

                        audio_data_flat = audio_to_transcribe.flatten().astype(np.float32)

                        try:
                            segments, info = model.transcribe(audio_data_flat, language=LANGUAGE, beam_size=5)

                            full_text = ""
                            for segment in segments:
                                full_text += segment.text

                            text = clean_transcription(full_text)
                            timestamp = time.time()

                            if text:
                                # MODIFICATION 2: Transcription message now conforms to UniversalMessage
                                transcription_payload = {
                                    "text": text,
                                    "language": info.language,
                                    "confidence": info.language_probability
                                }
                                message = {
                                    "id": str(uuid4()),
                                    "type": "stt.transcription", # Use a structured type like "stt.transcription"
                                    "timestamp": timestamp,
                                    "payload": transcription_payload, # All specific data goes in payload
                                    "origin": "stt_module", # Optional: specify origin
                                    "client_id": stt_client_id
                                }
                                await websocket.send(json.dumps(message))
                                logger.info(f"Gesendet an Backend: {text[:50]}...")

                        except Exception as e:
                            logger.error(f"Fehler bei der Transkription oder beim Senden: {e}", exc_info=True)

                    await asyncio.sleep(0.01)

        except websockets.exceptions.WebSocketException as e:
            logger.warning(f"WebSocket-Fehler ({type(e).__name__}): {e}. Verbindung verloren. Versuche erneut in 3 Sekunden...", exc_info=True)
            await asyncio.sleep(3)
        except Exception as e:
            logger.critical(f"Ein unerwarteter Fehler im Transkriptions-Loop (Hauptschleife): {e}", exc_info=True)
            await asyncio.sleep(5)

    logger.info("Transkriptions- und Sende-Loop beendet.")


# --- Hauptausführung ---
if __name__ == "__main__":
    try:
        asyncio.run(transcribe_and_send_to_backend())
    except KeyboardInterrupt:
        logger.info("Skript durch Benutzer beendet.")
    finally:
        is_recording.clear()
        logger.info("Cleanup abgeschlossen. Beende Programm.")