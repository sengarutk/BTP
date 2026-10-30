#!/usr/bin/env python3
"""What do joint link failures cost, and could better prediction recover it? (replay, 29 Oct 2026)

All mesh links share one 2.4 GHz channel, so interference can hit the laptop path and the Jetson path at the same
moment. The replay's two paths draw goodput independently, so this script adds short deep fades ("bursts") on top
of the unimpaired static_good scenario and varies only how often the two paths fade together:
  bursts    Poisson arrivals, exponential durations (mean 0.3 s or 1.5 s); during a burst the path's goodput is
            capped at FADE_MBPS (a transfer's time is integrated over the burst timeline, so a burst starting or
            ending mid-transfer slows only that part)
  rho       share of bursts that hit both paths: 0 (independent), 0.5, 1 (every burst joint). The total burst rate
            per path is the same for every rho, so each path is faded for the same share of time (about 14 %,
            1 - exp(-0.15)) and only the overlap changes (about 2 % of the time at rho 0, 14 % at rho 1)
  none      no bursts (reference)
The bursts of a (condition, seed) are the same for every policy (common random numbers, as replay.py).
Policies: v4.1, v4.1 with a clairvoyant link (it knows the exact transfer time, bursts included, as in
replay_oracle.py), v5, and fixed laptop / Jetson / onboard. These bursts are synthetic: they show what joint fades
would cost if they occur, not whether they occur on the mesh (that needs the interference test on hardware).

usage: replay_joint.py run --cond none r0_d0.3 r1_d1.5 ... --seeds 1-10 --out DIR
       replay_joint.py analyze DIR      -> DIR/joint_summary.json
"""
import argparse
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import replay as R  # noqa: E402
import replay_oracle as O  # noqa: E402  (registers v41_clair and the fixed policies)
from adaptive2 import LAPTOP_EXTRA, PATH_VARIANTS  # noqa: E402

FADE_MBPS, BAD_RATE_X_DUR = 0.5, 0.15      # cap during a burst; per-path burst rate x mean duration
POLS = ["v41", "v41_clair", "v5", "fix_laptop_m640q90", "fix_jetson_s640q90", "fix_onboard_n320"]
CONDS = ["none"] + [f"r{r:g}_d{d:g}" for d in (0.3, 1.5) for r in (0, 0.5, 1)]


def parse(cond):
    if cond == "none":
        return None
    r, d = cond.split("_")
    return float(r[1:]), float(d[1:])


def bursts(cond, seed, total):
    """Burst intervals per path for a condition and seed: the union of the joint and the path's own bursts."""
    if parse(cond) is None:
        return {"laptop": [], "jetson": []}
    rho, dur = parse(cond)
    lam = BAD_RATE_X_DUR / dur
    rng = random.Random(seed * 104729 + int(rho * 10) * 31 + int(dur * 10))

    def poisson(rate):
        out, t = [], 0.0
        while rate > 0:
            t += rng.expovariate(rate)
            if t >= total:
                return out
            out.append((t, t + rng.expovariate(1.0 / dur)))
        return out
    joint = poisson(rho * lam)
    own = {p: poisson((1 - rho) * lam) for p in ("laptop", "jetson")}
    res = {}
    for p in own:
        iv = sorted(joint + own[p])
        merged = []
        for a, b in iv:
            if merged and a <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        res[p] = [tuple(x) for x in merged]
    return res


def covered(iv, total, step=0.01):
    m = np.zeros(int(total / step), bool)
    for a, b in iv:
        m[int(a / step):int(min(b, total) / step)] = True
    return m


class BurstLink(R.Link):
    """replay.Link with burst fades: the transfer time is integrated over the burst timeline."""

    def tx_s(self, t0, nbytes, g):
        """Seconds to move nbytes from t0 at goodput g (Mbit/s) outside bursts and min(g, FADE) inside."""
        left, t = nbytes * 8 / 1e6, t0          # Mbit
        for a, b in self.bursts:
            if b <= t:
                continue
            if a > t:                            # clear stretch before the burst
                if left <= g * (a - t):
                    return t + left / g - t0
                left -= g * (a - t)
                t = a
            gb = min(g, FADE_MBPS)               # inside the burst
            if left <= gb * (b - t):
                return t + left / gb - t0
            left -= gb * (b - t)
            t = b
        return t + left / g - t0

    def send(self, t, nbytes):
        c = self.cap(t)
        g = self.sample()
        if c is not None:
            g = min(g, c)
        t_done = float("inf") if g <= 0 else t + self.tx_s(t, nbytes, g) + self.rtt / 1e3
        self.inflight = (t, nbytes, t_done)
        return t_done


class JointReplay(O.OracleReplay):
    def __init__(self, cond, *a, **kw):
        super().__init__(*a, **kw)
        total = float(sum(ph[3] for ph in self.phases))
        self.bursts = bursts(cond, self.seed, total)
        for p, L_ in self.links.items():
            L_.__class__ = BurstLink
            L_.bursts = self.bursts[p]

    def path_value(self, p, var, t):
        if not self.cfg.get("clair"):
            return super().path_value(p, var, t)
        L_ = self.links[p]                        # clairvoyant: the true transfer time, bursts included
        if not L_.up:
            return -1.0, 0.0
        model, res, q = (dict(PATH_VARIANTS, **(LAPTOP_EXTRA if p == "laptop" else {})))[var]
        b = self.nbytes[(res, q)]
        te, rem, rtt = R.ENC_MS[res], L_.remote[model], L_.rtt
        c, g = L_.cap(t), O.peek(L_)
        if c is not None:
            g = min(g, c)
        if g <= 0:
            return -1.0, 0.0
        tx_s = L_.tx_s(t + te / 1e3, b, g)
        if tx_s + rtt / 1e3 > R.STALL_S:
            return -1.0, 0.0
        tx = tx_s * 1e3
        lat = te + tx + rtt + rem * O.REM_MEAN + rtt / 2
        p_on, p_late = float(lat <= R.D), float(lat <= R.LATE_MS)
        busy = max(tx + rtt, 1000 * R.PERIOD)
        cf = self.cfg
        v = self.acc_of(model, res, q) / self.ref * self.H(lat, busy / max(1, self.n_active)) * p_late
        if "energy" in cf:
            v -= self.cam_price() * self.e_off(res, q, b, b * 8 / (tx_s * 1e6))
        if "fresh" in cf and self.aoi + lat >= R.D:
            v += self.lam_f * p_on
        return v, p_on


def cmd_run(a):
    from stream_ap import evaluate
    R.NETEM_LEGACY = False
    lo, hi = (int(x) for x in a.seeds.split("-"))
    gp = R.load_goodput()
    c, decays, accs, vd = R.load_all()
    labels = json.load(open(R.VID / "labels.json"))
    fp = json.load(open(R.HW / "forecast_tuning_v2.json"))["best"]["params"]
    out = Path(a.out)
    (out / "rows").mkdir(parents=True, exist_ok=True)
    for cond in a.cond:
        for seed in range(lo, hi + 1):
            for pol in a.policy:
                row_f = out / "rows" / f"{cond}__{pol}__r{seed}.json"
                if row_f.exists():
                    continue
                rp = JointReplay(cond, pol, "static_good", 20.0, seed, gp, c, decays, vd, accs)
                path, m = rp.run(out / "runs" / cond)
                ev = evaluate(path, labels, "newest", forecast=fp, extras=True)
                total = m["duration_s"]
                cl, cj = covered(rp.bursts["laptop"], total), covered(rp.bursts["jetson"], total)
                run = json.load(open(path))
                srv = defaultdict(int)
                for f in run["frames"]:
                    if f.get("server"):
                        srv[f["server"]] += 1
                row = dict(policy=pol, cond=cond, seed=seed, **m,
                           **{k: ev[k] for k in ("sAP", "fresh_AP", "age_p95_ms", "longest_stale_s", "fresh_share")},
                           faded_laptop=float(cl.mean()), faded_jetson=float(cj.mean()),
                           faded_both=float((cl & cj).mean()), dispatches=dict(srv))
                json.dump(row, open(row_f, "w"))
                print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()}), flush=True)


def tci(d):
    d = np.array(d, float)
    h = O.t975(len(d) - 1) * d.std(ddof=1) / math.sqrt(len(d)) if len(d) > 1 else float("nan")
    return [float(d.mean()), float(h)]


def cmd_analyze(a):
    rows = [json.load(open(f)) for f in sorted(Path(a.dir).glob("rows/*.json"))]
    by = defaultdict(dict)
    for r in rows:
        by[(r["cond"], r["seed"])][r["policy"]] = r
    conds = [c for c in CONDS if any(k[0] == c for k in by)]
    out = {"fade_mbps": FADE_MBPS, "conds": {}}
    for cond in conds:
        seeds = sorted(s for (c, s) in by if c == cond and all(p in by[(c, s)] for p in POLS))
        runs = [by[(cond, s)] for s in seeds]
        x = {"seeds": seeds,
             "faded": {k: tci([r["v41"][k] for r in runs]) for k in ("faded_laptop", "faded_jetson", "faded_both")},
             "policies": {p: {k: tci([r[p][k] for r in runs]) for k in
                              ("sAP", "fresh_share", "longest_stale_s", "pi_w")} for p in POLS},
             "paired": {f"v41-{p}": tci([r["v41"]["sAP"] - r[p]["sAP"] for r in runs]) for p in POLS if p != "v41"},
             "v41_dispatch_share": {s: float(np.mean([r["v41"]["dispatches"].get(s, 0) /
                                                      max(1, sum(r["v41"]["dispatches"].values())) for r in runs]))
                                    for s in ("laptop", "jetson", "onboard")}}
        if cond != "none":
            ref = [by[("none", s)] for s in seeds if ("none", s) in by]
            if len(ref) == len(seeds):
                x["loss_vs_none"] = {p: tci([r[p]["sAP"] - q[p]["sAP"] for r, q in zip(runs, ref)]) for p in POLS}
        out["conds"][cond] = x
    # correlation at equal marginal: rho 1 against rho 0, paired by seed
    out["rho1_minus_rho0"] = {}
    for d in (0.3, 1.5):
        c0, c1 = f"r0_d{d:g}", f"r1_d{d:g}"
        ss = [s for s in range(1, 100) if all((c, s) in by and all(p in by[(c, s)] for p in POLS) for c in (c0, c1))]
        if ss:
            out["rho1_minus_rho0"][f"d{d:g}"] = {p: tci([by[(c1, s)][p]["sAP"] - by[(c0, s)][p]["sAP"] for s in ss])
                                                 for p in POLS}
    json.dump(out, open(Path(a.dir) / "joint_summary.json", "w"), indent=1)
    for cond, x in out["conds"].items():
        f = x["faded"]
        print(f"{cond:9s} faded L {f['faded_laptop'][0]:.3f} J {f['faded_jetson'][0]:.3f} both {f['faded_both'][0]:.3f} | " +
              "  ".join(f"{p} {v['sAP'][0]:.4f}" for p, v in x["policies"].items()))
        print("          " + "  ".join(f"{k} {v[0]:+.4f}±{v[1]:.4f}" for k, v in x["paired"].items()))
        if "loss_vs_none" in x:
            print("          loss vs none: " + "  ".join(f"{k} {v[0]:+.4f}±{v[1]:.4f}" for k, v in x["loss_vs_none"].items()))
        print(f"          v41 dispatch {x['v41_dispatch_share']}  fresh {x['policies']['v41']['fresh_share'][0]:.3f}")
    for d, x in out["rho1_minus_rho0"].items():
        print(f"rho1 - rho0 ({d}): " + "  ".join(f"{k} {v[0]:+.4f}±{v[1]:.4f}" for k, v in x.items()))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--cond", nargs="+", default=CONDS)
    r.add_argument("--policy", nargs="+", default=POLS)
    r.add_argument("--seeds", default="1-10")
    r.add_argument("--out", required=True)
    z = sub.add_parser("analyze")
    z.add_argument("dir")
    a = ap.parse_args()
    cmd_run(a) if a.cmd == "run" else cmd_analyze(a)


if __name__ == "__main__":
    main()
