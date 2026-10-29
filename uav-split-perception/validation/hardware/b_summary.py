#!/usr/bin/env python3
"""Task B campaign (vid_campaign_b/, relay path, VisDrone weights): scoring and statistics.

Per run (cached in vid_campaign_b/_eval_cache_b.json): standard sAP without and with the live forecaster v2,
masked sAP, sAP50, mAP of the delivered results, freshness (report_rescore metrics), per-phase sAP with the
forecaster, Pi power and temperature (measured), share of frames per server.
Per policy x scenario: means. Paired comparisons over scenario x repetition pairs (exact sign-flip permutation
p-values, Holm within each reference): v4.1 against every fixed policy, and the relay against the direct laptop
path (both YOLOv8m), pooled and in the out-of-range scenario alone.
usage: b_summary.py [--workers 8]   -> vid_campaign_b_summary.json, vid_campaign_b_summary.md, and one line per run
on stdout in the format scripts/report_parts_oct22b.py reads
"""
import argparse
import collections
import glob
import json
from pathlib import Path

import numpy as np

from report_rescore import HW, holm, perm_p, tci

D = HW / "vid_campaign_b"


def score(f):
    import torch
    torch.set_num_threads(1)
    from stream_ap import VID, evaluate
    labels = json.load(open(VID / "labels.json"))
    fp = json.load(open(HW / "forecast_tuning_v2.json"))["best"]["params"]
    d = json.load(open(f))
    r0 = evaluate(Path(f), labels, "newest", extras=True)
    r1 = evaluate(Path(f), labels, "newest", forecast=fp, live=True, extras=True)
    srv = collections.Counter(x.get("server") for x in d["frames"] if x.get("server"))
    me = d["measured_energy"]
    return Path(f).stem[3:], {
        "sAP": r0["sAP"], "sAP_fc": r1["sAP"], "sAP_masked_fc": r1["sAP_masked"], "sAP50_fc": r1["sAP50"],
        "mAP": r0["fresh_AP"], "fresh_share": r0["fresh_share"], "age_p95_ms": r0["age_p95_ms"],
        "longest_stale_s": r0["longest_stale_s"], "pi_w": me["mean_w"], "temp_c": me["temp_mean_c"],
        "servers": dict(srv), "phase_fc": r1["per_phase_sAP"]}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    cf = D / "_eval_cache_b.json"
    cache = json.load(open(cf)) if cf.exists() else {}
    todo = [f for f in sorted(glob.glob(str(D / "a2_*__*__r*.json"))) if Path(f).stem[3:] not in cache]
    if todo:
        import multiprocessing as mp
        with mp.get_context("fork").Pool(a.workers) as pool:
            for stem, res in pool.imap_unordered(score, todo):
                cache[stem] = res
                json.dump(cache, open(cf, "w"))
    runs = {tuple(k.split("__")): v for k, v in cache.items()}         # (scenario, policy, rN) -> metrics
    for (sc, pol, rep), m in sorted(runs.items()):
        print(f"{sc}__{pol}__{rep} sAP {m['sAP']:.4f} fc {m['sAP_fc']:.4f} mAP {m['mAP']:.3f} fresh "
              f"{m['fresh_share']:.3f} p95 {m['age_p95_ms']:.0f} W {m['pi_w']:.2f} T {m['temp_c']:.1f} {m['servers']}")
    pols = sorted({k[1] for k in runs})
    scs = sorted({k[0] for k in runs})
    keys = ["sAP", "sAP_fc", "sAP_masked_fc", "sAP50_fc", "mAP", "fresh_share", "age_p95_ms", "longest_stale_s",
            "pi_w", "temp_c"]
    cells = {}
    for sc in scs + ["ALL"]:
        for p in pols:
            ms = [m for (s, q, _), m in runs.items() if q == p and (sc == "ALL" or s == sc)]
            if ms:
                c = {k: tci([m[k] for m in ms]) for k in keys}
                c["n"] = len(ms)
                tot = collections.Counter()
                for m in ms:
                    tot.update(m["servers"])
                c["server_share"] = {k: v / sum(tot.values()) for k, v in tot.items()}
                cells[f"{sc}|{p}"] = c
    phases = {}
    for p in pols:
        ph = collections.defaultdict(list)
        for (s, q, _), m in runs.items():
            if q == p and s == "mission":
                for k, v in m["phase_fc"].items():
                    ph[k].append(v)
        phases[p] = {k: float(np.mean(v)) for k, v in ph.items()}

    def paired(ref, others, scen=None):
        res = {}
        for p in others:
            d = [runs[(s, ref, r)]["sAP_fc"] - runs[(s, p, r)]["sAP_fc"] for (s, q, r) in runs
                 if q == p and (s, ref, r) in runs and (scen is None or s == scen)]
            if d:
                mu, hw = tci(d)
                res[p] = {"pairs": len(d), "mean_diff": mu, "ci95": hw, "wins": int(sum(x > 0 for x in d)),
                          "p_perm": perm_p(d)}
        for p, q in zip(res, holm([r["p_perm"] for r in res.values()])):
            res[p]["p_holm"] = float(q)
        return res
    fixed = [p for p in pols if p != "v41"]
    out = {"cells": cells, "mission_phases_fc": phases,
           "paired_v41": paired("v41", fixed),
           "paired_v41_by_scenario": {sc: paired("v41", fixed, sc) for sc in scs},
           "relay_vs_laptop": paired("relay_m", ["lap_m"]),
           "relay_vs_laptop_by_scenario": {sc: paired("relay_m", ["lap_m"], sc) for sc in scs}}
    json.dump(out, open(HW / "vid_campaign_b_summary.json", "w"), indent=1)
    md = ["# Task B: relay campaign (VisDrone weights), standard sAP with the live forecaster v2\n",
          "| scenario | policy | n | sAP | sAP + fc | masked + fc | sAP50 + fc | mAP | fresh | age p95 (ms) | Pi W | °C | servers |",
          "|" + "---|" * 13]
    for k, c in cells.items():
        sc, p = k.split("|")
        sh = ", ".join(f"{s} {100 * v:.0f} %" for s, v in sorted(c["server_share"].items(), key=lambda x: -x[1]))
        md.append(f"| {sc} | {p} | {c['n']} | {c['sAP'][0]:.4f} | **{c['sAP_fc'][0]:.4f} ± {c['sAP_fc'][1]:.4f}** | "
                  f"{c['sAP_masked_fc'][0]:.4f} | {c['sAP50_fc'][0]:.4f} | {c['mAP'][0]:.3f} | {c['fresh_share'][0]:.3f} | "
                  f"{c['age_p95_ms'][0]:.0f} | {c['pi_w'][0]:.2f} | {c['temp_c'][0]:.1f} | {sh} |")
    md += ["", "## Paired (reference minus policy, sAP + fc)", "| comparison | scope | pairs | Δ ± 95 % CI | wins | p | p Holm |",
           "|---|---|---|---|---|---|---|"]
    for name, scope, res in ([("v4.1", "all", out["paired_v41"]), ("relay", "all", out["relay_vs_laptop"])]
                             + [("v4.1", sc, r) for sc, r in out["paired_v41_by_scenario"].items()]
                             + [("relay", sc, r) for sc, r in out["relay_vs_laptop_by_scenario"].items()]):
        for p, r in res.items():
            md.append(f"| {name} vs {p} | {scope} | {r['pairs']} | {r['mean_diff']:+.4f} ± {r['ci95']:.4f} | "
                      f"{r['wins']}/{r['pairs']} | {r['p_perm']:.3f} | {r['p_holm']:.3f} |")
    md += ["", "## Mission phases (sAP + fc, mean over repetitions)", "| policy | " + " | ".join(next(iter(phases.values()))) + " |",
           "|" + "---|" * (1 + len(next(iter(phases.values()))))]
    for p, ph in phases.items():
        md.append(f"| {p} | " + " | ".join(f"{v:.3f}" for v in ph.values()) + " |")
    (HW / "vid_campaign_b_summary.md").write_text("\n".join(md) + "\n")


if __name__ == "__main__":
    main()
