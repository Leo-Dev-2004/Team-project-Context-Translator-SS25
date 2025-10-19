#!/usr/bin/env python3
"""
Test script for immediate feedback improvements
"""

import asyncio
import sys
import os
import time

# Add the project root to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from Backend.AI.SmallModel import SmallModel
from Backend.models.UniversalMessage import UniversalMessage
from Backend.core.Queues import queues

async def test_immediate_feedback():
    """Test the immediate feedback functionality"""
    
    print("=== Testing Immediate Feedback Improvements ===")
    
    # Create test message with technical content
    test_message = UniversalMessage(
        type="stt.transcription",
        payload={
            "text": "We need to implement machine learning algorithms with neural networks and backpropagation for our API endpoints",
            "user_role": "Developer"
        },
        client_id="test_client_immediate",
        origin="STT",
        destination="SmallModel",
    )
    
    print(f"Input: {test_message.payload.get('text', 'N/A')}")
    print("Testing immediate feedback flow...")
    
    # Initialize SmallModel
    small_model = SmallModel()
    
    # Monitor outgoing queue for immediate notifications
    initial_queue_size = queues.outgoing.qsize()
    
    # Test processing with timing
    start_time = time.time()
    try:
        # Process the message (should trigger immediate feedback)
        await small_model.process_message(test_message)
        
        # Check if immediate notification was sent
        await asyncio.sleep(0.1)  # Small delay for processing
        final_queue_size = queues.outgoing.qsize()
        
        processing_time = time.time() - start_time
        print(f"Processing completed in: {processing_time:.2f} seconds")
        
        if final_queue_size > initial_queue_size:
            print("✅ Immediate feedback notification sent to frontend!")
            
            # Try to get the message from the queue
            try:
                immediate_msg = await queues.outgoing.dequeue()
                if immediate_msg and immediate_msg.type == "detection.immediate":
                    print(f"✅ Immediate detection message type: {immediate_msg.type}")
                    detected_terms = immediate_msg.payload.get("detected_terms", [])
                    print(f"✅ Detected {len(detected_terms)} terms immediately:")
                    for term_data in detected_terms:
                        print(f"  - {term_data.get('term')} (confidence: {term_data.get('confidence')})")
                else:
                    print("⚠️  Message in queue but not immediate detection type")
            except Exception as e:
                print(f"⚠️  Could not retrieve message from queue: {e}")
                
        else:
            print("❌ No immediate feedback notification was sent")
        
        # Test fallback detection performance
        print("\n=== Testing Fallback Detection Performance ===")
        fallback_start = time.time()
        fallback_terms = await small_model.detect_terms_fallback(test_message.payload.get('text', ''))
        fallback_time = time.time() - fallback_start
        
        print(f"Fallback detection completed in: {fallback_time:.3f} seconds")
        print(f"Fallback detected {len(fallback_terms)} terms:")
        for term in fallback_terms:
            print(f"  - {term.get('term')} (confidence: {term.get('confidence')})")
            
    except Exception as e:
        print(f"Error testing immediate feedback: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_immediate_feedback())