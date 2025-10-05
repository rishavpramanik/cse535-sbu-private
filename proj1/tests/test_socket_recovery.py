#!/usr/bin/env python3
"""
Test script to verify socket recovery functionality
"""

import sys
import os
import time

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from node import Node

def test_socket_recovery():
    """Test that nodes can simulate failure and recover properly"""
    print("Testing socket recovery functionality...")
    
    # Create a single node for testing
    all_nodes = {"n1": ("localhost", 5001)}
    node = Node("n1", 5001, all_nodes)
    
    try:
        # Start the node
        print("1. Starting node...")
        node.start()
        time.sleep(1)
        
        # Simulate failure
        print("2. Simulating failure...")
        node.simulate_failure()
        time.sleep(1)
        
        # Try to recover
        print("3. Attempting recovery...")
        node.recover()
        time.sleep(1)
        
        print("✅ Socket recovery test PASSED!")
        return True
        
    except Exception as e:
        print(f"❌ Socket recovery test FAILED: {e}")
        return False
        
    finally:
        # Clean shutdown
        if node.running:
            node.stop()

if __name__ == "__main__":
    success = test_socket_recovery()
    exit(0 if success else 1)
