#!/usr/bin/env python3
"""Worst-phase streaming AP and staleness of every hardware campaign, from the existing per-run scores (29 Oct 2026).

Mean sAP can rank systems differently from their worst moments (Yu, Moon and Lee, "Rethinking Streaming-Perception
Evaluation on Heterogeneous Edge Platforms", recommend worst-stream sAP and deadline-miss rates next to the mean).
This reads the per-run caches written by report_rescore.py (nothing is re-scored, nothing is changed) and reports,
per campaign, scenario and policy, with the headline forecaster of each campaign:
  sAP            mean streaming AP of the run
  worst_phase    the run's lowest per-phase sAP (6 phases of 20 s in mission / mission_mirror / static_good;
                 the random scenario's phases are 4 s, so its worst phase is noisier)
  miss           share of camera frames whose held result is older than 300 ms (1 - fresh_share)
  longest_stale  longest stretch with the held result older than 300 ms (s); age_p95 (ms)
mean ± Student-t 95 % half-width over the repetitions; paired worst-phase differences against each campaign's
reference controllers with the exact sign-flip p and Holm over the unique comparisons of the campaign (as 19.5).
Also: per scenario, whether the policy ranked first by mean sAP is also first by worst-phase sAP.
usage: report_worstphase_oct29.py [--coco]   -> experiments/results/hardware/worst_phase_oct29[_coco].json and .md
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "validation" / "hardware"))
from report_rescore import CAMPAIGNS, HW, holm, perm_p, tci  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--coco", action="store_true", help="the COCO-detector scores (default: the VisDrone replay)")
    a = ap.parse_args()
    cname, tag = ("_eval_cache_c.json", "_coco") if a.coco else ("_eval_cache_vd.json", "")
    out, md = {}, [f"# Worst-phase streaming AP and staleness ({'COCO' if a.coco else 'VisDrone'} detectors, "
                   "headline forecaster)\n"]
    for camp, (_, refs, sect) in CAMPAIGNS.items():
        cf = HW / camp / cname
        if not cf.exists():
            continue
        cache = json.load(open(cf))
        runs = defaultdict(dict)                       # (scenario, rep) -> policy -> metrics
        for stem, res in cache.items():
            sc, pol, rep = stem.split("__")
            m = res["fc"]
            ph = list(m["per_phase_sAP"].values())
            runs[(sc, rep)][pol] = {"sAP": m["sAP"], "worst_phase": min(ph), "miss": 1.0 - m["fresh_share"],
                                    "longest_stale_s": m["longest_stale_s"], "age_p95_ms": m["age_p95_ms"],
                                    "worst_name": min(m["per_phase_sAP"], key=m["per_phase_sAP"].get)}
        scen = sorted({s for s, _ in runs})
        pols = sorted({p for d in runs.values() for p in d})
        c = {"section": sect, "scenarios": {}, "paired_worst_phase": {}, "rank_check": {}}
        md += [f"\n## {camp}: {sect}\n"]
        for sc in scen:
            c["scenarios"][sc] = {}
            md += [f"\n**{sc}**\n", "| Policy | n | sAP | worst-phase sAP | most often worst | miss > 300 ms | "
                   "longest stale (s) | age p95 (ms) |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
            for p in pols:
                v = [d[p] for (s, _), d in runs.items() if s == sc and p in d]
                if not v:
                    continue
                names = defaultdict(int)
                for x in v:
                    names[x["worst_name"]] += 1
                row = {k: tci([x[k] for x in v]) for k in ("sAP", "worst_phase", "miss", "longest_stale_s",
                                                           "age_p95_ms")}
                row["n"], row["most_often_worst"] = len(v), max(names, key=names.get)
                c["scenarios"][sc][p] = row
                f = lambda k, d=4: f"{row[k][0]:.{d}f} ± {row[k][1]:.{d}f}"  # noqa: E731
                md += [f"| {p} | {len(v)} | {f('sAP')} | {f('worst_phase')} | {row['most_often_worst']} | "
                       f"{100 * row['miss'][0]:.1f} % | {f('longest_stale_s', 2)} | {row['age_p95_ms'][0]:.0f} |"]
            r = c["scenarios"][sc]
            by_mean = max(r, key=lambda p: r[p]["sAP"][0])
            by_worst = max(r, key=lambda p: r[p]["worst_phase"][0])
            c["rank_check"][sc] = {"first_by_mean": by_mean, "first_by_worst_phase": by_worst,
                                   "same": by_mean == by_worst}
            md += [f"\nFirst by mean sAP: {by_mean}; first by worst-phase sAP: {by_worst}"
                   f"{'' if by_mean == by_worst else ' (different)'}.\n"]
        # paired worst-phase differences, Holm over the unique comparisons of the campaign
        tests, seen = [], set()
        for ref in refs:
            for sc in scen:
                for p in pols:
                    if p == ref or (sc, frozenset((p, ref))) in seen:
                        continue
                    d = [x[p]["worst_phase"] - x[ref]["worst_phase"] for (s, _), x in runs.items()
                         if s == sc and p in x and ref in x]
                    if len(d) < 2:
                        continue
                    seen.add((sc, frozenset((p, ref))))
                    m, h = tci(d)
                    tests.append({"ref": ref, "scenario": sc, "policy": p, "n": len(d), "diff": m, "ci95": h,
                                  "p": perm_p(d)})
        if tests:
            for t, q in zip(tests, holm([t["p"] for t in tests])):
                t["p_holm"] = float(q)
            c["paired_worst_phase"] = tests
            sig = [t for t in tests if t["p_holm"] < 0.05]
            md += [f"Paired worst-phase sAP against {', '.join(refs)}: {len(tests)} unique comparisons, "
                   f"{len(sig)} significant after Holm" + (": " + "; ".join(
                       f"{t['policy']} vs {t['ref']} ({t['scenario']}) {t['diff']:+.4f} ± {t['ci95']:.4f}"
                       for t in sig) if sig else "") + ".\n"]
        out[camp] = c
    dst = HW / f"worst_phase_oct29{tag}"
    json.dump(out, open(dst.with_suffix(".json"), "w"), indent=1)
    open(dst.with_suffix(".md"), "w").write("\n".join(md) + "\n")
    n_rank = [(k, sc, v) for k, c in out.items() for sc, v in c["rank_check"].items()]
    diff = [(k, sc, v) for k, sc, v in n_rank if not v["same"]]
    print(f"wrote {dst}.json/.md; first-by-mean differs from first-by-worst-phase in {len(diff)} of {len(n_rank)} "
          "campaign scenarios")
    for k, sc, v in diff:
        print(f"  {k} {sc}: mean -> {v['first_by_mean']}, worst phase -> {v['first_by_worst_phase']}")


if __name__ == "__main__":
    main()
