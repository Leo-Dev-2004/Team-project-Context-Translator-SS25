#!/usr/bin/env python3

"""
Test script for Option B: Event-Driven Direct Integration
Tests that SmallModel triggers MainModel automatically after detecting terms.
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from Backend.AI.SmallModel import SmallModel
from Backend.models.UniversalMessage import UniversalMessage

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_real_time_integration():
    """Test that SmallModel automatically triggers MainModel after detection."""
    
    logger.info("=== Testing Option B: Event-Driven Direct Integration ===")
    
    # Clear existing queues for clean test
    detections_file = Path("Backend/AI/detections_queue.json")
    explanations_file = Path("Backend/AI/explanations_queue.json")
    
    logger.info("Clearing existing queues for clean test...")
    for file in [detections_file, explanations_file]:
        if file.exists():
            with open(file, 'w', encoding='utf-8') as f:
                json.dump([], f)
    
    # Initialize SmallModel
    small_model = SmallModel()
    
    # Create test message with technical terms
    test_message = UniversalMessage(
        type="stt.transcription",
        payload={
            "text": "We need to implement machine learning algorithms using neural networks and deep learning frameworks like TensorFlow",
            "user_role": "student"  # Lower role to detect more terms
        },
        origin="test_script",
        destination="small_model",
        client_id="integration_test",
    )
    
    logger.info(f"Processing test message: {test_message.payload['text']}")
    
    # Record start time
    start_time = time.time()
    
    # Process message (this should now trigger MainModel automatically)
    result = await small_model.process_message(test_message)
    
    end_time = time.time()
    processing_time = end_time - start_time
    
    if result:
        logger.info(f"SmallModel processing completed in {processing_time:.2f} seconds")
        logger.info(f"SmallModel result: {result.type}")
    
    # Check if detections were created
    if detections_file.exists():
        with open(detections_file, 'r', encoding='utf-8') as f:
            detections = json.load(f)
        logger.info(f"Found {len(detections)} detections in queue")
        for detection in detections[-3:]:  # Show last 3
            logger.info(f"  - Term: '{detection['term']}' (confidence: {detection['confidence']})")
    
    # Wait a moment for MainModel processing to complete
    logger.info("Waiting 3 seconds for MainModel processing...")
    await asyncio.sleep(3)
    
    # Check if explanations were generated automatically
    if explanations_file.exists():
        with open(explanations_file, 'r', encoding='utf-8') as f:
            explanations = json.load(f)
        logger.info(f"Found {len(explanations)} explanations generated")
        
        # Show recent explanations
        recent_explanations = [exp for exp in explanations if exp.get('client_id') == 'integration_test']
        logger.info(f"Found {len(recent_explanations)} explanations for our test")
        
        for exp in recent_explanations[-2:]:  # Show last 2
            logger.info(f"  - Explained: '{exp['term']}' - Status: {exp['status']}")
            logger.info(f"    Explanation: {exp['explanation'][:100]}...")
    
    # Test Results Analysis
    logger.info("\n=== INTEGRATION TEST RESULTS ===")
    
    if result:
        if result.type == "ai.terms_detected":
            logger.info("✅ SmallModel successfully detected terms")
            detected_terms = result.payload.get('detected_terms', [])
            logger.info(f"   Detected terms: {detected_terms}")
            
            if explanations_file.exists():
                with open(explanations_file, 'r', encoding='utf-8') as f:
                    explanations = json.load(f)
                test_explanations = [exp for exp in explanations if exp.get('client_id') == 'integration_test']
                
                if test_explanations:
                    logger.info("✅ MainModel automatically generated explanations")
                    logger.info(f"   Generated {len(test_explanations)} explanations")
                    logger.info("✅ OPTION B INTEGRATION SUCCESSFUL - Real-time pipeline working!")
                else:
                    logger.warning("⚠️  MainModel processing may be delayed or failed")
                    logger.info("   Check logs above for MainModel errors")
            else:
                logger.warning("⚠️  No explanations file found - MainModel may not have processed")
                
    elif result and result.type == "ai.no_terms_detected":
        logger.warning("⚠️  SmallModel found no terms - check detection logic")
        
    else:
        if result:
            logger.error(f"❌ SmallModel returned unexpected result: {result.type}")
    
    logger.info(f"\nTotal test time: {processing_time:.2f} seconds")
    logger.info("=== Test Complete ===")

if __name__ == "__main__":
    asyncio.run(test_real_time_integration())