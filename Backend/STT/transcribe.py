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
CHUNK_DURATION_SEC = 1.0  # Process smaller chunks more frequently for responsiveness
SAMPLE_RATE = 16000
CHANNELS = 1
MODEL_SIZE = "small"
LANGUAGE = "en"
WEBSOCKET_URI = "ws://localhost:8000/ws"

# --- New: Silence Threshold for Sending Transcriptions ---
# If no new speech is detected for this duration, send the current buffered text.
SILENCE_TIMEOUT_FOR_SEND_SEC = 1.0
# Minimum number of characters before considering a transcription ready to send
MIN_CHARS_FOR_SEND = 5

# --- Logging konfigurieren ---
# Set default logging level to INFO for better visibility during development
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Globale Variablen ---
model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")

audio_queue = queue.Queue()
is_recording = threading.Event()
is_recording.set()

# --- VAD-Einstellungen (passed to faster_whisper) ---
VAD_PARAMS = dict(
    min_silence_duration_ms=500, # Shorter silence to detect end of segment
    max_speech_duration_s=15,    # Max segment length for VAD
    threshold=0.6                # VAD threshold (adjust based on environment noise)
)

# --- Buffer für gesammelten Text und Timing ---
current_buffered_text = ""
last_segment_end_time = 0.0 # Tracks the end time of the last processed segment
last_transcription_send_time = time.time() # Tracks when the last full transcription was sent

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
                sd.sleep(100) # Sleep less to be more responsive to shutdown
    except Exception as e:
        logger.critical(f"Fehler bei der Audioaufnahme: {e}", exc_info=True)
    finally:
        logger.info("Audioaufnahme beendet.")

# Start the audio recording thread
threading.Thread(target=record_audio, daemon=True).start()

# --- Textbereinigungs-Funktion ---
def clean_transcription(text):
    text = text.strip()
    text = re.sub(r'\s+', ' ', text) # Replace multiple spaces with a single one
    # Only remove leading/trailing punctuation if it's not part of a sentence end
    # For robust sentence end detection, you might want a more sophisticated NLTK-based approach
    # For now, let's just strip common trailing punctuation that might be a transcription artifact.
    text = re.sub(r'[\.,!?]$', '', text).strip() # Remove trailing . , ! ?
    return text if text else None

# --- Helper to send messages over WebSocket ---
async def send_websocket_message(websocket, msg_type, payload, client_id):
    message = {
        "id": str(uuid4()),
        "type": msg_type,
        "timestamp": time.time(),
        "payload": payload,
        "origin": "stt_module",
        "client_id": client_id
    }
    await websocket.send(json.dumps(message))
    logger.info(f"Gesendet an Backend ({msg_type}): {payload.get('text', str(payload))[:100]}...")


# --- Transkriptions- und Sende-Funktion an Backend über WebSocket ---
async def transcribe_and_send_to_backend():
    """
    Connects to the backend WebSocket, transcribes audio chunks, and sends the text
    when a silence pause is detected or a max duration/size is reached.
    """
    global current_buffered_text, last_segment_end_time, last_transcription_send_time

    audio_buffer_for_whisper = []
    # Collect enough samples for a reasonable whisper processing chunk,
    # but still process queue frequently
    min_samples_for_whisper_processing = int(CHUNK_DURATION_SEC * SAMPLE_RATE)

    stt_client_id = f"stt_instance_{uuid4()}"
    websocket_uri_with_id = f"{WEBSOCKET_URI}/{stt_client_id}"

    logger.info(f"STT Client ID: {stt_client_id}")
    logger.info(f"Versuche, eine Verbindung zum WebSocket unter {websocket_uri_with_id} herzustellen...")

    while is_recording.is_set():
        try:
            async with websockets.connect(websocket_uri_with_id) as websocket:
                logger.info("WebSocket-Verbindung zum Backend hergestellt.")

                # Initial message
                initial_payload = {"message": "STT service connected"}
                await send_websocket_message(websocket, "stt.init", initial_payload, stt_client_id)
                
                # Reset buffers for new connection
                current_buffered_text = ""
                last_segment_end_time = 0.0
                last_transcription_send_time = time.time() # Reset this on reconnect too


                while is_recording.is_set():
                    # --- Collect audio from queue ---
                    while not audio_queue.empty():
                        data = audio_queue.get()
                        audio_buffer_for_whisper.append(data.flatten().astype(np.float32))

                    # --- Process with Whisper if enough audio is collected ---
                    if len(audio_buffer_for_whisper) > 0 and \
                       sum(arr.shape[0] for arr in audio_buffer_for_whisper) >= min_samples_for_whisper_processing:
                        
                        full_audio_data = np.concatenate(audio_buffer_for_whisper)
                        audio_buffer_for_whisper = [] # Clear buffer after processing

                        try:
                            # Use stream=True for continuous transcription if needed,
                            # but for sentence-based sending, processing chunks then segmenting is fine.
                            # The VAD filter within transcribe will help with silence detection.
                            segments_generator, info = model.transcribe(
                                full_audio_data,
                                language=LANGUAGE,
                                beam_size=5,
                                word_timestamps=True,
                                vad_filter=True,
                                vad_parameters=VAD_PARAMS
                            )

                            current_time = time.time()
                            has_new_speech = False

                            for segment in segments_generator:
                                has_new_speech = True
                                cleaned_segment_text = clean_transcription(segment.text)
                                if cleaned_segment_text:
                                    current_buffered_text += (" " + cleaned_segment_text).strip()
                                last_segment_end_time = segment.end # Use segment end for silence check

                            # --- Logic for sending transcription ---
                            # Send if:
                            # 1. A silence timeout has occurred AND there is buffered text
                            # 2. Or, if current_buffered_text is very long (fallback to prevent infinite buffering)
                            # 3. Or, if a segment explicitly ends with common punctuation and is of reasonable length
                            
                            # Check for silence timeout
                            if (current_time - last_segment_end_time > SILENCE_TIMEOUT_FOR_SEND_SEC or \
                               (time.time() - last_transcription_send_time > MAX_SENTENCE_DURATION_SECONDS and current_buffered_text)) \
                                and len(current_buffered_text) >= MIN_CHARS_FOR_SEND:

                                # Check if the last part of the buffered text ends with punctuation
                                # This is a heuristic, VAD silence is more reliable
                                ends_with_punctuation = bool(re.search(r'[.!?]$', current_buffered_text.strip()))

                                if current_buffered_text and (ends_with_punctuation or (current_time - last_transcription_send_time > SILENCE_TIMEOUT_FOR_SEND_SEC)):
                                    
                                    payload = {
                                        "text": current_buffered_text,
                                        "language": info.language if 'info' in locals() else LANGUAGE,
                                        "confidence": info.language_probability if 'info' in locals() else 1.0
                                    }
                                    await send_websocket_message(websocket, "stt.transcription", payload, stt_client_id)
                                    current_buffered_text = ""  # Clear buffer after sending
                                    last_transcription_send_time = time.time() # Update last send time

                            # If no new speech was detected for a while, and there's buffered text, send it
                            # This handles cases where VAD_FILTER might be too aggressive or there's a long pause.
                            elif not has_new_speech and current_buffered_text and \
                                 (time.time() - last_transcription_send_time > SILENCE_TIMEOUT_FOR_SEND_SEC):
                                
                                payload = {
                                    "text": current_buffered_text,
                                    "language": info.language if 'info' in locals() else LANGUAGE,
                                    "confidence": info.language_probability if 'info' in locals() else 1.0
                                }
                                await send_websocket_message(websocket, "stt.transcription", payload, stt_client_id)
                                current_buffered_text = ""
                                last_transcription_send_time = time.time()
                                

                        except Exception as e:
                            logger.error(f"Fehler bei der Transkription oder beim Senden: {e}", exc_info=True)
                    
                    # Short sleep to prevent busy-waiting and allow other tasks to run
                    await asyncio.sleep(0.05) 

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