"""
Client implementation for the Distributed Paxos Banking System.
Each client sends transaction requests to the leader node.
"""

import socket
import threading
import time
import random
from typing import Dict, List, Tuple, Optional
from messages import *


class Client:
    def __init__(self, client_id: str, all_nodes: Dict[str, Tuple[str, int]]):
        self.client_id = client_id
        self.all_nodes = all_nodes  # node_id -> (host, port)
        self.current_leader = None
        self.timestamp = 0
        self.pending_requests = {}  # timestamp -> (transaction, response_received)
        self.response_timeout = 10.0
        
        # Client state
        self.running = False
        self.socket = None
        self.port = None
        
        # Locks
        self.request_lock = threading.RLock()
        
    def start(self, port: int):
        """Start the client"""
        self.port = port
        self.running = True
        
        # Start socket server for receiving responses
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(("localhost", port))
        self.socket.listen(5)
        
        print(f"Client {self.client_id} started on port {port}")
        
        # Start response handler thread
        threading.Thread(target=self._accept_responses, daemon=True).start()
        threading.Thread(target=self._timeout_handler, daemon=True).start()
    
    def stop(self):
        """Stop the client and all its threads"""
        print(f"Client {self.client_id} shutting down...")
        self.running = False
        
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
        
        print(f"Client {self.client_id} stopped")
    
    def _accept_responses(self):
        """Accept incoming response connections"""
        while self.running:
            try:
                client_socket, addr = self.socket.accept()
                threading.Thread(target=self._handle_response_connection, 
                               args=(client_socket,), daemon=True).start()
            except Exception as e:
                if self.running:
                    print(f"Client {self.client_id} response connection error: {e}")
                break
    
    def _handle_response_connection(self, client_socket):
        """Handle incoming response connection"""
        try:
            while self.running:
                data = client_socket.recv(4096)
                if not data:
                    break
                
                try:
                    message = Message.from_json(data.decode())
                    self._handle_response(message)
                except Exception as e:
                    print(f"Client {self.client_id} response handling error: {e}")
        except Exception as e:
            if self.running:
                print(f"Client {self.client_id} response connection handling error: {e}")
        finally:
            client_socket.close()
    
    def _handle_response(self, message: Message):
        """Handle response from node"""
        if message.msg_type != MessageType.CLIENT_RESPONSE:
            return
        
        client_timestamp = message.data['client_timestamp']
        success = message.data['success']
        response_message = message.data['message']
        
        with self.request_lock:
            if client_timestamp in self.pending_requests:
                transaction, _ = self.pending_requests[client_timestamp]
                self.pending_requests[client_timestamp] = (transaction, True)
                
                if success:
                    print(f"Client {self.client_id}: Transaction {transaction} SUCCESS - {response_message}")
                else:
                    print(f"Client {self.client_id}: Transaction {transaction} FAILED - {response_message}")
                    
                    # If not leader, update leader info
                    if "try" in response_message.lower():
                        parts = response_message.split()
                        if len(parts) > 2:
                            self.current_leader = parts[-1]
    
    def send_transaction(self, transaction: Transaction) -> bool:
        """Send transaction request to leader"""
        self.timestamp += 1
        current_timestamp = self.timestamp
        
        with self.request_lock:
            self.pending_requests[current_timestamp] = (transaction, False)
        
        # Try to send to current leader first
        if self.current_leader and self.current_leader in self.all_nodes:
            if self._send_to_node(self.current_leader, transaction, current_timestamp):
                return True
        
        # Try all nodes to find leader
        for node_id in self.all_nodes:
            if self._send_to_node(node_id, transaction, current_timestamp):
                self.current_leader = node_id
                return True
        
        print(f"Client {self.client_id}: Failed to send transaction {transaction}")
        return False
    
    def _send_to_node(self, node_id: str, transaction: Transaction, timestamp: int) -> bool:
        """Send transaction to specific node"""
        try:
            host, port = self.all_nodes[node_id]
            
            # Create client request message
            request = ClientRequestMessage(self.client_id, node_id, transaction, timestamp)
            
            # Send to node
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect((host, port))
            sock.send(request.to_json().encode())
            sock.close()
            
            return True
        except Exception as e:
            print(f"Client {self.client_id} failed to send to {node_id}: {e}")
            return False
    
    def _timeout_handler(self):
        """Handle request timeouts"""
        while self.running:
            current_time = time.time()
            timed_out_requests = []
            
            with self.request_lock:
                for timestamp, (transaction, response_received) in list(self.pending_requests.items()):
                    if not response_received and current_time - timestamp > self.response_timeout:
                        timed_out_requests.append((timestamp, transaction))
            
            # Handle timeouts
            for timestamp, transaction in timed_out_requests:
                print(f"Client {self.client_id}: Transaction {transaction} TIMEOUT")
                with self.request_lock:
                    if timestamp in self.pending_requests:
                        del self.pending_requests[timestamp]
            
            time.sleep(1.0)
    
    def wait_for_response(self, timeout: float = 10.0) -> bool:
        """Wait for pending responses"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            with self.request_lock:
                if not any(not response_received for _, response_received in self.pending_requests.values()):
                    return True
            time.sleep(0.1)
        
        return False


class ClientManager:
    """Manages multiple clients and coordinates transaction sending"""
    
    def __init__(self, all_nodes: Dict[str, Tuple[str, int]]):
        self.all_nodes = all_nodes
        self.clients = {}  # client_id -> Client
        self.client_ports = {}  # client_id -> port
        
    def create_clients(self, client_ids: List[str], start_port: int = 8000):
        """Create and start clients"""
        for i, client_id in enumerate(client_ids):
            port = start_port + i
            client = Client(client_id, self.all_nodes)
            client.start(port)
            
            self.clients[client_id] = client
            self.client_ports[client_id] = port
            
            # Small delay to avoid port conflicts
            time.sleep(0.1)
    
    def stop_all_clients(self):
        """Stop all clients"""
        for client in self.clients.values():
            client.stop()
    
    def send_transactions(self, transactions: List[Transaction], delay: float = 1.0):
        """Send a list of transactions with delays between them"""
        print(f"\nSending {len(transactions)} transactions...")
        
        for i, transaction in enumerate(transactions):
            client = self.clients.get(transaction.sender)
            if client:
                print(f"Transaction {i+1}: {transaction}")
                client.send_transaction(transaction)
                
                # Add delay between transactions
                if i < len(transactions) - 1:
                    time.sleep(delay)
            else:
                print(f"Client {transaction.sender} not found!")
        
        # Wait for all responses
        print("Waiting for responses...")
        time.sleep(5.0)
    
    def send_transactions_batch(self, transactions: List[Transaction]):
        """Send all transactions simultaneously"""
        print(f"\nSending {len(transactions)} transactions in batch...")
        
        threads = []
        for i, transaction in enumerate(transactions):
            client = self.clients.get(transaction.sender)
            if client:
                print(f"Transaction {i+1}: {transaction}")
                thread = threading.Thread(target=client.send_transaction, args=(transaction,))
                threads.append(thread)
                thread.start()
            else:
                print(f"Client {transaction.sender} not found!")
        
        # Wait for all sends to complete
        for thread in threads:
            thread.join()
        
        # Wait for responses
        print("Waiting for responses...")
        time.sleep(5.0)
    
    def get_client(self, client_id: str) -> Optional[Client]:
        """Get client by ID"""
        return self.clients.get(client_id)


def parse_transactions(transaction_str: str) -> List[Transaction]:
    """Parse transaction string from CSV format"""
    transactions = []
    
    # Remove spaces and split by commas outside parentheses
    transaction_str = transaction_str.strip()
    
    # Find all transactions in format (sender,receiver,amount)
    import re
    pattern = r'\(([A-E]),([A-E]),(\d+)\)'
    matches = re.findall(pattern, transaction_str)
    
    for match in matches:
        sender, receiver, amount = match
        transactions.append(Transaction(sender, receiver, int(amount)))
    
    return transactions


# Example usage and testing
if __name__ == "__main__":
    # Test transaction parsing
    test_str = "(A,C,5),(C,E,4),(B,D,2),(E,A,10),(E,C,3)"
    transactions = parse_transactions(test_str)
    
    for t in transactions:
        print(t)
    
    # Test client creation
    nodes = {
        "n1": ("localhost", 5001),
        "n2": ("localhost", 5002),
        "n3": ("localhost", 5003),
        "n4": ("localhost", 5004),
        "n5": ("localhost", 5005)
    }
    
    client_manager = ClientManager(nodes)
    client_manager.create_clients(['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J'])
    
    print("Clients created and started")
    time.sleep(2)
    
    client_manager.stop_all_clients()
    print("Clients stopped")
