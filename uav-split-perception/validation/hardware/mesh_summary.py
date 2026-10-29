#!/usr/bin/env python3
"""Mesh campaign (vid_campaign_mesh/, 23 Oct 2026): v4.1 (direct three-tier) against the hierarchical chain
(camera -> Jetson -> laptop, each tier deciding), on the AegisSwarm mesh, VisDrone weights.

Per run (cached in vid_campaign_mesh/_eval_cache_mesh.json): standard sAP without and with the live forecaster v2,
sAP50, mAP of the delivered results, AoI (mean of the held result, 95th percentile, peak, P(AoI <= 300 ms)),
camera-drone power, temperature and throttled-time ratio, share of frames per server and, in the chain, per processing
place (Jetson / laptop), per-phase sAP with the forecaster; from edge_<run>.json the Jetson's decisions, power and
temperature. Per method x scenario: means (95 % CI). Paired v4.1 minus chain over scenario x repetition pairs (exact
sign-flip permutation p-values).
usage: mesh_summary.py [--workers 6]  -> vid_campaign_mesh_summary.json / .md
"""
import argparse
import collections
import glob
import json
from pathlib import Path

import numpy as np

from report_rescore import HW, perm_p, tci

D = HW / "vid_campaign_mesh"


def score(f):
    import torch
    torch.set_num_threads(1)
    from stream_ap import VID, evaluate
    labels = json.load(open(VID / "labels.json"))
    fp = json.load(open(HW / "forecast_tuning_v2.json"))["best"]["params"]
    d = json.load(open(f))
    r0 = evaluate(Path(f), labels, "newest", extras=True)
    r1 = evaluate(Path(f), labels, "newest", forecast=fp, live=True, extras=True)
    fr = [x for x in d["frames"] if x.get("server")]
    me = d["measured_energy"]
    ck = np.array(me.get("clock_log_t_mhz_flags", []), float)
    thr = float(np.mean((ck[ck[:, 2] >= 0, 2].astype(int) & 4) > 0)) if len(ck) else None
    place = collections.Counter(x.get("where") or x["server"] for x in fr if x.get("lat_ms") is not None)
    out = {"sAP": r0["sAP"], "sAP_fc": r1["sAP"], "sAP50_fc": r1["sAP50"], "mAP": r0["fresh_AP"],
           "aoi_p95_ms": r0["age_p95_ms"], "aoi_peak_ms": r0["age_max_ms"], "p_aoi300": r0["fresh_share"],
           "aoi_mean_ms": d["total"]["aoi_mean_ms"], "deadline_met_fps": d["total"]["on_time_fps"],
           "lat_median_ms": float(np.median([x["lat_ms"] for x in fr if x.get("lat_ms")])),
           "pi_w": me["mean_w"], "pi_temp_c": me["temp_mean_c"], "pi_throttled": thr,
           "servers": dict(collections.Counter(x["server"] for x in fr)), "processed_at": dict(place),
           "phase_fc": r1["per_phase_sAP"]}
    if me.get("edge_w_log"):     # Jetson board power, logged by the camera in every strategy (from 25 Oct 2026)
        out["jetson_w"] = float(np.mean([x[1] for x in me["edge_w_log"]]))
    e = Path(str(f).replace("/a2_", "/edge_"))
    if e.exists():
        ed = json.load(open(e))
        env = np.array([x for x in ed["env"] if x[1] is not None], float)
        out["edge"] = {**ed["summary"], "jetson_w": float(env[:, 1].mean()) if len(env) else None,
                       "jetson_temp_c": float(env[:, 2].mean()) if len(env) else None}
    return Path(f).stem[3:], out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    cf = D / "_eval_cache_mesh.json"
    cache = json.load(open(cf)) if cf.exists() else {}
    todo = [f for f in sorted(glob.glob(str(D / "a2_*__*__r*.json"))) if Path(f).stem[3:] not in cache]
    if todo:
        import multiprocessing as mp
        with mp.get_context("fork").Pool(a.workers) as pool:
            for stem, res in pool.imap_unordered(score, todo):
                cache[stem] = res
                json.dump(cache, open(cf, "w"))
    runs = {tuple(k.split("__")): v for k, v in cache.items()}
    keys = ["sAP", "sAP_fc", "sAP50_fc", "mAP", "aoi_mean_ms", "aoi_p95_ms", "aoi_peak_ms", "p_aoi300",
            "deadline_met_fps", "lat_median_ms", "pi_w", "pi_temp_c", "pi_throttled"]
    cells = {}
    for sc in sorted({k[0] for k in runs}) + ["ALL"]:
        for m in ("v41", "hier"):
            ms = [v for (s, p, _), v in runs.items() if p == m and (sc == "ALL" or s == sc)]
            if not ms:
                continue
            c = {k: tci([x[k] for x in ms if x.get(k) is not None]) for k in keys}
            c["n"] = len(ms)
            tot = collections.Counter()
            for x in ms:
                tot.update(x["processed_at"])
            c["processed_at"] = {k: v / sum(tot.values()) for k, v in tot.items()}
            eds = [x["edge"] for x in ms if "edge" in x]
            if eds:
                c["edge_forwarded_share"] = float(np.mean([e["laptop"] / max(e["frames"], 1) for e in eds]))
                c["jetson_w"] = float(np.mean([e["jetson_w"] for e in eds if e["jetson_w"] is not None]))
                c["jetson_temp_c"] = float(np.mean([e["jetson_temp_c"] for e in eds if e["jetson_temp_c"] is not None]))
            cells[f"{sc}|{m}"] = c
    phases = {}
    for m in ("v41", "hier"):
        ph = collections.defaultdict(list)
        for (s, p, _), v in runs.items():
            if p == m and s == "mesh_mission":
                for k, x in v["phase_fc"].items():
                    ph[k].append(x)
        phases[m] = {k: float(np.mean(x)) for k, x in ph.items()}
    paired = {}
    for sc in sorted({k[0] for k in runs}) + ["ALL"]:
        res = {}
        for metric in ("sAP_fc", "sAP", "p_aoi300", "pi_w"):
            d = [runs[(s, "v41", r)][metric] - runs[(s, "hier", r)][metric] for (s, p, r) in runs
                 if p == "hier" and (s, "v41", r) in runs and (sc == "ALL" or s == sc)]
            if d:
                mu, hw = tci(d)
                res[metric] = {"pairs": len(d), "mean_diff": mu, "ci95": hw, "v41_ahead": int(sum(x > 0 for x in d)),
                               "p_perm": perm_p(d)}
        paired[sc] = res
    out = {"cells": cells, "mission_phases_fc": phases, "paired_v41_minus_hier": paired}
    json.dump(out, open(HW / "vid_campaign_mesh_summary.json", "w"), indent=1)
    md = ["# Mesh campaign: v4.1 (direct) vs hierarchical chain, VisDrone weights, standard sAP with live forecaster v2\n",
          "| scenario | method | n | sAP | sAP + fc | mAP | P(AoI ≤ 300 ms) | 95th-pct AoI (ms) | median latency (ms) | Pi W | Pi °C | throttled | processed at |",
          "|" + "---|" * 13]
    for k, c in cells.items():
        sc, m = k.split("|")
        pa = ", ".join(f"{p} {100 * v:.0f} %" for p, v in sorted(c["processed_at"].items(), key=lambda x: -x[1]))
        md.append(f"| {sc} | {m} | {c['n']} | {c['sAP'][0]:.4f} | **{c['sAP_fc'][0]:.4f} ± {c['sAP_fc'][1]:.4f}** | "
                  f"{c['mAP'][0]:.3f} | {c['p_aoi300'][0]:.3f} | {c['aoi_p95_ms'][0]:.0f} | {c['lat_median_ms'][0]:.0f} | "
                  f"{c['pi_w'][0]:.2f} | {c['pi_temp_c'][0]:.1f} | {c['pi_throttled'][0]:.2f} | {pa} |")
    md += ["", "## Paired: v4.1 minus hierarchical chain", "| scope | metric | pairs | Δ ± 95 % CI | v4.1 ahead | p |",
           "|---|---|---|---|---|---|"]
    for sc, res in paired.items():
        for metric, r in res.items():
            md.append(f"| {sc} | {metric} | {r['pairs']} | {r['mean_diff']:+.4f} ± {r['ci95']:.4f} | "
                      f"{r['v41_ahead']}/{r['pairs']} | {r['p_perm']:.3f} |")
    if phases.get("v41"):
        names = list(phases["v41"])
        md += ["", "## mesh_mission phases (sAP + fc)", "| method | " + " | ".join(names) + " |", "|" + "---|" * (1 + len(names))]
        for m, ph in phases.items():
            md.append(f"| {m} | " + " | ".join(f"{ph.get(k, float('nan')):.3f}" for k in names) + " |")
    (HW / "vid_campaign_mesh_summary.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
