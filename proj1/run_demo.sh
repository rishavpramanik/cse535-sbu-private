#!/bin/bash

# Demo script for CSE535 Project 1: Distributed Paxos Banking System

echo "=================================================="
echo "CSE535 Project 1: Distributed Paxos Banking System"
echo "=================================================="

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed."
    exit 1
fi

echo "1. Creating sample CSV test file..."
python3 main.py create_csv demo_input.csv

echo ""
echo "2. Running basic functionality test..."
python3 test_basic.py

echo ""
echo "3. Sample CSV file created: demo_input.csv"
echo "   To run with CSV input: python3 main.py csv demo_input.csv"
echo ""
echo "4. For interactive mode: python3 main.py interactive"
echo ""
echo "Demo completed!"
echo "=================================================="
