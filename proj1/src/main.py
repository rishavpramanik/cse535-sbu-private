"""
Main orchestration for the Distributed Paxos Banking System.
Handles CSV input processing, node management, and testing.
"""

import csv
import time
import threading
import sys
import signal
from typing import Dict, List, Tuple, Set
from node import Node
from client import ClientManager, parse_transactions
from messages import Transaction


class BankingSystem:
    def __init__(self):
        self.nodes = {}  # node_id -> Node
        self.client_manager = None
        self.all_nodes_config = {
            "n1": ("localhost", 5001),
            "n2": ("localhost", 5002),
            "n3": ("localhost", 5003),
            "n4": ("localhost", 5004),
            "n5": ("localhost", 5005)
        }
        self.live_nodes = set(self.all_nodes_config.keys())
        
    def initialize_system(self):
        """Initialize all nodes and clients"""
        print("Initializing Distributed Paxos Banking System...")
        
        # Create client manager and clients first (10 clients as per specification)
        self.client_manager = ClientManager(self.all_nodes_config)
        self.client_manager.create_clients(['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J'])
        
        # Create and start all nodes with client port information
        for node_id, (host, port) in self.all_nodes_config.items():
            node = Node(node_id, port, self.all_nodes_config, self.client_manager.client_ports)
            self.nodes[node_id] = node
            node.start()
            time.sleep(0.5)  # Small delay between node starts
        
        print("System initialized. Waiting for leader election...")
        time.sleep(3)  # Wait for initial leader election
        
    def shutdown_system(self):
        """Shutdown all nodes and clients"""
        print("Shutting down system...")
        
        # Stop clients first
        if self.client_manager:
            self.client_manager.stop_all_clients()
        
        # Stop all nodes
        for node_id, node in self.nodes.items():
            if node:
                node.stop()
        
        # Give everything time to shut down
        time.sleep(0.5)
        
        print("System shutdown complete.")
    
    def process_csv_file(self, filename: str):
        """Process CSV input file with test sets"""
        try:
            with open(filename, 'r') as file:
                reader = csv.DictReader(file)
                
                for row in reader:
                    set_number = int(row['SetNumber'])
                    transactions_str = row['Transactions']
                    live_nodes_str = row['LiveNodes']
                    
                    print(f"\n{'='*50}")
                    print(f"Processing Set {set_number}")
                    print(f"{'='*50}")
                    
                    # Parse transactions
                    transactions = parse_transactions(transactions_str)
                    
                    # Parse live nodes
                    live_nodes = self._parse_live_nodes(live_nodes_str)
                    
                    # Update live nodes
                    self._update_live_nodes(live_nodes)
                    
                    # Process transactions
                    self._process_transaction_set(transactions)
                    
                    # Allow time for processing
                    time.sleep(2)
                    
                    # Print system state
                    self._print_system_state()
                    
                    # Pause between sets
                    print(f"\nSet {set_number} complete. Press Enter to continue...")
                    input()
                    
        except FileNotFoundError:
            print(f"Error: File {filename} not found")
        except Exception as e:
            print(f"Error processing CSV file: {e}")
    
    def _parse_live_nodes(self, live_nodes_str: str) -> Set[str]:
        """Parse live nodes string from CSV"""
        # Remove brackets and split by comma
        live_nodes_str = live_nodes_str.strip('[]')
        live_nodes = [node.strip() for node in live_nodes_str.split(',')]
        return set(live_nodes)
    
    def _update_live_nodes(self, live_nodes: Set[str]):
        """Update which nodes are live"""
        # Nodes to fail
        nodes_to_fail = self.live_nodes - live_nodes
        # Nodes to recover
        nodes_to_recover = live_nodes - self.live_nodes
        
        # Simulate failures
        for node_id in nodes_to_fail:
            if node_id in self.nodes:
                print(f"Simulating failure of {node_id}")
                self.nodes[node_id].simulate_failure()
        
        # Simulate recoveries
        for node_id in nodes_to_recover:
            if node_id in self.nodes:
                print(f"Recovering {node_id}")
                self.nodes[node_id].recover()
                time.sleep(1)  # Allow time for recovery
        
        self.live_nodes = live_nodes
        
        # Update alive nodes in all running nodes
        for node_id, node in self.nodes.items():
            if node.running:
                node.alive_nodes = live_nodes.copy()
    
    def _process_transaction_set(self, transactions: List[Transaction]):
        """Process a set of transactions"""
        print(f"Processing {len(transactions)} transactions:")
        for i, transaction in enumerate(transactions):
            print(f"  {i+1}. {transaction}")
        
        # Send transactions with delays
        self.client_manager.send_transactions(transactions, delay=1.0)
    
    def _print_system_state(self):
        """Print current system state"""
        print(f"\n{'='*30} SYSTEM STATE {'='*30}")
        
        # Print databases
        for node_id in sorted(self.live_nodes):
            if node_id in self.nodes and self.nodes[node_id].running:
                self.nodes[node_id].print_db()
        
        # Print leader info
        leader_node = self._get_current_leader()
        if leader_node:
            print(f"\nCurrent Leader: {leader_node.node_id}")
        else:
            print("\nNo current leader detected")
        
        print(f"{'='*75}")
    
    def _get_current_leader(self) -> Node:
        """Get current leader node"""
        for node in self.nodes.values():
            if node.running and node.paxos_state.is_leader:
                return node
        return None
    
    def interactive_mode(self):
        """Interactive mode for testing"""
        print("\n" + "="*50)
        print("INTERACTIVE MODE")
        print("="*50)
        print("Commands:")
        print("  tx <sender> <receiver> <amount> - Send transaction")
        print("  fail <node_id> - Simulate node failure")
        print("  recover <node_id> - Recover failed node")
        print("  status <seq_num> - Print status of sequence number")
        print("  log <node_id> - Print log of node")
        print("  db <node_id> - Print database of node")
        print("  view <node_id> - Print view messages of node")
        print("  leader - Show current leader")
        print("  quit - Exit interactive mode")
        print()
        
        while True:
            try:
                command = input(">>> ").strip().split()
                if not command:
                    continue
                
                cmd = command[0].lower()
                
                if cmd == "quit":
                    break
                elif cmd == "tx" and len(command) == 4:
                    sender, receiver, amount = command[1], command[2], int(command[3])
                    transaction = Transaction(sender, receiver, amount)
                    client = self.client_manager.get_client(sender)
                    if client:
                        client.send_transaction(transaction)
                    else:
                        print(f"Client {sender} not found")
                
                elif cmd == "fail" and len(command) == 2:
                    node_id = command[1]
                    if node_id in self.nodes:
                        self.nodes[node_id].simulate_failure()
                        self.live_nodes.discard(node_id)
                        print(f"Node {node_id} failed")
                    else:
                        print(f"Node {node_id} not found")
                
                elif cmd == "recover" and len(command) == 2:
                    node_id = command[1]
                    if node_id in self.nodes:
                        self.nodes[node_id].recover()
                        self.live_nodes.add(node_id)
                        print(f"Node {node_id} recovered")
                    else:
                        print(f"Node {node_id} not found")
                
                elif cmd == "status" and len(command) == 2:
                    seq_num = int(command[1])
                    for node_id in sorted(self.live_nodes):
                        if node_id in self.nodes and self.nodes[node_id].running:
                            self.nodes[node_id].print_status(seq_num)
                
                elif cmd == "log" and len(command) == 2:
                    node_id = command[1]
                    if node_id in self.nodes and self.nodes[node_id].running:
                        self.nodes[node_id].print_log()
                    else:
                        print(f"Node {node_id} not running")
                
                elif cmd == "db" and len(command) == 2:
                    node_id = command[1]
                    if node_id in self.nodes and self.nodes[node_id].running:
                        self.nodes[node_id].print_db()
                    else:
                        print(f"Node {node_id} not running")
                
                elif cmd == "view" and len(command) == 2:
                    node_id = command[1]
                    if node_id in self.nodes and self.nodes[node_id].running:
                        self.nodes[node_id].print_view()
                    else:
                        print(f"Node {node_id} not running")
                
                elif cmd == "leader":
                    leader = self._get_current_leader()
                    if leader:
                        print(f"Current leader: {leader.node_id}")
                    else:
                        print("No current leader")
                
                else:
                    print("Invalid command")
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")
    
    def create_sample_csv(self, filename: str = "test_input.csv"):
        """Create sample CSV file for testing"""
        with open(filename, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['SetNumber', 'Transactions', 'LiveNodes'])
            # Use all 10 clients (A-J) in sample transactions
            writer.writerow([1, '(A,C,5),(C,E,4),(B,D,2),(E,A,10),(F,G,3),(H,I,1),(J,F,2)', '[n1,n2,n3,n4,n5]'])
            writer.writerow([2, '(G,H,6),(I,J,8),(A,F,4)', '[n1,n3,n5]'])
            writer.writerow([3, '(J,A,3),(B,I,5),(D,H,7)', '[n2,n3,n4,n5]'])
        
        print(f"Sample CSV file '{filename}' created with 10-client support")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python main.py csv <filename>    - Process CSV file")
        print("  python main.py interactive       - Interactive mode")
        print("  python main.py create_csv        - Create sample CSV")
        return
    
    mode = sys.argv[1].lower()
    
    system = BankingSystem()
    
    # Set up signal handler for clean shutdown
    def signal_handler(sig, frame):
        print("\nReceived interrupt signal, shutting down...")
        system.shutdown_system()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        if mode == "csv":
            if len(sys.argv) < 3:
                print("Please provide CSV filename")
                return
            
            filename = sys.argv[2]
            system.initialize_system()
            system.process_csv_file(filename)
            
        elif mode == "interactive":
            system.initialize_system()
            system.interactive_mode()
            
        elif mode == "create_csv":
            filename = sys.argv[2] if len(sys.argv) > 2 else "test_input.csv"
            system.create_sample_csv(filename)
            return
            
        else:
            print("Invalid mode. Use 'csv', 'interactive', or 'create_csv'")
            return
            
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        system.shutdown_system()


if __name__ == "__main__":
    main()
