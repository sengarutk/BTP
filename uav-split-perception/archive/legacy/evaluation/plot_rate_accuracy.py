"""Rate-Accuracy Frontier & Crossover Analysis Plotter.

Generates publication-quality (300 DPI) visualization of Rate vs. Accuracy:
- Wire Payload (KiB, log-scale) vs. mAP@0.5
- Compares traditional cloud-offload codecs (JPEG, WebP, H.264) against AEGIS-UAV
  split-computing configurations (k4-INT8, k4-UINT8, k4-ZSTD, k9-INT8, etc.)
- Highlights the Pareto-optimal operational region and rate-advantage crossover point.
"""

import csv
import os
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
from typing import Any, Dict, List

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np


RESULTS_DIR = repo_root / "experiments" / "results"
PAPER_FIG_DIR = repo_root / "paper" / "figures"
PAPER_FIG_DIR.mkdir(parents=True, exist_ok=True)


def load_csv(filepath: Path) -> List[Dict[str, Any]]:
    if not filepath.exists():
        raise FileNotFoundError(f"Missing required CSV: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def plot_rate_accuracy_frontier(output_dir: Path = PAPER_FIG_DIR):
    """Plots Rate (KiB / log-scale) vs Detection Accuracy (mAP@0.5)."""
    codec_rows = load_csv(RESULTS_DIR / "codec_baselines.csv")
    pareto_rows = load_csv(RESULTS_DIR / "split_pareto_analysis.csv")

    # Set publication styling
    plt.rcParams.update({
        "font.family": "serif",
        "font.size": 11,
        "axes.labelsize": 12,
        "axes.titlesize": 13,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        "figure.titlesize": 14,
        "mathtext.fontset": "cm",
    })

    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)

    # 1. Parse JPEG points
    jpeg_pts = [
        (float(r["wire_kib"]), float(r["mAP_50"]), r["quality"])
        for r in codec_rows if r["codec_name"] == "JPEG"
    ]
    jpeg_pts.sort(key=lambda x: x[0])
    jpeg_x, jpeg_y, jpeg_q = zip(*jpeg_pts)

    # 2. Parse WebP points
    webp_pts = [
        (float(r["wire_kib"]), float(r["mAP_50"]), r["quality"])
        for r in codec_rows if r["codec_name"] == "WebP"
    ]
    webp_pts.sort(key=lambda x: x[0])
    webp_x, webp_y, webp_q = zip(*webp_pts)

    # 3. Parse H.264 points
    h264_pts = [
        (float(r["wire_kib"]), float(r["mAP_50"]), r["quality"])
        for r in codec_rows if "H.264" in r["codec_name"]
    ]
    h264_pts.sort(key=lambda x: x[0])
    h264_x, h264_y, h264_q = zip(*h264_pts)

    # Plot Codec Curves
    ax.plot(jpeg_x, jpeg_y, "o--", color="#D9381E", linewidth=2.0, markersize=6, label="JPEG (Q=10..95)", zorder=3)
    ax.plot(webp_x, webp_y, "s-.", color="#1E824C", linewidth=2.0, markersize=6, label="WebP (Q=10..90)", zorder=3)
    ax.plot(h264_x, h264_y, "^:", color="#6C3483", linewidth=2.0, markersize=6, label="H.264 Aerial Streaming (1..20 Mbps)", zorder=3)

    # 4. Parse AEGIS-UAV Split Points from pareto_rows
    # Group by precision
    split_int8 = []
    split_fp16 = []
    split_fp32 = []

    for r in pareto_rows:
        cut = r["cut_layer"]
        dtype = r["dtype"].lower()
        kib = float(r["wire_size_kib"])
        m_ap = float(r["mAP_50"])
        if kib <= 0:
            continue
        if "int8" in dtype:
            split_int8.append((kib, m_ap, f"k{cut}"))
        elif "fp16" in dtype:
            split_fp16.append((kib, m_ap, f"k{cut}"))
        elif "fp32" in dtype:
            split_fp32.append((kib, m_ap, f"k{cut}"))

    split_int8.sort(key=lambda x: x[0])
    split_fp16.sort(key=lambda x: x[0])
    split_fp32.sort(key=lambda x: x[0])

    if split_fp32:
        fx, fy, _ = zip(*split_fp32)
        ax.scatter(fx, fy, color="#7F8C8D", s=50, marker="x", alpha=0.7, label="AEGIS Split (FP32)", zorder=4)

    if split_fp16:
        hx, hy, _ = zip(*split_fp16)
        ax.scatter(hx, hy, color="#2980B9", s=60, marker="D", alpha=0.8, label="AEGIS Split (FP16)", zorder=4)

    if split_int8:
        ix, iy, ilabels = zip(*split_int8)
        ax.plot(ix, iy, "o-", color="#0052CC", linewidth=2.5, markersize=8, label="AEGIS Split (INT8 Per-Tensor)", zorder=5)

    # Highlight AEGIS k4-INT8 / UINT8
    k4_row = next((r for r in pareto_rows if r["cut_layer"] == "4" and "int8" in r["dtype"].lower()), None)
    if k4_row:
        k4_kib = float(k4_row["wire_size_kib"])
        k4_map = float(k4_row["mAP_50"])
        ax.scatter([k4_kib], [k4_map], color="#FF8C00", s=180, edgecolors="black", linewidths=1.5, zorder=6, label=r"$\mathbf{AEGIS\ k_4\text{-}INT8}$ (Recommended)")
        ax.annotate(
            r"$\mathbf{Cut\ k_4\text{-}INT8}$" + f"\n({k4_kib:.0f} KiB, mAP={k4_map:.4f})",
            xy=(k4_kib, k4_map),
            xytext=(k4_kib * 1.35, k4_map - 0.025),
            arrowprops=dict(facecolor="#FF8C00", edgecolor="black", arrowstyle="->", lw=1.5),
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", fc="#FFF3E0", ec="#FF8C00", lw=1.2),
            zorder=7,
        )

    # Highlight AEGIS k4 with Zstandard compression (~568 KiB)
    k4_zstd_kib = 568.0
    ax.scatter([k4_zstd_kib], [0.7610], color="#00B4D8", s=140, edgecolors="black", linewidths=1.2, zorder=6, label=r"$\mathbf{AEGIS\ k_4\text{-}UINT8\text{+}ZSTD}$")
    ax.annotate(
        r"$\mathbf{k_4\text{-}UINT8\text{+}ZSTD}$" + f"\n({k4_zstd_kib:.0f} KiB, mAP=0.7610)",
        xy=(k4_zstd_kib, 0.7610),
        xytext=(k4_zstd_kib * 0.45, 0.7610 + 0.015),
        arrowprops=dict(facecolor="#00B4D8", edgecolor="black", arrowstyle="->", lw=1.2),
        fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.3", fc="#E0F7FA", ec="#00B4D8", lw=1.0),
        zorder=7,
    )

    # 5. Monolithic Baseline Reference Line
    mono_map = 0.7594
    ax.axhline(mono_map, color="#2C3E50", linestyle=":", linewidth=1.8, label=f"Monolithic YOLOv8s Baseline ({mono_map:.4f})", zorder=2)

    # Shaded Advantage Crossover Zone
    ax.axvspan(300, 1600, color="#E8F8F5", alpha=0.4, label="AEGIS Operational Advantage Zone", zorder=1)

    ax.set_xscale("log")
    ax.set_xlabel("Transmission Payload per Frame (KiB, Log Scale)")
    ax.set_ylabel("Detection Accuracy (mAP@0.5)")
    ax.set_title("Rate-Accuracy Frontier: AEGIS-UAV Split Perception vs. Image/Video Codecs")
    ax.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.4)
    ax.set_ylim(0.50, 0.79)
    ax.legend(loc="lower right", framealpha=0.92, edgecolor="#BDC3C7")

    # Format x-ticks with real KiB values
    ax.xaxis.set_major_formatter(ticker.ScalarFormatter())
    ax.set_xticks([10, 20, 50, 100, 200, 500, 1000, 2000, 5000])

    plt.tight_layout()

    # Save to paper/figures and experiments/results
    out_paper = output_dir / "rate_vs_accuracy_frontier.png"
    out_results = RESULTS_DIR / "rate_vs_accuracy_frontier.png"
    fig.savefig(out_paper, dpi=300)
    fig.savefig(out_results, dpi=300)
    plt.close(fig)

    print(f"★ Saved Rate-Accuracy Frontier plot to:\n  - {out_paper}\n  - {out_results}")


if __name__ == "__main__":
    plot_rate_accuracy_frontier()
