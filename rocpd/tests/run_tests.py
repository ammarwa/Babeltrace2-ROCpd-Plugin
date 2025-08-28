#!/usr/bin/env python3
"""
Test runner for ROCpd module tests using pytest.

This script runs all the test suites for the ROCpd module including:
- Output format tests (csv, pftrace, otf2, ctf)
- Edge case and error handling tests  
- Database size variation tests
- Command line option tests

Usage:
    python3 run_tests.py [--verbose] [--test-pattern PATTERN] [--markers MARKERS]
    
    --verbose       Enable verbose test output
    --test-pattern  Run only tests matching the pattern
    --markers       Run only tests with specific markers (e.g., "not slow")
"""

import argparse
import sys
import os
import subprocess
from pathlib import Path

# Add repo root to path to import rocpd modules
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root))


def run_pytest(test_pattern=None, verbosity=1, markers=None, coverage=False):
    """Run tests using pytest."""
    
    # Set up pytest command
    tests_dir = Path(__file__).parent
    
    cmd = ["python3", "-m", "pytest"]
    
    # Add verbosity
    if verbosity == 2:
        cmd.append("-v")
    elif verbosity >= 3:
        cmd.append("-vv")
    
    # Add test pattern if specified
    if test_pattern:
        cmd.append(f"{tests_dir}/{test_pattern}")
    else:
        cmd.append(str(tests_dir))
    
    # Add markers if specified
    if markers:
        cmd.extend(["-m", markers])
    
    # Add coverage if requested
    if coverage:
        cmd.extend(["--cov=rocpd", "--cov-report=term-missing", "--cov-report=html"])
    
    # Run pytest
    print("Running command:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=repo_root)
    
    return result.returncode == 0


def main():
    """Main entry point for test runner."""
    parser = argparse.ArgumentParser(
        description="Run ROCpd module tests using pytest",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python3 run_tests.py                          # Run all tests
    python3 run_tests.py --verbose                # Run with verbose output
    python3 run_tests.py --test-pattern test_output_formats.py  # Run specific test file
    python3 run_tests.py --markers "not slow"     # Skip slow tests
    python3 run_tests.py --coverage               # Run with coverage report
        """
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='count',
        default=0,
        help='Enable verbose test output (use -vv for extra verbose)'
    )
    
    parser.add_argument(
        '--test-pattern', '-p',
        help='Run only tests matching the pattern (file or test name)'
    )
    
    parser.add_argument(
        '--markers', '-m',
        help='Run only tests with specific markers (e.g., "not slow")'
    )
    
    parser.add_argument(
        '--coverage', '-c',
        action='store_true',
        help='Generate coverage report'
    )
    
    args = parser.parse_args()
    
    # Set verbosity level
    verbosity = max(1, args.verbose + 1)
    
    print("=" * 70)
    print("ROCpd Module Test Suite (pytest)")
    print("=" * 70)
    print()
    
    if args.test_pattern:
        print(f"Running tests matching pattern: {args.test_pattern}")
    elif args.markers:
        print(f"Running tests with markers: {args.markers}")
    else:
        print("Running all tests...")
    
    if args.coverage:
        print("Coverage reporting enabled")
    
    print()
    
    # Run the tests
    success = run_pytest(
        test_pattern=args.test_pattern, 
        verbosity=verbosity,
        markers=args.markers,
        coverage=args.coverage
    )
    
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