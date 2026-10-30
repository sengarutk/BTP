#!/usr/bin/env python3
"""Are the controller's deadline probabilities calibrated on the hardware? (the check of brief 19.8, on real runs)

Every offloaded frame of an adaptive2.py run (code since 29 Oct 2026) logs what the controller predicted when it sent
it (frames[].pred: p_on = P(result within the 300 ms deadline), p_late = P(within the 1 s late window), the goodput
estimate and the expected latency). The run's metrics add the measured latency (lat_ms; none if the result never
came back). This bins the predictions against the outcomes, with the same reliability bins, expected calibration
error and Brier score as the replay (replay_oracle.calib_table), per strategy and per scenario.

usage: calib_hw.py DIR [DIR ...] [--out FILE.json]     (DIR: a campaign folder of a2_<scenario>__<strategy>__r<k>.json)
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def calib_table(pairs):
    """pairs: (predicted probability, outcome 0/1) -> reliability bins, expected calibration error, Brier score
    (the same definition as replay_oracle.calib_table, repeated so this runs without the replay's data)."""
    if not pairs:
        return None
    p = np.array([x[0] for x in pairs], float)
    y = np.array([x[1] for x in pairs], float)
    edges = np.linspace(0, 1, 11)
    bins, ece = [], 0.0
    for i in range(10):
        m = (p >= edges[i]) & ((p < edges[i + 1]) if i < 9 else (p <= 1.0))
        if m.sum():
            bins.append({"bin": f"{edges[i]:.1f}-{edges[i + 1]:.1f}", "n": int(m.sum()),
                         "pred": float(p[m].mean()), "observed": float(y[m].mean())})
            ece += m.sum() / len(p) * abs(p[m].mean() - y[m].mean())
    return {"n": len(p), "mean_pred": float(p.mean()), "observed": float(y.mean()), "ece": float(ece),
            "brier": float(np.mean((p - y) ** 2)), "bins": bins}


def pairs_of(run, deadline_ms, late_ms):
    on, late = [], []
    for f in run["frames"]:
        pr = f.get("pred")
        if not pr:
            continue
        lat = f.get("lat_ms")
        on.append((pr["p_on"], float(lat is not None and lat <= deadline_ms)))
        late.append((pr["p_late"], float(lat is not None and lat <= late_ms)))
    return on, late


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--late-ms", type=float, default=1000.0, help="the controller's --late-ms (adaptive2 default)")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    by = defaultdict(lambda: ([], []))
    n_runs, skipped = 0, []
    for d in a.dirs:
        for f in sorted(Path(d).glob("a2_*.json")):
            m = re.match(r"a2_(.+?)__(.+?)__r\d+\.json$", f.name)
            run = json.load(open(f))
            if "frames" not in run:
                continue
            on, late = pairs_of(run, run.get("deadline_ms", 300.0), a.late_ms)
            if not on:
                skipped.append(f.name)              # an older run (no logged predictions) or no offloading
                continue
            n_runs += 1
            sc, st = (m.group(1), m.group(2)) if m else ("?", run.get("policy", "?"))
            for k in (("all", "all"), (st, "all"), (st, sc)):
                by[k][0].extend(on)
                by[k][1].extend(late)
    out = {"runs": n_runs, "skipped_without_predictions": skipped, "late_ms": a.late_ms, "groups": {}}
    for (st, sc), (on, late) in sorted(by.items()):
        out["groups"][f"{st}/{sc}"] = {"p_on_vs_deadline": calib_table(on), "p_late_vs_late_ms": calib_table(late)}
    for k, v in out["groups"].items():
        for name, t in v.items():
            if t:
                print(f"{k:32s} {name:18s} n {t['n']:6d}  ECE {t['ece']:.3f}  Brier {t['brier']:.3f}")
    if skipped:
        print(f"skipped {len(skipped)} runs without predictions")
    if a.out:
        json.dump(out, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
