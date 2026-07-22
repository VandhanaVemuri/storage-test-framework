"""
report.py

Turns a list of TestCaseResult objects into a console summary and a
CSV report suitable for archiving alongside a CI run.
"""

import csv
from typing import List
from .runner import TestCaseResult


def print_summary(results: List[TestCaseResult]) -> bool:
    passed = sum(1 for r in results if r.passed)
    total = len(results)

    print("\n=== Storage Test Automation Framework: Functional Test Results ===\n")
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"[{status}] {r.name}  ({r.duration_ms:.2f} ms)")
        if r.description:
            print(f"        {r.description}")
        if r.error:
            print(f"        ERROR: {r.error}")
        for step in r.steps:
            if not step.passed:
                print(f"        step {step.step_index} ({step.op}) FAILED: {step.reason}")

    print(f"\n{passed}/{total} test cases passed\n")
    return passed == total


def write_csv_report(results: List[TestCaseResult], path: str) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["test_name", "passed", "duration_ms", "num_steps", "failed_steps", "error"])
        for r in results:
            failed_steps = [s.step_index for s in r.steps if not s.passed]
            writer.writerow([
                r.name,
                r.passed,
                f"{r.duration_ms:.3f}",
                len(r.steps),
                ";".join(map(str, failed_steps)),
                r.error or "",
            ])
