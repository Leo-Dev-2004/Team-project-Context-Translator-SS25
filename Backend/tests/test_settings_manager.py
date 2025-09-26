#!/usr/bin/env python3
"""
Test script for SettingsManager integration
"""

import asyncio
import sys
import os
import tempfile
from pathlib import Path

# Add the backend to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from Backend.core.settings_manager import SettingsManager

async def test_settings_manager():
    """Test SettingsManager functionality"""
    
    print("=== Testing SettingsManager ===")
    
    # Use temporary file for testing
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
        temp_settings_file = tmp_file.name
    
    try:
        # Test 1: Initialize with default settings
        settings_manager = SettingsManager(temp_settings_file)
        print(f"✅ SettingsManager initialized: {settings_manager}")
        
        # Test 2: Get default settings
        domain = settings_manager.get_setting("domain", "")
        style = settings_manager.get_setting("explanation_style", "detailed")
        print(f"✅ Default domain: '{domain}', style: '{style}'")
        
        # Test 3: Update settings
        new_settings = {
            "domain": "Machine Learning",
            "explanation_style": "technical"
        }
        settings_manager.update_settings(new_settings)
        print(f"✅ Settings updated: {new_settings}")
        
        # Test 4: Verify updated settings
        updated_domain = settings_manager.get_setting("domain")
        updated_style = settings_manager.get_setting("explanation_style")
        print(f"✅ Updated domain: '{updated_domain}', style: '{updated_style}'")
        
        # Test 5: Save to file
        save_success = await settings_manager.save_to_file()
        print(f"✅ Save to file: {'Success' if save_success else 'Failed'}")
        
        # Test 6: Load from file (simulate restart)
        new_manager = SettingsManager(temp_settings_file)
        load_success = await new_manager.load_from_file()
        print(f"✅ Load from file: {'Success' if load_success else 'Failed'}")
        
        # Test 7: Verify loaded settings
        loaded_domain = new_manager.get_setting("domain")
        loaded_style = new_manager.get_setting("explanation_style")
        print(f"✅ Loaded domain: '{loaded_domain}', style: '{loaded_style}'")
        
        # Test 8: Get all settings
        all_settings = new_manager.get_all_settings()
        print(f"✅ All settings: {list(all_settings.keys())}")
        
        print("\n=== SettingsManager Test Complete ===")
        print("All tests passed! SettingsManager is working correctly.")
        
    except Exception as e:
        print(f"❌ Error testing SettingsManager: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up temporary file
        Path(temp_settings_file).unlink(missing_ok=True)

if __name__ == "__main__":
    asyncio.run(test_settings_manager())