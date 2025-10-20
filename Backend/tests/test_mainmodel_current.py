#!/usr/bin/env python3
"""
Test MainModel with current queue data
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

async def test_current_queue():
    """Process current queue data"""
    
    print("=== Testing MainModel with Current Queue ===")
    
    # Check current queue
    detections_file = Path("Backend/AI/detections_queue.json")
    if detections_file.exists():
        with open(detections_file, 'r') as f:
            detections = json.load(f)
        
        pending_count = sum(1 for d in detections if d.get('status') == 'pending')
        print(f"Found {len(detections)} total detections, {pending_count} pending")
        
        if pending_count > 0:
            print("Processing queue...")
            main_model = MainModel()
            await main_model.process_detections_queue()
            
            # Check results
            explanations_file = Path("Backend/AI/explanations_queue.json")
            if explanations_file.exists():
                with open(explanations_file, 'r') as f:
                    explanations = json.load(f)
                print(f"Generated {len(explanations)} explanations")
                
                for explanation in explanations:
                    term = explanation.get('term', 'N/A')
                    print(f"- {term}: Generated")
            else:
                print("No explanations file created")
                
            # Check updated status
            with open(detections_file, 'r') as f:
                updated_detections = json.load(f)
            
            processed_count = sum(1 for d in updated_detections if d.get('status') == 'processed')
            print(f"Status: {processed_count}/{len(updated_detections)} processed")
        else:
            print("No pending detections to process")
    else:
        print("No detections queue file found")

if __name__ == "__main__":
    asyncio.run(test_current_queue())