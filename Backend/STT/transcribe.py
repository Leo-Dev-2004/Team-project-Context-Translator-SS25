#  Backend/STT/transcribe.py

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

# --- Konfigurationsobjekt (NEU) ---
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

# --- Logging konfigurieren ---
# Entferne logging.basicConfig() hier, da es Konflikte verursacht.
# Stattdessen nutzen wir das Standard-Logging und das Logging des parent-Prozesses (run_electron.py)
logger = logging.getLogger(__name__)

# --- Globale Variablen ---
model = WhisperModel(CONFIG["MODEL_SIZE"], device="cpu", compute_type="int8")
audio_queue = queue.Queue()
is_recording = threading.Event()
is_recording.set()

# --- VAD-Einstellungen ---
VAD_PARAMS = dict(
    min_silence_duration_ms=700,
    max_speech_duration_s=15
)

# --- Audioaufnahme-Funktion ---
def record_audio():
    logger.info("Starte Audioaufnahme...")
    
    block_size = int(CONFIG["SAMPLE_RATE"] * 0.05)
    
    def callback(indata, frames, time_info, status):
        if status:
            logger.warning(f"Aufnahme-Status-Meldung: {status}")
        if is_recording.is_set():
            audio_queue.put(indata.copy())

    try:
        with sd.InputStream(samplerate=CONFIG["SAMPLE_RATE"], channels=CONFIG["CHANNELS"], callback=callback, blocksize=block_size) as stream:
            logger.info(f"Aufnahme läuft mit Samplerate: {stream.samplerate}, Kanälen: {stream.channels}, Blocksize: {block_size}...")
            while is_recording.is_set():
                time.sleep(0.1)
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
    return text if text else None

# --- Transkriptions- und Sende-Funktion an Backend über WebSocket ---
async def transcribe_and_send_to_backend():
    audio_buffer_for_transcription = []
    samples_per_chunk = int(CONFIG["CHUNK_DURATION_SEC"] * CONFIG["SAMPLE_RATE"])
    
    global_audio_time_offset = 0.0

    stt_client_id = f"stt_instance_{uuid4()}"
    websocket_uri_with_id = f"{CONFIG['WEBSOCKET_URI']}/{stt_client_id}"

    logger.info(f"STT Client ID: {stt_client_id}")
    logger.info(f"Versuche, eine Verbindung zum WebSocket unter {websocket_uri_with_id} herzustellen...")

    current_sentence_words = []
    last_emitted_word_end_time_global = 0.0
    first_word_start_time_global = None

    reconnect_attempt = 0
    MAX_RECONNECT_ATTEMPTS = 10
    BASE_RECONNECT_DELAY = 1

    while is_recording.is_set():
        try:
            async with websockets.connect(websocket_uri_with_id) as websocket:
                logger.info("WebSocket-Verbindung zum Backend hergestellt.")
                reconnect_attempt = 0
                
                initial_message_payload = {
                    "message": "STT service connected"
                }
                initial_message = {
                    "id": str(uuid4()),
                    "type": "stt.init",
                    "timestamp": time.time(),
                    "payload": initial_message_payload,
                    "origin": "stt_module",
                    "client_id": stt_client_id
                }
                await websocket.send(json.dumps(initial_message))
                logger.debug(f"Gesendet an Backend (initial): {initial_message['type']} from {initial_message['client_id']}")

                while is_recording.is_set():
                    while not audio_queue.empty():
                        data = audio_queue.get()
                        audio_buffer_for_transcription.append(data)

                    if sum(a.shape[0] for a in audio_buffer_for_transcription) >= samples_per_chunk:
                        full_audio_data = np.concatenate(audio_buffer_for_transcription, axis=0)
                        
                        audio_to_transcribe_chunk = full_audio_data[:samples_per_chunk]
                        remaining_audio = full_audio_data[samples_per_chunk:]

                        audio_buffer_for_transcription = [remaining_audio] if remaining_audio.shape[0] > 0 else []
                        
                        audio_data_flat = audio_to_transcribe_chunk.flatten().astype(np.float32)

                        try:
                            segments, info = model.transcribe(
                                audio_data_flat,
                                language=CONFIG["LANGUAGE"],
                                beam_size=5,
                                word_timestamps=True,
                                vad_filter=True,
                                vad_parameters=VAD_PARAMS
                            )

                            for segment in segments:
                                if segment.words is not None:
                                    for word_info in segment.words:
                                        word_end_time_global = global_audio_time_offset + word_info.end
                                        
                                        if word_end_time_global > last_emitted_word_end_time_global:
                                            current_sentence_words.append(word_info.word)
                                            last_emitted_word_end_time_global = word_end_time_global

                                            if first_word_start_time_global is None:
                                                first_word_start_time_global = global_audio_time_offset + word_info.start

                                            if word_info.word.strip().endswith((".", "?", "!")) and len(current_sentence_words) >= CONFIG["MIN_WORDS_PER_SENTENCE"]:
                                                full_sentence = " ".join(current_sentence_words).strip()
                                                await send_sentence(full_sentence, websocket, info, stt_client_id)
                                                current_sentence_words.clear()
                                                first_word_start_time_global = None

                                            elif first_word_start_time_global is not None and (word_end_time_global - first_word_start_time_global) > CONFIG["MAX_SENTENCE_DURATION_SECONDS"]:
                                                full_sentence = " ".join(current_sentence_words).strip()
                                                await send_sentence(full_sentence, websocket, info, stt_client_id)
                                                current_sentence_words.clear()
                                                first_word_start_time_global = None
                            
                            global_audio_time_offset += CONFIG["CHUNK_DURATION_SEC"]

                        except Exception as e:
                            logger.error(f"Fehler bei der Transkription oder beim Senden: {e}", exc_info=True)

                    await asyncio.sleep(0.01)

        except websockets.exceptions.WebSocketException as e:
            reconnect_attempt += 1
            if reconnect_attempt <= MAX_RECONNECT_ATTEMPTS:
                delay = BASE_RECONNECT_DELAY * (2 ** (reconnect_attempt - 1))
                logger.warning(f"WebSocket-Fehler ({type(e).__name__}): {e}. Verbindung verloren. Versuche erneut in {delay:.1f} Sekunden (Versuch {reconnect_attempt}/{MAX_RECONNECT_ATTEMPTS})...", exc_info=True)
                await asyncio.sleep(delay)
            else:
                logger.critical(f"Maximale WebSocket-Wiederverbindungsversuche ({MAX_RECONNECT_ATTEMPTS}) erreicht. Beende Transkriptionsmodul.", exc_info=True)
                is_recording.clear()
        except Exception as e:
            logger.critical(f"Ein unerwarteter Fehler im Transkriptions-Loop (Hauptschleife): {e}", exc_info=True)
            await asyncio.sleep(5)

    logger.info("Transkriptions- und Sende-Loop beendet.")

async def send_sentence(sentence, websocket, info, client_id):
    if sentence:
        transcription_payload = {
            "text": sentence,
            "language": info.language,
            "confidence": info.language_probability
        }
        message = {
            "id": str(uuid4()),
            "type": "stt.transcription",
            "timestamp": time.time(),
            "payload": transcription_payload,
            "origin": "stt_module",
            "client_id": client_id
        }
        await websocket.send(json.dumps(message))
        logger.debug(f"Gesendet an Backend (Satz): {sentence[:50]}...")

# --- Hauptausführung ---
if __name__ == "__main__":
    try:
        # Starte den Audio-Aufnahme-Thread
        threading.Thread(target=record_audio, daemon=True).start()
        # Starte den Haupt-Transkriptions-Loop
        asyncio.run(transcribe_and_send_to_backend())
    except KeyboardInterrupt:
        logger.info("Skript durch Benutzer beendet.")
    finally:
        is_recording.clear()
        logger.info("Cleanup abgeschlossen. Beende Programm.")