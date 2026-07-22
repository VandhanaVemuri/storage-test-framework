# Design Document — Storage Test Automation Framework

## 1. Purpose

This project is a small-scale storage test automation framework, built to
mirror the structure of real SSD/NVMe validation tooling: a C++ engine that
models firmware-level device behavior, and a Python automation layer that
drives config-driven test suites against it and reports results.

It is intentionally scoped to demonstrate the *shape* of real storage
validation work — protocol-level command handling, firmware-like fault
behavior, and automated reporting — rather than to implement a full NVMe
stack.

## 2. Architecture

```
┌─────────────────────┐        line protocol         ┌──────────────────────┐
│  Python automation   │  (WRITE/READ/FLUSH/... over  │   C++ test engine     │
│  layer               │   stdin/stdout of a spawned   │   (storage_test_cli)  │
│  - runner.py          │───────── subprocess) ───────▶│   - SimulatedDevice   │
│  - device_client.py   │◀───────────────────────────── │     (device.cpp/hpp) │
│  - perf.py            │                               └──────────────────────┘
│  - report.py          │
└─────────────────────┘
```

The C++ binary is treated as the "device under test" (DUT). The Python
layer never reaches into its internals — it only talks to it over the line
protocol, the same way a real automation framework talks to hardware over
a vendor SDK, serial link, or NVMe passthrough ioctl.

## 3. Simulated device behavior

`SimulatedDevice` (cpp/include/device.hpp, cpp/src/device.cpp) models:

- **Block storage**: a fixed-size array of blocks (960 user-addressable +
  64 spare), each `block_size` bytes.
- **Write-then-flush durability contract**: writes land in an uncommitted
  "shadow" area first. They are visible to reads immediately
  (read-after-write), but are only guaranteed to survive a simulated power
  loss once `FLUSH` has been called. This is the same contract real block
  devices make, and it's the behavior the power-loss test cases validate.
- **Bad-block remap**: a logical block address (LBA) can be marked bad via
  fault injection. Subsequent writes to that LBA are transparently
  redirected to a spare block and the mapping is recorded — the same
  approach a flash translation layer (FTL) uses to hide failing physical
  cells from the host.
- **Wear tracking**: every committed write increments a per-physical-block
  wear counter, surfaced via `GET_LOG_PAGE` (a stand-in for SMART-style
  health telemetry).
- **TRIM**: zeroes a range and drops any pending shadow writes for it,
  modeling the deallocate/discard contract hosts rely on after deleting
  data.
- **Fault injection**: `INJECT_ERROR BAD_BLOCK <lba>` and
  `INJECT_ERROR POWER_LOSS` are test-only hooks, analogous to the
  fault-injection interfaces real test benches use to exercise firmware
  error paths without needing hardware that is actually failing.

## 4. Line protocol

One command per line in, one response line out:

```
WRITE <lba> <hex_data>
READ <lba> <length>
FLUSH
TRIM <lba> <length>
GET_LOG_PAGE
IDENTIFY
INJECT_ERROR BAD_BLOCK <lba>
INJECT_ERROR POWER_LOSS
EXIT
```

Response: `<STATUS> [data=<hex_or_kv>] [msg=<text>] latency_us=<n>`

Latency is measured in the C++ process around the operation itself, so
performance numbers reported by the Python layer reflect device-side
processing time, not IPC overhead alone.

## 5. Test automation layer

- **`runner.py`**: loads YAML test-case files, executes each step against
  a fresh device instance, and checks `expect_status` / `expect_data`
  against the actual response. Adding a test case means adding a YAML
  file — no code changes.
- **`report.py`**: renders a console pass/fail summary and writes a CSV
  report for archiving.
- **`perf.py`**: runs a configurable mixed read/write load, then reports
  IOPS, throughput (MB/s), and p50/p95/p99 latency, plus a latency
  histogram (matplotlib).
- **`pytest` suite** (`python/tests/test_storage_framework.py`): wraps the
  YAML functional cases as parametrized pytest cases (so they show up
  individually in CI output) and adds direct unit tests for protocol
  parsing and the device client.

## 6. Why these specific test cases

The four functional test cases were chosen because they mirror the
first things a real storage validation suite checks:

1. **`sequential_write_read`** — basic data integrity (read-after-write).
2. **`bad_block_remap`** — FTL correctness under a failing cell.
3. **`power_loss_during_write`** — crash consistency / durability contract.
4. **`trim_and_reclaim`** — deallocate/discard correctness.

## 7. Known simplifications

- No real NVMe/SATA transport — the line protocol stands in for it.
- No concurrent/multi-queue command handling (real NVMe controllers
  process many queues in parallel).
- Wear leveling is tracked but not actively balanced (no read-time
  relocation of hot blocks).
- Power-loss simulation is instantaneous and total (drops all unflushed
  shadow writes), rather than modeling partial-write torn pages.

These are documented rather than hidden — they're the natural next steps
if this were extended into a larger project.
