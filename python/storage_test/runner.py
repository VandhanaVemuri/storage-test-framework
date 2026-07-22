"""
runner.py

Loads YAML test-case definitions and executes them step-by-step against a
DeviceClient, checking each step's actual status/data against the expected
values declared in the test case. Adding a new test case means adding a
YAML file - no C++ or Python code changes required.
"""

import glob
import os
import time
import yaml
from dataclasses import dataclass, field
from typing import List, Optional

from .device_client import DeviceClient, DeviceResponse


@dataclass
class StepResult:
    step_index: int
    op: str
    passed: bool
    reason: str
    latency_us: int


@dataclass
class TestCaseResult:
    name: str
    description: str
    passed: bool
    steps: List[StepResult] = field(default_factory=list)
    duration_ms: float = 0.0
    error: Optional[str] = None


def load_test_cases(directory: str) -> List[dict]:
    cases = []
    for path in sorted(glob.glob(os.path.join(directory, "*.yaml"))):
        with open(path, "r") as f:
            case = yaml.safe_load(f)
            case["_source_file"] = os.path.basename(path)
            cases.append(case)
    return cases


def _execute_step(client: DeviceClient, step: dict) -> DeviceResponse:
    op = step["op"]
    if op == "WRITE":
        return client.write(step["lba"], step["data"])
    elif op == "READ":
        return client.read(step["lba"], step["length"])
    elif op == "FLUSH":
        return client.flush()
    elif op == "TRIM":
        return client.trim(step["lba"], step["length"])
    elif op == "GET_LOG_PAGE":
        return client.get_log_page()
    elif op == "IDENTIFY":
        return client.identify()
    elif op == "INJECT_ERROR":
        if step["type"] == "BAD_BLOCK":
            return client.inject_bad_block(step["lba"])
        elif step["type"] == "POWER_LOSS":
            return client.inject_power_loss()
        raise ValueError(f"unknown INJECT_ERROR type: {step['type']}")
    raise ValueError(f"unknown op in test case: {op}")


def run_test_case(client: DeviceClient, case: dict) -> TestCaseResult:
    result = TestCaseResult(name=case["name"], description=case.get("description", ""), passed=True)
    start = time.perf_counter()

    for i, step in enumerate(case.get("steps", [])):
        try:
            resp = _execute_step(client, step)
        except Exception as e:
            result.passed = False
            result.error = f"step {i} ({step.get('op')}) raised: {e}"
            break

        expect_status = step.get("expect_status", "OK")
        expect_data = step.get("expect_data")

        step_passed = True
        reasons = []

        if resp.status != expect_status:
            step_passed = False
            reasons.append(f"expected status {expect_status}, got {resp.status}")

        if expect_data is not None and resp.data != expect_data:
            step_passed = False
            reasons.append(f"expected data {expect_data!r}, got {resp.data!r}")

        result.steps.append(StepResult(
            step_index=i,
            op=step["op"],
            passed=step_passed,
            reason="; ".join(reasons) if reasons else "ok",
            latency_us=resp.latency_us,
        ))

        if not step_passed:
            result.passed = False

    result.duration_ms = (time.perf_counter() - start) * 1000
    return result


def run_all(binary_path: str, test_dir: str) -> List[TestCaseResult]:
    cases = load_test_cases(test_dir)
    results = []
    for case in cases:
        with DeviceClient(binary_path) as client:
            results.append(run_test_case(client, case))
    return results
