#!/usr/bin/env python3
"""
Comprehensive test runner for the Distributed Paxos Banking System.
Runs unit tests, integration tests, and system validation.
"""

import unittest
import sys
import os
import time
from io import StringIO

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import test modules
try:
    from test_unit import *
    from test_integration import *
except ImportError as e:
    print(f"Error importing test modules: {e}")
    sys.exit(1)


class TestResult:
    """Custom test result class for better reporting"""
    
    def __init__(self):
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.error_tests = 0
        self.failures = []
        self.errors = []
        self.test_results = {}
    
    def add_result(self, test_name, result):
        """Add a test result"""
        self.test_results[test_name] = result
        self.total_tests += result.testsRun
        self.failed_tests += len(result.failures)
        self.error_tests += len(result.errors)
        self.passed_tests += result.testsRun - len(result.failures) - len(result.errors)
        
        self.failures.extend([(test_name, test, traceback) for test, traceback in result.failures])
        self.errors.extend([(test_name, test, traceback) for test, traceback in result.errors])
    
    def print_summary(self):
        """Print comprehensive test summary"""
        print(f"\n{'='*80}")
        print(f"COMPREHENSIVE TEST SUMMARY")
        print(f"{'='*80}")
        
        # Overall statistics
        print(f"Total Tests Run: {self.total_tests}")
        print(f"Passed: {self.passed_tests} ({self.passed_tests/self.total_tests*100:.1f}%)")
        print(f"Failed: {self.failed_tests} ({self.failed_tests/self.total_tests*100:.1f}%)")
        print(f"Errors: {self.error_tests} ({self.error_tests/self.total_tests*100:.1f}%)")
        
        # Per-suite breakdown
        print(f"\nPer-Suite Results:")
        print(f"-" * 40)
        for test_name, result in self.test_results.items():
            passed = result.testsRun - len(result.failures) - len(result.errors)
            status = "✅ PASS" if result.wasSuccessful() else "❌ FAIL"
            print(f"{test_name:20} | {passed:3}/{result.testsRun:3} | {status}")
        
        # Detailed failures
        if self.failures:
            print(f"\nFAILURES ({len(self.failures)}):")
            print(f"-" * 40)
            for suite_name, test, traceback in self.failures:
                print(f"❌ [{suite_name}] {test}")
                # Print first few lines of traceback
                lines = traceback.strip().split('\n')
                for line in lines[-3:]:  # Last 3 lines usually most relevant
                    if line.strip():
                        print(f"   {line}")
                print()
        
        # Detailed errors
        if self.errors:
            print(f"\nERRORS ({len(self.errors)}):")
            print(f"-" * 40)
            for suite_name, test, traceback in self.errors:
                print(f"💥 [{suite_name}] {test}")
                lines = traceback.strip().split('\n')
                for line in lines[-3:]:
                    if line.strip():
                        print(f"   {line}")
                print()
        
        # Final verdict
        print(f"{'='*80}")
        if self.failed_tests == 0 and self.error_tests == 0:
            print(f"🎉 ALL TESTS PASSED! System is ready for deployment.")
        else:
            print(f"⚠️  {self.failed_tests + self.error_tests} tests need attention.")
        print(f"{'='*80}")


def run_test_suite(test_classes, suite_name):
    """Run a specific test suite"""
    print(f"\n{'='*60}")
    print(f"Running {suite_name}")
    print(f"{'='*60}")
    
    # Create test suite
    test_suite = unittest.TestSuite()
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Capture output
    stream = StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=1)
    result = runner.run(test_suite)
    
    # Print results
    output = stream.getvalue()
    if result.wasSuccessful():
        print(f"✅ {suite_name}: {result.testsRun} tests passed")
    else:
        print(f"❌ {suite_name}: {result.testsRun - len(result.failures) - len(result.errors)}/{result.testsRun} tests passed")
        if result.failures:
            print(f"   Failures: {len(result.failures)}")
        if result.errors:
            print(f"   Errors: {len(result.errors)}")
    
    return result


def run_component_validation():
    """Run basic component validation"""
    print(f"\n{'='*60}")
    print(f"Running Component Validation")
    print(f"{'='*60}")
    
    validation_results = []
    
    # Test 1: Import validation
    try:
        from messages import Transaction, LogEntry, MessageType
        from paxos import PaxosState, PaxosLeader, PaxosBackup
        from node import Node
        from client import Client, ClientManager
        from main import BankingSystem
        validation_results.append(("Import Test", True, "All modules imported successfully"))
    except Exception as e:
        validation_results.append(("Import Test", False, f"Import failed: {e}"))
    
    # Test 2: Basic object creation
    try:
        tx = Transaction("A", "B", 5)
        entry = LogEntry(0, tx, False, "A")
        state = PaxosState("n1")
        validation_results.append(("Object Creation", True, "Basic objects created successfully"))
    except Exception as e:
        validation_results.append(("Object Creation", False, f"Object creation failed: {e}"))
    
    # Test 3: Message serialization
    try:
        from messages import PrepareMessage
        msg = PrepareMessage("n1", "n2", 1)
        json_str = msg.to_json()
        msg2 = Message.from_json(json_str)
        assert msg.msg_type == msg2.msg_type
        validation_results.append(("Serialization", True, "Message serialization works"))
    except Exception as e:
        validation_results.append(("Serialization", False, f"Serialization failed: {e}"))
    
    # Test 4: Transaction parsing
    try:
        from client import parse_transactions
        transactions = parse_transactions("(A,B,5),(C,D,3)")
        assert len(transactions) == 2
        assert transactions[0].sender == "A"
        validation_results.append(("Transaction Parsing", True, "Transaction parsing works"))
    except Exception as e:
        validation_results.append(("Transaction Parsing", False, f"Parsing failed: {e}"))
    
    # Print validation results
    for test_name, success, message in validation_results:
        status = "✅" if success else "❌"
        print(f"{status} {test_name:20} | {message}")
    
    return all(success for _, success, _ in validation_results)


def main():
    """Main test runner"""
    print("🚀 Starting Comprehensive Test Suite for Distributed Paxos Banking System")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    overall_result = TestResult()
    
    # 1. Component Validation
    validation_passed = run_component_validation()
    if not validation_passed:
        print("\n❌ Component validation failed. Aborting test run.")
        return False
    
    # 2. Unit Tests
    unit_test_classes = [
        TestMessages,
        TestPaxosState,
        TestPaxosLeader,
        TestPaxosBackup,
        TestTransactionParsing,
        TestNodeInitialization,
        TestClientManager,
        TestBankingSystem,
        TestLogMerging
    ]
    
    unit_result = run_test_suite(unit_test_classes, "Unit Tests")
    overall_result.add_result("Unit Tests", unit_result)
    
    # 3. Integration Tests
    integration_test_classes = [
        TestLeaderElection,
        TestFailureHandling,
        TestTransactionExecution,
        TestEndToEndScenarios,
        TestCSVProcessing
    ]
    
    integration_result = run_test_suite(integration_test_classes, "Integration Tests")
    overall_result.add_result("Integration Tests", integration_result)
    
    # 4. Print comprehensive summary
    overall_result.print_summary()
    
    # Return success status
    return overall_result.failed_tests == 0 and overall_result.error_tests == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
