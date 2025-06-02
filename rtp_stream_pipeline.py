import subprocess
import threading
import queue
import whisper
import numpy as np
import soundfile as sf

# === Parameter Settings ===
CHUNK_DURATION_SEC = 10      # Duration of each audio chunk (in seconds)
OVERLAP_SEC = 2              # Overlap duration (in seconds)
SAMPLE_RATE = 48000          # Sampling rate in Hz
CHANNELS = 1                 # Mono audio recommended for transcription
SAMPLE_WIDTH = 2             # 16-bit audio = 2 bytes
CHUNK_SIZE = SAMPLE_RATE * SAMPLE_WIDTH * CHANNELS * CHUNK_DURATION_SEC
OVERLAP_SIZE = SAMPLE_RATE * SAMPLE_WIDTH * CHANNELS * OVERLAP_SEC

# === Shared Resources ===
audio_queue = queue.Queue()
buffer = b""  # Initial buffer for accumulating audio data

# === RTP Audio Stream to WAV PCM using ffmpeg ===
def ffmpeg_stream_to_queue(sdp_file: str, audio_queue: queue.Queue):
    process = subprocess.Popen([
        'ffmpeg',
        '-protocol_whitelist', 'file,udp,rtp',
        '-i', sdp_file,
        '-acodec', 'pcm_s16le',
        '-ar', str(SAMPLE_RATE),
        '-ac', str(CHANNELS),
        '-f', 'wav', 'pipe:1'
    ], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    while True:
        data = process.stdout.read(4096)
        if not data:
            break
        audio_queue.put(data)

# === Chunking audio data with overlap ===
def chunk_audio_stream(audio_queue: queue.Queue):
    global buffer
    while True:
        data = audio_queue.get()
        buffer += data
        while len(buffer) >= CHUNK_SIZE:
            chunk = buffer[:CHUNK_SIZE]
            buffer = buffer[CHUNK_SIZE - OVERLAP_SIZE:]  # keep overlap
            yield chunk

# === Load Whisper model once ===
model = whisper.load_model("base")

# === Transcribe each chunk using Whisper ===
def transcribe_chunk(chunk_data: bytes):
    with open("temp_chunk.wav", "wb") as f:
        f.write(chunk_data)

    audio_np, _ = sf.read("temp_chunk.wav", dtype="float32")

    result = model.transcribe(audio_np, fp16=False)
    print("[Whisper] Transcription:", result["text"])

# === Start background thread to receive audio ===
threading.Thread(
    target=ffmpeg_stream_to_queue,
    args=("input.sdp", audio_queue),
    daemon=True
).start()

# === Main processing loop ===
for chunk in chunk_audio_stream(audio_queue):
    transcribe_chunk(chunk)