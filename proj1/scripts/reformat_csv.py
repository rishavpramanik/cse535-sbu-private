#!/usr/bin/env python3
"""
Script to reformat the CSE535 test cases CSV file into the format expected by our system.
"""

import csv
import re

def parse_csv_file(input_file, output_file):
    """Parse and reformat the CSV file"""
    
    # Read the input CSV
    with open(input_file, 'r') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    # Skip header
    rows = rows[1:]
    
    # Parse into test sets
    test_sets = []
    current_set = None
    current_transactions = []
    current_live_nodes = None
    
    for row in rows:
        if not row or len(row) < 2:
            continue
            
        set_num = row[0].strip()
        transaction = row[1].strip()
        live_nodes = row[2].strip() if len(row) > 2 else ""
        
        # If we have a set number, start a new set
        if set_num and set_num.isdigit():
            # Save previous set if it exists
            if current_set is not None:
                test_sets.append({
                    'set_num': current_set,
                    'transactions': current_transactions.copy(),
                    'live_nodes': current_live_nodes
                })
            
            # Start new set
            current_set = int(set_num)
            current_transactions = []
            current_live_nodes = live_nodes
            
            # Add the transaction from this row if it exists
            if transaction and transaction != 'LF':
                current_transactions.append(transaction)
                
        else:
            # This is a continuation row
            if transaction and transaction != 'LF':
                current_transactions.append(transaction)
    
    # Don't forget the last set
    if current_set is not None:
        test_sets.append({
            'set_num': current_set,
            'transactions': current_transactions.copy(),
            'live_nodes': current_live_nodes
        })
    
    # Convert client names from A-J to A-E (map J->E, I->D, H->C, G->B, F->A)
    client_mapping = {
        'J': 'E', 'I': 'D', 'H': 'C', 'G': 'B', 'F': 'A'
    }
    
    def map_transaction(transaction):
        """Map transaction clients from A-J to A-E"""
        # Extract sender, receiver, amount using regex
        match = re.match(r'\(([A-J])\s*,\s*([A-J])\s*,\s*(\d+)\)', transaction)
        if match:
            sender, receiver, amount = match.groups()
            
            # Map to A-E range
            mapped_sender = client_mapping.get(sender, sender)
            mapped_receiver = client_mapping.get(receiver, receiver)
            
            # Skip transactions where sender == receiver (invalid)
            if mapped_sender == mapped_receiver:
                return None
            
            return f"({mapped_sender},{mapped_receiver},{amount})"
        return None
    
    # Write the reformatted CSV
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['SetNumber', 'Transactions', 'LiveNodes'])
        
        for test_set in test_sets:
            # Map all transactions and filter out invalid ones
            mapped_transactions = []
            for t in test_set['transactions']:
                mapped = map_transaction(t)
                if mapped:  # Only add valid transactions
                    mapped_transactions.append(mapped)
            
            # Skip sets with no valid transactions
            if not mapped_transactions:
                continue
            
            # Limit very long sets (like set 10)
            if len(mapped_transactions) > 20:
                mapped_transactions = mapped_transactions[:10]  # Take first 10
                
            # Join transactions with commas
            transactions_str = ','.join(mapped_transactions)
            
            # Clean up live nodes format
            live_nodes = test_set['live_nodes']
            if live_nodes and not live_nodes.startswith('['):
                # Convert to proper format
                nodes = live_nodes.split(',')
                live_nodes = '[' + ','.join(node.strip() for node in nodes) + ']'
            
            writer.writerow([
                test_set['set_num'],
                transactions_str,
                live_nodes
            ])
    
    print(f"Reformatted {len(test_sets)} test sets")
    
    # Print summary
    for test_set in test_sets[:5]:  # Show first 5 sets
        print(f"Set {test_set['set_num']}: {len(test_set['transactions'])} transactions, nodes: {test_set['live_nodes']}")

if __name__ == "__main__":
    input_file = "/home/stufs1/rpramanik/usels/535/proj1/CSE535-F25-Project-1-Testcases.csv"
    output_file = "/home/stufs1/rpramanik/usels/535/proj1/CSE535-F25-Project-1-Testcases-Reformatted.csv"
    
    parse_csv_file(input_file, output_file)
    print(f"Reformatted CSV saved to: {output_file}")
