#!/usr/bin/env python3
"""Cross-validates the Python streaming simulator against a packet-level ns-3 replay (V3, V4).

For every case, both simulators get identical inputs: the same channel trace per UAV (generated
with the seeds the Python simulator uses), the same frame size, onboard time and server time of
the measured configuration, the same camera rate, deadline and frame logic. ns-3 then carries the
frames over real TCP on links that follow the trace slot by slot (and, for swarms, through a
shared fair-queued bottleneck), whereas the Python simulator uses its fluid model.

V4  single UAV: 4 channel profiles x 2 onboard speeds x 3 offloading configurations
V3  swarm: 2 profiles x N in {1,2,5,10,20} x 2 configurations, 100 Mbit/s shared cell

The comparison reports on-time frames/s per UAV from both, their difference, and whether the
ranking of strategies within each setting (including onboard inference, which uses no network)
is the same. Output: experiments/results/validation/stream_compare.csv and stream_summary.json.
"""

import argparse
import csv
import json
import os
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from simulation.stream_sim import SimParams, simulate
from simulation.system_model import load_offload_configs, make_hardware
from simulation.trace_generator import PROFILES, export_trace_csv, generate_trace
from validation.run_link_validation import OUT, binary, env, write_csv

CACHE = OUT / "stream_cache"


def ns3_run(cfg, hw, profile, n, seed, duration, cell):
    """Runs ns-3 on the traces the Python simulator would generate for (profile, seed, UAV)."""
    key = f"{profile}_{cfg.name}_t{hw.t_full_ms:g}_n{n}_c{cell or 0:g}_s{seed}_d{duration:g}"
    cached = CACHE / f"{key}.json"
    if cached.exists():
        return json.loads(cached.read_text())
    prof = PROFILES[profile]
    with tempfile.TemporaryDirectory() as tmp:
        for u in range(n):  # same seed formula as StreamSimulator.__init__
            export_trace_csv(Path(tmp) / f"uav{u}.csv",
                             generate_trace(prof, duration_s=duration, seed=prof.seed * 100_003 + seed * 1_009 + u))
        out = subprocess.run(
            [binary("stream"), f"--nUav={n}", f"--traceDir={tmp}", f"--cellMbps={cell or 0}",
             f"--payloadBytes={int(round(cfg.payload_bytes))}", f"--onboardMs={hw.onboard_ms(cfg)}",
             f"--cloudMs={cfg.cloud_ms}", "--deadlineMs=300", "--fps=30", f"--duration={duration}", f"--seed={seed}"],
            capture_output=True, text=True, check=True, env=env()).stdout
    rows = list(csv.DictReader(out.strip().splitlines()))
    res = {"on_time_fps_per_uav": sum(int(r["on_time"]) for r in rows) / duration / n,
           "delivered_fps_per_uav": sum(int(r["delivered"]) for r in rows) / duration / n,
           "per_uav": rows}
    CACHE.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps(res))
    return res


def py_run(cfg_name, configs, hw, profile, n, seed, duration, cell):
    r = simulate(SimParams(hw, configs, mode=cfg_name, profile=profile, n_uavs=n, duration_s=duration, seed=seed,
                           cell_capacity_mbps=cell))
    return {"on_time_fps_per_uav": r["on_time_fps_per_uav"], "delivered_fps_per_uav": r["delivered_fps_per_uav"]}


def cases(quick: bool):
    seeds = [0, 1] if quick else [0, 1, 2]
    single = [("single", p, t, c, 1, None, s) for p in PROFILES for t in (40.0, 180.0)
              for c in ("k4_int8_zstd", "k4_int8", "jpeg_q90") for s in seeds]
    swarm = [("swarm", p, 180.0, c, n, 100.0, s) for p in ("moderate", "blackout") for n in (1, 2, 5, 10, 20)
             for c in ("k4_int8_zstd", "jpeg_q90") for s in seeds[:2]]
    return single + swarm


def main(duration: float, quick: bool, workers: int) -> None:
    configs = load_offload_configs()
    hws = {t: make_hardware(t) for t in (40.0, 180.0)}

    def one(c):
        study, profile, t, cfg, n, cell, seed = c
        hw = hws[t]
        a = py_run(cfg, configs, hw, profile, n, seed, duration, cell)
        b = ns3_run(configs[cfg], hw, profile, n, seed, duration, cell)
        return {"study": study, "profile": profile, "t_full_ms": t, "config": cfg, "n_uavs": n,
                "cell_mbps": cell or 0, "seed": seed,
                "py_on_time_fps": round(a["on_time_fps_per_uav"], 3),
                "ns3_on_time_fps": round(b["on_time_fps_per_uav"], 3),
                "py_delivered_fps": round(a["delivered_fps_per_uav"], 3),
                "ns3_delivered_fps": round(b["delivered_fps_per_uav"], 3)}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        rows = list(ex.map(one, cases(quick)))
    write_csv(OUT / "stream_compare.csv", rows, list(rows[0].keys()))

    # Aggregate over seeds, then compare.
    groups = {}
    for r in rows:
        k = (r["study"], r["profile"], r["t_full_ms"], r["config"], r["n_uavs"])
        groups.setdefault(k, []).append(r)
    agg = []
    for k, rs in groups.items():
        py, ns = np.mean([r["py_on_time_fps"] for r in rs]), np.mean([r["ns3_on_time_fps"] for r in rs])
        agg.append({"study": k[0], "profile": k[1], "t_full_ms": k[2], "config": k[3], "n_uavs": k[4],
                    "py": py, "ns3": ns, "diff": ns - py})
    diffs = np.array([a["diff"] for a in agg])
    pys, nss = np.array([a["py"] for a in agg]), np.array([a["ns3"] for a in agg])

    # Ranking agreement within each single-UAV setting, including onboard inference (network-free).
    rank_same, rank_total = 0, 0
    for p in PROFILES:
        for t in (40.0, 180.0):
            onboard = py_run("full_fp32", configs, hws[t], p, 1, 0, duration, None)["on_time_fps_per_uav"]
            sel = {a["config"]: a for a in agg if a["study"] == "single" and a["profile"] == p and a["t_full_ms"] == t}
            py_rank = sorted(list(sel) + ["onboard"], key=lambda c: -(onboard if c == "onboard" else sel[c]["py"]))
            ns_rank = sorted(list(sel) + ["onboard"], key=lambda c: -(onboard if c == "onboard" else sel[c]["ns3"]))
            rank_total += 1
            rank_same += int(py_rank[0] == ns_rank[0])
    summary = {
        "n_settings": len(agg), "duration_s": duration,
        "mean_abs_diff_fps": float(np.mean(np.abs(diffs))), "max_abs_diff_fps": float(np.max(np.abs(diffs))),
        "pearson_r": float(np.corrcoef(pys, nss)[0, 1]),
        "best_strategy_agrees": f"{rank_same}/{rank_total}",
        "rows": agg,
    }
    (OUT / "stream_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=2))
    for a in sorted(agg, key=lambda a: (a["study"], a["profile"], a["t_full_ms"], a["n_uavs"], a["config"])):
        print(f"{a['study']:6} {a['profile']:17} t={a['t_full_ms']:>5.0f} N={a['n_uavs']:<2} {a['config']:13} "
              f"python {a['py']:6.2f}  ns-3 {a['ns3']:6.2f}  diff {a['diff']:+6.2f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--duration", type=float, default=60.0)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--workers", type=int, default=int(os.environ.get("VALIDATION_WORKERS", 6)))
    a = ap.parse_args()
    main(a.duration, a.quick, a.workers)
