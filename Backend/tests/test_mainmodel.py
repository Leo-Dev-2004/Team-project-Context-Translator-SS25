#!/usr/bin/env python3
"""
Test script for MainModel integration
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

async def test_mainmodel():
    """Test MainModel queue processing"""
    
    print("=== Testing MainModel File Queue Processing ===")
    
    # Check input queue
    detections_file = Path("Backend/AI/detections_queue.json")
    if not detections_file.exists():
        print("ERROR: detections_queue.json not found")
        return
        
    with open(detections_file, 'r') as f:
        detections = json.load(f)
    
    print(f"Found {len(detections)} pending detections in queue")
    
    # Initialize MainModel
    main_model = MainModel()
    
    # Test processing queue
    try:
        print("Processing queue...")
        await main_model.process_detections_queue()
        
        # Check output queue
        explanations_file = Path("Backend/AI/explanations_queue.json")
        if explanations_file.exists():
            with open(explanations_file, 'r') as f:
                explanations = json.load(f)
            print(f"Generated {len(explanations)} explanations")
            
            # Show sample explanations
            for i, explanation in enumerate(explanations[:2], 1):
                term = explanation.get('term', 'N/A')
                exp_text = explanation.get('explanation', 'N/A')[:100] + "..." if len(explanation.get('explanation', '')) > 100 else explanation.get('explanation', 'N/A')
                print(f"  {i}. '{term}': {exp_text}")
        else:
            print("ERROR: explanations_queue.json not created")
            
        # Check if detections were updated
        with open(detections_file, 'r') as f:
            updated_detections = json.load(f)
        
        processed_count = sum(1 for d in updated_detections if d.get('status') == 'completed')
        print(f"Processed {processed_count}/{len(updated_detections)} detections")
        
    except Exception as e:
        print(f"ERROR testing MainModel: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_mainmodel())