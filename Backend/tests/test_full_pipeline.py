#!/usr/bin/env python3
"""
Test full pipeline: SmallModel detection → MainModel explanation
"""

import asyncio
import sys
import os
import json
from pathlib import Path
import time

sys.path.append(os.path.dirname(__file__))

from ..AI.SmallModel import SmallModel
from ..AI.MainModel import MainModel
from ..models.UniversalMessage import UniversalMessage

async def test_full_pipeline():
    """Test complete SmallModel → MainModel pipeline"""
    
    print("=== Testing Full Pipeline Integration ===")
    
    # Clear existing queue files
    detections_file = Path("Backend/AI/detections_queue.json")
    explanations_file = Path("Backend/AI/explanations_queue.json")
    
    if detections_file.exists():
        detections_file.unlink()
    if explanations_file.exists():
        explanations_file.unlink()
    
    print("Cleared existing queue files")
    
    # Step 1: Test SmallModel with new input
    test_message = UniversalMessage(
        type="stt.transcription",
        payload={
            "text": "We are implementing deep learning algorithms using TensorFlow and PyTorch frameworks for computer vision tasks",
            "user_role": "Student"
        },
        client_id="pipeline_test",
        origin="STT",
        destination="SmallModel",
    )
    
    print(f"Step 1: SmallModel processing...")
    print(f"Input: {test_message.payload['text']}")
    
    small_model = SmallModel()
    small_response = await small_model.process_message(test_message)
    
    if small_response:
        detected_terms = small_response.payload.get('detected_terms', [])
        print(f"SmallModel detected {len(detected_terms)} terms: {detected_terms}")
    else:
        print("SmallModel failed")
        return
    
    # Verify detections were written to queue
    if not detections_file.exists():
        print("ERROR: detections_queue.json not created")
        return
        
    with open(detections_file, 'r') as f:
        detections = json.load(f)
    
    print(f"Queue has {len(detections)} pending detections")
    
    # Step 2: Test MainModel processing
    print(f"\\nStep 2: MainModel processing...")
    
    main_model = MainModel()
    await main_model.process_detections_queue()
    
    # Check results
    if explanations_file.exists():
        with open(explanations_file, 'r') as f:
            explanations = json.load(f)
        
        print(f"MainModel generated {len(explanations)} explanations:")
        
        for i, explanation in enumerate(explanations, 1):
            term = explanation.get('term', 'N/A')
            exp_text = explanation.get('explanation', 'N/A')
            print(f"  {i}. '{term}': {exp_text[:80]}...")
    else:
        print("ERROR: No explanations generated")
        return
    
    # Step 3: Verify processing status
    with open(detections_file, 'r') as f:
        updated_detections = json.load(f)
    
    processed_count = sum(1 for d in updated_detections if d.get('status') == 'processed')
    total_count = len(updated_detections)
    
    print(f"\\nStep 3: Pipeline Results")
    print(f"Processed {processed_count}/{total_count} detections")
    
    if processed_count == total_count and len(explanations) > 0:
        print("SUCCESS: Full pipeline working end-to-end!")
        
        # Show complete flow
        print("\\n=== Complete Flow Verification ===")
        for detection in updated_detections:
            term = detection['term']
            status = detection['status']
            explanation = next((e for e in explanations if e['original_detection_id'] == detection['id']), None)
            exp_preview = explanation['explanation'][:50] + "..." if explanation else "No explanation"
            print(f"'{term}' → {status} → {exp_preview}")
        
    else:
        print(f"PARTIAL SUCCESS: {processed_count}/{total_count} processed, {len(explanations)} explanations")

if __name__ == "__main__":
    asyncio.run(test_full_pipeline())