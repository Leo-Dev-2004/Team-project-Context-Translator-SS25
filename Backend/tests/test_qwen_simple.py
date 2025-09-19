#!/usr/bin/env python3
"""
Simple test of qwen3 API call using original working format
"""

import requests
import time

def test_qwen3_simple():
    """Test qwen3 with the exact same format as original working MainModel"""
    
    print("=== Testing qwen3 API Call (Original Format) ===")
    
    # Use exact same format as original working MainModel
    messages = [
        {
            "role": "system", 
            "content": "You are a helpful assistant explaining terms in simple, clear language."
        },
        {
            "role": "user",
            "content": 'Please directly explain the term "neural networks" in the following sentence:\n"I am a machine learning engineer working on neural networks and backpropagation algorithms"\n\nYour answer must be a short, clear definition only. Do not include any reasoning, steps, or thoughts. Just the explanation in 1-2 sentences. /no_think.'
        }
    ]
    
    print("Sending request to qwen3...")
    start_time = time.time()
    
    try:
        response = requests.post(
            "http://localhost:11434/api/chat",
            json={"model": "qwen3", "messages": messages, "stream": False},
            timeout=45  # Increase timeout to 45 seconds
        )
        
        elapsed = time.time() - start_time
        print(f"Response received in {elapsed:.2f} seconds")
        
        response.raise_for_status()
        result = response.json()["message"]["content"].strip()
        
        print(f"SUCCESS: {result[:100]}...")
        return True
        
    except requests.exceptions.Timeout:
        elapsed = time.time() - start_time
        print(f"TIMEOUT after {elapsed:.2f} seconds")
        return False
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"ERROR after {elapsed:.2f} seconds: {e}")
        return False

if __name__ == "__main__":
    success = test_qwen3_simple()
    
    if not success:
        print("\n=== RECOMMENDATION ===")
        print("qwen3 model appears to be too slow/unresponsive.")
        print("Options:")
        print("1. Use llama3.2 instead (faster, smaller model)")
        print("2. Increase timeout in MainModel")
        print("3. Check if qwen3 needs to be redownloaded")
        print("4. Use original simple MainModel approach")