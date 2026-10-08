#!/usr/bin/env python3
"""Summary of the controller-v2 campaign (experiments/results/hardware/adaptive2/).

Per scenario and policy: median over repetitions of the run-level (duration-weighted) metrics
  on_time_fps, acc_on_time_fps (each on-time result weighted by its variant's mAP / mAP of
  YOLOv8s@640), availability (share of time the newest result is <= deadline old),
  aoi_mean_ms (mean age of the newest result), pi_power_w.
Phase oracle: in every phase (every 4 s step for `random`), the best fixed single-server policy of
that repetition, chosen with hindsight; its duration-weighted mean is an upper bound for any
policy that commits to one fixed server and variant per phase.
Output: experiments/results/hardware/adaptive2_summary.json, adaptive2_summary.csv
"""
import csv
import glob
import json
import statistics
from collections import defaultdict
from pathlib import Path

D = Path(__file__).resolve().parent.parent.parent / "experiments" / "results" / "hardware"
METRICS = ["on_time_fps", "acc_on_time_fps", "availability", "aoi_mean_ms", "pi_power_w"]
HIGHER = {"on_time_fps": True, "acc_on_time_fps": True, "availability": True, "aoi_mean_ms": False, "pi_power_w": False}


def main():
    runs = defaultdict(dict)        # (scenario, rep) -> policy -> run
    for f in glob.glob(str(D / "adaptive2" / "a2_*_r*.json")):
        r = json.load(open(f))
        rep = int(Path(f).stem.rsplit("_r", 1)[1])
        runs[(r["scenario"], rep)][r["policy"]] = r
    scen = sorted({s for s, _ in runs})
    out, rows = {}, []
    for sc in scen:
        reps = sorted(rep for s, rep in runs if s == sc)
        pols = sorted({p for rep in reps for p in runs[(sc, rep)]})
        med = {p: {m: statistics.median(runs[(sc, rep)][p]["total"][m] for rep in reps if p in runs[(sc, rep)])
                   for m in METRICS} for p in pols}
        # phase oracle per repetition, then median over repetitions
        orc = defaultdict(list)
        for rep in reps:
            fixed = {p: r for p, r in runs[(sc, rep)].items() if p.startswith("fixed:")}
            if not fixed:
                continue
            any_run = next(iter(fixed.values()))
            phases = list(any_run["per_phase"])
            durs = [1.0] * len(phases)
            for m in METRICS:
                pick = max if HIGHER[m] else min
                vals = [pick(fx["per_phase"][ph][m] for fx in fixed.values()) for ph in phases]
                orc[m].append(sum(v * d for v, d in zip(vals, durs)) / sum(durs))
        oracle = {m: statistics.median(v) for m, v in orc.items()}
        fixed_pols = [p for p in pols if p.startswith("fixed:")]
        best_fixed = {m: (max if HIGHER[m] else min)(fixed_pols, key=lambda p: med[p][m]) for m in METRICS} if fixed_pols else {}
        res = {"reps": reps, "policies": med, "phase_oracle": oracle, "best_fixed": best_fixed}
        if "A_full" in med and fixed_pols:
            a = med["A_full"]
            res["A_full_vs_best_fixed"] = {m: a[m] / med[best_fixed[m]][m] if med[best_fixed[m]][m] else None for m in METRICS}
            res["A_full_vs_oracle"] = {m: a[m] / oracle[m] if oracle.get(m) else None for m in METRICS}
            if "static_multi" in med:
                res["A_full_vs_static_multi"] = {m: a[m] / med["static_multi"][m] if med["static_multi"][m] else None
                                                 for m in METRICS}
        out[sc] = res
        for p in sorted(pols, key=lambda p: -med[p]["acc_on_time_fps"]):
            rows.append({"scenario": sc, "policy": p, **{m: round(med[p][m], 3) for m in METRICS}})
        rows.append({"scenario": sc, "policy": "phase_oracle(fixed)", **{m: round(oracle.get(m, float("nan")), 3) for m in METRICS}})
    json.dump(out, open(D / "adaptive2_summary.json", "w"), indent=1)
    with open(D / "adaptive2_summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["scenario", "policy"] + METRICS)
        w.writeheader()
        w.writerows(rows)
    cur = None
    for r in rows:
        if r["scenario"] != cur:
            cur = r["scenario"]
            print(f"\n== {cur}   reps={out[cur]['reps']}")
            print(f"{'policy':24s} {'on-time':>8s} {'acc-wtd':>8s} {'avail':>6s} {'AoI ms':>7s} {'Pi W':>5s}")
        print(f"{r['policy']:24s} {r['on_time_fps']:8.2f} {r['acc_on_time_fps']:8.2f} {r['availability']:6.3f} "
              f"{r['aoi_mean_ms']:7.0f} {r['pi_power_w']:5.2f}")
    for sc, res in out.items():
        if "A_full_vs_best_fixed" in res:
            print(sc, "A_full / best fixed:", {k: round(v, 2) for k, v in res["A_full_vs_best_fixed"].items() if v},
                  "| / oracle:", {k: round(v, 2) for k, v in res["A_full_vs_oracle"].items() if v},
                  "| / static_multi:", {k: round(v, 2) for k, v in res.get("A_full_vs_static_multi", {}).items() if v})


if __name__ == "__main__":
    main()
