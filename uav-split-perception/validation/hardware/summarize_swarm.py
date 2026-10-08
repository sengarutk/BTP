#!/usr/bin/env python3
"""Two-camera swarm campaign summary (experiments/results/hardware/swarm_duo/, campaign_swarm.sh).

Per run and camera: streaming AP on VisDrone-VID val with the camera-aligned forecaster (forecast_tuning_v2.json,
newest-result holding, camera motion as computed live on the camera when available) and without forecasting,
plus availability and mean age of information from the run. Per (scenario, setting): mean and 95 % t-interval over
repetitions of the swarm mean and the worst camera, and the Pi camera alone. Paired comparisons (same scenario and
repetition): duo_coord against duo_none and duo_fixed, and every duo setting against pi_alone for the Pi camera.
Output: experiments/results/hardware/swarm_duo_summary.json
"""
import glob
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from stream_ap import VID, evaluate
from summarize_vid import tci

HW = Path(__file__).resolve().parent.parent.parent / "experiments" / "results" / "hardware"


def main(d=HW / "swarm_duo"):
    labels = json.load(open(VID / "labels.json"))
    fp = json.load(open(HW / "forecast_tuning_v2.json"))["best"]["params"]
    cache_f = d / "_eval_cache.json"
    cache = json.load(open(cache_f)) if cache_f.exists() else {}
    runs = defaultdict(dict)          # (scenario, setting, rep) -> {camera: metrics}
    for f in sorted(glob.glob(str(d / "a2_*__r*.json"))):
        stem = Path(f).stem[3:]
        parts = stem.split("__")
        sc, st, rep = parts[0], parts[1], int(parts[2][1:])
        cam = parts[3] if len(parts) > 3 else "pi"
        if stem not in cache:
            r = json.load(open(f))
            live = Path(f[:-5] + "_livefc.npz").exists()
            cache[stem] = {"sAP_fc": evaluate(Path(f), labels, "newest", forecast=fp, live=live)["sAP"],
                           "sAP": evaluate(Path(f), labels, "newest")["sAP"],
                           "availability": r["total"]["availability"], "aoi_ms": r["total"]["aoi_mean_ms"],
                           "power_w": r["total"]["pi_power_w"], "on_time_fps": r["total"]["on_time_fps"],
                           "laptop_share": sum(1 for x in r["frames"] if x.get("server") == "laptop") /
                           max(1, sum(1 for x in r["frames"] if x.get("server")))}
            json.dump(cache, open(cache_f, "w"))
        runs[(sc, st, rep)][cam] = cache[stem]
    out = {"cells": {}, "paired": {}}
    for sc in sorted({k[0] for k in runs}):
        for st in sorted({k[1] for k in runs if k[0] == sc}):
            reps = [v for k, v in runs.items() if k[:2] == (sc, st)]
            row = {"reps": len(reps)}
            for m in ("sAP_fc", "sAP", "availability", "aoi_ms", "laptop_share"):
                for cam in ("pi", "jetson"):
                    vals = [r[cam][m] for r in reps if cam in r]
                    if vals:
                        row[f"{cam}_{m}"] = tci(vals)
                if st != "pi_alone":
                    both = [r for r in reps if "pi" in r and "jetson" in r]
                    row[f"mean_{m}"] = tci([(r["pi"][m] + r["jetson"][m]) / 2 for r in both])
                    row[f"worst_{m}"] = tci([min(r["pi"][m], r["jetson"][m]) for r in both])
            out["cells"][f"{sc}|{st}"] = row
    for a, b, key in (("duo_coord", "duo_none", "mean_sAP_fc"), ("duo_coord", "duo_none", "worst_sAP_fc"),
                      ("duo_coord", "duo_fixed", "mean_sAP_fc"), ("duo_none", "duo_fixed", "mean_sAP_fc"),
                      ("duo_coord", "pi_alone", "pi_sAP_fc"), ("duo_none", "pi_alone", "pi_sAP_fc")):
        diffs = []
        for (sc, st, rep), ra in runs.items():
            rb = runs.get((sc, b, rep))
            if st != a or not rb:
                continue
            def val(r, k):
                m = k.split("_", 1)[1]
                if k.startswith("mean_"):
                    return (r["pi"][m] + r["jetson"][m]) / 2 if "jetson" in r else None
                if k.startswith("worst_"):
                    return min(r["pi"][m], r["jetson"][m]) if "jetson" in r else None
                return r["pi"][m]
            va, vb = val(ra, key), val(rb, key)
            if va is not None and vb is not None:
                diffs.append(va - vb)
        if diffs:
            mu, hw = tci(diffs)
            out["paired"][f"{a} - {b} ({key})"] = {"n": len(diffs), "mean_diff": mu, "ci95": hw,
                                                   "wins": int(sum(x > 0 for x in diffs))}
    json.dump(out, open(HW / "swarm_duo_summary.json", "w"), indent=1)
    for k, row in out["cells"].items():
        print(k, {m: (round(v[0], 4), round(v[1], 4)) for m, v in row.items() if m != "reps" and "sAP_fc" in m},
              "avail", {m: round(v[0], 3) for m, v in row.items() if m.endswith("availability")})
    for k, v in out["paired"].items():
        print(f"{k:50s} n={v['n']:2d} diff={v['mean_diff']:+.4f}±{v['ci95']:.4f} wins={v['wins']}/{v['n']}")


if __name__ == "__main__":
    main()
