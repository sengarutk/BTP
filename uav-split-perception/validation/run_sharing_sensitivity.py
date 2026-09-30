#!/usr/bin/env python3
"""Swarm results under the cell-sharing behaviour measured in Simu5G (validation O2/O2b).

The paper's simulator shares the cell by max-min fair water-filling. Simu5G confirms this for up to
5 saturated UAVs and for mixed demands, but its proportional-fair uplink scheduler starves all but
7 of 10-20 saturated UAVs, and MAX-C/I serves everyone unequally. This script repeats the swarm grid
of evaluation/benchmark_system.py with
  waterfill   the paper's model
  capped      Simu5G PF: bottlenecked UAVs beyond the 7 highest-priority get nothing
  weighted    persistent unequal (log-normal) weights, like MAX-C/I
and reports the swarm conclusions and the spread of on-time rates across UAVs.
Output: experiments/results/validation/sharing_swarm.csv, sharing_conclusions.json.
"""

import argparse
import hashlib
import json
import multiprocessing as mp

import numpy as np

from evaluation.benchmark_system import aggregate, strategies
from simulation.stream_sim import SimParams, simulate
from simulation.system_model import load_offload_configs, make_hardware
from validation.run_link_validation import OUT, write_csv

MODELS = ["waterfill", "capped", "weighted"]
SIZES = [1, 2, 5, 10, 20]
NAMES = ["onboard", "split_k4_int8_zstd", "jpeg_q90", "adaptive_split", "adaptive_all"]
CACHE = OUT / "sharing_cache"


def _cell(job):
    path = CACHE / (hashlib.sha256(json.dumps(job).encode()).hexdigest()[:24] + ".json")
    if path.exists():
        return json.loads(path.read_text())
    model, profile, name, n, relay, seeds, duration = job
    configs = load_offload_configs()
    hw = make_hardware(180.0)
    s = strategies(configs)[name]
    runs = [simulate(SimParams(hw, configs, profile=profile, duration_s=duration, seed=k, n_uavs=n,
                               cell_capacity_mbps=100.0, relay=relay, sharing=model, **s)) for k in range(seeds)]
    row = aggregate(runs, {"sharing": model, "profile": profile, "strategy": name, "n_uavs": n, "relay": relay})
    per = [u["on_time_fps"] for r in runs for u in r["per_uav"]]
    row["per_uav_min_fps"], row["per_uav_max_fps"] = float(np.min(per)), float(np.max(per))
    CACHE.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(row))
    tmp.replace(path)
    return row


def main(seeds, duration, workers):
    jobs = [(m, p, s, n, relay, seeds, duration) for m in MODELS for p in ("moderate", "blackout") for n in SIZES
            for s in NAMES for relay in ((False, True) if s != "onboard" and n > 1 else (False,))]
    with mp.get_context("fork").Pool(workers) as pool:
        rows = pool.map(_cell, jobs, chunksize=1)
    write_csv(OUT / "sharing_swarm.csv", rows, list(rows[0].keys()))
    out = {}
    for m in MODELS:
        rs = [r for r in rows if r["sharing"] == m]
        get = lambda p, s, n, relay=False: next(r for r in rs if r["profile"] == p and r["strategy"] == s  # noqa: E731
                                                and r["n_uavs"] == n and r["relay"] == relay)
        res = {}
        for p in ("moderate", "blackout"):
            res[p] = {s: [round(get(p, s, n)["on_time_fps_per_uav"], 2) for n in SIZES] for s in NAMES}
            res[p]["jpeg_q90_n20_min_max_per_uav"] = [round(get(p, "jpeg_q90", 20)["per_uav_min_fps"], 2),
                                                     round(get(p, "jpeg_q90", 20)["per_uav_max_fps"], 2)]
            res[p]["jpeg_beats_split_all_n"] = all(get(p, "jpeg_q90", n)["on_time_fps_per_uav"]
                                                   >= get(p, "split_k4_int8_zstd", n)["on_time_fps_per_uav"] for n in SIZES)
            res[p]["adaptive_all_best_all_n"] = all(get(p, "adaptive_all", n)["on_time_fps_per_uav"] + 0.05 >=
                                                    max(get(p, s, n)["on_time_fps_per_uav"] for s in NAMES) for n in SIZES)
            gains = [get(p, s, n, True)["on_time_fps_per_uav"] - get(p, s, n)["on_time_fps_per_uav"]
                     for s in NAMES if s != "onboard" for n in SIZES if n > 1]
            res[p]["relay_gain_max"] = round(max(gains), 2)
        out[m] = res
    (OUT / "sharing_conclusions.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--duration", type=float, default=120.0)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    main(a.seeds, a.duration, a.workers)
