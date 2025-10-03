"""
Unit tests for the Distributed Paxos Banking System.
Tests individual components and their interactions.
"""

import unittest
import threading
import time
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
import json

# Import our modules
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from messages import *
from paxos import PaxosState, PaxosLeader, PaxosBackup
from node import Node
from client import Client, ClientManager, parse_transactions
from main import BankingSystem


class TestMessages(unittest.TestCase):
    """Test message serialization and deserialization"""
    
    def test_transaction_serialization(self):
        """Test Transaction to/from dict conversion"""
        tx = Transaction("A", "B", 10)
        tx_dict = tx.to_dict()
        
        self.assertEqual(tx_dict["sender"], "A")
        self.assertEqual(tx_dict["receiver"], "B")
        self.assertEqual(tx_dict["amount"], 10)
        
        # Test round-trip
        tx2 = Transaction.from_dict(tx_dict)
        self.assertEqual(tx.sender, tx2.sender)
        self.assertEqual(tx.receiver, tx2.receiver)
        self.assertEqual(tx.amount, tx2.amount)
    
    def test_log_entry_serialization(self):
        """Test LogEntry serialization"""
        tx = Transaction("A", "B", 5)
        entry = LogEntry(1, tx, False, "A")
        
        entry_dict = entry.to_dict()
        entry2 = LogEntry.from_dict(entry_dict)
        
        self.assertEqual(entry.seq_num, entry2.seq_num)
        self.assertEqual(entry.transaction.sender, entry2.transaction.sender)
        self.assertEqual(entry.is_noop, entry2.is_noop)
        self.assertEqual(entry.status, entry2.status)
    
    def test_noop_log_entry(self):
        """Test no-op log entry"""
        entry = LogEntry(0, None, True, "A")
        entry_dict = entry.to_dict()
        entry2 = LogEntry.from_dict(entry_dict)
        
        self.assertTrue(entry2.is_noop)
        self.assertIsNone(entry2.transaction)
    
    def test_message_json_serialization(self):
        """Test Message JSON serialization"""
        msg = PrepareMessage("n1", "n2", 1)
        json_str = msg.to_json()
        
        # Should be valid JSON
        data = json.loads(json_str)
        self.assertEqual(data["msg_type"], "PREPARE")
        self.assertEqual(data["sender_id"], "n1")
        self.assertEqual(data["receiver_id"], "n2")
        
        # Test round-trip
        msg2 = Message.from_json(json_str)
        self.assertEqual(msg.msg_type, msg2.msg_type)
        self.assertEqual(msg.sender_id, msg2.sender_id)
        self.assertEqual(msg.receiver_id, msg2.receiver_id)
    
    def test_all_message_types(self):
        """Test all message type serializations"""
        tx = Transaction("A", "B", 5)
        log_entries = [LogEntry(0, tx, False, "A")]
        
        messages = [
            PrepareMessage("n1", "n2", 1),
            AckMessage("n1", "n2", 1, log_entries),
            NewViewMessage("n1", "n2", 1, log_entries),
            RequestMessage("n1", "n2", 0, tx),
            AcceptMessage("n1", "n2", 0, tx),
            AcceptedMessage("n1", "n2", 0),
            CommitMessage("n1", "n2", 0),
            ClientRequestMessage("A", "n1", tx, 123),
            ClientResponseMessage("n1", "A", True, "Success", 123),
            HeartbeatMessage("n1", "n2"),
            HeartbeatAckMessage("n1", "n2"),
            CatchUpRequestMessage("n1", "n2", 5),
            CatchUpResponseMessage("n1", "n2", log_entries)
        ]
        
        for msg in messages:
            json_str = msg.to_json()
            msg2 = Message.from_json(json_str)
            self.assertEqual(msg.msg_type, msg2.msg_type)
            self.assertEqual(msg.sender_id, msg2.sender_id)


class TestPaxosState(unittest.TestCase):
    """Test Paxos state management"""
    
    def setUp(self):
        self.state = PaxosState("n1")
    
    def test_initial_state(self):
        """Test initial Paxos state"""
        self.assertEqual(self.state.node_id, "n1")
        self.assertEqual(self.state.view_num, 0)
        self.assertFalse(self.state.is_leader)
        self.assertIsNone(self.state.leader_id)
        self.assertEqual(self.state.current_seq_num, 0)
        self.assertEqual(self.state.last_executed_seq, -1)
    
    def test_log_management(self):
        """Test log entry management"""
        tx = Transaction("A", "B", 5)
        entry = LogEntry(0, tx, False, "A")
        
        self.state.accept_log.append(entry)
        self.assertEqual(len(self.state.accept_log), 1)
        self.assertEqual(self.state.accept_log[0].seq_num, 0)


class TestPaxosLeader(unittest.TestCase):
    """Test Paxos leader functionality"""
    
    def setUp(self):
        self.mock_node = Mock()
        self.mock_node.paxos_state = PaxosState("n1")
        self.mock_node.broadcast_message = Mock()
        self.mock_node.send_message = Mock()
        self.mock_node.pending_client_requests = {}
        
        self.leader = PaxosLeader(self.mock_node)
    
    def test_start_leader_election(self):
        """Test starting leader election"""
        self.leader.start_leader_election(1)
        
        self.assertEqual(self.leader.state.view_num, 1)
        self.assertIn(1, self.leader.state.prepare_responses)
        self.mock_node.broadcast_message.assert_called_once()
    
    def test_handle_prepare_higher_view(self):
        """Test handling PREPARE with higher view number"""
        self.leader.state.view_num = 1
        prepare_msg = PrepareMessage("n2", "n1", 2)
        
        result = self.leader.handle_prepare(prepare_msg)
        
        self.assertTrue(result)
        self.assertEqual(self.leader.state.view_num, 2)
        self.assertFalse(self.leader.state.is_leader)
        self.mock_node.send_message.assert_called_once()
    
    def test_handle_prepare_lower_view(self):
        """Test handling PREPARE with lower view number"""
        self.leader.state.view_num = 2
        prepare_msg = PrepareMessage("n2", "n1", 1)
        
        result = self.leader.handle_prepare(prepare_msg)
        
        self.assertFalse(result)
        self.assertEqual(self.leader.state.view_num, 2)
    
    def test_handle_ack_majority(self):
        """Test handling ACK messages to reach majority"""
        self.leader.state.view_num = 1
        self.leader.state.prepare_responses[1] = []
        
        # Simulate ACK from 3 nodes (including self)
        for i in range(3):
            ack_msg = AckMessage(f"n{i+1}", "n1", 1, [])
            self.leader.handle_ack(ack_msg)
        
        # Should become leader after 3 ACKs
        self.assertTrue(self.leader.state.is_leader)
        self.assertEqual(self.leader.state.leader_id, "n1")
    
    def test_client_request_handling(self):
        """Test handling client requests"""
        tx = Transaction("A", "B", 5)
        self.leader.state.is_leader = True
        
        success, msg = self.leader.handle_client_request(tx, "A", 123)
        
        self.assertTrue(success)
        self.assertEqual(msg, "Request accepted")
        self.assertEqual(len(self.leader.state.accept_log), 1)
        self.mock_node.broadcast_message.assert_called_once()
    
    def test_client_request_not_leader(self):
        """Test client request when not leader"""
        tx = Transaction("A", "B", 5)
        self.leader.state.is_leader = False
        
        success, msg = self.leader.handle_client_request(tx, "A", 123)
        
        self.assertFalse(success)
        self.assertEqual(msg, "Not the leader")


class TestPaxosBackup(unittest.TestCase):
    """Test Paxos backup functionality"""
    
    def setUp(self):
        self.mock_node = Mock()
        self.mock_node.paxos_state = PaxosState("n2")
        self.mock_node.send_message = Mock()
        
        self.backup = PaxosBackup(self.mock_node)
    
    def test_handle_new_view(self):
        """Test handling NEW_VIEW message"""
        tx = Transaction("A", "B", 5)
        log_entries = [LogEntry(0, tx, False, "A")]
        new_view_msg = NewViewMessage("n1", "n2", 1, log_entries)
        
        result = self.backup.handle_new_view(new_view_msg)
        
        self.assertTrue(result)
        self.assertEqual(self.backup.state.view_num, 1)
        self.assertEqual(self.backup.state.leader_id, "n1")
        self.assertFalse(self.backup.state.is_leader)
        self.assertEqual(len(self.backup.state.accept_log), 1)
    
    def test_handle_accept(self):
        """Test handling ACCEPT message"""
        tx = Transaction("A", "B", 5)
        self.backup.state.leader_id = "n1"
        accept_msg = AcceptMessage("n1", "n2", 0, tx)
        
        result = self.backup.handle_accept(accept_msg)
        
        self.assertTrue(result)
        self.assertEqual(len(self.backup.state.accept_log), 1)
        self.assertEqual(self.backup.state.accept_log[0].status, "A")
        self.mock_node.send_message.assert_called_once()
    
    def test_handle_commit(self):
        """Test handling COMMIT message"""
        # First add an accepted entry
        tx = Transaction("A", "B", 5)
        entry = LogEntry(0, tx, False, "A")
        self.backup.state.accept_log.append(entry)
        self.backup.state.leader_id = "n1"
        
        commit_msg = CommitMessage("n1", "n2", 0)
        result = self.backup.handle_commit(commit_msg)
        
        self.assertTrue(result)
        self.assertEqual(self.backup.state.accept_log[0].status, "C")


class TestTransactionParsing(unittest.TestCase):
    """Test transaction parsing from CSV format"""
    
    def test_parse_single_transaction(self):
        """Test parsing single transaction"""
        tx_str = "(A,B,5)"
        transactions = parse_transactions(tx_str)
        
        self.assertEqual(len(transactions), 1)
        self.assertEqual(transactions[0].sender, "A")
        self.assertEqual(transactions[0].receiver, "B")
        self.assertEqual(transactions[0].amount, 5)
    
    def test_parse_multiple_transactions(self):
        """Test parsing multiple transactions"""
        tx_str = "(A,C,5),(C,E,4),(B,D,2)"
        transactions = parse_transactions(tx_str)
        
        self.assertEqual(len(transactions), 3)
        self.assertEqual(transactions[0].sender, "A")
        self.assertEqual(transactions[1].sender, "C")
        self.assertEqual(transactions[2].sender, "B")
    
    def test_parse_empty_string(self):
        """Test parsing empty string"""
        transactions = parse_transactions("")
        self.assertEqual(len(transactions), 0)
    
    def test_parse_malformed_transaction(self):
        """Test parsing malformed transaction string"""
        tx_str = "(A,B)"  # Missing amount
        transactions = parse_transactions(tx_str)
        self.assertEqual(len(transactions), 0)


class TestNodeInitialization(unittest.TestCase):
    """Test node initialization and basic functionality"""
    
    def setUp(self):
        self.all_nodes = {
            "n1": ("localhost", 5001),
            "n2": ("localhost", 5002)
        }
    
    def test_node_initialization(self):
        """Test node initialization"""
        node = Node("n1", 5001, self.all_nodes)
        
        self.assertEqual(node.node_id, "n1")
        self.assertEqual(node.port, 5001)
        self.assertEqual(node.host, "localhost")
        self.assertFalse(node.running)
        
        # Test initial balances
        expected_clients = ['A', 'B', 'C', 'D', 'E']
        for client in expected_clients:
            self.assertEqual(node.balances[client], 10)
    
    def test_transaction_execution_success(self):
        """Test successful transaction execution"""
        node = Node("n1", 5001, self.all_nodes)
        tx = Transaction("A", "B", 5)
        entry = LogEntry(0, tx, False, "C")
        
        result = node._execute_transaction(entry)
        
        self.assertTrue(result)
        self.assertEqual(node.balances["A"], 5)  # 10 - 5
        self.assertEqual(node.balances["B"], 15)  # 10 + 5
    
    def test_transaction_execution_insufficient_funds(self):
        """Test transaction execution with insufficient funds"""
        node = Node("n1", 5001, self.all_nodes)
        tx = Transaction("A", "B", 15)  # More than A's balance
        entry = LogEntry(0, tx, False, "C")
        
        result = node._execute_transaction(entry)
        
        self.assertFalse(result)
        self.assertEqual(node.balances["A"], 10)  # Unchanged
        self.assertEqual(node.balances["B"], 10)  # Unchanged
    
    def test_noop_transaction_execution(self):
        """Test no-op transaction execution"""
        node = Node("n1", 5001, self.all_nodes)
        entry = LogEntry(0, None, True, "C")
        
        result = node._execute_transaction(entry)
        
        self.assertTrue(result)
        # Balances should remain unchanged
        for client in ['A', 'B', 'C', 'D', 'E']:
            self.assertEqual(node.balances[client], 10)


class TestClientManager(unittest.TestCase):
    """Test client manager functionality"""
    
    def setUp(self):
        self.all_nodes = {
            "n1": ("localhost", 5001),
            "n2": ("localhost", 5002)
        }
        self.client_manager = ClientManager(self.all_nodes)
    
    def test_client_creation(self):
        """Test client creation"""
        client_ids = ['A', 'B', 'C']
        
        # Mock the client start method to avoid actual socket creation
        with patch.object(Client, 'start'):
            self.client_manager.create_clients(client_ids, 8000)
        
        self.assertEqual(len(self.client_manager.clients), 3)
        self.assertIn('A', self.client_manager.clients)
        self.assertIn('B', self.client_manager.clients)
        self.assertIn('C', self.client_manager.clients)
    
    def test_get_client(self):
        """Test getting client by ID"""
        with patch.object(Client, 'start'):
            self.client_manager.create_clients(['A'], 8000)
        
        client = self.client_manager.get_client('A')
        self.assertIsNotNone(client)
        self.assertEqual(client.client_id, 'A')
        
        non_existent = self.client_manager.get_client('Z')
        self.assertIsNone(non_existent)


class TestBankingSystem(unittest.TestCase):
    """Test banking system integration"""
    
    def setUp(self):
        self.system = BankingSystem()
    
    def test_parse_live_nodes(self):
        """Test parsing live nodes from CSV format"""
        live_nodes_str = "[n1,n2,n3]"
        live_nodes = self.system._parse_live_nodes(live_nodes_str)
        
        expected = {"n1", "n2", "n3"}
        self.assertEqual(live_nodes, expected)
    
    def test_parse_live_nodes_with_spaces(self):
        """Test parsing live nodes with spaces"""
        live_nodes_str = "[n1, n2, n3]"
        live_nodes = self.system._parse_live_nodes(live_nodes_str)
        
        expected = {"n1", "n2", "n3"}
        self.assertEqual(live_nodes, expected)
    
    def test_system_initialization(self):
        """Test system initialization"""
        # This test would require mocking socket operations
        # For now, just test the configuration
        expected_nodes = {"n1", "n2", "n3", "n4", "n5"}
        self.assertEqual(set(self.system.all_nodes_config.keys()), expected_nodes)
        self.assertEqual(self.system.live_nodes, expected_nodes)


class TestLogMerging(unittest.TestCase):
    """Test log merging functionality in Paxos"""
    
    def setUp(self):
        self.mock_node = Mock()
        self.mock_node.paxos_state = PaxosState("n1")
        self.mock_node.broadcast_message = Mock()
        self.mock_node.send_message = Mock()
        self.mock_node.pending_client_requests = {}
        
        self.leader = PaxosLeader(self.mock_node)
    
    def test_status_priority(self):
        """Test status priority for log merging"""
        priorities = {
            'X': 1, 'A': 2, 'C': 3, 'E': 4
        }
        
        for status, expected_priority in priorities.items():
            actual_priority = self.leader._status_priority(status)
            self.assertEqual(actual_priority, expected_priority)
    
    def test_merge_accept_log_with_gaps(self):
        """Test merging accept logs with gaps"""
        # Local log has entries 0, 2
        tx1 = Transaction("A", "B", 5)
        tx3 = Transaction("C", "D", 3)
        local_entries = [
            LogEntry(0, tx1, False, "A"),
            LogEntry(2, tx3, False, "C")
        ]
        self.leader.state.accept_log = local_entries
        
        # Remote log has entry 1
        tx2 = Transaction("B", "C", 7)
        remote_entries = [LogEntry(1, tx2, False, "A")]
        
        self.leader._merge_accept_log(remote_entries)
        
        # Should have all entries including no-op for missing slots
        self.assertEqual(len(self.leader.state.accept_log), 3)
        
        # Check sequence numbers are present
        seq_nums = {entry.seq_num for entry in self.leader.state.accept_log}
        self.assertEqual(seq_nums, {0, 1, 2})
    
    def test_fill_gaps_with_noops(self):
        """Test filling gaps with no-ops"""
        # Create log with gaps: has 0, 2, 4
        tx1 = Transaction("A", "B", 5)
        tx3 = Transaction("C", "D", 3)
        tx5 = Transaction("E", "A", 1)
        
        self.leader.state.accept_log = [
            LogEntry(0, tx1, False, "A"),
            LogEntry(2, tx3, False, "A"),
            LogEntry(4, tx5, False, "A")
        ]
        
        self.leader._fill_gaps_with_noops()
        
        # Should have 5 entries (0-4)
        self.assertEqual(len(self.leader.state.accept_log), 5)
        
        # Check that gaps are filled with no-ops
        for entry in self.leader.state.accept_log:
            if entry.seq_num in [1, 3]:
                self.assertTrue(entry.is_noop)
                self.assertIsNone(entry.transaction)


if __name__ == '__main__':
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestMessages,
        TestPaxosState,
        TestPaxosLeader,
        TestPaxosBackup,
        TestTransactionParsing,
        TestNodeInitialization,
        TestClientManager,
        TestBankingSystem,
        TestLogMerging
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"UNIT TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.failures:
        print(f"\nFAILURES:")
        for test, traceback in result.failures:
            print(f"  {test}: {traceback}")
    
    if result.errors:
        print(f"\nERRORS:")
        for test, traceback in result.errors:
            print(f"  {test}: {traceback}")
    
    if result.wasSuccessful():
        print(f"\n🎉 ALL TESTS PASSED!")
    else:
        print(f"\n❌ SOME TESTS FAILED!")
    
    print(f"{'='*60}")
