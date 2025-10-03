# CSE535 Project 1: Distributed Paxos Banking System

A distributed banking system implementing the Stable-Leader Paxos consensus algorithm with 5 nodes and 10 clients.

## Architecture

- **5 Nodes**: Independent processes implementing Paxos consensus
- **10 Clients**: Separate processes sending transaction requests
- **Communication**: TCP sockets for inter-node and client-node communication
- **Fault Tolerance**: Tolerates up to 2 node failures (f=2)

## Features

### Banking Application
- Each client starts with balance = 10
- Transactions: `(sender, receiver, amount)`
- Clients send requests to leader node
- Responses: success/failure with insufficient funds handling

### Consensus (Stable-Leader Paxos)
- **Leader Election Phase**: PREPARE/ACK/NEW-VIEW with AcceptLog
- **Normal Operation**: REQUEST/ACCEPT/ACCEPTED/COMMIT cycle
- **Failure Handling**: Leader crash detection and new election
- **Recovery**: Catch-up mechanism for recovering nodes

### Print Functions
- `PrintLog(node)`: All messages handled by node
- `PrintDB(node)`: Current client balances
- `PrintStatus(seqNum)`: Status of sequence number (A/C/E/X)
- `PrintView()`: All NEW-VIEW messages exchanged

## File Structure

```
proj1/
├── main.py           # Main orchestration and CSV processing
├── node.py           # Node implementation (leader + backup)
├── client.py         # Client implementation and management
├── paxos.py          # Paxos consensus algorithms
├── messages.py       # Message classes and formats
├── test_input.csv    # Sample test data
└── README.md         # This file
```

## Usage

### 1. Create Sample CSV File
```bash
python main.py create_csv [filename]
```

### 2. Process CSV Test File
```bash
python main.py csv test_input.csv
```

### 3. Interactive Mode
```bash
python main.py interactive
```

#### Interactive Commands:
- `tx <sender> <receiver> <amount>` - Send transaction
- `fail <node_id>` - Simulate node failure
- `recover <node_id>` - Recover failed node
- `status <seq_num>` - Print status of sequence number
- `log <node_id>` - Print message log of node
- `db <node_id>` - Print database (balances) of node
- `view <node_id>` - Print NEW-VIEW messages of node
- `leader` - Show current leader
- `quit` - Exit interactive mode

## CSV Input Format

```csv
SetNumber,Transactions,LiveNodes
1,"(A,C,5),(C,E,4),(B,D,2)","[n1,n2,n3,n4,n5]"
2,"(A,E,4),(C,A,1)","[n1,n3,n5]"
```

- **SetNumber**: Test set identifier
- **Transactions**: Comma-separated transactions in format (sender,receiver,amount)
- **LiveNodes**: List of nodes that should be alive for this test set

## Implementation Details

### Node Communication
- Each node runs on ports 5001-5005
- Clients run on ports 8000-8004
- TCP sockets with JSON message serialization
- Heartbeat-based failure detection

### Paxos Algorithm
1. **Leader Election**:
   - PREPARE messages with view numbers
   - ACK responses with accept logs
   - NEW-VIEW messages with merged logs
   - Missing slots filled with no-ops

2. **Normal Operation**:
   - Client REQUEST to leader
   - Leader sends ACCEPT to all nodes
   - Nodes respond with ACCEPTED
   - Leader sends COMMIT after majority
   - Nodes execute in sequence order

3. **Failure Recovery**:
   - Heartbeat monitoring (2s interval, 6s timeout)
   - Leader failure triggers new election
   - Recovering nodes request catch-up
   - Log merging with status priorities

### Transaction Execution
- Transactions executed only when all lower sequence numbers are committed
- Atomic balance updates with insufficient funds checking
- Client responses sent after execution

## Testing

The system includes a comprehensive test suite with **45 tests** covering all aspects:

### Test Categories

1. **Unit Tests (32 tests)**:
   - Message serialization/deserialization
   - Paxos state management
   - Leader and backup functionality
   - Transaction parsing
   - Node initialization
   - Client management
   - Log merging algorithms

2. **Integration Tests (13 tests)**:
   - Leader election scenarios
   - Failure detection and recovery
   - Transaction execution ordering
   - End-to-end workflows
   - CSV processing

### Running Tests

```bash
# Run all tests
./build.sh test
# or
python3 run_tests.py

# Run specific test categories
./build.sh test-unit
./build.sh test-integration
./build.sh test-basic

# Run with build script
./build.sh validate    # Component validation
./build.sh lint        # Code style checking
```

### Test Results
- **Total Tests**: 45
- **Success Rate**: 100% ✅
- **Coverage**: All major components and failure scenarios

The system includes comprehensive testing with:
- Multiple transaction sets
- Node failures and recoveries
- Leader election scenarios
- Concurrent client requests
- Print function verification

## Requirements

- Python 3.7+
- No external dependencies (uses only standard library)

## Example Run

```bash
# Create sample data
python main.py create_csv

# Run test
python main.py csv test_input.csv

# Interactive testing
python main.py interactive
>>> tx A C 5
>>> fail n1
>>> recover n1
>>> leader
>>> quit
```
