#!/usr/bin/env python3
"""
Test script for SmallModel integration
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(__file__))

from Backend.AI.SmallModel import SmallModel
from Backend.models.UniversalMessage import UniversalMessage

async def test_smallmodel():
    """Test SmallModel with sample input"""
    
    print("=== Testing SmallModel Integration ===")
    
    # Create test message
    test_message = UniversalMessage(
        type="stt.transcription",
        payload={
            "text": "I am a machine learning engineer working on neural networks and backpropagation algorithms",
            "user_role": "Engineer"
        },
        client_id="test_client",
        origin="STT"
    )
    
    print(f"Input: {test_message.payload.get('text', 'N/A')}")
    
    # Initialize SmallModel
    small_model = SmallModel()
    
    # Test processing
    try:
        response = await small_model.process_message(test_message)
        print(f"Response: {response.payload if response else 'No response'}")
        
        # Check if detections were written to queue
        import json
        from pathlib import Path
        
        queue_file = Path("Backend/AI/detections_queue.json")
        if queue_file.exists():
            with open(queue_file, 'r') as f:
                queue_data = json.load(f)
                print(f"Queue entries: {len(queue_data)}")
                for entry in queue_data[-3:]:  # Show last 3 entries
                    print(f"  - {entry.get('term', 'N/A')} (confidence: {entry.get('confidence', 'N/A')})")
        else:
            print("detections_queue.json not created")
            
    except Exception as e:
        print(f"Error testing SmallModel: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_smallmodel())