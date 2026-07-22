"""
perf.py

Runs a mixed read/write load against the device and reports the
performance indicators a storage test bench cares about: IOPS,
throughput (MB/s), and latency percentiles (p50/p95/p99).
"""

import csv
import os
import random
import time
from dataclasses import dataclass
from typing import List

from .device_client import DeviceClient


@dataclass
class PerfResult:
    total_ops: int
    duration_s: float
    iops: float
    throughput_mb_s: float
    p50_latency_us: float
    p95_latency_us: float
    p99_latency_us: float
    latencies_us: List[int]


def _percentile(sorted_values: List[int], pct: float) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * pct
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[f]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


def run_load_test(binary_path: str, num_ops: int = 500, num_blocks: int = 900,
                   block_size: int = 512, write_ratio: float = 0.5, seed: int = 42) -> PerfResult:
    rng = random.Random(seed)
    latencies = []
    bytes_moved = 0
    payload_hex = ("ab" * block_size)  # dummy full-block payload

    start = time.perf_counter()
    with DeviceClient(binary_path) as client:
        for _ in range(num_ops):
            lba = rng.randint(0, num_blocks - 1)
            if rng.random() < write_ratio:
                resp = client.write(lba, payload_hex)
            else:
                resp = client.read(lba, block_size)
            latencies.append(resp.latency_us)
            bytes_moved += block_size
        client.flush()
    duration_s = time.perf_counter() - start

    latencies_sorted = sorted(latencies)
    iops = num_ops / duration_s if duration_s > 0 else 0.0
    throughput_mb_s = (bytes_moved / (1024 * 1024)) / duration_s if duration_s > 0 else 0.0

    return PerfResult(
        total_ops=num_ops,
        duration_s=duration_s,
        iops=iops,
        throughput_mb_s=throughput_mb_s,
        p50_latency_us=_percentile(latencies_sorted, 0.50),
        p95_latency_us=_percentile(latencies_sorted, 0.95),
        p99_latency_us=_percentile(latencies_sorted, 0.99),
        latencies_us=latencies,
    )


def write_perf_csv(result: PerfResult, path: str) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        writer.writerow(["total_ops", result.total_ops])
        writer.writerow(["duration_s", f"{result.duration_s:.4f}"])
        writer.writerow(["iops", f"{result.iops:.2f}"])
        writer.writerow(["throughput_mb_s", f"{result.throughput_mb_s:.2f}"])
        writer.writerow(["p50_latency_us", f"{result.p50_latency_us:.2f}"])
        writer.writerow(["p95_latency_us", f"{result.p95_latency_us:.2f}"])
        writer.writerow(["p99_latency_us", f"{result.p99_latency_us:.2f}"])


def plot_latency_histogram(result: PerfResult, path: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.hist(result.latencies_us, bins=40, color="#8B1A1A", edgecolor="white")
    ax.axvline(result.p50_latency_us, color="black", linestyle="--", linewidth=1, label=f"p50={result.p50_latency_us:.0f}us")
    ax.axvline(result.p95_latency_us, color="gray", linestyle="--", linewidth=1, label=f"p95={result.p95_latency_us:.0f}us")
    ax.axvline(result.p99_latency_us, color="darkgray", linestyle="--", linewidth=1, label=f"p99={result.p99_latency_us:.0f}us")
    ax.set_xlabel("Latency (microseconds)")
    ax.set_ylabel("Operation count")
    ax.set_title(f"Storage Op Latency Distribution — {result.total_ops} ops, {result.iops:.0f} IOPS")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
