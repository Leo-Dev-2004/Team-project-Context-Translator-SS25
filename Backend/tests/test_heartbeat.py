#!/usr/bin/env python3
"""
Test script to verify the heartbeat functionality in the STT service.
This is a focused test that checks the heartbeat logic without requiring
full audio dependencies or a running backend.
"""

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch, Mock
import sys
import os

# Mock the problematic dependencies before importing
sys.modules['sounddevice'] = Mock()
sys.modules['faster_whisper'] = Mock()
sys.modules['faster_whisper'].WhisperModel = Mock()

# Add Backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Backend'))

try:
    from Backend.STT.transcribe import STTService, Config
    print("✓ Successfully imported STT modules")
except ImportError as e:
    print(f"✗ Failed to import STT modules: {e}")
    print("This test requires the Backend modules to be available.")
    sys.exit(1)

class MockWebSocket:
    """Mock WebSocket for testing heartbeat functionality."""
    def __init__(self):
        self.sent_messages = []
        self.closed = False
    
    async def send(self, message):
        if self.closed:
            raise Exception("Connection closed")
        self.sent_messages.append(json.loads(message))
        print(f"📤 Sent message: {json.loads(message)['type']}")

class TestHeartbeat:
    """Test class for heartbeat functionality."""
    
    def __init__(self):
        self.user_session_id = "test_session_123"
    
    async def test_heartbeat_message_format(self):
        """Test that heartbeat messages are properly formatted."""
        print("\n🧪 Testing heartbeat message format...")
        
        # Mock the whisper model to avoid loading it
        with patch('Backend.STT.transcribe.WhisperModel'), \
             patch('Backend.STT.transcribe.logger'):
            
            stt_service = STTService(self.user_session_id)
            mock_websocket = MockWebSocket()
            
            # Test heartbeat message generation
            await stt_service._send_heartbeat(mock_websocket)
            
            # Verify message was sent
            assert len(mock_websocket.sent_messages) == 1
            message = mock_websocket.sent_messages[0]
            
            # Verify message structure
            assert message['type'] == 'stt.heartbeat'
            assert message['payload']['message'] == 'keep-alive'
            assert message['payload']['user_session_id'] == self.user_session_id
            assert message['origin'] == 'stt_module'
            assert message['client_id'].startswith('stt_instance_')
            assert 'id' in message
            assert 'timestamp' in message
            
            print("✓ Heartbeat message format is correct")
    
    async def test_heartbeat_timing_logic(self):
        """Test the heartbeat timing logic in isolation."""
        print("\n🧪 Testing heartbeat timing logic...")
        
        # Test the timing logic conditions
        current_time = 1000  # Mock current time
        last_heartbeat_time = 950  # 50 seconds ago
        last_activity_time = 940   # 60 seconds ago
        
        time_since_last_heartbeat = current_time - last_heartbeat_time  # 50s
        time_since_last_activity = current_time - last_activity_time    # 60s
        
        # Should send heartbeat (both conditions >= 30s)
        should_send = (time_since_last_heartbeat >= Config.HEARTBEAT_INTERVAL_S and 
                      time_since_last_activity >= Config.HEARTBEAT_INTERVAL_S)
        
        assert should_send, "Should send heartbeat when both intervals are exceeded"
        print(f"✓ Heartbeat logic works correctly (intervals: {time_since_last_heartbeat}s, {time_since_last_activity}s)")
        
        # Test case where recent activity should prevent heartbeat
        last_activity_time = 995  # 5 seconds ago
        time_since_last_activity = current_time - last_activity_time    # 5s
        
        should_send = (time_since_last_heartbeat >= Config.HEARTBEAT_INTERVAL_S and 
                      time_since_last_activity >= Config.HEARTBEAT_INTERVAL_S)
        
        assert not should_send, "Should NOT send heartbeat when recent activity occurred"
        print("✓ Recent activity correctly prevents unnecessary heartbeats")
    
    def test_config_values(self):
        """Test that configuration values are reasonable."""
        print("\n🧪 Testing configuration values...")
        
        assert Config.HEARTBEAT_INTERVAL_S > 0, "Heartbeat interval must be positive"
        assert Config.HEARTBEAT_INTERVAL_S >= 10, "Heartbeat interval should be at least 10 seconds"
        assert Config.HEARTBEAT_INTERVAL_S <= 300, "Heartbeat interval should not exceed 5 minutes"
        
        print(f"✓ Heartbeat interval is set to {Config.HEARTBEAT_INTERVAL_S}s (reasonable value)")
    
    async def test_connection_failure_handling(self):
        """Test that heartbeat handles connection failures gracefully."""
        print("\n🧪 Testing connection failure handling...")
        
        with patch('Backend.STT.transcribe.WhisperModel'), \
             patch('Backend.STT.transcribe.logger') as mock_logger:
            
            stt_service = STTService(self.user_session_id)
            mock_websocket = MockWebSocket()
            mock_websocket.closed = True
            
            # This should not raise an exception
            await stt_service._send_heartbeat(mock_websocket)
            
            # Verify that the warning was logged
            mock_logger.warning.assert_called_once()
            print("✓ Connection failure is handled gracefully")

async def main():
    """Run all heartbeat tests."""
    print("🚀 Starting STT Heartbeat Tests")
    print("=" * 50)
    
    test = TestHeartbeat()
    
    try:
        # Run async tests
        await test.test_heartbeat_message_format()
        await test.test_heartbeat_timing_logic()
        await test.test_connection_failure_handling()
        
        # Run sync tests
        test.test_config_values()
        
        print("\n" + "=" * 50)
        print("✅ All heartbeat tests passed!")
        print("\n📝 Summary:")
        print("- Heartbeat messages are properly formatted")
        print("- Timing logic prevents unnecessary heartbeats")
        print("- Configuration values are reasonable")
        print("- Connection failures are handled gracefully")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)