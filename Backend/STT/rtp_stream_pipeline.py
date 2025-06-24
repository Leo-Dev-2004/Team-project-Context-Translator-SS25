import asyncio
import websockets
import whisper
import numpy as np
import sounddevice as sd
import queue
import threading
import time
import json
import re

CHUNK_DURATION_SEC = 5
SAMPLE_RATE = 16000
CHANNELS = 1
WEBSOCKET_URI = "ws://localhost:8000/ws"

model = whisper.load_model("tiny")

audio_queue = queue.Queue()

def record_audio():
    def callback(indata, frames, time_info, status):
        audio_queue.put(indata.copy())

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, callback=callback):
        while True:
            sd.sleep(1000)

threading.Thread(target=record_audio, daemon=True).start()

def clean_transcription(text):
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    return text if text else None

async def transcribe_and_send():
    async with websockets.connect(WEBSOCKET_URI) as websocket:
        buffer = []
        last_chunk_time = time.time()

        while True:
            if not audio_queue.empty():
                data = audio_queue.get()
                buffer.append(data)

            if time.time() - last_chunk_time >= CHUNK_DURATION_SEC:
                if buffer:
                    audio_chunk = np.concatenate(buffer, axis=0)
                    buffer = []
                    last_chunk_time = time.time()

                    audio_data = audio_chunk.flatten().astype(np.float32)

                    result = model.transcribe(audio_data, language="en", fp16=False)
                    text = clean_transcription(result["text"])
                    timestamp = time.time()

                    if text:
                        message = {
                            "type": "transcription",
                            "timestamp": timestamp,
                            "text": text
                        }

                        print(f"[{timestamp:.2f}] {text}")
                        await websocket.send(json.dumps(message))

if __name__ == "__main__":
    asyncio.run(transcribe_and_send())