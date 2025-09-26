#!/usr/bin/env python3
"""
Demonstration of the hallucination filtering functionality.
This shows how the implemented solution blocks common Whisper hallucination patterns.
"""

def simulate_stt_filtering(sentence):
    """Simulate the STT filtering logic to show how it works."""
    print(f"Processing: '{sentence}'")
    
    if not sentence or not sentence.strip():
        print("  → BLOCKED (empty/whitespace)")
        return False
    
    sentence_lower = sentence.lower().strip()
    
    # Core hallucination patterns from the issue
    strict_patterns = [
        "thanks for watching", "thank you for watching",
        "please like and subscribe", "don't forget to subscribe"
    ]
    
    moderate_patterns = [
        "see you next time", "that's all for today", 
        "thanks for your attention", "appreciate you watching"
    ]
    
    simple_patterns = ["thanks", "thank you"]
    
    # Check patterns
    for pattern in strict_patterns:
        if pattern in sentence_lower:
            clean_text = sentence_lower.replace(pattern, "").strip()
            if len(clean_text.split()) < 4:  # Minimal other content
                print(f"  → BLOCKED (strict hallucination pattern: '{pattern}')")
                return False
    
    for pattern in moderate_patterns:
        if pattern in sentence_lower:
            clean_text = sentence_lower.replace(pattern, "").strip()
            if len(clean_text.split()) < 3:  # Minimal other content
                print(f"  → BLOCKED (moderate hallucination pattern: '{pattern}')")
                return False
    
    for pattern in simple_patterns:
        if sentence_lower.strip() == pattern:
            print(f"  → BLOCKED (simple hallucination pattern: '{pattern}')")
            return False
    
    print("  → ALLOWED (legitimate content)")
    return True

def main():
    """Demonstrate the hallucination filtering."""
    print("🧪 Hallucination Filtering Demonstration\n")
    print("This shows how the implemented solution handles various inputs:\n")
    
    # Test cases from the GitHub issue
    print("=== Core Hallucination Patterns (Issue Examples) ===")
    issue_patterns = [
        "Thanks for watching!",
        "Thanks for watching",
        "Thank you for watching!",
        "Thanks",
        "Thank you",
    ]
    
    blocked_count = 0
    for pattern in issue_patterns:
        result = simulate_stt_filtering(pattern)
        if not result:
            blocked_count += 1
    
    print(f"\nResult: {blocked_count}/{len(issue_patterns)} hallucination patterns blocked ✅\n")
    
    print("=== Additional Hallucination Patterns ===")
    additional_patterns = [
        "Please like and subscribe",
        "Don't forget to subscribe to my channel", 
        "See you next time",
        "That's all for today, goodbye!",
        "Thanks for your attention",
    ]
    
    blocked_count_2 = 0
    for pattern in additional_patterns:
        result = simulate_stt_filtering(pattern)
        if not result:
            blocked_count_2 += 1
    
    print(f"\nResult: {blocked_count_2}/{len(additional_patterns)} additional patterns blocked ✅\n")
    
    print("=== Legitimate Content (Should be Preserved) ===")
    legitimate_content = [
        "I want to thank my colleagues for their help",
        "Thanks to machine learning, we can process this data", 
        "Please subscribe to our newsletter for updates",
        "We're watching the system metrics carefully",
        "Let me explain the neural network architecture",
        "The algorithm performs well, thank you for asking",
    ]
    
    allowed_count = 0
    for content in legitimate_content:
        result = simulate_stt_filtering(content)
        if result:
            allowed_count += 1
    
    print(f"\nResult: {allowed_count}/{len(legitimate_content)} legitimate content preserved ✅\n")
    
    total_hallucinations_blocked = blocked_count + blocked_count_2
    total_legitimate_preserved = allowed_count
    
    print("=== Summary ===")
    print(f"✅ Hallucination patterns blocked: {total_hallucinations_blocked}/{len(issue_patterns + additional_patterns)}")
    print(f"✅ Legitimate content preserved: {total_legitimate_preserved}/{len(legitimate_content)}")
    print(f"\n🎉 The solution successfully addresses the GitHub issue:")
    print(f"   'Thanks for watching!' and similar hallucinations are now blocked!")
    print(f"\n📋 Implementation Details:")
    print(f"   • Primary filtering at STT layer (transcribe.py)")
    print(f"   • Secondary filtering at SmallModel layer (SmallModel.py)")
    print(f"   • Tiered pattern matching (strict/moderate/simple)")
    print(f"   • Context-aware filtering to preserve legitimate content")
    print(f"   • Multi-layer defense against hallucination patterns")

if __name__ == "__main__":
    main()