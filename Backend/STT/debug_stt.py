#!/usr/bin/env python3
"""
STT Debugging Helper Script
This script helps diagnose why transcription isn't working by testing each component.
"""

import os
import sys
import time
import logging
from pathlib import Path

# Add Backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

# Setup verbose logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_imports():
    """Test if all required modules can be imported."""
    print("\n=== Testing Module Imports ===")
    
    required_modules = [
        ('numpy', 'pip install numpy'),
        ('sounddevice', 'pip install sounddevice'),
        ('websockets', 'pip install websockets'),
        ('faster_whisper', 'pip install faster-whisper'),
    ]
    
    missing_modules = []
    for module_name, install_cmd in required_modules:
        try:
            __import__(module_name)
            print(f"✓ {module_name}")
        except ImportError:
            print(f"✗ {module_name} - Install with: {install_cmd}")
            missing_modules.append(module_name)
    
    return len(missing_modules) == 0

def test_microphone_access():
    """Test if microphone is accessible."""
    print("\n=== Testing Microphone Access ===")
    
    try:
        import sounddevice as sd
        print("✓ sounddevice imported successfully")
        
        # List audio devices
        devices = sd.query_devices()
        print(f"Found {len(devices)} audio devices:")
        
        input_devices = []
        for i, device in enumerate(devices):
            # FIXED: Use .get() for safer access and to satisfy the type checker.
            if device.get('max_input_channels', 0) > 0:
                input_devices.append((i, device))
                # FIXED: Use .get() here as well.
                print(f"  {i}: {device.get('name')} (inputs: {device.get('max_input_channels')})")
        
        if not input_devices:
            print("✗ No input devices found")
            return False
        
        # Test recording briefly
        print("\nTesting brief recording...")
        default_device = sd.default.device[0] if sd.default.device else input_devices[0][0]
        
        try:
            # Record 0.5 seconds
            recording = sd.rec(int(0.5 * 16000), samplerate=16000, channels=1, dtype='float32')
            sd.wait()  # Wait until recording is finished
            
            # Check if we got any audio
            import numpy as np
            max_amplitude = np.max(np.abs(recording))
            print(f"✓ Recording successful, max amplitude: {max_amplitude:.6f}")
            
            if max_amplitude < 0.001:
                print("⚠️  WARNING: Very quiet audio - check microphone levels")
            
            return True
            
        except Exception as e:
            print(f"✗ Recording failed: {e}")
            return False
            
    except ImportError:
        print("✗ sounddevice not available")
        return False
    except Exception as e:
        print(f"✗ Microphone test failed: {e}")
        return False

def test_performance_config():
    """Test performance configuration system."""
    print("\n=== Testing Performance Configuration ===")
    
    try:
        from Backend.STT.performance_configs import config_manager
        
        # Test all profiles
        profiles = ['current_default', 'optimized_default', 'balanced_fast', 'ultra_responsive']
        
        for profile_name in profiles:
            config = config_manager.get_config(profile_name)
            print(f"✓ {profile_name}: {config.model_size} model, VAD {config.vad_energy_threshold}")
        
        # Test environment variable
        os.environ['STT_PERFORMANCE_PROFILE'] = 'current_default'
        config = config_manager.get_config()
        print(f"✓ Environment variable test: {config.name}")
        
        return True
        
    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_model_loading():
    """Test if Whisper model can be loaded."""
    print("\n=== Testing Whisper Model Loading ===")
    
    try:
        from faster_whisper import WhisperModel
        from Backend.STT.performance_configs import config_manager
        
        # Test with the fastest model first
        config = config_manager.get_config('ultra_responsive')  # tiny model
        print(f"Testing with {config.model_size} model...")
        
        start_time = time.time()
        model = WhisperModel(config.model_size, device="cpu", compute_type="int8")
        load_time = time.time() - start_time
        
        print(f"✓ Model loaded successfully in {load_time:.2f}s")
        
        # Test a simple transcription
        print("Testing transcription with dummy audio...")
        import numpy as np
        
        # Generate 2 seconds of sine wave (dummy audio)
        sample_rate = 16000
        duration = 2.0
        frequency = 440  # A4 note
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio = 0.1 * np.sin(2 * np.pi * frequency * t).astype(np.float32)
        
        segments, info = model.transcribe(audio, language="en")
        segments_list = list(segments)
        
        print(f"✓ Transcription test completed ({len(segments_list)} segments)")
        if segments_list:
            for i, segment in enumerate(segments_list):
                print(f"   Segment {i+1}: '{segment.text.strip()}'")
        
        return True
        
    except Exception as e:
        print(f"✗ Model loading failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def suggest_solutions(test_results):
    """Suggest solutions based on test results."""
    print("\n=== Diagnosis and Solutions ===")
    
    if not test_results['imports']:
        print("❌ MISSING DEPENDENCIES:")
        print("   Install missing modules with pip install commands shown above")
        return
    
    if not test_results['microphone']:
        print("❌ MICROPHONE ISSUES:")
        print("   - Check if microphone is connected and not muted")
        print("   - Verify application has microphone permissions")
        print("   - Try different audio devices")
        print("   - On Linux: sudo apt-get install portaudio19-dev")
        print("   - On macOS: Check System Preferences > Security & Privacy > Microphone")
        print("   - On Windows: Check Settings > Privacy > Microphone")
        return
    
    if not test_results['config']:
        print("❌ CONFIGURATION ISSUES:")
        print("   - Check if Backend/STT/performance_configs.py exists and is correct")
        print("   - Verify Python path is set correctly")
        return
    
    if not test_results['model']:
        print("❌ MODEL LOADING ISSUES:")
        print("   - Ensure internet connection for model download")
        print("   - Check available disk space (models are large)")
        print("   - Try different model size: STT_PERFORMANCE_PROFILE=current_default")
        print("   - Clear cache: rm -rf ~/.cache/huggingface/")
        return
    
    if all(test_results.values()) or all(v for k, v in test_results.items() if k != 'websocket'):
        print("✓ ALL CORE SYSTEMS WORKING")
        print("\nPossible issues:")
        print("1. VAD settings too restrictive - try speaking louder or closer to mic")
        print("2. Model accuracy - try 'current_default' profile for better accuracy")
        print("3. Audio format issues - check sample rate and channels")
        
        print("\nQuick test commands:")
        print("   # Test with original settings")
        print("   STT_PERFORMANCE_PROFILE=current_default python -m Backend.STT.transcribe --user-session-id test")
        print("   # List all profiles")
        print("   python -m Backend.STT.transcribe --list-profiles --user-session-id test")

def main():
    """Run all diagnostic tests."""
    print("STT Transcription Diagnostic Tool")
    print("=" * 50)
    
    test_results = {
        'imports': test_imports(),
        'microphone': test_microphone_access(),
        'config': test_performance_config(),
        'model': False,  # Skip by default as it's slow
        'websocket': False  # Skip by default as backend might not be running
    }
    
    # Only test model loading if basic tests pass
    if test_results['imports'] and test_results['config']:
        print("\nContinuing with model loading test (this may take a while)...")
        test_results['model'] = test_model_loading()
    
    suggest_solutions(test_results)

if __name__ == "__main__":
    main()