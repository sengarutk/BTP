#!/usr/bin/env python3
"""Item 6 of the laptop strengthening (16 Nov 2026; predictions: docs/laptop_strengthening_predictions_nov16.md):
how much airflow removes the heat cost. Airflow lowers the board's thermal resistance R, so the replay's plant slope
(C/W) and time constant (R*C) are both scaled by k (replay.py plant_k); the controller's own thermal model is not told.
Policies (replay, validated setting: --netem reset, the "power" onboard model; common random numbers):
  af{k}_v41      v4.1, blackout hold always
  af{k}_hold     v4.1 with the hold capped at 78 C
  af{k}_guard    v4.1 with the hold capped and the hard guard at 76.5 C (the final controller's thermal rules)
  af{k}_noprice  the unpriced controller (v3 + forecaster)
usage: replay_airflow.py run --scenario mission --phase-s 240 --seeds 1-5 [--only ...]
       replay_airflow.py analyze   -> experiments/results/hardware/replay/airflow_nov16/airflow_summary.json
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import replay as R  # noqa: E402
import replay_accumo as A  # noqa: E402

OUT = R.HW / "replay" / "airflow_nov16"
KS = (1.0, 0.9, 0.8, 0.7, 0.6, 0.5)
BASES = {"v41": dict(R.POLICIES["v41"]), "hold": dict(R.POLICIES["v41"], hold_max_c=78.0),
         "guard": dict(R.POLICIES["v41"], hold_max_c=76.5, guard_hard_c=76.5),
         "noprice": dict(R.POLICIES["stream_fc2"])}
for k in KS:
    for b, cf in BASES.items():
        R.POLICIES[f"af{k:g}_{b}"] = dict(cf, plant_k=k)
ALL = [f"af{k:g}_{b}" for k in KS for b in BASES]


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--scenario", nargs="+", default=["mission"])
    r.add_argument("--phase-s", type=float, default=240.0)
    r.add_argument("--seeds", default="1-5")
    r.add_argument("--only", nargs="+")
    sub.add_parser("analyze")
    a = ap.parse_args()
    if a.cmd == "run":
        A.cmd_run(argparse.Namespace(policy=a.only or ALL, scenario=a.scenario, phase_s=a.phase_s, seeds=a.seeds,
                                     netem="reset", onboard_power="power", out=str(OUT)))
        return
    rows = [json.load(open(f)) for f in sorted((OUT / "rows").glob("*.json"))]
    by = defaultdict(dict)
    for x in rows:
        by[f"{x['scenario']}_{x['phase_s']:g}s"].setdefault(x["policy"], []).append(x)
    out = {}
    for sc, pols in sorted(by.items()):
        out[sc] = {}
        for pol in ALL:
            if pol not in pols:
                continue
            rs = sorted(pols[pol], key=lambda x: x["seed"])
            e = {m: float(np.mean([x[m] for x in rs])) for m in ("sAP", "pi_w", "temp_mean_c", "temp_max_c", "hot_share")}
            e["hot_share_max"] = float(max(x["hot_share"] for x in rs))
            e["seeds"] = [x["seed"] for x in rs]
            k, b = pol[2:].split("_", 1)
            ref = {x["seed"]: x for x in pols.get(f"af{k}_v41", [])}
            if b != "v41" and ref:
                d = [x["sAP"] - ref[x["seed"]]["sAP"] for x in rs if x["seed"] in ref]
                w = [x["pi_w"] - ref[x["seed"]]["pi_w"] for x in rs if x["seed"] in ref]
                e["sAP_minus_v41"], e["pi_w_minus_v41"] = A.paired(d), A.paired(w)
            out[sc][pol] = e
            print(f"{sc:14s} k {k:>4s} {b:8s} sAP {e['sAP']:.4f} W {e['pi_w']:.2f} T {e['temp_mean_c']:.1f}/"
                  f"{e['temp_max_c']:.1f} hot {100 * e['hot_share']:.1f} % (max {100 * e['hot_share_max']:.1f})"
                  + (f"  dsAP {e['sAP_minus_v41']['mean']:+.4f}" if "sAP_minus_v41" in e else ""), flush=True)
    json.dump(out, open(OUT / "airflow_summary.json", "w"), indent=1)


if __name__ == "__main__":
    main()
