#!/usr/bin/env python3
"""The 24-minute runs (vid_campaign_long: PHASE_S=240, 6 phases x 4 min): does heat build up over a mission and
change which controller is best?

Per run, in 4-minute windows (one per phase) and in total: Pi power and temperature (measured log), time at or
above 80 C, ARM-throttling proxy (temperature >= 80 C), the energy and heat prices (mu, lam_T), freshness, and
streaming AP per phase (from the scorer's per-phase sAP, forecaster v2, live camera motion). Also the first and
last 6 minutes compared (does the gap between controllers grow as the board heats?). Pooled per policy over
repetitions; pairs by repetition against the reference.
usage: summarize_long.py [--dir DIR] [--ref v5]  (needs summarize_vid.py --fc v2 --live on DIR first, for sAP)
Output: <dir>_long_summary.json
"""
import argparse
import glob
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
HW = Path(__file__).resolve().parent.parent.parent / "experiments" / "results" / "hardware"


def per_run(d):
    cache = json.load(open(d / "_eval_cache.json")) if (d / "_eval_cache.json").exists() else {}
    rows = []
    for f in sorted(glob.glob(str(d / "a2_*__r*.json"))):
        stem = Path(f).stem
        if stem.endswith(("_dets", "_livefc")):
            continue
        sc, pol, rep = stem[3:].split("__")[:3]
        r = json.load(open(f))
        me = r.get("measured_energy") or {}
        lg = np.array([x for x in me.get("log_t_w_c", []) if x[1] == x[1] and x[2] == x[2]], float)
        if not len(lg):
            continue
        t = lg[:, 0] - lg[0, 0]
        win = []
        names = list(r["per_phase"])
        dur = t[-1] / max(1, len(names))
        for i, ph in enumerate(names):
            m = (t >= i * dur) & (t < (i + 1) * dur)
            win.append({"phase": ph, "pi_w": float(lg[m, 1].mean()) if m.any() else None,
                        "temp_c": float(lg[m, 2].mean()) if m.any() else None,
                        "temp_end_c": float(lg[m, 2][-1]) if m.any() else None,
                        "hot_share": float((lg[m, 2] >= 80).mean()) if m.any() else None,
                        "availability": r["per_phase"][ph]["availability"]})
        tl = me.get("thermal_log_t_lam_pred_meas") or []
        ml = me.get("mu_log") or []
        c = cache.get(stem[3:], {})
        first, last = t <= 360, t >= t[-1] - 360
        rows.append({"policy": pol, "scenario": sc, "rep": int(rep[1:]), "sAP": c.get("sAP_quality_fcv2live"),
                     "pi_w": float(lg[:, 1].mean()), "temp_mean_c": float(lg[:, 2].mean()),
                     "temp_max_c": float(lg[:, 2].max()), "hot_share": float((lg[:, 2] >= 80).mean()),
                     "hot_first6": float((lg[first, 2] >= 80).mean()), "hot_last6": float((lg[last, 2] >= 80).mean()),
                     "temp_first6": float(lg[first, 2].mean()), "temp_last6": float(lg[last, 2].mean()),
                     "availability": r["total"]["availability"], "windows": win,
                     "lam_t_mean": float(np.mean([x[1] for x in tl])) if tl else None,
                     "lam_t_max": float(np.max([x[1] for x in tl])) if tl else None,
                     "mu_mean": float(np.mean([x[1] for x in ml])) if ml else None})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(HW / "vid_campaign_long"))
    ap.add_argument("--ref", default="v5")
    a = ap.parse_args()
    d = Path(a.dir)
    rows = per_run(d)
    by = defaultdict(list)
    for r in rows:
        by[r["policy"]].append(r)
    pooled = {}
    keys = ("sAP", "pi_w", "temp_mean_c", "temp_max_c", "hot_share", "hot_first6", "hot_last6", "temp_first6",
            "temp_last6", "availability", "lam_t_mean", "lam_t_max", "mu_mean")
    for p, rs in sorted(by.items()):
        pooled[p] = {"n": len(rs), **{k: float(np.mean([x[k] for x in rs if x.get(k) is not None]))
                                      for k in keys if any(x.get(k) is not None for x in rs)}}
        nwin = len(rs[0]["windows"])
        pooled[p]["windows"] = [{k: float(np.mean([x["windows"][i][k] for x in rs if x["windows"][i][k] is not None]))
                                 for k in ("pi_w", "temp_c", "temp_end_c", "hot_share", "availability")}
                                | {"phase": rs[0]["windows"][i]["phase"]} for i in range(nwin)]
    ref = {r["rep"]: r for r in by.get(a.ref, [])}
    paired = {p: {k: [x[k] - ref[x["rep"]][k] for x in rs if x["rep"] in ref and x.get(k) is not None
                      and ref[x["rep"]].get(k) is not None] for k in ("sAP", "pi_w", "hot_share", "availability")}
              for p, rs in by.items() if p != a.ref}
    json.dump({"ref": a.ref, "runs": rows, "pooled": pooled, "paired_vs_ref": paired},
              open(str(d) + "_long_summary.json", "w"), indent=1)
    print(f"{'policy':22s} n  sAP     PiW   Tmean  hot  hot first6/last6  T first6/last6  fresh  lamT")
    for p, s in pooled.items():
        print(f"{p:22s} {s['n']} {s.get('sAP', float('nan')):.4f} {s['pi_w']:.2f} {s['temp_mean_c']:.1f} "
              f"{s['hot_share']:.2f} {s['hot_first6']:.2f}/{s['hot_last6']:.2f}       {s['temp_first6']:.1f}/"
              f"{s['temp_last6']:.1f}     {s['availability']:.3f}  {s.get('lam_t_mean', float('nan')):.2f}")
    print("per-phase temperature (mean):")
    for p, s in pooled.items():
        print(f"  {p:22s}", " ".join(f"{w['phase'][:12]}:{w['temp_c']:.0f}" for w in s["windows"]))


if __name__ == "__main__":
    main()
