"""
device_client.py

Wraps the compiled C++ storage_test_cli binary as a persistent subprocess
and speaks its line protocol. This is the Python-side analog of a real
storage test automation layer talking to a DUT (device under test) over
whatever transport the vendor exposes (SDK, serial, ioctl, etc.) - here
the "transport" is stdin/stdout of the simulated firmware binary.
"""

import subprocess
import shlex
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class DeviceResponse:
    status: str
    data: Optional[str]
    message: Optional[str]
    latency_us: int
    raw: str

    @property
    def ok(self) -> bool:
        return self.status == "OK"


class DeviceClientError(RuntimeError):
    pass


class DeviceClient:
    """Manages the lifecycle of the storage_test_cli subprocess and provides
    a typed Python method per storage operation."""

    def __init__(self, binary_path: str):
        self.binary_path = binary_path
        self._proc: Optional[subprocess.Popen] = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self):
        self._proc = subprocess.Popen(
            [self.binary_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # line-buffered
        )

    def stop(self):
        if self._proc is None:
            return
        try:
            self._send_raw("EXIT")
        except Exception:
            pass
        self._proc.terminate()
        try:
            self._proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._proc.kill()
        self._proc = None

    def _send_raw(self, command: str) -> DeviceResponse:
        if self._proc is None or self._proc.stdin is None or self._proc.stdout is None:
            raise DeviceClientError("device process is not running")

        self._proc.stdin.write(command + "\n")
        self._proc.stdin.flush()

        line = self._proc.stdout.readline()
        if not line:
            stderr = self._proc.stderr.read() if self._proc.stderr else ""
            raise DeviceClientError(f"device process closed unexpectedly. stderr: {stderr}")

        return self._parse_response(line.strip())

    @staticmethod
    def _parse_response(line: str) -> DeviceResponse:
        tokens = shlex.split(line)
        if not tokens:
            raise DeviceClientError(f"empty response line: {line!r}")

        status = tokens[0]
        data = None
        message = None
        latency_us = -1

        for tok in tokens[1:]:
            if tok.startswith("data="):
                data = tok[len("data="):]
            elif tok.startswith("msg="):
                message = tok[len("msg="):]
            elif tok.startswith("latency_us="):
                latency_us = int(tok[len("latency_us="):])

        return DeviceResponse(status=status, data=data, message=message, latency_us=latency_us, raw=line)

    # --- typed operations -------------------------------------------------

    def write(self, lba: int, hex_data: str) -> DeviceResponse:
        return self._send_raw(f"WRITE {lba} {hex_data}")

    def read(self, lba: int, length: int) -> DeviceResponse:
        return self._send_raw(f"READ {lba} {length}")

    def flush(self) -> DeviceResponse:
        return self._send_raw("FLUSH")

    def trim(self, lba: int, length: int) -> DeviceResponse:
        return self._send_raw(f"TRIM {lba} {length}")

    def get_log_page(self) -> DeviceResponse:
        return self._send_raw("GET_LOG_PAGE")

    def identify(self) -> DeviceResponse:
        return self._send_raw("IDENTIFY")

    def inject_bad_block(self, lba: int) -> DeviceResponse:
        return self._send_raw(f"INJECT_ERROR BAD_BLOCK {lba}")

    def inject_power_loss(self) -> DeviceResponse:
        return self._send_raw("INJECT_ERROR POWER_LOSS")
