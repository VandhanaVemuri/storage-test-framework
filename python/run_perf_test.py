#!/usr/bin/env python3
"""
Entry point for the performance / load test.

Usage:
    python3 run_perf_test.py [--binary PATH] [--ops N] [--csv PATH] [--chart PATH]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from storage_test.perf import run_load_test, write_perf_csv, plot_latency_histogram

DEFAULT_BINARY = os.path.join(os.path.dirname(__file__), "..", "cpp", "storage_test_cli")


def main():
    parser = argparse.ArgumentParser(description="Run storage performance/load test")
    parser.add_argument("--binary", default=DEFAULT_BINARY, help="path to storage_test_cli")
    parser.add_argument("--ops", type=int, default=500, help="number of ops to issue")
    parser.add_argument("--csv", default=None, help="path to write perf metrics CSV")
    parser.add_argument("--chart", default=None, help="path to write latency histogram PNG")
    args = parser.parse_args()

    if not os.path.isfile(args.binary):
        print(f"error: binary not found at {args.binary}. Build it first with scripts/build.sh", file=sys.stderr)
        sys.exit(2)

    result = run_load_test(args.binary, num_ops=args.ops)

    print("\n=== Storage Test Automation Framework: Performance Results ===\n")
    print(f"Total ops:        {result.total_ops}")
    print(f"Duration:         {result.duration_s:.3f} s")
    print(f"IOPS:             {result.iops:.2f}")
    print(f"Throughput:       {result.throughput_mb_s:.2f} MB/s")
    print(f"Latency p50:      {result.p50_latency_us:.2f} us")
    print(f"Latency p95:      {result.p95_latency_us:.2f} us")
    print(f"Latency p99:      {result.p99_latency_us:.2f} us\n")

    if args.csv:
        write_perf_csv(result, args.csv)
        print(f"CSV metrics written to {args.csv}")

    if args.chart:
        plot_latency_histogram(result, args.chart)
        print(f"Latency histogram written to {args.chart}")


if __name__ == "__main__":
    main()
