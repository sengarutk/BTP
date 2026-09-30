#!/usr/bin/env python3
"""Swarm relay results when the relay forwards packet by packet (validation O5).

ns-3 (validation/run_relay_validation.py) shows that the paper's relay model is conservative on
two counts: the analytic A2A goodput is below ns-3's, and a relay that forwards packets as they
arrive overlaps the two hops, whereas the model forwards whole frames. This script repeats the
swarm relay grid of evaluation/benchmark_system.py under
  analytic/frame   the paper's setting
  ns3/frame        ns-3 A2A goodput (V1)
  analytic/packet  packet forwarding
  ns3/packet       both
and reports the relay gain and the share of relayed frames on time.
Output: experiments/results/validation/relay_forwarding_swarm.csv, relay_forwarding_conclusions.json
"""

import argparse
import hashlib
import json
import multiprocessing as mp

from evaluation.benchmark_system import aggregate, strategies
from simulation.stream_sim import SimParams, simulate
from simulation.system_model import load_offload_configs, make_hardware
from validation.run_link_validation import OUT, write_csv

VARIANTS = [("analytic", "frame"), ("ns3", "frame"), ("analytic", "packet"), ("ns3", "packet")]
SIZES = [2, 5, 10, 20]
NAMES = ["split_k4_int8_zstd", "jpeg_q90", "adaptive_split", "adaptive_all"]
CACHE = OUT / "relay_forwarding_cache"


def _cell(job):
    path = CACHE / (hashlib.sha256(json.dumps(job).encode()).hexdigest()[:24] + ".json")
    if path.exists():
        return json.loads(path.read_text())
    a2a, fwd, profile, name, n, relay, seeds, duration = job
    configs = load_offload_configs()
    hw = make_hardware(180.0)
    s = strategies(configs)[name]
    runs = [simulate(SimParams(hw, configs, profile=profile, duration_s=duration, seed=k, n_uavs=n,
                               cell_capacity_mbps=100.0, relay=relay, a2a_model=a2a, relay_forwarding=fwd, **s))
            for k in range(seeds)]
    row = aggregate(runs, {"a2a_model": a2a, "forwarding": fwd, "profile": profile, "strategy": name,
                           "n_uavs": n, "relay": relay})
    CACHE.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(row))
    tmp.replace(path)
    return row


def main(seeds, duration, workers):
    base = [("analytic", "frame", p, s, n, False, seeds, duration) for p in ("moderate", "blackout")
            for n in SIZES for s in NAMES]
    rel = [(a, f, p, s, n, True, seeds, duration) for a, f in VARIANTS for p in ("moderate", "blackout")
           for n in SIZES for s in NAMES]
    with mp.get_context("fork").Pool(workers) as pool:
        rows = pool.map(_cell, base + rel, chunksize=1)
    write_csv(OUT / "relay_forwarding_swarm.csv", rows, list(rows[0].keys()))
    no_relay = {(r["profile"], r["strategy"], r["n_uavs"]): r["on_time_fps_per_uav"] for r in rows if not r["relay"]}
    out = {}
    for a, f in VARIANTS:
        rs = [r for r in rows if r["relay"] and r["a2a_model"] == a and r["forwarding"] == f]
        gains = {(r["profile"], r["strategy"], r["n_uavs"]): r["on_time_fps_per_uav"] - no_relay[(r["profile"], r["strategy"], r["n_uavs"])]
                 for r in rs}
        best = max(gains, key=gains.get)
        frac = {}
        for s in NAMES:
            sel = [r for r in rs if r["strategy"] == s]
            done, tot = sum(r["relayed_on_time"] for r in sel), sum(r["relayed_frames"] for r in sel)
            frac[s] = round(done / tot, 4) if tot else None
        out[f"{a}/{f}"] = {"relay_gain_fps_max": round(gains[best], 2), "relay_gain_at": list(best),
                           "relay_loss_fps_max": round(-min(gains.values()), 2), "relayed_on_time_fraction": frac}
    (OUT / "relay_forwarding_conclusions.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--duration", type=float, default=120.0)
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()
    main(a.seeds, a.duration, a.workers)
