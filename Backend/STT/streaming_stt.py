"""
Alternative STT implementation using streaming chunks for lower latency.
This processes smaller audio chunks continuously instead of waiting for complete sentences.
"""

import asyncio
import numpy as np
import time
import logging
from typing import List, Optional, Callable
from collections import deque
import threading
import queue
from dataclasses import dataclass

try:
    import sounddevice as sd
except OSError:
    sd = None

logger = logging.getLogger(__name__)

@dataclass
class AudioChunk:
    """Represents a chunk of audio data with metadata."""
    data: np.ndarray
    timestamp: float
    energy: float
    is_speech: bool

class StreamingSTTProcessor:
    """
    Streaming STT processor that processes audio in smaller chunks for lower latency.
    Instead of waiting for complete sentences, this processes overlapping windows.
    """
    
    def __init__(self, model, config, chunk_duration_s: float = 0.5, overlap_s: float = 0.1):
        self.model = model
        self.config = config
        self.chunk_duration_s = chunk_duration_s
        self.overlap_s = overlap_s
        
        # Audio buffering
        self.chunk_size = int(chunk_duration_s * config.SAMPLE_RATE)
        self.overlap_size = int(overlap_s * config.SAMPLE_RATE)
        self.audio_buffer = deque(maxlen=self.chunk_size + self.overlap_size)
        
        # Processing state
        self.last_transcription = ""
        self.transcription_history = deque(maxlen=5)  # Keep last 5 partial results
        self.processing_lock = threading.Lock()
        
        # Performance tracking
        self.chunk_processing_times = []
        
        logger.info(f"StreamingSTTProcessor initialized: chunk={chunk_duration_s}s, overlap={overlap_s}s")
    
    def add_audio_data(self, audio_data: np.ndarray) -> List[AudioChunk]:
        """Add new audio data and return any chunks ready for processing."""
        self.audio_buffer.extend(audio_data.flatten())
        
        chunks = []
        while len(self.audio_buffer) >= self.chunk_size:
            # Extract chunk
            chunk_data = np.array(list(self.audio_buffer)[:self.chunk_size])
            
            # Calculate energy and speech detection
            energy = np.sqrt(np.mean(np.square(chunk_data)))
            is_speech = energy > self.config.VAD_ENERGY_THRESHOLD
            
            chunk = AudioChunk(
                data=chunk_data,
                timestamp=time.time(),
                energy=energy,
                is_speech=is_speech
            )
            chunks.append(chunk)
            
            # Remove processed data (keeping overlap)
            for _ in range(self.chunk_size - self.overlap_size):
                if self.audio_buffer:
                    self.audio_buffer.popleft()
            
            break  # Process one chunk at a time to avoid blocking
        
        return chunks
    
    async def process_chunk(self, chunk: AudioChunk) -> Optional[str]:
        """Process a single audio chunk and return partial transcription."""
        if not chunk.is_speech:
            return None
        
        try:
            start_time = time.time()
            
            # Transcribe the chunk
            segments, info = await asyncio.to_thread(
                self.model.transcribe, 
                chunk.data,
                language=self.config.LANGUAGE,
                without_timestamps=True,  # Faster processing
                word_timestamps=False
            )
            
            processing_time = time.time() - start_time
            self.chunk_processing_times.append(processing_time)
            
            # Extract text from segments
            chunk_text = "".join(s.text for s in segments).strip()
            
            if chunk_text:
                logger.debug(f"Chunk transcription ({processing_time:.3f}s): '{chunk_text}'")
                return chunk_text
                
        except Exception as e:
            logger.error(f"Error processing chunk: {e}")
        
        return None
    
    def merge_transcriptions(self, new_text: str) -> Optional[str]:
        """Merge new partial transcription with previous results to form coherent sentences."""
        if not new_text:
            return None
        
        with self.processing_lock:
            # Add to history
            self.transcription_history.append(new_text.lower())
            
            # Simple merging strategy: look for common words between chunks
            if len(self.transcription_history) < 2:
                return new_text
            
            # Try to merge with previous chunk
            prev_text = list(self.transcription_history)[-2] if len(self.transcription_history) > 1 else ""
            merged = self._smart_merge(prev_text, new_text)
            
            # Only return if we have a meaningful change
            if merged != self.last_transcription:
                self.last_transcription = merged
                return merged
        
        return None
    
    def _smart_merge(self, prev_text: str, new_text: str) -> str:
        """Smart merging of overlapping transcriptions."""
        if not prev_text:
            return new_text
        
        # Find overlap between texts
        prev_words = prev_text.split()
        new_words = new_text.split()
        
        # Look for best overlap
        best_overlap = 0
        best_merge = new_text
        
        for i in range(1, min(len(prev_words), len(new_words)) + 1):
            if prev_words[-i:] == new_words[:i]:
                # Found overlap
                if i > best_overlap:
                    best_overlap = i
                    best_merge = ' '.join(prev_words + new_words[i:])
        
        return best_merge if best_overlap > 0 else f"{prev_text} {new_text}"
    
    def get_performance_stats(self) -> dict:
        """Get performance statistics for the streaming processor."""
        if not self.chunk_processing_times:
            return {}
        
        import statistics
        return {
            'chunks_processed': len(self.chunk_processing_times),
            'avg_chunk_processing_time': statistics.mean(self.chunk_processing_times),
            'chunk_duration': self.chunk_duration_s,
            'processing_overhead': statistics.mean(self.chunk_processing_times) / self.chunk_duration_s,
            'fastest_chunk': min(self.chunk_processing_times),
            'slowest_chunk': max(self.chunk_processing_times)
        }

class StreamingSTTService:
    """
    Alternative STT service using streaming chunks for lower latency.
    This is an experimental approach that may provide better responsiveness.
    """
    
    def __init__(self, model, config, on_transcription: Callable[[str], None]):
        self.model = model
        self.config = config
        self.on_transcription = on_transcription
        
        # Streaming processor
        self.processor = StreamingSTTProcessor(model, config)
        
        # Audio recording
        self.audio_queue = queue.Queue()
        self.is_recording = threading.Event()
        
        logger.info("StreamingSTTService initialized")
    
    def start_recording(self):
        """Start audio recording thread."""
        if sd is None:
            logger.error("sounddevice not available - cannot start recording")
            return False
            
        self.is_recording.set()
        threading.Thread(target=self._record_audio_thread, daemon=True).start()
        return True
    
    def _record_audio_thread(self):
        """Audio recording thread."""
        def callback(indata, frames, time_info, status):
            if status: 
                logger.warning(f"Recording status: {status}")
            if self.is_recording.is_set(): 
                self.audio_queue.put(indata.copy())
        
        try:
            with sd.InputStream(
                samplerate=self.config.SAMPLE_RATE, 
                channels=self.config.CHANNELS, 
                callback=callback, 
                dtype='float32',
                blocksize=1024  # Smaller blocks for lower latency
            ) as stream:
                logger.info(f"Streaming recording active: {stream.samplerate}Hz, {stream.channels}ch")
                while self.is_recording.is_set(): 
                    time.sleep(0.1)
        except Exception as e:
            logger.critical(f"Streaming audio recording error: {e}", exc_info=True)
        finally:
            logger.info("Streaming audio recording stopped.")
    
    async def process_audio_stream(self):
        """Main processing loop for streaming audio."""
        logger.info("Starting streaming audio processing...")
        
        while self.is_recording.is_set():
            try:
                # Get audio data (non-blocking with timeout)
                try:
                    audio_data = self.audio_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                
                # Add to processor and get chunks
                chunks = self.processor.add_audio_data(audio_data)
                
                # Process each chunk
                for chunk in chunks:
                    partial_text = await self.processor.process_chunk(chunk)
                    if partial_text:
                        # Try to merge with previous transcriptions
                        merged_text = self.processor.merge_transcriptions(partial_text)
                        if merged_text:
                            # Send the transcription
                            await asyncio.create_task(
                                asyncio.to_thread(self.on_transcription, merged_text)
                            )
                
            except Exception as e:
                logger.error(f"Error in streaming processing: {e}", exc_info=True)
                await asyncio.sleep(0.1)
        
        logger.info("Streaming audio processing stopped.")
    
    def stop(self):
        """Stop the streaming service."""
        self.is_recording.clear()
        
        # Log performance stats
        stats = self.processor.get_performance_stats()
        if stats:
            logger.info("=== Streaming STT Performance Stats ===")
            for key, value in stats.items():
                if isinstance(value, float):
                    logger.info(f"{key}: {value:.3f}")
                else:
                    logger.info(f"{key}: {value}")
        
        logger.info("StreamingSTTService stopped.")

# Example usage function
async def test_streaming_stt():
    """Test the streaming STT implementation."""
    from Backend.STT.performance_configs import config_manager
    from faster_whisper import WhisperModel
    
    # Use a fast configuration for streaming
    config = config_manager.get_config('balanced_fast')
    
    # Load model
    logger.info("Loading model for streaming test...")
    model = WhisperModel(config.model_size, device="cpu", compute_type="int8")
    
    transcriptions = []
    def on_transcription(text):
        transcriptions.append(text)
        print(f"Streaming transcription: {text}")
    
    # Create streaming service
    service = StreamingSTTService(model, config, on_transcription)
    
    print("Starting streaming STT test (would need real microphone)...")
    
    # In real usage:
    # service.start_recording()
    # await service.process_audio_stream()
    
    print("Streaming STT test completed.")

if __name__ == "__main__":
    # This would be integrated into the main STT service as an alternative mode
    asyncio.run(test_streaming_stt())