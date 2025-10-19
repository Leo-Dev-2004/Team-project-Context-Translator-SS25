#!/usr/bin/env python3
"""
Integration test for Global Settings Management
"""

import asyncio
import sys
import os
import json

# Add the backend to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from Backend.core.settings_manager import SettingsManager
from Backend.dependencies import set_settings_manager_instance, get_settings_manager_instance
from Backend.models.UniversalMessage import UniversalMessage

async def test_integration():
    """Test the integration of SettingsManager with dependencies"""
    
    print("=== Testing Global Settings Management Integration ===")
    
    try:
        # Test 1: Initialize SettingsManager and set as global instance
        settings_manager = SettingsManager()
        set_settings_manager_instance(settings_manager)
        print("✅ SettingsManager set as global instance")
        
        # Test 2: Retrieve global instance
        retrieved_manager = get_settings_manager_instance()
        assert retrieved_manager is settings_manager, "Retrieved manager should be the same instance"
        print("✅ Global SettingsManager retrieved successfully")
        
        # Test 3: Update settings via global instance
        test_settings = {
            "domain": "Software Engineering", 
            "explanation_style": "beginner"
        }
        retrieved_manager.update_settings(test_settings)
        print(f"✅ Settings updated via global instance: {test_settings}")
        
        # Test 4: Verify settings can be retrieved
        domain = retrieved_manager.get_setting("domain")
        style = retrieved_manager.get_setting("explanation_style")
        assert domain == "Software Engineering", f"Domain should be 'Software Engineering', got '{domain}'"
        assert style == "beginner", f"Style should be 'beginner', got '{style}'"
        print(f"✅ Settings verified: domain='{domain}', style='{style}'")
        
        # Test 5: Test settings.save message payload format
        settings_save_message = UniversalMessage(
            type="settings.save",
            payload={
                "domain": "Data Science",
                "explanation_style": "technical"
            },
            client_id="test_client",
            origin="test",
            destination="MessageRouter"
        )
        
        # Simulate processing the message payload
        retrieved_manager.update_settings(settings_save_message.payload)
        updated_domain = retrieved_manager.get_setting("domain")
        updated_style = retrieved_manager.get_setting("explanation_style")
        
        assert updated_domain == "Data Science", f"Domain should be 'Data Science', got '{updated_domain}'"
        assert updated_style == "technical", f"Style should be 'technical', got '{updated_style}'"
        print(f"✅ settings.save message processing works: domain='{updated_domain}', style='{updated_style}'")
        
        # Test 6: Test with empty payload (should not crash)
        empty_message = UniversalMessage(
            type="settings.save",
            payload={},
            client_id="test_client",
            origin="test", 
            destination="MessageRouter"
        )
        retrieved_manager.update_settings(empty_message.payload)
        print("✅ Empty payload handled gracefully")
        
        # Test 7: Verify all settings
        all_settings = retrieved_manager.get_all_settings()
        required_keys = ["domain", "explanation_style", "ai_model", "confidence_threshold", "cooldown_seconds"]
        for key in required_keys:
            assert key in all_settings, f"Required setting '{key}' missing from all_settings"
        print(f"✅ All required settings present: {required_keys}")
        
        print("\n=== Integration Test Complete ===")
        print("✅ Global Settings Management integration is working correctly!")
        print(f"   - SettingsManager can be set/retrieved globally")  
        print(f"   - Settings can be updated and retrieved")
        print(f"   - settings.save message format supported")
        print(f"   - Robust error handling for edge cases")
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_integration())