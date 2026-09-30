#!/usr/bin/env python3
"""Generalization, part 3: Monte Carlo over the whole system-parameter space.

Every scenario draws ALL system variables at once from wide ranges (onboard speed, deadline,
camera rate, channel: mean SINR, shadowing, correlation distance, speed, bandwidth, Rician K,
delay, blackouts; server speed; power figures; airframe mass and battery; policy settings; and,
for swarm scenarios, the number of UAVs and the cell capacity). For each scenario the slotted
simulator runs every fixed configuration measured for YOLOv8s (onboard, 8 cuts x 4 wire formats
plus extra k4 modes, JPEG/WebP) and both adaptive policies on the same channel realisation.

Per scenario the script records the simulated utility (on-time detections per second weighted by
relative accuracy) of every strategy and the predictions of simulation/analytic.py, so the
propositions stated there can be checked on scenarios they were not derived from.

Outputs (experiments/results/generalization/): scenarios.csv (one row per scenario),
scenario_strategies.csv (one row per scenario x strategy).
"""

import argparse
import csv
import json
import math
import multiprocessing as mp
from dataclasses import replace
from pathlib import Path
from typing import Dict, List

import numpy as np

import simulation.stream_sim as stream_sim
from simulation.analytic import Option, System, break_even_mbps, dominates, endurance_spread_bound, utility
from simulation.stream_sim import SimParams, StreamSimulator
from simulation.system_model import (EdgeHardware, PlatformModel, PolicyWeights, host_full_ms, hover_power_w,
                                     load_offload_configs)
from simulation.trace_generator import ChannelProfile, generate_trace
from utils.logger import get_logger

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "experiments" / "results" / "generalization"
logger = get_logger("Scenarios")

DURATION_S = 60.0
SWARM_STRATEGIES = ["full_fp32", "k2_int8_zstd", "k4_int8", "k4_int8_zstd", "jpeg_q50", "jpeg_q75", "jpeg_q90",
                    "jpeg_q95", "webp_q90", "adaptive_split", "adaptive_all"]

# name: (sampler, description) -- the parameter space of the study
def _logu(rng, lo, hi):
    return float(math.exp(rng.uniform(math.log(lo), math.log(hi))))


def sample(rng: np.random.Generator, swarm: bool) -> Dict:
    p = {
        "t_full_ms": _logu(rng, 10, 1000),
        "deadline_ms": _logu(rng, 100, 1000),
        "camera_fps": float(rng.choice([10, 15, 24, 30, 60])),
        "mean_sinr_db": float(rng.uniform(-5, 20)),
        "shadow_sigma_db": float(rng.uniform(2, 8)),
        "d_corr_m": float(rng.uniform(10, 100)),
        "speed_mps": float(rng.uniform(0, 30)),
        "bandwidth_mhz": _logu(rng, 5, 100),
        "rician_k_db": float(rng.uniform(-5, 15)),
        "base_delay_ms": _logu(rng, 5, 100),
        "n_blackouts": int(rng.integers(0, 4)),
        "blackout_s": float(rng.uniform(1, 5)),
        "server_scale": _logu(rng, 0.5, 4),
        "p_compute_w": float(rng.uniform(5, 30)),
        "p_idle_w": float(rng.uniform(1, 4)),
        "p_tx_w": float(rng.uniform(1.5, 6)),
        "p_rx_w": float(rng.uniform(0.5, 1.5)),
        "mass_kg": _logu(rng, 0.25, 5),
        "avionics_w": float(rng.uniform(3, 20)),
        "hysteresis": float(rng.uniform(0, 0.2)),
        "min_rel_std": float(rng.uniform(0.05, 0.3)),
        "est_tau_ms": _logu(rng, 50, 1000),
        "n_uavs": int(rng.integers(2, 31)) if swarm else 1,
        "cell_capacity_mbps": _logu(rng, 20, 400) if swarm else None,
    }
    return p


def platform_of(p: Dict) -> PlatformModel:
    # Battery ~25% of take-off mass at 150 Wh/kg; rotor disk area ~0.15 m^2 per kg (quadcopter scaling).
    return PlatformModel(battery_wh=37.5 * p["mass_kg"], avionics_w=p["avionics_w"],
                         hover_w=hover_power_w(mass_kg=p["mass_kg"], disk_area_m2=0.15 * p["mass_kg"]))


def profile_of(p: Dict, seed: int) -> ChannelProfile:
    return ChannelProfile("scenario", "Monte Carlo scenario", p["mean_sinr_db"], p["shadow_sigma_db"], p["d_corr_m"],
                          p["speed_mps"], p["bandwidth_mhz"], p["rician_k_db"], p["base_delay_ms"],
                          blackouts_s=[(10.0 * i + 5.0, 10.0 * i + 5.0 + p["blackout_s"]) for i in range(p["n_blackouts"])],
                          seed=seed)


def run_scenario(args) -> List[Dict]:
    idx, p, swarm = args
    configs = {n: replace(c, cloud_ms=c.cloud_ms * p["server_scale"]) for n, c in load_offload_configs().items()}
    host_full = host_full_ms(configs)
    hw = EdgeHardware(name="scenario", t_full_ms=p["t_full_ms"], host_full_ms=host_full, p_idle_w=p["p_idle_w"],
                      p_compute_w=p["p_compute_w"], p_tx_w=p["p_tx_w"], p_rx_idle_w=p["p_rx_w"])
    prof = profile_of(p, seed=10_000 + idx)
    platform = platform_of(p)

    # One channel realisation per UAV, shared by every strategy of this scenario.
    traces: Dict[int, list] = {}
    real_generate = generate_trace

    def cached_trace(profile, duration_s, seed, fc_hz):
        if seed not in traces:
            traces[seed] = real_generate(profile, duration_s=duration_s, seed=seed, fc_hz=fc_hz)
        return traces[seed]

    stream_sim.generate_trace = cached_trace
    names = SWARM_STRATEGIES if swarm else list(configs) + ["adaptive_split", "adaptive_all"]
    splits = [n for n, c in configs.items() if c.kind == "split"]
    rows = []
    for name in names:
        if name.startswith("adaptive"):
            cand = ["full_fp32"] + splits + ([n for n, c in configs.items() if c.kind == "codec"] if name == "adaptive_all" else [])
            mode = dict(mode="adaptive", candidates=cand)
        else:
            mode = dict(mode=name)
        sp = SimParams(hw, configs, profile=prof, n_uavs=p["n_uavs"], duration_s=DURATION_S, seed=0,
                       deadline_ms=p["deadline_ms"], cell_capacity_mbps=p["cell_capacity_mbps"],
                       est_tau_ms=p["est_tau_ms"], camera_fps=p["camera_fps"], hysteresis=p["hysteresis"],
                       policy_weights=PolicyWeights(min_rel_std=p["min_rel_std"]), platform=platform,
                       policy_delay_ms=p["base_delay_ms"] + 5.0, **mode)
        r = StreamSimulator(sp).run()
        acc = r["mean_map50_95_on_time"]
        rows.append({"scenario": idx, "strategy": name,
                     "kind": "adaptive" if name.startswith("adaptive") else configs[name].kind,
                     "on_time_fps": r["on_time_fps_per_uav"],
                     "utility": 0.0 if not np.isfinite(acc) else r["on_time_fps_per_uav"] * acc / configs["full_fp32"].map50_95,
                     "perception_w": r["perception_power_w"], "endurance_min": r["endurance_min"]})
    stream_sim.generate_trace = real_generate

    # Analytic predictions from the mean goodput of UAV 0's realisation (equal share in a swarm).
    rec = traces[min(traces)]
    goodput = float(np.mean([t["bandwidth_mbps"] * (1 - t["packet_loss_pct"] / 100) for t in rec]))
    if swarm:
        goodput = min(goodput, p["cell_capacity_mbps"] / p["n_uavs"])
    sysm = System(p["t_full_ms"], p["deadline_ms"], p["camera_fps"], p["base_delay_ms"] + 5.0)
    opts = {n: Option.from_config(c, host_full) for n, c in configs.items()}
    base_acc = configs["full_fp32"].map50_95
    ana = {n: utility(o, sysm, goodput, base_acc) for n, o in opts.items()}
    by = {r["strategy"]: r for r in rows}
    fixed = [r for r in rows if r["kind"] != "adaptive"]

    def best(kind):
        cand = [r for r in fixed if r["kind"] == kind]
        return max(cand, key=lambda r: r["utility"]) if cand else None

    bs, bc, bo = best("split"), best("codec"), by["full_fp32"]
    oracle = max(fixed, key=lambda r: r["utility"])
    k_best = opts[bs["strategy"]]
    endurance = [r["endurance_min"] for r in fixed]
    summary = {
        "scenario": idx, "swarm": swarm, **p, "mean_goodput_mbps": goodput,
        "best_split": bs["strategy"], "u_best_split": bs["utility"],
        "best_codec": bc["strategy"], "u_best_codec": bc["utility"],
        "u_onboard": bo["utility"], "oracle": oracle["strategy"], "u_oracle": oracle["utility"],
        "u_adaptive_split": by["adaptive_split"]["utility"], "u_adaptive_all": by["adaptive_all"]["utility"],
        # Proposition 2 (offload dominance): does some codec dominate every split (bits, onboard time, onboard+server)?
        "prop1_codec_dominates_all_splits": any(
            all(dominates(opts[q], opts[k], replace(sysm, server_scale=p["server_scale"])) for k in splits)
            for q in opts if opts[q].kind == "codec"),
        "acc_ratio_split_codec": opts[bs["strategy"]].acc / opts[bc["strategy"]].acc,
        # Proposition 3 (split versus onboard): analytic break-even goodput for the best split vs onboard
        "break_even_mbps": break_even_mbps(k_best, replace(sysm, server_scale=p["server_scale"])),
        "analytic_winner": max(ana, key=ana.get) if max(ana.values()) > 0 else "none",
        # Proposition 5 (endurance)
        "endurance_spread": (max(endurance) - min(endurance)) / max(endurance) if max(endurance) > 0 else 0.0,
        "endurance_bound": endurance_spread_bound(p["p_compute_w"], p["p_idle_w"], p["p_tx_w"], p["p_rx_w"],
                                                  platform.hover_w, p["avionics_w"]),
        "hover_w": platform.hover_w,
    }
    return [summary] + rows


def write_csv(path: Path, rows: List[Dict]) -> None:
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def run(n_single: int, n_swarm: int, workers: int, seed: int) -> None:
    """Resumable: finished scenarios are kept in experiments/cache/scenarios/<idx>.json."""
    cache = REPO_ROOT / "experiments" / "cache" / "scenarios"
    cache.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    jobs = [(i, sample(rng, swarm=i >= n_single), i >= n_single) for i in range(n_single + n_swarm)]
    todo = [j for j in jobs if not (cache / f"{j[0]}.json").exists()]
    logger.info(f"{len(jobs) - len(todo)} scenarios cached, {len(todo)} to run on {workers} processes")
    with mp.get_context("fork").Pool(workers) as pool:
        for out in pool.imap_unordered(run_scenario, todo):
            path = cache / f"{out[0]['scenario']}.json"
            path.with_suffix(".tmp").write_text(json.dumps(out))
            path.with_suffix(".tmp").replace(path)
    summaries, strategies = [], []
    for i in range(len(jobs)):
        out = json.loads((cache / f"{i}.json").read_text())
        summaries.append(out[0])
        strategies += out[1:]
    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUT / "scenarios.csv", summaries)
    write_csv(OUT / "scenario_strategies.csv", strategies)
    logger.success(f"Wrote {len(summaries)} scenarios")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--single", type=int, default=1000)
    ap.add_argument("--swarm", type=int, default=300)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    run(args.single, args.swarm, args.workers, args.seed)
