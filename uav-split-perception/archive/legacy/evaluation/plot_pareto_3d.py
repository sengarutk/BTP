"""Publication-Grade 3D & 2D Pareto Visualization Suite for Split YOLOv8 Perception.

Generates IEEE-compliant 300 DPI figures:
1. experiments/results/pareto_3d_frontier.png:
   3D Pareto surface/scatter plot (Total Latency @ 20 Mbps, Payload Size KiB, Detection Accuracy mAP@0.5)
   with non-dominated Pareto frontier points and key split annotations.
2. experiments/results/pareto_2d_tradeoffs.png:
   Subplot A: mAP@0.5 vs. Total Latency @ 20 Mbps (Compute-Optimal Frontiers).
   Subplot B: Transmitted Payload Size (KiB) vs. Edge Parameter Share (%).
   Subplot C: Crossover Trade-off Curve demonstrating k4 and k9 dominance.
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
from mpl_toolkits.mplot3d import Axes3D


from utils.logger import get_logger

logger = get_logger("PlotPareto3D")

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
})


def load_split_pareto_data(results_file: str = "experiments/results/split_pareto_analysis.json") -> List[Dict[str, Any]]:
    """Loads split Pareto analysis JSON records."""
    if not os.path.exists(results_file):
        raise FileNotFoundError(f"Missing results file: '{results_file}'. Run benchmark_split_pareto.py first.")
    with open(results_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("configurations", [])


def compute_pareto_frontier_3d(points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Computes non-dominated Pareto optimal points: minimize Latency, minimize Payload, maximize mAP."""
    pareto_points = []
    for p in points:
        lat = p.get("total_latency_20mbps_ms", p.get("t_e2e_compute_ms_mean", 10.0))
        wire = p.get("wire_size_kib", 0.0)
        acc = p.get("mAP_50", 0.4)

        is_dominated = False
        for other in points:
            o_lat = other.get("total_latency_20mbps_ms", other.get("t_e2e_compute_ms_mean", 10.0))
            o_wire = other.get("wire_size_kib", 0.0)
            o_acc = other.get("mAP_50", 0.4)

            if (o_lat <= lat and o_wire <= wire and o_acc >= acc) and (o_lat < lat or o_wire < wire or o_acc > acc):
                is_dominated = True
                break

        if not is_dominated:
            pareto_points.append(p)
    return pareto_points


def plot_pareto_3d_surface(configs: List[Dict[str, Any]], output_path: str):
    """Figure 1: 3D Pareto Scatter/Surface with Non-Dominated Frontiers and Annotations."""
    logger.info("Generating Figure 1: 3D Pareto Surface...")
    fig = plt.figure(figsize=(10.0, 7.5))
    ax = fig.add_subplot(111, projection="3d")

    pareto_front = compute_pareto_frontier_3d(configs)
    pareto_names = {p["config_name"] for p in pareto_front}

    dtype_markers = {"int8": "o", "fp16": "s", "fp32": "^"}
    dtype_colors = {"int8": "#2ca02c", "fp16": "#1f77b4", "fp32": "#d62728"}

    for c in configs:
        lat = c.get("total_latency_20mbps_ms", c.get("t_e2e_compute_ms_mean", 10.0))
        # Ensure wire is at least 0.1 for log scale representation
        wire = max(c.get("wire_size_kib", 0.0), 0.1)
        acc = c.get("mAP_50", 0.4)
        dtype = c.get("dtype", "fp32")
        name = c["config_name"]

        is_pareto = name in pareto_names
        color = dtype_colors.get(dtype, "#7f7f7f")
        marker = dtype_markers.get(dtype, "o")

        if is_pareto:
            ax.scatter(
                np.log10(lat), np.log10(wire), acc,
                color="gold", edgecolors="black", s=180, marker="*", linewidths=1.2, zorder=10,
                label="Pareto Optimal" if "Pareto Optimal" not in [l.get_label() for l in ax.collections] else ""
            )
        else:
            ax.scatter(
                np.log10(lat), np.log10(wire), acc,
                color=color, edgecolors="black", s=70, marker=marker, alpha=0.85, linewidths=0.6,
                label=f"{dtype.upper()} Config" if f"{dtype.upper()} Config" not in [l.get_label() for l in ax.collections] else ""
            )

        # Annotate key optimal split junctions
        if "k4 (INT8)" in name or "k9 (INT8)" in name or "k15 (INT8)" in name or "Monolithic" in name:
            ax.text(
                np.log10(lat), np.log10(wire), acc + 0.002,
                f"  {name.replace('Split ', '')}", fontsize=8.5, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.8, edgecolor="gray")
            )

    ax.set_xlabel("Log10 Total Latency @ 20 Mbps (ms)", fontweight="bold", labelpad=10)
    ax.set_ylabel("Log10 Payload Footprint (KiB)", fontweight="bold", labelpad=10)
    ax.set_zlabel("COCO128 Accuracy (mAP@0.5)", fontweight="bold", labelpad=10)
    ax.set_title("3D Pareto Frontier: Latency vs. Payload vs. COCO128 mAP", fontweight="bold", pad=15)
    ax.view_init(elev=22, azim=-55)
    ax.legend(loc="upper left", frameon=True, facecolor="white", shadow=True)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    fig_path = Path("/home/sengar/BTP/uav-split-perception/paper/figures") / Path(output_path).name
    fig_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(fig_path, dpi=300)
    plt.close()
    logger.success(f"Saved 3D Pareto plot to '{output_path}'")


def plot_pareto_2d_tradeoffs(configs: List[Dict[str, Any]], output_path: str):
    """Figure 2: 2D Pareto Projections & Structural Trade-offs (3 Subplots)."""
    logger.info("Generating Figure 2: 2D Pareto Trade-offs...")
    fig, axes = plt.subplots(1, 3, figsize=(16.5, 4.8))

    # -------------------------------------------------------------
    # Subplot A: mAP@0.5 vs. Total Latency @ 20 Mbps
    # -------------------------------------------------------------
    ax_a = axes[0]
    for dtype, color, marker in [("int8", "#2ca02c", "o"), ("fp16", "#1f77b4", "s"), ("fp32", "#d62728", "^")]:
        subset = [c for c in configs if c.get("dtype") == dtype and "Monolithic" not in c["config_name"]]
        subset.sort(key=lambda x: x["cut_layer"])
        lats = [c["total_latency_20mbps_ms"] for c in subset]
        maps = [c["mAP_50"] for c in subset]
        ax_a.plot(lats, maps, label=f"{dtype.upper()} Split Points", color=color, marker=marker, linewidth=1.5, markersize=6)

    # Add Monolithic point
    mono = next((c for c in configs if "Monolithic" in c["config_name"]), None)
    if mono:
        ax_a.scatter(
            mono["total_latency_20mbps_ms"], mono["mAP_50"],
            color="black", marker="D", s=100, label="Monolithic FP32", zorder=5
        )

    ax_a.set_xlabel("Total System Latency @ 20 Mbps (ms) [Log Scale]", fontweight="bold")
    ax_a.set_ylabel("COCO128 mAP@0.5", fontweight="bold")
    ax_a.set_xscale("log")
    ax_a.set_title("Subplot A: mAP@0.5 vs. Total Latency @ 20 Mbps", fontweight="bold")
    ax_a.grid(True, which="both", linestyle="--", alpha=0.5)
    ax_a.legend(loc="lower right", frameon=True)

    # -------------------------------------------------------------
    # Subplot B: Payload Size (KiB) vs. Edge Parameter Share (%)
    # -------------------------------------------------------------
    ax_b = axes[1]
    int8_subset = [c for c in configs if c.get("dtype") == "int8"]
    int8_subset.sort(key=lambda x: x["cut_layer"])

    cuts = [f"k{c['cut_layer']}" for c in int8_subset]
    edge_param_pcts = [c["edge_param_pct"] for c in int8_subset]
    payloads_kib = [c["wire_size_kib"] for c in int8_subset]

    ax_b.bar(cuts, payloads_kib, color="#7570b3", edgecolor="black", alpha=0.85, label="INT8 Wire Payload (KiB)")
    ax_b2 = ax_b.twinx()
    ax_b2.plot(cuts, edge_param_pcts, color="#d95f02", marker="o", linewidth=2.0, label="Edge Parameter Share (%)")

    ax_b.set_xlabel("Split Boundary Cut Layer (k)", fontweight="bold")
    ax_b.set_ylabel("Transmitted Payload (KiB)", fontweight="bold", color="#7570b3")
    ax_b2.set_ylabel("Edge Parameters (%)", fontweight="bold", color="#d95f02")
    ax_b.set_title("Subplot B: Payload vs. Edge Compute Partition", fontweight="bold")
    ax_b.grid(True, axis="y", linestyle="--", alpha=0.5)

    # -------------------------------------------------------------
    # Subplot C: Trade-off & Dominance (k4 and k9 vs. Neck cuts)
    # -------------------------------------------------------------
    ax_c = axes[2]
    # Highlight why k4 and k9 are Pareto optimal
    for c in int8_subset:
        k = c["cut_layer"]
        lat = c["total_latency_20mbps_ms"]
        wire = c["wire_size_kib"]

        if k in [4, 9]:
            ax_c.scatter(wire, lat, color="#2ca02c", s=140, marker="*", edgecolor="black", zorder=5)
            ax_c.annotate(
                f" k{k} (Dominant)", (wire, lat), textcoords="offset points",
                xytext=(8, -3), fontweight="bold", color="#1b7837"
            )
        elif k in [12, 15, 18]:
            ax_c.scatter(wire, lat, color="#7570b3", s=80, marker="o", edgecolor="black", zorder=4)
            ax_c.annotate(f" k{k} (Neck)", (wire, lat), textcoords="offset points", xytext=(8, -3), fontsize=8.5)
        else:
            ax_c.scatter(wire, lat, color="#999999", s=60, marker="s", edgecolor="black", zorder=3)
            ax_c.annotate(f" k{k}", (wire, lat), textcoords="offset points", xytext=(8, -3), fontsize=8)

    ax_c.set_xlabel("Transmitted INT8 Payload (KiB)", fontweight="bold")
    ax_c.set_ylabel("Total System Latency @ 20 Mbps (ms)", fontweight="bold")
    ax_c.set_title("Subplot C: Structural Split Point Dominance", fontweight="bold")
    ax_c.grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    fig_path = Path("/home/sengar/BTP/uav-split-perception/paper/figures") / Path(output_path).name
    fig_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(fig_path, dpi=300)
    plt.close()
    logger.success(f"Saved 2D Pareto Trade-offs plot to '{output_path}'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="3D and 2D Pareto Visualization Suite")
    parser.add_argument("--results-json", type=str, default="experiments/results/split_pareto_analysis.json")
    parser.add_argument("--output-dir", type=str, default="experiments/results")
    args = parser.parse_args()

    data = load_split_pareto_data(args.results_json)
    plot_pareto_3d_surface(data, os.path.join(args.output_dir, "pareto_3d_frontier.png"))
    plot_pareto_2d_tradeoffs(data, os.path.join(args.output_dir, "pareto_2d_tradeoffs.png"))
