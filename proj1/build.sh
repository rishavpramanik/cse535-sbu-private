#!/bin/bash

# Makefile-style script for the Distributed Paxos Banking System

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function definitions
help() {
    echo "Distributed Paxos Banking System - Build Script"
    echo ""
    echo "Usage: ./build.sh [command]"
    echo ""
    echo "Commands:"
    echo "  help          Show this help message"
    echo "  test          Run all tests (unit + integration)"
    echo "  test-unit     Run only unit tests"
    echo "  test-integration  Run only integration tests"
    echo "  test-basic    Run basic functionality test"
    echo "  demo          Run interactive demo"
    echo "  csv           Run with sample CSV input"
    echo "  create-csv    Create sample CSV file"
    echo "  clean         Clean up temporary files"
    echo "  validate      Validate system components"
    echo "  lint          Check code style (if available)"
    echo ""
    echo "Examples:"
    echo "  ./build.sh test           # Run all tests"
    echo "  ./build.sh demo           # Start interactive demo"
    echo "  ./build.sh csv test_input.csv  # Run with CSV file"
}

validate() {
    print_status "Validating system components..."
    
    # Check Python version
    python_version=$(python3 --version 2>&1)
    print_status "Python version: $python_version"
    
    # Check if all required files exist
    required_files=("main.py" "node.py" "client.py" "paxos.py" "messages.py")
    for file in "${required_files[@]}"; do
        if [ ! -f "$file" ]; then
            print_error "Required file missing: $file"
            exit 1
        fi
    done
    print_success "All required files present"
    
    # Test basic imports
    if python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from messages import Transaction, MessageType
    from paxos import PaxosState
    from node import Node
    from client import Client
    from main import BankingSystem
    print('✅ All imports successful')
except ImportError as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)
"; then
        print_success "Component validation passed"
    else
        print_error "Component validation failed"
        exit 1
    fi
}

test_unit() {
    print_status "Running unit tests..."
    if [ -f "test_unit.py" ]; then
        python3 test_unit.py
    else
        print_error "Unit test file not found"
        exit 1
    fi
}

test_integration() {
    print_status "Running integration tests..."
    if [ -f "test_integration.py" ]; then
        python3 test_integration.py
    else
        print_error "Integration test file not found"
        exit 1
    fi
}

test_basic() {
    print_status "Running basic functionality test..."
    if [ -f "test_basic.py" ]; then
        python3 test_basic.py
    else
        print_error "Basic test file not found"
        exit 1
    fi
}

test_all() {
    print_status "Running comprehensive test suite..."
    if [ -f "run_tests.py" ]; then
        python3 run_tests.py
    else
        print_warning "Comprehensive test runner not found, running individual tests..."
        validate
        test_unit
        test_integration
    fi
}

demo() {
    print_status "Starting interactive demo..."
    validate
    print_status "Use 'quit' to exit the interactive mode"
    python3 main.py interactive
}

csv_demo() {
    local csv_file=${1:-"test_input.csv"}
    print_status "Running CSV demo with file: $csv_file"
    
    if [ ! -f "$csv_file" ]; then
        print_warning "CSV file $csv_file not found, creating sample..."
        create_csv "$csv_file"
    fi
    
    validate
    python3 main.py csv "$csv_file"
}

create_csv() {
    local filename=${1:-"test_input.csv"}
    print_status "Creating sample CSV file: $filename"
    python3 main.py create_csv "$filename"
    print_success "Sample CSV file created: $filename"
}

clean() {
    print_status "Cleaning up temporary files..."
    
    # Remove Python cache
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyc" -delete 2>/dev/null || true
    
    # Remove temporary test files
    rm -f test_output_*.csv 2>/dev/null || true
    rm -f demo_input.csv 2>/dev/null || true
    
    print_success "Cleanup completed"
}

lint() {
    print_status "Checking code style..."
    
    # Check if flake8 is available
    if command -v flake8 &> /dev/null; then
        print_status "Running flake8..."
        flake8 --max-line-length=100 --ignore=E501,W503 *.py || true
    elif command -v pylint &> /dev/null; then
        print_status "Running pylint..."
        pylint --disable=C0103,C0114,C0115,C0116 *.py || true
    else
        print_warning "No linting tools available (flake8, pylint)"
        print_status "Install with: pip install flake8 pylint"
    fi
}

# Main script logic
case "${1:-help}" in
    help|--help|-h)
        help
        ;;
    validate)
        validate
        ;;
    test)
        test_all
        ;;
    test-unit)
        test_unit
        ;;
    test-integration)
        test_integration
        ;;
    test-basic)
        test_basic
        ;;
    demo)
        demo
        ;;
    csv)
        csv_demo "$2"
        ;;
    create-csv)
        create_csv "$2"
        ;;
    clean)
        clean
        ;;
    lint)
        lint
        ;;
    *)
        print_error "Unknown command: $1"
        echo ""
        help
        exit 1
        ;;
esac
