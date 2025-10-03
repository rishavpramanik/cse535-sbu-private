"""
Node implementation for the Distributed Paxos Banking System.
Each node can act as either a leader or backup in the Paxos consensus.
"""

import socket
import threading
import time
import json
from typing import Dict, List, Set, Optional, Tuple
from messages import *
from paxos import PaxosState, PaxosLeader, PaxosBackup


class Node:
    def __init__(self, node_id: str, port: int, all_nodes: Dict[str, Tuple[str, int]]):
        self.node_id = node_id
        self.port = port
        self.host = "localhost"
        self.all_nodes = all_nodes  # node_id -> (host, port)
        
        # Banking state
        self.balances = {}  # client_id -> balance
        self.initialize_balances()
        
        # Paxos state
        self.paxos_state = PaxosState(node_id)
        self.paxos_leader = PaxosLeader(self)
        self.paxos_backup = PaxosBackup(self)
        
        # Communication
        self.socket = None
        self.running = False
        self.message_log = []  # All messages handled by this node
        self.pending_client_requests = {}  # seq_num -> (client_id, timestamp)
        
        # Failure detection
        self.alive_nodes = set(all_nodes.keys())
        self.last_heartbeat = {}  # node_id -> timestamp
        self.heartbeat_interval = 2.0
        self.failure_timeout = 6.0
        
        # Locks
        self.balance_lock = threading.RLock()
        self.log_lock = threading.RLock()
        
    def initialize_balances(self):
        """Initialize client balances to 10 each"""
        clients = ['A', 'B', 'C', 'D', 'E']
        with self.balance_lock:
            for client in clients:
                self.balances[client] = 10
    
    def start(self):
        """Start the node"""
        self.running = True
        
        # Start socket server
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen(10)
        
        print(f"Node {self.node_id} started on {self.host}:{self.port}")
        
        # Start threads
        threading.Thread(target=self._accept_connections, daemon=True).start()
        threading.Thread(target=self._heartbeat_sender, daemon=True).start()
        threading.Thread(target=self._failure_detector, daemon=True).start()
        threading.Thread(target=self._transaction_executor, daemon=True).start()
        
        # Start leader election if this is the first node
        if self.node_id == "n1":
            threading.Timer(1.0, lambda: self.paxos_leader.start_leader_election(1)).start()
    
    def stop(self):
        """Stop the node"""
        self.running = False
        if self.socket:
            self.socket.close()
    
    def _accept_connections(self):
        """Accept incoming connections"""
        while self.running:
            try:
                client_socket, addr = self.socket.accept()
                threading.Thread(target=self._handle_connection, 
                               args=(client_socket,), daemon=True).start()
            except Exception as e:
                if self.running:
                    print(f"Node {self.node_id} connection error: {e}")
                break
    
    def _handle_connection(self, client_socket):
        """Handle incoming connection"""
        try:
            while self.running:
                data = client_socket.recv(4096)
                if not data:
                    break
                
                try:
                    message = Message.from_json(data.decode())
                    self._handle_message(message)
                except Exception as e:
                    print(f"Node {self.node_id} message handling error: {e}")
        except Exception as e:
            if self.running:
                print(f"Node {self.node_id} connection handling error: {e}")
        finally:
            client_socket.close()
    
    def _handle_message(self, message: Message):
        """Handle incoming message"""
        with self.log_lock:
            self.message_log.append(message)
        
        msg_type = message.msg_type
        
        try:
            if msg_type == MessageType.PREPARE:
                self.paxos_leader.handle_prepare(message)
            elif msg_type == MessageType.ACK:
                self.paxos_leader.handle_ack(message)
            elif msg_type == MessageType.NEW_VIEW:
                self.paxos_backup.handle_new_view(message)
            elif msg_type == MessageType.ACCEPT:
                self.paxos_backup.handle_accept(message)
            elif msg_type == MessageType.ACCEPTED:
                self.paxos_leader.handle_accepted(message)
            elif msg_type == MessageType.COMMIT:
                self.paxos_backup.handle_commit(message)
            elif msg_type == MessageType.CLIENT_REQUEST:
                self._handle_client_request(message)
            elif msg_type == MessageType.HEARTBEAT:
                self._handle_heartbeat(message)
            elif msg_type == MessageType.HEARTBEAT_ACK:
                self._handle_heartbeat_ack(message)
            elif msg_type == MessageType.CATCH_UP_REQUEST:
                self._handle_catch_up_request(message)
            elif msg_type == MessageType.CATCH_UP_RESPONSE:
                self._handle_catch_up_response(message)
        except Exception as e:
            print(f"Node {self.node_id} error handling {msg_type}: {e}")
    
    def _handle_client_request(self, message: Message):
        """Handle client transaction request"""
        transaction = Transaction.from_dict(message.data['transaction'])
        client_timestamp = message.data['client_timestamp']
        
        if self.paxos_state.is_leader:
            success, msg = self.paxos_leader.handle_client_request(
                transaction, message.sender_id, client_timestamp)
            
            if not success:
                # Send immediate failure response
                response = ClientResponseMessage(
                    self.node_id, message.sender_id, False, msg, client_timestamp)
                self.send_message(response)
        else:
            # Redirect to leader
            leader_id = self.paxos_state.leader_id
            if leader_id and leader_id in self.alive_nodes:
                response = ClientResponseMessage(
                    self.node_id, message.sender_id, False, 
                    f"Not leader, try {leader_id}", client_timestamp)
            else:
                response = ClientResponseMessage(
                    self.node_id, message.sender_id, False, 
                    "No leader available", client_timestamp)
            self.send_message(response)
    
    def _handle_heartbeat(self, message: Message):
        """Handle heartbeat message"""
        # Send heartbeat ack
        ack = HeartbeatAckMessage(self.node_id, message.sender_id)
        self.send_message(ack)
    
    def _handle_heartbeat_ack(self, message: Message):
        """Handle heartbeat acknowledgment"""
        self.last_heartbeat[message.sender_id] = time.time()
    
    def _handle_catch_up_request(self, message: Message):
        """Handle catch-up request from recovering node"""
        last_seq_num = message.data['last_seq_num']
        
        # Send log entries after last_seq_num
        catch_up_entries = []
        with self.paxos_state.state_lock:
            for entry in self.paxos_state.accept_log:
                if entry.seq_num > last_seq_num:
                    catch_up_entries.append(entry)
        
        response = CatchUpResponseMessage(self.node_id, message.sender_id, catch_up_entries)
        self.send_message(response)
    
    def _handle_catch_up_response(self, message: Message):
        """Handle catch-up response"""
        log_entries = [LogEntry.from_dict(entry) for entry in message.data['log_entries']]
        
        with self.paxos_state.state_lock:
            for entry in log_entries:
                # Add missing entries
                existing = any(e.seq_num == entry.seq_num for e in self.paxos_state.accept_log)
                if not existing:
                    self.paxos_state.accept_log.append(entry)
            
            # Sort by sequence number
            self.paxos_state.accept_log.sort(key=lambda x: x.seq_num)
    
    def send_message(self, message: Message):
        """Send message to specific node"""
        if message.receiver_id == "broadcast":
            self.broadcast_message(message)
            return
        
        if message.receiver_id not in self.all_nodes:
            return False
        
        try:
            host, port = self.all_nodes[message.receiver_id]
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect((host, port))
            sock.send(message.to_json().encode())
            sock.close()
            return True
        except Exception as e:
            print(f"Node {self.node_id} failed to send to {message.receiver_id}: {e}")
            return False
    
    def broadcast_message(self, message: Message):
        """Broadcast message to all nodes"""
        for node_id in self.all_nodes:
            if node_id != self.node_id and node_id in self.alive_nodes:
                message.receiver_id = node_id
                self.send_message(message)
    
    def _heartbeat_sender(self):
        """Send periodic heartbeats"""
        while self.running:
            for node_id in self.all_nodes:
                if node_id != self.node_id and node_id in self.alive_nodes:
                    heartbeat = HeartbeatMessage(self.node_id, node_id)
                    self.send_message(heartbeat)
            time.sleep(self.heartbeat_interval)
    
    def _failure_detector(self):
        """Detect node failures"""
        while self.running:
            current_time = time.time()
            failed_nodes = []
            
            for node_id in list(self.alive_nodes):
                if node_id != self.node_id:
                    last_hb = self.last_heartbeat.get(node_id, 0)
                    if current_time - last_hb > self.failure_timeout:
                        failed_nodes.append(node_id)
            
            # Handle failures
            for node_id in failed_nodes:
                self.alive_nodes.discard(node_id)
                print(f"Node {self.node_id} detected failure of {node_id}")
                
                # If leader failed, start new election
                if node_id == self.paxos_state.leader_id:
                    print(f"Node {self.node_id} leader {node_id} failed, starting election")
                    new_view = self.paxos_state.view_num + 1
                    threading.Timer(1.0, lambda: self.paxos_leader.start_leader_election(new_view)).start()
            
            time.sleep(1.0)
    
    def _transaction_executor(self):
        """Execute committed transactions in order"""
        while self.running:
            with self.paxos_state.state_lock:
                # Find next transaction to execute
                next_seq = self.paxos_state.last_executed_seq + 1
                
                # Find entry with this sequence number
                entry_to_execute = None
                for entry in self.paxos_state.accept_log:
                    if entry.seq_num == next_seq and entry.status == "C":
                        entry_to_execute = entry
                        break
                
                if entry_to_execute:
                    success = self._execute_transaction(entry_to_execute)
                    entry_to_execute.status = "E"
                    self.paxos_state.last_executed_seq = next_seq
                    
                    # Send response to client if this node is leader
                    if (self.paxos_state.is_leader and 
                        next_seq in self.pending_client_requests):
                        client_id, client_timestamp = self.pending_client_requests[next_seq]
                        
                        if success:
                            msg = "Transaction executed successfully"
                        else:
                            msg = "Transaction failed: insufficient funds"
                        
                        response = ClientResponseMessage(
                            self.node_id, client_id, success, msg, client_timestamp)
                        self.send_message(response)
                        
                        del self.pending_client_requests[next_seq]
            
            time.sleep(0.1)
    
    def _execute_transaction(self, entry: LogEntry) -> bool:
        """Execute a single transaction"""
        if entry.is_noop or not entry.transaction:
            return True
        
        transaction = entry.transaction
        
        with self.balance_lock:
            # Check if sender has sufficient funds
            if self.balances.get(transaction.sender, 0) < transaction.amount:
                return False
            
            # Execute transaction
            self.balances[transaction.sender] -= transaction.amount
            self.balances[transaction.receiver] = self.balances.get(transaction.receiver, 0) + transaction.amount
            
            print(f"Node {self.node_id} executed: {transaction}")
            return True
    
    def simulate_failure(self):
        """Simulate node failure"""
        print(f"Node {self.node_id} simulating failure")
        self.running = False
        if self.socket:
            self.socket.close()
    
    def recover(self):
        """Recover from failure"""
        print(f"Node {self.node_id} recovering")
        self.running = True
        
        # Restart socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen(10)
        
        # Restart threads
        threading.Thread(target=self._accept_connections, daemon=True).start()
        threading.Thread(target=self._heartbeat_sender, daemon=True).start()
        threading.Thread(target=self._failure_detector, daemon=True).start()
        threading.Thread(target=self._transaction_executor, daemon=True).start()
        
        # Request catch-up from other nodes
        self._request_catch_up()
    
    def _request_catch_up(self):
        """Request catch-up from other nodes"""
        last_seq = -1
        if self.paxos_state.accept_log:
            last_seq = max(entry.seq_num for entry in self.paxos_state.accept_log)
        
        for node_id in self.all_nodes:
            if node_id != self.node_id:
                catch_up_req = CatchUpRequestMessage(self.node_id, node_id, last_seq)
                self.send_message(catch_up_req)
    
    # Print functions for debugging and testing
    def print_log(self):
        """Print all messages handled by this node"""
        print(f"\n=== Log for Node {self.node_id} ===")
        with self.log_lock:
            for i, msg in enumerate(self.message_log):
                print(f"{i+1}: {msg.msg_type.value} from {msg.sender_id} to {msg.receiver_id}")
        print("=" * 30)
    
    def print_db(self):
        """Print current balances"""
        print(f"\n=== Database for Node {self.node_id} ===")
        with self.balance_lock:
            for client, balance in sorted(self.balances.items()):
                print(f"{client}: {balance}")
        print("=" * 35)
    
    def print_status(self, seq_num: int):
        """Print status of specific sequence number"""
        with self.paxos_state.state_lock:
            for entry in self.paxos_state.accept_log:
                if entry.seq_num == seq_num:
                    print(f"Node {self.node_id} Seq {seq_num}: {entry.status}")
                    return
            print(f"Node {self.node_id} Seq {seq_num}: X")
    
    def print_view(self):
        """Print all NEW_VIEW messages exchanged"""
        print(f"\n=== NEW_VIEW Messages for Node {self.node_id} ===")
        with self.paxos_state.state_lock:
            for msg in self.paxos_state.new_view_messages:
                print(f"View {msg.data['view_num']}: Leader {msg.sender_id}")
        print("=" * 45)
