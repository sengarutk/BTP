"""Comprehensive Dynamic 5G Trace Benchmarking Suite.

Evaluates 5 offloading configurations under 4 real-world 3GPP 5G channel trace profiles:
1. Split k4 - INT8 Per-Tensor (800.0 KiB)
2. Split k4 - INT8 Per-Channel (800.5 KiB)
3. Split k9 - INT8 Per-Tensor (1400.1 KiB)
4. Split k9 - INT8 Per-Channel (1403.6 KiB)
5. Monolithic Cloud Offload (Raw Image: 1200.0 KiB)

Across 4 Channels:
- Good 5G Channel (50-100 Mbps, 8-12ms, 0% loss)
- Urban Mobile / Moderate (12-28 Mbps, 18-38ms, 0.5% loss)
- Deep Fading & Blackout (35 Mbps -> 0 Mbps for 3.0s dropouts)
- Vehicular Fast Fading (2-45 Mbps Rayleigh/Rician multipath)
"""

import argparse
import csv
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple


import numpy as np
import torch
from tabulate import tabulate

from utils.logger import get_logger

logger = get_logger("Benchmark5G")

from simulation.channel_proxy import load_trace_csv
from simulation.netem_controller import UserSpaceRateLimiter
from simulation.trace_generator import generate_all_traces, TRACES_DIR

RESULTS_DIR = Path("experiments/results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
JSON_EXPORT_PATH = RESULTS_DIR / "5g_trace_benchmark_results.json"
CSV_EXPORT_PATH = RESULTS_DIR / "5g_trace_benchmark_results.csv"

# Configuration Payload Footprints and Edge/Cloud Compute Latencies (from Track 1.1/1.2 microbenchmarks)
CONFIGS = [
    {
        "id": "k4_int8_per_tensor",
        "name": "Split k4 - INT8 (Per-Tensor)",
        "split": "k4",
        "dtype": "int8_per_tensor",
        "payload_bytes": 800 * 1024,
        "t_edge_compute_ms": 1.25,
        "t_cloud_compute_ms": 5.56,
    },
    {
        "id": "k4_int8_per_channel",
        "name": "Split k4 - INT8 (Per-Channel)",
        "split": "k4",
        "dtype": "int8_per_channel",
        "payload_bytes": int(800.5 * 1024),
        "t_edge_compute_ms": 1.30,
        "t_cloud_compute_ms": 5.58,
    },
    {
        "id": "k9_int8_per_tensor",
        "name": "Split k9 - INT8 (Per-Tensor)",
        "split": "k9",
        "dtype": "int8_per_tensor",
        "payload_bytes": int(1400.1 * 1024),
        "t_edge_compute_ms": 4.10,
        "t_cloud_compute_ms": 2.71,
    },
    {
        "id": "k9_int8_per_channel",
        "name": "Split k9 - INT8 (Per-Channel)",
        "split": "k9",
        "dtype": "int8_per_channel",
        "payload_bytes": int(1403.6 * 1024),
        "t_edge_compute_ms": 4.15,
        "t_cloud_compute_ms": 2.73,
    },
    {
        "id": "monolithic_cloud_offload",
        "name": "Monolithic Cloud Offload (Raw Image)",
        "split": "monolithic",
        "dtype": "raw_image",
        "payload_bytes": 1200 * 1024,  # Raw preprocessed 640x640x3 image frame
        "t_edge_compute_ms": 0.10,      # Zero edge DNN compute
        "t_cloud_compute_ms": 6.81,     # Full YOLOv8s monolithic inference
    },
]

CHANNEL_TRACES = [
    ("good", "Good 5G Link (50-100 Mbps)", "traces/trace_5g_good.csv"),
    ("moderate", "Urban Mobile / Moderate (12-28 Mbps)", "traces/trace_5g_moderate.csv"),
    ("blackout", "Deep Fading & Blackout", "traces/trace_5g_blackout.csv"),
    ("vehicular_fading", "Vehicular Fast Fading (2-45 Mbps)", "traces/trace_5g_vehicular_fading.csv"),
]


def run_pipeline_simulation(
    config: Dict[str, Any],
    trace_records: List[Dict[str, float]],
    duration_s: float = 120.0,
    input_fps: float = 30.0,
    max_queue_depth: int = 30,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Simulates end-to-end streaming of a 30 FPS video source across time-varying 5G trace."""
    shaper = UserSpaceRateLimiter(max_queue_depth=max_queue_depth)
    shaper.reset()

    frame_interval_ms = 1000.0 / input_fps
    total_frames = int(duration_s * input_fps)
    trace_len = len(trace_records)

    frame_telemetry: List[Dict[str, Any]] = []
    delivered_frames = 0
    dropped_frames = 0
    e2e_latencies = []
    tx_latencies = []
    congestion_durations = 0.0

    for f_idx in range(total_frames):
        src_timestamp_ms = f_idx * frame_interval_ms

        # Map to trace state (10ms resolution)
        trace_idx = int(src_timestamp_ms / 10.0) % trace_len
        ch_state = trace_records[trace_idx]

        # 1. Edge Compute Stage
        t_edge = config["t_edge_compute_ms"]

        # 2. Network Emulation Stage
        net_res = shaper.emulate_packet_transmission(config["payload_bytes"], ch_state)

        # 3. Cloud Compute Stage
        if net_res["delivered"]:
            t_cloud = config["t_cloud_compute_ms"]
            t_e2e = t_edge + net_res["t_total_net_ms"] + t_cloud
            delivered_frames += 1
            e2e_latencies.append(t_e2e)
            tx_latencies.append(net_res["t_tx_ms"])
            dropped = False
            drop_reason = "none"
        else:
            t_cloud = 0.0
            t_e2e = float("nan")
            dropped_frames += 1
            dropped = True
            drop_reason = net_res["drop_reason"]

        if net_res["queue_depth"] > 5:
            congestion_durations += frame_interval_ms / 1000.0

        record = {
            "config_id": config["id"],
            "frame_id": f_idx + 1,
            "timestamp_ms": round(src_timestamp_ms, 1),
            "channel_bw_mbps": ch_state["bandwidth_mbps"],
            "channel_delay_ms": ch_state["delay_ms"],
            "payload_kib": net_res["payload_kib"],
            "t_edge_ms": round(t_edge, 2),
            "t_tx_ms": round(net_res["t_tx_ms"], 2),
            "t_prop_delay_ms": round(net_res["t_prop_delay_ms"], 2),
            "t_net_total_ms": round(net_res["t_total_net_ms"], 2),
            "t_cloud_ms": round(t_cloud, 2),
            "t_e2e_total_ms": round(t_e2e, 2) if not np.isnan(t_e2e) else None,
            "queue_depth": net_res["queue_depth"],
            "dropped": dropped,
            "drop_reason": drop_reason,
        }
        frame_telemetry.append(record)

    delivery_rate_pct = (delivered_frames / total_frames) * 100.0
    effective_fps = delivered_frames / duration_s

    valid_e2e = [x for x in e2e_latencies if not np.isnan(x)]
    p50_e2e = float(np.percentile(valid_e2e, 50)) if valid_e2e else float("nan")
    p95_e2e = float(np.percentile(valid_e2e, 95)) if valid_e2e else float("nan")
    p99_e2e = float(np.percentile(valid_e2e, 99)) if valid_e2e else float("nan")
    mean_e2e = float(np.mean(valid_e2e)) if valid_e2e else float("nan")
    std_e2e = float(np.std(valid_e2e)) if valid_e2e else float("nan")
    mean_tx = float(np.mean(tx_latencies)) if tx_latencies else float("nan")

    summary = {
        "config_id": config["id"],
        "config_name": config["name"],
        "total_frames": total_frames,
        "delivered_frames": delivered_frames,
        "dropped_frames": dropped_frames,
        "delivery_rate_pct": round(delivery_rate_pct, 2),
        "effective_fps": round(effective_fps, 2),
        "mean_tx_ms": round(mean_tx, 2),
        "mean_e2e_ms": round(mean_e2e, 2),
        "std_e2e_ms": round(std_e2e, 2),
        "p50_e2e_ms": round(p50_e2e, 2),
        "p95_e2e_ms": round(p95_e2e, 2),
        "p99_e2e_ms": round(p99_e2e, 2),
        "congestion_duration_s": round(congestion_durations, 2),
    }

    return summary, frame_telemetry


def run_5g_benchmark_suite(duration_s: float = 120.0, quick: bool = False) -> Dict[str, Any]:
    """Executes the full 5G Trace Benchmarking Suite."""
    if quick:
        duration_s = 30.0

    logger.info(f"Initiating 5G Channel Trace Benchmark Suite (Duration: {duration_s}s, Quick: {quick})")

    # Ensure traces exist
    generate_all_traces()

    all_summaries: List[Dict[str, Any]] = []
    all_telemetry: List[Dict[str, Any]] = []

    for trace_key, trace_name, trace_file in CHANNEL_TRACES:
        logger.info(f"\n--- Benchmarking Channel Profile: [{trace_name}] ---")
        records = load_trace_csv(Path(trace_file))

        for cfg in CONFIGS:
            summary, telemetry = run_pipeline_simulation(
                config=cfg,
                trace_records=records,
                duration_s=duration_s,
                input_fps=30.0,
            )
            summary["channel_key"] = trace_key
            summary["channel_name"] = trace_name
            all_summaries.append(summary)

            for t in telemetry:
                t["channel_key"] = trace_key
                all_telemetry.append(t)

            logger.info(
                f"  [{cfg['name']:<38}] -> Delivery: {summary['delivery_rate_pct']:>6.2f}%, "
                f"FPS: {summary['effective_fps']:>5.2f}, Mean E2E: {summary['mean_e2e_ms']:>6.2f} ms, "
                f"P95 E2E: {summary['p95_e2e_ms']:>6.2f} ms, Mean Tx: {summary['mean_tx_ms']:>6.2f} ms"
            )

    # Export Full JSON
    final_output = {
        "metadata": {
            "title": "AEGIS-UAV 5G Channel Trace Benchmarking Suite",
            "duration_s": duration_s,
            "input_fps": 30.0,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "summaries": all_summaries,
        "sample_telemetry": all_telemetry[:500],  # Sample for inspection
    }

    with open(JSON_EXPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=2)
    logger.info(f"Exported 5G Trace Benchmark JSON -> {JSON_EXPORT_PATH}")

    # Export Full CSV
    csv_headers = [
        "channel_key", "channel_name", "config_id", "config_name",
        "total_frames", "delivered_frames", "dropped_frames",
        "delivery_rate_pct", "effective_fps",
        "mean_tx_ms", "mean_e2e_ms", "std_e2e_ms", "p50_e2e_ms", "p95_e2e_ms", "p99_e2e_ms",
        "congestion_duration_s"
    ]

    with open(CSV_EXPORT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_headers)
        writer.writeheader()
        for s in all_summaries:
            writer.writerow({k: s.get(k, "") for k in csv_headers})
    logger.info(f"Exported 5G Trace Benchmark CSV -> {CSV_EXPORT_PATH}")

    # Print Pretty Summary Table
    table_rows = []
    for s in all_summaries:
        table_rows.append([
            s["channel_name"][:20],
            s["config_name"][:30],
            f"{s['delivery_rate_pct']:.1f}%",
            f"{s['effective_fps']:.1f}",
            f"{s['mean_tx_ms']:.1f} ms",
            f"{s['mean_e2e_ms']:.1f} ± {s['std_e2e_ms']:.1f}",
            f"{s['p95_e2e_ms']:.1f} ms",
            f"{s['congestion_duration_s']:.1f}s",
        ])

    headers = [
        "Channel Profile", "Pipeline Configuration", "Delivery", "FPS", "Mean Tx", "Mean E2E Lat (ms)", "P95 E2E", "Congestion"
    ]

    print("\n" + "=" * 135)
    print("                        AEGIS-UAV DYNAMIC 5G TRACE BENCHMARK SUMMARY")
    print("=" * 135)
    print(tabulate(table_rows, headers=headers, tablefmt="fancy_grid"))
    print("=" * 135 + "\n")

    return final_output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run 5G Channel Trace Benchmark Suite")
    parser.add_argument("--duration", type=float, default=120.0, help="Simulation duration in seconds")
    parser.add_argument("--quick", action="store_true", help="Quick mode (30s duration)")
    args = parser.parse_args()

    run_5g_benchmark_suite(duration_s=args.duration, quick=args.quick)
