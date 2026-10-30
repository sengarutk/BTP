#!/usr/bin/env python3
"""Sensitivity of v4.1 to its own settings, in the replay (29 Oct 2026).

One setting at a time is moved away from the value the board runs (adaptive2.py flags in brackets), everything else
held at v4.1's:
  energy target      2.8 W     (--power-budget)   2.4, 2.6, 3.0, 3.2
  freshness target   0.95      (--fresh-target)   0.85, 0.90, 0.99
  energy price step  0.1       (--eta)            0.05, 0.2
  freshness step     2.0       (--eta-f)          1.0, 4.0
  freshness cap      2.0       (--lam-f-max)      1.0, 4.0
Each variant runs on the same seeds and link draws as v4.1 (common random numbers, replay_accumo.py's harness, netem
reset per phase) and is compared with v4.1 seed by seed. This measures how flat v4.1's result is around its settings;
it does not choose new settings (any change would need a held-out check first).

usage: replay_sweep.py run --scenario mission random --seeds 1-10 --out DIR [--only v41 sw_e2.4 ...]
       replay_sweep.py analyze DIR      -> DIR/sweep_summary.json
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
SWEEP = {   # name -> (setting, value)
    **{f"sw_e{v:g}": ("energy", v) for v in (2.4, 2.6, 3.0, 3.2)},
    **{f"sw_f{v:g}": ("fresh", v) for v in (0.85, 0.90, 0.99)},
    **{f"sw_mustep{v:g}": ("mu_step", v) for v in (0.05, 0.2)},
    **{f"sw_fstep{v:g}": ("fresh_step", v) for v in (1.0, 4.0)},
    **{f"sw_fcap{v:g}": ("fresh_cap", v) for v in (1.0, 4.0)},
}
DEFAULT = {"energy": 2.8, "fresh": 0.95, "mu_step": 0.1, "fresh_step": 2.0, "fresh_cap": 2.0}
for name, (k, v) in SWEEP.items():
    R.POLICIES[name] = dict(BASE, **{k: v})


def cmd_run(a):
    pols = a.only or ["v41"] + list(SWEEP)
    A.cmd_run(argparse.Namespace(policy=pols, scenario=a.scenario, phase_s=a.phase_s, seeds=a.seeds,
                                 netem="reset", onboard_power=a.onboard_power, out=a.out))


def cmd_analyze(a):
    rows = [json.load(open(f)) for f in sorted(Path(a.dir).glob("rows/*.json"))]
    by = defaultdict(dict)
    for r in rows:
        by[(f"{r['scenario']}_{r['phase_s']:g}s", r["seed"])][r["policy"]] = r
    out = {"default": DEFAULT, "scenarios": {}}
    for sc in sorted({k[0] for k in by}):
        keys = sorted(k for k in by if k[0] == sc and "v41" in by[k])
        ent = {"seeds": [k[1] for k in keys], "v41": {m: float(np.mean([by[k]["v41"][m] for k in keys]))
                                                      for m in ("sAP", "pi_w", "fresh_share", "hot_share")},
               "variants": {}}
        for name, (setting, val) in SWEEP.items():
            ks = [k for k in keys if name in by[k]]
            if not ks:
                continue
            rs = [by[k][name] for k in ks]
            ent["variants"][name] = dict(
                setting=setting, value=val,
                **{m: float(np.mean([r[m] for r in rs])) for m in ("sAP", "pi_w", "fresh_share", "hot_share")},
                onboard_share=float(np.mean([r["sends"].get("onboard", 0) / r["n_frames"] for r in rs])),
                minus_v41=A.paired([by[k][name]["sAP"] - by[k]["v41"]["sAP"] for k in ks]),
                pi_w_minus_v41=float(np.mean([by[k][name]["pi_w"] - by[k]["v41"]["pi_w"] for k in ks])))
        out["scenarios"][sc] = ent
    json.dump(out, open(Path(a.dir) / "sweep_summary.json", "w"), indent=1)
    for sc, ent in out["scenarios"].items():
        v = ent["v41"]
        print(f"{sc}  n {len(ent['seeds'])}  v41 sAP {v['sAP']:.4f}  Pi {v['pi_w']:.2f} W  fresh {100 * v['fresh_share']:.1f} %")
        for name, e in ent["variants"].items():
            d = e["minus_v41"]
            print(f"  {e['setting']:10s} {e['value']:<5g} sAP {e['sAP']:.4f}  this - v41 {d['mean']:+.4f} ± {d['ci95']:.4f}"
                  f"  Pi {e['pi_w_minus_v41']:+.2f} W  fresh {100 * e['fresh_share']:.1f} %  onboard "
                  f"{100 * e['onboard_share']:.1f} %")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--scenario", nargs="+", default=["mission", "random"])
    r.add_argument("--phase-s", type=float, default=20.0)
    r.add_argument("--seeds", default="1-10")
    r.add_argument("--only", nargs="*")
    r.add_argument("--onboard-power", default="energy", choices=["energy", "power"])
    r.add_argument("--out", required=True)
    z = sub.add_parser("analyze")
    z.add_argument("dir")
    a = ap.parse_args()
    cmd_run(a) if a.cmd == "run" else cmd_analyze(a)


if __name__ == "__main__":
    main()
