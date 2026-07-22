#!/usr/bin/env python3
"""
Entry point for the functional test suite.

Usage:
    python3 run_functional_tests.py [--binary PATH] [--tests-dir PATH] [--csv PATH]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from storage_test.runner import run_all
from storage_test.report import print_summary, write_csv_report

DEFAULT_BINARY = os.path.join(os.path.dirname(__file__), "..", "cpp", "storage_test_cli")
DEFAULT_TESTS_DIR = os.path.join(os.path.dirname(__file__), "..", "tests", "functional")


def main():
    parser = argparse.ArgumentParser(description="Run storage functional test suite")
    parser.add_argument("--binary", default=DEFAULT_BINARY, help="path to storage_test_cli")
    parser.add_argument("--tests-dir", default=DEFAULT_TESTS_DIR, help="directory of YAML test cases")
    parser.add_argument("--csv", default=None, help="optional path to write a CSV report")
    args = parser.parse_args()

    if not os.path.isfile(args.binary):
        print(f"error: binary not found at {args.binary}. Build it first with scripts/build.sh", file=sys.stderr)
        sys.exit(2)

    results = run_all(args.binary, args.tests_dir)
    all_passed = print_summary(results)

    if args.csv:
        write_csv_report(results, args.csv)
        print(f"CSV report written to {args.csv}")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
