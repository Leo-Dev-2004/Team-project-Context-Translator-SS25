#!/usr/bin/env python3
"""
Integration test for MainModel to ExplanationDeliveryService event triggering
Tests that MainModel can trigger immediate explanation delivery
"""

import asyncio
import json
import logging
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

# Add Backend to Python path for imports
import sys
sys.path.append(str(Path(__file__).parent.parent))

from Backend.AI.MainModel import MainModel
from Backend.services.ExplanationDeliveryService import ExplanationDeliveryService
from Backend.dependencies import set_explanation_delivery_service_instance, get_explanation_delivery_service_instance

logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_mainmodel_triggers_explanation_delivery():
    """Test that MainModel triggers ExplanationDeliveryService when writing explanations"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Set up temporary files
        temp_explanations_file = Path(temp_dir) / "explanations_queue.json"
        
        # Create mock outgoing queue for ExplanationDeliveryService
        mock_queue = AsyncMock()
        
        # Create and set up ExplanationDeliveryService
        delivery_service = ExplanationDeliveryService(outgoing_queue=mock_queue)
        delivery_service.explanations_file = temp_explanations_file
        
        # Set the global instance for MainModel to use
        set_explanation_delivery_service_instance(delivery_service)
        
        # Start the delivery service
        await delivery_service.start()
        
        # Initialize empty queue file
        with open(temp_explanations_file, 'w') as f:
            json.dump([], f)
        
        try:
            # Create MainModel instance
            with patch('Backend.AI.MainModel.httpx.AsyncClient') as mock_http_client:
                main_model = MainModel()
                # Override the explanations file path for testing
                main_model.explanations_queue_file = temp_explanations_file
                
                # Test explanation entry
                test_explanation = {
                    "id": "test_integration_123",
                    "term": "neural network",
                    "explanation": "A network of interconnected nodes that mimics the human brain",
                    "status": "ready_for_delivery",
                    "client_id": "test_client_integration",
                    "timestamp": time.time()
                }
                
                # Write explanation to queue (this should trigger the delivery service)
                start_time = time.time()
                result = await main_model.write_explanation_to_queue(test_explanation)
                
                # Wait a bit for the delivery service to process
                await asyncio.sleep(0.5)
                
                processing_time = time.time() - start_time
                
                # Verify that the explanation was written successfully
                assert result is True, "MainModel should successfully write explanation to queue"
                
                # Verify that the delivery service was triggered and processed quickly
                assert processing_time < 2.0, f"Processing took {processing_time:.2f}s, expected < 2.0s"
                
                # Verify that the mock queue received the explanation
                assert mock_queue.enqueue.called, "Delivery service should have enqueued the explanation"
                
                # Check that the explanation was marked as delivered
                with open(temp_explanations_file, 'r') as f:
                    final_queue = json.load(f)
                
                assert len(final_queue) == 1, "Should have one explanation in queue"
                assert final_queue[0]["status"] == "delivered", "Explanation should be marked as delivered"
                
                logger.info(f"Integration test completed successfully in {processing_time:.3f} seconds")
                
        finally:
            # Clean up
            await delivery_service.stop()
            # Clear global instance
            set_explanation_delivery_service_instance(None)

@pytest.mark.asyncio
async def test_dependency_injection_works():
    """Test that the dependency injection system works correctly"""
    
    # Initially no instance should be set
    assert get_explanation_delivery_service_instance() is None
    
    # Create a mock service
    mock_service = MagicMock()
    
    # Set it
    set_explanation_delivery_service_instance(mock_service)
    
    # Verify we can get it back
    retrieved_service = get_explanation_delivery_service_instance()
    assert retrieved_service is mock_service
    
    # Clear it
    set_explanation_delivery_service_instance(None)
    assert get_explanation_delivery_service_instance() is None

if __name__ == "__main__":
    pytest.main([__file__, "-v"])