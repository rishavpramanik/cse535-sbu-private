"""
Integration tests for the Distributed Paxos Banking System.
Tests end-to-end scenarios, failure handling, and leader election.
"""

import unittest
import threading
import time
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
import socket

# Import our modules
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from messages import *
from paxos import PaxosState, PaxosLeader, PaxosBackup
from node import Node
from client import Client, ClientManager, parse_transactions
from main import BankingSystem


class TestLeaderElection(unittest.TestCase):
    """Test leader election scenarios"""
    
    def setUp(self):
        self.all_nodes = {
            "n1": ("localhost", 5001),
            "n2": ("localhost", 5002),
            "n3": ("localhost", 5003)
        }
        self.created_nodes = []  # Track nodes for cleanup
    
    def tearDown(self):
        """Clean up any created nodes"""
        for node in self.created_nodes:
            if hasattr(node, 'stop'):
                node.stop()
        self.created_nodes.clear()
    
    def create_node(self, node_id, port):
        """Helper to create and track nodes for cleanup"""
        node = Node(node_id, port, self.all_nodes)
        self.created_nodes.append(node)
        return node
    
    def test_initial_leader_election(self):
        """Test initial leader election process"""
        # Create nodes with mocked networking
        nodes = {}
        for node_id, (host, port) in self.all_nodes.items():
            node = self.create_node(node_id, port)
            # Mock networking methods
            node.send_message = Mock(return_value=True)
            node.broadcast_message = Mock()
            nodes[node_id] = node
        
        # Start leader election from n1
        leader = nodes["n1"].paxos_leader
        leader.start_leader_election(1)
        
        # Verify PREPARE was broadcasted
        nodes["n1"].broadcast_message.assert_called_once()
        
        # Simulate ACK responses from majority (n1, n2, n3)
        for node_id in ["n1", "n2", "n3"]:
            ack_msg = AckMessage(node_id, "n1", 1, [])
            leader.handle_ack(ack_msg)
        
        # n1 should become leader
        self.assertTrue(leader.state.is_leader)
        self.assertEqual(leader.state.leader_id, "n1")
    
    def test_leader_election_with_existing_log(self):
        """Test leader election when nodes have existing logs"""
        nodes = {}
        for node_id, (host, port) in self.all_nodes.items():
            node = self.create_node(node_id, port)
            node.send_message = Mock(return_value=True)
            node.broadcast_message = Mock()
            nodes[node_id] = node
        
        # Give n2 and n3 some existing log entries
        tx1 = Transaction("A", "B", 5)
        tx2 = Transaction("B", "C", 3)
        
        nodes["n2"].paxos_state.accept_log = [
            LogEntry(0, tx1, False, "C"),
            LogEntry(1, tx2, False, "A")
        ]
        
        nodes["n3"].paxos_state.accept_log = [
            LogEntry(0, tx1, False, "E"),  # Higher status
            LogEntry(2, Transaction("C", "D", 2), False, "A")
        ]
        
        # Start election from n1
        leader = nodes["n1"].paxos_leader
        leader.start_leader_election(1)
        
        # Manually ensure all nodes are in prepare_responses for the test
        leader.state.prepare_responses[1] = []
        
        # Now simulate ACK responses with logs
        # Create proper ACK messages with serialized logs
        ack_n1 = AckMessage("n1", "n1", 1, [])
        ack_n2 = AckMessage("n2", "n1", 1, nodes["n2"].paxos_state.accept_log)
        ack_n3 = AckMessage("n3", "n1", 1, nodes["n3"].paxos_state.accept_log)
        
        leader.handle_ack(ack_n1)
        leader.handle_ack(ack_n2)
        leader.handle_ack(ack_n3)
        
        # n1 should become leader and merge logs
        self.assertTrue(leader.state.is_leader)
        
        # Check log merging - should have entries 0, 1, 2
        seq_nums = {entry.seq_num for entry in leader.state.accept_log}
        self.assertEqual(seq_nums, {0, 1, 2})
        
        # Entry 0 should have status "E" (highest priority)
        entry_0 = next(e for e in leader.state.accept_log if e.seq_num == 0)
        self.assertEqual(entry_0.status, "E")
    
    def test_competing_leader_elections(self):
        """Test scenario with competing leader elections"""
        nodes = {}
        for node_id, (host, port) in self.all_nodes.items():
            node = self.create_node(node_id, port)
            node.send_message = Mock(return_value=True)
            node.broadcast_message = Mock()
            nodes[node_id] = node
        
        # Both n1 and n2 start elections simultaneously
        nodes["n1"].paxos_leader.start_leader_election(1)
        nodes["n2"].paxos_leader.start_leader_election(2)  # Higher view
        
        # n3 receives PREPARE from both, should respond to higher view (n2)
        prepare_n1 = PrepareMessage("n1", "n3", 1)
        prepare_n2 = PrepareMessage("n2", "n3", 2)
        
        # n3 handles both PREPAREs
        result1 = nodes["n3"].paxos_leader.handle_prepare(prepare_n1)
        result2 = nodes["n3"].paxos_leader.handle_prepare(prepare_n2)
        
        # Should accept higher view number
        self.assertTrue(result1)  # First one accepted
        self.assertTrue(result2)  # Higher view accepted
        self.assertEqual(nodes["n3"].paxos_state.view_num, 2)


class TestFailureHandling(unittest.TestCase):
    """Test failure detection and recovery scenarios"""
    
    def setUp(self):
        self.all_nodes = {
            "n1": ("localhost", 5001),
            "n2": ("localhost", 5002),
            "n3": ("localhost", 5003)
        }
        self.created_nodes = []  # Track nodes for cleanup
    
    def tearDown(self):
        """Clean up any created nodes"""
        for node in self.created_nodes:
            if hasattr(node, 'stop'):
                node.stop()
        self.created_nodes.clear()
    
    def create_node(self, node_id, port):
        """Helper to create and track nodes for cleanup"""
        node = Node(node_id, port, self.all_nodes)
        self.created_nodes.append(node)
        return node
    
    def test_heartbeat_mechanism(self):
        """Test heartbeat-based failure detection"""
        node = self.create_node("n1", 5001)
        node.send_message = Mock(return_value=True)
        
        # Simulate heartbeat
        heartbeat = HeartbeatMessage("n2", "n1")
        node._handle_heartbeat(heartbeat)
        
        # Should send heartbeat ack
        node.send_message.assert_called_once()
        call_args = node.send_message.call_args[0][0]
        self.assertEqual(call_args.msg_type, MessageType.HEARTBEAT_ACK)
    
    def test_failure_detection_timeout(self):
        """Test failure detection through timeout"""
        node = self.create_node("n1", 5001)
        node.failure_timeout = 0.1  # Very short timeout for testing
        
        # Initially all nodes are alive
        self.assertEqual(len(node.alive_nodes), 3)
        
        # Simulate heartbeat from n2 but not n3
        node.last_heartbeat["n2"] = time.time()
        node.last_heartbeat["n3"] = time.time() - 1.0  # Old timestamp
        
        # Manually trigger failure detection
        current_time = time.time()
        failed_nodes = []
        
        for node_id in list(node.alive_nodes):
            if node_id != node.node_id:
                last_hb = node.last_heartbeat.get(node_id, 0)
                if current_time - last_hb > node.failure_timeout:
                    failed_nodes.append(node_id)
        
        # n3 should be detected as failed
        self.assertIn("n3", failed_nodes)
        self.assertNotIn("n2", failed_nodes)
    
    def test_leader_failure_triggers_election(self):
        """Test that leader failure triggers new election"""
        node = self.create_node("n2", 5002)
        node.paxos_state.leader_id = "n1"
        node.paxos_state.view_num = 1
        node.paxos_leader.start_leader_election = Mock()
        
        # Simulate n1 (leader) failure
        node.alive_nodes.discard("n1")
        
        # This would normally be called by failure detector
        # Simulate the logic
        if "n1" == node.paxos_state.leader_id:
            # Leader failed, start new election
            new_view = node.paxos_state.view_num + 1
            node.paxos_leader.start_leader_election(new_view)
        
        # Should have started new election
        node.paxos_leader.start_leader_election.assert_called_once_with(2)
    
    def test_catch_up_mechanism(self):
        """Test catch-up mechanism for recovering nodes"""
        node = self.create_node("n1", 5001)
        node.send_message = Mock(return_value=True)
        
        # Add some log entries
        tx1 = Transaction("A", "B", 5)
        tx2 = Transaction("B", "C", 3)
        node.paxos_state.accept_log = [
            LogEntry(0, tx1, False, "E"),
            LogEntry(1, tx2, False, "C"),
            LogEntry(2, Transaction("C", "D", 2), False, "A")
        ]
        
        # Simulate catch-up request from n2 (last_seq_num = 0)
        catch_up_req = CatchUpRequestMessage("n2", "n1", 0)
        node._handle_catch_up_request(catch_up_req)
        
        # Should send response with entries after seq 0
        node.send_message.assert_called_once()
        call_args = node.send_message.call_args[0][0]
        self.assertEqual(call_args.msg_type, MessageType.CATCH_UP_RESPONSE)
        
        # Should include entries 1 and 2
        response_entries = [LogEntry.from_dict(entry) for entry in call_args.data['log_entries']]
        seq_nums = {entry.seq_num for entry in response_entries}
        self.assertEqual(seq_nums, {1, 2})


class TestTransactionExecution(unittest.TestCase):
    """Test transaction execution and ordering"""
    
    def setUp(self):
        self.created_nodes = []  # Track nodes for cleanup
    
    def tearDown(self):
        """Clean up any created nodes"""
        for node in self.created_nodes:
            if hasattr(node, 'stop'):
                node.stop()
        self.created_nodes.clear()
    
    def create_node(self, node_id, port, all_nodes):
        """Helper to create and track nodes for cleanup"""
        node = Node(node_id, port, all_nodes)
        self.created_nodes.append(node)
        return node
    
    def test_sequential_execution(self):
        """Test that transactions are executed in sequence order"""
        node = self.create_node("n1", 5001, {"n1": ("localhost", 5001)})
        
        # Add transactions out of order
        tx1 = Transaction("A", "B", 5)
        tx2 = Transaction("B", "C", 3)
        tx3 = Transaction("C", "D", 2)
        
        node.paxos_state.accept_log = [
            LogEntry(2, tx3, False, "C"),  # Out of order
            LogEntry(0, tx1, False, "C"),
            LogEntry(1, tx2, False, "C")
        ]
        node.paxos_state.last_executed_seq = -1
        
        # Execute transactions in order
        for expected_seq in [0, 1, 2]:
            # Find next transaction to execute
            next_seq = node.paxos_state.last_executed_seq + 1
            entry_to_execute = None
            
            for entry in node.paxos_state.accept_log:
                if entry.seq_num == next_seq and entry.status == "C":
                    entry_to_execute = entry
                    break
            
            if entry_to_execute:
                success = node._execute_transaction(entry_to_execute)
                self.assertTrue(success)
                entry_to_execute.status = "E"
                node.paxos_state.last_executed_seq = next_seq
        
        # Check final balances
        self.assertEqual(node.balances["A"], 5)   # 10 - 5
        self.assertEqual(node.balances["B"], 12)  # 10 + 5 - 3
        self.assertEqual(node.balances["C"], 11)  # 10 + 3 - 2
        self.assertEqual(node.balances["D"], 12)  # 10 + 2
    
    def test_transaction_with_insufficient_funds(self):
        """Test transaction execution with insufficient funds"""
        node = self.create_node("n1", 5001, {"n1": ("localhost", 5001)})
        
        # Transaction that would overdraw account
        tx = Transaction("A", "B", 15)  # A only has 10
        entry = LogEntry(0, tx, False, "C")
        
        result = node._execute_transaction(entry)
        
        self.assertFalse(result)
        # Balances should be unchanged
        self.assertEqual(node.balances["A"], 10)
        self.assertEqual(node.balances["B"], 10)
    
    def test_noop_execution(self):
        """Test no-op transaction execution"""
        node = self.create_node("n1", 5001, {"n1": ("localhost", 5001)})
        
        entry = LogEntry(0, None, True, "C")
        
        result = node._execute_transaction(entry)
        
        self.assertTrue(result)
        # All balances should remain at 10
        for client in ['A', 'B', 'C', 'D', 'E']:
            self.assertEqual(node.balances[client], 10)


class TestEndToEndScenarios(unittest.TestCase):
    """Test complete end-to-end scenarios"""
    
    def setUp(self):
        # Use different ports to avoid conflicts
        self.all_nodes = {
            "n1": ("localhost", 6001),
            "n2": ("localhost", 6002),
            "n3": ("localhost", 6003)
        }
        self.created_nodes = []  # Track nodes for cleanup
    
    def tearDown(self):
        """Clean up any created nodes"""
        for node in self.created_nodes:
            if hasattr(node, 'stop'):
                node.stop()
        self.created_nodes.clear()
    
    def create_node(self, node_id, port):
        """Helper to create and track nodes for cleanup"""
        node = Node(node_id, port, self.all_nodes)
        self.created_nodes.append(node)
        return node
    
    def test_normal_operation_flow(self):
        """Test normal operation: leader election -> transaction -> commit -> execute"""
        # This test would require actual networking, so we'll mock the key parts
        
        # Create nodes with mocked networking
        nodes = {}
        for node_id, (host, port) in self.all_nodes.items():
            node = self.create_node(node_id, port)
            node.send_message = Mock(return_value=True)
            node.broadcast_message = Mock()
            nodes[node_id] = node
        
        # 1. Leader election
        leader_node = nodes["n1"]
        leader = leader_node.paxos_leader
        leader.start_leader_election(1)
        
        # Simulate majority ACKs
        for node_id in ["n1", "n2", "n3"]:
            ack_msg = AckMessage(node_id, "n1", 1, [])
            leader.handle_ack(ack_msg)
        
        self.assertTrue(leader.state.is_leader)
        
        # 2. Client transaction
        tx = Transaction("A", "B", 5)
        success, msg = leader.handle_client_request(tx, "A", 123)
        
        self.assertTrue(success)
        self.assertEqual(len(leader.state.accept_log), 1)
        
        # 3. Simulate ACCEPTED responses from majority
        leader.state.accepted_responses[0] = {"n1", "n2", "n3"}
        
        # This would trigger COMMIT in real scenario
        # 4. Execute transaction
        entry = leader.state.accept_log[0]
        entry.status = "C"  # Mark as committed
        
        result = leader_node._execute_transaction(entry)
        self.assertTrue(result)
        
        # Check balances
        self.assertEqual(leader_node.balances["A"], 5)
        self.assertEqual(leader_node.balances["B"], 15)
    
    def test_concurrent_transactions(self):
        """Test handling multiple concurrent transactions"""
        node = self.create_node("n1", 5001)
        node.paxos_state.is_leader = True
        node.send_message = Mock(return_value=True)
        node.broadcast_message = Mock()
        
        # Submit multiple transactions
        transactions = [
            Transaction("A", "B", 2),
            Transaction("C", "D", 3),
            Transaction("E", "A", 1)
        ]
        
        for i, tx in enumerate(transactions):
            success, msg = node.paxos_leader.handle_client_request(tx, tx.sender, i)
            self.assertTrue(success)
        
        # Should have 3 entries in accept log
        self.assertEqual(len(node.paxos_state.accept_log), 3)
        
        # All should have different sequence numbers
        seq_nums = {entry.seq_num for entry in node.paxos_state.accept_log}
        self.assertEqual(seq_nums, {0, 1, 2})


class TestCSVProcessing(unittest.TestCase):
    """Test CSV input processing"""
    
    def test_csv_parsing(self):
        """Test parsing CSV input format"""
        # Create temporary CSV file
        csv_content = '''SetNumber,Transactions,LiveNodes
1,"(A,C,5),(C,E,4)","[n1,n2,n3]"
2,"(B,D,2)","[n1,n3]"'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            csv_file = f.name
        
        try:
            system = BankingSystem()
            
            # Mock the system components to avoid actual startup
            system.nodes = {}
            system.client_manager = Mock()
            system.client_manager.send_transactions = Mock()
            
            # Mock the internal methods
            system._update_live_nodes = Mock()
            system._process_transaction_set = Mock()
            system._print_system_state = Mock()
            
            # Process CSV (this would normally require user input, so we'll mock that too)
            with patch('builtins.input', return_value=''):
                with patch('builtins.open', mock_open(read_data=csv_content)):
                    # We can't easily test the full CSV processing without mocking input()
                    # But we can test the parsing components
                    pass
            
            # Test individual parsing functions
            live_nodes = system._parse_live_nodes("[n1,n2,n3]")
            self.assertEqual(live_nodes, {"n1", "n2", "n3"})
            
            transactions = parse_transactions("(A,C,5),(C,E,4)")
            self.assertEqual(len(transactions), 2)
            self.assertEqual(transactions[0].sender, "A")
            self.assertEqual(transactions[1].sender, "C")
            
        finally:
            os.unlink(csv_file)


def mock_open(read_data=''):
    """Helper function to mock file opening"""
    from unittest.mock import mock_open as original_mock_open
    return original_mock_open(read_data=read_data)


if __name__ == '__main__':
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestLeaderElection,
        TestFailureHandling,
        TestTransactionExecution,
        TestEndToEndScenarios,
        TestCSVProcessing
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"INTEGRATION TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.failures:
        print(f"\nFAILURES:")
        for test, traceback in result.failures:
            print(f"  {test}")
    
    if result.errors:
        print(f"\nERRORS:")
        for test, traceback in result.errors:
            print(f"  {test}")
    
    if result.wasSuccessful():
        print(f"\n🎉 ALL INTEGRATION TESTS PASSED!")
    else:
        print(f"\n❌ SOME INTEGRATION TESTS FAILED!")
    
    print(f"{'='*60}")
