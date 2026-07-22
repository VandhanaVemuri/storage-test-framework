# Storage Test Automation Framework

A small-scale storage test automation framework modeled on real SSD/NVMe
validation tooling: a C++ engine simulating firmware-level device behavior
(bad-block remap, wear tracking, write-then-flush crash consistency), and a
Python automation layer that drives YAML-defined test suites against it and
reports functional results plus performance indicators (IOPS, throughput,
latency percentiles).

## Highlights

- **C++ simulated device** with bad-block detection + spare-block remap,
  per-block wear counters, and a crash-consistency (power-loss) model.
- **Config-driven functional tests** — add a YAML file, no code changes.
- **Performance test suite** reporting IOPS, throughput (MB/s), and
  p50/p95/p99 latency, with a generated latency histogram.
- **CI-integrated**: GitHub Actions builds the engine and runs the full
  pytest suite on every push.

## Quick start

```bash
bash scripts/build.sh
python3 python/run_functional_tests.py
python3 python/run_perf_test.py --ops 500 --chart reports/latency_histogram.png
```

Or run everything at once:

```bash
bash scripts/run_all.sh
```

## Project layout

```
cpp/            C++ simulated device + test-engine CLI (storage_test_cli)
python/         Test automation layer (runner, device client, perf, reports)
tests/          YAML functional test cases + perf test config
scripts/        build.sh, run_all.sh
docs/           DESIGN.md, USER_MANUAL.md
.github/        CI workflow
```

See [`docs/DESIGN.md`](docs/DESIGN.md) for architecture and design
rationale, and [`docs/USER_MANUAL.md`](docs/USER_MANUAL.md) for usage
details and how to add new test cases.
