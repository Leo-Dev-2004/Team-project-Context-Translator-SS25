#!/usr/bin/env python3
"""
Test MainModel with single term processing
"""

import asyncio
import sys
import os
import json
from pathlib import Path

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from Backend.AI.MainModel import MainModel

async def test_single_term():
    """Test MainModel with just one term"""
    
    print("=== Testing MainModel Single Term Processing ===")
    
    # Create a simple test queue with just one term
    test_queue = [
        {
            "id": "test-001",
            "term": "neural networks",
            "context": "I am working with neural networks",
            "confidence": 0.8,
            "timestamp": 1757413476,
            "client_id": "test_client",
            "user_session_id": None,
            "original_message_id": "test-msg",
            "status": "pending",
            "explanation": None
        }
    ]
    
    # Write test queue
    queue_file = Path("Backend/AI/detections_queue.json")
    with open(queue_file, 'w') as f:
        json.dump(test_queue, f, indent=2)
    
    print("Created test queue with 1 term")
    
    # Initialize MainModel
    main_model = MainModel()
    
    # Test direct LLM query
    print("Testing direct LLM query...")
    
    messages = main_model.build_prompt("neural networks", "I am working with neural networks")
    result = await main_model.query_llm(messages)
    
    if result:
        print(f"SUCCESS: Direct LLM query worked")
        print(f"Result: {result[:100]}...")
        
        # Now test full processing
        print("\nTesting full queue processing...")
        await main_model.process_detections_queue()
        
        # Check results
        explanations_file = Path("Backend/AI/explanations_queue.json")
        if explanations_file.exists():
            with open(explanations_file, 'r') as f:
                explanations = json.load(f)
            print(f"Generated {len(explanations)} explanations")
        else:
            print("No explanations file created")
    else:
        print("FAILED: Direct LLM query failed")

if __name__ == "__main__":
    asyncio.run(test_single_term())