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
    MODEL_SIZE = "tiny"
    LANGUAGE = "en"
    WEBSOCKET_URI = "ws://localhost:8000/ws"
    MIN_WORDS_PER_SENTENCE = 6 # Reduced for better responsiveness
    
    # VAD (Voice Activity Detection) settings are key for responsiveness
    VAD_ENERGY_THRESHOLD = 0.0035 # Energy threshold to detect speech
    VAD_SILENCE_DURATION_S = 0.35  # How long of a pause indicates end of sentence
    VAD_BUFFER_DURATION_S = 0.5 # Seconds of silence to keep before speech starts
    
    # Heartbeat settings to prevent connection timeouts during silence
    HEARTBEAT_INTERVAL_S = 5.0 # Send heartbeat every 10 seconds during silence (30s default was too long)
    
    # STREAMING OPTIMIZATION SETTINGS
    STREAMING_ENABLED = True # Enable streaming transcription for long speech
    STREAMING_CHUNK_DURATION_S = 3.5 # Process chunks every N seconds during speech
    STREAMING_OVERLAP_DURATION_S = 0.8 # Overlap between chunks for context
    STREAMING_MIN_BUFFER_S = 3.0 # Minimum buffer before starting streaming

    # Maximum duration (seconds) for any single chunk that is transcribed/sent.
    MAX_CHUNK_DURATION_S = 14.0

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
        self.model = WhisperModel(Config.MODEL_SIZE, device="auto", compute_type="int8")
        logger.info("Whisper model loaded.")
        self.audio_queue = asyncio.Queue()
        self.is_recording = threading.Event()
        self.is_recording.set()
        
        # Streaming transcription state
        self.streaming_processor = None
        self.streaming_active = False
        self.processed_chunks = []  # Store processed chunk results
        self.unsent_sentences = []  # Buffer for unsent sentences
        logger.info(f"STTService initialized for session {self.user_session_id}")
        if Config.STREAMING_ENABLED:
            logger.info("Streaming transcription optimization enabled")

    def _record_audio_thread(self):
        """[Thread Target] Captures audio from microphone into a thread-safe queue."""
        def callback(indata, frames, time_info, status):
            if status: logger.warning(f"Recording status: {status}")
            if self.is_recording.is_set(): self.audio_queue.put_nowait(indata.copy())
            
        try:
            with sd.InputStream(samplerate=Config.SAMPLE_RATE, channels=Config.CHANNELS, callback=callback, dtype='float32') as stream:
                logger.info(f"Recording active: {stream.samplerate}Hz, {stream.channels}ch")
                while self.is_recording.is_set(): time.sleep(0.1)
        except Exception as e:
            logger.critical(f"Audio recording error: {e}", exc_info=True)
        finally:
            logger.info("Audio recording stopped.")

    async def _send_sentence(self, websocket, sentence: str, is_interim: bool = False):
        """Formats and sends a transcribed sentence over the WebSocket."""
        
        if is_interim:
            return  # Skip filtering for interim results
        
        if not sentence or not sentence.strip():
            logger.warning("STTService: Blocked empty or whitespace-only transcription from being sent.")
            return

        transcription_logger.info(f"{'[INTERIM]' if is_interim else '[FINAL]'} {sentence}")
        message_type = "stt.transcription.interim" if is_interim else "stt.transcription"
        
        # Filter out common Whisper hallucination patterns that occur during silence
        sentence_lower = sentence.lower().strip()
        
        # Define patterns with different strictness levels
        # Very strict patterns - block even with extra content
        strict_patterns = [
            "thanks for watching", "thank you for watching", 
            "please like and subscribe", "don't forget to subscribe",
            "hit that subscribe button", "smash that like button"
        ]
        
        # Moderate patterns - block if they dominate the sentence
        moderate_patterns = [
            "see you next time", "that's all for today", "until next time",
            "catch you later", "thanks for your attention", "thank you for your time",
            "appreciate you watching", "goodbye", "bye bye"
        ]
        
        # Simple patterns - only block if they're the entire sentence
        simple_patterns = ["thanks", "thank you"]
        
        # Check for multiple patterns (even if individually they wouldn't be blocked)
        pattern_count = 0
        found_patterns = []
        all_patterns = strict_patterns + moderate_patterns + simple_patterns
        for pattern in all_patterns:
            if pattern in sentence_lower:
                pattern_count += 1
                found_patterns.append(pattern)
        
        # If multiple patterns found, be more aggressive about blocking
        if pattern_count >= 2:
            # Calculate how much of the sentence is NOT pattern-related
            clean_text = sentence_lower
            for pattern in found_patterns:
                clean_text = clean_text.replace(pattern, "")
            clean_text = clean_text.strip()
            non_filler_words = [w for w in clean_text.split() if w not in ["for", "and", "the", "a", "to", "my", "your", "our", "everyone", "today", ","]]
            if len(non_filler_words) < 3:
                logger.warning(f"STTService: Blocked likely Whisper hallucination (multiple patterns): '{sentence}'")
                return
        
        # Check strict patterns - block even with some extra content
        for pattern in strict_patterns:
            if pattern in sentence_lower:
                # Allow if it's clearly in a different context (has substantial other content)
                clean_text = sentence_lower.replace(pattern, "").strip()
                non_filler_words = [w for w in clean_text.split() if w not in ["for", "and", "the", "a", "to", "my", "your", "our"]]
                if len(non_filler_words) < 3:  # Less than 3 meaningful words left
                    logger.warning(f"STTService: Blocked likely Whisper hallucination: '{sentence}'")
                    return
        
        # Check moderate patterns - block if they dominate
        for pattern in moderate_patterns:
            if pattern in sentence_lower:
                clean_text = sentence_lower.replace(pattern, "").strip()
                non_filler_words = [w for w in clean_text.split() if w not in ["for", "and", "the", "a", "to", "my", "your", "our", "everyone", "today"]]
                if len(non_filler_words) < 2:  # Less than 2 meaningful words left
                    logger.warning(f"STTService: Blocked likely Whisper hallucination: '{sentence}'")
                    return
        
        # Check simple patterns - only block if entire sentence
        for pattern in simple_patterns:
            if sentence_lower.strip() == pattern:
                logger.warning(f"STTService: Blocked likely Whisper hallucination: '{sentence}'")
                return

        transcription_logger.info(sentence)
        message = {
            "id": str(uuid4()), "type": message_type, "timestamp": time.time(),
            "payload": {
                "text": sentence, "language": Config.LANGUAGE,
                "user_session_id": self.user_session_id,
                "is_interim": is_interim
            },
            "origin": "stt_module", "client_id": self.stt_client_id
        }
        
        # Check if websocket is still open before attempting to send
        if not websocket.open:
            
            logger.warning(f"Cannot send sentence - WebSocket is not open. Buffering for retry.")
            self.unsent_sentences.append(message)
            return
            
        try:
            await websocket.send(json.dumps(message))
            # logger.info(f"Sent {'interim' if is_interim else 'final'}: {sentence}")
        except websockets.exceptions.ConnectionClosed:
            # Connection closed - buffer for retry
            logger.info(f"Cannot send sentence - WebSocket connection closed. Buffering for retry.")
            self.unsent_sentences.append(message)
        except Exception as e:
            # Unexpected error - buffer and log warning
            logger.warning(f"Failed to send sentence, unexpected error: {e}. Buffering for retry.")
            self.unsent_sentences.append(message)

    async def _process_streaming_chunk(self, audio_chunk: np.ndarray, chunk_index: int):
        """Process a streaming audio chunk in the background.
        Returns a list of chunk_info dicts. Each returned chunk_info corresponds to
        at most Config.MAX_CHUNK_DURATION_S seconds of audio.
        """
        try:
            total_samples = len(audio_chunk)
            chunk_duration = total_samples / Config.SAMPLE_RATE
            logger.info(f"Processing streaming chunk {chunk_index} ({chunk_duration:.2f}s)")
            
            # If the chunk is within the max allowed duration, process normally
            max_samples = int(Config.MAX_CHUNK_DURATION_S * Config.SAMPLE_RATE)
            results = []
            
            if total_samples <= max_samples:
                start_time = time.monotonic()
                segments, _ = await asyncio.to_thread(
                    self.model.transcribe, audio_chunk, language=Config.LANGUAGE
                )
                processing_time = time.monotonic() - start_time
                
                result_text = "".join(s.text for s in segments).strip()
                
                chunk_info = {
                    'index': chunk_index,
                    'text': result_text,
                    'duration': chunk_duration,
                    'processing_time': processing_time,
                    'timestamp': time.time()
                }
                
                logger.info(f"Chunk {chunk_index} processed in {processing_time:.2f}s: '{result_text}'")
                results.append(chunk_info)
                return results
            
            # If the chunk is too long, split into multiple subchunks (no overlap),
            # process each subchunk and return a list of chunk infos.
            logger.info(f"Chunk {chunk_index} exceeds max duration ({chunk_duration:.2f}s > {Config.MAX_CHUNK_DURATION_S}s). Splitting...")
            start_sample = 0
            part_idx = 0
            while start_sample < total_samples:
                end_sample = min(start_sample + max_samples, total_samples)
                part_audio = audio_chunk[start_sample:end_sample]
                part_duration = len(part_audio) / Config.SAMPLE_RATE
                
                start_time = time.monotonic()
                segments, _ = await asyncio.to_thread(
                    self.model.transcribe, part_audio, language=Config.LANGUAGE
                )
                processing_time = time.monotonic() - start_time
                
                part_text = "".join(s.text for s in segments).strip()
                
                part_info = {
                    'index': f"{chunk_index}.{part_idx}",
                    'text': part_text,
                    'duration': part_duration,
                    'processing_time': processing_time,
                    'timestamp': time.time()
                }
                
                logger.info(f"Subchunk {chunk_index}.{part_idx} processed in {processing_time:.2f}s: '{part_text}'")
                results.append(part_info)
                
                part_idx += 1
                start_sample = end_sample
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing streaming chunk {chunk_index}: {e}", exc_info=True)
            return None

    async def _start_streaming_processing(self, websocket, initial_buffer):
        """Start streaming processing for long speech segments."""
        if not Config.STREAMING_ENABLED or self.streaming_active:
            return
            
        self.streaming_active = True
        self.processed_chunks = []
        
        logger.info("Starting streaming transcription processing")
        
        try:
            # Process initial chunk
            chunk_audio = np.concatenate([chunk.flatten() for chunk in initial_buffer])
            chunk_infos = await self._process_streaming_chunk(chunk_audio, 0)
            
            if chunk_infos:
                for ci in chunk_infos:
                    if ci and ci.get('text'):
                        self.processed_chunks.append(ci)
                        # Send interim result for each sub-chunk
                        await self._send_sentence(websocket, ci['text'], is_interim=True)
                
        except Exception as e:
            logger.error(f"Error starting streaming processing: {e}", exc_info=True)
            self.streaming_active = False

    async def _process_streaming_buffer_chunk(self, websocket, buffer_chunk, chunk_index):
        """Process additional streaming chunks while speech continues."""
        if not self.streaming_active:
            return
            
        try:
            chunk_audio = np.concatenate([chunk.flatten() for chunk in buffer_chunk])
            chunk_infos = await self._process_streaming_chunk(chunk_audio, chunk_index)
            
            if chunk_infos:
                for ci in chunk_infos:
                    if ci and ci.get('text'):
                        self.processed_chunks.append(ci)
                        # Send interim result for each sub-chunk
                        await self._send_sentence(websocket, ci['text'], is_interim=True)
                
        except Exception as e:
            logger.error(f"Error processing streaming buffer chunk: {e}", exc_info=True)

    def _consolidate_streaming_results(self):
        """Consolidate streaming results into final transcription."""
        if not self.processed_chunks:
            return ""
            
        # Simple concatenation for now - could be improved with overlap handling
        consolidated = " ".join(chunk['text'] for chunk in self.processed_chunks if chunk['text'])
        
        logger.info(f"Consolidated {len(self.processed_chunks)} streaming chunks into final result")
        return consolidated.strip()

    async def _send_heartbeat(self, websocket):
        """Sends a heartbeat keep-alive message to prevent connection timeout."""
        # Check if websocket is still open before attempting to send
        if not websocket.open:
            logger.debug("Skipping heartbeat - WebSocket is not open")
            return
            
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
        except websockets.exceptions.ConnectionClosed:
            # Connection closed gracefully or unexpectedly - this is normal during shutdown
            logger.debug("Cannot send heartbeat - WebSocket connection closed")
        except Exception as e:
            # Only log warnings for unexpected errors, not connection closure
            logger.warning(f"Failed to send heartbeat, unexpected error: {e}")

    async def _process_audio_loop(self, websocket):
        """[Async Task] Implements the VAD-based 'record-then-transcribe' logic with streaming optimization."""
        logger.info("Entered _process_audio_loop")
        audio_buffer = []
        is_speaking = False
        silence_start_time = None
        last_heartbeat_time = time.monotonic()
        last_activity_time = time.monotonic()  # Track last transcription or significant activity
        
        # Streaming processing state
        speech_start_time = None
        last_streaming_process_time = None
        streaming_chunk_index = 0
        
        # Keep a small buffer of recent silence to catch the start of speech
        silence_buffer_size = int(Config.VAD_BUFFER_DURATION_S * Config.SAMPLE_RATE)
        silence_buffer = deque(maxlen=silence_buffer_size)

        while self.is_recording.is_set():
            logger.debug("Audio loop: Waiting for audio chunk...")
            current_time = time.monotonic()
            
            try:
                # Get a chunk of audio from the queue
                audio_chunk = await asyncio.wait_for(self.audio_queue.get(), timeout=1.0)
                
                # Mark the task as done after processing
                self.audio_queue.task_done()
                
                logger.debug("Audio loop: Got an audio chunk.")
                frame_energy = np.sqrt(np.mean(np.square(audio_chunk)))
                
                if is_speaking:
                    audio_buffer.append(audio_chunk)
                    buffer_duration = len(audio_buffer) * len(audio_chunk) / Config.SAMPLE_RATE
                    
                    if frame_energy < Config.VAD_ENERGY_THRESHOLD:
                        if silence_start_time is None:
                            silence_start_time = time.monotonic()
                        # If silence duration is exceeded, end of sentence is detected
                        elif time.monotonic() - silence_start_time > Config.VAD_SILENCE_DURATION_S:
                            is_speaking = False
                            # Process streaming results if any
                            if self.streaming_active:
                                await self._finalize_streaming_results(websocket, audio_buffer)
                    else:
                        silence_start_time = None # Reset silence timer if speech is detected
                        
                        # STREAMING OPTIMIZATION: Process chunks while speaking continues
                        if (Config.STREAMING_ENABLED and 
                            buffer_duration >= Config.STREAMING_MIN_BUFFER_S):
                            
                            # Check if it's time to process a streaming chunk
                            if last_streaming_process_time is None:
                                # Start streaming processing
                                chunk_samples = int(Config.STREAMING_CHUNK_DURATION_S * Config.SAMPLE_RATE)
                                chunk_size = chunk_samples // len(audio_chunk)
                                
                                if len(audio_buffer) >= chunk_size:
                                    initial_buffer = audio_buffer[:chunk_size]
                                    await self._start_streaming_processing(websocket, initial_buffer)
                                    last_streaming_process_time = current_time
                                    
                            elif (current_time - last_streaming_process_time >= Config.STREAMING_CHUNK_DURATION_S):
                                # Process next streaming chunk with overlap
                                chunk_samples = int(Config.STREAMING_CHUNK_DURATION_S * Config.SAMPLE_RATE)
                                overlap_samples = int(Config.STREAMING_OVERLAP_DURATION_S * Config.SAMPLE_RATE)
                                
                                chunk_size = chunk_samples // len(audio_chunk)
                                overlap_size = overlap_samples // len(audio_chunk)
                                
                                # Calculate buffer slice for next chunk (with overlap)
                                start_idx = max(0, len(audio_buffer) - chunk_size - overlap_size)
                                end_idx = len(audio_buffer)
                                
                                if end_idx - start_idx >= chunk_size:
                                    buffer_chunk = audio_buffer[start_idx:end_idx]
                                    streaming_chunk_index += 1
                                    
                                    # Process in background (fire and forget for responsiveness)
                                    asyncio.create_task(
                                        self._process_streaming_buffer_chunk(
                                            websocket, buffer_chunk, streaming_chunk_index
                                        )
                                    )
                                    last_streaming_process_time = current_time
                        
                else:
                    silence_buffer.extend(audio_chunk.flatten())
                    if frame_energy > Config.VAD_ENERGY_THRESHOLD:
                        logger.info("Speech detected.")
                        is_speaking = True
                        silence_start_time = None
                        speech_start_time = current_time
                        last_streaming_process_time = None
                        streaming_chunk_index = 0
                        self.streaming_active = False
                        self.processed_chunks = []
                        last_activity_time = current_time  # Update activity time
                        # Prepend the silence buffer to capture the start of the word
                        audio_buffer = [np.array(list(silence_buffer))]
                        audio_buffer.append(audio_chunk)

                # If speech has ended, process the collected audio buffer
                if not is_speaking and audio_buffer:
                    await self._process_final_utterance(websocket, audio_buffer, current_time)
                    audio_buffer.clear()
                    last_activity_time = current_time

                # Send heartbeat if needed (no recent activity and sufficient time has passed)
                time_since_last_heartbeat = current_time - last_heartbeat_time
                time_since_last_activity = current_time - last_activity_time
                
                if (time_since_last_heartbeat >= Config.HEARTBEAT_INTERVAL_S and 
                    time_since_last_activity >= Config.HEARTBEAT_INTERVAL_S):
                    await self._send_heartbeat(websocket)
                    last_heartbeat_time = current_time

            except asyncio.TimeoutError:
                logger.debug("Audio loop: Queue was empty, continuing.")
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
                    if audio_buffer:
                        await self._process_final_utterance(websocket, audio_buffer, current_time)
                        audio_buffer.clear()
                        last_activity_time = current_time
                continue
            except Exception as e:
                logger.error(f"CRITICAL ERROR in transcription loop: {e}", exc_info=True)
                # Reset state on error
                audio_buffer.clear()
                is_speaking = False
                self.streaming_active = False
                self.processed_chunks = []
                await asyncio.sleep(1)

    async def _finalize_streaming_results(self, websocket, audio_buffer):
        """Finalize streaming results and send consolidated transcription."""
        try:
            if self.processed_chunks:
                # Optionally process any remaining audio not covered by streaming.
                # This is the most crucial part.
                remaining_audio = np.concatenate([chunk.flatten() for chunk in audio_buffer]) if audio_buffer else np.array([])
                
                # Use the new, safe helper function to transcribe the entire utterance.
                # This handles both short and long audio gracefully by chunking it.
                logger.info("Finalizing transcription for the complete utterance...")
                final_transcription = await self._transcribe_long_audio(remaining_audio)
                
                if len(final_transcription.split()) >= Config.MIN_WORDS_PER_SENTENCE:
                    await self._send_sentence(websocket, final_transcription, is_interim=False)
                else:
                    # This branch is now less likely to be hit, but good for safety
                    logger.info(f"Skipping final short or empty sentence: '{final_transcription}'")

            # Reset streaming state for the next utterance
            self.streaming_active = False
            self.processed_chunks = []
            
        except Exception as e:
            logger.error(f"Error finalizing streaming results: {e}", exc_info=True)
    
    async def _process_final_utterance(self, websocket, audio_buffer, current_time):
        """Process final utterance using the new chunking transcription method."""
        if self.streaming_active and self.processed_chunks:
            # We have streaming results, finalize them
            await self._finalize_streaming_results(websocket, audio_buffer)
        else:
            # Traditional processing for short utterances or when streaming is disabled
            full_utterance = np.concatenate([chunk.flatten() for chunk in audio_buffer])
            
            # Use the new, safe helper function to transcribe
            # This handles both short and long audio gracefully
            full_sentence = await self._transcribe_long_audio(full_utterance)
            
            if len(full_sentence.split()) >= Config.MIN_WORDS_PER_SENTENCE:
                await self._send_sentence(websocket, full_sentence, is_interim=False)
            else:
                logger.info(f"Skipping short sentence: '{full_sentence}'")


    async def _transcribe_long_audio(self, audio_data: np.ndarray) -> str:
        """
        Transcribes audio data, splitting it into manageable chunks if it exceeds
        a maximum duration to avoid long blocking calls.
        """
        MAX_CHUNK_DURATION_S = 20.0
        OVERLAP_DURATION_S = 1.0  # 1-second overlap for context between chunks

        total_samples = len(audio_data)
        total_duration_s = total_samples / Config.SAMPLE_RATE

        # If the audio is short enough, transcribe it directly
        if total_duration_s <= MAX_CHUNK_DURATION_S:
            logger.info(f"Transcribing short utterance ({total_duration_s:.2f}s) in a single pass.")
            segments, _ = await asyncio.to_thread(
                self.model.transcribe, audio_data, language=Config.LANGUAGE
            )
            return "".join(s.text for s in segments).strip()

        # --- Logic for splitting long audio ---
        logger.info(f"Audio duration ({total_duration_s:.2f}s) exceeds max chunk size. Splitting into chunks...")
        
        transcribed_parts = []
        
        # Convert durations to sample counts
        max_samples_per_chunk = int(MAX_CHUNK_DURATION_S * Config.SAMPLE_RATE)
        overlap_samples = int(OVERLAP_DURATION_S * Config.SAMPLE_RATE)
        
        start_sample = 0
        chunk_index = 0
        while start_sample < total_samples:
            end_sample = min(start_sample + max_samples_per_chunk, total_samples)
            
            chunk_audio = audio_data[start_sample:end_sample]
            chunk_duration = len(chunk_audio) / Config.SAMPLE_RATE
            
            logger.info(f"Transcribing chunk {chunk_index} ({chunk_duration:.2f}s)...")
            
            segments, _ = await asyncio.to_thread(
                self.model.transcribe, chunk_audio, language=Config.LANGUAGE
            )
            
            chunk_text = "".join(s.text for s in segments).strip()
            transcribed_parts.append(chunk_text)
            
            logger.info(f"Chunk {chunk_index} result: '{chunk_text}'")
            
            # Move to the next chunk
            start_sample += max_samples_per_chunk - overlap_samples
            chunk_index += 1
            
        return " ".join(part for part in transcribed_parts if part)

    async def run(self):
        """Main service loop that manages WebSocket connection and tasks."""
        logger.info("Starting STTService.run()")
        websocket_uri = f"{Config.WEBSOCKET_URI}/{self.stt_client_id}"
        threading.Thread(target=self._record_audio_thread, daemon=True).start()

        while self.is_recording.is_set():
            logger.info("Main loop: Attempting to connect to WebSocket...")
            try:
                async with websockets.connect(websocket_uri, ping_interval=5, ping_timeout=30) as websocket:
                    logger.info(f"STT: ✅ WebSocket connection established to {websocket_uri}")
                    initial_message = {
                        "id": str(uuid4()), "type": "stt.init", "timestamp": time.time(),
                        "payload": {"message": "STT service connected", "user_session_id": self.user_session_id},
                        "origin": "stt_module", "client_id": self.stt_client_id,
                    }
                    await websocket.send(json.dumps(initial_message))
                    logger.info(f"STT: 📤 Sent handshake init message for session {self.user_session_id}")

                    # Retry any unsent sentences from previous connection failures
                    if self.unsent_sentences:
                        logger.info(f"Retrying {len(self.unsent_sentences)} unsent sentences after reconnect.")
                        for msg in self.unsent_sentences:
                            try:
                                await websocket.send(json.dumps(msg))
                                logger.info(f"Retried and sent buffered sentence: {msg['payload']['text']}")
                            except websockets.exceptions.ConnectionClosed:
                                logger.info("Cannot resend buffered sentence - connection closed during retry.")
                                break  # Stop trying to send more if connection is closed
                            except Exception as e:
                                logger.warning(f"Failed to resend buffered sentence: {e}")
                        self.unsent_sentences.clear()

                    await self._process_audio_loop(websocket)
            except websockets.exceptions.ConnectionClosed as e:
                close_code = getattr(e, 'code', 'Unknown')
                close_reason = getattr(e, 'reason', 'No reason provided')
                logger.warning(f"STT: 🔌 WebSocket connection to {websocket_uri} closed. Code: {close_code}, Reason: {close_reason}. Reconnecting in 3s...", exc_info=True)
                await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"STT: ❌ WebSocket connection to {websocket_uri} failed: {e}. Retrying in 3s...", exc_info=True)
                await asyncio.sleep(3)

    def stop(self):
        """Stops the recording and shuts down the service."""
        self.is_recording.clear()
        self.streaming_active = False
        self.processed_chunks = []
        logger.info("Shutdown signal received. Stopping STT service.")
        logger.info("STTService.stop() method completed.")

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