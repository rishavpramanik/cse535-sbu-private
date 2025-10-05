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
    def __init__(self, node_id: str, port: int, all_nodes: Dict[str, Tuple[str, int]], client_ports: Dict[str, int] = None):
        self.node_id = node_id
        self.port = port
        self.host = "localhost"
        self.all_nodes = all_nodes  # node_id -> (host, port)
        self.client_ports = client_ports or {}  # client_id -> port
        
        # Locks (initialize first)
        self.balance_lock = threading.RLock()
        self.log_lock = threading.RLock()
        
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
        
        # Thread management
        self.threads = []  # Track all threads for proper shutdown
        self.timers = []   # Track all timers for proper shutdown
        
        # Failure detection
        self.alive_nodes = set(all_nodes.keys())
        self.last_heartbeat = {}  # node_id -> timestamp
        self.heartbeat_interval = 2.0
        self.failure_timeout = 6.0
        
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
        
        # Start threads and track them
        t1 = threading.Thread(target=self._accept_connections, daemon=True)
        t2 = threading.Thread(target=self._heartbeat_sender, daemon=True)
        t3 = threading.Thread(target=self._failure_detector, daemon=True)
        t4 = threading.Thread(target=self._transaction_executor, daemon=True)
        
        self.threads.extend([t1, t2, t3, t4])
        
        for thread in [t1, t2, t3, t4]:
            thread.start()
        
        # Start leader election if this is the first node
        if self.node_id == "n1":
            # Wait a bit longer for all nodes to start before beginning election
            timer = threading.Timer(3.0, lambda: self._safe_start_election(1))
            self.timers.append(timer)
            timer.start()
    
    def _safe_start_election(self, view_num):
        """Safely start election only if node is still running"""
        if self.running:
            self.paxos_leader.start_leader_election(view_num)
    
    def stop(self):
        """Stop the node and all its threads/timers"""
        print(f"Node {self.node_id} shutting down...")
        self.running = False
        
        # Cancel all timers
        for timer in self.timers:
            if timer.is_alive():
                timer.cancel()
        self.timers.clear()
        
        # Close socket to break accept() calls
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None
        
        # Give threads a moment to see running=False and exit gracefully
        import time
        time.sleep(0.1)
        
        print(f"Node {self.node_id} stopped")
    
    def add_timer(self, timer):
        """Add a timer to be tracked for shutdown"""
        self.timers.append(timer)
    
    def _accept_connections(self):
        """Accept incoming connections"""
        if not self.socket:
            return  # No socket to accept on
            
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
        sender_id = message.sender_id
        self.last_heartbeat[sender_id] = time.time()
        
        # If this node was marked as failed, mark it as alive again
        if sender_id not in self.alive_nodes:
            self.alive_nodes.add(sender_id)
    
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
            # Track what was our last executed sequence before catch-up
            old_last_executed = self.paxos_state.last_executed_seq
            
            for entry in log_entries:
                # Add missing entries
                existing = any(e.seq_num == entry.seq_num for e in self.paxos_state.accept_log)
                if not existing:
                    self.paxos_state.accept_log.append(entry)
            
            # Sort by sequence number
            self.paxos_state.accept_log.sort(key=lambda x: x.seq_num)
            
            # Execute any committed transactions that we missed
            for entry in self.paxos_state.accept_log:
                if (entry.status == "C" and 
                    entry.seq_num > old_last_executed and 
                    entry.seq_num > self.paxos_state.last_executed_seq):
                    
                    if entry.transaction.transaction_type != "noop":
                        success = self._execute_transaction(entry)
                    
                    entry.status = "E"
                    self.paxos_state.last_executed_seq = entry.seq_num
    
    def send_message(self, message: Message):
        """Send message to specific node or client"""
        if message.receiver_id == "broadcast":
            self.broadcast_message(message)
            return
        
        # Check if this is a client response
        if (message.msg_type == MessageType.CLIENT_RESPONSE and 
            message.receiver_id in self.client_ports):
            return self._send_to_client(message)
        
        # Regular node-to-node message
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
    
    def _send_to_client(self, message: Message):
        """Send message to client"""
        try:
            client_id = message.receiver_id
            port = self.client_ports[client_id]
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect(("localhost", port))
            sock.send(message.to_json().encode())
            sock.close()
            return True
        except Exception as e:
            print(f"Node {self.node_id} failed to send to client {message.receiver_id}: {e}")
            return False
    
    def broadcast_message(self, message: Message):
        """Broadcast message to all nodes"""
        for node_id in self.all_nodes:
            if node_id != self.node_id and node_id in self.alive_nodes:
                message.receiver_id = node_id
                self.send_message(message)
    
    def _heartbeat_sender(self):
        """Send periodic heartbeats"""
        # Wait a bit before starting heartbeats to let all nodes initialize
        import time
        time.sleep(2.0)
        
        while self.running:
            for node_id in self.all_nodes:
                if node_id != self.node_id and node_id in self.alive_nodes:
                    heartbeat = HeartbeatMessage(self.node_id, node_id)
                    self.send_message(heartbeat)
            time.sleep(self.heartbeat_interval)
    
    def _failure_detector(self):
        """Detect node failures"""
        # Wait before starting failure detection to allow initial heartbeats
        import time
        time.sleep(5.0)
        
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
                    timer = threading.Timer(1.0, lambda: self._safe_start_election(new_view))
                    self.timers.append(timer)
                    timer.start()
            
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
        
        # Cancel all timers
        for timer in self.timers:
            if timer.is_alive():
                timer.cancel()
        self.timers.clear()
        
        # Close socket properly
        if self.socket:
            try:
                # Shutdown the socket before closing to release it faster
                self.socket.shutdown(socket.SHUT_RDWR)
                self.socket.close()
            except Exception:
                pass
            self.socket = None
        
        # Give a moment for socket to be released
        import time
        time.sleep(0.5)
    
    def recover(self):
        """Recover from failure"""
        print(f"Node {self.node_id} recovering")
        self.running = True
        
        # Clear old timers list
        self.timers.clear()
        
        # Try to restart socket with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Create new socket
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                # Also set SO_REUSEPORT if available (Linux)
                try:
                    self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                except AttributeError:
                    pass  # SO_REUSEPORT not available on this system
                self.socket.bind((self.host, self.port))
                self.socket.listen(10)
                break
            except OSError as e:
                if e.errno == 98:  # Address already in use
                    print(f"Node {self.node_id} port {self.port} still in use, retrying... (attempt {attempt + 1}/{max_retries})")
                    import time
                    time.sleep(1.0)  # Wait longer between attempts
                    if self.socket:
                        try:
                            self.socket.close()
                        except Exception:
                            pass
                        self.socket = None
                else:
                    raise e
        else:
            # If we exhausted all retries, try a different approach
            print(f"Node {self.node_id} could not bind to original port, continuing without socket server...")
            self.socket = None
            # Continue without server socket - node can still send messages
        
        # Restart threads and track them (only start accept_connections if we have a socket)
        threads_to_start = []
        if self.socket:
            threads_to_start.append(threading.Thread(target=self._accept_connections, daemon=True))
        
        threads_to_start.extend([
            threading.Thread(target=self._heartbeat_sender, daemon=True),
            threading.Thread(target=self._failure_detector, daemon=True),
            threading.Thread(target=self._transaction_executor, daemon=True)
        ])
        
        self.threads.extend(threads_to_start)
        
        for thread in threads_to_start:
            thread.start()
        
        # Request catch-up from other nodes and announce recovery
        self._request_catch_up()
        self._announce_recovery()
    
    def _announce_recovery(self):
        """Announce recovery to all other nodes"""
        for node_id in self.all_nodes:
            if node_id != self.node_id:
                # Send immediate heartbeat to announce we're back
                heartbeat = HeartbeatMessage(self.node_id, node_id)
                self.send_message(heartbeat)
    
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
