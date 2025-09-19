#!/usr/bin/env python3
"""
Simple integration test to verify backend task lifecycle
"""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

async def test_backend_integration():
    """Test backend startup and shutdown with MainModel task"""
    
    # Mock minimal dependencies to avoid full setup
    import unittest.mock as mock
    
    # Create async mock instances
    mock_websocket_manager = mock.AsyncMock()
    mock_session_manager = mock.AsyncMock()
    mock_message_router = mock.AsyncMock()
    mock_explanation_service = mock.AsyncMock()
    
    with mock.patch('Backend.backend.WebSocketManager', return_value=mock_websocket_manager), \
         mock.patch('Backend.backend.SessionManager', return_value=mock_session_manager), \
         mock.patch('Backend.backend.MessageRouter', return_value=mock_message_router), \
         mock.patch('Backend.backend.ExplanationDeliveryService', return_value=mock_explanation_service), \
         mock.patch('Backend.backend.queues'), \
         mock.patch('Backend.backend.set_websocket_manager_instance'), \
         mock.patch('Backend.backend.set_session_manager_instance'), \
         mock.patch('Backend.backend.send_queue_status_to_frontend', new_callable=mock.AsyncMock):
        
        # Import backend after patching
        import Backend.backend as backend
        
        # Reset globals
        backend.main_model_task = None
        backend.main_model_instance = None
        backend.queue_status_sender_task = None
        
        print("Testing startup...")
        await backend.startup_event()
        
        # Verify MainModel task was created and stored
        assert backend.main_model_task is not None
        assert not backend.main_model_task.done()
        assert backend.main_model_instance is not None
        print("✓ MainModel task created and stored successfully")
        
        # Let it run briefly
        await asyncio.sleep(0.1)
        
        print("Testing shutdown...")
        await backend.shutdown_event()
        
        # Verify task was cancelled
        assert backend.main_model_task.done()
        print("✓ MainModel task cancelled successfully")
        
        print("✓ All integration tests passed!")

if __name__ == "__main__":
    asyncio.run(test_backend_integration())