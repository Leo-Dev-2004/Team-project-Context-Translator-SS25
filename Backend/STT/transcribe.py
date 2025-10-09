import asyncio
import numpy as np
try:
    import sounddevice as sd
except (OSError, ImportError):
    # PortAudio not available or sounddevice not installed
    sd = None
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
# Import performance configurations
from .performance_configs import config_manager

# Simple configuration that delegates to performance config
class ConfigManager:
    # Streaming optimization settings
    @staticmethod
    def STREAMING_ENABLED():
        return True

    @staticmethod
    def STREAMING_CHUNK_DURATION_S():
        return 3.0

    @staticmethod
    def STREAMING_OVERLAP_DURATION_S():
        return 0.5

    @staticmethod
    def STREAMING_MIN_BUFFER_S():
        return 2.0
    """Configuration manager that dynamically reads from performance profiles."""

    # Static configuration
    SAMPLE_RATE = 16000
    CHANNELS = 1
    LANGUAGE = "en"
    WEBSOCKET_URI = "ws://localhost:8000/ws"

    @staticmethod
    def get_performance_config():
        """Get the current performance configuration, default to 'current_default' for maximum accuracy."""
        import os
        # Use current_default for maximum accuracy unless explicitly overridden
        profile = os.environ.get('STT_PERFORMANCE_PROFILE', 'current_default')
        return config_manager.get_config(profile)

    @staticmethod
    def MODEL_SIZE():
        return ConfigManager.get_performance_config().model_size

    @staticmethod
    def VAD_ENERGY_THRESHOLD():
        return ConfigManager.get_performance_config().vad_energy_threshold

    @staticmethod
    def VAD_SILENCE_DURATION_S():
        return ConfigManager.get_performance_config().vad_silence_duration_s

    @staticmethod
    def VAD_BUFFER_DURATION_S():
        return ConfigManager.get_performance_config().vad_buffer_duration_s

    @staticmethod
    def MIN_WORDS_PER_SENTENCE():
        return ConfigManager.get_performance_config().min_words_per_sentence

# Use the manager as Config for backward compatibility
Config = ConfigManager
# VAD (Voice Activity Detection) settings are key for responsiveness
VAD_ENERGY_THRESHOLD = 0.004 # Energy threshold to detect speech
VAD_SILENCE_DURATION_S = 1.0 # How long of a pause indicates end of sentence
VAD_BUFFER_DURATION_S = 0.5 # Seconds of silence to keep before speech starts

# Heartbeat settings to prevent connection timeouts during silence
HEARTBEAT_INTERVAL_S = 5.0 # Send heartbeat every 10 seconds during silence (30s default was too long)

# STREAMING OPTIMIZATION SETTINGS
STREAMING_ENABLED = True # Enable streaming transcription for long speech
STREAMING_CHUNK_DURATION_S = 3.0 # Process chunks every N seconds during speech
STREAMING_OVERLAP_DURATION_S = 0.5 # Overlap between chunks for context
STREAMING_MIN_BUFFER_S = 2.0 # Minimum buffer before starting streaming

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

        # Get current performance configuration
        perf_config = Config.get_performance_config()
        logger.info(f"Using STT performance profile: {perf_config.name}")
        logger.info(f"Profile description: {perf_config.description}")
        logger.info(f"Model: {perf_config.model_size}, VAD threshold: {perf_config.vad_energy_threshold}, "
                    f"Silence duration: {perf_config.vad_silence_duration_s}s")

        # Measure model loading time for performance monitoring
        load_start_time = time.time()
        logger.info(f"Loading Whisper model '{Config.MODEL_SIZE()}'...")
        try:
            self.model = WhisperModel(Config.MODEL_SIZE(), device="cpu", compute_type="int8")
            load_time = time.time() - load_start_time
            logger.info(f"Whisper model loaded successfully in {load_time:.2f}s")
        except Exception as e:
            logger.critical(f"Failed to load Whisper model '{Config.MODEL_SIZE()}': {e}")
            logger.critical("This is likely due to:")
            logger.critical("  1. Missing dependencies (pip install faster-whisper)")
            logger.critical("  2. No internet connection (models need to be downloaded)")
            logger.critical("  3. Insufficient disk space")
            logger.critical("  4. Firewall blocking model download")
            raise
        logger.info(f"Whisper model loaded in {load_time:.2f}s")

        self.audio_queue = queue.Queue()
        self.is_recording = threading.Event()
        self.is_recording.set()

        # Performance tracking
        self.transcription_times = []
        self.audio_durations = []

        logger.info(f"STTService initialized for session {self.user_session_id}")
        logger.info("To debug transcription issues, check:")
        logger.info("  1. Microphone permissions and hardware")
        logger.info("  2. Audio levels (speak clearly into microphone)")
        logger.info(f"  3. VAD settings (threshold: {Config.VAD_ENERGY_THRESHOLD()}, silence: {Config.VAD_SILENCE_DURATION_S()}s)")
        logger.info("  4. Backend WebSocket server running on localhost:8000")
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
        if sd is None:
            logger.error("sounddevice not available - cannot record audio")
            return

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

    async def _send_sentence(self, websocket, sentence: str, is_interim: bool = False):
        """Formats and sends a transcribed sentence over the WebSocket."""
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
        try:
            await websocket.send(json.dumps(message))
            logger.info(f"Sent {'interim' if is_interim else 'final'}: {sentence}")
        except Exception as e:
            logger.warning(f"Failed to send sentence, connection error: {e}. Buffering for retry.")
            self.unsent_sentences.append(message)

    async def _process_streaming_chunk(self, audio_chunk: np.ndarray, chunk_index: int):
        """Process a streaming audio chunk in the background."""
        try:
            chunk_duration = len(audio_chunk) / Config.SAMPLE_RATE
            logger.info(f"Processing streaming chunk {chunk_index} ({chunk_duration:.2f}s)")

            start_time = time.monotonic()
            segments, _ = await asyncio.to_thread(
                self.model.transcribe, audio_chunk, language=Config.LANGUAGE
            )
            processing_time = time.monotonic() - start_time

            result = "".join(s.text for s in segments).strip()

            chunk_info = {
                'index': chunk_index,
                'text': result,
                'duration': chunk_duration,
                'processing_time': processing_time,
                'timestamp': time.time()
            }

            logger.info(f"Chunk {chunk_index} processed in {processing_time:.2f}s: '{result}'")
            return chunk_info

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
            chunk_info = await self._process_streaming_chunk(chunk_audio, 0)

            if chunk_info and chunk_info['text']:
                self.processed_chunks.append(chunk_info)
                # Send interim result immediately
                await self._send_sentence(websocket, chunk_info['text'], is_interim=True)

        except Exception as e:
            logger.error(f"Error starting streaming processing: {e}", exc_info=True)
            self.streaming_active = False

    async def _process_streaming_buffer_chunk(self, websocket, buffer_chunk, chunk_index):
        """Process additional streaming chunks while speech continues."""
        if not self.streaming_active:
            return

        try:
            chunk_audio = np.concatenate([chunk.flatten() for chunk in buffer_chunk])
            chunk_info = await self._process_streaming_chunk(chunk_audio, chunk_index)

            if chunk_info and chunk_info['text']:
                self.processed_chunks.append(chunk_info)
                # Send interim result
                await self._send_sentence(websocket, chunk_info['text'], is_interim=True)

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
        """[Async Task] Implements the VAD-based 'record-then-transcribe' logic with streaming optimization."""
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
        silence_buffer_size = int(Config.VAD_BUFFER_DURATION_S() * Config.SAMPLE_RATE)
        silence_buffer = deque(maxlen=silence_buffer_size)

        while self.is_recording.is_set():
            current_time = time.monotonic()

            try:
                # Get a chunk of audio from the queue
                audio_chunk = self.audio_queue.get(timeout=1.0)
                frame_energy = np.sqrt(np.mean(np.square(audio_chunk)))

                # Debug logging for VAD (only occasionally to avoid spam)
                if hasattr(self, '_debug_counter'):
                    self._debug_counter += 1
                else:
                    self._debug_counter = 0

                if self._debug_counter % 50 == 0:  # Log every 50th frame (roughly every 5 seconds)
                    logger.debug(f"Audio energy: {frame_energy:.6f}, threshold: {Config.VAD_ENERGY_THRESHOLD()}, speaking: {is_speaking}")

                if is_speaking:
                    audio_buffer.append(audio_chunk)
                    
                    # Calculate buffer duration to decide when to start streaming
                    buffer_duration_frames = sum(len(c) for c in audio_buffer)
                    buffer_duration = buffer_duration_frames / Config.SAMPLE_RATE

                    if frame_energy < Config.VAD_ENERGY_THRESHOLD():
                        if silence_start_time is None:
                            silence_start_time = time.monotonic()
                        # If silence duration is exceeded, end of sentence is detected
                        elif time.monotonic() - silence_start_time > Config.VAD_SILENCE_DURATION_S():
                            logger.info(f"End of speech detected after {Config.VAD_SILENCE_DURATION_S()}s silence")
                            is_speaking = False
                            # Process streaming results if any
                            if self.streaming_active:
                                await self._finalize_streaming_results(websocket, audio_buffer)
                    else:
                        silence_start_time = None # Reset silence timer if speech is detected

                        # STREAMING OPTIMIZATION: Process chunks while speaking continues
                        if (Config.STREAMING_ENABLED and
                            buffer_duration >= Config.STREAMING_MIN_BUFFER_S()):

                            # Check if it's time to process a streaming chunk
                            if last_streaming_process_time is None:
                                # Start streaming processing
                                chunk_samples = int(Config.STREAMING_CHUNK_DURATION_S() * Config.SAMPLE_RATE)
                                chunk_size = chunk_samples // len(audio_chunk)

                                if len(audio_buffer) >= chunk_size:
                                    initial_buffer = audio_buffer[:chunk_size]
                                    await self._start_streaming_processing(websocket, initial_buffer)
                                    last_streaming_process_time = current_time

                            elif (current_time - last_streaming_process_time >= Config.STREAMING_CHUNK_DURATION_S()):
                                # Process next streaming chunk with overlap
                                chunk_samples = int(Config.STREAMING_CHUNK_DURATION_S() * Config.SAMPLE_RATE)
                                overlap_samples = int(Config.STREAMING_OVERLAP_DURATION_S() * Config.SAMPLE_RATE)

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
                    if frame_energy > Config.VAD_ENERGY_THRESHOLD():
                        logger.info(f"Speech detected! Energy: {frame_energy:.6f} > threshold: {Config.VAD_ENERGY_THRESHOLD()}")
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

                if (time_since_last_heartbeat >= HEARTBEAT_INTERVAL_S and
                    time_since_last_activity >= HEARTBEAT_INTERVAL_S):
                    await self._send_heartbeat(websocket)
                    last_heartbeat_time = current_time

            except queue.Empty:
                # Check for heartbeat even when no audio data is available
                current_time = time.monotonic()
                time_since_last_heartbeat = current_time - last_heartbeat_time
                time_since_last_activity = current_time - last_activity_time

                if (time_since_last_heartbeat >= HEARTBEAT_INTERVAL_S and
                    time_since_last_activity >= HEARTBEAT_INTERVAL_S):
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
                logger.error(f"Error in transcription loop: {e}", exc_info=True)
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
                # Use streaming results as base
                consolidated = self._consolidate_streaming_results()

                # Optionally process any remaining audio not covered by streaming
                remaining_samples = len(audio_buffer) * len(audio_buffer[0]) if audio_buffer else 0
                last_processed = sum(chunk.get('duration', 0) for chunk in self.processed_chunks) * Config.SAMPLE_RATE

                if remaining_samples > last_processed + (Config.SAMPLE_RATE * 0.5):  # 0.5s threshold
                    logger.info("Processing remaining audio after streaming chunks")
                    remaining_audio = np.concatenate([chunk.flatten() for chunk in audio_buffer])

                    segments, _ = await asyncio.to_thread(
                        self.model.transcribe, remaining_audio, language=Config.LANGUAGE
                    )
                    final_transcription = "".join(s.text for s in segments).strip()

                    if len(final_transcription.split()) >= Config.MIN_WORDS_PER_SENTENCE():
                        await self._send_sentence(websocket, final_transcription, is_interim=False)
                else:
                    # Send consolidated streaming result as final
                    if consolidated and len(consolidated.split()) >= Config.MIN_WORDS_PER_SENTENCE():
                        await self._send_sentence(websocket, consolidated, is_interim=False)

            # Reset streaming state
            self.streaming_active = False
            self.processed_chunks = []

        except Exception as e:
            logger.error(f"Error finalizing streaming results: {e}", exc_info=True)

    async def _process_final_utterance(self, websocket, audio_buffer, current_time):
        """Process final utterance - either from streaming or traditional processing."""
        if self.streaming_active and self.processed_chunks:
            # We have streaming results, finalize them
            await self._finalize_streaming_results(websocket, audio_buffer)
        else:
            # Traditional processing for short utterances or when streaming is disabled
            full_utterance = np.concatenate([chunk.flatten() for chunk in audio_buffer])

            audio_duration = len(full_utterance) / Config.SAMPLE_RATE
            logger.info(f"Processing utterance of duration {audio_duration:.2f}s...")
            
            # Measure transcription performance
            transcription_start = time.time()
            try:
                segments, _ = await asyncio.to_thread(
                    self.model.transcribe, full_utterance, language=Config.LANGUAGE
                )
                transcription_time = time.time() - transcription_start
                
                # Track performance metrics
                self.transcription_times.append(transcription_time)
                self.audio_durations.append(audio_duration)
                processing_overhead = transcription_time / audio_duration if audio_duration > 0 else 0
                
                logger.info(f"Transcription completed in {transcription_time:.3f}s "
                            f"(overhead: {processing_overhead:.2f}x)")
                
                full_sentence = "".join(s.text for s in segments).strip()
                
                if not full_sentence:
                    logger.info("Transcription result was empty - no recognizable speech")
                elif len(full_sentence.split()) >= Config.MIN_WORDS_PER_SENTENCE():
                    logger.info(f"Sending transcription: '{full_sentence}'")
                    await self._send_sentence(websocket, full_sentence)
                else:
                    logger.info(f"Skipping short sentence: '{full_sentence}' (min words: {Config.MIN_WORDS_PER_SENTENCE()})")
            
            except Exception as transcription_error:
                logger.error(f"Transcription failed: {transcription_error}")
                logger.error("This could be due to:")
                logger.error("  1. Model loading issues")
                logger.error("  2. Audio format incompatibility")
                logger.error("  3. Insufficient system resources")


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

                    # Retry any unsent sentences from previous connection failures
                    if self.unsent_sentences:
                        logger.info(f"Retrying {len(self.unsent_sentences)} unsent sentences after reconnect.")
                        for msg in self.unsent_sentences:
                            try:
                                await websocket.send(json.dumps(msg))
                                logger.info(f"Retried and sent buffered sentence: {msg['payload']['text']}")
                            except Exception as e:
                                logger.warning(f"Failed to resend buffered sentence: {e}")
                        self.unsent_sentences.clear()

                    await self._process_audio_loop(websocket)
            except Exception as e:
                logger.error(f"WebSocket connection failed, retrying in 5s: {e}")
                await asyncio.sleep(5)

    def stop(self):
        """Stops the recording and shuts down the service."""
        self.is_recording.clear()
        
        # Reset streaming state for a clean shutdown
        self.streaming_active = False
        self.processed_chunks = []
        
        # Log performance statistics if we have data
        if self.transcription_times and self.audio_durations:
            self._log_performance_stats()
            
        logger.info("Shutdown signal received. Stopping STT service.")

    def _log_performance_stats(self):
        """Log performance statistics for analysis."""
        import statistics

        if not self.transcription_times:
            return

        avg_transcription_time = statistics.mean(self.transcription_times)
        avg_audio_duration = statistics.mean(self.audio_durations)
        avg_overhead = avg_transcription_time / avg_audio_duration if avg_audio_duration > 0 else 0

        total_audio = sum(self.audio_durations)
        total_processing = sum(self.transcription_times)

        perf_config = Config.get_performance_config()

        logger.info("=== STT Performance Statistics ===")
        logger.info(f"Profile: {perf_config.name} ({perf_config.model_size} model)")
        logger.info(f"Total utterances processed: {len(self.transcription_times)}")
        logger.info(f"Total audio duration: {total_audio:.1f}s")
        logger.info(f"Total processing time: {total_processing:.1f}s")
        logger.info(f"Average transcription time: {avg_transcription_time:.3f}s")
        logger.info(f"Average processing overhead: {avg_overhead:.2f}x")
        logger.info(f"Fastest transcription: {min(self.transcription_times):.3f}s")
        logger.info(f"Slowest transcription: {max(self.transcription_times):.3f}s")

# --- MAIN EXECUTION BLOCK ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="STT Module for Context Translator with Performance Optimization.")
    parser.add_argument("--user-session-id", required=True, help="The unique ID for the user session.")
    parser.add_argument("--performance-profile",
                        choices=['ultra_responsive', 'balanced_fast', 'optimized_default', 'current_default', 'high_accuracy', 'streaming_optimized'],
                        help="STT performance profile to use. Can also be set via STT_PERFORMANCE_PROFILE environment variable.")
    parser.add_argument("--list-profiles", action="store_true", help="List available performance profiles and exit.")

    service = None
    try:
        args = parser.parse_args()

        if args.list_profiles:
            print("Available STT Performance Profiles:")
            configs = config_manager.list_configs()
            for name, description in configs.items():
                print(f"  {name}: {description}")
            print(f"\nCurrent profile: {config_manager.get_config().name}")
            print("Set profile via --performance-profile or STT_PERFORMANCE_PROFILE environment variable")
            exit(0)

        # Set performance profile if specified
        if args.performance_profile:
            import os
            os.environ['STT_PERFORMANCE_PROFILE'] = args.performance_profile

        # Log the configuration being used
        perf_config = Config.get_performance_config()
        logger.info(f"Starting STT service with performance profile: {perf_config.name}")

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