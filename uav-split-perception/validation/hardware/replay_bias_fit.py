#!/usr/bin/env python3
"""Fit and test the replay's bias corrections (paper 2, roadmap L7, 12 Nov 2026; predictions in
docs/replay_bias_predictions_nov12.md).

Replays the main campaign's scenarios (as validate_main_oct30_power_t85: --netem legacy --onboard-power power, seeds
1-5, 20-s phases) for one half of the policies, with the switches --contention-ms D and --shared-radio, and compares
the result with the 240 live runs (the comparison of replay_check.py). Four processes, one per scenario.
  fit       the fit half, every setting of the grid; chooses the setting with the smallest mean |replay - hw| sAP
  test      the held-out half with the chosen setting (and with no correction, from the stored validation)
usage: replay_bias_fit.py fit | test   -> experiments/results/hardware/replay/bias_fit_nov12/
"""
import argparse
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
HW = HERE.parent.parent / "experiments" / "results" / "hardware"
OUT = HW / "replay" / "bias_fit_nov12"
STORED = HW / "replay" / "validate_main_oct30_power_t85" / "replay_summary_20s.json"
FIT = ["v5", "v42", "v5_exp", "conf_trigger", "jsq", "aoi_thr"]
HELD = ["v5", "v5_lin", "v5_flat", "v5_nofc", "leaf", "reward_offload", "fixed_laptop_m640q90"]
GRID = [(d, sr) for sr in (False, True) for d in (0.0, 10.0, 20.0, 40.0)]
GROUPS = (["mission"], ["mission_mirror"], ["random"], ["static_good"])


def tag(d, sr):
    return f"c{d:g}_{'sr' if sr else 'ind'}"


def run(policies, d, sr, out):
    out.mkdir(parents=True, exist_ok=True)
    if (out / "replay_summary_20s.json").exists():
        return json.load(open(out / "replay_summary_20s.json"))
    procs = []
    for k, scs in enumerate(GROUPS):
        g = out / f"g{k}"
        cmd = [sys.executable, str(HERE / "replay.py"), "--policy", *policies, "--scenario", *scs, "--seeds", "1-5",
               "--netem", "legacy", "--onboard-power", "power", "--contention-ms", str(d), "--out", str(g)]
        if sr:
            cmd.append("--shared-radio")
        procs.append(subprocess.Popen(cmd, cwd=HERE, stdout=open(out / f"g{k}.log", "w"), stderr=subprocess.STDOUT))
    for p in procs:
        if p.wait() != 0:
            raise SystemExit(f"replay failed in {out}")
    rows = [r for k in range(len(GROUPS)) for r in json.load(open(out / f"g{k}" / "replay_summary_20s.json"))]
    json.dump(rows, open(out / "replay_summary_20s.json", "w"), indent=1)
    return rows


def compare(rows, policies):
    hw = json.load(open(HW / "vid_campaign_main_measured_summary.json"))["runs"]
    by_h, by_r = defaultdict(list), defaultdict(list)
    for r in hw:
        by_h[r["policy"]].append(r)
    for r in rows:
        by_r[r["policy"]].append(r)
    per = {}
    for p in policies:
        rs, hs = np.mean([x["sAP"] for x in by_r[p]]), np.mean([x["sAP"] for x in by_h[p] if x.get("sAP") is not None])
        per[p] = {"replay": float(rs), "hardware": float(hs), "diff": float(rs - hs),
                  "pi_w_replay": float(np.mean([x["pi_w"] for x in by_r[p]])),
                  "pi_w_hardware": float(np.mean([x["camera_w"] for x in by_h[p] if x.get("camera_w") is not None]))}
    ref_r = {(x["scenario"], x["seed"]): x["sAP"] for x in by_r["v5"]}
    ref_h = {(x["scenario"], x["rep"]): x["sAP"] for x in by_h["v5"]}
    for p in policies:
        if p != "v5":
            per[p]["vs_v5_replay"] = float(np.mean([x["sAP"] - ref_r[(x["scenario"], x["seed"])] for x in by_r[p]]))
            per[p]["vs_v5_hardware"] = float(np.mean([x["sAP"] - ref_h[(x["scenario"], x["rep"])] for x in by_h[p]
                                                      if x.get("sAP") is not None and (x["scenario"], x["rep"]) in ref_h]))
    a = np.array([per[p]["replay"] for p in policies])
    b = np.array([per[p]["hardware"] for p in policies])
    return {"per_policy": per, "mean_abs_diff": float(np.mean(np.abs(a - b))), "pearson": float(np.corrcoef(a, b)[0, 1])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["fit", "test"])
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    res_f = OUT / "fit.json"
    if a.cmd == "fit":
        res = json.load(open(res_f)) if res_f.exists() else {}
        for d, sr in GRID:
            t = tag(d, sr)
            if t in res:
                continue
            res[t] = compare(run(FIT, d, sr, OUT / "fit" / t), FIT)
            json.dump(res, open(res_f, "w"), indent=1)
            print(f"{t}: mean |diff| {res[t]['mean_abs_diff']:.4f}  r {res[t]['pearson']:.3f}", flush=True)
        best = min(res, key=lambda k: res[k]["mean_abs_diff"])
        print("chosen:", best)
        json.dump(res, open(res_f, "w"), indent=1)
    else:
        res = json.load(open(res_f))
        best = min(res, key=lambda k: res[k]["mean_abs_diff"])
        d, sr = next((d, sr) for d, sr in GRID if tag(d, sr) == best)
        stored = [r for r in json.load(open(STORED)) if r["policy"] in HELD]
        out = {"chosen": best, "uncorrected": compare(stored, HELD),
               "corrected": compare(run(HELD, d, sr, OUT / "test" / best), HELD)}
        json.dump(out, open(OUT / "test.json", "w"), indent=1)
        for k in ("uncorrected", "corrected"):
            c = out[k]
            print(f"{k}: mean |diff| {c['mean_abs_diff']:.4f}  r {c['pearson']:.3f}  leaf - v5 replay "
                  f"{c['per_policy']['leaf']['vs_v5_replay']:+.4f} (hardware {c['per_policy']['leaf']['vs_v5_hardware']:+.4f})")


if __name__ == "__main__":
    main()
