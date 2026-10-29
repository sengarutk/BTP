#!/usr/bin/env python3
"""Report fixes (task C): every VisDrone-VID campaign rescored and summarised with the standard metrics.

For every run of the campaigns below (existing data, no new runs) and both without and with the campaign's forecaster:
  C1  sAP with the STANDARD 'newest' holding rule (Li et al.) next to the 'quality' rule the Phase G tables reported
  C2  the official VisDrone protocol: ignored regions masked (stream_ap.drop_ignored, > 50 % inside -> dropped)
  C3  sAP50, sAP by object size (COCO area ranges in the 640-px frame; 'large' has only 7 objects in the 7 test clips
      and is not reported), worst-case freshness: 95th-percentile and maximum age of the held result, longest stretch
      older than 300 ms, fresh share
  C4  per scenario, and inside the mission scenarios per phase (normal phases separate from the blackouts)
  C6  paired comparisons with the campaign's reference controller: mean difference, 95 % t-interval, wins, exact
      two-sided sign-flip permutation p-value and Holm-adjusted p-value (family = all unique comparisons of one
      campaign and metric, over all its reference controllers; a mirrored pair is one comparison)
Per-run scores are cached in <campaign>/_eval_cache_c.json (resumable).
--visdrone: the same runs replayed with the VisDrone-trained detectors (each recorded result keeps its frame, variant
and arrival time; its detections are those of the same variant from weights/<model>_visdrone.pt, vd_variant_dets.py).
The architectures are the same, so the timing holds; the controllers' choices were made with the COCO accuracy table,
so this is "the same schedules with VisDrone detectors". Cached in <campaign>/_eval_cache_vd.json.
usage: report_rescore.py [--workers 8] [--only vid_campaign_main,...] [--visdrone]
Output: experiments/results/hardware/report_c_summary.json and report_c_tables.md
"""
import argparse
import glob
import itertools
import json
import os
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
HW = HERE.parent.parent / "experiments" / "results" / "hardware"
# campaign -> (forecaster used by its headline numbers: 'v2' offline or 'v2live', reference controllers, report section)
CAMPAIGNS = {
    "vid_campaign_wifi": ("v2", ["A_full"], "Part 12 (108 runs, shared Wi-Fi)"),
    "vid_campaign_wifi_fc": ("v2", ["A_full"], "Part 14 (forecaster v1 campaign)"),
    "vid_campaign_wifi_fc2": ("v2live", ["A_full", "A_stream_fc2"], "Part 14 (80-run campaign, live forecaster v2)"),
    "vid_campaign_energy": ("v2live", ["A_stream_fc2"], "G9 (energy campaign)"),
    "vid_campaign_v42": ("v2live", ["A_eco_tight"], "G11 (live power on both boards)"),
    "vid_campaign_main": ("v2live", ["v5"], "G12 (main campaign, 240 runs)"),
    "vid_campaign_table": ("v2live", ["v41", "v5"], "G13 (same-day table)"),
    "vid_campaign_long": ("v2live", ["v41", "v5"], "G13 (24-minute missions)"),
}
EXTRA_KEYS = ["sAP", "sAP50", "fresh_AP", "sAP_masked", "sAP50_masked", "fresh_AP_masked", "age_p95_ms", "age_max_ms",
              "longest_stale_s", "fresh_share"]


_SUBST = {}


def score(args):
    f, fc, vd = args
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    import torch
    torch.set_num_threads(1)
    from stream_ap import VID, evaluate
    labels = json.load(open(VID / "labels.json"))
    fp = json.load(open(HW / "forecast_tuning_v2.json"))["best"]["params"]
    out = {}
    if vd and not _SUBST:
        z = HW / "vd_variant_dets"
        _SUBST.update({p.stem: np.load(p) for p in z.glob("*.npz")})
    for tag, kw in (("nofc", {}), ("fc", {"forecast": fp, "live": fc == "v2live"})):
        r = evaluate(Path(f), labels, "newest", extras=True, subst=_SUBST if vd else None, **kw)
        out[tag] = {k: r[k] for k in EXTRA_KEYS}
        out[tag].update({f"sAP_{k}_masked": v for k, v in r["sAP_size_masked"].items() if k != "large"})
        out[tag]["per_phase_sAP"] = r["per_phase_sAP"]
    return Path(f).stem[3:], out


T975 = {1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57, 6: 2.45, 7: 2.36, 8: 2.31, 9: 2.26, 10: 2.23, 11: 2.20, 12: 2.18,
        13: 2.16, 14: 2.14, 15: 2.13, 16: 2.12, 17: 2.11, 18: 2.10, 19: 2.09, 20: 2.086, 21: 2.080, 22: 2.074, 23: 2.069,
        24: 2.064, 25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042}


def t975(df):
    """Two-sided 95 % Student-t quantile; beyond 30 df the Cornish-Fisher expansion (error < 0.1 %)."""
    if df in T975:
        return T975[df]
    z = 1.959964
    return z + (z ** 3 + z) / (4 * df) + (5 * z ** 5 + 16 * z ** 3 + 3 * z) / (96 * df ** 2)


def tci(x):
    x = np.asarray(x, float)
    if len(x) < 2:
        return float(x.mean()) if len(x) else float("nan"), float("nan")
    return float(x.mean()), float(t975(len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x)))     # was 1.96 beyond 19 df


def perm_p(d):
    """Exact two-sided sign-flip permutation p-value of the mean paired difference (all 2^n sign patterns)."""
    d = np.asarray(d, float)
    n = len(d)
    if n == 0:
        return float("nan")
    if n > 20:                       # Monte Carlo above 2^20 patterns
        s = np.random.default_rng(0).choice([-1.0, 1.0], size=(200000, n))
    else:
        s = np.array(list(itertools.product([-1.0, 1.0], repeat=n)))
    null = np.abs(s @ d)
    return float(np.mean(null >= abs(d.sum()) - 1e-12))


def holm(ps):
    """Holm step-down adjusted p-values (same order as the input)."""
    ps = np.asarray(ps, float)
    order = np.argsort(ps)
    adj, run = np.empty_like(ps), 0.0
    for i, k in enumerate(order):
        run = max(run, min(1.0, (len(ps) - i) * ps[k]))
        adj[k] = run
    return adj


def camps_list(a):
    return [k for k in CAMPAIGNS if not a.only or k in a.only.split(",")]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--only", default="")
    ap.add_argument("--visdrone", action="store_true")
    a = ap.parse_args()
    cname = "_eval_cache_vd.json" if a.visdrone else "_eval_cache_c.json"
    if a.visdrone:     # every variant the campaigns used must have VisDrone detections
        need = set()
        for camp in camps_list(a):
            for f in glob.glob(str(HW / camp / "a2_*__*__r*.json")):
                need |= {x["variant"] for x in json.load(open(f))["frames"] if x.get("server")}
        have = {p.stem for p in (HW / "vd_variant_dets").glob("*.npz")}
        if need - have:
            raise SystemExit(f"missing VisDrone detections for variants {sorted(need - have)} (vd_variant_dets.py)")
    camps = {k: v for k, v in CAMPAIGNS.items() if not a.only or k in a.only.split(",")}
    import multiprocessing as mp
    for camp, (fc, _, _) in camps.items():
        cf = HW / camp / cname
        cache = json.load(open(cf)) if cf.exists() else {}
        todo = [(f, fc, a.visdrone) for f in sorted(glob.glob(str(HW / camp / "a2_*__*__r*.json")))
                if not f.endswith("_dets.json") and Path(f).stem[3:] not in cache]
        if todo:
            print(f"{camp}: scoring {len(todo)} runs", flush=True)
            with mp.get_context("fork").Pool(a.workers) as pool:
                for i, (stem, res) in enumerate(pool.imap_unordered(score, todo, chunksize=1)):
                    cache[stem] = res
                    if i % 10 == 9 or i == len(todo) - 1:
                        tmp = cf.with_suffix(".tmp")
                        json.dump(cache, open(tmp, "w"))
                        tmp.replace(cf)
                        print(f"  {camp} {i + 1}/{len(todo)}", flush=True)
    summary, md = {}, []
    for camp, (fc, refs, sect) in camps.items():
        cache = json.load(open(HW / camp / cname))
        old = json.load(open(HW / camp / "_eval_cache.json"))
        fk = "_fc" + fc
        runs = defaultdict(dict)                           # (scenario, rep) -> policy -> metrics
        for stem, res in cache.items():
            sc, pol, rep = stem.split("__")
            # the 'quality' rule was scored only with the COCO detections (the campaigns' own caches); with --visdrone
            # it is left out instead of copying the COCO values (they were copied until 28 Oct 2026)
            m = ({"sAP_quality": None, "sAP_quality_fc": None} if a.visdrone else
                 {"sAP_quality": old[stem]["sAP_quality"], "sAP_quality_fc": old[stem].get("sAP_quality" + fk)})
            for tag, sfx in (("nofc", ""), ("fc", "_fc")):
                m.update({k + sfx: v for k, v in res[tag].items() if k != "per_phase_sAP"})
                m["phase" + sfx] = res[tag]["per_phase_sAP"]
            # the cached standard-rule values from the original summaries must equal the new ones (COCO pass)
            assert a.visdrone or abs(m["sAP"] - old[stem]["sAP_newest"]) < 1e-9, stem
            runs[(sc, int(rep[1:]))][pol] = m
        pols = sorted({p for d in runs.values() for p in d})
        scen = sorted({s for s, _ in runs})
        metrics = ["sAP_quality_fc", "sAP_fc", "sAP_masked_fc", "sAP50_masked_fc", "sAP_small_masked_fc",
                   "sAP_medium_masked_fc", "sAP_quality", "sAP", "sAP_masked", "fresh_AP_masked", "age_p95_ms",
                   "age_max_ms", "longest_stale_s", "fresh_share"]
        cs = {"section": sect, "forecaster": fc, "scenarios": {}, "paired": {}, "phases": {}}
        for sc in scen + ["ALL"]:
            cs["scenarios"][sc] = {}
            for p in pols:
                vals = [d[p] for (s, _), d in runs.items() if p in d and (sc == "ALL" or s == sc)]
                if vals:
                    cs["scenarios"][sc][p] = {"n": len(vals), **{m: tci([v[m] for v in vals if v.get(m) is not None])
                                                                 for m in metrics}}
        # C4: per phase inside each scenario (standard rule, with forecaster)
        for sc in scen:
            ph = defaultdict(lambda: defaultdict(list))
            for (s, _), d in runs.items():
                if s == sc:
                    for p, m in d.items():
                        for k, v in m["phase_fc"].items():
                            ph[p][k].append(v)
            cs["phases"][sc] = {p: {k: float(np.mean(v)) for k, v in d.items()} for p, d in ph.items()}
        # C6: paired comparisons, Holm within (campaign, metric) over the UNIQUE comparisons of all references: a pair
        # reached from both references (A vs B and B vs A) is one test, corrected once, and is marked mirror_of.
        # Until 28 Oct 2026 each reference was its own family, so a mirrored pair was counted twice and the two
        # families of one campaign were not corrected jointly.
        for ref in refs:
            cs["paired"][ref] = {}
            for metric in ("sAP_fc", "sAP_masked_fc", "sAP", "sAP_quality_fc"):
                res = {}
                for p in pols:
                    if p == ref:
                        continue
                    d = [v[ref][metric] - v[p][metric] for v in runs.values()
                         if ref in v and p in v and v[ref].get(metric) is not None and v[p].get(metric) is not None]
                    if d:
                        mu, hw = tci(d)
                        res[p] = {"pairs": len(d), "mean_diff": mu, "ci95": hw, "wins": int(sum(x > 0 for x in d)),
                                  "p_perm": perm_p(d)}
                cs["paired"][ref][metric] = res
        for metric in ("sAP_fc", "sAP_masked_fc", "sAP", "sAP_quality_fc"):
            fam = {}                                       # frozenset({ref, policy}) -> first (ref, policy) seen
            for ref in refs:
                for p in cs["paired"][ref][metric]:
                    key = frozenset((ref, p))
                    if key in fam:
                        cs["paired"][ref][metric][p]["mirror_of"] = list(fam[key])
                    else:
                        fam[key] = (ref, p)
            if fam:
                adj = holm([cs["paired"][r][metric][p]["p_perm"] for r, p in fam.values()])
                for (r, p), q in zip(fam.values(), adj):
                    cs["paired"][r][metric][p]["p_holm"] = float(q)
                    if p in cs["paired"] and r in cs["paired"][p][metric]:
                        cs["paired"][p][metric][r]["p_holm"] = float(q)
        summary[camp] = cs
        # markdown tables
        md.append(f"## {camp} - {sect}\nforecaster: {fc}; reference(s): {', '.join(refs)}; "
                  f"{sum(len(d) for d in runs.values())} runs\n")
        md.append("### All scenarios pooled (mean over runs)\n")
        md.append("| policy | n | sAP quality+fc (reported) | **sAP standard+fc** | sAP std+fc, masked | sAP50 masked+fc "
                  "| small | medium | sAP std (no fc) | fresh AP masked | age p95 (ms) | age max (ms) | longest stale (s) "
                  "| fresh share |")
        md.append("|" + "---|" * 14)
        for p, r in sorted(cs["scenarios"]["ALL"].items(), key=lambda x: -x[1]["sAP_fc"][0]):
            g = lambda m, f=".4f": format(r[m][0], f)  # noqa: E731
            md.append(f"| {p} | {r['n']} | {g('sAP_quality_fc')} | **{g('sAP_fc')}** | {g('sAP_masked_fc')} | "
                      f"{g('sAP50_masked_fc')} | {g('sAP_small_masked_fc')} | {g('sAP_medium_masked_fc')} | {g('sAP')} | "
                      f"{g('fresh_AP_masked')} | {g('age_p95_ms', '.0f')} | {g('age_max_ms', '.0f')} | "
                      f"{g('longest_stale_s', '.1f')} | {g('fresh_share', '.3f')} |")
        md.append("\n### Per scenario: standard sAP with forecaster (masked), mean ± 95 % CI\n")
        md.append("| policy | " + " | ".join(scen) + " |")
        md.append("|" + "---|" * (len(scen) + 1))
        for p in pols:
            cells = []
            for sc in scen:
                r = cs["scenarios"][sc].get(p)
                cells.append(f"{r['sAP_masked_fc'][0]:.4f} ± {r['sAP_masked_fc'][1]:.4f}" if r else "-")
            md.append(f"| {p} | " + " | ".join(cells) + " |")
        for sc in ("mission", "mission_mirror"):
            if sc in cs["phases"]:
                phs = list(next(iter(cs["phases"][sc].values())))
                md.append(f"\n### {sc}: standard sAP with forecaster per phase\n")
                md.append("| policy | " + " | ".join(phs) + " |")
                md.append("|" + "---|" * (len(phs) + 1))
                for p, d in sorted(cs["phases"][sc].items()):
                    md.append(f"| {p} | " + " | ".join(f"{d.get(k, float('nan')):.4f}" for k in phs) + " |")
        for ref in refs:
            md.append(f"\n### Paired: {ref} minus policy (all scenarios x repetitions)\n")
            md.append("| policy | metric | pairs | mean diff ± 95 % CI | wins | p (exact perm.) | p (Holm) |")
            md.append("|---|---|---|---|---|---|---|")
            for metric in ("sAP_fc", "sAP_masked_fc", "sAP", "sAP_quality_fc"):
                for p, r in sorted(cs["paired"][ref][metric].items(), key=lambda x: -x[1]["mean_diff"]):
                    md.append(f"| {p} | {metric} | {r['pairs']} | {r['mean_diff']:+.4f} ± {r['ci95']:.4f} | "
                              f"{r['wins']}/{r['pairs']} | {r['p_perm']:.4f} | {r['p_holm']:.4f} |")
        md.append("")
    out = HW / (("report_c_summary" + ("_visdrone" if a.visdrone else "")) + (".json" if not a.only else "_partial.json"))
    json.dump(summary, open(out, "w"), indent=1)
    (HW / out.name.replace("summary", "tables").replace(".json", ".md")).write_text(
        "# Task C: standard-metric rescoring of every VisDrone-VID campaign\n\n"
        "sAP = streaming AP, standard 'newest' holding rule unless marked 'quality'. 'masked' = VisDrone ignored regions "
        "masked (official protocol). +fc = with the campaign's forecaster (v2 offline for the Part 12/14 campaigns, v2 "
        "computed live on the Pi from the 80-run campaign on). Sizes: COCO area ranges in the 640-px frame (91 % of the "
        "objects are small, 9 % medium, 7 objects large -> not reported). Freshness: age of the held result at each camera "
        "frame (30 fps); stale = older than 300 ms. Compare numbers within one campaign only.\n\n" + "\n".join(md))
    print("wrote", out)


if __name__ == "__main__":
    main()
