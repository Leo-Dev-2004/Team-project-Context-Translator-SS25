#!/usr/bin/env python3
"""
Test script for backend startup/shutdown lifecycle including MainModel task management
"""

import asyncio
import pytest
import sys
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add Backend to Python path for imports
sys.path.append(str(Path(__file__).parent.parent))

@pytest.mark.asyncio
async def test_backend_task_lifecycle():
    """Test that backend properly manages MainModel task lifecycle"""
    
    # Mock dependencies
    with patch('Backend.backend.WebSocketManager') as mock_websocket_manager, \
         patch('Backend.backend.SessionManager') as mock_session_manager, \
         patch('Backend.backend.MessageRouter') as mock_message_router, \
         patch('Backend.backend.ExplanationDeliveryService') as mock_explanation_service, \
         patch('Backend.backend.MainModel') as mock_main_model:
        
        # Configure mocks
        mock_main_model_instance = AsyncMock()
        mock_main_model.return_value = mock_main_model_instance
        mock_main_model_instance.run_continuous_processing = AsyncMock()
        
        mock_websocket_manager_instance = AsyncMock()
        mock_websocket_manager.return_value = mock_websocket_manager_instance
        
        mock_session_manager_instance = AsyncMock()
        mock_session_manager.return_value = mock_session_manager_instance
        
        mock_message_router_instance = AsyncMock()
        mock_message_router.return_value = mock_message_router_instance
        
        mock_explanation_service_instance = AsyncMock()
        mock_explanation_service.return_value = mock_explanation_service_instance
        
        # Import backend after mocking dependencies
        from Backend import backend
        
        # Reset globals for clean test
        backend.main_model_task = None
        backend.main_model_instance = None
        backend.queue_status_sender_task = None
        
        # Test startup
        await backend.startup_event()
        
        # Verify MainModel task was created and stored
        assert backend.main_model_task is not None
        assert not backend.main_model_task.done()
        assert backend.main_model_instance is not None
        
        # Test shutdown
        await backend.shutdown_event()
        
        # Verify task was cancelled
        assert backend.main_model_task.cancelled()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])