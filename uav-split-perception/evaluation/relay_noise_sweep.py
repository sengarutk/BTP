#!/usr/bin/env python3
"""Noise on relayed links (hardening plan, Phase 4; 10 Nov 2026): does relaying through another drone stay useful when the
air-to-air link is noisy, does any strategy ranking change, and how far ahead does the adaptive controller stay?

The paper's swarm setting (benchmark_system.py: cell capacity 100 Mbit/s, onboard 180 ms, 5 seeds of 120 s, moderate and
blackout channel profiles) with relaying on, swept over
  shadowing   sigma of the per-link log-normal shadowing of the air-to-air links: 3 (the paper's), 6 and 8 dB
  loss        per-packet loss on the relay hop: 0, 1, 5 and 10 %, with link-layer retransmission (1500-byte packets,
              a lost packet is resent until it arrives: its airtime again plus a 1 ms backoff per retry, an assumption)
  swarm size  5, 10 and 20 drones
  hops        1 (direct air-to-air link to the neighbour) or 2 (through an intermediate drone, store-and-forward,
              each hop with its own shadowing and losses; added 11 Nov 2026)
and the strategies of the paper's swarm study that send data (fixed k4 INT8 + zstd split, adaptive among onboard and
splits, adaptive among all options), each also without relaying (unaffected by the relay link) as the reference.
A relayed frame crosses two hops: the air-to-air link to the neighbour, then the neighbour's cellular uplink, which
carries the trace's own residual loss as before.
--calib pi5 (paper 2): the swarm of paper 2 instead (validation/hardware/swarm_calibrated.py, its "_mp" setting): the
Pi 5's measured 758 ms onboard YOLOv8s, the measured board powers, and the testbed Wi-Fi access point's 25 Mbit/s as
the shared capacity -> experiments/results/relay_noise_pi5/.
usage: relay_noise_sweep.py [--workers 6] [--hops 1 2] [--calib paper1|pi5]  (rows of hops already in relay_noise.csv are reused: the
       simulator is deterministic, and one-hop results were checked identical after the two-hop change)   -> experiments/results/relay_noise/relay_noise.csv and summary.json
"""
import argparse
import csv
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
OUT = REPO / "experiments" / "results" / "relay_noise"
SIGMAS, LOSSES, SIZES, PROFILES_ = (3.0, 6.0, 8.0), (0.0, 0.01, 0.05, 0.10), (5, 10, 20), ("moderate", "blackout")
STRATS = ("split_k4_int8_zstd", "adaptive_split", "adaptive_all")
SEEDS, DURATION, CELL, T_FULL, RETRY_MS = 5, 120.0, 100.0, 180.0, 1.0
HOPS = (1, 2)
METRICS = ("on_time_fps_per_uav", "relayed_frames", "relayed_on_time", "mean_map50_95_on_time")


CALIB = {"paper1": dict(t_full=T_FULL, cell=CELL, out="relay_noise"),
         "pi5": dict(t_full=758.0, cell=25.0, out="relay_noise_pi5")}


def make_hw(calib):
    from simulation.system_model import make_hardware
    if calib == "pi5":
        from validation.hardware.swarm_calibrated import measured_power
        return make_hardware(CALIB[calib]["t_full"], **measured_power()["pi5"])
    return make_hardware(CALIB[calib]["t_full"])


def cell(job):
    from evaluation.benchmark_system import strategies
    from simulation.stream_sim import SimParams, simulate
    from simulation.system_model import load_offload_configs
    prof, n, strat, relay, sigma, loss, hops, calib = job
    cfg = load_offload_configs()
    s = strategies(cfg)[strat]
    hw = make_hw(calib)
    runs = [simulate(SimParams(hw, cfg, profile=prof, duration_s=DURATION, seed=k, n_uavs=n, cell_capacity_mbps=CALIB[calib]["cell"],
                               relay=relay, a2a_shadow_sigma_db=sigma, a2a_loss=loss, a2a_retry_ms=RETRY_MS,
                               relay_hops=hops, **s))
            for k in range(SEEDS)]
    row = {"profile": prof, "n_uavs": n, "strategy": strat, "relay": relay, "sigma_db": sigma, "loss": loss,
           "hops": hops}
    for m in METRICS:
        v = np.array([r[m] for r in runs], float)
        row[m] = float(np.nanmean(v))
        row[m + "_seeds"] = [float(x) for x in v]
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--hops", type=int, nargs="+", default=list(HOPS))
    ap.add_argument("--calib", default="paper1", choices=list(CALIB))
    a = ap.parse_args()
    global OUT
    OUT = REPO / "experiments" / "results" / CALIB[a.calib]["out"]
    c = a.calib
    jobs = [(p, n, s, False, 3.0, 0.0, 1, c) for p in PROFILES_ for n in SIZES for s in STRATS]
    jobs += [(p, n, s, True, sg, ls, h, c) for h in a.hops for p in PROFILES_ for n in SIZES for s in STRATS
             for sg in SIGMAS for ls in LOSSES]
    have = {}
    if (OUT / "relay_noise.csv").exists():
        for r in csv.DictReader(open(OUT / "relay_noise.csv")):
            r = {**r, "n_uavs": int(r["n_uavs"]), "relay": r["relay"] == "True", "sigma_db": float(r["sigma_db"]),
                 "loss": float(r["loss"]), "hops": int(r.get("hops") or 1), **{m: float(r[m]) for m in METRICS}}
            have[(r["profile"], r["n_uavs"], r["strategy"], r["relay"], r["sigma_db"], r["loss"], r["hops"], c)] = r
    todo = [j for j in jobs if j not in have]
    print(f"{len(jobs)} cells, {len(jobs) - len(todo)} reused, {len(todo)} to run", flush=True)
    with ProcessPoolExecutor(a.workers) as ex:
        new = dict(zip(todo, ex.map(cell, todo)))
    rows = [have.get(j) or new[j] for j in jobs]
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "relay_noise.csv", "w", newline="") as f:
        keys = [k for k in new[todo[0]] if not k.endswith("_seeds")] if todo else list(rows[0])
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    summary(rows, a.calib)


def summary_hops(rows, hops):
    key = lambda r: (r["profile"], r["n_uavs"], r["sigma_db"], r["loss"])  # noqa: E731
    ref = {(r["profile"], r["n_uavs"], r["strategy"]): r for r in rows if not r["relay"]}
    rel = [r for r in rows if r["relay"] and r["hops"] == hops]
    # 1) are relayed frames still on time? share for the adaptive controller with all options, by shadowing x loss
    on_time = {}
    for sg in SIGMAS:
        for ls in LOSSES:
            rr = [r for r in rel if r["strategy"] == "adaptive_all" and r["sigma_db"] == sg and r["loss"] == ls]
            fr, ot = sum(r["relayed_frames"] for r in rr), sum(r["relayed_on_time"] for r in rr)
            on_time[f"{sg:g}dB_{100 * ls:g}pct"] = {"relayed_frames": fr, "relayed_on_time": ot,
                                                     "share": ot / fr if fr else None}
    # 2) does any strategy ranking change? per (profile, size): the leader among the three strategies with relaying
    base_order, changes = {}, []
    for p in PROFILES_:
        for n in SIZES:
            def order(sg, ls):
                rr = {r["strategy"]: r["on_time_fps_per_uav"] for r in rel
                      if (r["profile"], r["n_uavs"], r["sigma_db"], r["loss"]) == (p, n, sg, ls)}
                return sorted(rr, key=lambda s: -rr[s]), rr
            o0, _ = order(3.0, 0.0)
            base_order[f"{p}_{n}"] = o0
            for sg in SIGMAS:
                for ls in LOSSES:
                    o, v = order(sg, ls)
                    if o != o0:
                        changes.append({"profile": p, "n_uavs": n, "sigma_db": sg, "loss": ls, "order": o, "values": v})
    # 3) relaying gain (relay minus no relay) and the adaptive controller's lead over the fixed split
    gain, lead = [], []
    for r in rel:
        b = ref[(r["profile"], r["n_uavs"], r["strategy"])]
        gain.append({**{k: r[k] for k in ("profile", "n_uavs", "strategy", "sigma_db", "loss")},
                     "relay_gain_fps": r["on_time_fps_per_uav"] - b["on_time_fps_per_uav"]})
        if r["strategy"] == "adaptive_all":
            fx = next(x for x in rel if key(x) == key(r) and x["strategy"] == "split_k4_int8_zstd")
            lead.append({**{k: r[k] for k in ("profile", "n_uavs", "sigma_db", "loss")},
                         "lead_fps": r["on_time_fps_per_uav"] - fx["on_time_fps_per_uav"]})
    g = np.array([x["relay_gain_fps"] for x in gain])
    ld = np.array([x["lead_fps"] for x in lead])
    ga = np.array([x["relay_gain_fps"] for x in gain if x["strategy"] == "adaptive_all"])
    return {"cells": len(rel), "relayed_on_time_adaptive_all": on_time, "base_order": base_order,
            "ranking_changes": changes,
            "relay_gain_fps": {"min": float(g.min()), "max": float(g.max()),
                               "adaptive_all_min": float(ga.min()), "adaptive_all_max": float(ga.max()),
                               "adaptive_all_median": float(np.median(ga)), "per_cell": gain},
            "adaptive_lead_fps": {"min": float(ld.min()), "max": float(ld.max()), "per_cell": lead}}


def summary(rows, calib="paper1"):
    hops = sorted({r["hops"] for r in rows if r["relay"]})
    out = {"setting": {"calib": calib, "seeds": SEEDS, "duration_s": DURATION, "cell_mbps": CALIB[calib]["cell"],
                       "t_full_ms": CALIB[calib]["t_full"],
                       "retry_ms": RETRY_MS, "sigmas_db": SIGMAS, "losses": LOSSES, "sizes": SIZES, "hops": hops},
           **{f"hops{h}": summary_hops(rows, h) for h in hops}}
    if len(hops) == 2:     # what the second hop costs the adaptive controller, per cell (on-time fps per UAV)
        k = lambda r: (r["profile"], r["n_uavs"], r["strategy"], r["sigma_db"], r["loss"])  # noqa: E731
        one = {k(r): r for r in rows if r["relay"] and r["hops"] == 1}
        d = [r["on_time_fps_per_uav"] - one[k(r)]["on_time_fps_per_uav"] for r in rows
             if r["relay"] and r["hops"] == 2 and r["strategy"] == "adaptive_all"]
        out["second_hop_cost_adaptive_all_fps"] = {"min": float(min(d)), "max": float(max(d)),
                                                    "median": float(np.median(d))}
    json.dump(out, open(OUT / "summary.json", "w"), indent=1)
    for h in hops:
        s = out[f"hops{h}"]
        sh = {k: round(v["share"], 3) for k, v in s["relayed_on_time_adaptive_all"].items() if v["share"] is not None}
        print(f"hops {h}: relayed on-time share {sh}")
        print(f"  ranking changes {len(s['ranking_changes'])}; relay gain adaptive_all {s['relay_gain_fps']['adaptive_all_min']:.3f}"
              f"..{s['relay_gain_fps']['adaptive_all_max']:.3f}; lead {s['adaptive_lead_fps']['min']:.2f}..{s['adaptive_lead_fps']['max']:.2f}")
    if "second_hop_cost_adaptive_all_fps" in out:
        print("second hop, adaptive_all:", out["second_hop_cost_adaptive_all_fps"])


if __name__ == "__main__":
    main()
