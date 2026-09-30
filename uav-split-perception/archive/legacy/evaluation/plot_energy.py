"""Publication-Grade Visualization Engine for UAV Energy Modeling & Power Tradeoffs.

Generates 3 IEEE-compliant 300 DPI figures:
1. Energy vs. Latency Pareto Frontier (experiments/results/energy_vs_latency_pareto.png)
2. Energy Breakdown Stacked Bars (experiments/results/energy_breakdown_bars.png)
3. 3D Energy-Latency-Accuracy Pareto Surface (experiments/results/energy_pareto_3d.png)
"""

import csv
import json
import logging
import os
import sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parent.parent
FIGURES_DIR = REPO_ROOT / "paper" / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)
from typing import Any, Dict, List, Tuple

import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from mpl_toolkits.mplot3d import Axes3D
from matplotlib import cm
import numpy as np

from utils.logger import get_logger

logger = get_logger("PlotEnergy")

RESULTS_DIR = Path("experiments/results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
ENERGY_JSON_PATH = RESULTS_DIR / "energy_benchmark_results.json"
ENERGY_CSV_PATH = RESULTS_DIR / "energy_benchmark_results.csv"

# Global IEEE Plot Styling
plt.rcParams.update({
    "font.family": "serif",
    "font.size": 11,
    "axes.labelsize": 13,
    "axes.titlesize": 14,
    "xtick.labelsize": 11,
    "ytick.labelsize": 11,
    "legend.fontsize": 10,
    "figure.titlesize": 15,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "axes.grid": True,
    "grid.alpha": 0.35,
    "grid.linestyle": "--",
})

DTYPE_COLORS = {
    "fp32": "#D62728",      # Crimson Red
    "fp16": "#FF7F0E",      # Orange / Amber
    "int8": "#2CA02C",      # Emerald Green
    "baseline": "#1F77B4",  # Deep Blue
}

DTYPE_MARKERS = {
    "fp32": "s",
    "fp16": "^",
    "int8": "o",
    "baseline": "D",
}


def load_energy_data() -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Loads energy benchmark JSON & CSV records."""
    if not ENERGY_JSON_PATH.exists():
        from evaluation.benchmark_energy import load_pareto_records, evaluate_energy_across_configs
        pareto_recs = load_pareto_records()
        evaluate_energy_across_configs(pareto_recs)

    with open(ENERGY_JSON_PATH, "r", encoding="utf-8") as f:
        meta_data = json.load(f)

    records = []
    with open(ENERGY_CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            records.append({
                "config_id": r["config_id"],
                "split_cut": r["split_cut"],
                "dtype": r["dtype_precision"],
                "bw_mbps": float(r["bandwidth_mbps"]),
                "map50": float(r["map_50"]),
                "map50_95": float(r["map_50_95"]),
                "payload_kib": float(r["payload_kib"]),
                "t_edge": float(r["t_edge_ms"]),
                "t_quant": float(r["t_quant_ms"]),
                "t_tx": float(r["t_tx_ms"]),
                "t_cloud": float(r["t_cloud_ms"]),
                "t_total": float(r["t_total_ms"]),
                "e_edge": float(r["e_edge_mj"]),
                "e_quant": float(r["e_quant_mj"]),
                "e_tx": float(r["e_tx_mj"]),
                "e_uav": float(r["e_uav_total_mj"]),
                "e_cloud": float(r["e_cloud_mj"]),
                "e_system": float(r["e_system_total_mj"]),
                "batt_hours": float(r["battery_lifetime_hours"]),
                "batt_ext": float(r["battery_extension_factor"]),
            })
    return meta_data, records


def plot_energy_vs_latency_pareto(records: List[Dict[str, Any]]):
    """Figure 1: Energy vs. Latency Pareto Frontier (@ 20 Mbps)."""
    fig, ax = plt.subplots(figsize=(10, 6.5))

    recs_20 = [r for r in records if r["bw_mbps"] == 20.0]

    # Plot points by dtype
    for dtype, color in [("fp32", DTYPE_COLORS["fp32"]), ("fp16", DTYPE_COLORS["fp16"]), ("int8", DTYPE_COLORS["int8"])]:
        sub = [r for r in recs_20 if r["dtype"] == dtype and r["config_id"] != "monolithic_baseline"]
        x = [r["t_total"] for r in sub]
        y = [r["e_uav"] for r in sub]
        ax.scatter(
            x, y,
            c=color,
            marker=DTYPE_MARKERS[dtype],
            s=90,
            alpha=0.85,
            edgecolors="k",
            linewidths=0.8,
            label=f"Split Cuts ({dtype.upper()})",
            zorder=4,
        )
        # Annotate cut labels
        for r in sub:
            ax.annotate(
                r["split_cut"].upper(),
                (r["t_total"], r["e_uav"]),
                textcoords="offset points",
                xytext=(0, 7),
                ha="center",
                fontsize=8,
                color="#333333",
            )

    # Plot monolithic baseline
    mono = next((r for r in recs_20 if r["config_id"] == "monolithic_baseline"), None)
    if mono:
        ax.scatter(
            [mono["t_total"]], [mono["e_uav"]],
            c=DTYPE_COLORS["baseline"],
            marker=DTYPE_MARKERS["baseline"],
            s=160,
            edgecolors="k",
            linewidths=1.2,
            label="Monolithic (Full Edge YOLOv8s)",
            zorder=6,
        )
        ax.annotate(
            "Monolithic Baseline\n(6.71 ms, 59.2 mJ)",
            (mono["t_total"], mono["e_uav"]),
            textcoords="offset points",
            xytext=(15, 10),
            fontsize=9.5,
            fontweight="bold",
            color=DTYPE_COLORS["baseline"],
            arrowprops=dict(arrowstyle="->", color=DTYPE_COLORS["baseline"], lw=1.2),
        )

    # Highlight optimal points (e.g. k4-INT8 and k2-INT8)
    k4_int8 = next((r for r in recs_20 if r["config_id"] == "k4_int8"), None)
    if k4_int8:
        ax.scatter(
            [k4_int8["t_total"]], [k4_int8["e_uav"]],
            facecolors="none",
            edgecolors="#D62728",
            s=260,
            linewidths=2.0,
            linestyle="--",
            zorder=5,
        )
        ax.annotate(
            f"k4-INT8 Optimal Split\n({k4_int8['t_total']:.1f} ms, {k4_int8['e_uav']:.1f} mJ)",
            (k4_int8["t_total"], k4_int8["e_uav"]),
            textcoords="offset points",
            xytext=(-30, -35),
            fontsize=9.5,
            fontweight="bold",
            color="#2CA02C",
            arrowprops=dict(arrowstyle="->", color="#2CA02C", lw=1.2),
        )

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Total System Latency per Frame [ $T_{total}$ ] (ms, log scale)")
    ax.set_ylabel("On-Drone UAV Energy per Frame [ $E_{uav}$ ] (mJ, log scale)")
    ax.set_title("AEGIS-UAV: Energy vs. Latency Pareto Tradeoffs (@ 20 Mbps 5G Uplink)", pad=12)
    ax.legend(loc="lower right", framealpha=0.9)

    out_path = RESULTS_DIR / "energy_vs_latency_pareto.png"
    plt.tight_layout()
    plt.savefig(out_path, dpi=300)
    fig_path = FIGURES_DIR / out_path.name
    plt.savefig(fig_path, dpi=300)
    plt.close()
    logger.info(f"Generated Figure 1 -> {out_path}")


def plot_energy_breakdown_bars(records: List[Dict[str, Any]]):
    """Figure 2: Energy Breakdown Stacked Bars (@ 20 Mbps)."""
    fig, ax = plt.subplots(figsize=(13, 6.5))

    recs_20 = [r for r in records if r["bw_mbps"] == 20.0 and r["config_id"] != "monolithic_baseline"]

    # Filter to INT8 and FP16 for visual clarity
    int8_recs = [r for r in recs_20 if r["dtype"] == "int8"]
    fp16_recs = [r for r in recs_20 if r["dtype"] == "fp16"]

    cuts = [r["split_cut"].upper() for r in int8_recs]
    x_indices = np.arange(len(cuts))
    width = 0.38

    # Stacked components for INT8
    int8_e_edge = [r["e_edge"] for r in int8_recs]
    int8_e_quant = [r["e_quant"] for r in int8_recs]
    int8_e_tx = [r["e_tx"] for r in int8_recs]

    # Stacked components for FP16
    fp16_e_edge = [r["e_edge"] for r in fp16_recs]
    fp16_e_quant = [r["e_quant"] for r in fp16_recs]
    fp16_e_tx = [r["e_tx"] for r in fp16_recs]

    # Bar positions
    x_int8 = x_indices - width / 2
    x_fp16 = x_indices + width / 2

    # INT8 Bars
    b1_int8 = ax.bar(x_int8, int8_e_edge, width, label="Edge Compute (INT8)", color="#1F77B4", edgecolor="k", linewidth=0.6)
    b2_int8 = ax.bar(x_int8, int8_e_quant, width, bottom=int8_e_edge, label="Quantization (INT8)", color="#17BECF", edgecolor="k", linewidth=0.6)
    b3_int8 = ax.bar(x_int8, int8_e_tx, width, bottom=np.array(int8_e_edge) + np.array(int8_e_quant), label="5G RF Uplink (INT8)", color="#2CA02C", edgecolor="k", linewidth=0.6)

    # FP16 Bars
    b1_fp16 = ax.bar(x_fp16, fp16_e_edge, width, color="#AEC7E8", edgecolor="k", linewidth=0.6)
    b2_fp16 = ax.bar(x_fp16, fp16_e_quant, width, bottom=fp16_e_edge, color="#9EDAE5", edgecolor="k", linewidth=0.6)
    b3_fp16 = ax.bar(x_fp16, fp16_e_tx, width, bottom=np.array(fp16_e_edge) + np.array(fp16_e_quant), label="5G RF Uplink (FP16)", color="#FF7F0E", edgecolor="k", linewidth=0.6)

    ax.set_xticks(x_indices)
    ax.set_xticklabels([f"{c}\n(INT8 | FP16)" for c in cuts], fontsize=9.5)
    ax.set_ylabel("On-Drone Energy per Frame (mJ)")
    ax.set_title("AEGIS-UAV: Component-Wise Energy Breakdown Across Split Cuts (@ 20 Mbps 5G)", pad=12)
    ax.legend(loc="upper left", framealpha=0.9, ncol=2)

    out_path = RESULTS_DIR / "energy_breakdown_bars.png"
    plt.tight_layout()
    plt.savefig(out_path, dpi=300)
    fig_path = FIGURES_DIR / out_path.name
    plt.savefig(fig_path, dpi=300)
    plt.close()
    logger.info(f"Generated Figure 2 -> {out_path}")


def plot_energy_pareto_3d(records: List[Dict[str, Any]]):
    """Figure 3: 3D Energy-Latency-Accuracy Pareto Surface (@ 20 Mbps)."""
    fig = plt.figure(figsize=(11, 8.5))
    ax = fig.add_subplot(111, projection="3d")

    recs_20 = [r for r in records if r["bw_mbps"] == 20.0]

    for dtype, color in [("fp32", DTYPE_COLORS["fp32"]), ("fp16", DTYPE_COLORS["fp16"]), ("int8", DTYPE_COLORS["int8"])]:
        sub = [r for r in recs_20 if r["dtype"] == dtype and r["config_id"] != "monolithic_baseline"]
        x = [r["t_total"] for r in sub]
        y = [r["e_uav"] for r in sub]
        z = [r["map50"] for r in sub]
        ax.scatter(
            x, y, z,
            c=color,
            marker=DTYPE_MARKERS[dtype],
            s=80,
            alpha=0.85,
            edgecolors="k",
            depthshade=True,
            label=f"Split Cuts ({dtype.upper()})",
        )

    # Monolithic point
    mono = next((r for r in recs_20 if r["config_id"] == "monolithic_baseline"), None)
    if mono:
        ax.scatter(
            [mono["t_total"]], [mono["e_uav"]], [mono["map50"]],
            c=DTYPE_COLORS["baseline"],
            marker=DTYPE_MARKERS["baseline"],
            s=150,
            edgecolors="k",
            label="Monolithic (Full Edge)",
        )

    ax.set_xlabel("\nTotal Latency (ms)", linespacing=2.0)
    ax.set_ylabel("\nOnboard Energy (mJ)", linespacing=2.0)
    ax.set_zlabel("\nCOCO128 mAP@0.5", linespacing=2.0)
    ax.set_title("AEGIS-UAV: 3D Energy - Latency - Accuracy Pareto Space", pad=15)
    ax.legend(loc="upper right", framealpha=0.9)
    ax.view_init(elev=24, azim=130)

    out_path = RESULTS_DIR / "energy_pareto_3d.png"
    plt.tight_layout()
    plt.savefig(out_path, dpi=300)
    fig_path = FIGURES_DIR / out_path.name
    plt.savefig(fig_path, dpi=300)
    plt.close()
    logger.info(f"Generated Figure 3 -> {out_path}")


def generate_all_energy_plots():
    """Master generation function for Track 1.4 energy visualizations."""
    meta, records = load_energy_data()
    plot_energy_vs_latency_pareto(records)
    plot_energy_breakdown_bars(records)
    plot_energy_pareto_3d(records)
    logger.info("All 3 Energy Visualizations generated successfully!")


if __name__ == "__main__":
    generate_all_energy_plots()
