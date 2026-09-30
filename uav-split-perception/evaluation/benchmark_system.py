#!/usr/bin/env python3
"""Trace-driven system evaluation: single UAV, swarm, energy, and the adaptive policy.

All numbers come from simulation/stream_sim.py driven by measured per-configuration costs
(split_pareto_analysis.csv, codec_offload.csv) and the synthetic channel traces. Every cell
is averaged over independent seeds (independent channel realisations) and reported with a
95% t-interval across seeds.

Outputs (experiments/results/):
  system_single_uav.csv   profile x onboard-speed x strategy
  system_swarm.csv        swarm size x profile x strategy (shared cell, optional relaying)
  system_timeline.json    per-decision trace of the adaptive policy on the blackout profile
"""

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Dict, List

import numpy as np

from simulation.stream_sim import SimParams, StreamSimulator, simulate
from simulation.system_model import HARDWARE_SCENARIOS_MS, load_offload_configs, make_hardware
from simulation.trace_generator import PROFILES
from utils.logger import get_logger

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS = REPO_ROOT / "experiments" / "results"
logger = get_logger("SystemBenchmark")

# Two-sided 95% Student-t critical values, df = 1..30.
T975 = [12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228, 2.201, 2.179, 2.160, 2.145,
        2.131, 2.120, 2.110, 2.101, 2.093, 2.086, 2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042]


def t975(df: int) -> float:
    return T975[df - 1] if df <= len(T975) else 1.96


METRICS = ["on_time_fps_per_uav", "on_time_fraction", "delivered_fps_per_uav", "latency_p50_ms",
           "latency_p95_ms", "mean_map50_95_on_time", "perception_power_w", "endurance_min",
           "relayed_frames", "relayed_on_time", "policy_switches"]


def strategies(configs) -> Dict[str, Dict]:
    splits = [c for c in configs if configs[c].kind == "split"]
    codecs = [c for c in configs if configs[c].kind == "codec"]
    best_split = "k4_int8_zstd" if "k4_int8_zstd" in configs else "k4_int8"
    s = {
        "onboard": {"mode": "full_fp32"},
        "split_k4_int8": {"mode": "k4_int8"},
        "split_k4_int8_zstd": {"mode": best_split},
        "split_k9_int8": {"mode": "k9_int8"},
        "adaptive_split": {"mode": "adaptive", "candidates": ["full_fp32"] + splits},
    }
    if codecs:
        s["jpeg_q90"] = {"mode": "jpeg_q90"}
        s["adaptive_all"] = {"mode": "adaptive", "candidates": ["full_fp32"] + splits + codecs}
    return s


def aggregate(runs: List[Dict], keys: Dict) -> Dict:
    row = dict(keys)
    row["n_seeds"] = len(runs)
    for m in METRICS:
        vals = np.array([r[m] for r in runs], dtype=float)
        vals = vals[np.isfinite(vals)]
        if vals.size == 0:
            row[m], row[f"{m}_ci"] = math.nan, math.nan
            continue
        row[m] = float(vals.mean())
        row[f"{m}_ci"] = float(t975(vals.size - 1) * vals.std(ddof=1) / math.sqrt(vals.size)) if vals.size > 1 else 0.0
    usage: Dict[str, float] = {}
    for r in runs:
        tot = sum(r["config_usage"].values()) or 1
        for k, v in r["config_usage"].items():
            usage[k] = usage.get(k, 0.0) + v / tot / len(runs)
    row["config_usage"] = json.dumps({k: round(v, 3) for k, v in sorted(usage.items(), key=lambda kv: -kv[1])})
    return row


CACHE = REPO_ROOT / "experiments" / "cache" / "system"


def cached_cell(key: Dict, compute) -> Dict:
    """Aggregated result for one cell, cached on disk so interrupted runs resume where they stopped.

    The cache key includes a fingerprint of the input CSVs and simulator sources, so any change
    to measurements or code invalidates it.
    """
    import hashlib

    h = hashlib.sha256(json.dumps(key, sort_keys=True).encode())
    for f in ("split_pareto_analysis.csv", "codec_offload.csv"):
        h.update((RESULTS / f).read_bytes())
    for f in ("simulation/stream_sim.py", "simulation/system_model.py", "simulation/trace_generator.py"):
        h.update((REPO_ROOT / f).read_bytes())
    path = CACHE / f"{h.hexdigest()[:24]}.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            path.unlink()  # partial write from an interrupted run
    row = compute()
    CACHE.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(row))
    tmp.replace(path)  # atomic
    return row


def write_csv(path: Path, rows: List[Dict]) -> None:
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    logger.success(f"Wrote {len(rows)} rows -> {path.relative_to(REPO_ROOT)}")


def run(seeds: int, duration_s: float, swarm_sizes: List[int], cell_capacity: float) -> None:
    configs = load_offload_configs()
    strat = strategies(configs)

    single = []
    for profile in PROFILES:
        for t_full in HARDWARE_SCENARIOS_MS:
            hw = make_hardware(t_full)
            for name, s in strat.items():
                key = {"profile": profile, "t_full_ms": t_full, "strategy": name}
                single.append(cached_cell({**key, "seeds": seeds, "duration": duration_s}, lambda: aggregate(
                    [simulate(SimParams(hw, configs, profile=profile, duration_s=duration_s, seed=k, **s))
                     for k in range(seeds)], key)))
                logger.info(f"{profile:>16} t_full={t_full:>5.0f} {name:>20}: on-time {single[-1]['on_time_fps_per_uav']:5.2f} fps, "
                            f"p95 {single[-1]['latency_p95_ms']:6.1f} ms, P {single[-1]['perception_power_w']:5.2f} W")
    write_csv(RESULTS / "system_single_uav.csv", single)

    swarm = []
    hw = make_hardware(180.0)
    swarm_strats = {k: v for k, v in strat.items() if k in ("onboard", "split_k4_int8_zstd", "adaptive_split", "adaptive_all")}
    for profile in ("moderate", "blackout"):
        for n in swarm_sizes:
            for name, s in swarm_strats.items():
                for relay in ((False, True) if s["mode"] != "full_fp32" and n > 1 else (False,)):
                    key = {"profile": profile, "n_uavs": n, "strategy": name, "relay": relay,
                           "cell_capacity_mbps": cell_capacity, "t_full_ms": 180.0}
                    swarm.append(cached_cell({**key, "seeds": seeds, "duration": duration_s}, lambda: aggregate(
                        [simulate(SimParams(hw, configs, profile=profile, duration_s=duration_s, seed=k, n_uavs=n,
                                            cell_capacity_mbps=cell_capacity, relay=relay, **s)) for k in range(seeds)],
                        key)))
                    logger.info(f"swarm {profile:>9} N={n:<3} {name:>20} relay={relay!s:<5}: "
                                f"on-time {swarm[-1]['on_time_fps_per_uav']:5.2f} fps/UAV, relayed on-time "
                                f"{swarm[-1]['relayed_on_time']:.0f}/{swarm[-1]['relayed_frames']:.0f}")
    write_csv(RESULTS / "system_swarm.csv", swarm)

    # Timeline of the adaptive policy on the blackout profile (seed 0) for the figure.
    sim = StreamSimulator(SimParams(hw, configs, profile="blackout", duration_s=duration_s, seed=0,
                                    **strat.get("adaptive_all", strat["adaptive_split"])))
    summary = sim.run()
    u = sim.uavs[0]
    frames = [{"t_ms": f.capture_ms, "cfg": f.cfg.name if f.cfg else None, "status": f.status,
               "latency_ms": f.latency_ms if f.status == "delivered" else None} for f in u.frames]
    (RESULTS / "system_timeline.json").write_text(json.dumps({
        "t_full_ms": 180.0, "profile": "blackout", "summary": {k: summary[k] for k in METRICS},
        "bandwidth_mbps": u.bw.tolist(), "slot_ms": 10.0, "frames": frames}), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--duration", type=float, default=120.0)
    ap.add_argument("--swarm-sizes", type=int, nargs="+", default=[1, 2, 5, 10, 20])
    ap.add_argument("--cell-capacity", type=float, default=100.0)
    args = ap.parse_args()
    run(args.seeds, args.duration, args.swarm_sizes, args.cell_capacity)
