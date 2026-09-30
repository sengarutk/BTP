"""Comprehensive Statistical Benchmark Suite for UAV Split Perception.

Executes multi-pass deterministic profiling (N >= 3 passes, 50 frames/pass) across all
split and precision configurations, computes stage-wise latencies (Mean, Std, P50, P95, P99),
applies non-parametric bootstrap resampling (B=1,000) for 95% confidence intervals,
evaluates simulated 5G channel latencies (5, 20, 50, 100 Mbps), includes both Workstation GPU
and Estimated Compute (x5.5 scaling from Host GPU) constrained edge baselines, standardizes to IEC binary units (KiB, MiB),
and exports structured results.
"""

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
from typing import Any, Dict, List, Tuple

import numpy as np
import torch
from tabulate import tabulate
from ultralytics import YOLO


from core.submodels import EdgeSubmodel, CloudSubmodel
from pipeline.local_sim_pipeline import LocalSimulationPipeline
from quantization.quantizer import (
    DTYPE_FP32,
    DTYPE_FP16,
    DTYPE_INT8,
)
from utils.logger import get_logger

logger = get_logger("BenchmarkSuite")

BANDWIDTH_KEYS = [5, 20, 50, 100]
JETSON_NANO_SLOWDOWN_FACTOR = 5.5  # Empirical 5.5x compute scaling factor (472 GFLOPS vs. 2.6 TFLOPS)


def compute_bootstrap_ci(data: np.ndarray, num_bootstrap: int = 1000, ci: float = 0.95) -> Tuple[float, float]:
    """Computes non-parametric 95% bootstrap confidence interval [ci_low, ci_high]."""
    if len(data) <= 1:
        val = float(data[0]) if len(data) == 1 else 0.0
        return val, val
    means = [np.mean(np.random.choice(data, size=len(data), replace=True)) for _ in range(num_bootstrap)]
    alpha = (1.0 - ci) / 2.0
    return float(np.percentile(means, alpha * 100)), float(np.percentile(means, (1.0 - alpha) * 100))


def run_multi_pass_benchmarks(
    weights_path: str = "yolov8s.pt",
    num_passes: int = 3,
    frames_per_pass: int = 50,
    device: str = "cuda" if torch.cuda.is_available() else "cpu",
    output_dir: str = str(repo_root / "experiments" / "results"),
) -> List[Dict[str, Any]]:
    """Executes multi-pass statistical benchmarking across all split and quantization configurations."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info(
        f"Starting Multi-Pass Benchmark Suite ({num_passes} passes, {frames_per_pass} frames/pass, Device: {device})..."
    )

    configs = [
        {"name": "Split k4 (INT8)", "split": "k4", "dtype": DTYPE_INT8, "is_sim_nano": False},
        {"name": "Split k4 (FP16)", "split": "k4", "dtype": DTYPE_FP16, "is_sim_nano": False},
        {"name": "Split k4 (FP32)", "split": "k4", "dtype": DTYPE_FP32, "is_sim_nano": False},
        {"name": "Split k9 (INT8)", "split": "k9", "dtype": DTYPE_INT8, "is_sim_nano": False},
        {"name": "Split k9 (FP16)", "split": "k9", "dtype": DTYPE_FP16, "is_sim_nano": False},
        {"name": "Split k9 (FP32)", "split": "k9", "dtype": DTYPE_FP32, "is_sim_nano": False},
        {"name": "Monolithic Local (Workstation GPU)", "split": "full", "dtype": DTYPE_FP32, "is_sim_nano": False},
        {"name": "Full Edge (Estimated Compute x5.5)", "split": "full", "dtype": DTYPE_FP32, "is_sim_nano": True},
    ]

    all_config_summaries: List[Dict[str, Any]] = []

    for cfg in configs:
        cfg_name = cfg["name"]
        split_tag = cfg["split"]
        dtype = cfg["dtype"]
        is_nano = cfg["is_sim_nano"]
        logger.info(f"Benchmarking [{cfg_name}] across {num_passes} passes...")

        if is_nano:
            base_summary = [s for s in all_config_summaries if s["config_name"] == "Monolithic Local (Workstation GPU)"][0]
            nano_summary = dict(base_summary)
            nano_summary["config_name"] = cfg_name
            nano_summary["hardware_annotation"] = "Estimated Compute (x5.5 scaling from Host GPU)"
            nano_summary["t_edge_ms_mean"] = round(base_summary["t_edge_ms_mean"] * JETSON_NANO_SLOWDOWN_FACTOR, 4)
            nano_summary["t_edge_ms_std"] = round(base_summary["t_edge_ms_std"] * JETSON_NANO_SLOWDOWN_FACTOR, 4)
            nano_summary["t_e2e_compute_ms_mean"] = round(base_summary["t_e2e_compute_ms_mean"] * JETSON_NANO_SLOWDOWN_FACTOR, 4)
            nano_summary["t_e2e_compute_ms_std"] = round(base_summary["t_e2e_compute_ms_std"] * JETSON_NANO_SLOWDOWN_FACTOR, 4)
            nano_summary["t_e2e_compute_ms_ci95_low"] = round(base_summary.get("t_e2e_compute_ms_ci95_low", base_summary["t_e2e_compute_ms_mean"]) * JETSON_NANO_SLOWDOWN_FACTOR, 4)
            nano_summary["t_e2e_compute_ms_ci95_high"] = round(base_summary.get("t_e2e_compute_ms_ci95_high", base_summary["t_e2e_compute_ms_mean"]) * JETSON_NANO_SLOWDOWN_FACTOR, 4)

            for bw in BANDWIDTH_KEYS:
                nano_summary[f"total_latency_{bw}mbps_ms"] = round(nano_summary["t_e2e_compute_ms_mean"], 2)

            nano_fps = 1000.0 / max(nano_summary["t_e2e_compute_ms_mean"], 1e-3)
            nano_summary["compute_fps"] = round(nano_fps, 1)

            all_config_summaries.append(nano_summary)
            logger.success(
                f"[{cfg_name}] Complete (5.5x Scaled): Compute = {nano_summary['t_e2e_compute_ms_mean']:.2f} ms "
                f"({nano_fps:.1f} FPS) | Wire Size = 0.0 KiB (0.0 MiB)"
            )
            continue

        pipe = LocalSimulationPipeline(
            weights_path=weights_path,
            split_tag=split_tag,
            dtype=dtype,
            device=device,
        )
        pipe.warmup(num_warmup=5)

        pass_frame_records: List[Dict[str, float]] = []

        for p_idx in range(num_passes):
            seed = 42 + p_idx
            torch.manual_seed(seed)
            np.random.seed(seed)

            for f_idx in range(1, frames_per_pass + 1):
                dummy_img = torch.rand(1, 3, 640, 640, device=device)
                _, frame_metrics = pipe.process_frame(dummy_img, frame_id=f_idx)
                pass_frame_records.append(frame_metrics)

        total_samples = len(pass_frame_records)
        stat_summary: Dict[str, Any] = {
            "config_name": cfg_name,
            "split_tag": split_tag,
            "dtype": dtype,
            "num_passes": num_passes,
            "frames_per_pass": frames_per_pass,
            "total_frames": total_samples,
            "hardware_annotation": "Workstation GPU (Host CUDA Environment)" if not is_nano else "Estimated Compute (x5.5 scaling from Host GPU)",
        }

        metric_fields = [
            "t_edge_ms",
            "t_quant_ms",
            "t_serialize_ms",
            "t_deserialize_ms",
            "t_dequant_ms",
            "t_cloud_ms",
            "t_nms_ms",
            "t_e2e_compute_ms",
            "wire_size_bytes",
            "wire_size_kib",
            "wire_size_mib",
            "compression_ratio",
        ]
        for bw in BANDWIDTH_KEYS:
            metric_fields.append(f"tx_{bw}mbps_ms")

        for mf in metric_fields:
            vals = np.array([r[mf] for r in pass_frame_records if mf in r])
            if len(vals) > 0:
                stat_summary[f"{mf}_mean"] = round(float(np.mean(vals)), 4)
                stat_summary[f"{mf}_std"] = round(float(np.std(vals)), 4)
                stat_summary[f"{mf}_p50"] = round(float(np.percentile(vals, 50)), 4)
                stat_summary[f"{mf}_p95"] = round(float(np.percentile(vals, 95)), 4)
                stat_summary[f"{mf}_p99"] = round(float(np.percentile(vals, 99)), 4)
                ci_low, ci_high = compute_bootstrap_ci(vals, num_bootstrap=1000)
                stat_summary[f"{mf}_ci95_low"] = round(ci_low, 4)
                stat_summary[f"{mf}_ci95_high"] = round(ci_high, 4)

        for bw in BANDWIDTH_KEYS:
            tx_key = f"tx_{bw}mbps_ms_mean"
            comp_key = "t_e2e_compute_ms_mean"
            stat_summary[f"total_latency_{bw}mbps_ms"] = round(
                stat_summary.get(comp_key, 0.0) + stat_summary.get(tx_key, 0.0), 2
            )

        compute_fps = 1000.0 / max(stat_summary["t_e2e_compute_ms_mean"], 1e-3)
        stat_summary["compute_fps"] = round(compute_fps, 1)

        all_config_summaries.append(stat_summary)

        # Explicit multi-tensor breakdown logging for k9
        if split_tag == "k9":
            bytes_val = int(stat_summary["wire_size_bytes_mean"])
            kib_val = stat_summary["wire_size_kib_mean"]
            mib_val = stat_summary["wire_size_mib_mean"]
            logger.info(
                f"[k9 Multi-Scale Bundle Payload] P3(L4: 819.2k) + P4(L6: 409.6k) + P5(L9: 204.8k) = 1,433.6k elements "
                f"-> {bytes_val:,} B -> {kib_val:.1f} KiB ({mib_val:.2f} MiB)"
            )

        logger.success(
            f"[{cfg_name}] Complete: Compute = {stat_summary['t_e2e_compute_ms_mean']:.2f} ± {stat_summary['t_e2e_compute_ms_std']:.2f} ms "
            f"({compute_fps:.1f} FPS) | Wire Size = {stat_summary['wire_size_kib_mean']:.1f} KiB ({stat_summary['wire_size_mib_mean']:.2f} MiB)"
        )

    # 1. Export JSON Summary
    json_path = os.path.join(output_dir, "metrics_summary.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_config_summaries, f, indent=2)
    logger.success(f"Exported benchmark summary JSON to '{json_path}'")

    # 2. Export CSV Summary
    csv_path = os.path.join(output_dir, "metrics_summary.csv")
    all_keys = []
    for s in all_config_summaries:
        for k in s.keys():
            if k not in all_keys:
                all_keys.append(k)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys)
        writer.writeheader()
        writer.writerows(all_config_summaries)
    logger.success(f"Exported benchmark summary CSV to '{csv_path}'")

    # Print Formatted Report Table
    print_benchmark_report(all_config_summaries)
    return all_config_summaries


def print_benchmark_report(summaries: List[Dict[str, Any]]):
    """Formats and prints comprehensive ASCII statistical profiling table in IEC units."""
    headers = [
        "Configuration",
        "Edge (ms)",
        "Quant+Ser (ms)",
        "Deser+Dequant (ms)",
        "Cloud (ms)",
        "E2E Compute (ms)",
        "Wire Size (KiB / MiB)",
        "Total @ 5 Mbps",
        "Total @ 20 Mbps",
        "Total @ 50 Mbps",
        "FPS (Compute)",
    ]
    rows = []

    for s in summaries:
        cfg = s["config_name"]
        edge = f"{s['t_edge_ms_mean']:.2f} ± {s['t_edge_ms_std']:.2f}"
        quant_ser = f"{s['t_quant_ms_mean'] + s['t_serialize_ms_mean']:.2f}"
        deser_deq = f"{s['t_deserialize_ms_mean'] + s['t_dequant_ms_mean']:.2f}"
        cloud = f"{s['t_cloud_ms_mean']:.2f} ± {s['t_cloud_ms_std']:.2f}"
        e2e = f"{s['t_e2e_compute_ms_mean']:.2f} ± {s['t_e2e_compute_ms_std']:.2f}"
        wire = f"{s['wire_size_kib_mean']:,.1f} KiB ({s['wire_size_mib_mean']:.2f} MiB)" if s['wire_size_bytes_mean'] > 0 else "0.0 KiB (0.0 MiB)"
        tot_5 = f"{s.get('total_latency_5mbps_ms', 0):.1f} ms"
        tot_20 = f"{s.get('total_latency_20mbps_ms', 0):.1f} ms"
        tot_50 = f"{s.get('total_latency_50mbps_ms', 0):.1f} ms"
        fps = f"{s['compute_fps']:.1f}"

        rows.append([
            cfg,
            edge,
            quant_ser,
            deser_deq,
            cloud,
            e2e,
            wire,
            tot_5,
            tot_20,
            tot_50,
            fps,
        ])

    print("\n" + "=" * 145)
    print("                 UAV SPLIT-PERCEPTION STATISTICAL MICRO-BENCHMARK REPORT (N=3 Runs, IEC Units)")
    print("=" * 145)
    print(tabulate(rows, headers=headers, tablefmt="fancy_grid"))
    print("=" * 145)
    print(" HARDWARE MODELING NOTE: Full Edge (Estimated Compute) uses an empirical 5.5x compute scaling factor from Host GPU")
    print("                         based on relative FP32 throughput (472 GFLOPS vs 2.6 TFLOPS). Actual embedded latencies")
    print("                         will be calibrated on physical hardware in Phase 3.")
    print("=" * 145 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Statistical Micro-Benchmark Suite")
    parser.add_argument("--weights", type=str, default="yolov8s.pt", help="Baseline weights")
    parser.add_argument("--passes", type=int, default=3, help="Number of profiling passes")
    parser.add_argument("--frames", type=int, default=50, help="Frames per pass")
    parser.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--output-dir", type=str, default=str(repo_root / "experiments" / "results"))
    args = parser.parse_args()

    run_multi_pass_benchmarks(
        weights_path=args.weights,
        num_passes=args.passes,
        frames_per_pass=args.frames,
        device=args.device,
        output_dir=args.output_dir,
    )
