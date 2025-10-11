#!/usr/bin/env python3
"""
Targeted STT Issue Analysis and Solutions
Focuses on the specific problems identified in the current implementation.
"""

import os
import sys

# Add Backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

def analyze_configuration_issues():
    """Analyze configuration-specific issues."""
    print("=== CONFIGURATION ANALYSIS ===")
    
    try:
        from Backend.STT.performance_configs import config_manager
        
        # Test the forced 'current_default' behavior
        original_env = os.environ.get('STT_PERFORMANCE_PROFILE')
        
        # Clear env var to test forced behavior
        if 'STT_PERFORMANCE_PROFILE' in os.environ:
            del os.environ['STT_PERFORMANCE_PROFILE']
        
        # This should trigger the forced 'current_default' in ConfigManager.get_performance_config()
        base_config = config_manager.get_config()
        print(f"✓ Base configuration would be: {base_config.name}")
        print(f"  Model: {base_config.model_size}")
        print(f"  VAD threshold: {base_config.vad_energy_threshold}")
        print(f"  Silence duration: {base_config.vad_silence_duration_s}s")
        
        # Calculate what the modifications would do
        modified_threshold = base_config.vad_energy_threshold * 0.5
        modified_silence = base_config.vad_silence_duration_s * 0.4
        
        print(f"\nCurrent ConfigManager modifications:")
        print(f"  Original threshold: {base_config.vad_energy_threshold:.6f}")
        print(f"  Modified threshold: {modified_threshold:.6f} (50% reduction)")
        print(f"  Original silence: {base_config.vad_silence_duration_s:.3f}s") 
        print(f"  Modified silence: {modified_silence:.3f}s (60% reduction)")
        
        # Analyze these values
        print(f"\nAnalysis of modifications:")
        issues = []
        
        if modified_threshold < 0.001:
            issues.append("CRITICAL: VAD threshold too low - will trigger on background noise")
        elif modified_threshold < 0.002:
            issues.append("WARNING: VAD threshold very low - may cause false positives")
            
        if modified_silence < 0.2:
            issues.append("CRITICAL: Silence duration too short - will cut off speech")
        elif modified_silence < 0.4:
            issues.append("WARNING: Silence duration very short - may be too aggressive")
        
        if issues:
            print("  🔥 IDENTIFIED ISSUES:")
            for issue in issues:
                print(f"     {issue}")
        else:
            print("  ✓ Modifications appear reasonable")
        
        # Restore environment
        if original_env:
            os.environ['STT_PERFORMANCE_PROFILE'] = original_env
            
        return len(issues) == 0
        
    except Exception as e:
        print(f"✗ Configuration analysis failed: {e}")
        return False

def test_import_issues():
    """Test import issues and suggest solutions."""
    print("\n=== IMPORT DEPENDENCY ANALYSIS ===")
    
    missing_modules = []
    
    # Test critical imports
    try:
        import numpy as np
        print("✓ numpy - available")
    except ImportError:
        print("✗ numpy - MISSING")
        missing_modules.append("numpy")
    
    try:
        import websockets
        print("✓ websockets - available") 
    except ImportError:
        print("✗ websockets - MISSING")
        missing_modules.append("websockets")
        
    try:
        import sounddevice as sd
        print("✓ sounddevice - available")
    except (ImportError, OSError) as e:
        print(f"✗ sounddevice - MISSING ({e})")
        missing_modules.append("sounddevice")
        
    try:
        from faster_whisper import WhisperModel
        print("✓ faster_whisper - available")
    except ImportError as e:
        print(f"✗ faster_whisper - MISSING ({e})")
        missing_modules.append("faster-whisper")
    
    if missing_modules:
        print(f"\n🔥 CRITICAL: Missing dependencies!")
        print(f"Install command: pip install {' '.join(missing_modules)}")
        
    return len(missing_modules) == 0

def create_minimal_test_script():
    """Create a minimal test script without dependencies."""
    script_content = '''#!/usr/bin/env python3
"""
Minimal STT Test Script - Tests configuration without heavy dependencies
"""

import os
import sys

sys.path.append('.')

def test_config_without_dependencies():
    """Test configuration system without importing transcribe.py"""
    print("=== MINIMAL CONFIGURATION TEST ===")
    
    try:
        from Backend.STT.performance_configs import config_manager
        
        # Clear environment to test forced behavior
        if 'STT_PERFORMANCE_PROFILE' in os.environ:
            del os.environ['STT_PERFORMANCE_PROFILE']
        
        # This gets the config that ConfigManager.get_performance_config() would force
        config = config_manager.get_config('current_default')  # What it forces to
        
        print(f"Base config: {config.name}")
        print(f"  Model: {config.model_size}")
        print(f"  VAD threshold: {config.vad_energy_threshold:.6f}")
        print(f"  Silence duration: {config.vad_silence_duration_s:.3f}s")
        
        # Simulate the ConfigManager modifications
        modified_threshold = config.vad_energy_threshold * 0.5
        modified_silence = config.vad_silence_duration_s * 0.4
        
        print(f"\\nAfter ConfigManager modifications:")
        print(f"  VAD threshold: {modified_threshold:.6f} (reduced by 50%)")
        print(f"  Silence duration: {modified_silence:.3f}s (reduced by 60%)")
        
        # Check for extreme values
        warnings = []
        if modified_threshold < 0.001:
            warnings.append("VAD threshold extremely low - will cause false positives")
        if modified_silence < 0.2:
            warnings.append("Silence duration extremely short - will cut off speech")
            
        if warnings:
            print("\\n⚠️  POTENTIAL ISSUES:")
            for warning in warnings:
                print(f"  {warning}")
        else:
            print("\\n✓ Values appear reasonable")
            
        return True
        
    except Exception as e:
        print(f"Configuration test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_config_without_dependencies()
    print(f"\\nResult: {'SUCCESS' if success else 'FAILURE'}")
'''
    
    with open('/tmp/minimal_stt_test.py', 'w') as f:
        f.write(script_content)
    
    print("\n=== MINIMAL TEST SCRIPT CREATED ===")
    print("Created: /tmp/minimal_stt_test.py")
    print("This script tests configuration without heavy dependencies")
    
def generate_fix_recommendations():
    """Generate specific fix recommendations."""
    print("\n=== SPECIFIC FIX RECOMMENDATIONS ===")
    
    print("🔥 IMMEDIATE ACTIONS (High Priority):")
    print("1. Install missing dependencies:")
    print("   pip install faster-whisper sounddevice numpy websockets")
    print()
    
    print("2. Fix the extreme VAD modifications in ConfigManager:")
    print("   The current 50% threshold reduction and 60% silence reduction are too extreme")
    print("   EITHER:")
    print("   A) Revert to original values (remove * 0.5 and * 0.4 modifications)")
    print("   B) Use less aggressive modifications (e.g., * 0.8 and * 0.7)")
    print()
    
    print("3. Test with original settings:")
    print("   STT_PERFORMANCE_PROFILE=current_default python -m Backend.STT.transcribe --user-session-id test")
    print()
    
    print("📋 TESTING STRATEGY (Medium Priority):")
    print("1. Start with original unmodified settings")
    print("2. Verify microphone access and permissions")
    print("3. Test with loud, clear speech close to microphone")
    print("4. Check logs for specific error messages")
    print("5. Gradually adjust VAD settings if needed")
    print()
    
    print("🔧 DIAGNOSTIC COMMANDS:")
    print("# Test minimal configuration")
    print("python /tmp/minimal_stt_test.py")
    print()
    print("# Test original STT with debug logging")
    print("PYTHONPATH=. python -c \"import logging; logging.basicConfig(level=logging.DEBUG)\" \\")
    print("  -c \"exec(open('Backend/STT/transcribe.py').read())\"")
    print()
    print("# Run comprehensive diagnostic")
    print("python Backend/STT/debug_stt.py")

def main():
    """Run targeted analysis."""
    print("TARGETED STT ISSUE ANALYSIS")
    print("="*50)
    
    config_ok = analyze_configuration_issues()
    imports_ok = test_import_issues() 
    
    create_minimal_test_script()
    generate_fix_recommendations()
    
    print(f"\n=== SUMMARY ===")
    print(f"Configuration system: {'✓ OK' if config_ok else '✗ ISSUES'}")
    print(f"Dependencies: {'✓ OK' if imports_ok else '✗ MISSING'}")
    
    if not imports_ok:
        print("\n🔥 PRIMARY ISSUE: Missing dependencies - install them first")
    elif not config_ok:
        print("\n🔥 PRIMARY ISSUE: VAD configuration too extreme - causing transcription failure")
    else:
        print("\n✓ Configuration appears OK - issue may be environmental")

if __name__ == "__main__":
    main()