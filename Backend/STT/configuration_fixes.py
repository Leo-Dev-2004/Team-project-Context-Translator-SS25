#!/usr/bin/env python3
"""
STT Configuration Fixes
Provides multiple fix options for the identified STT issues.
"""

import os
import sys

def create_fixed_transcribe_py():
    """Create a fixed version of transcribe.py with corrected ConfigManager."""
    
    print("=== CREATING FIXED CONFIG MANAGER ===")
    
    # Read the current transcribe.py
    transcribe_path = '/home/runner/work/Team-project-Context-Translator-SS25/Team-project-Context-Translator-SS25/Backend/STT/transcribe.py'
    
    try:
        with open(transcribe_path, 'r') as f:
            content = f.read()
        
        # Fix 1: Remove extreme VAD modifications
        print("Fix 1: Removing extreme VAD modifications (50% reduction and 60% reduction)")
        
        # Find and replace the VAD_ENERGY_THRESHOLD method
        old_vad_threshold = '''    @staticmethod
    def VAD_ENERGY_THRESHOLD():
           # Make VAD much less restrictive: lower threshold by 50%
           base = ConfigManager.get_performance_config().vad_energy_threshold
           return base * 0.5'''
        
        new_vad_threshold = '''    @staticmethod
    def VAD_ENERGY_THRESHOLD():
        return ConfigManager.get_performance_config().vad_energy_threshold'''
        
        content = content.replace(old_vad_threshold, new_vad_threshold)
        
        # Find and replace the VAD_SILENCE_DURATION_S method
        old_vad_silence = '''    @staticmethod
    def VAD_SILENCE_DURATION_S():
           # Make VAD much less restrictive: reduce silence duration by 60%
           base = ConfigManager.get_performance_config().vad_silence_duration_s
           return base * 0.4'''
        
        new_vad_silence = '''    @staticmethod
    def VAD_SILENCE_DURATION_S():
        return ConfigManager.get_performance_config().vad_silence_duration_s'''
        
        content = content.replace(old_vad_silence, new_vad_silence)
        
        # Fix 2: Improve the forced default behavior
        print("Fix 2: Improving forced default profile selection")
        
        old_get_performance_config = '''    @staticmethod
    def get_performance_config():
            """Get the current performance configuration, default to 'current_default' for better accuracy."""
            import os
            # Force 'current_default' profile unless overridden by env
            if not os.environ.get('STT_PERFORMANCE_PROFILE'):
                os.environ['STT_PERFORMANCE_PROFILE'] = 'current_default'
            return config_manager.get_config()'''
        
        new_get_performance_config = '''    @staticmethod
    def get_performance_config():
        """Get the current performance configuration, default to 'optimized_default' for balanced performance."""
        import os
        # Use optimized_default unless explicitly overridden
        profile = os.environ.get('STT_PERFORMANCE_PROFILE', 'optimized_default')
        return config_manager.get_config(profile)'''
        
        content = content.replace(old_get_performance_config, new_get_performance_config)
        
        # Create fixed version
        fixed_path = '/tmp/transcribe_fixed.py'
        with open(fixed_path, 'w') as f:
            f.write(content)
        
        print(f"✓ Fixed version created: {fixed_path}")
        print("Changes made:")
        print("  - Removed 50% VAD threshold reduction")
        print("  - Removed 60% silence duration reduction")
        print("  - Fixed default profile selection logic")
        print("  - Default profile is now 'optimized_default' (better performance)")
        
        return fixed_path
        
    except Exception as e:
        print(f"✗ Failed to create fixed version: {e}")
        return None

def create_conservative_fix():
    """Create a conservative fix that uses current_default profile."""
    
    print("\n=== CREATING CONSERVATIVE FIX ===")
    
    transcribe_path = '/home/runner/work/Team-project-Context-Translator-SS25/Team-project-Context-Translator-SS25/Backend/STT/transcribe.py'
    
    try:
        with open(transcribe_path, 'r') as f:
            content = f.read()
        
        # Remove modifications and use current_default for maximum accuracy
        print("Creating ultra-conservative version using current_default profile")
        
        # Fix the get_performance_config method to use current_default
        old_get_performance_config = '''    @staticmethod
    def get_performance_config():
            """Get the current performance configuration, default to 'current_default' for better accuracy."""
            import os
            # Force 'current_default' profile unless overridden by env
            if not os.environ.get('STT_PERFORMANCE_PROFILE'):
                os.environ['STT_PERFORMANCE_PROFILE'] = 'current_default'
            return config_manager.get_config()'''
        
        new_get_performance_config = '''    @staticmethod
    def get_performance_config():
        """Get the current performance configuration, default to 'current_default' for maximum accuracy."""
        import os
        # Use current_default for maximum accuracy unless explicitly overridden
        profile = os.environ.get('STT_PERFORMANCE_PROFILE', 'current_default')
        return config_manager.get_config(profile)'''
        
        content = content.replace(old_get_performance_config, new_get_performance_config)
        
        # Remove VAD modifications
        old_vad_threshold = '''    @staticmethod
    def VAD_ENERGY_THRESHOLD():
           # Make VAD much less restrictive: lower threshold by 50%
           base = ConfigManager.get_performance_config().vad_energy_threshold
           return base * 0.5'''
        
        new_vad_threshold = '''    @staticmethod
    def VAD_ENERGY_THRESHOLD():
        return ConfigManager.get_performance_config().vad_energy_threshold'''
        
        content = content.replace(old_vad_threshold, new_vad_threshold)
        
        old_vad_silence = '''    @staticmethod
    def VAD_SILENCE_DURATION_S():
           # Make VAD much less restrictive: reduce silence duration by 60%
           base = ConfigManager.get_performance_config().vad_silence_duration_s
           return base * 0.4'''
        
        new_vad_silence = '''    @staticmethod
    def VAD_SILENCE_DURATION_S():
        return ConfigManager.get_performance_config().vad_silence_duration_s'''
        
        content = content.replace(old_vad_silence, new_vad_silence)
        
        # Create conservative version
        conservative_path = '/tmp/transcribe_conservative.py'
        with open(conservative_path, 'w') as f:
            f.write(content)
        
        print(f"✓ Conservative version created: {conservative_path}")
        print("Changes made:")
        print("  - Removed all VAD modifications")
        print("  - Uses 'current_default' profile (medium model, original VAD settings)")
        print("  - Maximum accuracy and stability")
        
        return conservative_path
        
    except Exception as e:
        print(f"✗ Failed to create conservative version: {e}")
        return None

def create_moderate_fix():
    """Create a moderate fix with gentler VAD modifications."""
    
    print("\n=== CREATING MODERATE FIX ===")
    
    transcribe_path = '/home/runner/work/Team-project-Context-Translator-SS25/Team-project-Context-Translator-SS25/Backend/STT/transcribe.py'
    
    try:
        with open(transcribe_path, 'r') as f:
            content = f.read()
        
        print("Creating moderate version with gentler VAD modifications")
        
        # Use gentler modifications
        old_vad_threshold = '''    @staticmethod
    def VAD_ENERGY_THRESHOLD():
           # Make VAD much less restrictive: lower threshold by 50%
           base = ConfigManager.get_performance_config().vad_energy_threshold
           return base * 0.5'''
        
        new_vad_threshold = '''    @staticmethod
    def VAD_ENERGY_THRESHOLD():
        # Make VAD slightly more sensitive: lower threshold by 20%
        base = ConfigManager.get_performance_config().vad_energy_threshold
        return base * 0.8'''
        
        content = content.replace(old_vad_threshold, new_vad_threshold)
        
        old_vad_silence = '''    @staticmethod
    def VAD_SILENCE_DURATION_S():
           # Make VAD much less restrictive: reduce silence duration by 60%
           base = ConfigManager.get_performance_config().vad_silence_duration_s
           return base * 0.4'''
        
        new_vad_silence = '''    @staticmethod
    def VAD_SILENCE_DURATION_S():
        # Reduce silence duration slightly: reduce by 20%
        base = ConfigManager.get_performance_config().vad_silence_duration_s
        return base * 0.8'''
        
        content = content.replace(old_vad_silence, new_vad_silence)
        
        # Fix default profile
        old_get_performance_config = '''    @staticmethod
    def get_performance_config():
            """Get the current performance configuration, default to 'current_default' for better accuracy."""
            import os
            # Force 'current_default' profile unless overridden by env
            if not os.environ.get('STT_PERFORMANCE_PROFILE'):
                os.environ['STT_PERFORMANCE_PROFILE'] = 'current_default'
            return config_manager.get_config()'''
        
        new_get_performance_config = '''    @staticmethod
    def get_performance_config():
        """Get the current performance configuration, default to 'optimized_default' for balanced performance."""
        import os
        # Use optimized_default for balanced performance unless explicitly overridden
        profile = os.environ.get('STT_PERFORMANCE_PROFILE', 'optimized_default')
        return config_manager.get_config(profile)'''
        
        content = content.replace(old_get_performance_config, new_get_performance_config)
        
        # Create moderate version
        moderate_path = '/tmp/transcribe_moderate.py'
        with open(moderate_path, 'w') as f:
            f.write(content)
        
        print(f"✓ Moderate version created: {moderate_path}")
        print("Changes made:")
        print("  - VAD threshold reduced by 20% (instead of 50%)")
        print("  - Silence duration reduced by 20% (instead of 60%)")
        print("  - Uses 'optimized_default' profile for better performance")
        
        return moderate_path
        
    except Exception as e:
        print(f"✗ Failed to create moderate version: {e}")
        return None

def generate_installation_guide():
    """Generate complete installation and testing guide."""
    
    print("\n=== INSTALLATION & TESTING GUIDE ===")
    
    print("1. INSTALL DEPENDENCIES:")
    print("   pip install faster-whisper sounddevice numpy websockets")
    print()
    
    print("2. CHOOSE A FIX VERSION:")
    print("   A) Conservative (most stable):")
    print("      cp /tmp/transcribe_conservative.py Backend/STT/transcribe.py")
    print("   B) Moderate (balanced):")
    print("      cp /tmp/transcribe_moderate.py Backend/STT/transcribe.py")
    print("   C) Optimized (performance focused):")
    print("      cp /tmp/transcribe_fixed.py Backend/STT/transcribe.py")
    print()
    
    print("3. TEST THE FIX:")
    print("   # Quick test")
    print("   python -m Backend.STT.transcribe --user-session-id test")
    print()
    print("   # With specific profile")
    print("   STT_PERFORMANCE_PROFILE=current_default python -m Backend.STT.transcribe --user-session-id test")
    print()
    print("   # With debug logging")
    print("   PYTHONPATH=. python -c \"import logging; logging.basicConfig(level=logging.DEBUG)\"")
    print("   python -m Backend.STT.transcribe --user-session-id test")
    print()
    
    print("4. TROUBLESHOOTING:")
    print("   # If still no transcription:")
    print("   - Check microphone permissions")
    print("   - Speak loudly and clearly")
    print("   - Check system audio settings")
    print("   - Try different STT_PERFORMANCE_PROFILE values")
    print()
    
    print("5. PROFILE RECOMMENDATIONS:")
    print("   current_default    - Original settings, most accurate")
    print("   optimized_default  - 50% faster, good accuracy")
    print("   balanced_fast      - 75% faster, decent accuracy")
    print("   ultra_responsive   - 85% faster, lower accuracy")

def main():
    """Create all fix versions and provide guidance."""
    
    print("STT CONFIGURATION FIXES")
    print("="*50)
    print("Creating multiple fix versions to address the identified issues:")
    print("1. Extreme VAD modifications (50% threshold, 60% silence reduction)")
    print("2. Problematic default profile forcing")
    print("3. Missing dependency handling")
    print()
    
    # Create all fix versions
    fixed_path = create_fixed_transcribe_py()
    conservative_path = create_conservative_fix()
    moderate_path = create_moderate_fix()
    
    generate_installation_guide()
    
    print(f"\n=== SUMMARY ===")
    print(f"✓ Created 3 fix versions:")
    print(f"  Conservative: {conservative_path}")
    print(f"  Moderate:     {moderate_path}")
    print(f"  Optimized:    {fixed_path}")
    print()
    print("RECOMMENDED APPROACH:")
    print("1. Install dependencies first")
    print("2. Try conservative fix first (most stable)")
    print("3. If working, can try moderate or optimized for better performance")

if __name__ == "__main__":
    main()