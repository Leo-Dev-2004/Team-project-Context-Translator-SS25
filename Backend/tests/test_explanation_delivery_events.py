#!/usr/bin/env python3
"""
Test script for ExplanationDeliveryService event-driven notifications
Tests that the service responds immediately to trigger_immediate_check() instead of polling
"""

import asyncio
import json
import logging
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from Backend.services.ExplanationDeliveryService import ExplanationDeliveryService

logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_event_driven_processing():
    """Test that ExplanationDeliveryService responds immediately to events rather than polling"""
    
    # Create a temporary directory for test files
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_file = Path(temp_dir) / "test_explanations_queue.json"
        
        # Create mock outgoing queue
        mock_queue = AsyncMock()
        
        # Initialize service
        service = ExplanationDeliveryService(outgoing_queue=mock_queue)
        # Override the file path for testing
        service.explanations_file = temp_file
        
        # Start the service
        await service.start()
        
        try:
            # Initially empty queue - service should wait
            initial_queue = []
            with open(temp_file, 'w') as f:
                json.dump(initial_queue, f)
            
            # Give service a moment to start monitoring
            await asyncio.sleep(0.1)
            
            # Add a ready explanation to the file
            test_explanation = {
                "id": "test_123",
                "term": "machine learning",
                "explanation": "A subset of AI that learns patterns from data",
                "status": "ready_for_delivery",
                "client_id": "test_client",
                "timestamp": time.time()
            }
            
            with open(temp_file, 'w') as f:
                json.dump([test_explanation], f)
            
            # Measure time before triggering
            start_time = time.time()
            
            # Trigger immediate check (this should process without waiting for polling timeout)
            service.trigger_immediate_check()
            
            # Wait a short time for processing
            await asyncio.sleep(0.5)
            
            processing_time = time.time() - start_time
            
            # Verify that the explanation was processed quickly (much less than the 5-second timeout)
            assert processing_time < 2.0, f"Processing took {processing_time:.2f}s, expected < 2.0s for event-driven processing"
            
            # Verify that the mock queue's enqueue method was called
            assert mock_queue.enqueue.called, "Outgoing queue should have received the explanation"
            
            # Check that the explanation was marked as delivered
            with open(temp_file, 'r') as f:
                updated_queue = json.load(f)
            
            assert len(updated_queue) == 1
            assert updated_queue[0]["status"] == "delivered"
            
            logger.info(f"Event-driven processing completed in {processing_time:.3f} seconds")
            
        finally:
            # Clean up
            await service.stop()

@pytest.mark.asyncio
async def test_trigger_immediate_check_method():
    """Test that trigger_immediate_check() method works correctly"""
    
    mock_queue = AsyncMock()
    service = ExplanationDeliveryService(outgoing_queue=mock_queue)
    
    # Service not started - should not crash
    service.trigger_immediate_check()
    
    # Start service
    await service.start()
    
    try:
        # Should set the event when service is running
        assert not service._new_explanation_event.is_set()
        service.trigger_immediate_check()
        assert service._new_explanation_event.is_set()
        
    finally:
        await service.stop()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])