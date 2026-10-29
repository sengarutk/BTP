#!/usr/bin/env python3
"""Second mesh campaign (24 Oct 2026, plan agreed with the user): every strategy on the AegisSwarm mesh with VisDrone
weights and the motion forecaster. Short: v41 v41e heat heate noprice fixlap aoithr x static_good mesh_mission multihop
x 3 reps, plus hier x multihop x 3 (vid_campaign_mesh2/). Long (--long): 24-min mesh_mission, v41 heat x 5, v41e
heate x 3 (vid_campaign_mesh2_long/).

Per run: the same scores as mesh_summary.py (cached in <campaign>/_eval_cache_mesh.json), plus the Jetson's power
and temperature from the worker's power reports when present. Per strategy x scenario: means (95 % CI). Paired
differences over scenario x repetition pairs (exact sign-flip permutation p-values): every strategy minus v41, and the
effect of each price (v41e - v41 and heate - heat for the Jetson energy price, heat - v41 for heat vs Pi energy).
Strategies are compared only within this campaign.
usage: mesh2_summary.py [--long] [--workers 6]  -> vid_campaign_mesh2[_long]_summary.json / .md
"""
import argparse
import collections
import glob
import json

import numpy as np

from mesh_summary import score
from report_rescore import HW, perm_p, tci

ORDER = ["v41", "v41e", "v41e12", "heat", "heate", "noprice", "fixlap", "aoithr", "hier"]
PAIRS = [(m, "v41") for m in ORDER[1:]] + [("heate", "heat")]
CAMPAIGNS = {"short": "vid_campaign_mesh2", "long": "vid_campaign_mesh2_long", "mesh3": "vid_campaign_mesh3"}
KEYS = ["sAP", "sAP_fc", "sAP50_fc", "mAP", "aoi_mean_ms", "aoi_p95_ms", "aoi_peak_ms", "p_aoi300",
        "deadline_met_fps", "lat_median_ms", "pi_w", "pi_temp_c", "pi_throttled", "jetson_w"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--long", action="store_true")
    ap.add_argument("--campaign", choices=list(CAMPAIGNS), help="short (default), long or mesh3; overrides --long")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    name = CAMPAIGNS[a.campaign] if a.campaign else ("vid_campaign_mesh2_long" if a.long else "vid_campaign_mesh2")
    D = HW / name
    cf = D / "_eval_cache_mesh.json"
    cache = json.load(open(cf)) if cf.exists() else {}
    todo = [f for f in sorted(glob.glob(str(D / "a2_*__*__r*.json"))) if f.rsplit("/a2_", 1)[1][:-5] not in cache]
    if todo:
        import multiprocessing as mp
        with mp.get_context("fork").Pool(a.workers) as pool:
            for stem, res in pool.imap_unordered(score, todo):
                cache[stem] = res
                json.dump(cache, open(cf, "w"))
    runs = {tuple(k.split("__")): v for k, v in cache.items()}
    scen = sorted({k[0] for k in runs})
    cells = {}
    for sc in scen + ["ALL"]:
        for m in ORDER:
            ms = [v for (s, p, _), v in runs.items() if p == m and (sc == "ALL" or s == sc)]
            if not ms or (sc == "ALL" and m == "hier"):     # hier ran in multihop only: no ALL row
                continue
            c = {k: tci([x[k] for x in ms if x.get(k) is not None]) for k in KEYS}
            c["n"] = len(ms)
            tot = collections.Counter()
            for x in ms:
                tot.update(x["processed_at"])
            c["processed_at"] = {k: v / sum(tot.values()) for k, v in tot.items()}
            eds = [x["edge"] for x in ms if "edge" in x]
            if eds:
                c["edge_forwarded_share"] = float(np.mean([e["laptop"] / max(e["frames"], 1) for e in eds]))
            cells[f"{sc}|{m}"] = c
    phases = {}
    for m in ORDER:
        ph = collections.defaultdict(list)
        for (s, p, _), v in runs.items():
            if p == m and s == "mesh_mission":
                for k, x in v["phase_fc"].items():
                    ph[k].append(x)
        if ph:
            phases[m] = {k: float(np.mean(x)) for k, x in ph.items()}
    paired = {}
    for x, y in PAIRS:
        for sc in scen + ["ALL"]:
            res = {}
            for metric in ("sAP_fc", "sAP", "p_aoi300", "deadline_met_fps", "pi_w", "pi_temp_c", "jetson_w"):
                d = [runs[(s, x, r)][metric] - runs[(s, y, r)][metric] for (s, p, r) in runs
                     if p == x and (s, y, r) in runs and (sc == "ALL" or s == sc)
                     and runs[(s, x, r)].get(metric) is not None and runs[(s, y, r)].get(metric) is not None]
                if d:
                    mu, hw = tci(d)
                    res[metric] = {"pairs": len(d), "mean_diff": mu, "ci95": hw, "first_ahead": int(sum(v > 0 for v in d)),
                                   "p_perm": perm_p(d)}
            if res:
                paired[f"{x}-{y}|{sc}"] = res
    out = {"campaign": name, "cells": cells, "mission_phases_fc": phases, "paired": paired}
    json.dump(out, open(HW / f"{name}_summary.json", "w"), indent=1)
    md = [f"# {name}: strategies on the AegisSwarm mesh, VisDrone weights, standard sAP with live forecaster v2\n",
          "| scenario | strategy | n | sAP | sAP + fc | mAP | P(AoI ≤ 300 ms) | 95th-pct AoI (ms) | deadline-met /s | "
          "median latency (ms) | Pi W | Pi °C | throttled | Jetson W | processed at |", "|" + "---|" * 15]
    for k, c in cells.items():
        sc, m = k.split("|")
        pa = ", ".join(f"{p} {100 * v:.0f} %" for p, v in sorted(c["processed_at"].items(), key=lambda x: -x[1]))
        th = c["pi_throttled"][0]
        jw = "" if c["jetson_w"][0] != c["jetson_w"][0] else f"{c['jetson_w'][0]:.2f}"
        md.append(f"| {sc} | {m} | {c['n']} | {c['sAP'][0]:.4f} | **{c['sAP_fc'][0]:.4f} ± {c['sAP_fc'][1]:.4f}** | "
                  f"{c['mAP'][0]:.3f} | {c['p_aoi300'][0]:.3f} | {c['aoi_p95_ms'][0]:.0f} | {c['deadline_met_fps'][0]:.1f} | "
                  f"{c['lat_median_ms'][0]:.0f} | {c['pi_w'][0]:.2f} | {c['pi_temp_c'][0]:.1f} | "
                  f"{'' if th is None or th != th else f'{th:.2f}'} | {jw} | {pa} |")
    md += ["", "## Paired differences (same scenario and repetition)",
           "| comparison | scope | metric | pairs | Δ ± 95 % CI | first ahead | p |", "|---|---|---|---|---|---|---|"]
    for k, res in paired.items():
        cmp_, sc = k.split("|")
        for metric, r in res.items():
            md.append(f"| {cmp_} | {sc} | {metric} | {r['pairs']} | {r['mean_diff']:+.4f} ± {r['ci95']:.4f} | "
                      f"{r['first_ahead']}/{r['pairs']} | {r['p_perm']:.3f} |")
    if phases:
        names = list(next(iter(phases.values())))
        md += ["", "## mesh_mission phases (sAP + fc)", "| strategy | " + " | ".join(names) + " |", "|" + "---|" * (1 + len(names))]
        for m, ph in phases.items():
            md.append(f"| {m} | " + " | ".join(f"{ph.get(k, float('nan')):.3f}" for k in names) + " |")
    (HW / f"{name}_summary.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
