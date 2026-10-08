#!/usr/bin/env python3
"""Task-level campaign summary (experiments/results/hardware/vid_campaign/).

Per run: streaming AP on VisDrone-VID val (stream_ap.py) with the 'newest' and the 'quality' holding
rule (each also with the train-tuned motion forecaster of forecast.py, suffix _fc), plus availability, mean age of information and Pi perception power from the run itself.
Per scenario and policy: mean and 95 % t-interval over repetitions. Paired comparison of every policy
with the reference policy (default A_stream): mean difference over (scenario, repetition) pairs, its
95 % t-interval, and wins.
Output: experiments/results/hardware/<dir name>_summary.json and .csv (vid_summary.* for vid_campaign)
"""
import argparse
import csv
import glob
import json
import statistics
from collections import defaultdict
from pathlib import Path

import numpy as np

from stream_ap import VID, evaluate

HW = Path(__file__).resolve().parent.parent.parent / "experiments" / "results" / "hardware"


def tci(x):
    x = np.asarray(x, float)
    if len(x) < 2:
        return float(x.mean()) if len(x) else float("nan"), float("nan")
    from math import sqrt
    tcrit = {1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57, 6: 2.45, 7: 2.36, 8: 2.31, 9: 2.26}.get(len(x) - 1, 1.96)
    return float(x.mean()), float(tcrit * x.std(ddof=1) / sqrt(len(x)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="A_stream")
    ap.add_argument("--dir", default=str(HW / "vid_campaign"))
    ap.add_argument("--fc", default="", help="forecaster version: '' (forecast_tuning.json) or 'v2' "
                                             "(forecast_tuning_v2.json, camera-motion aligned); metrics get suffix _fc<ver>")
    ap.add_argument("--live", action="store_true", help="use the camera motion computed live on the Pi (runs made "
                                                        "with --live-forecast); metrics get suffix _fc<ver>live")
    a = ap.parse_args()
    labels = json.load(open(VID / "labels.json"))
    acc_tab = json.load(open(HW / "variant_accuracy_visdrone.json"))
    decay = json.load(open(HW / "staleness_decay.json"))
    cache_f = Path(a.dir) / "_eval_cache.json"
    cache = json.load(open(cache_f)) if cache_f.exists() else {}
    sfx = "_" + a.fc if a.fc else ""
    tuning = HW / f"forecast_tuning{sfx}.json"
    fparams = json.load(open(tuning))["best"]["params"] if tuning.exists() else None
    dfc = HW / f"staleness_decay_forecast{sfx}.json"     # with forecasting, the quality rule uses the forecast decay
    decay_fc = json.load(open(dfc)) if dfc.exists() else decay
    runs = []
    for f in sorted(glob.glob(f"{a.dir}/a2_*__*__r*.json")):
        stem = Path(f).stem[3:]
        sc, name, rep = stem.split("__")
        if stem not in cache:
            run = json.load(open(f))
            e_new = evaluate(Path(f), labels, "newest")
            e_q = evaluate(Path(f), labels, "quality", acc_tab, decay)
            cache[stem] = {"sAP_newest": e_new["sAP"], "sAP_quality": e_q["sAP"], "fresh_AP": e_new["fresh_AP"],
                           "sAP50_quality": e_q["sAP50"], "phase_sAP_quality": e_q["per_phase_sAP"],
                           "availability": run["total"]["availability"], "aoi_ms": run["total"]["aoi_mean_ms"],
                           "on_time_fps": run["total"]["on_time_fps"], "pi_w": run["total"]["pi_power_w"]}
            json.dump(cache, open(cache_f, "w"))
        fk = "_fc" + a.fc + ("live" if a.live else "")
        if fparams and "sAP_newest" + fk not in cache[stem]:
            cache[stem]["sAP_newest" + fk] = evaluate(Path(f), labels, "newest", forecast=fparams, live=a.live)["sAP"]
            json.dump(cache, open(cache_f, "w"))
        if fparams and cache[stem].get("fc_decay" + a.fc + ("live" if a.live else "")) != dfc.exists():
            cache[stem]["sAP_quality" + fk] = evaluate(Path(f), labels, "quality", acc_tab, decay_fc, fparams,
                                                       live=a.live)["sAP"]
            cache[stem]["fc_decay" + a.fc + ("live" if a.live else "")] = dfc.exists()
            json.dump(cache, open(cache_f, "w"))
        runs.append((sc, name, int(rep[1:]), cache[stem]))
    fk = "_fc" + a.fc + ("live" if a.live else "")
    fc_metrics = ["sAP_quality" + fk, "sAP_newest" + fk] if fparams else []
    metrics = ["sAP_quality", "sAP_newest"] + fc_metrics + ["fresh_AP", "availability", "aoi_ms", "on_time_fps", "pi_w"]
    by = defaultdict(list)
    for sc, name, rep, m in runs:
        by[(sc, name)].append((rep, m))
    rows, out = [], {"scenarios": {}, "paired_vs_ref": {}}
    for sc in sorted({k[0] for k in by}):
        out["scenarios"][sc] = {}
        for name in sorted({k[1] for k in by if k[0] == sc}):
            vals = by[(sc, name)]
            row = {"scenario": sc, "policy": name, "reps": len(vals)}
            for m in metrics:
                mu, hw = tci([v[1][m] for v in vals])
                row[m], row[m + "_ci"] = round(mu, 4), round(hw, 4)
            rows.append(row)
            out["scenarios"][sc][name] = row
    # paired comparison with the reference policy
    for metric in ["sAP_quality", "sAP_newest"] + fc_metrics:
        res = {}
        for name in sorted({k[1] for k in by}):
            if name == a.ref:
                continue
            diffs, rel, wins = [], [], 0
            for (sc, nm), vals in by.items():
                if nm != name:
                    continue
                refv = dict((r, m[metric]) for r, m in by.get((sc, a.ref), []))
                for rep, m in vals:
                    if rep in refv:
                        d = refv[rep] - m[metric]
                        diffs.append(d)
                        rel.append(refv[rep] / m[metric] - 1 if m[metric] > 0 else float("nan"))
                        wins += d > 0
            if diffs:
                mu, hw = tci(diffs)
                res[name] = {"pairs": len(diffs), "mean_diff": round(mu, 4), "ci95": round(hw, 4), "wins": wins,
                             "median_rel_gain": round(float(np.nanmedian(rel)), 3)}
        out["paired_vs_ref"][metric] = res
    if fc_metrics:   # forecasting gain per policy, pooled over scenarios and repetitions
        out["forecast_gain"] = {}
        for name in sorted({k[1] for k in by}):
            ms = [m for (sc, nm), vals in by.items() if nm == name for _, m in vals]
            out["forecast_gain"][name] = {h: round(float(np.median([m[h + fk] / m[h] - 1 for m in ms if m[h] > 0])), 3)
                                          for h in ("sAP_quality", "sAP_newest")}
    stem_out = ("vid_summary" if Path(a.dir).name == "vid_campaign" else Path(a.dir).name + "_summary") + sfx + ("_live" if a.live else "")
    json.dump(out, open(HW / f"{stem_out}.json", "w"), indent=1)
    with open(HW / f"{stem_out}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    for sc in out["scenarios"]:
        print(f"\n== {sc}")
        print(f"{'policy':22s} {'n':>2s} {'sAP(quality)':>16s} {'sAP(newest)':>16s} {'sAP(q)+fc':>9s} {'freshAP':>8s} {'avail':>6s} {'AoI':>6s} {'PiW':>5s}")
        for name, r in sorted(out["scenarios"][sc].items(), key=lambda x: -x[1]["sAP_quality"]):
            print(f"{name:22s} {r['reps']:2d} {r['sAP_quality']:.4f}±{r['sAP_quality_ci']:.4f} "
                  f"{r['sAP_newest']:.4f}±{r['sAP_newest_ci']:.4f} {r.get('sAP_quality' + fk, float('nan')):9.4f} {r['fresh_AP']:8.4f} {r['availability']:6.3f} "
                  f"{r['aoi_ms']:6.0f} {r['pi_w']:5.2f}")
    print(f"\npaired: {a.ref} minus policy (all scenarios x repetitions)")
    for metric, res in out["paired_vs_ref"].items():
        print(metric)
        for name, r in sorted(res.items(), key=lambda x: -x[1]["mean_diff"]):
            print(f"  {name:22s} n={r['pairs']:3d} diff={r['mean_diff']:+.4f}±{r['ci95']:.4f} wins={r['wins']}/{r['pairs']} "
                  f"median rel gain={r['median_rel_gain']:+.1%}")
    if "forecast_gain" in out:
        print("\nmedian relative sAP gain from forecasting:", json.dumps(out["forecast_gain"]))


if __name__ == "__main__":
    main()
