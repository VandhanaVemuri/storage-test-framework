# User Manual — Storage Test Automation Framework

## Requirements

- A C++17 compiler (`g++` or `clang++`)
- Python 3.9+
- `pip install -r python/requirements.txt` (PyYAML, matplotlib, pytest)

## 1. Build the test engine

```bash
bash scripts/build.sh
```

This compiles `cpp/src/device.cpp` and `cpp/src/main.cpp` into
`cpp/storage_test_cli`.

## 2. Run the functional test suite

```bash
python3 python/run_functional_tests.py
```

Optional flags:

```bash
python3 python/run_functional_tests.py \
  --binary cpp/storage_test_cli \
  --tests-dir tests/functional \
  --csv reports/functional_report.csv
```

This runs every YAML test case in `tests/functional/`, printing a
PASS/FAIL summary and optionally writing a CSV report.

### Running via pytest (used in CI)

```bash
cd python
python -m pytest tests/ -v
```

Each YAML test case appears as its own parametrized pytest case, so
CI output shows exactly which scenario failed.

## 3. Run the performance/load test

```bash
python3 python/run_perf_test.py --ops 500 \
  --csv reports/perf_report.csv \
  --chart reports/latency_histogram.png
```

Reports IOPS, throughput (MB/s), and p50/p95/p99 latency for a mixed
read/write workload, and (optionally) writes a latency histogram PNG.

## 4. Run everything at once

```bash
bash scripts/run_all.sh
```

Builds the engine, runs the functional suite, runs the perf test, and
writes all reports into `reports/`.

## 5. Adding a new functional test case

Drop a new YAML file into `tests/functional/`. No code changes needed.
Format:

```yaml
name: my_new_test
description: What this test checks and why.
steps:
  - op: WRITE
    lba: 100
    data: "aabbccdd"       # hex-encoded payload
    expect_status: OK       # optional, defaults to OK
  - op: READ
    lba: 100
    length: 4
    expect_status: OK
    expect_data: "aabbccdd" # optional; omit to skip data comparison
  - op: FLUSH
  - op: TRIM
    lba: 100
    length: 1
  - op: INJECT_ERROR
    type: BAD_BLOCK          # or POWER_LOSS
    lba: 100                 # only needed for BAD_BLOCK
```

## 6. Supported operations reference

| Op | Args | Notes |
|---|---|---|
| `WRITE` | `lba`, `data` (hex) | Zero-padded to block size |
| `READ` | `lba`, `length` | Returns hex payload |
| `FLUSH` | — | Commits all pending writes |
| `TRIM` | `lba`, `length` | Zeroes and discards pending writes for range |
| `GET_LOG_PAGE` | — | Returns wear/bad-block/spare stats |
| `IDENTIFY` | — | Returns device model/geometry |
| `INJECT_ERROR BAD_BLOCK` | `lba` | Marks LBA bad; next write remaps to spare |
| `INJECT_ERROR POWER_LOSS` | — | Drops all unflushed writes |

## 7. Troubleshooting

- **`binary not found` error**: run `bash scripts/build.sh` first.
- **`ModuleNotFoundError: yaml` / `matplotlib`**: run
  `pip install -r python/requirements.txt`.
- **A functional test fails after editing `device.cpp`**: rebuild with
  `scripts/build.sh` — the Python layer always calls whatever binary is
  on disk, so stale builds are a common source of confusing failures.
