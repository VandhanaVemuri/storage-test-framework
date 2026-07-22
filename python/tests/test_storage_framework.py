"""
Pytest wrapper around the functional test-case suite, plus a few direct
unit tests on the protocol parsing and device client. Running this file
is what the CI workflow (.github/workflows/ci.yml) invokes.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from storage_test.device_client import DeviceClient
from storage_test.runner import load_test_cases, run_test_case

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
BINARY = os.path.join(ROOT, "cpp", "storage_test_cli")
FUNCTIONAL_DIR = os.path.join(ROOT, "tests", "functional")


@pytest.fixture(scope="module")
def binary_path():
    if not os.path.isfile(BINARY):
        pytest.skip(f"binary not built at {BINARY}; run scripts/build.sh first")
    return BINARY


def _case_ids():
    return [c["name"] for c in load_test_cases(FUNCTIONAL_DIR)]


@pytest.mark.parametrize("case", load_test_cases(FUNCTIONAL_DIR), ids=_case_ids())
def test_functional_case(binary_path, case):
    with DeviceClient(binary_path) as client:
        result = run_test_case(client, case)
    assert result.passed, f"{result.name} failed: {result.error or [s.reason for s in result.steps if not s.passed]}"


# --- unit tests: protocol / client behavior, no C++ binary required -------

def test_parse_response_basic():
    from storage_test.device_client import DeviceClient
    resp = DeviceClient._parse_response("OK data=deadbeef latency_us=12")
    assert resp.status == "OK"
    assert resp.data == "deadbeef"
    assert resp.latency_us == 12


def test_parse_response_with_message():
    from storage_test.device_client import DeviceClient
    resp = DeviceClient._parse_response("OK msg=REMAPPED latency_us=3")
    assert resp.ok
    assert resp.message == "REMAPPED"


def test_parse_response_error_status():
    from storage_test.device_client import DeviceClient
    resp = DeviceClient._parse_response("ERR_BAD_BLOCK msg=blocked latency_us=1")
    assert not resp.ok
    assert resp.status == "ERR_BAD_BLOCK"


def test_device_lifecycle(binary_path):
    with DeviceClient(binary_path) as client:
        resp = client.identify()
        assert resp.ok
        assert "MODEL=SIM-SSD-01" in resp.data


def test_write_read_roundtrip(binary_path):
    with DeviceClient(binary_path) as client:
        w = client.write(5, "cafebabe")
        assert w.ok
        r = client.read(5, 4)
        assert r.ok
        assert r.data == "cafebabe"


def test_out_of_range_lba(binary_path):
    with DeviceClient(binary_path) as client:
        resp = client.write(999999, "aabb")
        assert resp.status == "ERR_OUT_OF_RANGE"


def test_bad_hex_payload(binary_path):
    with DeviceClient(binary_path) as client:
        resp = client.write(0, "not_hex!!")
        assert resp.status == "ERR_BAD_ARGS"


def test_get_log_page_reports_wear(binary_path):
    with DeviceClient(binary_path) as client:
        client.write(0, "aa")
        client.flush()
        resp = client.get_log_page()
        assert resp.ok
        assert "WEAR_AVG" in resp.data
        assert "BAD_BLOCKS" in resp.data
