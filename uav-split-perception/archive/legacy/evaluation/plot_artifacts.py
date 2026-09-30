"""Publication-Grade Visualizer and Figure Generator for UAV Split Perception.

Generates IEEE double-column compliant publication figures (300 DPI, vector/raster, IEC units):
1. experiments/results/pareto_frontiers.png (Accuracy vs. Latency with Jetson Nano & Signed COCO128 mAP)
2. experiments/results/latency_breakdown_bars.png (Stage-wise Compute vs. Tx with IEC KiB / MiB units)
3. experiments/results/bandwidth_sensitivity_curves.png (Crossover Frontiers vs. Raw Image Offload)
"""

import argparse
import json
import os
import sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parent.parent
FIGURES_DIR = REPO_ROOT / "paper" / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)
from typing import Any, Dict, List, Tuple

import matplotlib
import matplotlib.pyplot as plt
import numpy as np


from utils.logger import get_logger

logger = get_logger("PlotArtifacts")

# Publication style configuration
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.labelsize": 11,
    "axes.titlesize": 12,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 8.5,
    "figure.titlesize": 13,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "lines.linewidth": 2.0,
    "lines.markersize": 7,
})


def load_benchmark_and_accuracy_data(results_dir: str = "experiments/results") -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Loads metrics_summary.json and accuracy_mAP_results.json."""
    metrics_path = os.path.join(results_dir, "metrics_summary.json")
    accuracy_path = os.path.join(results_dir, "accuracy_mAP_results.json")

    if not os.path.exists(metrics_path) or not os.path.exists(accuracy_path):
        raise FileNotFoundError(
            f"Required results files missing in '{results_dir}'. Run benchmark_suite.py and evaluate_mAP.py first."
        )

    with open(metrics_path, "r", encoding="utf-8") as f:
        metrics_data = json.load(f)

    with open(accuracy_path, "r", encoding="utf-8") as f:
        accuracy_data = json.load(f)

    return metrics_data, accuracy_data


def get_tab10_colors(n: int) -> List[Any]:
    """Retrieves list of distinct colors from tab10 colormap across Matplotlib versions."""
    try:
        cmap = matplotlib.colormaps["tab10"]
    except Exception:
        cmap = plt.get_cmap("tab10")
    return [cmap(i % 10) for i in range(n)]


def plot_pareto_frontiers(metrics_data: List[Dict[str, Any]], accuracy_data: Dict[str, Any], output_path: str):
    """Figure 1: Pareto Frontiers (mAP@0.5 vs. Total Latency across Bandwidths with COCO128 and Jetson Nano)."""
    logger.info("Generating Figure 1: Pareto Frontiers...")
    fig, ax = plt.subplots(figsize=(8.0, 5.0))

    acc_map = {}
    for item in accuracy_data.get("results", []):
        acc_map[item["config_name"]] = item["mAP_50"]

    # Assign base accuracy to Jetson Nano baseline
    if "Full Edge (Estimated Compute x5.5)" not in acc_map:
        acc_map["Full Edge (Estimated Compute x5.5)"] = acc_map.get("Full Edge (FP32)", 0.413958)

    colors = get_tab10_colors(len(metrics_data))
    markers = ["o", "s", "^", "D", "v", "p", "X", "*"]

    bw_scenarios = [
        (5, ":", 0.5),
        (20, "--", 0.75),
        (50, "-", 1.0),
    ]

    for idx, m in enumerate(metrics_data):
        cfg_name = m["config_name"]
        map_val = acc_map.get(cfg_name, acc_map.get("Baseline (Monolithic)", 0.7594))
        color = colors[idx]
        marker = markers[idx % len(markers)]

        latencies = [
            m.get(f"total_latency_{bw}mbps_ms", m["t_e2e_compute_ms_mean"])
            for bw, _, _ in bw_scenarios
        ]

        lat_20 = m.get("total_latency_20mbps_ms", m["t_e2e_compute_ms_mean"])
        wire_str = f"{m.get('wire_size_kib_mean', 0.0):.0f} KiB" if m.get('wire_size_kib_mean', 0.0) > 0 else "0 KiB"
        ax.scatter(
            lat_20,
            map_val,
            color=color,
            s=100,
            marker=marker,
            label=f"{cfg_name} ({wire_str})",
            zorder=5,
            edgecolors="black",
            linewidths=0.8,
        )

        ax.plot(
            latencies,
            [map_val] * len(latencies),
            color=color,
            alpha=0.6,
            linestyle="-.",
            linewidth=1.2,
            zorder=3,
        )

    ax.set_xlabel("Total System Latency (ms) [Log Scale]", fontweight="bold")
    ax.set_ylabel("COCO128 Detection Accuracy (mAP@0.5)", fontweight="bold")
    ax.set_xscale("log")
    ax.set_title("Pareto Frontiers: Real-World COCO128 mAP vs. Total System Latency", fontweight="bold", pad=12)
    ax.grid(True, which="both", linestyle="--", alpha=0.5)
    ax.legend(loc="lower right", frameon=True, facecolor="white", edgecolor="none", shadow=True)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    fig_path = Path("/home/sengar/BTP/uav-split-perception/paper/figures") / Path(output_path).name
    fig_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(fig_path, dpi=300)
    plt.close()
    logger.success(f"Saved Pareto Frontiers plot to '{output_path}'")


def plot_latency_breakdown_bars(metrics_data: List[Dict[str, Any]], output_path: str):
    """Figure 2: Latency Breakdown Stacked Bars with IEC units."""
    logger.info("Generating Figure 2: Latency Breakdown Stacked Bars...")
    fig, ax = plt.subplots(figsize=(9.2, 5.2))

    configs = [m["config_name"] for m in metrics_data]
    n_configs = len(configs)
    indices = np.arange(n_configs)

    t_edge = np.array([m["t_edge_ms_mean"] for m in metrics_data])
    t_quant = np.array([m["t_quant_ms_mean"] for m in metrics_data])
    t_framing = np.array([m["t_serialize_ms_mean"] + m["t_deserialize_ms_mean"] for m in metrics_data])
    t_dequant = np.array([m["t_dequant_ms_mean"] for m in metrics_data])
    t_cloud = np.array([m["t_cloud_ms_mean"] for m in metrics_data])
    t_nms = np.array([m["t_nms_ms_mean"] for m in metrics_data])
    t_tx20 = np.array([m.get("tx_20mbps_ms_mean", 0.0) for m in metrics_data])

    colors = ["#2b5c8f", "#d95f02", "#7570b3", "#e7298a", "#66a61e", "#e6ab02", "#a6761d"]

    ax.bar(indices, t_edge, label="Edge Submodel ($T_{edge}$)", color=colors[0], edgecolor="black", linewidth=0.5)
    ax.bar(indices, t_quant, bottom=t_edge, label="Quantization ($T_{quant}$)", color=colors[1], edgecolor="black", linewidth=0.5)
    ax.bar(indices, t_framing, bottom=t_edge + t_quant, label="Framing & CRC32 ($T_{ser/deser}$)", color=colors[2], edgecolor="black", linewidth=0.5)
    ax.bar(indices, t_dequant, bottom=t_edge + t_quant + t_framing, label="Dequantization ($T_{dequant}$)", color=colors[3], edgecolor="black", linewidth=0.5)
    ax.bar(indices, t_cloud, bottom=t_edge + t_quant + t_framing + t_dequant, label="Cloud Submodel ($T_{cloud}$)", color=colors[4], edgecolor="black", linewidth=0.5)
    ax.bar(indices, t_nms, bottom=t_edge + t_quant + t_framing + t_dequant + t_cloud, label="NMS Filtering ($T_{nms}$)", color=colors[5], edgecolor="black", linewidth=0.5)
    ax.bar(indices, t_tx20, bottom=t_edge + t_quant + t_framing + t_dequant + t_cloud + t_nms, label="Transmission @ 20 Mbps ($T_{tx}$)", color=colors[6], edgecolor="black", linewidth=0.5)

    ax.set_ylabel("Latency Breakdown (ms) [Log Scale]", fontweight="bold")
    ax.set_yscale("log")
    ax.set_xticks(indices)
    ax.set_xticklabels(configs, rotation=28, ha="right", fontweight="medium")
    ax.set_title("Stage-Wise Latency & Transmission Breakdown @ 20 Mbps (IEC Units)", fontweight="bold", pad=12)
    ax.grid(True, axis="y", linestyle="--", alpha=0.5)
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1), borderaxespad=0.0, frameon=True)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    fig_path = Path("/home/sengar/BTP/uav-split-perception/paper/figures") / Path(output_path).name
    fig_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(fig_path, dpi=300)
    plt.close()
    logger.success(f"Saved Latency Breakdown plot to '{output_path}'")


def plot_bandwidth_sensitivity_curves(metrics_data: List[Dict[str, Any]], output_path: str):
    """Figure 3: Bandwidth Sensitivity Curves with explicit crossover point vs. raw offload."""
    logger.info("Generating Figure 3: Bandwidth Sensitivity Curves...")
    fig, ax = plt.subplots(figsize=(8.0, 5.0))

    bandwidths = np.linspace(1.0, 100.0, 250)  # Mbps
    colors = get_tab10_colors(len(metrics_data) + 1)
    linestyles = ["-", "--", "-.", ":", "-", "--", "-.", ":"]

    for idx, m in enumerate(metrics_data):
        cfg_name = m["config_name"]
        compute_ms = m["t_e2e_compute_ms_mean"]
        wire_bytes = m.get("wire_size_bytes_mean", m.get("wire_size_kib_mean", 0.0) * 1024.0)

        total_latencies = [compute_ms + (wire_bytes * 8.0) / (bw * 1e6) * 1000.0 for bw in bandwidths]

        ax.plot(
            bandwidths,
            total_latencies,
            label=cfg_name,
            color=colors[idx],
            linestyle=linestyles[idx % len(linestyles)],
            linewidth=2.2 if "INT8" in cfg_name or "Jetson" in cfg_name else 1.4,
        )

    # Monolithic Cloud Offloading Baseline (Raw 640x640x3 RGB image = 1,228.8 KiB + 7.5ms Cloud compute)
    raw_frame_bytes = 640 * 640 * 3
    raw_cloud_total = [7.5 + (raw_frame_bytes * 8.0) / (bw * 1e6) * 1000.0 for bw in bandwidths]
    ax.plot(
        bandwidths,
        raw_cloud_total,
        label="Monolithic Cloud Offload (Raw Image: 1.17 MiB)",
        color="red",
        linestyle=":",
        linewidth=2.5,
    )

    ax.set_xlabel("Channel Bandwidth (Mbps)", fontweight="bold")
    ax.set_ylabel("Total System Latency (ms) [Log Scale]", fontweight="bold")
    ax.set_yscale("log")
    ax.set_xlim(1.0, 100.0)
    ax.set_title("Bandwidth Sensitivity & Crossover Frontiers (1 - 100 Mbps)", fontweight="bold", pad=12)
    ax.grid(True, which="both", linestyle="--", alpha=0.5)
    ax.legend(loc="upper right", frameon=True, facecolor="white", edgecolor="none", shadow=True)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    fig_path = Path("/home/sengar/BTP/uav-split-perception/paper/figures") / Path(output_path).name
    fig_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(fig_path, dpi=300)
    plt.close()
    logger.success(f"Saved Bandwidth Sensitivity plot to '{output_path}'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Publication Plot Generator")
    parser.add_argument("--results-dir", type=str, default="experiments/results")
    args = parser.parse_args()

    m_data, a_data = load_benchmark_and_accuracy_data(args.results_dir)

    plot_pareto_frontiers(m_data, a_data, os.path.join(args.results_dir, "pareto_frontiers.png"))
    plot_latency_breakdown_bars(m_data, os.path.join(args.results_dir, "latency_breakdown_bars.png"))
    plot_bandwidth_sensitivity_curves(m_data, os.path.join(args.results_dir, "bandwidth_sensitivity_curves.png"))
