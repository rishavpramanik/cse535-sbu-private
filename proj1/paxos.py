"""
Paxos consensus algorithm implementation for the Distributed Banking System.
"""

import time
import threading
from typing import List, Dict, Optional, Set
from messages import *


class PaxosState:
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.view_num = 0
        self.is_leader = False
        self.leader_id = None
        
        # Paxos state
        self.accept_log: List[LogEntry] = []
        self.commit_log: List[LogEntry] = []
        self.executed_log: List[LogEntry] = []
        
        # Current sequence number
        self.current_seq_num = 0
        self.last_executed_seq = -1
        
        # For leader election
        self.prepare_responses: Dict[int, List[str]] = {}  # view_num -> list of node_ids
        self.new_view_messages: List[NewViewMessage] = []
        
        # For normal operation
        self.accepted_responses: Dict[int, Set[str]] = {}  # seq_num -> set of node_ids
        
        # Locks for thread safety
        self.state_lock = threading.RLock()


class PaxosLeader:
    def __init__(self, node):
        self.node = node
        self.state = node.paxos_state
        
    def start_leader_election(self, new_view_num: int):
        """Start leader election by sending PREPARE messages"""
        with self.state.state_lock:
            self.state.view_num = new_view_num
            self.state.prepare_responses[new_view_num] = []
            
        # Send PREPARE to all nodes (including self)
        prepare_msg = PrepareMessage(self.state.node_id, "broadcast", new_view_num)
        self.node.broadcast_message(prepare_msg)
        
        # Set timer for election timeout
        threading.Timer(5.0, self._election_timeout, args=[new_view_num]).start()
    
    def handle_prepare(self, msg: PrepareMessage):
        """Handle incoming PREPARE message"""
        with self.state.state_lock:
            if msg.data['view_num'] > self.state.view_num:
                self.state.view_num = msg.data['view_num']
                self.state.is_leader = False
                self.state.leader_id = None
                
                # Send ACK with accept log
                ack_msg = AckMessage(self.state.node_id, msg.sender_id, 
                                   msg.data['view_num'], self.state.accept_log)
                self.node.send_message(ack_msg)
                return True
        return False
    
    def handle_ack(self, msg: AckMessage):
        """Handle incoming ACK message"""
        view_num = msg.data['view_num']
        
        with self.state.state_lock:
            if view_num != self.state.view_num:
                return False
                
            if view_num not in self.state.prepare_responses:
                return False
                
            # Add to responses
            if msg.sender_id not in self.state.prepare_responses[view_num]:
                self.state.prepare_responses[view_num].append(msg.sender_id)
                
                # Merge accept log
                remote_log = [LogEntry.from_dict(entry) for entry in msg.data['accept_log']]
                self._merge_accept_log(remote_log)
                
                # Check if we have majority
                if len(self.state.prepare_responses[view_num]) >= 3:  # majority of 5
                    self._become_leader(view_num)
                    return True
        return False
    
    def _merge_accept_log(self, remote_log: List[LogEntry]):
        """Merge remote accept log with local log"""
        # Create a map of seq_num -> LogEntry for efficient lookup
        local_map = {entry.seq_num: entry for entry in self.state.accept_log}
        
        for remote_entry in remote_log:
            seq_num = remote_entry.seq_num
            if seq_num not in local_map:
                # Add missing entry
                self.state.accept_log.append(remote_entry)
            else:
                # Keep the one with higher status priority (E > C > A > X)
                local_entry = local_map[seq_num]
                if self._status_priority(remote_entry.status) > self._status_priority(local_entry.status):
                    local_map[seq_num] = remote_entry
        
        # Rebuild accept log from map and sort by seq_num
        self.state.accept_log = sorted(local_map.values(), key=lambda x: x.seq_num)
        
        # Fill gaps with no-ops
        self._fill_gaps_with_noops()
    
    def _status_priority(self, status: str) -> int:
        """Return priority of status for merging logs"""
        priorities = {'E': 4, 'C': 3, 'A': 2, 'X': 1}
        return priorities.get(status, 0)
    
    def _fill_gaps_with_noops(self):
        """Fill gaps in accept log with no-op entries"""
        if not self.state.accept_log:
            return
            
        max_seq = max(entry.seq_num for entry in self.state.accept_log)
        existing_seqs = {entry.seq_num for entry in self.state.accept_log}
        
        for seq_num in range(max_seq + 1):
            if seq_num not in existing_seqs:
                noop_entry = LogEntry(seq_num, None, is_noop=True, status="A")
                self.state.accept_log.append(noop_entry)
        
        # Sort again
        self.state.accept_log.sort(key=lambda x: x.seq_num)
    
    def _become_leader(self, view_num: int):
        """Become leader and send NEW_VIEW messages"""
        self.state.is_leader = True
        self.state.leader_id = self.state.node_id
        
        # Update current sequence number
        if self.state.accept_log:
            self.state.current_seq_num = max(entry.seq_num for entry in self.state.accept_log) + 1
        else:
            self.state.current_seq_num = 0
        
        # Send NEW_VIEW to all nodes
        new_view_msg = NewViewMessage(self.state.node_id, "broadcast", 
                                     view_num, self.state.accept_log)
        self.node.broadcast_message(new_view_msg)
        
        # Store NEW_VIEW message for PrintView
        self.state.new_view_messages.append(new_view_msg)
        
        print(f"Node {self.state.node_id} became leader for view {view_num}")
    
    def _election_timeout(self, view_num: int):
        """Handle election timeout"""
        with self.state.state_lock:
            if (view_num == self.state.view_num and 
                not self.state.is_leader and 
                len(self.state.prepare_responses.get(view_num, [])) < 3):
                # Election failed, try again with higher view number
                print(f"Node {self.state.node_id} election timeout for view {view_num}")
                threading.Timer(2.0, lambda: self.start_leader_election(view_num + 1)).start()
    
    def handle_client_request(self, transaction: Transaction, client_id: str, client_timestamp: int):
        """Handle client transaction request"""
        if not self.state.is_leader:
            return False, "Not the leader"
        
        with self.state.state_lock:
            seq_num = self.state.current_seq_num
            self.state.current_seq_num += 1
            
            # Create log entry
            log_entry = LogEntry(seq_num, transaction, status="A")
            self.state.accept_log.append(log_entry)
            self.state.accepted_responses[seq_num] = set()
            
            # Send ACCEPT to all nodes
            accept_msg = AcceptMessage(self.state.node_id, "broadcast", seq_num, transaction)
            self.node.broadcast_message(accept_msg)
            
            # Store client info for response
            self.node.pending_client_requests[seq_num] = (client_id, client_timestamp)
            
            return True, "Request accepted"
    
    def handle_accepted(self, msg: AcceptedMessage):
        """Handle ACCEPTED message from backup"""
        seq_num = msg.data['seq_num']
        
        with self.state.state_lock:
            if seq_num not in self.state.accepted_responses:
                return False
                
            self.state.accepted_responses[seq_num].add(msg.sender_id)
            
            # Check if we have majority
            if len(self.state.accepted_responses[seq_num]) >= 3:  # majority of 5
                # Send COMMIT
                commit_msg = CommitMessage(self.state.node_id, "broadcast", seq_num)
                self.node.broadcast_message(commit_msg)
                
                # Update local state
                self._update_log_status(seq_num, "C")
                
                return True
        return False
    
    def _update_log_status(self, seq_num: int, status: str):
        """Update status of log entry"""
        for entry in self.state.accept_log:
            if entry.seq_num == seq_num:
                entry.status = status
                break


class PaxosBackup:
    def __init__(self, node):
        self.node = node
        self.state = node.paxos_state
    
    def handle_new_view(self, msg: NewViewMessage):
        """Handle NEW_VIEW message from new leader"""
        view_num = msg.data['view_num']
        
        with self.state.state_lock:
            if view_num >= self.state.view_num:
                self.state.view_num = view_num
                self.state.is_leader = False
                self.state.leader_id = msg.sender_id
                
                # Update accept log
                new_log = [LogEntry.from_dict(entry) for entry in msg.data['accept_log']]
                self.state.accept_log = new_log
                
                # Store NEW_VIEW message for PrintView
                self.state.new_view_messages.append(msg)
                
                print(f"Node {self.state.node_id} accepted new leader {msg.sender_id} for view {view_num}")
                return True
        return False
    
    def handle_accept(self, msg: AcceptMessage):
        """Handle ACCEPT message from leader"""
        if msg.sender_id != self.state.leader_id:
            return False
            
        seq_num = msg.data['seq_num']
        transaction = Transaction.from_dict(msg.data['transaction'])
        
        with self.state.state_lock:
            # Add to accept log
            log_entry = LogEntry(seq_num, transaction, status="A")
            
            # Find if entry already exists
            existing_entry = None
            for i, entry in enumerate(self.state.accept_log):
                if entry.seq_num == seq_num:
                    existing_entry = i
                    break
            
            if existing_entry is not None:
                self.state.accept_log[existing_entry] = log_entry
            else:
                self.state.accept_log.append(log_entry)
                self.state.accept_log.sort(key=lambda x: x.seq_num)
            
            # Send ACCEPTED back to leader
            accepted_msg = AcceptedMessage(self.state.node_id, msg.sender_id, seq_num)
            self.node.send_message(accepted_msg)
            
            return True
    
    def handle_commit(self, msg: CommitMessage):
        """Handle COMMIT message from leader"""
        if msg.sender_id != self.state.leader_id:
            return False
            
        seq_num = msg.data['seq_num']
        
        with self.state.state_lock:
            # Update status to committed
            for entry in self.state.accept_log:
                if entry.seq_num == seq_num:
                    entry.status = "C"
                    break
            
            return True
