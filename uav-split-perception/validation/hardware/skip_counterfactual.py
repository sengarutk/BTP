#!/usr/bin/env python3
"""Item 7a of the laptop strengthening (16 Nov 2026; predictions: docs/laptop_strengthening_predictions_nov16.md):
is the late-path skip (adaptive2 --late-path-skip 0.5, designed after the final_nov multihop result) post hoc?

On board logs of v4.1-family runs WITHOUT the skip, every frame the skip would have acted on is identified: a network
frame whose logged p_on is below 0.5, sent while the other network path's latest decision (at most 0.5 s earlier) had
p_on >= 0.5. (The skip then re-picks a smaller on-time setting on that path or sends nothing; which one is not in the
log, so these frames are "affected", not "removed".) Their observed on-time share (result within 300 ms) is measured:
a skip is right where most of them were late anyway.
  held out (never used to design the skip): mesh4, topology_nov, relaynoise_nov, energy_nov (v41 runs, 14-15 Nov)
  design data: final_nov (v41 runs)
  recalibrated skip: fix_nov's runs without the skip (v41final24, 16 Nov), p_on mapped by the per-path isotonic map
  fitted on 14-15 Nov (calib_recal.py): which affected frames would a per-path recalibrated skip still act on?
usage: python validation/hardware/skip_counterfactual.py -> experiments/results/hardware/skip_counterfactual/skip_cf.json
"""
import datetime as dt
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import calib_recal as CR  # noqa: E402

H = HERE.parent.parent / "experiments" / "results" / "hardware"
TH, WIN = 0.5, 15          # threshold; window 0.5 s = 15 frames at 30 fps
SETS = {"held_out": [("mesh4", "v41"), ("topology_nov", "v41"), ("relaynoise_nov", "v41"), ("energy_nov", "v41")],
        "design": [("final_nov", "v41")], "recal_16nov": [("fix_nov", "v41final24")]}


def topo(sc):
    return "multihop" if sc.startswith("multihop") else "one_hop"


def affected(run, pmap=None):
    last = {}
    out = []
    for f in sorted(run["frames"], key=lambda x: x["id"]):
        s, pr = f.get("server"), f.get("pred")
        if s not in ("laptop", "jetson") or not pr:
            continue
        p = pr["p_on"] if pmap is None else float(CR.iso_apply(pmap[s], np.array([pr["p_on"]]))[0])
        other = "jetson" if s == "laptop" else "laptop"
        if p < TH and other in last and f["id"] - last[other][0] <= WIN and last[other][1] >= TH:
            lat = f.get("lat_ms")
            out.append((s, lat is not None and lat <= run.get("deadline_ms", 300.0), lat))
        last[s] = (f["id"], p)
    n_net = sum(1 for f in run["frames"] if f.get("server") in ("laptop", "jetson") and f.get("pred"))
    return out, n_net


def summarize(rows):
    res = {}
    for key in sorted({(r[0], r[1]) for r in rows}):
        aff = [a for r in rows if (r[0], r[1]) == key for a in r[2]]
        n_net = sum(r[3] for r in rows if (r[0], r[1]) == key)
        e = {"runs": sum(1 for r in rows if (r[0], r[1]) == key), "network_frames": n_net, "affected": len(aff),
             "affected_share": len(aff) / n_net if n_net else None}
        for s in ("laptop", "jetson", "all"):
            a = [x for x in aff if s == "all" or x[0] == s]
            if a:
                lats = [x[2] for x in a if x[2] is not None]
                e[s] = {"n": len(a), "on_time_share": float(np.mean([x[1] for x in a])),
                        "lat_median_ms": float(np.median(lats)) if lats else None,
                        "no_result_share": float(np.mean([x[2] is None for x in a]))}
        res[f"{key[0]}|{key[1]}"] = e
    return res


def main():
    out = {"threshold": TH, "window_frames": WIN}
    # the per-path isotonic maps of calib_recal.py, fitted on 14-15 Nov only
    rows = CR.frames()
    day = np.array([r[0] for r in rows])
    srv = np.array([r[1] for r in rows])
    p = np.array([r[2] for r in rows])
    y = np.array([r[3] for r in rows])
    tr = day < CR.TEST_DAY
    pmap = {s: CR.pav(p[tr & (srv == s)], y[tr & (srv == s)]) for s in ("laptop", "jetson")}
    for name, camps in SETS.items():
        rr = []
        for camp, st in camps:
            for f in sorted((H / f"vid_campaign_{camp}").glob(f"a2_*__{st}__r*.json")):
                sc = re.match(r"a2_(.+?)__", f.name).group(1)
                run = json.load(open(f))
                a, n = affected(run)
                rr.append((topo(sc), "raw", a, n))
                if name == "recal_16nov":
                    a2, n2 = affected(run, pmap)
                    rr.append((topo(sc), "recalibrated_per_path", a2, n2))
        out[name] = summarize(rr)
    (H / "skip_counterfactual").mkdir(exist_ok=True)
    json.dump(out, open(H / "skip_counterfactual" / "skip_cf.json", "w"), indent=1)
    for name in SETS:
        for k, e in out[name].items():
            print(f"{name:12s} {k:32s} runs {e['runs']:2d} affected {e['affected']:5d} "
                  f"({100 * (e['affected_share'] or 0):.1f} % of network frames) " +
                  " ".join(f"{s}: n {e[s]['n']} on time {100 * e[s]['on_time_share']:.0f} % "
                           f"(median {e[s]['lat_median_ms'] or float('nan'):.0f} ms)" for s in ("laptop", "jetson") if s in e))


if __name__ == "__main__":
    main()
