#!/usr/bin/env python3
"""
Test to validate the confidence filtering logic in SmallModel.
This test specifically validates the fix for issue #81 - inverted confidence logic.
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

# Add the project root to the Python path
sys.path.insert(0, '/home/runner/work/Team-project-Context-Translator-SS25/Team-project-Context-Translator-SS25')

from Backend.AI.SmallModel import SmallModel

def test_confidence_filter_logic():
    """Test that the confidence filtering logic works correctly."""
    print("=== Testing Confidence Filter Logic ===")
    
    # Initialize SmallModel
    small_model = SmallModel()
    
    # Test cases:
    # According to the new prompt: 0.99 = very technical, 0.01 = common
    # We should KEEP high-confidence (technical) terms and FILTER OUT low-confidence (common) terms
    
    test_cases = [
        # (confidence, term, expected_result, description)
        (0.95, "neural networks", True, "High confidence technical term - should PASS"),
        (0.85, "backpropagation", False, "Below threshold - should be FILTERED"),
        (0.05, "common word", False, "Low confidence common term - should be FILTERED"),
        (0.1, "simple term", False, "Low confidence common term - should be FILTERED"),
        (0.9, "exactly at threshold", True, "At threshold - should PASS after fix"),
    ]
    
    print(f"Using confidence threshold: {small_model.confidence_threshold}")
    print()
    
    failed_tests = []
    
    for confidence, term, expected_result, description in test_cases:
        actual_result = small_model.should_pass_filters(confidence, term)
        status = "✓" if actual_result == expected_result else "✗"
        
        print(f"{status} {description}")
        print(f"   Confidence: {confidence}, Expected: {expected_result}, Actual: {actual_result}")
        
        if actual_result != expected_result:
            failed_tests.append((confidence, term, expected_result, actual_result, description))
        print()
    
    if failed_tests:
        print("=== FAILED TESTS (demonstrating the bug) ===")
        for confidence, term, expected, actual, desc in failed_tests:
            print(f"FAIL: {desc}")
            print(f"      Confidence: {confidence}, Expected: {expected}, Got: {actual}")
        print(f"\nTotal failed: {len(failed_tests)}/{len(test_cases)}")
        return False
    else:
        print("All tests passed!")
        return True

if __name__ == "__main__":
    success = test_confidence_filter_logic()
    sys.exit(0 if success else 1)