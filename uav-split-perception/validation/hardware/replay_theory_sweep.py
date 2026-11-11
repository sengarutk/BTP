#!/usr/bin/env python3
"""Paper 2's guarantees against the validated replay: step size and budget (11 Nov 2026, hardening plan, Phase 1).
Predictions written before any run: docs/theory_sweep_predictions_nov11.md.

One setting of v4.1 is changed at a time, everything else held (replay_sweep.py's design, common random numbers):
  step size eta (mu_step)   0.02, 0.05, 0.1 (v4.1), 0.2, 0.5, 1.0        budget 2.8 W
  budget B (energy)         2.4, 2.8 (v4.1), 3.2, 3.6, 4.0, 4.5 W        eta 0.1
  ambient (ambient_c)       +5 C at 3.6 and 3.2 W, +10 C at 3.6 and 2.8 W (plant intercept and start shifted)
The replay (replay.py) logs, per run, the price updates and Theorem 1's terms: N updates, the mean of the 1-s power
P_t the updates used, the final price mu_N, and the sums of (-s_t)^+ over held and capped updates. From these:
  excess      mean P_t - B (Theorem 1's left side minus B)
  price term  mu_N / (eta N);  hold term, cap term  sum (-s_t)^+ / (eta N);  bound = B + the three terms
  gap term    (eta / 2) mean (P_t - B)^2, Theorem 2's idealised accuracy gap (value units per second)
and, as replay_sweep.py, sAP, the true mean board power, the temperature and the share of time at or above 80 C.
The replay's thermal plant is Proposition 1's own first-order fit, so the mean temperature is not evidence for it.
usage: replay_theory_sweep.py run --scenario mission --phase-s 20 --seeds 1-10 --out DIR [--only th_eta0.5 ...]
       replay_theory_sweep.py analyze DIR     -> DIR/theory_sweep_summary.json
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import replay as R  # noqa: E402
import replay_accumo as A  # noqa: E402

BASE = dict(R.POLICIES["v41"])
ETAS = (0.02, 0.05, 0.1, 0.2, 0.5, 1.0)
BUDGETS = (2.4, 2.8, 3.2, 3.6, 4.0, 4.5)
# a hotter room than the measured one (ambient extrapolation, docs/theory_sweep_predictions_nov11.md, addendum):
# +5 and +10 C with the lab's 80-C budget kept (3.6 W) or with the budget the rule gives for that room (80 - a - dT)/b
AMBIENT = {(5, 3.6), (5, 3.2), (10, 3.6), (10, 2.8)}
SWEEP = {**{f"th_eta{v:g}": {"mu_step": v} for v in ETAS if v != 0.1},
         **{f"th_b{v:g}": {"energy": v} for v in BUDGETS if v != 2.8},
         **{f"th_amb{d}_b{b:g}": {"ambient_c": float(d), "energy": b} for d, b in sorted(AMBIENT)}}
DEFAULT = {"mu_step": 0.1, "energy": 2.8, "ambient_c": 0.0}
for name, ov in SWEEP.items():
    R.POLICIES[name] = dict(BASE, **ov)
ETA_POLS = ["v41"] + [n for n, ov in SWEEP.items() if list(ov) == ["mu_step"]]
BUDGET_POLS = ["v41"] + [n for n, ov in SWEEP.items() if list(ov) == ["energy"]]
AMB_POLS = [n for n in SWEEP if n.startswith("th_amb")]
METRICS = ("sAP", "pi_w", "temp_mean_c", "temp_max_c", "hot_share", "fresh_share")


def setting(pol):
    return {**DEFAULT, **SWEEP.get(pol, {})}


def terms(row):
    """Theorem 1's and Theorem 2's terms of one run, from the replay's price log."""
    s, pr = setting(row["policy"]), row["price"]
    eta, B, n = s["mu_step"], s["energy"], pr["n"]
    mean_p = pr["sum_p"] / n
    t = {"eta": eta, "budget": B, "updates": n, "mean_p_updates": mean_p, "excess": mean_p - B,
         "price_term": pr["mu_final"] / (eta * n), "hold_term": pr["neg_held"] / (eta * n),
         "cap_term": pr["neg_cap"] / (eta * n), "other_neg": pr["neg_step"], "mu_final": pr["mu_final"],
         "mu_max": pr["mu_max"], "held_share": pr["n_held"] / n, "cap_share": pr["n_cap"] / n,
         "msq": pr["sum_sq"] / n, "gap_term": eta / 2 * pr["sum_sq"] / n}
    t["bound"] = B + t["price_term"] + t["hold_term"] + t["cap_term"]
    t["bound_holds"] = bool(mean_p <= t["bound"] + 1e-9)
    return t


def cmd_run(a):
    pols = a.only or (ETA_POLS + BUDGET_POLS[1:])
    A.cmd_run(argparse.Namespace(policy=pols, scenario=a.scenario, phase_s=a.phase_s, seeds=a.seeds,
                                 netem="reset", onboard_power="power", out=a.out))


def cmd_analyze(a):
    rows = [json.load(open(f)) for f in sorted(Path(a.dir).glob("rows/*.json"))]
    by = defaultdict(dict)
    for r in rows:
        by[(f"{r['scenario']}_{r['phase_s']:g}s", r["seed"])][r["policy"]] = r
    out = {"default": DEFAULT, "predictions": "docs/theory_sweep_predictions_nov11.md", "scenarios": {}}
    for sc in sorted({k[0] for k in by}):
        keys = sorted(k for k in by if k[0] == sc and "v41" in by[k])
        ent = {"seeds": [k[1] for k in keys], "policies": {}}
        for pol in ETA_POLS + BUDGET_POLS[1:] + AMB_POLS:
            ks = [k for k in keys if pol in by[k]]
            if not ks:
                continue
            rs = [by[k][pol] for k in ks]
            tt = [terms(r) for r in rs]
            e = {"setting": setting(pol), "n": len(ks),
                 **{m: float(np.mean([r[m] for r in rs])) for m in METRICS},
                 **{k: float(np.mean([t[k] for t in tt])) for k in tt[0] if not isinstance(tt[0][k], bool)},
                 "excess_max": float(max(t["excess"] for t in tt)),
                 "bound_holds_all": all(t["bound_holds"] for t in tt),
                 "onboard_share": float(np.mean([r["sends"].get("onboard", 0) / r["n_frames"] for r in rs]))}
            if pol != "v41":
                e["sAP_minus_v41"] = A.paired([by[k][pol]["sAP"] - by[k]["v41"]["sAP"] for k in ks])
                e["pi_w_minus_v41"] = A.paired([by[k][pol]["pi_w"] - by[k]["v41"]["pi_w"] for k in ks])
            ent["policies"][pol] = e
        out["scenarios"][sc] = ent
    json.dump(out, open(Path(a.dir) / "theory_sweep_summary.json", "w"), indent=1)
    for sc, ent in out["scenarios"].items():
        print(f"{sc}  seeds {ent['seeds']}")
        for pol, e in ent["policies"].items():
            d = e.get("sAP_minus_v41", {"mean": 0.0, "ci95": 0.0})
            print(f"  {pol:14s} amb +{e['setting']['ambient_c']:g} eta {e['setting']['mu_step']:<4g} B {e['setting']['energy']:<3g}  excess {e['excess']:+.3f}"
                  f" (max {e['excess_max']:+.3f})  price {e['price_term']:.3f} hold {e['hold_term']:.3f} cap "
                  f"{e['cap_term']:.3f}  gap {e['gap_term']:.3f}  bound {'ok' if e['bound_holds_all'] else 'FAILS'}  "
                  f"sAP {e['sAP']:.4f} ({d['mean']:+.4f} ± {d['ci95']:.4f})  T {e['temp_mean_c']:.1f}/{e['temp_max_c']:.1f}"
                  f"  hot {100 * e['hot_share']:.1f} %  onboard {100 * e['onboard_share']:.1f} %", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--scenario", nargs="+", default=["mission"])
    r.add_argument("--phase-s", type=float, default=20.0)
    r.add_argument("--seeds", default="1-10")
    r.add_argument("--only", nargs="+")
    r.add_argument("--out", required=True)
    z = sub.add_parser("analyze")
    z.add_argument("dir")
    a = ap.parse_args()
    {"run": cmd_run, "analyze": cmd_analyze}[a.cmd](a)


if __name__ == "__main__":
    main()
