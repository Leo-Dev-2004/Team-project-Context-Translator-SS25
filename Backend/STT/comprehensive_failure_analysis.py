#!/usr/bin/env python3
"""
Comprehensive STT Failure Analysis Tool
Tests every possible point of failure in the STT transcription pipeline.
"""

import os
import sys
import time
import logging
from pathlib import Path
import traceback

# Add Backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

# Setup detailed logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class STTFailureAnalyzer:
    """Systematic analysis of all possible STT failure points."""
    
    def __init__(self):
        self.test_results = {}
        self.failure_points = []
        
    def test_1_module_imports(self):
        """Test 1: Check if all required modules can be imported."""
        print("\n=== TEST 1: Module Import Analysis ===")
        
        critical_modules = [
            ('numpy', 'Core array processing'),
            ('sounddevice', 'Audio capture'),
            ('websockets', 'Backend communication'),
            ('faster_whisper', 'Speech recognition'),
            ('asyncio', 'Async processing'),
            ('threading', 'Background processing'),
            ('queue', 'Audio buffering'),
        ]
        
        import_failures = []
        for module_name, description in critical_modules:
            try:
                __import__(module_name)
                print(f"✓ {module_name:15} - {description}")
            except ImportError as e:
                print(f"✗ {module_name:15} - {description} - ERROR: {e}")
                import_failures.append((module_name, str(e)))
        
        self.test_results['imports'] = len(import_failures) == 0
        if import_failures:
            self.failure_points.append("Missing critical modules: " + ", ".join([m[0] for m in import_failures]))
        
        return len(import_failures) == 0
    
    def test_2_performance_config_system(self):
        """Test 2: Check performance configuration system integrity."""
        print("\n=== TEST 2: Performance Configuration System ===")
        
        try:
            from Backend.STT.performance_configs import config_manager, STTPerformanceConfig
            print("✓ Performance config modules imported")
            
            # Test all profiles
            profiles = ['current_default', 'optimized_default', 'balanced_fast', 'ultra_responsive', 'high_accuracy', 'streaming_optimized']
            config_failures = []
            
            for profile_name in profiles:
                try:
                    config = config_manager.get_config(profile_name)
                    print(f"✓ {profile_name:18} - {config.model_size} model, VAD {config.vad_energy_threshold}")
                    
                    # Validate config values
                    if config.vad_energy_threshold <= 0 or config.vad_energy_threshold > 1:
                        config_failures.append(f"{profile_name}: Invalid VAD threshold {config.vad_energy_threshold}")
                    if config.vad_silence_duration_s <= 0 or config.vad_silence_duration_s > 10:
                        config_failures.append(f"{profile_name}: Invalid silence duration {config.vad_silence_duration_s}")
                        
                except Exception as e:
                    print(f"✗ {profile_name:18} - ERROR: {e}")
                    config_failures.append(f"{profile_name}: {str(e)}")
            
            # Test environment variable behavior
            original_env = os.environ.get('STT_PERFORMANCE_PROFILE')
            try:
                os.environ['STT_PERFORMANCE_PROFILE'] = 'balanced_fast'
                config = config_manager.get_config()
                if config.name == 'balanced_fast':
                    print("✓ Environment variable override working")
                else:
                    config_failures.append("Environment variable override not working")
            except Exception as e:
                config_failures.append(f"Environment variable test failed: {e}")
            finally:
                if original_env:
                    os.environ['STT_PERFORMANCE_PROFILE'] = original_env
                elif 'STT_PERFORMANCE_PROFILE' in os.environ:
                    del os.environ['STT_PERFORMANCE_PROFILE']
            
            self.test_results['config_system'] = len(config_failures) == 0
            if config_failures:
                self.failure_points.extend(config_failures)
            
            return len(config_failures) == 0
            
        except Exception as e:
            print(f"✗ Configuration system failure: {e}")
            self.test_results['config_system'] = False
            self.failure_points.append(f"Configuration system error: {str(e)}")
            return False
    
    def test_3_config_manager_class(self):
        """Test 3: Check ConfigManager class and dynamic settings."""
        print("\n=== TEST 3: ConfigManager Class Analysis ===")
        
        try:
            # Import the ConfigManager from transcribe.py
            from Backend.STT.transcribe import ConfigManager
            print("✓ ConfigManager imported from transcribe.py")
            
            config_issues = []
            
            # Test static attributes
            static_attrs = ['SAMPLE_RATE', 'CHANNELS', 'LANGUAGE', 'WEBSOCKET_URI']
            for attr in static_attrs:
                try:
                    value = getattr(ConfigManager, attr)
                    print(f"✓ Static {attr}: {value}")
                except Exception as e:
                    config_issues.append(f"Static attribute {attr} failed: {e}")
            
            # Test dynamic methods
            dynamic_methods = ['MODEL_SIZE', 'VAD_ENERGY_THRESHOLD', 'VAD_SILENCE_DURATION_S', 'VAD_BUFFER_DURATION_S', 'MIN_WORDS_PER_SENTENCE']
            for method_name in dynamic_methods:
                try:
                    method = getattr(ConfigManager, method_name)
                    value = method()
                    print(f"✓ Dynamic {method_name}(): {value}")
                    
                    # Check for problematic values
                    if method_name == 'VAD_ENERGY_THRESHOLD' and (value <= 0 or value > 1):
                        config_issues.append(f"VAD_ENERGY_THRESHOLD out of range: {value}")
                    elif method_name == 'VAD_SILENCE_DURATION_S' and (value <= 0 or value > 10):
                        config_issues.append(f"VAD_SILENCE_DURATION_S out of range: {value}")
                    elif method_name == 'MODEL_SIZE' and value not in ['tiny', 'base', 'small', 'medium', 'large']:
                        config_issues.append(f"Invalid model size: {value}")
                        
                except Exception as e:
                    print(f"✗ Dynamic {method_name}() failed: {e}")
                    config_issues.append(f"Dynamic method {method_name} failed: {e}")
            
            # Test the forced 'current_default' behavior
            original_env = os.environ.get('STT_PERFORMANCE_PROFILE')
            try:
                # Clear environment variable to test forced default
                if 'STT_PERFORMANCE_PROFILE' in os.environ:
                    del os.environ['STT_PERFORMANCE_PROFILE']
                
                config = ConfigManager.get_performance_config()
                if config.name == 'current_default':
                    print("✓ Forced 'current_default' profile working")
                else:
                    config_issues.append(f"Expected 'current_default', got '{config.name}'")
                    
            except Exception as e:
                config_issues.append(f"Forced default test failed: {e}")
            finally:
                if original_env:
                    os.environ['STT_PERFORMANCE_PROFILE'] = original_env
            
            # Test the VAD modifications (50% threshold, 40% silence duration)
            try:
                base_config = ConfigManager.get_performance_config()
                modified_threshold = ConfigManager.VAD_ENERGY_THRESHOLD()
                modified_silence = ConfigManager.VAD_SILENCE_DURATION_S()
                
                expected_threshold = base_config.vad_energy_threshold * 0.5
                expected_silence = base_config.vad_silence_duration_s * 0.4
                
                if abs(modified_threshold - expected_threshold) < 0.001:
                    print(f"✓ VAD threshold modification: {base_config.vad_energy_threshold} → {modified_threshold}")
                else:
                    config_issues.append(f"VAD threshold modification incorrect: expected {expected_threshold}, got {modified_threshold}")
                
                if abs(modified_silence - expected_silence) < 0.001:
                    print(f"✓ VAD silence modification: {base_config.vad_silence_duration_s} → {modified_silence}")
                else:
                    config_issues.append(f"VAD silence modification incorrect: expected {expected_silence}, got {modified_silence}")
                    
            except Exception as e:
                config_issues.append(f"VAD modification test failed: {e}")
            
            self.test_results['config_manager'] = len(config_issues) == 0
            if config_issues:
                self.failure_points.extend(config_issues)
                
            return len(config_issues) == 0
            
        except Exception as e:
            print(f"✗ ConfigManager class test failed: {e}")
            traceback.print_exc()
            self.test_results['config_manager'] = False
            self.failure_points.append(f"ConfigManager class error: {str(e)}")
            return False
    
    def test_4_vad_settings_analysis(self):
        """Test 4: Analyze VAD settings for potential issues."""
        print("\n=== TEST 4: VAD Settings Analysis ===")
        
        try:
            from Backend.STT.transcribe import ConfigManager as Config
            
            vad_issues = []
            
            # Get actual VAD values
            energy_threshold = Config.VAD_ENERGY_THRESHOLD()
            silence_duration = Config.VAD_SILENCE_DURATION_S()
            buffer_duration = Config.VAD_BUFFER_DURATION_S()
            
            print(f"Current VAD Settings:")
            print(f"  Energy threshold: {energy_threshold:.6f}")
            print(f"  Silence duration: {silence_duration:.3f}s")
            print(f"  Buffer duration: {buffer_duration:.3f}s")
            
            # Analyze for problematic values
            if energy_threshold < 0.0005:
                vad_issues.append(f"VAD threshold too low ({energy_threshold:.6f}) - will trigger on noise")
            elif energy_threshold > 0.02:
                vad_issues.append(f"VAD threshold too high ({energy_threshold:.6f}) - will miss quiet speech")
            
            if silence_duration < 0.1:
                vad_issues.append(f"Silence duration too short ({silence_duration:.3f}s) - will cut off words")
            elif silence_duration > 3.0:
                vad_issues.append(f"Silence duration too long ({silence_duration:.3f}s) - will delay processing")
            
            if buffer_duration < 0.05:
                vad_issues.append(f"Buffer duration too short ({buffer_duration:.3f}s) - will miss speech start")
            elif buffer_duration > 2.0:
                vad_issues.append(f"Buffer duration too long ({buffer_duration:.3f}s) - will increase latency")
            
            # Check for extreme modifications that might cause issues
            base_config = Config.get_performance_config()
            original_threshold = base_config.vad_energy_threshold
            original_silence = base_config.vad_silence_duration_s
            
            threshold_reduction = (original_threshold - energy_threshold) / original_threshold * 100
            silence_reduction = (original_silence - silence_duration) / original_silence * 100
            
            print(f"VAD Modifications:")
            print(f"  Threshold reduced by: {threshold_reduction:.1f}%")
            print(f"  Silence duration reduced by: {silence_reduction:.1f}%")
            
            if threshold_reduction > 80:
                vad_issues.append(f"Extreme threshold reduction ({threshold_reduction:.1f}%) may cause false positives")
            if silence_reduction > 80:
                vad_issues.append(f"Extreme silence reduction ({silence_reduction:.1f}%) may cut off speech")
            
            self.test_results['vad_settings'] = len(vad_issues) == 0
            if vad_issues:
                self.failure_points.extend(vad_issues)
            
            for issue in vad_issues:
                print(f"⚠️  {issue}")
            
            if not vad_issues:
                print("✓ VAD settings appear reasonable")
            
            return len(vad_issues) == 0
            
        except Exception as e:
            print(f"✗ VAD settings analysis failed: {e}")
            self.test_results['vad_settings'] = False
            self.failure_points.append(f"VAD settings analysis error: {str(e)}")
            return False
    
    def test_5_stt_service_initialization(self):
        """Test 5: Check STTService initialization without model loading."""
        print("\n=== TEST 5: STTService Initialization Analysis ===")
        
        try:
            # Mock the WhisperModel to avoid actual model loading
            import unittest.mock
            
            with unittest.mock.patch('Backend.STT.transcribe.WhisperModel') as mock_whisper:
                # Setup mock
                mock_model = unittest.mock.MagicMock()
                mock_whisper.return_value = mock_model
                
                from Backend.STT.transcribe import STTService
                
                # Test service initialization
                service = STTService(user_session_id="test_session")
                print("✓ STTService initialized successfully")
                
                # Check if all attributes are properly set
                init_issues = []
                
                if not hasattr(service, 'user_session_id') or service.user_session_id != "test_session":
                    init_issues.append("user_session_id not set correctly")
                
                if not hasattr(service, 'stt_client_id') or not service.stt_client_id.startswith("stt_instance_"):
                    init_issues.append("stt_client_id not set correctly")
                
                if not hasattr(service, 'model'):
                    init_issues.append("model not set")
                
                if not hasattr(service, 'audio_queue'):
                    init_issues.append("audio_queue not initialized")
                
                if not hasattr(service, 'is_recording'):
                    init_issues.append("is_recording event not initialized")
                
                if not hasattr(service, 'transcription_times'):
                    init_issues.append("transcription_times not initialized")
                
                if not hasattr(service, 'audio_durations'):
                    init_issues.append("audio_durations not initialized")
                
                # Check if the model was called with correct parameters
                mock_whisper.assert_called_once()
                call_args = mock_whisper.call_args
                
                if call_args is None:
                    init_issues.append("WhisperModel not called")
                else:
                    args, kwargs = call_args
                    if len(args) > 0 and args[0] not in ['tiny', 'base', 'small', 'medium', 'large']:
                        init_issues.append(f"Invalid model size passed: {args[0]}")
                    
                    expected_kwargs = {'device': 'cpu', 'compute_type': 'int8'}
                    for key, value in expected_kwargs.items():
                        if key not in kwargs or kwargs[key] != value:
                            init_issues.append(f"Incorrect {key}: expected {value}, got {kwargs.get(key)}")
                
                self.test_results['stt_initialization'] = len(init_issues) == 0
                if init_issues:
                    self.failure_points.extend([f"STTService init: {issue}" for issue in init_issues])
                
                for issue in init_issues:
                    print(f"✗ {issue}")
                
                if not init_issues:
                    print("✓ All STTService attributes initialized correctly")
                
                return len(init_issues) == 0
                
        except Exception as e:
            print(f"✗ STTService initialization test failed: {e}")
            traceback.print_exc()
            self.test_results['stt_initialization'] = False
            self.failure_points.append(f"STTService initialization error: {str(e)}")
            return False
    
    def test_6_audio_pipeline_components(self):
        """Test 6: Check audio pipeline components."""
        print("\n=== TEST 6: Audio Pipeline Components ===")
        
        pipeline_issues = []
        
        # Test sounddevice availability
        try:
            import sounddevice as sd
            print("✓ sounddevice module available")
            
            # Test device listing
            try:
                devices = sd.query_devices()
                input_devices = [d for d in devices if d['max_input_channels'] > 0]
                print(f"✓ Found {len(input_devices)} audio input devices")
                
                if len(input_devices) == 0:
                    pipeline_issues.append("No audio input devices found")
                
            except Exception as e:
                pipeline_issues.append(f"Audio device query failed: {e}")
                
        except (ImportError, OSError) as e:
            pipeline_issues.append(f"sounddevice not available: {e}")
        
        # Test numpy for audio processing
        try:
            import numpy as np
            print("✓ numpy available for audio processing")
            
            # Test basic audio operations
            sample_rate = 16000
            duration = 1.0
            samples = int(sample_rate * duration)
            
            # Test audio array creation
            audio = np.random.random(samples).astype(np.float32)
            energy = np.sqrt(np.mean(np.square(audio)))
            
            if energy <= 0:
                pipeline_issues.append("Audio energy calculation failed")
            else:
                print(f"✓ Audio energy calculation working: {energy:.6f}")
                
        except Exception as e:
            pipeline_issues.append(f"Audio processing test failed: {e}")
        
        # Test queue system
        try:
            import queue
            import threading
            
            audio_queue = queue.Queue()
            is_recording = threading.Event()
            
            # Test queue operations
            test_data = b"test_audio_data"
            audio_queue.put(test_data)
            
            retrieved = audio_queue.get(timeout=1.0)
            if retrieved == test_data:
                print("✓ Audio queue operations working")
            else:
                pipeline_issues.append("Audio queue data integrity failed")
                
            # Test threading event
            is_recording.set()
            if is_recording.is_set():
                print("✓ Threading event operations working")
            else:
                pipeline_issues.append("Threading event operations failed")
                
        except Exception as e:
            pipeline_issues.append(f"Queue/threading test failed: {e}")
        
        self.test_results['audio_pipeline'] = len(pipeline_issues) == 0
        if pipeline_issues:
            self.failure_points.extend([f"Audio pipeline: {issue}" for issue in pipeline_issues])
        
        for issue in pipeline_issues:
            print(f"✗ {issue}")
        
        return len(pipeline_issues) == 0
    
    def test_7_websocket_connectivity(self):
        """Test 7: Check WebSocket connectivity potential."""
        print("\n=== TEST 7: WebSocket Connectivity Analysis ===")
        
        websocket_issues = []
        
        try:
            import websockets
            print("✓ websockets module available")
            
            # Test WebSocket URI construction
            from Backend.STT.transcribe import ConfigManager as Config
            
            base_uri = Config.WEBSOCKET_URI
            test_client_id = "test_client_123"
            full_uri = f"{base_uri}/{test_client_id}"
            
            print(f"✓ WebSocket URI construction: {full_uri}")
            
            # Basic URI validation
            if not full_uri.startswith("ws://"):
                websocket_issues.append("WebSocket URI doesn't start with ws://")
            
            if "localhost" not in full_uri and "127.0.0.1" not in full_uri:
                websocket_issues.append("WebSocket URI doesn't target localhost")
            
            # Note: We can't actually test connection without running backend
            print("⚠️  WebSocket connection test requires running backend server")
            
        except ImportError as e:
            websocket_issues.append(f"websockets module not available: {e}")
        except Exception as e:
            websocket_issues.append(f"WebSocket analysis failed: {e}")
        
        self.test_results['websocket'] = len(websocket_issues) == 0
        if websocket_issues:
            self.failure_points.extend([f"WebSocket: {issue}" for issue in websocket_issues])
        
        for issue in websocket_issues:
            print(f"✗ {issue}")
        
        return len(websocket_issues) == 0
    
    def generate_failure_report(self):
        """Generate comprehensive failure analysis report."""
        print("\n" + "="*70)
        print("COMPREHENSIVE STT FAILURE ANALYSIS REPORT")
        print("="*70)
        
        print(f"\nTest Results Summary:")
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result)
        
        for test_name, passed in self.test_results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"  {test_name:<25}: {status}")
        
        print(f"\nOverall: {passed_tests}/{total_tests} tests passed")
        
        if self.failure_points:
            print(f"\n🔥 IDENTIFIED FAILURE POINTS ({len(self.failure_points)}):")
            for i, failure in enumerate(self.failure_points, 1):
                print(f"  {i:2}. {failure}")
        
        print(f"\n💡 RECOMMENDED ACTIONS:")
        
        if not self.test_results.get('imports', True):
            print("  1. CRITICAL: Install missing dependencies")
            print("     - pip install faster-whisper sounddevice websockets numpy")
        
        if not self.test_results.get('config_system', True) or not self.test_results.get('config_manager', True):
            print("  2. CRITICAL: Configuration system failure")
            print("     - Check Backend/STT/performance_configs.py")
            print("     - Verify Python path and imports")
        
        if not self.test_results.get('vad_settings', True):
            print("  3. HIGH: VAD settings causing issues")
            print("     - Current modifications may be too extreme")
            print("     - Try: STT_PERFORMANCE_PROFILE=current_default")
            print("     - Or remove the 50%/40% modifications in ConfigManager")
        
        if not self.test_results.get('audio_pipeline', True):
            print("  4. HIGH: Audio pipeline issues")
            print("     - Check microphone permissions")
            print("     - Verify audio drivers and hardware")
            print("     - Test with different audio devices")
        
        if not self.test_results.get('stt_initialization', True):
            print("  5. MEDIUM: STTService initialization problems")
            print("     - Check model loading and dependencies")
            print("     - Verify network connectivity for model download")
        
        if not self.test_results.get('websocket', True):
            print("  6. LOW: WebSocket connectivity (optional for testing)")
            print("     - Start backend server: python Backend/backend.py")
            print("     - Check port 8000 availability")
        
        print(f"\n🔧 DEBUGGING COMMANDS:")
        print("  # Test with original settings")
        print("  STT_PERFORMANCE_PROFILE=current_default python -m Backend.STT.transcribe --user-session-id test")
        print("  # Enable verbose logging")
        print("  python -c \"import logging; logging.basicConfig(level=logging.DEBUG)\" -m Backend.STT.transcribe --user-session-id test")
        print("  # Run basic diagnostic")
        print("  python Backend/STT/debug_stt.py")
        
        return passed_tests == total_tests

def main():
    """Run comprehensive failure analysis."""
    print("STT Comprehensive Failure Analysis")
    print("This tool systematically tests every component of the STT pipeline")
    print("to identify exactly why transcription might not be working.\n")
    
    analyzer = STTFailureAnalyzer()
    
    # Run all tests
    tests = [
        analyzer.test_1_module_imports,
        analyzer.test_2_performance_config_system,
        analyzer.test_3_config_manager_class,
        analyzer.test_4_vad_settings_analysis,
        analyzer.test_5_stt_service_initialization,
        analyzer.test_6_audio_pipeline_components,
        analyzer.test_7_websocket_connectivity,
    ]
    
    for test_func in tests:
        try:
            test_func()
        except Exception as e:
            print(f"TEST EXCEPTION: {test_func.__name__} failed with {e}")
            analyzer.failure_points.append(f"{test_func.__name__} exception: {str(e)}")
    
    # Generate final report
    all_passed = analyzer.generate_failure_report()
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED - STT system should be working!")
        print("If transcription still fails, the issue may be environmental")
        print("(microphone hardware, permissions, audio levels, etc.)")
    else:
        print("\n⚠️  ISSUES FOUND - Follow the recommended actions above")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)