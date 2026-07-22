#!/usr/bin/env bash
# Builds the engine, runs the functional suite, then the perf/load test,
# writing reports into ./reports.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

bash "$ROOT/scripts/build.sh"

mkdir -p "$ROOT/reports"

echo
echo ">>> Running functional test suite..."
python3 "$ROOT/python/run_functional_tests.py" --csv "$ROOT/reports/functional_report.csv"

echo
echo ">>> Running performance/load test..."
python3 "$ROOT/python/run_perf_test.py" --ops 500 \
    --csv "$ROOT/reports/perf_report.csv" \
    --chart "$ROOT/reports/latency_histogram.png"

echo
echo "Reports written to $ROOT/reports/"
