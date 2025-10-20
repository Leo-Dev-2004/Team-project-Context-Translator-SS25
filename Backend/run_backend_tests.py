#!/usr/bin/env python3
"""
Comprehensive Backend Test Runner
Runs all backend tests with timeout, captures results, and returns sentinel values.
Returns: OK, WARNING, or ERROR for each test.

Usage:
    python Backend/run_backend_tests.py [--verbose] [--timeout SECONDS]
"""

import sys
import os
import asyncio
import subprocess
import time
from pathlib import Path
import argparse
import json

# Add Backend to path
BACKEND_DIR = Path(__file__).parent
PROJECT_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

TESTS_DIR = BACKEND_DIR / "tests"
DEFAULT_TIMEOUT = 15  # seconds per test


class TestResult:
    """Stores result of a test run"""
    def __init__(self, name, status, duration, output="", error=""):
        self.name = name
        self.status = status  # OK, WARNING, ERROR
        self.duration = duration
        self.output = output
        self.error = error


def run_single_test(test_file: Path, timeout: int, verbose: bool) -> TestResult:
    """Run a single test file with timeout"""
    test_name = test_file.stem
    start_time = time.time()
    
    try:
        if verbose:
            print(f"\n{'='*60}")
            print(f"Running: {test_name}")
            print(f"{'='*60}")
        
        # Run the test as a subprocess
        result = subprocess.run(
            [sys.executable, str(test_file)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_ROOT)
        )
        
        duration = time.time() - start_time
        
        # Determine status based on return code and output
        if result.returncode == 0:
            # Check if output indicates success
            output_lower = result.stdout.lower() + result.stderr.lower()
            if "error" in output_lower or "failed" in output_lower or "traceback" in output_lower:
                status = "WARNING"
            else:
                status = "OK"
        else:
            status = "ERROR"
        
        if verbose:
            print(result.stdout)
            if result.stderr:
                print("STDERR:", result.stderr)
        
        return TestResult(
            name=test_name,
            status=status,
            duration=duration,
            output=result.stdout,
            error=result.stderr
        )
        
    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        if verbose:
            print(f"TIMEOUT after {duration:.2f}s")
        return TestResult(
            name=test_name,
            status="ERROR",
            duration=duration,
            error=f"Test timed out after {timeout} seconds"
        )
    
    except Exception as e:
        duration = time.time() - start_time
        if verbose:
            print(f"EXCEPTION: {e}")
        return TestResult(
            name=test_name,
            status="ERROR",
            duration=duration,
            error=str(e)
        )


def discover_tests(tests_dir: Path) -> list[Path]:
    """Find all test_*.py files in tests directory"""
    test_files = sorted(tests_dir.glob("test_*.py"))
    # Exclude performance_test.py as it might be long-running
    test_files = [f for f in test_files if f.name != "performance_test.py"]
    return test_files


def print_summary(results: list[TestResult], total_duration: float):
    """Print summary of all test results"""
    print(f"\n{'='*80}")
    print("TEST RESULTS SUMMARY")
    print(f"{'='*80}")
    
    # Count statuses
    ok_count = sum(1 for r in results if r.status == "OK")
    warning_count = sum(1 for r in results if r.status == "WARNING")
    error_count = sum(1 for r in results if r.status == "ERROR")
    
    # Print results table
    print(f"\n{'Test Name':<50} {'Status':<10} {'Duration':>10}")
    print(f"{'-'*50} {'-'*10} {'-'*10}")
    
    for result in results:
        status_symbol = {
            "OK": "✓ OK",
            "WARNING": "⚠ WARNING",
            "ERROR": "✗ ERROR"
        }.get(result.status, result.status)
        
        print(f"{result.name:<50} {status_symbol:<10} {result.duration:>9.2f}s")
        
        # Print error details for failed tests
        if result.status == "ERROR" and result.error:
            print(f"  └─ Error: {result.error[:100]}")
    
    print(f"\n{'-'*80}")
    print(f"Total Tests: {len(results)}")
    print(f"  ✓ OK:       {ok_count}")
    print(f"  ⚠ WARNING:  {warning_count}")
    print(f"  ✗ ERROR:    {error_count}")
    print(f"Total Duration: {total_duration:.2f}s")
    print(f"{'='*80}\n")
    
    # Overall status
    if error_count > 0:
        print("OVERALL STATUS: ERROR - Some tests failed")
        return 1
    elif warning_count > 0:
        print("OVERALL STATUS: WARNING - All tests completed with warnings")
        return 0
    else:
        print("OVERALL STATUS: OK - All tests passed")
        return 0


def save_results_json(results: list[TestResult], output_file: Path):
    """Save results to JSON file"""
    data = {
        "timestamp": time.time(),
        "total_tests": len(results),
        "ok_count": sum(1 for r in results if r.status == "OK"),
        "warning_count": sum(1 for r in results if r.status == "WARNING"),
        "error_count": sum(1 for r in results if r.status == "ERROR"),
        "tests": [
            {
                "name": r.name,
                "status": r.status,
                "duration": r.duration,
                "error": r.error if r.error else None
            }
            for r in results
        ]
    }
    
    output_file.write_text(json.dumps(data, indent=2))
    print(f"Results saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Run all Backend tests with timeout and return sentinel values"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed output for each test"
    )
    parser.add_argument(
        "--timeout", "-t",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Timeout per test in seconds (default: {DEFAULT_TIMEOUT})"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Save results to JSON file"
    )
    parser.add_argument(
        "--test", 
        type=str,
        help="Run only a specific test file (without .py extension)"
    )
    
    args = parser.parse_args()
    
    if not TESTS_DIR.exists():
        print(f"ERROR: Tests directory not found: {TESTS_DIR}")
        return 2
    
    # Discover tests
    if args.test:
        test_files = [TESTS_DIR / f"{args.test}.py"]
        if not test_files[0].exists():
            print(f"ERROR: Test file not found: {test_files[0]}")
            return 2
    else:
        test_files = discover_tests(TESTS_DIR)
    
    if not test_files:
        print("No test files found!")
        return 2
    
    print(f"Found {len(test_files)} test(s) to run")
    print(f"Timeout per test: {args.timeout}s")
    
    # Run all tests
    results = []
    total_start = time.time()
    
    for test_file in test_files:
        result = run_single_test(test_file, args.timeout, args.verbose)
        results.append(result)
        
        # Print quick status
        if not args.verbose:
            status_symbol = {"OK": "✓", "WARNING": "⚠", "ERROR": "✗"}[result.status]
            print(f"{status_symbol} {result.name:<50} {result.status:<10} {result.duration:>6.2f}s")
    
    total_duration = time.time() - total_start
    
    # Print summary
    exit_code = print_summary(results, total_duration)
    
    # Save to JSON if requested
    if args.output:
        save_results_json(results, Path(args.output))
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
