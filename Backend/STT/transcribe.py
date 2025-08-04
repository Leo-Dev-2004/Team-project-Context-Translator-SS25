# Backend/STT/transcribe.py (REVISED)

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
CHUNK_DURATION_SEC = 0.5 # Smaller chunks for lower latency
SAMPLE_RATE = 16000
CHANNELS = 1
MODEL_SIZE = "medium" # Adjust as needed / performance requirements
LANGUAGE = "de" # Change to English or other languages as needed
WEBSOCKET_URI = "ws://localhost:8000/ws"

MIN_WORDS_PER_SENTENCE = 3
MAX_SENTENCE_DURATION_SECONDS = 15

# --- Logging konfigurieren ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Globale Variablen ---
model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8") # Consider 'cuda' for GPU, or smaller models
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
    # This buffer should be very short, just enough to handle sounddevice's internal block size
    # frames_per_buffer = int(SAMPLE_RATE * CHUNK_DURATION_SEC / 4) # e.g., 125ms buffer for sounddevice
    # You might need to experiment with blocksize or let sounddevice choose.
    
    # We remove sd.sleep(1000) entirely or reduce it significantly.
    # The callback handles pushing data. The while loop just keeps the stream active.
    
    # Using a small blocksize can reduce latency from the audio input side.
    block_size = int(SAMPLE_RATE * 0.05) # Process audio in 50ms blocks internally
    
    def callback(indata, frames, time_info, status):
        if status:
            logger.warning(f"Aufnahme-Status-Meldung: {status}")
        # Only put data if recording is active to avoid queue buildup after stop
        if is_recording.is_set():
            audio_queue.put(indata.copy())

    try:
        # The .start() call on InputStream keeps it running. The while loop is for graceful shutdown.
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, callback=callback, blocksize=block_size) as stream:
            logger.info(f"Aufnahme läuft mit Samplerate: {stream.samplerate}, Kanälen: {stream.channels}, Blocksize: {stream.blocksize}...")
            # Keep the main thread alive without blocking heavily
            while is_recording.is_set():
                time.sleep(0.1) # Sleep briefly to yield CPU, but not block audio collection
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
    # This now correctly retains punctuation at the end of words/sentences if the model provides it
    return text if text else None

# --- Transkriptions- und Sende-Funktion an Backend über WebSocket ---
async def transcribe_and_send_to_backend():
    """
    Connects to the backend WebSocket, transcribes audio chunks, and sends the text.
    """
    audio_buffer_for_transcription = [] # Buffer for audio currently being accumulated for transcription
    samples_per_chunk = int(CHUNK_DURATION_SEC * SAMPLE_RATE)
    
    # Global audio time offset to track absolute word timestamps
    global_audio_time_offset = 0.0 # Will accumulate chunk_duration_sec

    stt_client_id = f"stt_instance_{uuid4()}"
    websocket_uri_with_id = f"{WEBSOCKET_URI}/{stt_client_id}"

    logger.info(f"STT Client ID: {stt_client_id}")
    logger.info(f"Versuche, eine Verbindung zum WebSocket unter {websocket_uri_with_id} herzustellen...")

    # --- Initialize state variables for this function call ---
    current_sentence_words = []
    last_emitted_word_end_time_global = 0.0 # This tracks the global end time of the last *emitted* word
    first_word_start_time_global = None # This tracks the global start time of the current sentence

    # Add retry logic variables
    reconnect_attempt = 0
    MAX_RECONNECT_ATTEMPTS = 10
    BASE_RECONNECT_DELAY = 1 # seconds

    while is_recording.is_set():
        try:
            async with websockets.connect(websocket_uri_with_id) as websocket:
                logger.info("WebSocket-Verbindung zum Backend hergestellt.")
                reconnect_attempt = 0 # Reset on successful connection
                
                # MODIFICATION 1: Initial message now conforms to UniversalMessage
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

                # Inner loop for continuous transcription while connected
                while is_recording.is_set():
                    # Accumulate audio data until we have enough for a chunk
                    while not audio_queue.empty():
                        data = audio_queue.get()
                        audio_buffer_for_transcription.append(data)

                    # Only transcribe if we have at least one full chunk duration
                    if sum(a.shape[0] for a in audio_buffer_for_transcription) >= samples_per_chunk:
                        full_audio_data = np.concatenate(audio_buffer_for_transcription, axis=0)
                        
                        audio_to_transcribe_chunk = full_audio_data[:samples_per_chunk]
                        remaining_audio = full_audio_data[samples_per_chunk:]

                        audio_buffer_for_transcription = [remaining_audio] if remaining_audio.shape[0] > 0 else []
                        
                        audio_data_flat = audio_to_transcribe_chunk.flatten().astype(np.float32)

                        try:
                            segments, info = model.transcribe(
                                audio_data_flat,
                                language=LANGUAGE,
                                beam_size=5,
                                word_timestamps=True,
                                vad_filter=True,
                                vad_parameters=VAD_PARAMS
                            )

                            # Process words from the transcribed chunk relative to the global offset
                            for segment in segments:
                                if segment.words is not None:
                                    for word_info in segment.words:
                                        # Calculate global end time for the word
                                        word_end_time_global = global_audio_time_offset + word_info.end
                                        
                                        # Only process if this word is "new" (its end time is beyond the last emitted word's end time)
                                        # This helps prevent duplicates from overlapping faster-whisper segments.
                                        if word_end_time_global > last_emitted_word_end_time_global:
                                            current_sentence_words.append(word_info.word)
                                            last_emitted_word_end_time_global = word_end_time_global

                                            if first_word_start_time_global is None:
                                                first_word_start_time_global = global_audio_time_offset + word_info.start

                                            # Sentence completion by punctuation
                                            if word_info.word.strip().endswith((".", "?", "!")) and len(current_sentence_words) >= MIN_WORDS_PER_SENTENCE:
                                                full_sentence = " ".join(current_sentence_words).strip()
                                                await send_sentence(full_sentence, websocket, info, stt_client_id)
                                                current_sentence_words.clear()
                                                first_word_start_time_global = None # Reset sentence start time

                                            # Sentence completion by duration
                                            elif first_word_start_time_global is not None and (word_end_time_global - first_word_start_time_global) > MAX_SENTENCE_DURATION_SECONDS:
                                                full_sentence = " ".join(current_sentence_words).strip()
                                                await send_sentence(full_sentence, websocket, info, stt_client_id)
                                                current_sentence_words.clear()
                                                first_word_start_time_global = None # Reset sentence start time
                            
                            # Update the global audio time offset for the next chunk
                            global_audio_time_offset += CHUNK_DURATION_SEC

                            # If there are any remaining words in current_sentence_words after a long pause
                            # (not explicitly a problem you listed, but a common improvement for 'not transcribed at all' scenarios)
                            # You might want to add a timeout/flush logic here if no new words come for a while.
                            # For simplicity, we'll leave it as is, relying on punctuation/duration for now.

                        except Exception as e:
                            logger.error(f"Fehler bei der Transkription oder beim Senden: {e}", exc_info=True)

                    await asyncio.sleep(0.01) # Yield control briefly

        except websockets.exceptions.WebSocketException as e:
            reconnect_attempt += 1
            if reconnect_attempt <= MAX_RECONNECT_ATTEMPTS:
                delay = BASE_RECONNECT_DELAY * (2 ** (reconnect_attempt - 1))
                logger.warning(f"WebSocket-Fehler ({type(e).__name__}): {e}. Verbindung verloren. Versuche erneut in {delay:.1f} Sekunden (Versuch {reconnect_attempt}/{MAX_RECONNECT_ATTEMPTS})...", exc_info=True)
                await asyncio.sleep(delay)
            else:
                logger.critical(f"Maximale WebSocket-Wiederverbindungsversuche ({MAX_RECONNECT_ATTEMPTS}) erreicht. Beende Transkriptionsmodul.", exc_info=True)
                is_recording.clear() # Stop the loop if max attempts reached
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
        logger.info(f"Gesendet an Backend (Satz): {sentence[:50]}...")

# --- Hauptausführung ---
if __name__ == "__main__":
    try:
        asyncio.run(transcribe_and_send_to_backend())
    except KeyboardInterrupt:
        logger.info("Skript durch Benutzer beendet.")
    finally:
        is_recording.clear()
        logger.info("Cleanup abgeschlossen. Beende Programm.")