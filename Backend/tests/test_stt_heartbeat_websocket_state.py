#!/usr/bin/env python3
"""
Test script for STT heartbeat WebSocket state checking
Verifies that the heartbeat mechanism properly checks WebSocket state
before attempting to send messages, preventing "no close frame" errors.
"""

import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock, patch, Mock
import json

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Mock ALL heavy dependencies before importing
mock_numpy = MagicMock()
mock_numpy.ndarray = type('ndarray', (), {})
sys.modules['numpy'] = mock_numpy
sys.modules['sounddevice'] = MagicMock()

# Mock WhisperModel
mock_whisper = MagicMock()
mock_whisper_model = MagicMock()
mock_whisper.WhisperModel = Mock(return_value=mock_whisper_model)
sys.modules['faster_whisper'] = mock_whisper

from Backend.STT.transcribe import STTService

async def test_heartbeat_with_closed_websocket():
    """Test that heartbeat gracefully handles a closed WebSocket"""
    
    print("=== Testing Heartbeat with Closed WebSocket ===")
    
    # Create STT service instance
    stt_service = STTService(user_session_id="test_session_123")
    
    # Create mock websocket that is closed
    mock_websocket = MagicMock()
    mock_websocket.open = False  # WebSocket is closed
    mock_websocket.send = AsyncMock()
    
    # Test heartbeat with closed websocket
    print("Testing heartbeat with closed WebSocket...")
    await stt_service._send_heartbeat(mock_websocket)
    
    # Verify that send was NOT called (because websocket is closed)
    assert not mock_websocket.send.called, "send() should not be called when WebSocket is closed"
    print("✓ Heartbeat correctly skipped when WebSocket is closed")
    
    # Now test with open websocket
    mock_websocket.open = True
    await stt_service._send_heartbeat(mock_websocket)
    
    # Verify that send WAS called (because websocket is open)
    assert mock_websocket.send.called, "send() should be called when WebSocket is open"
    print("✓ Heartbeat correctly sent when WebSocket is open")
    
    # Verify message structure
    sent_message = json.loads(mock_websocket.send.call_args[0][0])
    assert sent_message['type'] == 'stt.heartbeat', "Message type should be stt.heartbeat"
    assert sent_message['payload']['message'] == 'keep-alive', "Payload should contain keep-alive message"
    print("✓ Heartbeat message structure is correct")
    
    print("\n=== Heartbeat WebSocket State Test PASSED ===\n")

async def test_send_sentence_with_closed_websocket():
    """Test that _send_sentence gracefully handles a closed WebSocket"""
    
    print("=== Testing Send Sentence with Closed WebSocket ===")
    
    # Create STT service instance
    stt_service = STTService(user_session_id="test_session_123")
    
    # Create mock websocket that is closed
    mock_websocket = MagicMock()
    mock_websocket.open = False  # WebSocket is closed
    mock_websocket.send = AsyncMock()
    
    test_sentence = "This is a test sentence"
    
    # Test send_sentence with closed websocket
    print("Testing send_sentence with closed WebSocket...")
    await stt_service._send_sentence(mock_websocket, test_sentence, is_interim=False)
    
    # Verify that send was NOT called (because websocket is closed)
    assert not mock_websocket.send.called, "send() should not be called when WebSocket is closed"
    
    # Verify that the message was buffered for retry
    assert len(stt_service.unsent_sentences) == 1, "Message should be buffered when WebSocket is closed"
    assert stt_service.unsent_sentences[0]['payload']['text'] == test_sentence, "Buffered message should contain the test sentence"
    print("✓ Sentence correctly buffered when WebSocket is closed")
    
    # Clear buffer
    stt_service.unsent_sentences.clear()
    
    # Now test with open websocket
    mock_websocket.open = True
    await stt_service._send_sentence(mock_websocket, test_sentence, is_interim=False)
    
    # Verify that send WAS called (because websocket is open)
    assert mock_websocket.send.called, "send() should be called when WebSocket is open"
    print("✓ Sentence correctly sent when WebSocket is open")
    
    # Verify that message was NOT buffered (because it was sent successfully)
    assert len(stt_service.unsent_sentences) == 0, "Message should not be buffered when sent successfully"
    print("✓ Sentence not buffered when successfully sent")
    
    print("\n=== Send Sentence WebSocket State Test PASSED ===\n")

async def test_websocket_error_handling():
    """Test that WebSocket errors are caught and handled gracefully"""
    
    print("=== Testing WebSocket Error Handling ===")
    
    # Create STT service instance
    stt_service = STTService(user_session_id="test_session_123")
    
    # Create mock websocket that raises an error on send
    mock_websocket = MagicMock()
    mock_websocket.open = True
    mock_websocket.send = AsyncMock(side_effect=Exception("Connection error: no close frame received or sent"))
    
    test_sentence = "This is a test sentence"
    
    # Test send_sentence with error
    print("Testing send_sentence with connection error...")
    await stt_service._send_sentence(mock_websocket, test_sentence, is_interim=False)
    
    # Verify that the message was buffered for retry (error handling worked)
    assert len(stt_service.unsent_sentences) == 1, "Message should be buffered when send fails"
    print("✓ Sentence correctly buffered when send fails")
    
    # Clear buffer
    stt_service.unsent_sentences.clear()
    
    # Test heartbeat with error - should just log and continue
    print("Testing heartbeat with connection error...")
    await stt_service._send_heartbeat(mock_websocket)
    
    # Heartbeat errors should not buffer (they're just skipped)
    assert len(stt_service.unsent_sentences) == 0, "Heartbeat errors should not buffer messages"
    print("✓ Heartbeat error handled gracefully (not buffered)")
    
    print("\n=== WebSocket Error Handling Test PASSED ===\n")

async def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("STT HEARTBEAT WEBSOCKET STATE TESTS")
    print("="*60 + "\n")
    
    try:
        await test_heartbeat_with_closed_websocket()
        await test_send_sentence_with_closed_websocket()
        await test_websocket_error_handling()
        
        print("="*60)
        print("ALL TESTS PASSED ✓")
        print("="*60 + "\n")
        return 0
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        return 1
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
