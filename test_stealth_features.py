#!/usr/bin/env python3
"""
Test script to verify all stealth features are working correctly
"""

import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from ai.sandbox import execute_code_safely, can_execute_safely
from ai.engine import AIEngine

def test_sandbox():
    """Test sandbox execution functionality"""
    print("=== Testing Sandbox Features ===")
    
    # Test safe code
    safe_code = """
print("Hello from sandbox!")
for i in range(3):
    print(f"Count: {i}")
"""
    
    print("Testing safe code execution...")
    result = execute_code_safely(safe_code)
    print(f"Safe code result: {result}")
    
    # Test dangerous code detection
    dangerous_code = """
import os
os.system("echo 'This should be blocked'")
"""
    
    print(f"Can execute dangerous code: {can_execute_safely(dangerous_code)}")
    
    # Test mathematical operations
    math_code = """
import math
result = math.sqrt(16)
print(f"Square root of 16 is: {result}")
"""
    
    print("Testing mathematical operations...")
    result = execute_code_safely(math_code)
    print(f"Math code result: {result}")

def test_cache():
    """Test caching functionality"""
    print("\n=== Testing Cache Features ===")
    
    engine = AIEngine()
    
    # Test cache key generation
    screen_text = "test screen content"
    audio_text = "test audio content"
    
    cache_key = engine._get_cache_key(screen_text, audio_text)
    print(f"Generated cache key: {cache_key[:16]}...")
    
    # Test cache storage and retrieval
    test_response = "This is a test response"
    engine.cache[cache_key] = {
        'response': test_response,
        'timestamp': time.time()
    }
    
    # Test cache validity
    is_valid = engine._is_cache_valid(engine.cache[cache_key]['timestamp'])
    print(f"Cache entry is valid: {is_valid}")
    
    # Test cache cleanup
    engine._cleanup_cache()
    print(f"Cache size after cleanup: {len(engine.cache)}")

def test_local_execution_integration():
    """Test local execution integration in AI engine"""
    print("\n=== Testing Local Execution Integration ===")
    
    engine = AIEngine()
    
    # Test code extraction from response
    response_with_code = """
Here's a simple calculation:
```python
print("2 + 2 =", 2 + 2)
```
"""
    
    result = engine._try_local_execution(response_with_code)
    print(f"Local execution result: {result}")

if __name__ == "__main__":
    try:
        test_sandbox()
        test_cache()
        test_local_execution_integration()
        print("\n=== All tests completed! ===")
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()