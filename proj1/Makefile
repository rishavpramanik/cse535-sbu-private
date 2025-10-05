# Makefile for CSE535 Project 1: Distributed Paxos Banking System
# Author: CSE535 Student
# Description: Build automation for distributed banking system with Paxos consensus

# Python interpreter
PYTHON := python3

# Directories
SRC_DIR := src
TEST_DIR := tests
SCRIPT_DIR := scripts
DOC_DIR := docs

# Main files
MAIN_MODULE := $(SRC_DIR)/main.py
TEST_RUNNER := $(SCRIPT_DIR)/run_tests.py
DEMO_SCRIPT := $(SCRIPT_DIR)/run_demo.sh
BUILD_SCRIPT := $(SCRIPT_DIR)/build.sh

# Test files
UNIT_TESTS := $(TEST_DIR)/test_unit.py
INTEGRATION_TESTS := $(TEST_DIR)/test_integration.py
BASIC_TESTS := $(TEST_DIR)/test_basic.py

# Data files
SAMPLE_CSV := test_input.csv

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[1;33m
BLUE := \033[0;34m
NC := \033[0m # No Color

# Default target
.PHONY: help
help:
	@echo "$(BLUE)CSE535 Project 1: Distributed Paxos Banking System$(NC)"
	@echo "$(BLUE)=================================================$(NC)"
	@echo ""
	@echo "Available targets:"
	@echo "  $(GREEN)help$(NC)          - Show this help message"
	@echo "  $(GREEN)validate$(NC)      - Validate system components"
	@echo "  $(GREEN)test$(NC)          - Run all tests (unit + integration)"
	@echo "  $(GREEN)test-unit$(NC)     - Run unit tests only"
	@echo "  $(GREEN)test-integration$(NC) - Run integration tests only"
	@echo "  $(GREEN)test-basic$(NC)    - Run basic functionality test"
	@echo "  $(GREEN)demo$(NC)          - Run interactive demo"
	@echo "  $(GREEN)csv$(NC)           - Run with sample CSV input"
	@echo "  $(GREEN)create-csv$(NC)    - Create sample CSV file"
	@echo "  $(GREEN)reformat-csv$(NC)  - Reformat external CSV to our format"
	@echo "  $(GREEN)clean$(NC)         - Clean up temporary files"
	@echo "  $(GREEN)lint$(NC)          - Check code style (if available)"
	@echo "  $(GREEN)install$(NC)       - Install dependencies (none required)"
	@echo "  $(GREEN)build$(NC)         - Build/validate the entire project"
	@echo "  $(GREEN)run$(NC)           - Run the system interactively"
	@echo ""
	@echo "Examples:"
	@echo "  make test         # Run all tests"
	@echo "  make demo         # Start interactive demo"
	@echo "  make csv FILE=my_input.csv  # Run with custom CSV"

# Validate system components
.PHONY: validate
validate:
	@echo "$(BLUE)[INFO]$(NC) Validating system components..."
	@$(PYTHON) --version
	@echo "$(BLUE)[INFO]$(NC) Checking required files..."
	@test -f $(MAIN_MODULE) || (echo "$(RED)[ERROR]$(NC) Main module not found" && exit 1)
	@test -f $(SRC_DIR)/node.py || (echo "$(RED)[ERROR]$(NC) Node module not found" && exit 1)
	@test -f $(SRC_DIR)/client.py || (echo "$(RED)[ERROR]$(NC) Client module not found" && exit 1)
	@test -f $(SRC_DIR)/paxos.py || (echo "$(RED)[ERROR]$(NC) Paxos module not found" && exit 1)
	@test -f $(SRC_DIR)/messages.py || (echo "$(RED)[ERROR]$(NC) Messages module not found" && exit 1)
	@echo "$(BLUE)[INFO]$(NC) Testing basic imports..."
	@cd $(SRC_DIR) && $(PYTHON) -c "from main import BankingSystem; from node import Node; from client import Client; print('✅ All imports successful')"
	@echo "$(GREEN)[SUCCESS]$(NC) System validation passed"

# Run all tests
.PHONY: test
test: validate
	@echo "$(BLUE)[INFO]$(NC) Running comprehensive test suite..."
	@PYTHONPATH=$(SRC_DIR) $(PYTHON) $(TEST_RUNNER)

# Run unit tests only
.PHONY: test-unit
test-unit: validate
	@echo "$(BLUE)[INFO]$(NC) Running unit tests..."
	@PYTHONPATH=$(SRC_DIR) $(PYTHON) $(UNIT_TESTS)

# Run integration tests only
.PHONY: test-integration
test-integration: validate
	@echo "$(BLUE)[INFO]$(NC) Running integration tests..."
	@PYTHONPATH=$(SRC_DIR) $(PYTHON) $(INTEGRATION_TESTS)

# Run basic functionality test
.PHONY: test-basic
test-basic: validate
	@echo "$(BLUE)[INFO]$(NC) Running basic functionality test..."
	@PYTHONPATH=$(SRC_DIR) $(PYTHON) $(BASIC_TESTS)

# Run interactive demo
.PHONY: demo
demo: validate
	@echo "$(BLUE)[INFO]$(NC) Starting interactive demo..."
	@echo "$(YELLOW)[TIP]$(NC) Use 'quit' to exit the interactive mode"
	@cd $(SRC_DIR) && $(PYTHON) main.py interactive

# Run with CSV input
.PHONY: csv
csv: validate
	@echo "$(BLUE)[INFO]$(NC) Running with CSV input: $(or $(FILE),$(SAMPLE_CSV))"
	@test -f $(or $(FILE),$(SAMPLE_CSV)) || (echo "$(RED)[ERROR]$(NC) CSV file not found: $(or $(FILE),$(SAMPLE_CSV))" && exit 1)
	@cd $(SRC_DIR) && $(PYTHON) main.py csv ../$(or $(FILE),$(SAMPLE_CSV))

# Create sample CSV file
.PHONY: create-csv
create-csv:
	@echo "$(BLUE)[INFO]$(NC) Creating sample CSV file: $(or $(FILE),$(SAMPLE_CSV))"
	@cd $(SRC_DIR) && $(PYTHON) main.py create_csv ../$(or $(FILE),$(SAMPLE_CSV))
	@echo "$(GREEN)[SUCCESS]$(NC) Sample CSV file created: $(or $(FILE),$(SAMPLE_CSV))"

# Reformat CSV file from external format to our format
.PHONY: reformat-csv
reformat-csv:
	@echo "$(BLUE)[INFO]$(NC) Reformatting CSV file: $(or $(FILE),CSE535-F25-Project-1-Testcases.csv)"
	@test -f $(or $(FILE),CSE535-F25-Project-1-Testcases.csv) || (echo "$(RED)[ERROR]$(NC) CSV file not found: $(or $(FILE),CSE535-F25-Project-1-Testcases.csv)" && exit 1)
	@$(PYTHON) $(SCRIPT_DIR)/reformat_csv.py
	@echo "$(GREEN)[SUCCESS]$(NC) CSV file reformatted"

# Clean up temporary files
.PHONY: clean
clean:
	@echo "$(BLUE)[INFO]$(NC) Cleaning up temporary files..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.pyc" -delete 2>/dev/null || true
	@find . -name "*.pyo" -delete 2>/dev/null || true
	@find . -name "*~" -delete 2>/dev/null || true
	@rm -f test_output_*.csv demo_input.csv 2>/dev/null || true
	@echo "$(GREEN)[SUCCESS]$(NC) Cleanup completed"

# Check code style
.PHONY: lint
lint:
	@echo "$(BLUE)[INFO]$(NC) Checking code style..."
	@if command -v flake8 >/dev/null 2>&1; then \
		echo "$(BLUE)[INFO]$(NC) Running flake8..."; \
		flake8 --max-line-length=100 --ignore=E501,W503 $(SRC_DIR)/*.py $(TEST_DIR)/*.py || true; \
	elif command -v pylint >/dev/null 2>&1; then \
		echo "$(BLUE)[INFO]$(NC) Running pylint..."; \
		pylint --disable=C0103,C0114,C0115,C0116 $(SRC_DIR)/*.py $(TEST_DIR)/*.py || true; \
	else \
		echo "$(YELLOW)[WARNING]$(NC) No linting tools available (flake8, pylint)"; \
		echo "$(BLUE)[INFO]$(NC) Install with: pip install flake8 pylint"; \
	fi

# Install dependencies (none required for this project)
.PHONY: install
install:
	@echo "$(BLUE)[INFO]$(NC) Checking dependencies..."
	@echo "$(GREEN)[SUCCESS]$(NC) No external dependencies required"
	@echo "$(BLUE)[INFO]$(NC) This project uses only Python standard library"

# Build/validate the entire project
.PHONY: build
build: clean validate test
	@echo "$(GREEN)[SUCCESS]$(NC) Build completed successfully"
	@echo "$(BLUE)[INFO]$(NC) Project is ready for deployment"

# Run the system interactively (alias for demo)
.PHONY: run
run: demo

# Show project structure
.PHONY: structure
structure:
	@echo "$(BLUE)[INFO]$(NC) Project structure:"
	@tree -I '__pycache__|*.pyc' || ls -la

# Show project statistics
.PHONY: stats
stats:
	@echo "$(BLUE)[INFO]$(NC) Project statistics:"
	@echo "Source files:"
	@wc -l $(SRC_DIR)/*.py | tail -1
	@echo "Test files:"
	@wc -l $(TEST_DIR)/*.py | tail -1
	@echo "Total Python files:"
	@find . -name "*.py" -exec wc -l {} + | tail -1

# Development targets
.PHONY: dev-setup
dev-setup:
	@echo "$(BLUE)[INFO]$(NC) Setting up development environment..."
	@echo "export PYTHONPATH=$(PWD)/$(SRC_DIR)" > .env
	@echo "$(GREEN)[SUCCESS]$(NC) Development environment ready"
	@echo "$(YELLOW)[TIP]$(NC) Source .env file: source .env"

# Quick test (fastest tests only)
.PHONY: quick-test
quick-test: validate
	@echo "$(BLUE)[INFO]$(NC) Running quick tests..."
	@PYTHONPATH=$(SRC_DIR) $(PYTHON) -m unittest $(TEST_DIR).test_unit.TestMessages -v
	@PYTHONPATH=$(SRC_DIR) $(PYTHON) -m unittest $(TEST_DIR).test_unit.TestTransactionParsing -v
	@echo "$(GREEN)[SUCCESS]$(NC) Quick tests passed"

# Performance test
.PHONY: perf-test
perf-test: validate
	@echo "$(BLUE)[INFO]$(NC) Running performance test..."
	@echo "$(YELLOW)[WARNING]$(NC) Performance tests not implemented yet"

# Documentation generation
.PHONY: docs
docs:
	@echo "$(BLUE)[INFO]$(NC) Documentation available in $(DOC_DIR)/"
	@ls -la $(DOC_DIR)/

# All-in-one target for CI/CD
.PHONY: ci
ci: clean validate test lint
	@echo "$(GREEN)[SUCCESS]$(NC) CI pipeline completed"

# Debugging target
.PHONY: debug
debug:
	@echo "$(BLUE)[INFO]$(NC) Debug information:"
	@echo "Python version: $$($(PYTHON) --version)"
	@echo "Working directory: $$(pwd)"
	@echo "PYTHONPATH: $(SRC_DIR)"
	@echo "Available files:"
	@find $(SRC_DIR) -name "*.py" -type f
