#!/usr/bin/env python3
"""
Test suite for hallucination pattern filtering in both STT and SmallModel.
This test validates that common Whisper hallucination patterns like 
"Thanks for watching!" are properly filtered out.
"""

import sys
import os
import asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

# Add project paths
sys.path.append(os.path.dirname(__file__))
sys.path.insert(0, '/home/runner/work/Team-project-Context-Translator-SS25/Team-project-Context-Translator-SS25')

from Backend.AI.SmallModel import SmallModel
from Backend.models.UniversalMessage import UniversalMessage

def test_stt_hallucination_filtering():
    """Test the STT sentence filtering logic directly."""
    print("=== Testing STT Hallucination Filtering Logic ===")
    
    # Import and simulate the filtering logic from STT without requiring hardware
    def simulate_stt_filtering(sentence):
        """Simulate the STT _send_sentence filtering logic."""
        if not sentence or not sentence.strip():
            return False, "Empty or whitespace-only"

        # Filter out common Whisper hallucination patterns that occur during silence
        sentence_lower = sentence.lower().strip()
        
        # Define patterns with different strictness levels
        # Very strict patterns - block even with extra content
        strict_patterns = [
            "thanks for watching", "thank you for watching", 
            "please like and subscribe", "don't forget to subscribe",
            "hit that subscribe button", "smash that like button"
        ]
        
        # Moderate patterns - block if they dominate the sentence
        moderate_patterns = [
            "see you next time", "that's all for today", "until next time",
            "catch you later", "thanks for your attention", "thank you for your time",
            "appreciate you watching", "goodbye", "bye bye"
        ]
        
        # Simple patterns - only block if they're the entire sentence
        simple_patterns = ["thanks", "thank you"]
        
        # Check for multiple patterns (even if individually they wouldn't be blocked)
        pattern_count = 0
        found_patterns = []
        all_patterns = strict_patterns + moderate_patterns + simple_patterns
        for pattern in all_patterns:
            if pattern in sentence_lower:
                pattern_count += 1
                found_patterns.append(pattern)
        
        # If multiple patterns found, be more aggressive about blocking
        if pattern_count >= 2:
            # Calculate how much of the sentence is NOT pattern-related
            clean_text = sentence_lower
            for pattern in found_patterns:
                clean_text = clean_text.replace(pattern, "")
            clean_text = clean_text.strip()
            non_filler_words = [w for w in clean_text.split() if w not in ["for", "and", "the", "a", "to", "my", "your", "our", "everyone", "today", ","]]
            if len(non_filler_words) < 3:
                return False, f"Blocked multiple hallucination patterns: {found_patterns}"
        
        # Check strict patterns - block even with some extra content
        for pattern in strict_patterns:
            if pattern in sentence_lower:
                # Allow if it's clearly in a different context (has substantial other content)
                clean_text = sentence_lower.replace(pattern, "").strip()
                non_filler_words = [w for w in clean_text.split() if w not in ["for", "and", "the", "a", "to", "my", "your", "our"]]
                if len(non_filler_words) < 3:  # Less than 3 meaningful words left
                    return False, f"Blocked strict hallucination pattern: {pattern}"
        
        # Check moderate patterns - block if they dominate
        for pattern in moderate_patterns:
            if pattern in sentence_lower:
                clean_text = sentence_lower.replace(pattern, "").strip()
                non_filler_words = [w for w in clean_text.split() if w not in ["for", "and", "the", "a", "to", "my", "your", "our", "everyone", "today"]]
                if len(non_filler_words) < 2:  # Less than 2 meaningful words left
                    return False, f"Blocked moderate hallucination pattern: {pattern}"
        
        # Check simple patterns - only block if entire sentence
        for pattern in simple_patterns:
            if sentence_lower.strip() == pattern:
                return False, f"Blocked simple hallucination pattern: {pattern}"
        
        return True, "Allowed through"
    
    # Test cases for hallucination patterns
    hallucination_cases = [
        ("thanks for watching", "Exact match - should be blocked"),
        ("Thank you for watching!", "Case insensitive - should be blocked"),
        ("thanks for watching everyone", "With minimal extra content - should be blocked"),
        ("Thanks", "Simple thanks alone - should be blocked"),
        ("Please like and subscribe", "YouTube pattern - should be blocked"),
        ("Don't forget to subscribe to my channel", "Subscribe pattern with minimal extra - should be blocked"),
        ("That's all for today, goodbye!", "Multiple patterns with minimal extra - should be blocked"),
        ("See you next time", "Farewell pattern - should be blocked"),
        ("Thanks for your attention", "Attention thanks - should be blocked"),
    ]
    
    # Test cases that should NOT be filtered (legitimate content)
    legitimate_cases = [
        ("I would like to thank my colleagues for their help with the algorithm", "Legitimate thanks in technical context"),
        ("The algorithm is working well, thank you for asking about the performance", "Thanks in technical conversation"),
        ("We're watching the metrics carefully to optimize the system", "Watching in different context"),
        ("Please subscribe to our newsletter for technical updates and insights", "Business context subscribe"),
        ("Let me explain the neural network architecture in detail", "Pure technical content"),
        ("Thanks to machine learning advances, we can now process this data efficiently", "Thanks in technical context"),
    ]
    
    failed_tests = []
    
    # Test that hallucinations are blocked
    print("Testing hallucination patterns (should be blocked):")
    for sentence, description in hallucination_cases:
        allowed, reason = simulate_stt_filtering(sentence)
        status = "✓" if not allowed else "✗"
        print(f"{status} {description}: '{sentence}' -> {'BLOCKED' if not allowed else 'ALLOWED'} ({reason})")
        
        if allowed:
            failed_tests.append((sentence, description, "Should have been blocked"))
    
    print("\nTesting legitimate content (should be allowed):")
    # Test that legitimate content is not filtered
    for sentence, description in legitimate_cases:
        allowed, reason = simulate_stt_filtering(sentence)
        status = "✓" if allowed else "✗"
        print(f"{status} {description}: '{sentence}' -> {'ALLOWED' if allowed else 'BLOCKED'} ({reason})")
        
        if not allowed:
            failed_tests.append((sentence, description, "Should have been allowed"))
    
    return len(failed_tests) == 0, failed_tests

async def test_smallmodel_hallucination_filtering():
    """Test that SmallModel also filters out hallucination patterns."""
    print("\n=== Testing SmallModel Hallucination Filtering ===")
    
    small_model = SmallModel()
    
    # Test cases for hallucination patterns
    hallucination_cases = [
        ("Thanks for watching!", "Direct YouTube ending"),
        ("Thank you for watching everyone", "YouTube ending with audience"),
        ("Thanks for your attention today", "Presentation ending"),
        ("See you next time, goodbye", "Video farewell"),
        ("Don't forget to subscribe", "Subscribe prompt"),
        ("Please like and subscribe to my channel", "Full YouTube CTA"),
        ("That's all for today, catch you later", "Casual ending"),
        ("Thanks", "Simple thanks"),
    ]
    
    # Test cases that should be processed
    legitimate_cases = [
        ("I want to thank the team for implementing the algorithm", "Legitimate thanks with technical content"),
        ("The neural network is watching for patterns", "Technical use of 'watching'"),
        ("Thanks to machine learning, we can process this data", "Thanks in technical context"),
        ("Please subscribe to our API updates for notifications", "Business subscribe context"),
    ]
    
    failed_tests = []
    
    print("Testing hallucination patterns (should be blocked):")
    for text, description in hallucination_cases:
        message = UniversalMessage(
            type="stt.transcription",
            payload={"text": text},
            client_id="test_client",
            origin="STT"
        )
        
        # Mock the AI detection to avoid external dependencies
        with patch.object(small_model, 'detect_terms_with_ai', new=AsyncMock(return_value=[])):
            # Capture log output to see if message was blocked
            with patch('Backend.AI.SmallModel.logger') as mock_logger:
                await small_model.process_message(message)
                
                # Check if warning about blocking was logged
                blocked = any(
                    call.args[0].startswith("SmallModel: Blocked Whisper hallucination") 
                    for call in mock_logger.warning.call_args_list
                )
                
                status = "✓" if blocked else "✗"
                print(f"{status} {description}: '{text}' -> {'BLOCKED' if blocked else 'PROCESSED'}")
                
                if not blocked:
                    failed_tests.append((text, description, "Should have been blocked"))
    
    print("\nTesting legitimate content (should be processed):")
    for text, description in legitimate_cases:
        message = UniversalMessage(
            type="stt.transcription",
            payload={"text": text},
            client_id="test_client",
            origin="STT"
        )
        
        # Mock AI detection to return some terms for legitimate content
        mock_terms = [{"term": "algorithm", "confidence": 0.8, "context": text, "timestamp": 123456789}]
        with patch.object(small_model, 'detect_terms_with_ai', new=AsyncMock(return_value=mock_terms)):
            with patch.object(small_model, 'send_immediate_detection_notification', new=AsyncMock()):
                with patch.object(small_model, 'write_detection_to_queue', new=AsyncMock()) as mock_write:
                    with patch('Backend.AI.SmallModel.logger') as mock_logger:
                        await small_model.process_message(message)
                        
                        # Check if the message was processed (queue write was called)
                        processed = mock_write.called
                        
                        # Also check it wasn't blocked by hallucination filter
                        blocked = any(
                            call.args[0].startswith("SmallModel: Blocked Whisper hallucination") 
                            for call in mock_logger.warning.call_args_list
                        )
                        
                        status = "✓" if processed and not blocked else "✗"
                        print(f"{status} {description}: '{text}' -> {'PROCESSED' if processed and not blocked else 'BLOCKED'}")
                        
                        if not processed or blocked:
                            failed_tests.append((text, description, "Should have been processed"))
    
    return len(failed_tests) == 0, failed_tests

async def test_edge_cases():
    """Test edge cases for hallucination filtering."""
    print("\n=== Testing Edge Cases ===")
    
    small_model = SmallModel()
    edge_cases = [
        ("", "Empty string"),
        ("   ", "Whitespace only"),
        ("Thanks for watching. Now let's discuss the API implementation.", "Mixed content - hallucination + technical"),
        ("The presentation ends with thanks for watching", "Hallucination mentioned in technical context"),
        ("I appreciate your time and attention to this matter", "Legitimate appreciation"),
    ]
    
    failed_tests = []
    
    for text, description in edge_cases:
        message = UniversalMessage(
            type="stt.transcription",
            payload={"text": text},
            client_id="test_client",
            origin="STT"
        )
        
        try:
            # Mock dependencies to focus on the filtering logic
            with patch.object(small_model, 'detect_terms_with_ai', new=AsyncMock(return_value=[])):
                with patch.object(small_model, 'send_immediate_detection_notification', new=AsyncMock()):
                    with patch.object(small_model, 'write_detection_to_queue', new=AsyncMock()):
                        await small_model.process_message(message)
            
            print(f"✓ {description}: '{text}' -> Handled without error")
        except Exception as e:
            print(f"✗ {description}: '{text}' -> Error: {e}")
            failed_tests.append((text, description, f"Error: {e}"))
    
    return len(failed_tests) == 0, failed_tests

async def main():
    """Run all hallucination filtering tests."""
    print("🧪 Running Hallucination Filtering Test Suite\n")
    
    # Run STT tests
    stt_success, stt_failures = test_stt_hallucination_filtering()
    
    # Run SmallModel tests
    sm_success, sm_failures = await test_smallmodel_hallucination_filtering()
    
    # Run edge case tests
    edge_success, edge_failures = await test_edge_cases()
    
    # Summary
    print(f"\n=== Test Results ===")
    print(f"STT Filtering: {'✓ PASSED' if stt_success else '✗ FAILED'}")
    print(f"SmallModel Filtering: {'✓ PASSED' if sm_success else '✗ FAILED'}")
    print(f"Edge Cases: {'✓ PASSED' if edge_success else '✗ FAILED'}")
    
    if not stt_success:
        print(f"\nSTT Failures ({len(stt_failures)}):")
        for failure in stt_failures:
            print(f"  - {failure}")
    
    if not sm_success:
        print(f"\nSmallModel Failures ({len(sm_failures)}):")
        for failure in sm_failures:
            print(f"  - {failure}")
    
    if not edge_success:
        print(f"\nEdge Case Failures ({len(edge_failures)}):")
        for failure in edge_failures:
            print(f"  - {failure}")
    
    overall_success = stt_success and sm_success and edge_success
    
    if overall_success:
        print("\n🎉 All hallucination filtering tests PASSED!")
    else:
        print("\n❌ Some hallucination filtering tests FAILED!")
    
    return overall_success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)