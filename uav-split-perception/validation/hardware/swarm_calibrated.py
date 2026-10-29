#!/usr/bin/env python3
"""Swarm study (simulation/stream_sim.py) with the device and network numbers measured on the hardware testbed.

Calibration (docs/hardware_results.md):
  onboard YOLOv8s time  758 ms  Raspberry Pi 5, sustained (throttled) 4-thread CPU
                         35 ms  Jetson Orin Nano GPU FP16, incl. pre/NMS (a camera drone that carries a GPU)
  shared capacity        25 Mbit/s  goodput of the testbed's Wi-Fi access point (22-30 Mbit/s measured)
                        100 Mbit/s  the paper's cellular cell
  payloads and server times: measured (experiments/results), as in the paper
Grid: swarm size {1,2,3,5,10,20} x channel profile {moderate, blackout} x strategy {onboard, k4 split, JPEG q90,
adaptive, adaptive + swarm admission coordination} x cell sharing {waterfill, capped (Simu5G-measured PF behaviour, validation O2)}; 5 seeds of 120 s.
Each cell is cached on disk as soon as it finishes (resumable).
Output: experiments/results/hardware/swarm_calibrated.csv, swarm_calibrated_summary.json
"""
import argparse
import hashlib
import json
import multiprocessing as mp
from pathlib import Path

import numpy as np

from evaluation.benchmark_system import aggregate, strategies
from simulation.stream_sim import SimParams, simulate
from simulation.system_model import load_offload_configs, make_hardware

OUT = Path(__file__).resolve().parent.parent.parent / "experiments" / "results" / "hardware"
CACHE = OUT / "swarm_calibrated_cache"
# --visdrone (task R3, 25 Oct 2026): every configuration's accuracy from the VisDrone fine-tuned YOLOv8s on
# VisDrone-DET val (experiments/results/visdrone_ft_split/, build_visdrone_configs.py); payloads and times unchanged
VD_DIR = OUT.parent / "visdrone_ft_split"
T_FULL = {"pi5": 758.0, "jetson": 35.0}
CAPACITY = {"wifi_ap": 25.0, "cell": 100.0}
SIZES = [1, 2, 3, 5, 10, 20]
NAMES = ["onboard", "split_k4_int8_zstd", "jpeg_q90", "adaptive_all", "adaptive_coord", "adaptive_coord_rssi"]


def measured_power():
    """Board powers measured by energy_profile.py (energy_constants.json): idle floor, sustained YOLOv8s-640
    inference, radio power above idle at about 5 Mbit/s (the radio's idle draw is inside the board idle)."""
    c = json.load(open(OUT / "energy" / "energy_constants.json"))
    out = {}
    for dev, key, comp in (("pi5", "pi", "s640"), ("jetson", "jetson", "s640")):
        b = c[key]
        p_idle = b["idle_w"]
        p_comp = p_idle + b["infer_j"][comp] / (b["infer_ms"][comp] / 1e3)
        tx = b["radio_tx_w"]["a"] + b["radio_tx_w"]["b_per_mbps"] * 5.0
        out[dev] = {"p_idle_w": p_idle, "p_compute_w": p_comp, "p_tx_w": tx, "p_rx_idle_w": 0.0, "p_a2a_tx_w": tx}
    return out


def _cell(job):
    path = CACHE / (hashlib.sha256(json.dumps(job).encode()).hexdigest()[:24] + ".json")
    if path.exists():
        return json.loads(path.read_text())
    dev, cap, sharing, profile, name, n, seeds, duration = job[:8]
    seed0 = job[8] if len(job) > 8 and isinstance(job[8], int) else 0
    mp, vd = "mp" in job[8:], "vd" in job[8:]
    configs = load_offload_configs(VD_DIR) if vd else load_offload_configs()
    hw = make_hardware(T_FULL[dev], **(measured_power()[dev] if mp else {}))
    s = dict(strategies(configs)["adaptive_all" if name.startswith("adaptive_coord") else name])
    if name.startswith("adaptive_coord"):
        s["coordination"] = "admission"
    if name == "adaptive_coord_rssi":          # + feedback with link health from the radio (stream_sim.py)
        s["coord_feedback"] = "rssi"
    runs = [simulate(SimParams(hw, configs, profile=profile, duration_s=duration, seed=seed0 + k, n_uavs=n,
                               cell_capacity_mbps=CAPACITY[cap], sharing=sharing, **s)) for k in range(seeds)]
    row = aggregate(runs, {"device": dev, "capacity": cap, "sharing": sharing, "profile": profile,
                           "strategy": name, "n_uavs": n})
    per = [u["on_time_fps"] for r in runs for u in r["per_uav"]]
    row["per_uav_min_fps"], row["per_uav_max_fps"] = float(np.min(per)), float(np.max(per))
    CACHE.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(row))
    tmp.replace(path)
    return row


def main(seeds, duration, workers, seed0=0, measured=False, visdrone=False):
    tag = (f"_seeds{seed0}-{seed0 + seeds - 1}" if seed0 else "") + ("_mp" if measured else "") + ("_visdrone" if visdrone else "")
    jobs = [(d, c, sh, p, s, n, seeds, duration) + ((seed0,) if seed0 else ()) + (("mp",) if measured else ())
            + (("vd",) if visdrone else ()) for d in T_FULL for c in CAPACITY for sh in ("waterfill", "capped")
            for p in ("moderate", "blackout") for n in SIZES for s in NAMES]
    with mp.get_context("fork").Pool(workers) as pool:
        rows = []
        for i, r in enumerate(pool.imap_unordered(_cell, jobs, chunksize=1), 1):
            rows.append(r)
            if i % 10 == 0:
                print(f"{i}/{len(jobs)} cells", flush=True)
    import csv
    keys = list(rows[0].keys())
    rows.sort(key=lambda r: (r["device"], r["capacity"], r["sharing"], r["profile"], r["n_uavs"], r["strategy"]))
    with open(OUT / f"swarm_calibrated{tag}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    summ = {}
    for d in T_FULL:
        for c in CAPACITY:
            for sh in ("waterfill", "capped"):
                for p in ("moderate", "blackout"):
                    key = f"{d}|{c}|{sh}|{p}"
                    sel = [r for r in rows if (r["device"], r["capacity"], r["sharing"], r["profile"]) == (d, c, sh, p)]
                    summ[key] = {s: [round(next(r for r in sel if r["strategy"] == s and r["n_uavs"] == n)
                                           ["on_time_fps_per_uav"], 2) for n in SIZES] for s in NAMES}
                    summ[key]["power_w"] = {s: [round(next(r for r in sel if r["strategy"] == s and r["n_uavs"] == n)
                                                      ["perception_power_w"], 3) for n in SIZES] for s in NAMES}
                    summ[key]["best_by_n"] = [max(NAMES, key=lambda s: next(r for r in sel if r["strategy"] == s and
                                                                             r["n_uavs"] == n)["on_time_fps_per_uav"])
                                              for n in SIZES]
    json.dump({"sizes": SIZES, "summary": summ}, open(OUT / f"swarm_calibrated{tag}_summary.json", "w"), indent=1)
    print("done")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--duration", type=float, default=120.0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--seed0", type=int, default=0, help="first seed (5: the held-out confirmation run)")
    ap.add_argument("--measured-power", action="store_true", help="board powers from energy_constants.json "
                    "instead of the paper's assumed ones (outputs *_mp*)")
    ap.add_argument("--visdrone", action="store_true", help="accuracies of the VisDrone fine-tuned YOLOv8s on VisDrone-DET "
                    "val (experiments/results/visdrone_ft_split/; outputs *_visdrone*)")
    a = ap.parse_args()
    main(a.seeds, a.duration, a.workers, a.seed0, a.measured_power, a.visdrone)
