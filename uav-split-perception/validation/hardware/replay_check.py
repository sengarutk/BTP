#!/usr/bin/env python3
"""Does the replay (replay.py) reproduce the hardware? Compares, per policy, the replay of the main campaign's
scenarios with the 240 live runs of vid_campaign_main: streaming AP (forecaster v2), Pi power, fresh-detection
share, time at or above 80 C. Reports the per-policy values side by side, the Pearson and Spearman correlation of
the policy means, and whether the replay picks the same best policy and the same paired verdicts against v5.
usage: replay_check.py [REPLAY_DIR]   -> experiments/results/hardware/replay/replay_check.json
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HW = Path(__file__).resolve().parent.parent.parent / "experiments" / "results" / "hardware"


def ranks(x):
    o = np.argsort(x)
    r = np.empty(len(x))
    r[o] = np.arange(len(x))
    return r


def main(rdir):
    rep = json.load(open(Path(rdir) / "replay_summary_20s.json"))
    hw = json.load(open(HW / "vid_campaign_main_measured_summary.json"))
    by_r = defaultdict(list)
    for r in rep:
        by_r[r["policy"]].append(r)
    by_h = defaultdict(list)
    for r in hw["runs"]:
        by_h[r["policy"]].append(r)
    pols = sorted(set(by_r) & set(by_h))
    rows, keys = {}, (("sAP", "sAP"), ("pi_w", "camera_w"), ("availability", "availability"),
                      ("hot_share", "hot_share"))
    for p in pols:
        rows[p] = {k: (float(np.mean([x[k] for x in by_r[p]])),
                       float(np.mean([x[h] for x in by_h[p] if x.get(h) is not None]))) for k, h in keys}
    out = {"policies": rows, "agreement": {}}
    for k, _ in keys:
        a = np.array([rows[p][k][0] for p in pols])
        b = np.array([rows[p][k][1] for p in pols])
        out["agreement"][k] = {"pearson": float(np.corrcoef(a, b)[0, 1]),
                               "spearman": float(np.corrcoef(ranks(a), ranks(b))[0, 1]),
                               "mean_abs_diff": float(np.mean(np.abs(a - b)))}
    out["best_replay"] = max(pols, key=lambda p: rows[p]["sAP"][0])
    out["best_hardware"] = max(pols, key=lambda p: rows[p]["sAP"][1])
    # paired verdicts against v5 (replay: same scenario and seed; hardware: same scenario and repetition)
    ref_r = {(x["scenario"], x["seed"]): x["sAP"] for x in by_r.get("v5", [])}
    ref_h = {(x["scenario"], x["rep"]): x["sAP"] for x in by_h.get("v5", [])}
    verdict = {}
    for p in pols:
        if p == "v5":
            continue
        dr = [x["sAP"] - ref_r[(x["scenario"], x["seed"])] for x in by_r[p] if (x["scenario"], x["seed"]) in ref_r]
        dh = [x["sAP"] - ref_h[(x["scenario"], x["rep"])] for x in by_h[p]
              if (x["scenario"], x["rep"]) in ref_h and x.get("sAP") is not None]
        def sig(d):
            m, h = float(np.mean(d)), 2.093 * float(np.std(d, ddof=1)) / np.sqrt(len(d))
            return "worse" if m + h < 0 else "better" if m - h > 0 else "tie"
        verdict[p] = {"replay": sig(dr), "hardware": sig(dh), "replay_diff": float(np.mean(dr)),
                      "hardware_diff": float(np.mean(dh))}
    out["paired_vs_v5"] = verdict
    out["verdicts_agree"] = sum(v["replay"] == v["hardware"] for v in verdict.values())
    json.dump(out, open(Path(rdir) / "replay_check.json", "w"), indent=1)
    print(f"{'policy':22s} {'sAP replay/hw':>18s} {'Pi W replay/hw':>16s} {'fresh replay/hw':>16s} {'hot replay/hw':>14s}")
    for p in pols:
        r = rows[p]
        print(f"{p:22s} {r['sAP'][0]:.4f}/{r['sAP'][1]:.4f}   {r['pi_w'][0]:.2f}/{r['pi_w'][1]:.2f}      "
              f"{r['availability'][0]:.2f}/{r['availability'][1]:.2f}      {r['hot_share'][0]:.2f}/{r['hot_share'][1]:.2f}")
    print("agreement", json.dumps({k: {a: round(b, 3) for a, b in v.items()} for k, v in out["agreement"].items()}))
    print("best:", out["best_replay"], "(replay)", out["best_hardware"], "(hardware)")
    print(f"paired verdicts vs v5 agree in {out['verdicts_agree']} of {len(verdict)}:",
          {p: (v["replay"], v["hardware"]) for p, v in verdict.items()})


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else HW / "replay" / "validate_main")
