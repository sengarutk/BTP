#!/usr/bin/env python3
"""Adaptive controller vs fixed strategies on the scripted mission (experiments/results/hardware/adaptive/).

For every policy and phase: median over repetitions of on-time (<= deadline), delivered, and
within-1-s frames/s, and accuracy-weighted on-time frames/s (each on-time result weighted by the
mAP of the action that produced it, relative to FP32). The phase oracle is the best fixed policy
in each phase chosen with hindsight (an upper bound for any policy that commits to one fixed
strategy per phase); the adaptive policy's share of it and its margin over every fixed policy
over the whole mission are reported.
Output: experiments/results/hardware/adaptive_summary.json and adaptive_summary.csv
"""
import csv
import glob
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

D = Path(__file__).resolve().parent.parent.parent / "experiments" / "results" / "hardware"
METRICS = ["on_time_fps", "acc_weighted_on_time", "delivered_fps", "within_1s_fps"]


def main():
    runs = defaultdict(list)
    for f in glob.glob(str(D / "adaptive" / "ad_mission_*_r*.json")):
        r = json.load(open(f))
        runs[r["policy"]].append(r)
    phases = list(next(iter(runs.values()))[0]["per_phase"].keys())
    med = {}
    for pol, rs in runs.items():
        med[pol] = {ph: {m: statistics.median(r["per_phase"][ph][m] for r in rs) for m in METRICS} for ph in phases}
        med[pol]["mission"] = {m: statistics.median(r["total"][m] for r in rs) for m in METRICS}
        med[pol]["_runs"] = len(rs)
        med[pol]["_switches"] = statistics.median(r["switches"] for r in rs)
    fixed = [p for p in runs if p != "adaptive"]
    oracle = {ph: {m: max(med[p][ph][m] for p in fixed) for m in METRICS} for ph in phases}
    oracle_choice = {ph: max(fixed, key=lambda p: med[p][ph]["on_time_fps"]) for ph in phases}
    oracle["mission"] = {m: sum(oracle[ph][m] for ph in phases) / len(phases) for m in METRICS}
    best_fixed = max(fixed, key=lambda p: med[p]["mission"]["on_time_fps"])
    out = {"policies": med, "phase_oracle": oracle, "phase_oracle_choice": oracle_choice,
           "best_fixed_overall": best_fixed}
    if "adaptive" in med:
        ad = med["adaptive"]
        out["adaptive_vs_oracle"] = {ph: {m: (ad[ph][m] / oracle[ph][m] if oracle[ph][m] > 0 else None) for m in METRICS}
                                     for ph in phases + ["mission"]}
        out["adaptive_vs_best_fixed"] = {m: ad["mission"][m] / med[best_fixed]["mission"][m] for m in METRICS}
        out["adaptive_ge_fixed_by_phase"] = {
            ph: sum(ad[ph]["on_time_fps"] >= med[p][ph]["on_time_fps"] - 0.25 for p in fixed) for ph in phases}
    json.dump(out, open(D / "adaptive_summary.json", "w"), indent=1)
    rows = []
    for pol in sorted(med, key=lambda p: -med[p]["mission"]["on_time_fps"]):
        row = {"policy": pol, "runs": med[pol]["_runs"], "switches": med[pol]["_switches"]}
        for ph in phases + ["mission"]:
            row[f"{ph}_on_time"] = round(med[pol][ph]["on_time_fps"], 2)
        row["mission_delivered"] = round(med[pol]["mission"]["delivered_fps"], 2)
        row["mission_within_1s"] = round(med[pol]["mission"]["within_1s_fps"], 2)
        row["mission_acc_weighted"] = round(med[pol]["mission"]["acc_weighted_on_time"], 2)
        rows.append(row)
    rows.append({"policy": "phase_oracle", "runs": "", "switches": "",
                 **{f"{ph}_on_time": round(oracle[ph]["on_time_fps"], 2) for ph in phases + ["mission"]},
                 "mission_delivered": round(oracle["mission"]["delivered_fps"], 2),
                 "mission_within_1s": round(oracle["mission"]["within_1s_fps"], 2),
                 "mission_acc_weighted": round(oracle["mission"]["acc_weighted_on_time"], 2)})
    with open(D / "adaptive_summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    hdr = ["policy"] + [p[:10] for p in phases] + ["MISSION", "deliv", "<=1s", "accW"]
    print(" ".join(f"{h:>11s}" for h in hdr))
    for r in rows:
        vals = [r["policy"]] + [r[f"{ph}_on_time"] for ph in phases] + [r["mission_on_time"], r["mission_delivered"],
                                                                         r["mission_within_1s"], r["mission_acc_weighted"]]
        print(" ".join(f"{str(v):>11s}" for v in vals))
    print("oracle choice per phase:", oracle_choice)
    if "adaptive" in med:
        print("adaptive / oracle (on-time):", {k: (round(v["on_time_fps"], 2) if v["on_time_fps"] else None)
                                              for k, v in out["adaptive_vs_oracle"].items()})
        print("adaptive / best fixed overall (%s):" % best_fixed,
              {k: round(v, 2) for k, v in out["adaptive_vs_best_fixed"].items()})


if __name__ == "__main__":
    main()
