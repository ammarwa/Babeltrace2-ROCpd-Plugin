#!/usr/bin/env python3
"""
Test runner for ROCpd module tests.

This script runs all the test suites for the ROCpd module including:
- Output format tests (csv, pftrace, otf2, ctf)
- Edge case and error handling tests  
- Database size variation tests
- Command line option tests

Usage:
    python3 run_tests.py [--verbose] [--test-pattern PATTERN]
    
    --verbose       Enable verbose test output
    --test-pattern  Run only tests matching the pattern
"""

import argparse
import sys
import unittest
import os
from pathlib import Path

# Add repo root to path to import rocpd modules
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root))

def discover_and_run_tests(test_pattern=None, verbosity=1):
    """Discover and run all tests in the tests directory."""
    
    # Set up test discovery
    tests_dir = Path(__file__).parent
    loader = unittest.TestLoader()
    
    if test_pattern:
        # Load specific test pattern
        suite = loader.loadTestsFromName(test_pattern, module=None)
    else:
        # Discover all tests
        suite = loader.discover(
            start_dir=str(tests_dir),
            pattern='test_*.py',
            top_level_dir=str(tests_dir.parent)
        )
    
    # Run the tests
    runner = unittest.TextTestRunner(
        verbosity=verbosity,
        buffer=True,  # Capture stdout/stderr during tests
        failfast=False  # Continue running tests after failures
    )
    
    result = runner.run(suite)
    
    # Return success/failure
    return result.wasSuccessful()


def main():
    """Main entry point for test runner."""
    parser = argparse.ArgumentParser(
        description="Run ROCpd module tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python3 run_tests.py                          # Run all tests
    python3 run_tests.py --verbose                # Run with verbose output
    python3 run_tests.py --test-pattern test_output_formats  # Run specific test module
        """
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose test output'
    )
    
    parser.add_argument(
        '--test-pattern', '-p',
        help='Run only tests matching the pattern (module or test name)'
    )
    
    args = parser.parse_args()
    
    # Set verbosity level
    verbosity = 2 if args.verbose else 1
    
    print("=" * 70)
    print("ROCpd Module Test Suite")
    print("=" * 70)
    print()
    
    if args.test_pattern:
        print(f"Running tests matching pattern: {args.test_pattern}")
    else:
        print("Running all tests...")
    
    print()
    
    # Run the tests
    success = discover_and_run_tests(args.test_pattern, verbosity)
    
    print()
    print("=" * 70)
    if success:
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed!")
        return 1


if __name__ == '__main__':
    sys.exit(main())