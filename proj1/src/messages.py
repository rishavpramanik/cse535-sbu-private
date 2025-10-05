"""
Message classes and formats for the Distributed Paxos Banking System.
"""

from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import json


class MessageType(Enum):
    # Leader Election Phase
    PREPARE = "PREPARE"
    ACK = "ACK"
    NEW_VIEW = "NEW_VIEW"
    
    # Normal Operation Phase
    REQUEST = "REQUEST"
    ACCEPT = "ACCEPT"
    ACCEPTED = "ACCEPTED"
    COMMIT = "COMMIT"
    
    # Client Communication
    CLIENT_REQUEST = "CLIENT_REQUEST"
    CLIENT_RESPONSE = "CLIENT_RESPONSE"
    
    # Failure Handling
    HEARTBEAT = "HEARTBEAT"
    HEARTBEAT_ACK = "HEARTBEAT_ACK"
    
    # Recovery
    CATCH_UP_REQUEST = "CATCH_UP_REQUEST"
    CATCH_UP_RESPONSE = "CATCH_UP_RESPONSE"


@dataclass
class Transaction:
    sender: str
    receiver: str
    amount: int
    
    def __str__(self):
        return f"({self.sender},{self.receiver},{self.amount})"
    
    def to_dict(self):
        return {"sender": self.sender, "receiver": self.receiver, "amount": self.amount}
    
    @classmethod
    def from_dict(cls, data):
        return cls(data["sender"], data["receiver"], data["amount"])


@dataclass
class LogEntry:
    seq_num: int
    transaction: Optional[Transaction]
    is_noop: bool = False
    status: str = "X"  # X (None), A (Accepted), C (Committed), E (Executed)
    
    def to_dict(self):
        return {
            "seq_num": self.seq_num,
            "transaction": self.transaction.to_dict() if self.transaction else None,
            "is_noop": self.is_noop,
            "status": self.status
        }
    
    @classmethod
    def from_dict(cls, data):
        transaction = Transaction.from_dict(data["transaction"]) if data["transaction"] else None
        return cls(data["seq_num"], transaction, data["is_noop"], data["status"])


class Message:
    def __init__(self, msg_type: MessageType, sender_id: str, receiver_id: str, **kwargs):
        self.msg_type = msg_type
        self.sender_id = sender_id
        self.receiver_id = receiver_id
        self.timestamp = kwargs.get('timestamp', 0)
        self.data = kwargs
    
    def to_json(self):
        data = {
            'msg_type': self.msg_type.value,
            'sender_id': self.sender_id,
            'receiver_id': self.receiver_id,
            'timestamp': self.timestamp,
            'data': self.data
        }
        return json.dumps(data, default=str)
    
    @classmethod
    def from_json(cls, json_str):
        data = json.loads(json_str)
        msg_type = MessageType(data['msg_type'])
        return cls(msg_type, data['sender_id'], data['receiver_id'], **data['data'])


class PrepareMessage(Message):
    def __init__(self, sender_id: str, receiver_id: str, view_num: int):
        super().__init__(MessageType.PREPARE, sender_id, receiver_id, view_num=view_num)


class AckMessage(Message):
    def __init__(self, sender_id: str, receiver_id: str, view_num: int, accept_log: List[LogEntry]):
        accept_log_data = [entry.to_dict() for entry in accept_log]
        super().__init__(MessageType.ACK, sender_id, receiver_id, 
                        view_num=view_num, accept_log=accept_log_data)


class NewViewMessage(Message):
    def __init__(self, sender_id: str, receiver_id: str, view_num: int, accept_log: List[LogEntry]):
        accept_log_data = [entry.to_dict() for entry in accept_log]
        super().__init__(MessageType.NEW_VIEW, sender_id, receiver_id,
                        view_num=view_num, accept_log=accept_log_data)


class RequestMessage(Message):
    def __init__(self, sender_id: str, receiver_id: str, seq_num: int, transaction: Transaction):
        super().__init__(MessageType.REQUEST, sender_id, receiver_id,
                        seq_num=seq_num, transaction=transaction.to_dict())


class AcceptMessage(Message):
    def __init__(self, sender_id: str, receiver_id: str, seq_num: int, transaction: Transaction):
        super().__init__(MessageType.ACCEPT, sender_id, receiver_id,
                        seq_num=seq_num, transaction=transaction.to_dict())


class AcceptedMessage(Message):
    def __init__(self, sender_id: str, receiver_id: str, seq_num: int):
        super().__init__(MessageType.ACCEPTED, sender_id, receiver_id, seq_num=seq_num)


class CommitMessage(Message):
    def __init__(self, sender_id: str, receiver_id: str, seq_num: int):
        super().__init__(MessageType.COMMIT, sender_id, receiver_id, seq_num=seq_num)


class ClientRequestMessage(Message):
    """Client request message in format ⟨REQUEST,t,τ,c⟩ where:
    - t: transaction (sender, receiver, amount)
    - τ: timestamp for exactly-once semantics
    - c: client identifier
    """
    def __init__(self, sender_id: str, receiver_id: str, transaction: Transaction, client_timestamp: int):
        super().__init__(MessageType.CLIENT_REQUEST, sender_id, receiver_id,
                        transaction=transaction.to_dict(), client_timestamp=client_timestamp)
    
    def __str__(self):
        """String representation following specification format"""
        t = self.data['transaction']
        τ = self.data['client_timestamp']
        c = self.sender_id
        return f"⟨REQUEST,({t['sender']},{t['receiver']},{t['amount']}),{τ},{c}⟩"


class ClientResponseMessage(Message):
    """Client response message in format ⟨REPLY,b,τ,c,r⟩ where:
    - b: ballot number (current leader's view)
    - τ: timestamp from original request
    - c: client identifier
    - r: result (success/failed)
    """
    def __init__(self, sender_id: str, receiver_id: str, success: bool, message: str, client_timestamp: int):
        super().__init__(MessageType.CLIENT_RESPONSE, sender_id, receiver_id,
                        success=success, message=message, client_timestamp=client_timestamp)
    
    def __str__(self):
        """String representation following specification format"""
        b = "current_ballot"  # Would need actual ballot number from context
        τ = self.data['client_timestamp']
        c = self.receiver_id
        r = "success" if self.data['success'] else "failed"
        return f"⟨REPLY,{b},{τ},{c},{r}⟩"


class HeartbeatMessage(Message):
    def __init__(self, sender_id: str, receiver_id: str):
        super().__init__(MessageType.HEARTBEAT, sender_id, receiver_id)


class HeartbeatAckMessage(Message):
    def __init__(self, sender_id: str, receiver_id: str):
        super().__init__(MessageType.HEARTBEAT_ACK, sender_id, receiver_id)


class CatchUpRequestMessage(Message):
    def __init__(self, sender_id: str, receiver_id: str, last_seq_num: int):
        super().__init__(MessageType.CATCH_UP_REQUEST, sender_id, receiver_id, last_seq_num=last_seq_num)


class CatchUpResponseMessage(Message):
    def __init__(self, sender_id: str, receiver_id: str, log_entries: List[LogEntry]):
        log_data = [entry.to_dict() for entry in log_entries]
        super().__init__(MessageType.CATCH_UP_RESPONSE, sender_id, receiver_id, log_entries=log_data)
