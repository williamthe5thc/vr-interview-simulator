#!/usr/bin/env python3
"""
VR Interview System Test Runner

This script runs the test suite for the VR Interview System.
It can run individual tests or all tests in sequence.
"""

import sys
import os
import subprocess
import argparse
import time
from datetime import datetime
from pathlib import Path

# Define the tests
TESTS = {
    "alltalk": "test_alltalk.py",
    "mic": "test_mic.py",
    "ollama": "test_ollama.py",
    "transcription": "test_transcription.py",
    "websocket": "test_websocket.py",
    "integration": "test_integration.py",
    "performance": "test_performance.py"
}

# Define test groups
TEST_GROUPS = {
    "core": ["ollama", "transcription", "websocket"],
    "audio": ["mic", "transcription", "alltalk"],
    "quick": ["ollama", "transcription"],
    "full": list(TESTS.keys())
}

def run_test(test_name, args=None):
    """Run a single test"""
    if test_name not in TESTS:
        print(f"Error: Unknown test '{test_name}'")
        return False
        
    test_script = TESTS[test_name]
    test_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), test_script)
    
    if not os.path.exists(test_path):
        print(f"Error: Test script not found: {test_path}")
        return False
    
    # Build command
    cmd = [sys.executable, test_path]
    if args:
        cmd.extend(args)
        
    print(f"\n{'='*50}")
    print(f"Running test: {test_name}")
    print(f"{'='*50}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*50}\n")
    
    # Run the test
    try:
        start_time = time.time()
        result = subprocess.run(cmd)
        elapsed = time.time() - start_time
        
        success = result.returncode == 0
        status = "PASSED" if success else "FAILED"
        
        print(f"\n{'='*50}")
        print(f"Test {test_name} {status} in {elapsed:.2f}s (exit code: {result.returncode})")
        print(f"{'='*50}\n")
        
        return success
    except Exception as e:
        print(f"\nError running test: {e}")
        return False

def run_test_group(group_name, args=None):
    """Run a group of tests"""
    if group_name not in TEST_GROUPS:
        print(f"Error: Unknown test group '{group_name}'")
        return False
        
    tests = TEST_GROUPS[group_name]
    print(f"\nRunning test group: {group_name} ({len(tests)} tests)")
    
    results = {}
    for test in tests:
        results[test] = run_test(test, args)
        
    # Summary
    print("\n" + "="*50)
    print(f"Test Group Summary: {group_name}")
    print("="*50)
    
    passed = sum(1 for r in results.values() if r)
    failed = len(results) - passed
    
    for test, success in results.items():
        status = "PASSED" if success else "FAILED"
        print(f"{test}: {status}")
        
    print(f"\nTotal: {len(results)} tests, {passed} passed, {failed} failed")
    
    return failed == 0

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="VR Interview System Test Runner")
    parser.add_argument("--test", choices=list(TESTS.keys()), help="Run a specific test")
    parser.add_argument("--group", choices=list(TEST_GROUPS.keys()), help="Run a group of tests")
    parser.add_argument("--list", action="store_true", help="List available tests and groups")
    parser.add_argument("--args", nargs=argparse.REMAINDER, help="Additional arguments to pass to the test script")
    
    args = parser.parse_args()
    
    # Create the output directory if it doesn't exist
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "output")
    os.makedirs(output_dir, exist_ok=True)
    
    # List tests if requested
    if args.list:
        print("\nAvailable Tests:")
        for name, script in TESTS.items():
            print(f"  {name}: {script}")
            
        print("\nTest Groups:")
        for group, tests in TEST_GROUPS.items():
            print(f"  {group}: {', '.join(tests)}")
        return 0
        
    # Record test run
    print(f"Test run started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run specific test or group
    if args.test:
        success = run_test(args.test, args.args)
    elif args.group:
        success = run_test_group(args.group, args.args)
    else:
        # Default: run quick tests
        success = run_test_group("quick", args.args)
        
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())