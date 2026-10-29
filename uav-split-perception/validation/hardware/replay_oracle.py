#!/usr/bin/env python3
"""How far is v4.1 from the best possible schedule, and are its deadline probabilities calibrated? (29 Oct 2026)

Runs on the trace-driven replay (replay.py, validated against the 240-run main campaign) and changes nothing in it.
Three references, all on the same seeds and link draws as v4.1 (common random numbers):
  clairvoyant   v41_clair: v4.1 with perfect knowledge of the goodput the next transfer on each path will get (the
                draw replay.Link.send is about to make, peeked without consuming it). Its decisions use the true
                latency instead of the Gaussian estimate; prices, forecaster and everything else are v4.1's. The
                gap v41 -> v41_clair is the most any better link prediction (radio-aware, conformal, ...) could add.
  fixed         fix_<server>_<variant>: every single configuration held for the whole run (17 of them).
  per phase     with hindsight, the best of {v4.1, the 17 fixed configurations} in each phase, scored by the
                per-phase streaming AP: (a) chosen per seed (optimistic: the max of noisy values), (b) one choice per
                (scenario, phase) from the mean over seeds (a schedule a designer who knew the scenario would program).
                Phase transitions are free in this bound, so it is optimistic.
None of these is a proven optimum (the exact optimum over per-frame choices is intractable); they bound what
better prediction or better per-phase configuration could add.
Calibration: for every frame v4.1 sends, the p_on / p_late it predicted (the controller's Gaussian formulas) against
whether the result arrived within 300 ms / 1000 ms of capture (never arrived = late).

usage: replay_oracle.py run --policy v41 v41_clair fixed --scenario mission --seeds 1-5 --out DIR
       replay_oracle.py analyze DIR      -> DIR/oracle_summary.json
"""
import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import replay as R  # noqa: E402
from report_rescore import t975  # noqa: E402  (the report's Student-t quantile, df argument)
from adaptive2 import LAPTOP_EXTRA, ONBOARD_VARIANTS, PATH_VARIANTS  # noqa: E402

FIXED = [("laptop", v) for v in dict(PATH_VARIANTS, **LAPTOP_EXTRA)] + [("jetson", v) for v in PATH_VARIANTS] + \
        [("onboard", v) for v in ONBOARD_VARIANTS]
R.POLICIES["v41_clair"] = dict(R.POLICIES["v41"], clair=True)
for _s, _v in FIXED:
    R.POLICIES[f"fix_{_s}_{_v}"] = dict(fixed=(_s, _v))
REM_MEAN = 1.05    # replay.Replay.run draws the server time as remote x (1 + 0.1 U)


def peek(link):
    """The goodput the next Link.send will draw, without consuming it (same stream state afterwards)."""
    st, seq, k = link.rng.getstate(), link.seq, link.k
    g = link.sample()
    link.rng.setstate(st)
    link.seq, link.k = seq, k
    return g


class OracleReplay(R.Replay):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.pred = {}

    def path_value(self, p, var, t):
        L_ = self.links[p]
        if not L_.up:
            return -1.0, 0.0
        model, res, q = (dict(PATH_VARIANTS, **(LAPTOP_EXTRA if p == "laptop" else {})))[var]
        b = self.nbytes[(res, q)]
        te, rem, rtt = R.ENC_MS[res], L_.remote[model], L_.rtt
        if not self.cfg.get("clair"):
            v, p_on = super().path_value(p, var, t)
            r, s = L_.est(t)
            lb = R.LATE_MS - te - rem - rtt
            p_late = R.phi((r - b * 8 / (lb * 1e3)) / s) if lb > 0 else 0.0
            self.pred[(int(round(t / R.PERIOD)), p, var)] = (p_on, p_late)
            return v, p_on
        c, g = L_.cap(t), peek(L_)
        if c is not None:
            g = min(g, c)
        tx = b * 8 / (g * 1e3) if g > 0 else float("inf")
        if tx / 1e3 + rtt / 1e3 > R.STALL_S:          # the transfer would stall and drop the link
            return -1.0, 0.0
        lat = te + tx + rtt + rem * REM_MEAN + rtt / 2
        p_on, p_late = float(lat <= R.D), float(lat <= R.LATE_MS)
        busy = max(tx + rtt, 1000 * R.PERIOD)
        cf = self.cfg
        v = self.acc_of(model, res, q) / self.ref * self.H(lat, busy / max(1, self.n_active)) * p_late
        if "energy" in cf:
            v -= self.cam_price() * self.e_off(res, q, b, g)
        if "fresh" in cf and self.aoi + lat >= R.D:
            v += self.lam_f * p_on
        return v, p_on


def cmd_run(a):
    from stream_ap import evaluate
    R.NETEM_LEGACY = a.netem == "legacy"
    pols = [p for x in a.policy for p in ([f"fix_{s}_{v}" for s, v in FIXED] if x == "fixed" else [x])]
    lo, hi = (int(x) for x in a.seeds.split("-"))
    gp = R.load_goodput()
    c, decays, accs, vd = R.load_all()
    labels = json.load(open(R.VID / "labels.json"))
    fp = json.load(open(R.HW / "forecast_tuning_v2.json"))["best"]["params"]
    out = Path(a.out)
    (out / "rows").mkdir(parents=True, exist_ok=True)
    for sc in a.scenario:
        for seed in range(lo, hi + 1):
            for pol in pols:
                row_f = out / "rows" / f"{sc}__{pol}__r{seed}.json"
                if row_f.exists():
                    continue
                rp = OracleReplay(pol, sc, a.phase_s, seed, gp, c, decays, vd, accs)
                path, m = rp.run(out / "runs")
                ext = not pol.startswith("fix_")            # staleness extras only where they are reported
                ev = evaluate(path, labels, "newest", forecast=fp, extras=ext)
                keys = ("sAP", "fresh_AP", "per_phase_sAP") + (("age_p95_ms", "longest_stale_s", "fresh_share")
                                                               if ext else ())
                row = dict(policy=pol, scenario=sc, seed=seed, netem=a.netem, **m, **{k: ev[k] for k in keys})
                if rp.pred:
                    run = json.load(open(path))
                    cal = []
                    for f in run["frames"]:
                        k = (f["id"], f.get("server"), f.get("variant"))
                        if k in rp.pred:
                            lat = (f["t_res"] - f["id"] * R.PERIOD) * 1e3 if f.get("t_res") is not None else None
                            cal.append([*rp.pred[k], lat])
                    row["calib"] = cal              # [p_on, p_late, latency ms or None]
                json.dump(row, open(row_f, "w"))
                print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()
                                  if k not in ("calib", "per_phase_sAP")}), flush=True)


def calib_table(pairs):
    """pairs: (predicted probability, outcome 0/1) -> reliability bins, expected calibration error, Brier score."""
    p = np.array([x[0] for x in pairs], float)
    y = np.array([x[1] for x in pairs], float)
    edges = np.linspace(0, 1, 11)
    bins, ece = [], 0.0
    for i in range(10):
        m = (p >= edges[i]) & ((p < edges[i + 1]) if i < 9 else (p <= 1.0))
        if m.sum():
            bins.append({"bin": f"{edges[i]:.1f}-{edges[i + 1]:.1f}", "n": int(m.sum()),
                         "pred": float(p[m].mean()), "observed": float(y[m].mean())})
            ece += m.sum() / len(p) * abs(p[m].mean() - y[m].mean())
    return {"n": len(p), "mean_pred": float(p.mean()), "observed": float(y.mean()), "ece": float(ece),
            "brier": float(np.mean((p - y) ** 2)), "bins": bins}


def paired(d):
    d = np.array(d, float)
    h = t975(len(d) - 1) * d.std(ddof=1) / math.sqrt(len(d))
    return {"mean": float(d.mean()), "ci95": float(h), "n": len(d)}


def cmd_analyze(a):
    rows = [json.load(open(f)) for f in sorted(Path(a.dir).glob("rows/*.json"))]
    by = defaultdict(dict)
    for r in rows:
        by[(r["scenario"], r["seed"])][r["policy"]] = r
    fixed = [f"fix_{s}_{v}" for s, v in FIXED]
    out = {"scenarios": {}, "calibration": {}}
    for sc in sorted({k[0] for k in by}):
        seeds = sorted(s for (x, s) in by if x == sc and "v41" in by[(x, s)] and "v41_clair" in by[(x, s)]
                       and all(f in by[(x, s)] for f in fixed))
        if not seeds:
            continue
        runs = [by[(sc, s)] for s in seeds]
        # phases by position (the random scenario's phase names differ between seeds; per_phase_sAP is in time order)
        ph_vals = lambda r: list(r["per_phase_sAP"].values())  # noqa: E731
        n_ph = len(ph_vals(runs[0]["v41"]))
        assert all(len(ph_vals(x[p])) == n_ph for x in runs for p in ["v41", "v41_clair"] + fixed)
        pm = lambda r: float(np.mean(ph_vals(r)))  # noqa: E731
        pool = ["v41"] + fixed
        # (a) per seed and phase, the best of the pool; (b) per phase position, the pool member best on the mean over
        # seeds (for the random scenario the impairments at a position differ between seeds, so (b) is weaker there)
        oa = [float(np.mean([max(ph_vals(x[p])[i] for p in pool) for i in range(n_ph)])) for x in runs]
        pick = [max(pool, key=lambda p: np.mean([ph_vals(x[p])[i] for x in runs])) for i in range(n_ph)]
        ob = [float(np.mean([ph_vals(x[pick[i]])[i] for i in range(n_ph)])) for x in runs]
        phases = list(runs[0]["v41"]["per_phase_sAP"])
        pick = dict(zip(phases, pick)) if sc != "random" else pick
        best_fixed = max(fixed, key=lambda p: np.mean([x[p]["sAP"] for x in runs]))
        v41 = [x["v41"]["sAP"] for x in runs]
        out["scenarios"][sc] = {
            "seeds": seeds, "phases": len(phases),
            "sAP": {"v41": float(np.mean(v41)), "v41_clair": float(np.mean([x["v41_clair"]["sAP"] for x in runs])),
                    "best_fixed": [best_fixed, float(np.mean([x[best_fixed]["sAP"] for x in runs]))]},
            "clair_minus_v41": paired([x["v41_clair"]["sAP"] - x["v41"]["sAP"] for x in runs]),
            "v41_minus_best_fixed": paired([x["v41"]["sAP"] - x[best_fixed]["sAP"] for x in runs]),
            "pi_w": {"v41": float(np.mean([x["v41"]["pi_w"] for x in runs])),
                     "v41_clair": float(np.mean([x["v41_clair"]["pi_w"] for x in runs]))},
            "phase_mean_sAP": {"v41": float(np.mean([pm(x["v41"]) for x in runs])),
                               "v41_clair": float(np.mean([pm(x["v41_clair"]) for x in runs])),
                               "oracle_per_seed": float(np.mean(oa)), "oracle_schedule": float(np.mean(ob))},
            "oracle_schedule_pick": pick,
            "v41_share_of_oracle_schedule": float(np.mean([pm(x["v41"]) for x in runs]) / np.mean(ob)),
            "v41_share_of_oracle_per_seed": float(np.mean([pm(x["v41"]) for x in runs]) / np.mean(oa)),
            "v41_share_of_clair": float(np.mean(v41) / np.mean([x["v41_clair"]["sAP"] for x in runs])),
        }
    cal = [c for r in rows if r["policy"] == "v41" for c in r.get("calib", [])]
    if cal:
        out["calibration"] = {
            "p_on_vs_300ms": calib_table([(c[0], float(c[2] is not None and c[2] <= R.D)) for c in cal]),
            "p_late_vs_1000ms": calib_table([(c[1], float(c[2] is not None and c[2] <= R.LATE_MS)) for c in cal])}
        for sc in out["scenarios"]:
            cs = [c for r in rows if r["policy"] == "v41" and r["scenario"] == sc for c in r.get("calib", [])]
            out["scenarios"][sc]["calibration_p_on"] = calib_table(
                [(c[0], float(c[2] is not None and c[2] <= R.D)) for c in cs])
    json.dump(out, open(Path(a.dir) / "oracle_summary.json", "w"), indent=1)
    for sc, s in out["scenarios"].items():
        print(f"{sc:15s} v41 {s['sAP']['v41']:.4f}  clair {s['sAP']['v41_clair']:.4f} "
              f"({s['clair_minus_v41']['mean']:+.4f} ± {s['clair_minus_v41']['ci95']:.4f})  best fixed "
              f"{s['sAP']['best_fixed'][0]} {s['sAP']['best_fixed'][1]:.4f}  | phase-mean v41 "
              f"{s['phase_mean_sAP']['v41']:.4f} oracle schedule {s['phase_mean_sAP']['oracle_schedule']:.4f} "
              f"per seed {s['phase_mean_sAP']['oracle_per_seed']:.4f}")
    if cal:
        for k, v in out["calibration"].items():
            print(k, f"n {v['n']} mean pred {v['mean_pred']:.3f} observed {v['observed']:.3f} "
                     f"ECE {v['ece']:.3f} Brier {v['brier']:.3f}")
            for b in v["bins"]:
                print(f"   {b['bin']}  n {b['n']:6d}  pred {b['pred']:.3f}  observed {b['observed']:.3f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--policy", nargs="+", default=["v41", "v41_clair", "fixed"])
    r.add_argument("--scenario", nargs="+", default=["mission"])
    r.add_argument("--phase-s", type=float, default=20.0)
    r.add_argument("--seeds", default="1-5")
    r.add_argument("--netem", default="reset", choices=["reset", "legacy"])
    r.add_argument("--out", required=True)
    z = sub.add_parser("analyze")
    z.add_argument("dir")
    a = ap.parse_args()
    cmd_run(a) if a.cmd == "run" else cmd_analyze(a)


if __name__ == "__main__":
    main()
