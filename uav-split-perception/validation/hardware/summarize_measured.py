#!/usr/bin/env python3
"""Accuracy + MEASURED energy and heat of a live campaign with power logging on both boards
(campaign_energy.sh / campaign_main.sh: --power-log on the Pi camera, JLOG=1 power_logger on the Jetson).

Unlike energy_rescore.py (model reconstruction), every watt here is measured in the run:
  camera W      the Pi's PMIC log (measured_energy.mean_w), temperature mean / max, share of time >= 80 C
  edge W        the Jetson's live INA3221 log (pw_<run>.json, whole board); edge extra = edge W - measured idle
  system views  (as energy_model.system_views; a run that never sent a frame to the Jetson has no edge drone)
                extra = camera + edge extra, board = camera + edge W, dedicated = board + edge flight power
Accuracy: streaming AP with the live camera-motion-aligned forecaster (summarize_vid.py --fc v2 --live must
have filled <dir>/_eval_cache.json first). Also availability (share of time the held result is <= 300 ms old).
Per policy: pooled mean +- 95 % t-interval; paired differences against --ref over (scenario, repetition).
usage: summarize_measured.py --dir DIR [--ref A_eco_tight]
Output: <dir>_measured_summary.json
"""
import argparse
import glob
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from energy_model import drone_classes, endurance_min  # noqa: E402
from summarize_vid import tci  # noqa: E402

HW = Path(__file__).resolve().parent.parent.parent / "experiments" / "results" / "hardware"
SAP = "sAP_quality_fcv2live"


def per_run(d):
    ec = json.load(open(HW / "energy" / "energy_constants.json"))
    j_idle = ec["jetson"]["idle_w"]
    edge_flight = drone_classes()["edge_1.5kg"]["flight_w"]
    cache = json.load(open(d / "_eval_cache.json")) if (d / "_eval_cache.json").exists() else {}
    rows = []
    for f in sorted(glob.glob(str(d / "a2_*__r*.json"))):
        stem = Path(f).stem
        if stem.endswith(("_dets", "_livefc")):
            continue
        sc, pol, rep = stem[3:].split("__")[:3]
        r = json.load(open(f))
        me = r.get("measured_energy")
        if not me or not me.get("mean_w"):
            continue
        row = {"scenario": sc, "policy": pol, "rep": int(rep[1:]), "sAP": cache.get(stem[3:], {}).get(SAP),
               "availability": r["total"]["availability"], "camera_w": me["mean_w"],
               "temp_mean_c": me["temp_mean_c"], "temp_max_c": me["temp_max_c"]}
        lg = [x for x in me["log_t_w_c"] if x[2] == x[2]]
        row["hot_share"] = float(np.mean([x[2] >= 80.0 for x in lg])) if lg else None
        used_edge = any(fr.get("server") == "jetson" for fr in r["frames"])
        pw = d / f"pw_{stem[3:]}.json"
        ew = json.load(open(pw))["mean_w"] if pw.exists() else None
        row.update(edge_used=used_edge, edge_w=ew if used_edge else 0.0,
                   edge_extra_w=max(0.0, ew - j_idle) if (used_edge and ew) else 0.0)
        if used_edge and ew is None:
            row["edge_w"] = row["edge_extra_w"] = None      # no live Jetson log for this run
        if row["edge_w"] is not None:
            row["system_w_extra"] = row["camera_w"] + row["edge_extra_w"]
            row["system_w_board"] = row["camera_w"] + row["edge_w"]
            row["system_w_dedicated"] = row["system_w_board"] + (edge_flight if used_edge else 0.0)
        for k in ("camera", "extra", "board", "dedicated"):
            w = row.get("camera_w" if k == "camera" else f"system_w_{k}")
            row[f"sAP_per_w_{k}"] = row["sAP"] / w if (row["sAP"] is not None and w) else None
        for cls in ("mini_249g", "quad_1.2kg"):
            row[f"endur_{cls}"] = endurance_min(cls, row["camera_w"])
            edge_end = endurance_min("edge_1.5kg", row["edge_w"]) if (used_edge and row["edge_w"]) else float("inf")
            row[f"swarm_lifetime_{cls}"] = min(row[f"endur_{cls}"], edge_end)
            if row["sAP"] is not None:
                row[f"mission_{cls}"] = row["sAP"] * row[f"swarm_lifetime_{cls}"]
        me_edge = me.get("mu_edge_log") or []
        row["mu_edge_mean"] = float(np.mean([x[1] for x in me_edge])) if me_edge else None
        tl = me.get("thermal_log_t_lam_pred_meas") or []
        row["lam_t_mean"] = float(np.mean([x[1] for x in tl])) if tl else None
        rows.append(row)
    return rows


KEYS = ["sAP", "availability", "camera_w", "edge_w", "edge_extra_w", "system_w_extra", "system_w_board",
        "sAP_per_w_camera", "sAP_per_w_extra", "sAP_per_w_board", "sAP_per_w_dedicated", "temp_mean_c",
        "hot_share", "endur_mini_249g", "swarm_lifetime_mini_249g", "mission_mini_249g", "mission_quad_1.2kg",
        "mu_edge_mean", "lam_t_mean"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--ref", default="A_eco_tight")
    a = ap.parse_args()
    d = Path(a.dir).resolve()
    rows = per_run(d)
    by = defaultdict(list)
    for r in rows:
        by[r["policy"]].append(r)
    pooled = {}
    for pol, rs in sorted(by.items()):
        s = {"n": len(rs)}
        for k in KEYS:
            v = [r[k] for r in rs if r.get(k) is not None]
            if v:
                s[k], s[k + "_ci"] = tci(v)
        pooled[pol] = s
    ref = {(r["scenario"], r["rep"]): r for r in by.get(a.ref, [])}
    paired = {}
    for pol, rs in by.items():
        if pol == a.ref:
            continue
        out = {}
        for k in ("sAP", "camera_w", "system_w_board", "sAP_per_w_board", "availability", "hot_share",
                  "mission_mini_249g"):
            diffs = [r[k] - ref[(r["scenario"], r["rep"])][k] for r in rs if (r["scenario"], r["rep"]) in ref
                     and r.get(k) is not None and ref[(r["scenario"], r["rep"])].get(k) is not None]
            if diffs:
                m, h = tci(diffs)
                out[k] = {"diff": m, "ci": h, "n": len(diffs), "ahead": int(sum(x > 0 for x in diffs))}
        paired[pol] = out
    json.dump({"dir": str(d), "ref": a.ref, "sap_key": SAP, "runs": rows, "pooled": pooled, "paired_vs_ref": paired},
              open(str(d) + "_measured_summary.json", "w"), indent=1, default=float)
    f = lambda s, k, p=4: f"{s[k]:.{p}f}" if k in s and s[k] == s[k] else "  -  "  # noqa: E731
    print(f"{'policy':22s} n  sAP     avail  camW  edgeW  sysB  sAP/W cam/extra/board   hot  mission249")
    for pol, s in pooled.items():
        print(f"{pol:22s} {s['n']:2d} {f(s, 'sAP')} {f(s, 'availability', 3)} {f(s, 'camera_w', 2)} "
              f"{f(s, 'edge_w', 2)} {f(s, 'system_w_board', 2)} {f(s, 'sAP_per_w_camera')}/"
              f"{f(s, 'sAP_per_w_extra')}/{f(s, 'sAP_per_w_board')} {f(s, 'hot_share', 2)} "
              f"{f(s, 'mission_mini_249g', 3)}")
    print(f"paired vs {a.ref}:")
    for pol, o in paired.items():
        print(f"  {pol:22s}", "  ".join(f"{k}={v['diff']:+.4f}±{v['ci']:.4f} ({v['ahead']}/{v['n']})"
                                       for k, v in o.items() if k in ("sAP", "camera_w", "sAP_per_w_board")))


if __name__ == "__main__":
    main()
