#!/usr/bin/env python3
"""Re-runs the system study with link models calibrated to ns-3, and checks the paper's conclusions.

Validations V1 and V2 found that the two analytic link models deviate from ns-3: the air-to-air
802.11ax model is conservative (ns-3 delivers 1.4-2.2x more goodput within range), and the
TR 36.942 cellular mapping is pessimistic above ~15 dB SINR and optimistic below ~12 dB. This script
repeats the single-UAV grid and the swarm grid of evaluation/benchmark_system.py with
  default     analytic A2A, TR 36.942 cellular mapping (the paper's setting)
  ns3_lte     cellular rates from ns-3 LTE (V2)
  ns3_a2a     air-to-air goodput from ns-3 802.11ax (V1)
  ns3_both    both
and reports, per variant, every system-level conclusion stated in the paper.

Output: experiments/results/validation/calibrated_single.csv, calibrated_swarm.csv,
calibrated_conclusions.json.
"""

import argparse
import json
import multiprocessing as mp
from pathlib import Path

import numpy as np

from evaluation.benchmark_system import aggregate, strategies
from simulation.stream_sim import SimParams, simulate
from simulation.system_model import HARDWARE_SCENARIOS_MS, load_offload_configs, make_hardware
from simulation.trace_generator import PROFILES
from validation.run_link_validation import OUT, write_csv

VARIANTS = {"default": ("tr36942", "analytic"), "ns3_lte": ("ns3_lte", "analytic"),
            "ns3_a2a": ("tr36942", "ns3"), "ns3_both": ("ns3_lte", "ns3")}
SWARM_SIZES = [1, 2, 5, 10, 20]


CACHE = OUT / "calibrated_cache"


def _cell(job):
    """One grid cell, cached on disk so an interrupted run resumes where it stopped."""
    import hashlib
    path = CACHE / (hashlib.sha256(json.dumps(job).encode()).hexdigest()[:24] + ".json")
    if path.exists():
        return json.loads(path.read_text())
    row = _compute(job)
    CACHE.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(row))
    tmp.replace(path)
    return row


def _compute(job):
    kind, variant, profile, t_full, name, n, relay, seeds, duration = job
    configs = load_offload_configs()
    hw = make_hardware(t_full)
    rate_model, a2a_model = VARIANTS[variant]
    s = strategies(configs)[name]
    runs = [simulate(SimParams(hw, configs, profile=profile, duration_s=duration, seed=k, n_uavs=n,
                               cell_capacity_mbps=100.0 if kind == "swarm" else None, relay=relay,
                               rate_model=rate_model, a2a_model=a2a_model, **s)) for k in range(seeds)]
    return aggregate(runs, {"variant": variant, "profile": profile, "t_full_ms": t_full, "strategy": name,
                            "n_uavs": n, "relay": relay})


def conclusions(single, swarm):
    out = {}
    for v in VARIANTS:
        rs = [r for r in single if r["variant"] == v]
        get = lambda p, t, s: next(r["on_time_fps_per_uav"] for r in rs  # noqa: E731
                                   if r["profile"] == p and r["t_full_ms"] == t and r["strategy"] == s)
        fixed = ["onboard", "split_k4_int8", "split_k4_int8_zstd", "split_k9_int8", "jpeg_q90"]
        splits = ["split_k4_int8", "split_k4_int8_zstd", "split_k9_int8"]
        jpeg_best = split_beats_onboard = 0
        ad_all, ad_split = [], []
        for p in PROFILES:
            for t in HARDWARE_SCENARIOS_MS:
                vals = {s: get(p, t, s) for s in fixed}
                best_split = max(vals[s] for s in splits)
                jpeg_best += int(vals["jpeg_q90"] >= max(vals.values()) - 1e-9)
                split_beats_onboard += int(best_split > vals["onboard"] + 1e-9)
                ad_all.append(get(p, t, "adaptive_all") / vals["jpeg_q90"] if vals["jpeg_q90"] > 0 else np.nan)
                best_os = max(best_split, vals["onboard"])
                ad_split.append(get(p, t, "adaptive_split") / best_os if best_os > 0 else np.nan)
        sw = [r for r in swarm if r["variant"] == v]
        rel = [r for r in sw if r["relay"]]
        split_rel = [r for r in rel if r["strategy"] in ("split_k4_int8_zstd", "adaptive_split")]
        jpeg_rel = [r for r in rel if r["strategy"] == "adaptive_all"]
        gains = []
        for r in rel:
            base = next(b for b in sw if not b["relay"] and b["profile"] == r["profile"] and b["n_uavs"] == r["n_uavs"]
                        and b["strategy"] == r["strategy"])
            gains.append(r["on_time_fps_per_uav"] - base["on_time_fps_per_uav"])
        out[v] = {
            "jpeg_best_fixed_cells": f"{jpeg_best}/16",
            "split_beats_onboard_cells": f"{split_beats_onboard}/16",
            "adaptive_all_over_jpeg": [round(float(np.nanmin(ad_all)), 2), round(float(np.nanmax(ad_all)), 2)],
            "adaptive_split_over_best_onboard_or_split": [round(float(np.nanmin(ad_split)), 2),
                                                          round(float(np.nanmax(ad_split)), 2)],
            "relayed_split_on_time": f"{sum(r['relayed_on_time'] for r in split_rel):.0f}/{sum(r['relayed_frames'] for r in split_rel):.0f}",
            "relayed_adaptive_all_on_time": f"{sum(r['relayed_on_time'] for r in jpeg_rel):.0f}/{sum(r['relayed_frames'] for r in jpeg_rel):.0f}",
            "relay_gain_fps_max": round(max(gains), 2), "relay_loss_fps_max": round(-min(gains), 2),
        }
    return out


def main(seeds: int, duration: float, workers: int) -> None:
    names = list(strategies(load_offload_configs()))
    jobs = [("single", v, p, t, s, 1, False, seeds, duration) for v in VARIANTS for p in PROFILES
            for t in HARDWARE_SCENARIOS_MS for s in names]
    sw_names = ["onboard", "split_k4_int8_zstd", "adaptive_split", "adaptive_all"]
    jobs += [("swarm", v, p, 180.0, s, n, relay, seeds, duration) for v in VARIANTS for p in ("moderate", "blackout")
             for n in SWARM_SIZES for s in sw_names for relay in ((False, True) if s != "onboard" and n > 1 else (False,))]
    with mp.get_context("fork").Pool(workers) as pool:
        res = pool.map(_cell, jobs, chunksize=1)
    single = [r for j, r in zip(jobs, res) if j[0] == "single"]
    swarm = [r for j, r in zip(jobs, res) if j[0] == "swarm"]
    write_csv(OUT / "calibrated_single.csv", single, list(single[0].keys()))
    write_csv(OUT / "calibrated_swarm.csv", swarm, list(swarm[0].keys()))
    c = conclusions(single, swarm)
    (OUT / "calibrated_conclusions.json").write_text(json.dumps(c, indent=2))
    print(json.dumps(c, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--duration", type=float, default=120.0)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    main(a.seeds, a.duration, a.workers)
