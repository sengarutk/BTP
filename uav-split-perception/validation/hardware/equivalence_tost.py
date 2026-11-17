#!/usr/bin/env python3
"""Item 5 of the laptop strengthening (16 Nov 2026; predictions in docs/laptop_strengthening_predictions_nov16.md):
every "same accuracy at less power / heat" claim of paper 2 as a tested equivalence.

Per comparison: paired differences (strategy A - strategy B, same scenario and repetition, one campaign) of
streaming AP with the forecaster (sAP_fc, the score cache every summary uses), the Pi's mean power and, where the
temperature log exists, the share of time at or above 80 C. Equivalence of sAP: two one-sided t-tests (TOST,
alpha 0.05) with margin +-0.005 sAP, i.e. the 90 % t-interval of the mean difference lies inside (-0.005, +0.005).
Power and hot time: mean difference, 95 % t-interval, two-sided t p-value.
usage: python validation/hardware/equivalence_tost.py  -> experiments/results/hardware/equivalence/equivalence.json
"""
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
H = ROOT / "experiments" / "results" / "hardware"
sys.path.insert(0, str(ROOT / "scripts"))
from audit_nov16 import t_two_sided_p  # noqa: E402  (regularised incomplete beta, no scipy in this venv)

MARGIN = 0.005
COMPARISONS = [   # (label, campaign, scenarios, A, B, what the paper claims)
    ("no prices vs v4.1", "mesh2", ("static_good", "mesh_mission", "multihop"), "noprice", "v41",
     "prices: same accuracy at far less power and heat"),
    ("heat price vs Pi energy price", "mesh2", ("static_good", "mesh_mission", "multihop"), "heat", "v41",
     "a heat price adds nothing beyond the energy price"),
    ("heat price vs Pi energy price, 24 min", "mesh2_long", ("mesh_mission",), "heat", "v41", "same, 24-min missions"),
    ("final controller vs v4.1", "final_nov", ("mesh_mission", "multihop"), "v41final", "v41",
     "the final configuration costs nothing against v4.1"),
    ("final controller vs v4.1, one hop", "final_nov", ("mesh_mission",), "v41final", "v41", ""),
    ("final controller vs v4.1, multihop", "final_nov", ("multihop",), "v41final", "v41", ""),
    ("capped hold vs hold always, 24 min", "heat_nov", ("mission",), "v41cap", "v41",
     "capping the hold removes the heat at no accuracy cost"),
    ("capped hold + guard vs hold always, 24 min", "heat_nov", ("mission",), "v41guard", "v41", ""),
    ("budget 2.4 vs 2.8 W", "budget_nov", ("mesh_mission", "multihop"), "v41final24", "v41final",
     "the 2.4 W budget saves power at the same accuracy"),
    ("late-path skip vs none, one hop", "fix_nov", ("mesh_mission",), "v41fix24", "v41final24",
     "the skip costs little on one hop"),
    ("CPU clock knob vs none, 24 min", "dvfs_heat", ("mission",), "v41dvfs", "v41final", "the clock knob is neutral"),
    ("CPU clock knob vs none, short", "dvfs_short", ("mission",), "v41dvfs", "v41final", ""),
]


def t_quantile(p_two_sided, df):
    """t such that the two-sided p-value is p (bisection on our own t CDF)"""
    lo, hi = 0.0, 100.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if t_two_sided_p(mid, df) > p_two_sided:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def hot_share(f):
    me = json.load(open(f))["measured_energy"]
    L = np.array(me["log_t_w_c"], float)
    t, T = L[:, 0], L[:, 2]
    w = np.r_[t[1:] - t[:-1], 0.0]
    return 100 * float(w[T >= 80.0].sum()) / float(t[-1])


def stats(d):
    d = np.asarray(d, float)
    n = len(d)
    m = float(d.mean())
    se = float(d.std(ddof=1)) / math.sqrt(n)
    out = {"n": n, "mean": m, "se": se}
    if se == 0:
        return out | {"ci95": 0.0, "p": 1.0 if m == 0 else 0.0}
    t95 = t_quantile(0.05, n - 1)
    return out | {"ci95": t95 * se, "p": t_two_sided_p(abs(m) / se, n - 1)}


def main():
    res = []
    for label, camp, scs, a, b, claim in COMPARISONS:
        c = json.load(open(H / f"vid_campaign_{camp}" / "_eval_cache_mesh.json"))
        keys = [(sc, r) for sc in scs for r in range(1, 10)
                if f"{sc}__{a}__r{r}" in c and f"{sc}__{b}__r{r}" in c]
        ds = [c[f"{sc}__{a}__r{r}"]["sAP_fc"] - c[f"{sc}__{b}__r{r}"]["sAP_fc"] for sc, r in keys]
        dw = [c[f"{sc}__{a}__r{r}"]["pi_w"] - c[f"{sc}__{b}__r{r}"]["pi_w"] for sc, r in keys]
        s = stats(ds)
        n = s["n"]
        t90 = t_quantile(0.10, n - 1)
        lo90, hi90 = s["mean"] - t90 * s["se"], s["mean"] + t90 * s["se"]
        # TOST p-value: the larger of the two one-sided p-values
        p_lo = t_two_sided_p(abs((s["mean"] + MARGIN) / s["se"]), n - 1) / 2
        p_lo = p_lo if s["mean"] + MARGIN > 0 else 1 - p_lo
        p_hi = t_two_sided_p(abs((s["mean"] - MARGIN) / s["se"]), n - 1) / 2
        p_hi = p_hi if s["mean"] - MARGIN < 0 else 1 - p_hi
        row = {"label": label, "campaign": camp, "scenarios": list(scs), "a": a, "b": b, "claim": claim,
               "pairs": n, "sap": s, "sap_ci90": [lo90, hi90], "tost_p": max(p_lo, p_hi),
               "equivalent": bool(-MARGIN < lo90 and hi90 < MARGIN), "pi_w": stats(dw)}
        D = H / f"vid_campaign_{camp}"
        try:
            dh = [hot_share(D / f"a2_{sc}__{a}__r{r}.json") - hot_share(D / f"a2_{sc}__{b}__r{r}.json") for sc, r in keys]
            row["hot_pct"] = stats(dh)
        except (KeyError, FileNotFoundError):
            pass
        res.append(row)
        print(f"{label:45s} n={n:2d} dsAP {s['mean']:+.4f} 90%CI [{lo90:+.4f},{hi90:+.4f}] "
              f"{'EQUIV' if row['equivalent'] else 'not shown'} (TOST p {row['tost_p']:.3f}) | "
              f"dW {row['pi_w']['mean']:+.3f}±{row['pi_w']['ci95']:.3f} p {row['pi_w']['p']:.4f}"
              + (f" | dhot {row['hot_pct']['mean']:+.1f}±{row['hot_pct']['ci95']:.1f} pts" if "hot_pct" in row else ""))
    out = H / "equivalence"
    out.mkdir(exist_ok=True)
    json.dump({"margin_sap": MARGIN, "alpha": 0.05, "comparisons": res}, open(out / "equivalence.json", "w"), indent=1)


if __name__ == "__main__":
    main()
