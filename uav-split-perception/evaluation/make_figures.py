#!/usr/bin/env python3
"""Generates every paper figure (vector PDF) from experiments/results. No numbers are typed in."""

import csv
import json
import math
from pathlib import Path
from typing import Dict, List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import NullFormatter

from simulation.system_model import AdaptivePolicy, load_offload_configs, make_hardware
from utils.logger import get_logger

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS = REPO_ROOT / "experiments" / "results"
FIGS = REPO_ROOT / "paper" / "figures"
logger = get_logger("MakeFigures")

COL_W = 3.45  # IEEE single-column width (inches)
# Okabe-Ito colour-blind-safe palette
C = {"onboard": "#000000", "split": "#0072B2", "zstd": "#56B4E9", "fp16": "#009E73", "jpeg": "#D55E00",
     "webp": "#E69F00", "h264": "#CC79A7", "adaptive": "#F0E442", "adaptive_split": "#999999"}
STRATEGY_STYLE = {
    "onboard": ("Onboard only", C["onboard"]),
    "split_k4_int8": ("Split k4 INT8", C["split"]),
    "split_k4_int8_zstd": ("Split k4 INT8+zstd", C["zstd"]),
    "split_k9_int8": ("Split k9 INT8", C["fp16"]),
    "jpeg_q90": ("Image offload (JPEG Q90)", C["jpeg"]),
    "adaptive_split": ("Adaptive (onboard/split)", C["adaptive_split"]),
    "adaptive_all": ("Adaptive (all)", "#8B6914"),
}
PROFILE_LABEL = {"good": "Good", "moderate": "Moderate", "blackout": "Blackout", "vehicular_fading": "Fast fading"}

plt.rcParams.update({
    "font.family": "serif", "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8, "legend.fontsize": 6.5,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "axes.grid": True, "grid.alpha": 0.3, "grid.linewidth": 0.5,
    "lines.linewidth": 1.2, "lines.markersize": 3.5, "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
    "pdf.fonttype": 42, "axes.spines.top": False, "axes.spines.right": False,
})


def read(name: str) -> List[Dict[str, str]]:
    with open(RESULTS / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save(fig, name: str) -> None:
    FIGS.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGS / f"{name}.pdf")
    plt.close(fig)
    logger.success(f"paper/figures/{name}.pdf")


def fig_payload_vs_cut() -> None:
    pareto = {r["config"]: r for r in read("split_pareto_analysis.csv")}
    codec = {r["config"]: r for r in read("codec_offload.csv")}
    topo = json.loads((RESULTS / "yolov8s_graph_topology.json").read_text())
    cuts = [2, 4, 5, 7, 9, 12, 15, 18]
    fig, ax = plt.subplots(figsize=(COL_W, 2.3))
    x = np.arange(len(cuts))
    for dt, lab, col, off in (("fp16", "FP16", C["fp16"], -0.27), ("int8", "INT8", C["split"], 0.0),
                              ("int8_zstd", "INT8+zstd", C["zstd"], 0.27)):
        ax.bar(x + off, [float(pareto[f"k{k}_{dt}"]["payload_kib_mean"]) for k in cuts], 0.26, label=lab, color=col)
    raw = topo["summary"]["input_uint8_kib"]
    ax.axhline(raw, color="k", ls="--", lw=0.8, label="Raw 640x640 image")
    for q, ls in (("jpeg_q90", ":"), ("jpeg_q75", "-.")):
        ax.axhline(float(codec[q]["payload_kib_mean"]), color=C["jpeg"], ls=ls, lw=1.0, label=f"JPEG {q[-3:].upper()}")
    ax.set_yscale("log")
    ax.set_xticks(x, [f"k{k}" for k in cuts])
    ax.set_ylabel("Payload per frame (KiB)")
    ax2 = ax.twinx()
    ax2.plot(x, [topo["splits"][f"k{k}"]["edge_flop_pct"] for k in cuts], "o-", color="0.3", ms=3)
    ax2.set_ylabel("Onboard FLOPs (%)", color="0.3")
    ax2.set_ylim(0, 100)
    ax2.grid(False)
    ax2.spines["right"].set_visible(True)
    ax.set_ylim(top=ax.get_ylim()[1] * 1.5)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.28), ncol=3, frameon=False)
    save(fig, "payload_vs_cut")


def fig_rate_accuracy() -> None:
    codecs = read("codec_baselines.csv")
    pareto = read("split_pareto_analysis.csv")
    fig, ax = plt.subplots(figsize=(COL_W, 2.3))
    for name, col, mk in (("JPEG", C["jpeg"], "o"), ("WebP", C["webp"], "s"), ("H.264", C["h264"], "^")):
        rows = sorted((r for r in codecs if r["codec_name"] == name), key=lambda r: float(r["wire_kib"]))
        xs = [float(r["wire_kib"]) for r in rows]
        ys = [100 * float(r["delta_map50_95"]) for r in rows]
        lo = [100 * (float(r["delta_map50_95"]) - float(r["delta_map50_95_ci_low"])) for r in rows]
        hi = [100 * (float(r["delta_map50_95_ci_high"]) - float(r["delta_map50_95"])) for r in rows]
        lab = "H.264 (intra, libx264)" if name == "H.264" else name
        ax.errorbar(xs, ys, yerr=[lo, hi], fmt=mk + "-", color=col, label=lab, capsize=1.5, elinewidth=0.6)
    for dt, col, mk, lab in (("int8", C["split"], "D", "Split INT8 (k2-k18)"),
                             ("int8_zstd", C["zstd"], "d", "Split INT8+zstd"),
                             ("fp16", C["fp16"], "P", "Split FP16")):
        rows = [r for r in pareto if r["kind"] == "split" and r["dtype"] == dt]
        xs = [float(r["payload_kib_mean"]) for r in rows]
        ys = [100 * float(r["delta_map50_95"]) for r in rows]
        lo = [100 * (float(r["delta_map50_95"]) - float(r["delta_map50_95_ci_low"])) for r in rows]
        hi = [100 * (float(r["delta_map50_95_ci_high"]) - float(r["delta_map50_95"])) for r in rows]
        ax.errorbar(xs, ys, yerr=[lo, hi], fmt=mk, color=col, label=lab, capsize=1.5, elinewidth=0.6, ms=3)
    ax.axhline(0, color="k", lw=0.6)
    ax.set_ylim(-4.0, 0.5)
    ax.text(0.98, 0.03, "lower-quality codec settings fall below the axis", transform=ax.transAxes, ha="right",
            fontsize=5.5, color="0.35")
    ax.set_xscale("log")
    ax.set_xlabel("Payload per frame (KiB, log scale)")
    ax.set_ylabel(r"$\Delta$mAP@[.5:.95] vs. FP32 (points)")
    ax.legend(frameon=False, ncol=2, loc="upper center", bbox_to_anchor=(0.5, 1.3))
    save(fig, "rate_accuracy")


def fig_latency_vs_bandwidth() -> None:
    configs = load_offload_configs()
    names = [("full_fp32", "Onboard", C["onboard"], "-"), ("k4_int8", "Split k4 INT8", C["split"], "-"),
             ("k4_int8_zstd", "Split k4 INT8+zstd", C["zstd"], "--"), ("k9_int8", "Split k9 INT8", C["fp16"], "-."),
             ("jpeg_q90", "JPEG Q90", C["jpeg"], "-"), ("jpeg_q75", "JPEG Q75", C["jpeg"], ":")]
    bws = np.logspace(0, math.log10(400), 200)
    t_fulls = [40.0, 180.0]
    fig, axes = plt.subplots(1, 2, figsize=(COL_W * 2, 2.1), sharey=True)
    for ax, tf in zip(axes, t_fulls):
        pol = AdaptivePolicy([configs[n] for n, *_ in names], make_hardware(tf))
        for n, lab, col, ls in names:
            lat = [pol.predict(configs[n], b)["latency_ms"] for b in bws]
            ax.plot(bws, lat, ls=ls, color=col, label=lab)
        ax.axhline(300, color="0.4", lw=0.8, ls="--")
        ax.text(250, 330, "deadline", fontsize=6, color="0.4", ha="right")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_ylim(20, 3000)
        ax.set_title(f"Onboard full-model latency $t_{{full}}$ = {tf:g} ms")
        ax.set_xlabel("Uplink goodput (Mbit/s)")
    axes[0].set_ylabel("Predicted frame latency (ms)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, ncol=6, loc="upper center", bbox_to_anchor=(0.5, 1.06))
    save(fig, "latency_vs_bandwidth")


def _grouped(ax, rows, profiles, strats, metric, ylabel):
    width = 0.8 / len(strats)
    x = np.arange(len(profiles))
    for i, s in enumerate(strats):
        vals, cis = [], []
        for p in profiles:
            r = next(r for r in rows if r["profile"] == p and r["strategy"] == s)
            vals.append(float(r[metric]))
            cis.append(float(r[f"{metric}_ci"]))
        lab, col = STRATEGY_STYLE[s]
        ax.bar(x + (i - (len(strats) - 1) / 2) * width, vals, width, yerr=cis, color=col, label=lab,
               capsize=1.2, error_kw={"elinewidth": 0.6})
    ax.set_xticks(x, [PROFILE_LABEL[p] for p in profiles])
    ax.set_ylabel(ylabel)


def fig_single_uav() -> None:
    rows = [r for r in read("system_single_uav.csv") if float(r["t_full_ms"]) == 180.0]
    strats = [s for s in STRATEGY_STYLE if any(r["strategy"] == s for r in rows)]
    profiles = list(PROFILE_LABEL)
    fig, axes = plt.subplots(2, 1, figsize=(COL_W * 2, 3.2), sharex=True)
    _grouped(axes[0], rows, profiles, strats, "on_time_fps_per_uav", "On-time frames/s")
    _grouped(axes[1], rows, profiles, strats, "latency_p95_ms", "p95 latency (ms)")
    axes[1].axhline(300, color="0.4", lw=0.8, ls="--")
    axes[0].legend(frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(0.5, 1.32))
    save(fig, "single_uav")


def fig_hardware_sensitivity() -> None:
    rows = read("system_single_uav.csv")
    fig, axes = plt.subplots(1, 2, figsize=(COL_W * 2, 2.0), sharey=True)
    for ax, prof in zip(axes, ("moderate", "good")):
        for s, (lab, col) in STRATEGY_STYLE.items():
            pts = sorted((float(r["t_full_ms"]), float(r["on_time_fps_per_uav"]), float(r["on_time_fps_per_uav_ci"]))
                         for r in rows if r["profile"] == prof and r["strategy"] == s)
            if pts:
                t, v, ci = zip(*pts)
                ax.errorbar(t, v, yerr=ci, fmt="o-", color=col, label=lab, capsize=1.5, elinewidth=0.6)
        ax.set_xscale("log")
        ax.set_xticks([40, 90, 180, 360], ["40", "90", "180", "360"])
        ax.xaxis.set_minor_formatter(NullFormatter())
        ax.set_xlabel(r"Onboard full-model latency $t_{full}$ (ms)")
        ax.set_title(f"{PROFILE_LABEL[prof]} channel")
    axes[0].set_ylabel("On-time frames/s")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(0.5, 1.16))
    save(fig, "hardware_sensitivity")


def fig_timeline() -> None:
    d = json.loads((RESULTS / "system_timeline.json").read_text())
    bw = np.array(d["bandwidth_mbps"])
    t_bw = np.arange(bw.size) * d["slot_ms"] / 1000.0
    frames = d["frames"]
    fig, axes = plt.subplots(3, 1, figsize=(COL_W, 3.0), sharex=True, gridspec_kw={"height_ratios": [1, 0.8, 1]})
    axes[0].plot(t_bw, bw, color=C["split"], lw=0.6)
    axes[0].set_ylabel("Goodput\n(Mbit/s)")
    kinds = sorted({f["cfg"] for f in frames if f["cfg"]}, key=lambda n: (n != "full_fp32", n))
    idx = {k: i for i, k in enumerate(kinds)}
    ts = [f["t_ms"] / 1000 for f in frames if f["cfg"]]
    ys = [idx[f["cfg"]] for f in frames if f["cfg"]]
    axes[1].scatter(ts, ys, s=1, color="k")
    pretty = {"full_fp32": "onboard"}
    axes[1].set_yticks(range(len(kinds)), [pretty.get(k, k.replace("_", " ").replace("jpeg q", "JPEG Q")) for k in kinds],
                       fontsize=5.5)
    axes[1].set_ylabel("Chosen\nconfig")
    ok = [(f["t_ms"] / 1000, f["latency_ms"]) for f in frames if f["status"] == "delivered"]
    if ok:
        t, l = zip(*ok)
        axes[2].scatter(t, l, s=1, color=C["jpeg"])
    axes[2].axhline(300, color="0.4", lw=0.8, ls="--")
    axes[2].set_ylabel("Latency\n(ms)")
    axes[2].set_xlabel("Time (s)")
    # Blackout times are drawn per run, so show the whole trace rather than a fixed window.
    for a in axes:
        a.set_xlim(0, t_bw[-1])
    save(fig, "timeline_blackout")


def fig_swarm() -> None:
    rows = read("system_swarm.csv")
    fig, axes = plt.subplots(1, 2, figsize=(COL_W * 2, 2.1), sharey=True)
    for ax, prof in zip(axes, ("moderate", "blackout")):
        for s, (lab, col) in STRATEGY_STYLE.items():
            for relay, ls in (("False", "-"), ("True", "--")):
                pts = sorted((int(r["n_uavs"]), float(r["on_time_fps_per_uav"]), float(r["on_time_fps_per_uav_ci"]))
                             for r in rows if r["profile"] == prof and r["strategy"] == s and r["relay"] == relay)
                if len(pts) < 2:
                    continue
                n, v, ci = zip(*pts)
                ax.errorbar(n, v, yerr=ci, fmt="o" + ls, color=col, capsize=1.5, elinewidth=0.6,
                            label=lab + (" + relay" if relay == "True" else ""))
        ax.set_xscale("log")
        ax.set_xticks([1, 2, 5, 10, 20], ["1", "2", "5", "10", "20"])
        ax.xaxis.set_minor_formatter(NullFormatter())
        ax.set_xlabel("UAVs sharing a 100 Mbit/s cell")
        ax.set_title(f"{PROFILE_LABEL[prof]} channel")
    axes[0].set_ylabel("On-time frames/s per UAV")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(0.5, 1.18))
    save(fig, "swarm")


def main() -> None:
    for f in (fig_payload_vs_cut, fig_rate_accuracy, fig_latency_vs_bandwidth, fig_single_uav,
              fig_hardware_sensitivity, fig_timeline, fig_swarm):
        f()


if __name__ == "__main__":
    main()
