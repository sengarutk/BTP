"""Publication-Grade Visualization Suite for 5G Channel Emulation (IEEE Style, 300 DPI).

Generates:
1. experiments/results/5g_blackout_timeline.png
   Multi-panel time-series (0 to 120s): Bandwidth (Mbps), E2E Latency (ms), and Queue Depth / Drops.
2. experiments/results/5g_fps_vs_channel.png
   Grouped Bar Chart: Sustained Receiver FPS across Good, Moderate, Fading, and Blackout channels.
3. experiments/results/5g_crossover_advantage.png
   Empirical CDF of frame delivery latency comparing k4-INT8, k9-INT8, and Monolithic offload.
"""

import json
import logging
import os
import sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parent.parent
FIGURES_DIR = REPO_ROOT / "paper" / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)
from typing import Any, Dict, List


import matplotlib.pyplot as plt
import numpy as np

from utils.logger import get_logger

logger = get_logger("Plot5GTraces")

from evaluation.benchmark_5g_traces import (
    run_pipeline_simulation,
    CONFIGS,
    CHANNEL_TRACES,
)
from simulation.channel_proxy import load_trace_csv

# Publication Quality Styling
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10.5,
    "axes.labelsize": 12,
    "axes.titlesize": 13,
    "xtick.labelsize": 10.5,
    "ytick.labelsize": 10.5,
    "legend.fontsize": 10,
    "figure.titlesize": 15,
    "lines.linewidth": 2.0,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "axes.grid": True,
    "grid.alpha": 0.35,
    "grid.linestyle": "--",
})

RESULTS_DIR = Path("experiments/results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
JSON_PATH = RESULTS_DIR / "5g_trace_benchmark_results.json"


def plot_blackout_timeline() -> None:
    """Figure 1: Multi-panel time series showing Bandwidth, E2E Latency, and Queue Dynamics during Blackouts."""
    records_blackout = load_trace_csv(Path("traces/trace_5g_blackout.csv"))

    cfg_k4 = next(c for c in CONFIGS if c["id"] == "k4_int8_per_tensor")
    cfg_k9 = next(c for c in CONFIGS if c["id"] == "k9_int8_per_tensor")
    cfg_mono = next(c for c in CONFIGS if c["id"] == "monolithic_cloud_offload")

    _, tele_k4 = run_pipeline_simulation(cfg_k4, records_blackout, duration_s=120.0, input_fps=30.0)
    _, tele_k9 = run_pipeline_simulation(cfg_k9, records_blackout, duration_s=120.0, input_fps=30.0)
    _, tele_mono = run_pipeline_simulation(cfg_mono, records_blackout, duration_s=120.0, input_fps=30.0)

    time_sec = [t["timestamp_ms"] / 1000.0 for t in tele_k4]
    bw_mbps = [t["channel_bw_mbps"] for t in tele_k4]

    e2e_k4 = [t["t_e2e_total_ms"] if t["t_e2e_total_ms"] is not None else np.nan for t in tele_k4]
    e2e_k9 = [t["t_e2e_total_ms"] if t["t_e2e_total_ms"] is not None else np.nan for t in tele_k9]
    e2e_mono = [t["t_e2e_total_ms"] if t["t_e2e_total_ms"] is not None else np.nan for t in tele_mono]

    q_k4 = [t["queue_depth"] for t in tele_k4]
    q_k9 = [t["queue_depth"] for t in tele_k9]
    q_mono = [t["queue_depth"] for t in tele_mono]

    fig, (ax_bw, ax_lat, ax_q) = plt.subplots(3, 1, figsize=(13, 8.5), sharex=True, gridspec_kw={"height_ratios": [1, 1.4, 1.1]})

    # Panel 1: Instantaneous Bandwidth
    ax_bw.plot(time_sec, bw_mbps, color="#2980b9", linewidth=2.0, label="5G Channel Bandwidth $B(t)$")
    ax_bw.axvspan(30, 33, color="#e74c3c", alpha=0.25, label="Blackout Window (0 Mbps)")
    ax_bw.axvspan(75, 78, color="#e74c3c", alpha=0.25)
    ax_bw.set_ylabel("Bandwidth (Mbps)", fontweight="bold")
    ax_bw.set_title("A: Dynamic 5G Channel Bandwidth Profile with Sudden Blackout Events", fontweight="bold", pad=8)
    ax_bw.legend(loc="upper right", frameon=True)
    ax_bw.set_ylim(-2, 55)

    # Panel 2: E2E Latency Timeline
    ax_lat.plot(time_sec, e2e_k4, color="#27ae60", linewidth=2.2, label="Split $k_4$-INT8 (800 KiB)")
    ax_lat.plot(time_sec, e2e_k9, color="#e67e22", linewidth=2.0, alpha=0.85, label="Split $k_9$-INT8 (1400 KiB)")
    ax_lat.plot(time_sec, e2e_mono, color="#8e44ad", linewidth=2.0, alpha=0.85, label="Monolithic Raw Offload (1200 KiB)")
    ax_lat.axvspan(30, 33, color="#e74c3c", alpha=0.25)
    ax_lat.axvspan(75, 78, color="#e74c3c", alpha=0.25)
    ax_lat.set_ylabel("E2E Latency (ms)", fontweight="bold")
    ax_lat.set_title("B: End-to-End Perception Latency Across Streaming Pipelines", fontweight="bold", pad=8)
    ax_lat.legend(loc="upper right", frameon=True)
    ax_lat.set_ylim(0, 1200)

    # Panel 3: Queue Depth & Buffer Congestion
    ax_q.plot(time_sec, q_k4, color="#27ae60", linewidth=2.0, label="Queue Depth ($k_4$-INT8)")
    ax_q.plot(time_sec, q_k9, color="#e67e22", linewidth=1.8, linestyle="--", label="Queue Depth ($k_9$-INT8)")
    ax_q.plot(time_sec, q_mono, color="#8e44ad", linewidth=1.8, linestyle=":", label="Queue Depth (Monolithic)")
    ax_q.axvspan(30, 33, color="#e74c3c", alpha=0.25)
    ax_q.axvspan(75, 78, color="#e74c3c", alpha=0.25)
    ax_q.set_xlabel("Elapsed Mission Time (s)", fontweight="bold")
    ax_q.set_ylabel("Buffer Queue Depth", fontweight="bold")
    ax_q.set_title("C: Edge Transmitter Queue Congestion & Backpressure Accumulation", fontweight="bold", pad=8)
    ax_q.legend(loc="upper right", frameon=True)
    ax_q.set_ylim(0, 35)

    out_path = RESULTS_DIR / "5g_blackout_timeline.png"
    plt.tight_layout()
    plt.savefig(out_path, dpi=300)
    fig_path = FIGURES_DIR / out_path.name
    plt.savefig(fig_path, dpi=300)
    plt.close()
    logger.info(f"Generated Figure 1 -> {out_path}")


def plot_fps_vs_channel(summaries: List[Dict[str, Any]]) -> None:
    """Figure 2: Grouped bar chart comparing sustained receiver FPS across 4 channel profiles."""
    fig, ax = plt.subplots(figsize=(11, 6))

    channel_keys = ["good", "moderate", "vehicular_fading", "blackout"]
    channel_labels = ["Good 5G Link\n(50-100 Mbps)", "Urban Mobile\n(12-28 Mbps)", "Vehicular Fading\n(2-45 Mbps)", "Deep Blackout\n(3s Dropouts)"]

    configs_to_plot = [
        ("k4_int8_per_tensor", "Split $k_4$-INT8", "#27ae60"),
        ("k9_int8_per_tensor", "Split $k_9$-INT8", "#e67e22"),
        ("monolithic_cloud_offload", "Monolithic Raw Offload", "#8e44ad"),
    ]

    x = np.arange(len(channel_keys))
    width = 0.25

    for i, (cfg_id, label, color) in enumerate(configs_to_plot):
        fps_vals = []
        for ch in channel_keys:
            rec = next((s for s in summaries if s["channel_key"] == ch and s["config_id"] == cfg_id), None)
            fps_vals.append(rec["effective_fps"] if rec else 0.0)

        offset = (i - 1) * width
        bars = ax.bar(x + offset, fps_vals, width, label=label, color=color, alpha=0.88, edgecolor="black", linewidth=1.1)

        # Bar value labels
        for b in bars:
            height = b.get_height()
            ax.annotate(
                f"{height:.1f}",
                xy=(b.get_x() + b.get_width() / 2, height),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=9.5,
                fontweight="bold",
            )

    ax.set_xticks(x)
    ax.set_xticklabels(channel_labels, fontweight="bold")
    ax.set_ylabel("Effective Sustained Receiver Frame Rate (FPS)", fontweight="bold")
    ax.set_title("Sustained Frame Rate Delivery Under Dynamic 5G Propagation Conditions\n(Source Input: 30.0 FPS)", fontweight="bold", pad=12)
    ax.set_ylim(0, 36)
    ax.axhline(30.0, color="#7f8c8d", linestyle="--", linewidth=1.5, label="Source Video Stream (30.0 FPS)")
    ax.legend(loc="upper right", frameon=True, facecolor="white", edgecolor="#bdc3c7")

    out_path = RESULTS_DIR / "5g_fps_vs_channel.png"
    plt.tight_layout()
    plt.savefig(out_path, dpi=300)
    fig_path = FIGURES_DIR / out_path.name
    plt.savefig(fig_path, dpi=300)
    plt.close()
    logger.info(f"Generated Figure 2 -> {out_path}")


def plot_crossover_advantage() -> None:
    """Figure 3: Empirical CDF of frame delivery latency demonstrating split computing resilience."""
    records_moderate = load_trace_csv(Path("traces/trace_5g_moderate.csv"))

    cfg_k4 = next(c for c in CONFIGS if c["id"] == "k4_int8_per_tensor")
    cfg_k9 = next(c for c in CONFIGS if c["id"] == "k9_int8_per_tensor")
    cfg_mono = next(c for c in CONFIGS if c["id"] == "monolithic_cloud_offload")

    _, tele_k4 = run_pipeline_simulation(cfg_k4, records_moderate, duration_s=120.0, input_fps=30.0)
    _, tele_k9 = run_pipeline_simulation(cfg_k9, records_moderate, duration_s=120.0, input_fps=30.0)
    _, tele_mono = run_pipeline_simulation(cfg_mono, records_moderate, duration_s=120.0, input_fps=30.0)

    lat_k4 = np.sort([t["t_e2e_total_ms"] for t in tele_k4 if t["t_e2e_total_ms"] is not None])
    lat_k9 = np.sort([t["t_e2e_total_ms"] for t in tele_k9 if t["t_e2e_total_ms"] is not None])
    lat_mono = np.sort([t["t_e2e_total_ms"] for t in tele_mono if t["t_e2e_total_ms"] is not None])

    cdf_k4 = np.arange(1, len(lat_k4) + 1) / len(lat_k4)
    cdf_k9 = np.arange(1, len(lat_k9) + 1) / len(lat_k9)
    cdf_mono = np.arange(1, len(lat_mono) + 1) / len(lat_mono)

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.plot(lat_k4, cdf_k4, color="#27ae60", label=f"Split $k_4$-INT8 (P95 = {np.percentile(lat_k4, 95):.1f} ms)", linewidth=2.5)
    ax.plot(lat_mono, cdf_mono, color="#8e44ad", label=f"Monolithic Raw Offload (P95 = {np.percentile(lat_mono, 95):.1f} ms)", linewidth=2.2, linestyle="--")
    ax.plot(lat_k9, cdf_k9, color="#e67e22", label=f"Split $k_9$-INT8 (P95 = {np.percentile(lat_k9, 95):.1f} ms)", linewidth=2.2, linestyle=":")

    ax.axvline(np.percentile(lat_k4, 95), color="#27ae60", linestyle=":", alpha=0.7)
    ax.axvline(np.percentile(lat_mono, 95), color="#8e44ad", linestyle=":", alpha=0.7)

    ax.set_xlabel("End-to-End Perception Latency (ms)", fontweight="bold")
    ax.set_ylabel("Cumulative Empirical Probability P(Latency $\\leq$ L)", fontweight="bold")
    ax.set_title("Empirical Latency CDF Under Urban Mobile 5G Channel\nDemonstrating Split $k_4$ Latency Reduction", fontweight="bold", pad=12)
    ax.legend(loc="lower right", frameon=True, facecolor="white", edgecolor="#bdc3c7")

    out_path = RESULTS_DIR / "5g_crossover_advantage.png"
    plt.tight_layout()
    plt.savefig(out_path, dpi=300)
    fig_path = FIGURES_DIR / out_path.name
    plt.savefig(fig_path, dpi=300)
    plt.close()
    logger.info(f"Generated Figure 3 -> {out_path}")


def main() -> None:
    if not JSON_PATH.exists():
        logger.error(f"Cannot find {JSON_PATH}. Running benchmark_5g_traces.py first...")
        from evaluation.benchmark_5g_traces import run_5g_benchmark_suite
        run_5g_benchmark_suite()

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    summaries = data["summaries"]

    logger.info("Generating publication figures for 5G Channel Emulation...")
    plot_blackout_timeline()
    plot_fps_vs_channel(summaries)
    plot_crossover_advantage()
    logger.info("All 3 5G publication figures generated successfully!")


if __name__ == "__main__":
    main()
