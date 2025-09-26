#!/usr/bin/env python3
"""
Test to validate the enhanced filtering logic in SmallModel.
This test validates the improvements for filtering out irrelevant, small talk, 
and prompt contamination words.
"""

import sys
import os
import asyncio
import json
from unittest.mock import AsyncMock, patch

sys.path.append(os.path.dirname(__file__))
sys.path.insert(0, '/home/runner/work/Team-project-Context-Translator-SS25/Team-project-Context-Translator-SS25')

from Backend.AI.SmallModel import SmallModel
from Backend.models.UniversalMessage import UniversalMessage

def test_known_terms_filtering():
    """Test that known terms (small talk, common words) are properly filtered."""
    print("=== Testing Known Terms Filtering ===")
    
    small_model = SmallModel()
    
    # Test cases for known terms that should be filtered
    known_term_cases = [
        ("hello", "Small talk greeting"),
        ("okay", "Conversational filler"),
        ("system", "Generic tech term"),
        ("the", "Basic article"),
        ("extract", "Prompt contamination word"),
        ("confidence", "Prompt contamination word"),
        ("really", "Common adverb"),
        ("basically", "Conversational filler"),
    ]
    
    failed_tests = []
    for term, description in known_term_cases:
        # High confidence to test that known terms are still filtered
        result = small_model.should_pass_filters(0.9, term)
        status = "✓" if not result else "✗"
        
        print(f"{status} {description}: '{term}' -> {'FILTERED' if not result else 'PASSED'}")
        
        if result:  # Should be False (filtered)
            failed_tests.append((term, description))
    
    print()
    return len(failed_tests) == 0, failed_tests

async def test_fallback_filtering():
    """Test the enhanced fallback detection with prompt contamination filtering."""
    print("=== Testing Fallback Detection Filtering ===")
    
    small_model = SmallModel()
    
    test_cases = [
        # (sentence, should_detect_terms, description)
        ("extract technical terms from this sentence", False, "Prompt contamination"),
        ("confidence json array format", False, "Multiple prompt keywords"),
        ("The API uses authentication protocols", True, "Valid technical sentence"),
        ("hello hello hello hello", False, "Repetitive transcription error"),
        ("We implemented a new algorithm", True, "Valid technical content"),
        ("domain extraction technical terms", False, "Prompt contamination mix"),
    ]
    
    failed_tests = []
    for sentence, should_detect, description in test_cases:
        detected_terms = await small_model.detect_terms_fallback(sentence)
        has_terms = len(detected_terms) > 0
        status = "✓" if has_terms == should_detect else "✗"
        
        print(f"{status} {description}: '{sentence}'")
        print(f"   Expected terms: {should_detect}, Got terms: {has_terms}")
        if detected_terms:
            print(f"   Terms: {[term['term'] for term in detected_terms]}")
        print()
        
        if has_terms != should_detect:
            failed_tests.append((sentence, should_detect, has_terms, description))
    
    return len(failed_tests) == 0, failed_tests

async def test_process_message_filtering():
    """Test the enhanced process_message filtering for silence contamination."""
    print("=== Testing Process Message Filtering ===")
    
    small_model = SmallModel()
    
    # Mock the AI detection to return consistent results
    mock_terms = [{"term": "test", "confidence": 0.8, "context": "test", "timestamp": 123}]
    
    test_cases = [
        # (text, should_process, description)
        ("", False, "Empty text"),
        ("   ", False, "Whitespace only"),
        ("hi", False, "Too short"),
        ("extract technical terms please", False, "Prompt contamination"),
        ("same same same same same", False, "Repetitive pattern"),
        ("We use neural networks for processing", True, "Valid technical sentence"),
        ("Hello, how are you doing today?", True, "Valid conversational sentence"),
    ]
    
    failed_tests = []
    processed_count = 0
    
    with patch.object(small_model, 'detect_terms_with_ai', new=AsyncMock(return_value=mock_terms)):
        with patch.object(small_model, 'write_detection_to_queue', new=AsyncMock(return_value=True)):
            
            for text, should_process, description in test_cases:
                # Create a mock message
                message = UniversalMessage(
                    type="stt.transcription",
                    payload={"text": text, "user_role": "test", "domain": "test"},
                    origin="test",
                    client_id="test"
                )
                
                # Count calls to detect_terms_with_ai to see if processing occurred
                small_model.detect_terms_with_ai.reset_mock()
                
                await small_model.process_message(message)
                
                was_processed = small_model.detect_terms_with_ai.called
                status = "✓" if was_processed == should_process else "✗"
                
                print(f"{status} {description}: '{text}'")
                print(f"   Expected processing: {should_process}, Got processing: {was_processed}")
                print()
                
                if was_processed != should_process:
                    failed_tests.append((text, should_process, was_processed, description))
                    
                if was_processed:
                    processed_count += 1
    
    print(f"Total processed: {processed_count}")
    return len(failed_tests) == 0, failed_tests

async def main():
    """Run all enhanced filtering tests."""
    print("=== Enhanced Filtering Test Suite ===\n")
    
    all_passed = True
    all_failures = []
    
    # Test 1: Known terms filtering
    passed, failures = test_known_terms_filtering()
    if not passed:
        all_passed = False
        all_failures.extend(failures)
        print(f"Known terms test FAILED with {len(failures)} errors")
    else:
        print("Known terms test PASSED")
    print()
    
    # Test 2: Fallback detection filtering
    passed, failures = await test_fallback_filtering()
    if not passed:
        all_passed = False
        all_failures.extend(failures)
        print(f"Fallback filtering test FAILED with {len(failures)} errors")
    else:
        print("Fallback filtering test PASSED")
    print()
    
    # Test 3: Process message filtering
    passed, failures = await test_process_message_filtering()
    if not passed:
        all_passed = False
        all_failures.extend(failures)
        print(f"Process message filtering test FAILED with {len(failures)} errors")
    else:
        print("Process message filtering test PASSED")
    print()
    
    if all_passed:
        print("🎉 All enhanced filtering tests PASSED!")
        return True
    else:
        print(f"❌ Enhanced filtering tests FAILED with {len(all_failures)} total errors")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)