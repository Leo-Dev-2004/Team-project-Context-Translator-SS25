#!/usr/bin/env python3
"""
Run backend tests under Backend/tests and print a concise summary.
- Tries to use pytest if installed (captures and summarizes results).
- Falls back to unittest discovery if pytest not available.

Usage:
    python scripts/run_backend_tests.py [--output <file>] [--verbose]

Options:
    --output <file>  Save full test output to a file
    --verbose        Print detailed output while running
"""
import argparse
import subprocess
import sys
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = ROOT / "Backend" / "tests"


def run_pytest(output_file: Path | None, verbose: bool) -> int:
    pytest_exec = shutil.which("pytest")
    if not pytest_exec:
        return -1

    cmd = [pytest_exec, str(TEST_DIR), "-q", "--disable-warnings"]
    if verbose:
        cmd = [pytest_exec, str(TEST_DIR)]

    print(f"Running pytest: {' '.join(cmd)}")

    # Run pytest and capture output
    proc = subprocess.run(cmd, capture_output=True, text=True)

    out = proc.stdout
    err = proc.stderr

    if output_file:
        output_file.write_text(out + "\n" + err)

    # Print short summary extracted from pytest output
    # Pytest prints a summary line like: "== 3 passed, 1 skipped in 0.12s =="
    summary_lines = [l for l in (out + err).splitlines() if "==" in l and "passed" in l]
    if summary_lines:
        print("\nTest summary:\n" + summary_lines[-1])
    else:
        # Fallback: print last 10 lines
        print("\nFull output (last 10 lines):\n" + "\n".join((out + err).splitlines()[-10:]))

    return proc.returncode


def run_unittest(output_file: Path | None, verbose: bool) -> int:
    # Use python -m unittest discover
    cmd = [sys.executable, "-m", "unittest", "discover", "-s", str(TEST_DIR), "-v"]
    if not verbose:
        # there's no quiet mode for unittest module, capture output
        proc = subprocess.run(cmd, capture_output=True, text=True)
        out = proc.stdout
        err = proc.stderr
        if output_file:
            output_file.write_text(out + "\n" + err)
        # Try to summarize: look for "OK" or "FAILED"
        if "OK" in out:
            print("All tests OK (unittest)")
            return 0
        else:
            # Print a short tail
            print("Unittest output (last 20 lines):\n" + "\n".join(out.splitlines()[-20:]))
            return proc.returncode
    else:
        proc = subprocess.run(cmd)
        return proc.returncode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", "-o", help="Path to save full output")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    output_path = Path(args.output) if args.output else None

    if not TEST_DIR.exists():
        print(f"Test directory not found: {TEST_DIR}")
        sys.exit(2)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    # Try pytest first
    rc = run_pytest(output_path, args.verbose)
    if rc == -1:
        print("pytest not found, falling back to unittest discovery")
        rc = run_unittest(output_path, args.verbose)

    if rc == 0:
        print("\nOverall result: SUCCESS")
    else:
        print("\nOverall result: FAIL")

    sys.exit(rc)


if __name__ == '__main__':
    main()
