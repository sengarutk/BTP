#!/usr/bin/env python3
"""Trade-off (Pareto) analysis, 26 Oct 2026: streaming accuracy against camera-drone power and heat, every campaign
with live Pi power (636 runs), strategies compared only within their own campaign.

Per run: sAP with the campaign's forecaster on the VisDrone detections (C7 replay, <campaign>/_eval_cache_vd.json;
the mesh campaigns' own scoring, _eval_cache_mesh.json), mean Pi board power, mean temperature, throttled-time ratio
(firmware flag, where the clock was logged). Per campaign x strategy: means over all its runs (every strategy ran the
same scenario x repetition set, so the pooled means compare like with like) and 95 % CIs. A strategy is on the
Pareto front if no other strategy of the same campaign has higher sAP AND lower power. Paired over scenario x
repetition: each strategy against the campaign's reference controller (sAP and power, exact sign-flip p).
usage: pareto_analysis.py  -> pareto_analysis.json / .md
"""
import collections
import glob
import json
from pathlib import Path

import numpy as np

from report_rescore import HW, perm_p, tci

CAMPAIGNS = {   # campaign -> (reference controller, scoring cache, cache key with the forecaster)
    "vid_campaign_energy": ("A_eco_tight", "_eval_cache_vd.json", "fc"),
    "vid_campaign_v42": ("A_eco_tight", "_eval_cache_vd.json", "fc"),
    "vid_campaign_main": ("v5", "_eval_cache_vd.json", "fc"),
    "vid_campaign_table": ("v41", "_eval_cache_vd.json", "fc"),
    "vid_campaign_long": ("v41", "_eval_cache_vd.json", "fc"),
    "vid_campaign_mesh2": ("v41", "_eval_cache_mesh.json", None),
    "vid_campaign_mesh3": ("v41", "_eval_cache_mesh.json", None),
}


def runs(camp):
    ref, cache, key = CAMPAIGNS[camp]
    c = json.load(open(HW / camp / cache))
    out = []
    for f in sorted(glob.glob(str(HW / camp / "a2_*__*__r*.json"))):
        stem = Path(f).stem[3:]
        if stem not in c:
            continue
        sc, pol, rep = stem.split("__")
        if camp == "vid_campaign_mesh2" and pol == "hier":   # multihop only: no pooled comparison possible
            continue
        sap = c[stem][key]["sAP"] if key else c[stem]["sAP_fc"]
        me = json.load(open(f))["measured_energy"]
        ck = np.array(me.get("clock_log_t_mhz_flags") or [], float)
        thr = float(np.mean((ck[ck[:, 2] >= 0, 2].astype(int) & 4) > 0)) if len(ck) else None
        out.append({"scenario": sc, "policy": pol, "rep": rep, "sAP_fc": sap, "pi_w": me["mean_w"],
                    "temp_c": me.get("temp_mean_c"), "throttled": thr})
    return out


def front(cells):
    """names of the non-dominated strategies (max sAP, min power)"""
    return sorted(p for p, a in cells.items()
                  if not any(b["sAP_fc"][0] >= a["sAP_fc"][0] and b["pi_w"][0] <= a["pi_w"][0]
                             and (b["sAP_fc"][0] > a["sAP_fc"][0] or b["pi_w"][0] < a["pi_w"][0])
                             for q, b in cells.items() if q != p))


def main():
    res = {}
    md = ["# Pareto analysis: streaming accuracy (VisDrone, with forecaster) against camera-drone power\n"]
    for camp, (ref, _, _) in CAMPAIGNS.items():
        rs = runs(camp)
        by = collections.defaultdict(list)
        for r in rs:
            by[r["policy"]].append(r)
        cells = {}
        for p, v in by.items():
            cells[p] = {"n": len(v), "sAP_fc": tci([x["sAP_fc"] for x in v]), "pi_w": tci([x["pi_w"] for x in v]),
                        "temp_c": tci([x["temp_c"] for x in v if x["temp_c"] is not None]),
                        "throttled": tci([x["throttled"] for x in v if x["throttled"] is not None])}
        idx = {(r["scenario"], r["policy"], r["rep"]): r for r in rs}
        paired = {}
        for p in cells:
            if p == ref:
                continue
            ks = [(s, q) for (s, pp, q) in idx if pp == p and (s, ref, q) in idx]
            d_s = [idx[(s, ref, q)]["sAP_fc"] - idx[(s, p, q)]["sAP_fc"] for s, q in ks]
            d_w = [idx[(s, ref, q)]["pi_w"] - idx[(s, p, q)]["pi_w"] for s, q in ks]
            if d_s:
                paired[p] = {"pairs": len(d_s), "dsAP_ref_minus": tci(d_s), "ref_ahead": int(sum(x > 0 for x in d_s)),
                             "p_sAP": perm_p(d_s), "dW_ref_minus": tci(d_w), "p_W": perm_p(d_w)}
        fr = front(cells)
        res[camp] = {"reference": ref, "runs": len(rs), "cells": cells, "front": fr, "paired_vs_reference": paired}
        md += [f"\n## {camp} ({len(rs)} runs; reference {ref}; Pareto front: {', '.join(fr)})",
               "| strategy | runs | sAP + fc | Pi W | Pi °C | throttled | on front | ref − strategy: ΔsAP (p) | ΔW (p) |",
               "|---|---|---|---|---|---|---|---|---|"]
        for p, c in sorted(cells.items(), key=lambda kv: -kv[1]["sAP_fc"][0]):
            pr = paired.get(p)
            th = c["throttled"][0]
            md.append(f"| {p} | {c['n']} | {c['sAP_fc'][0]:.4f} ± {c['sAP_fc'][1]:.4f} | {c['pi_w'][0]:.2f} | "
                      f"{c['temp_c'][0]:.1f} | {'' if th != th else f'{th:.2f}'} | {'yes' if p in fr else ''} | "
                      + (f"{pr['dsAP_ref_minus'][0]:+.4f} ({pr['p_sAP']:.3f}) | {pr['dW_ref_minus'][0]:+.2f} ({pr['p_W']:.3f}) |"
                         if pr else "reference | |"))
    json.dump(res, open(HW / "pareto_analysis.json", "w"), indent=1)
    (HW / "pareto_analysis.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
