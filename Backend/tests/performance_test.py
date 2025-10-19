#!/usr/bin/env python3
"""
Manual performance test to demonstrate the improvement in explanation delivery time
This shows the difference between event-driven vs. polling-based delivery
"""

import asyncio
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock
import sys

sys.path.append(str(Path(__file__).parent.parent))

from Backend.services.ExplanationDeliveryService import ExplanationDeliveryService

async def test_performance_improvement():
    """Demonstrate the performance improvement with event-driven notifications"""
    
    print("=== ExplanationDeliveryService Performance Test ===")
    
    # Create temporary test file
    temp_file = Path("/tmp/test_explanations_performance.json")
    
    # Initialize with empty queue
    with open(temp_file, 'w') as f:
        json.dump([], f)
    
    # Create service with mock queue
    mock_queue = AsyncMock()
    service = ExplanationDeliveryService(outgoing_queue=mock_queue)
    service.explanations_file = temp_file
    
    print("Starting ExplanationDeliveryService...")
    await service.start()
    
    try:
        # Test 1: Time how quickly a new explanation is processed after trigger
        print("\n--- Test 1: Event-driven processing ---")
        
        test_explanation = {
            "id": "perf_test_001",
            "term": "artificial intelligence",
            "explanation": "The simulation of human intelligence by machines",
            "status": "ready_for_delivery",
            "client_id": "perf_test_client",
            "timestamp": time.time()
        }
        
        # Add explanation to file
        with open(temp_file, 'w') as f:
            json.dump([test_explanation], f)
        
        # Measure time for event-driven processing
        start_time = time.time()
        service.trigger_immediate_check()
        
        # Wait for processing
        await asyncio.sleep(0.1)  # Small delay to allow processing
        
        # Check if processed (status changed to delivered)
        with open(temp_file, 'r') as f:
            result = json.load(f)
        
        if result and result[0].get("status") == "delivered":
            processing_time = time.time() - start_time
            print(f"✅ Event-driven delivery completed in {processing_time:.3f} seconds")
        else:
            print("❌ Event-driven delivery failed or incomplete")
        
        # Test 2: Demonstrate fallback timeout behavior
        print("\n--- Test 2: Fallback timeout behavior ---")
        
        # Add another explanation
        test_explanation2 = {
            "id": "perf_test_002", 
            "term": "machine learning",
            "explanation": "A subset of AI that learns from data",
            "status": "ready_for_delivery",
            "client_id": "perf_test_client",
            "timestamp": time.time()
        }
        
        with open(temp_file, 'w') as f:
            json.dump([test_explanation2], f)
        
        # Don't trigger - wait for timeout-based processing
        print("Waiting for timeout-based processing (up to 5 seconds)...")
        start_time = time.time()
        
        # Wait for timeout processing
        await asyncio.sleep(6)
        
        with open(temp_file, 'r') as f:
            result = json.load(f)
        
        if result and result[0].get("status") == "delivered":
            processing_time = time.time() - start_time
            print(f"✅ Timeout-based delivery completed in {processing_time:.3f} seconds")
        else:
            print("❌ Timeout-based delivery failed or incomplete")
        
        print(f"\nTotal mock queue calls: {mock_queue.enqueue.call_count}")
        
    finally:
        await service.stop()
        # Cleanup
        if temp_file.exists():
            temp_file.unlink()
    
    print("\n=== Performance Test Complete ===")

if __name__ == "__main__":
    asyncio.run(test_performance_improvement())