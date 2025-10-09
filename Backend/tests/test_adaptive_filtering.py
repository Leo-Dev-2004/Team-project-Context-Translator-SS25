#!/usr/bin/env python3
"""
Test to validate the adaptive filtering logic that adjusts thresholds based on conversation type.
This addresses the feedback about providing domain-specific examples and letting through
some easier words in small talk conversations.
"""

import sys
import os
import asyncio
from unittest.mock import AsyncMock, patch

sys.path.append(os.path.dirname(__file__))
sys.path.insert(0, '/home/runner/work/Team-project-Context-Translator-SS25/Team-project-Context-Translator-SS25')

from Backend.AI.SmallModel import SmallModel

def test_domain_examples():
    """Test that domain-specific examples are generated correctly."""
    print("=== Testing Domain-Specific Examples ===")
    
    small_model = SmallModel()
    
    test_cases = [
        ("technology", ["API", "database", "machine learning", "cybersecurity"]),
        ("business", ["revenue stream", "stakeholder", "ROI", "market segmentation"]),
        ("finance", ["portfolio", "derivative", "liquidity", "cryptocurrency"]),
        ("medicine", ["diagnosis", "treatment", "pathology", "clinical trial"]),
        ("unknown_domain", ["Technology:", "Business:", "Science:"]),  # Should show general examples
        ("", ["Technology:", "Business:", "Science:"]),  # Empty domain should show general examples
    ]
    
    failed_tests = []
    for domain, expected_keywords in test_cases:
        examples = small_model._get_domain_examples(domain)
        
        # Check if at least some expected keywords are present
        found_keywords = [kw for kw in expected_keywords if kw.lower() in examples.lower()]
        success = len(found_keywords) >= len(expected_keywords) // 2  # At least half should be found
        
        status = "✓" if success else "✗"
        print(f"{status} Domain '{domain}': Found {len(found_keywords)}/{len(expected_keywords)} keywords")
        if not success:
            print(f"   Expected keywords: {expected_keywords}")
            print(f"   Found keywords: {found_keywords}")
            print(f"   Generated examples: {examples[:100]}...")
        print()
        
        if not success:
            failed_tests.append((domain, expected_keywords, found_keywords))
    
    return len(failed_tests) == 0, failed_tests

def test_adaptive_thresholds():
    """Test that confidence thresholds adapt based on conversation type."""
    print("=== Testing Adaptive Confidence Thresholds ===")
    
    small_model = SmallModel()
    
    test_cases = [
        # (sentence, expected_threshold_adjustment, description)
        ("We implemented a neural network algorithm", "higher", "Technical conversation - stricter threshold"),
        ("I enjoyed that photography workshop yesterday", "lower", "Casual conversation - more permissive threshold"),
        ("The API uses authentication protocols", "normal", "Some technical content - normal threshold"),
        ("Hello, how are you doing today?", "normal", "No specific indicators - normal threshold"),
        ("We discussed the database optimization methodology", "higher", "Multiple technical terms - stricter threshold"),
    ]
    
    base_threshold = small_model.confidence_threshold  # 0.6
    failed_tests = []
    
    for sentence, expected_adjustment, description in test_cases:
        actual_threshold = small_model._get_adaptive_threshold(sentence)
        
        if expected_adjustment == "higher":
            expected = actual_threshold > base_threshold
        elif expected_adjustment == "lower":  
            expected = actual_threshold < base_threshold
        else:  # "normal"
            expected = actual_threshold == base_threshold
            
        status = "✓" if expected else "✗"
        print(f"{status} {description}")
        print(f"   Sentence: '{sentence}'")
        print(f"   Base threshold: {base_threshold}, Adaptive: {actual_threshold}")
        print(f"   Expected: {expected_adjustment}, Got: {'higher' if actual_threshold > base_threshold else 'lower' if actual_threshold < base_threshold else 'normal'}")
        print()
        
        if not expected:
            failed_tests.append((sentence, expected_adjustment, actual_threshold, description))
    
    return len(failed_tests) == 0, failed_tests

def test_adaptive_filtering_in_practice():
    """Test how adaptive filtering works with real scenarios."""
    print("=== Testing Adaptive Filtering in Practice ===")
    
    small_model = SmallModel()
    
    test_cases = [
        # (confidence, term, context, should_pass, description)
        (0.55, "workshop", "I enjoyed that photography workshop yesterday", True, "Casual context - should allow moderate terms"),
        (0.55, "system", "We need to optimize the system", False, "Known term should still be filtered regardless of context"),
        (0.55, "algorithm", "We implemented a neural network algorithm", False, "Technical context - stricter threshold, should filter"),
        (0.75, "algorithm", "We implemented a neural network algorithm", True, "Technical context - high confidence should pass"),
        (0.55, "photography", "I enjoyed that photography workshop yesterday", True, "Casual context - moderate term should pass"),
        (0.45, "meeting", "We had an interesting team meeting", False, "Too low confidence even for casual context"),
    ]
    
    failed_tests = []
    for confidence, term, context, expected_pass, description in test_cases:
        actual_pass = small_model.should_pass_filters(confidence, term, context)
        status = "✓" if actual_pass == expected_pass else "✗"
        
        print(f"{status} {description}")
        print(f"   Term: '{term}' (confidence: {confidence})")
        print(f"   Context: '{context}'")
        print(f"   Expected: {'PASS' if expected_pass else 'FILTER'}, Got: {'PASS' if actual_pass else 'FILTER'}")
        
        # Show adaptive threshold for debugging
        adaptive_threshold = small_model._get_adaptive_threshold(context)
        print(f"   Adaptive threshold: {adaptive_threshold}")
        print()
        
        if actual_pass != expected_pass:
            failed_tests.append((confidence, term, context, expected_pass, actual_pass, description))
    
    return len(failed_tests) == 0, failed_tests

async def main():
    """Run all adaptive filtering tests."""
    print("=== Adaptive Filtering Test Suite ===\n")
    
    all_passed = True
    all_failures = []
    
    # Test 1: Domain examples
    passed, failures = test_domain_examples()
    if not passed:
        all_passed = False
        all_failures.extend(failures)
        print(f"Domain examples test FAILED with {len(failures)} errors")
    else:
        print("Domain examples test PASSED")
    print()
    
    # Test 2: Adaptive thresholds
    passed, failures = test_adaptive_thresholds()
    if not passed:
        all_passed = False
        all_failures.extend(failures)
        print(f"Adaptive thresholds test FAILED with {len(failures)} errors")
    else:
        print("Adaptive thresholds test PASSED")
    print()
    
    # Test 3: Adaptive filtering in practice
    passed, failures = test_adaptive_filtering_in_practice()
    if not passed:
        all_passed = False
        all_failures.extend(failures)
        print(f"Adaptive filtering practice test FAILED with {len(failures)} errors")
    else:
        print("Adaptive filtering practice test PASSED")
    print()
    
    if all_passed:
        print("🎉 All adaptive filtering tests PASSED!")
        return True
    else:
        print(f"❌ Adaptive filtering tests FAILED with {len(all_failures)} total errors")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)