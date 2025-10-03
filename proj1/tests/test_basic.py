#!/usr/bin/env python3
"""
Basic functionality test for the Distributed Paxos Banking System.
"""

import time
import threading
import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from main import BankingSystem
from messages import Transaction


def test_basic_functionality():
    """Test basic system functionality"""
    print("Starting basic functionality test...")
    
    system = BankingSystem()
    
    try:
        # Initialize system
        system.initialize_system()
        
        # Wait for leader election
        print("Waiting for leader election...")
        time.sleep(5)
        
        # Check leader
        leader = system._get_current_leader()
        if leader:
            print(f"Leader elected: {leader.node_id}")
        else:
            print("No leader elected!")
            return False
        
        # Test single transaction
        print("\nTesting single transaction: A -> C, 5")
        transaction = Transaction("A", "C", 5)
        client_a = system.client_manager.get_client("A")
        if client_a:
            client_a.send_transaction(transaction)
            time.sleep(3)  # Wait for processing
        
        # Print system state
        system._print_system_state()
        
        # Test multiple transactions
        print("\nTesting multiple transactions...")
        transactions = [
            Transaction("C", "E", 4),
            Transaction("B", "D", 2),
            Transaction("E", "A", 10)
        ]
        
        for t in transactions:
            client = system.client_manager.get_client(t.sender)
            if client:
                client.send_transaction(t)
                time.sleep(1)
        
        time.sleep(5)  # Wait for processing
        system._print_system_state()
        
        # Test node failure
        print("\nTesting node failure...")
        if "n2" in system.nodes:
            system.nodes["n2"].simulate_failure()
            system.live_nodes.discard("n2")
            print("Node n2 failed")
            time.sleep(3)
        
        # Send another transaction
        print("Sending transaction after failure...")
        transaction = Transaction("A", "B", 3)
        client_a = system.client_manager.get_client("A")
        if client_a:
            client_a.send_transaction(transaction)
            time.sleep(3)
        
        system._print_system_state()
        
        print("\nBasic functionality test completed successfully!")
        return True
        
    except Exception as e:
        print(f"Test failed with error: {e}")
        return False
    finally:
        system.shutdown_system()


def test_print_functions():
    """Test the print functions"""
    print("\nTesting print functions...")
    
    system = BankingSystem()
    
    try:
        system.initialize_system()
        time.sleep(3)
        
        # Get a running node
        running_node = None
        for node in system.nodes.values():
            if node.running:
                running_node = node
                break
        
        if not running_node:
            print("No running nodes found!")
            return False
        
        print(f"\nTesting print functions on node {running_node.node_id}:")
        
        # Test PrintLog
        print("\n--- PrintLog ---")
        running_node.print_log()
        
        # Test PrintDB
        print("\n--- PrintDB ---")
        running_node.print_db()
        
        # Test PrintStatus
        print("\n--- PrintStatus ---")
        running_node.print_status(0)
        running_node.print_status(1)
        
        # Test PrintView
        print("\n--- PrintView ---")
        running_node.print_view()
        
        return True
        
    except Exception as e:
        print(f"Print functions test failed: {e}")
        return False
    finally:
        system.shutdown_system()


if __name__ == "__main__":
    print("="*60)
    print("DISTRIBUTED PAXOS BANKING SYSTEM - BASIC TESTS")
    print("="*60)
    
    # Run basic functionality test
    success1 = test_basic_functionality()
    
    time.sleep(2)
    
    # Run print functions test
    success2 = test_print_functions()
    
    print("\n" + "="*60)
    if success1 and success2:
        print("ALL TESTS PASSED!")
    else:
        print("SOME TESTS FAILED!")
    print("="*60)
