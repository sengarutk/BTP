import random
import torch
"""Publication-Grade Swarm Visualization Suite for AEGIS-UAV.

Generates 3 IEEE double-column 300 DPI figures:
1. experiments/results/swarm_scalability_latency.png (Mean & P95 Latency vs Swarm Size)
2. experiments/results/swarm_delivery_resilience.png (Delivery Success Rate under Blackout vs Swarm Size)
3. experiments/results/swarm_energy_distribution.png (Onboard Energy Distribution across Swarm Nodes)
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import matplotlib.pyplot as plt
import numpy as np

# Set publication style
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
    "font.size": 10,
    "axes.labelsize": 11,
    "axes.titlesize": 12,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 9.5,
    "figure.titlesize": 13,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "axes.grid": True,
    "grid.alpha": 0.35,
    "grid.linestyle": "--",
    "lines.linewidth": 2.2,
    "lines.markersize": 7,
})

REPO_ROOT = Path(__file__).resolve().parent.parent
FIGURES_DIR = REPO_ROOT / "paper" / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

from simulation.swarm_sim import SwarmSimulationEngine
from utils.logger import get_logger

logger = get_logger("SwarmPlotter")
RESULTS_DIR = REPO_ROOT / "experiments" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# Data Collection & Simulation Sweeps
# =============================================================================

def collect_swarm_scaling_data(swarm_sizes: List[int] = [1, 3, 5, 10, 20, 30, 50], duration_s: float = 30.0) -> Dict[str, Any]:
    """Runs parameterized multi-scenario simulations across swarm sizes."""
    random.seed(42)
    np.random.seed(42)
    torch.manual_seed(42)
    logger.info(f"Running simulation sweeps across Swarm Sizes: {swarm_sizes} (Duration: {duration_s}s)...")
    
    aegis_mean_lat = []
    aegis_p95_lat = []
    aegis_energy = []
    
    static_k4_mean_lat = []
    static_k4_p95_lat = []
    static_k4_energy = []
    
    direct_5g_mean_lat = []
    direct_5g_p95_lat = []
    
    blackout_aegis_delivery = []
    blackout_direct_delivery = []

    for n in swarm_sizes:
        # --- (A) AEGIS-UAV Dynamic on Moderate Channel ---
        sim_aegis = SwarmSimulationEngine(
            num_uavs=n,
            fidelity="L4",
            cell_capacity_mbps=200.0,
            mobility_model="formation",
            trace_file="trace_5g_moderate.csv",
            duration_s=duration_s,
            fps=30.0,
        )
        res_aegis = sim_aegis.run_simulation()
        aegis_mean_lat.append(res_aegis["mean_e2e_ms"])
        aegis_p95_lat.append(res_aegis["p95_e2e_ms"])
        aegis_energy.append(res_aegis["mean_energy_mj"])

        # --- (B) Static k4-INT8 on Moderate Channel ---
        sim_k4 = SwarmSimulationEngine(
            num_uavs=n,
            fidelity="L2",
            cell_capacity_mbps=200.0,
            mobility_model="formation",
            trace_file="trace_5g_moderate.csv",
            duration_s=duration_s,
            fps=30.0,
            fixed_cut="k4",
            fixed_dtype="int8",
        )
        res_k4 = sim_k4.run_simulation()
        static_k4_mean_lat.append(res_k4["mean_e2e_ms"])
        static_k4_p95_lat.append(res_k4["p95_e2e_ms"])
        static_k4_energy.append(res_k4["mean_energy_mj"])

        # --- (C) Direct 5G (Raw Offload under Shared Cell Contention) ---
        sim_direct = SwarmSimulationEngine(
            num_uavs=n,
            fidelity="L2",
            cell_capacity_mbps=200.0,
            mobility_model="formation",
            trace_file="trace_5g_moderate.csv",
            duration_s=duration_s,
            fps=30.0,
            fixed_cut="k2",
            fixed_dtype="fp32",
        )
        res_direct = sim_direct.run_simulation()
        direct_5g_mean_lat.append(res_direct["mean_e2e_ms"])
        direct_5g_p95_lat.append(res_direct["p95_e2e_ms"])

        # --- (D) Blackout Resilience (3GPP Blackout Trace) ---
        sim_blk_aegis = SwarmSimulationEngine(
            num_uavs=n,
            fidelity="L4",
            cell_capacity_mbps=200.0,
            mobility_model="formation",
            trace_file="trace_5g_blackout.csv",
            duration_s=duration_s,
            fps=30.0,
        )
        res_blk_aegis = sim_blk_aegis.run_simulation()
        blackout_aegis_delivery.append(res_blk_aegis["delivery_rate_pct"])

        sim_blk_direct = SwarmSimulationEngine(
            num_uavs=n,
            fidelity="L1" if n == 1 else "L2",
            cell_capacity_mbps=200.0,
            mobility_model="formation",
            trace_file="trace_5g_blackout.csv",
            duration_s=duration_s,
            fps=30.0,
            fixed_cut="k4",
            fixed_dtype="int8",
        )
        res_blk_direct = sim_blk_direct.run_simulation()
        blackout_direct_delivery.append(res_blk_direct["delivery_rate_pct"])

    # Collect real per-node energy distributions from empirical simulation runs at N=10
    sim_aegis = SwarmSimulationEngine(num_uavs=10, fidelity="L4", duration_s=15.0)
    res_aegis = sim_aegis.run_simulation()
    aegis_node_energies = [u["total_energy_mj"] / max(1, u["generated"]) for u in res_aegis["uav_stats"] if u["generated"] > 0]

    sim_static = SwarmSimulationEngine(num_uavs=10, fidelity="L4", duration_s=15.0, fixed_cut="k4", fixed_dtype="int8")
    res_static = sim_static.run_simulation()
    static_node_energies = [u["total_energy_mj"] / max(1, u["generated"]) for u in res_static["uav_stats"] if u["generated"] > 0]

    sim_mono = SwarmSimulationEngine(num_uavs=10, fidelity="L4", duration_s=15.0, fixed_cut="full", fixed_dtype="fp32")
    res_mono = sim_mono.run_simulation()
    mono_node_energies = [u["total_energy_mj"] / max(1, u["generated"]) for u in res_mono["uav_stats"] if u["generated"] > 0]

    energy_distributions = {
        "Monolithic Edge": mono_node_energies if mono_node_energies else [res_mono["mean_energy_mj"]],
        "Static k4-INT8": static_node_energies if static_node_energies else [res_static["mean_energy_mj"]],
        "AEGIS-UAV Dynamic": aegis_node_energies if aegis_node_energies else [res_aegis["mean_energy_mj"]],
    }

    data = {
        "swarm_sizes": swarm_sizes,
        "aegis_mean_lat": aegis_mean_lat,
        "aegis_p95_lat": aegis_p95_lat,
        "static_k4_mean_lat": static_k4_mean_lat,
        "static_k4_p95_lat": static_k4_p95_lat,
        "direct_5g_mean_lat": direct_5g_mean_lat,
        "direct_5g_p95_lat": direct_5g_p95_lat,
        "blackout_aegis_delivery": blackout_aegis_delivery,
        "blackout_direct_delivery": blackout_direct_delivery,
        "energy_distributions": energy_distributions,
    }
    return data


# =============================================================================
# Plotting Routines (IEEE 300 DPI Figures)
# =============================================================================

def plot_scalability_latency(data: Dict[str, Any]):
    """Figure 1: Mean & P95 End-to-End Latency vs Swarm Size."""
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    
    sizes = data["swarm_sizes"]
    
    ax.plot(sizes, data["direct_5g_mean_lat"], "s--", color="#d62728", label="Direct 5G Raw Offload (Mean)", alpha=0.85)
    ax.plot(sizes, data["direct_5g_p95_lat"], "^:", color="#d62728", label="Direct 5G Raw Offload (P95)", alpha=0.6)
    
    ax.plot(sizes, data["static_k4_mean_lat"], "D--", color="#ff7f0e", label="Static Split k4-INT8 (Mean)", alpha=0.85)
    ax.plot(sizes, data["static_k4_p95_lat"], "v:", color="#ff7f0e", label="Static Split k4-INT8 (P95)", alpha=0.6)
    
    ax.plot(sizes, data["aegis_mean_lat"], "o-", color="#1f77b4", linewidth=2.8, markersize=8, label="AEGIS-UAV Adaptive + Relay (Mean)")
    ax.plot(sizes, data["aegis_p95_lat"], "*-", color="#2ca02c", linewidth=2.4, markersize=9, label="AEGIS-UAV Adaptive + Relay (P95)")
    
    ax.axhline(y=300.0, color="#7f7f7f", linestyle="--", linewidth=1.8, label="Real-Time Deadline (300 ms)")
    ax.axhline(y=33.33, color="#9467bd", linestyle=":", linewidth=1.5, label="30 FPS Threshold (33.3 ms)")

    ax.annotate(
        "AEGIS-UAV autonomously adapts to local compute\npreventing cell uplink contention collapse",
        xy=(30, data["aegis_mean_lat"][sizes.index(30)]),
        xytext=(15, 180),
        arrowprops=dict(facecolor="#1f77b4", shrink=0.08, width=1.5, headwidth=7),
        bbox=dict(boxstyle="round,pad=0.4", fc="#eef4fb", ec="#1f77b4", lw=1.2),
        fontsize=8.5,
    )

    ax.set_xlabel(r"Swarm Size ($N$ Active UAVs)")
    ax.set_ylabel("End-to-End Perception Latency (ms)")
    ax.set_title(r"Multi-UAV Swarm Scalability: Latency vs. Swarm Density ($C_{\mathrm{cell}} = 200\ \mathrm{Mbps}$)")
    ax.set_xticks(sizes)
    ax.set_ylim(0, 550)
    ax.legend(loc="upper left", framealpha=0.92, fontsize=8.5, ncol=2)
    
    plt.tight_layout()
    out_path = RESULTS_DIR / "swarm_scalability_latency.png"
    plt.savefig(out_path, dpi=300)
    fig_path = FIGURES_DIR / out_path.name
    plt.savefig(fig_path, dpi=300)
    plt.close()
    logger.success(f"Generated Figure 1 -> {out_path}")


def plot_delivery_resilience(data: Dict[str, Any]):
    """Figure 2: Task Delivery Success Rate under 3GPP Blackout Traces."""
    fig, ax = plt.subplots(figsize=(7.5, 4.0))
    
    sizes = data["swarm_sizes"]
    x = np.arange(len(sizes))
    width = 0.35

    rects1 = ax.bar(x - width/2, data["blackout_direct_delivery"], width, label="Direct 5G (No Mesh Relaying)", color="#d62728", alpha=0.85, edgecolor="black", hatch="//")
    rects2 = ax.bar(x + width/2, data["blackout_aegis_delivery"], width, label="AEGIS-UAV (2nd-Price Auction Relay)", color="#2ca02c", alpha=0.90, edgecolor="black")

    for rect in rects1:
        height = rect.get_height()
        ax.annotate(f"{height:.1f}%",
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=8, color="#d62728", weight="bold")

    for rect in rects2:
        height = rect.get_height()
        ax.annotate(f"{height:.1f}%",
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=8, color="#2ca02c", weight="bold")

    ax.set_xlabel(r"Swarm Size ($N$ Active UAVs)")
    ax.set_ylabel("Perception Frame Delivery Success Rate (%)")
    ax.set_title("Swarm Resilience: Task Delivery under Severe 5G Blackout")
    ax.set_xticks(x)
    ax.set_xticklabels([f"N={n}" for n in sizes])
    ax.set_ylim(0, 118)
    ax.legend(loc="upper right", framealpha=0.92, fontsize=9)

    ax.annotate(
        "A2A 802.11ax mesh auction relays\npackets around localized 5G blackouts",
        xy=(x[3] + width/2, 100),
        xytext=(x[1] - 0.2, 75),
        arrowprops=dict(facecolor="#2ca02c", shrink=0.08, width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", fc="#f0faf0", ec="#2ca02c", lw=1.2),
        fontsize=8.5,
    )

    plt.tight_layout()
    out_path = RESULTS_DIR / "swarm_delivery_resilience.png"
    plt.savefig(out_path, dpi=300)
    fig_path = FIGURES_DIR / out_path.name
    plt.savefig(fig_path, dpi=300)
    plt.close()
    logger.success(f"Generated Figure 2 -> {out_path}")


def plot_energy_distribution(data: Dict[str, Any]):
    """Figure 3: Onboard Energy Distribution per Perception Frame."""
    fig, ax = plt.subplots(figsize=(7.2, 4.0))

    dist_data = data["energy_distributions"]
    labels = list(dist_data.keys())
    values = [dist_data[k] for k in labels]
    
    colors = ["#7f7f7f", "#ff7f0e", "#1f77b4"]

    try:
        box = ax.boxplot(
            values,
            patch_artist=True,
            tick_labels=labels,
            widths=0.55,
            medianprops=dict(color="black", linewidth=2.0),
            flierprops=dict(marker="o", markerfacecolor="gray", markersize=3, alpha=0.5),
        )
    except TypeError:
        box = ax.boxplot(
            values,
            patch_artist=True,
            labels=labels,
            widths=0.55,
            medianprops=dict(color="black", linewidth=2.0),
            flierprops=dict(marker="o", markerfacecolor="gray", markersize=3, alpha=0.5),
        )

    for patch, color in zip(box["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.75)
        patch.set_edgecolor("black")

    means = [np.mean(v) for v in values]
    for idx, mean_val in enumerate(means, 1):
        ax.scatter(idx, mean_val, marker="D", color="yellow", s=40, zorder=5, edgecolors="black")
        ax.text(idx, mean_val + 35, f"{mean_val:.1f} mJ", ha="center", fontsize=8.5, weight="bold")

    ax.set_ylabel(r"Onboard UAV Energy per Frame ($E_{\mathrm{uav}}$ in mJ)")
    ax.set_title(r"Onboard UAV Energy Consumption Distribution ($N=10$ Swarm, 30 FPS)")
    ax.set_ylim(0, 1450)
    
    aegis_mean = means[-1]
    edge_mean = means[0]
    savings_vs_edge = (1.0 - (aegis_mean / edge_mean)) * 100.0 if edge_mean > 0 else 0.0
    ax.text(
        0.03, 0.88,
        f"★ AEGIS-UAV Energy Savings:\n  • {savings_vs_edge:.1f}% vs. Monolithic Edge",
        transform=ax.transAxes,
        fontsize=9,
        verticalalignment="top",
        bbox=dict(boxstyle="round,pad=0.5", fc="#fdfefe", ec="#1f77b4", lw=1.2)
    )

    plt.tight_layout()
    out_path = RESULTS_DIR / "swarm_energy_distribution.png"
    plt.savefig(out_path, dpi=300)
    fig_path = FIGURES_DIR / out_path.name
    plt.savefig(fig_path, dpi=300)
    plt.close()
    logger.success(f"Generated Figure 3 -> {out_path}")


# =============================================================================
# Main Entry Point
# =============================================================================

def generate_all_swarm_plots():
    """Generates all 3 publication-grade figures."""
    logger.info("Collecting multi-UAV swarm scaling benchmark data...")
    data = collect_swarm_scaling_data(swarm_sizes=[1, 3, 5, 10, 20, 30, 50], duration_s=30.0)
    
    logger.info("Generating publication figures...")
    plot_scalability_latency(data)
    plot_delivery_resilience(data)
    plot_energy_distribution(data)
    logger.success("★ All 3 Swarm Simulation Visualizations generated successfully.")


if __name__ == "__main__":
    generate_all_swarm_plots()
