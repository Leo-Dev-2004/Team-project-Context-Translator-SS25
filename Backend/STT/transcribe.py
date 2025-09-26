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
    """Configuration manager that dynamically reads from performance profiles."""
    
    # Static configuration
    SAMPLE_RATE = 16000
    CHANNELS = 1
    LANGUAGE = "en"
    WEBSOCKET_URI = "ws://localhost:8000/ws"
    
    @staticmethod
    def get_performance_config():
            """Get the current performance configuration, default to 'current_default' for better accuracy."""
            import os
            # Force 'current_default' profile unless overridden by env
            if not os.environ.get('STT_PERFORMANCE_PROFILE'):
                os.environ['STT_PERFORMANCE_PROFILE'] = 'current_default'
            return config_manager.get_config()
    
    @staticmethod
    def MODEL_SIZE():
        return ConfigManager.get_performance_config().model_size
    
    @staticmethod
    def VAD_ENERGY_THRESHOLD():
           # Make VAD much less restrictive: lower threshold by 50%
           base = ConfigManager.get_performance_config().vad_energy_threshold
           return base * 0.5
    
    @staticmethod
    def VAD_SILENCE_DURATION_S():
           # Make VAD much less restrictive: reduce silence duration by 60%
           base = ConfigManager.get_performance_config().vad_silence_duration_s
           return base * 0.4
    
    @staticmethod
    def VAD_BUFFER_DURATION_S():
        return ConfigManager.get_performance_config().vad_buffer_duration_s
    
    @staticmethod
    def MIN_WORDS_PER_SENTENCE():
        return ConfigManager.get_performance_config().min_words_per_sentence

# Use the manager as Config for backward compatibility  
Config = ConfigManager

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

    async def _send_sentence(self, websocket, sentence: str):
        """Formats and sends a transcribed sentence over the WebSocket."""
        if not sentence or not sentence.strip():
            logger.warning("STTService: Blocked empty or whitespace-only transcription from being sent.")
            return

        transcription_logger.info(sentence)
        message = {
            "id": str(uuid4()), "type": "stt.transcription", "timestamp": time.time(),
            "payload": {
                "text": sentence, "language": Config.LANGUAGE,
                "user_session_id": self.user_session_id
            },
            "origin": "stt_module", "client_id": self.stt_client_id
        }
        try:
            await websocket.send(json.dumps(message))
            logger.info(f"Sent: {sentence}")
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Failed to send sentence, connection closed.")

    async def _process_audio_loop(self, websocket):
        """[Async Task] Implements the VAD-based 'record-then-transcribe' logic."""
        audio_buffer = []
        is_speaking = False
        silence_start_time = None
        
        # Keep a small buffer of recent silence to catch the start of speech
        silence_buffer_size = int(Config.VAD_BUFFER_DURATION_S() * Config.SAMPLE_RATE)
        silence_buffer = deque(maxlen=silence_buffer_size)

        while self.is_recording.is_set():
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
                    if frame_energy < Config.VAD_ENERGY_THRESHOLD():
                        if silence_start_time is None:
                            silence_start_time = time.monotonic()
                        # If silence duration is exceeded, end of sentence is detected
                        elif time.monotonic() - silence_start_time > Config.VAD_SILENCE_DURATION_S():
                            logger.info(f"End of speech detected after {Config.VAD_SILENCE_DURATION_S()}s silence")
                            is_speaking = False
                    else:
                        silence_start_time = None # Reset silence timer if speech is detected
                else:
                    silence_buffer.extend(audio_chunk.flatten())
                    if frame_energy > Config.VAD_ENERGY_THRESHOLD():
                        logger.info(f"Speech detected! Energy: {frame_energy:.6f} > threshold: {Config.VAD_ENERGY_THRESHOLD()}")
                        is_speaking = True
                        silence_start_time = None
                        # Prepend the silence buffer to capture the start of the word
                        audio_buffer = [np.array(list(silence_buffer))]
                        audio_buffer.append(audio_chunk)

                # If speech has ended, process the collected audio buffer
                if not is_speaking and audio_buffer:
                    full_utterance = np.concatenate([chunk.flatten() for chunk in audio_buffer])
                    audio_buffer.clear()
                    
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
                        processing_overhead = transcription_time / audio_duration
                        
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
                        continue

            except queue.Empty:
                # If speech was in progress and the queue is now empty, it's the end of an utterance
                if is_speaking:
                    is_speaking = False
                continue
            except Exception as e:
                logger.error(f"Error in transcription loop: {e}", exc_info=True)
                # Reset state on error
                audio_buffer.clear()
                is_speaking = False
                await asyncio.sleep(1)

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
                    
                    await self._process_audio_loop(websocket)
            except Exception as e:
                logger.error(f"WebSocket connection failed, retrying in 5s: {e}")
                await asyncio.sleep(5)

    def stop(self):
        """Stops the recording and shuts down the service."""
        self.is_recording.clear()
        
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