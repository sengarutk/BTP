#!/usr/bin/env python3
"""A published scheduler re-implemented in the replay: AccuMO-style model-predictive offloading (29 Oct 2026).

AccuMO (Kong, Xu, Meng, Hu; MobiCom 2023; docs/novelty_check_phase0.md) predicts how the accuracy of the last result
drops with time since its frame was captured, from content (its K1: the drop rate depends on camera angular
velocity), and plans offloading with model-predictive control over a 30-frame horizon to maximise the predicted
accuracy over that horizon. It prices neither energy nor heat. Re-implemented here for our system, on the replay
(replay.py, validated against the 240-run main campaign; nothing in it is changed):
  accuracy model  the measured decay of stale results with forecaster v2, conditioned on content as AccuMO does: the
                  curve of the camera ego-motion tertile of the current frame (decay_context_train.json, v2, cuts
                  fixed on train; ego speed from the val camera-motion chain, decay_context.ego_speed, live-computable)
  plan            one setting (or nothing) per server for the whole horizon: laptop 8+1, Jetson 6+1, onboard 3+1 =
                  252 plans. A server with setting v starts as soon as it is free and repeats every busy(v) (a path:
                  the transfer; onboard: the inference time, current throttling included), its results arriving after
                  the expected latency (path: encode + transfer at the live goodput estimate + server time + round
                  trips; settings whose transfer would stall the link are excluded). Results already in flight and the
                  one on screen are part of every plan.
  objective       sum over the next H = 30 frames of A(shown)/A_ref x rho(age of shown), where shown = the newest
                  captured result that has arrived by that frame (what the display holds)
  action          receding horizon: each tick the best plan is found and, of its servers that are idle now, the one
                  whose removal would cost the plan most is started (the harness sends at most one frame per tick, as
                  on the Pi); the plan is recomputed next tick
Variants:
  accumo          as above (AccuMO-style: content-conditioned decay, no energy or heat)
  accumo_global   the global forecaster-v2 curve (the one v4.1 uses): separates the content conditioning
  accumo_energy   accumo minus v4.1's energy price (same dual update, 2.8 W target) on each planned onboard
                  inference and transfer: separates planning from greedy choice, with the pricing held equal
Differences from AccuMO, unavoidable here: one task (detection), not several; the decay is measured per ego-motion
tertile rather than predicted by a learned model; goodput is the live EWMA estimate the other controllers use.

usage: replay_accumo.py run --policy accumo v41 ... --scenario mission --seeds 1-5 --out DIR
       replay_accumo.py analyze DIR      -> DIR/accumo_summary.json
"""
import argparse
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import replay as R  # noqa: E402
import replay_oracle as O  # noqa: E402  (registers v41_clair and the fixed policies)
from adaptive2 import LAPTOP_EXTRA, ONBOARD_VARIANTS, PATH_VARIANTS  # noqa: E402
from decay_context import EGO_STEPS, ego_speed  # noqa: E402,F401
from report_rescore import t975  # noqa: E402

H = 30
R.POLICIES["accumo"] = dict(base="accumo", ctx=True)
R.POLICIES["accumo_global"] = dict(base="accumo")
R.POLICIES["accumo_energy"] = dict(base="accumo", ctx=True, energy=2.8)
SERVERS = ("laptop", "jetson", "onboard")
OPTS = {"laptop": list(dict(PATH_VARIANTS, **LAPTOP_EXTRA)), "jetson": list(PATH_VARIANTS),
        "onboard": list(ONBOARD_VARIANTS)}


class AccuMOReplay(O.OracleReplay):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        dc = json.load(open(R.HW / "decay_context_train.json"))
        self.ctx_lag = np.array(dc["lags_ms"], float)
        self.ctx_rat = {k: np.array(dc["ratio"]["v2"][f"ego{k}"], float) for k in range(3)}
        self.ego_cuts = dc["cuts"]["ego"]
        z = np.load(R.VID / "egomotion.npz")
        self.chains = {k: z[k] for k in z.files}
        self.sent = {}                       # tick -> (srv, var, A/A_ref, expected arrival s, expected server-free s)
        self.plan_ms = []

    def tertile(self, tick):
        sq, i = self.keys[tick % len(self.keys)]
        e = ego_speed(self.chains[sq], i, 640, 360)
        return int(np.searchsorted(self.ego_cuts, e, side="right"))

    def baseline(self, t):
        if self.cfg["base"] != "accumo":
            return super().baseline(t)
        t0 = time.perf_counter()
        ch = self.plan(t)
        self.plan_ms.append((time.perf_counter() - t0) * 1e3)
        return ch

    # ---------------------------------------------------------------- the planner
    def option(self, srv, var, t):
        """(latency s, repeat period s, A/A_ref, energy J) of one setting, or None if unusable now."""
        if srv == "onboard":
            model, res = ONBOARD_VARIANTS[var]
            ms = self.onboard_ms(var)
            per = math.ceil(ms / (1000 * R.PERIOD) - 1e-9) * R.PERIOD
            return ms / 1e3, per, self.acc_of(model, res) / self.ref, self.e_onb(var)
        L_ = self.links[srv]
        if not L_.up:
            return None
        model, res, q = (dict(PATH_VARIANTS, **(LAPTOP_EXTRA if srv == "laptop" else {})))[var]
        r = L_.est(t)[0]
        b = self.nbytes[(res, q)]
        tx = b * 8 / (r * 1e6)
        if tx + L_.rtt / 1e3 > R.STALL_S:
            return None
        lat = R.ENC_MS[res] / 1e3 + tx + (L_.remote[model] * O.REM_MEAN + 1.5 * L_.rtt) / 1e3
        return lat, max(tx + L_.rtt / 1e3, R.PERIOD), self.acc_of(model, res, q) / self.ref, self.e_off(res, q, b, r)

    def plan(self, t):
        tick = int(round(t / R.PERIOD))
        if "ctx" in self.cfg:
            lag, rat = self.ctx_lag, self.ctx_rat[self.tertile(tick)]
        else:
            lag, rat = self.lag, self.rat
        fut = tick + np.arange(1, H + 1)                       # the frames of the horizon (ticks)
        # what is on screen and in flight: captures newer than the shown one that have not been shown yet
        shown = tick - self.aoi / 1e3 / R.PERIOD if math.isfinite(self.aoi) else -1e9
        shown = int(round(shown))
        # keep the shown result and those in flight; drop sends lost with a cut link (overdue by a stall time)
        self.sent = {k: v for k, v in self.sent.items() if k == shown or (k > shown and t - v[3] < R.STALL_S)}
        self.sent = {k: v for k, v in self.sent.items() if k == shown or v[0] == "onboard" or self.links[v[0]].up}
        base_cap = np.full(H, -1e9)
        base_acc = np.zeros(H)
        if shown in self.sent:
            base_cap[:] = shown
            base_acc[:] = self.sent[shown][2]
        for k, (srv, var, a, t_arr, _, t_send, rest) in sorted(self.sent.items()):
            if k <= shown:
                continue
            if srv != "onboard":                     # re-predict with the live estimator (its in-flight stall check)
                L_ = self.links[srv]
                if not L_.up:
                    continue                         # the link dropped: the result is lost
                if L_.inflight is not None and abs(L_.inflight[0] - t_send) < 1e-9:
                    t_arr = t_send + L_.inflight[1] * 8 / (max(L_.est(t)[0], 1e-3) * 1e6) + rest
            # overdue: the longer it is late, the later it is expected (soon beyond the horizon, i.e. given up)
            arr = (t_arr if t_arr > t else t + max(R.PERIOD, t - t_arr)) / R.PERIOD
            m = fut >= arr
            base_cap[m], base_acc[m] = k, a                    # sorted by capture: a newer one overrides
        free = {"onboard": max(self.onb_free, t)}
        for p in self.links:
            if self.links[p].idle(t):
                free[p] = t
            else:
                fr = [v[4] for v in self.sent.values() if v[0] == p and v[4] > t]
                free[p] = max(fr) if fr else t + R.PERIOD
        # per server and setting: the newest captured result of that server shown by each future frame
        caps, accs, costs, meta = [], [], [], []
        price = self.cam_price() if "energy" in self.cfg else 0.0
        if price and all(self.option(p, v, t) is None for p in self.links for v in OPTS[p]):
            price, self.exempt_t = 0.0, t      # as v4.1: onboard is not priced while no path is usable (anti-windup)
        for srv in SERVERS:
            c_l, a_l, e_l, m_l = [np.full(H, -1e9)], [np.zeros(H)], [0.0], [None]
            for var in OPTS[srv]:
                o = self.option(srv, var, t)
                if o is None:
                    continue
                lat, per, a, e = o
                starts = free[srv] + per * np.arange(0, int(H * R.PERIOD / per) + 2)
                starts = starts[starts < t + H * R.PERIOD]
                cap_k = np.ceil(starts / R.PERIOD - 1e-9)       # a send uses the newest frame at its start
                arr_k = (starts + lat) / R.PERIOD
                c = np.full(H, -1e9)
                for ck, ak in zip(cap_k, arr_k):
                    c[fut >= ak] = ck
                c_l.append(c)
                a_l.append(np.where(c > -1e8, a, 0.0))
                e_l.append(price * e * len(starts))
                m_l.append(var)
            caps.append(np.array(c_l))
            accs.append(np.array(a_l))
            costs.append(np.array(e_l))
            meta.append(m_l)
        # all 252 combinations at once: shown result per frame = the newest capture among the servers and the base
        C = np.stack(np.broadcast_arrays(caps[0][:, None, None, :], caps[1][None, :, None, :],
                                         caps[2][None, None, :, :], base_cap[None, None, None, :]))
        A = np.stack(np.broadcast_arrays(accs[0][:, None, None, :], accs[1][None, :, None, :],
                                         accs[2][None, None, :, :], base_acc[None, None, None, :]))
        w = np.argmax(C, axis=0)
        cw = np.take_along_axis(C, w[None], 0)[0]
        aw = np.take_along_axis(A, w[None], 0)[0]
        age_ms = np.where(cw > -1e8, (fut - cw) * R.PERIOD * 1e3, 1e9)
        val = (aw * np.interp(age_ms, lag, rat, right=0.0)).sum(-1) / H
        val = val - (costs[0][:, None, None] + costs[1][None, :, None] + costs[2][None, None, :]) / H
        best = np.unravel_index(int(np.argmax(val)), val.shape)
        # start one of the plan's servers that are idle now: the one whose removal would cost the plan most
        idle = {"laptop": self.links["laptop"].idle(t), "jetson": self.links["jetson"].idle(t),
                "onboard": self.onb_free <= t}
        cand = []
        for i, srv in enumerate(SERVERS):
            if best[i] == 0 or not idle[srv]:
                continue
            alt = list(best)
            alt[i] = 0
            cand.append((float(val[best] - val[tuple(alt)]), srv, meta[i][best[i]]))
        if not cand:
            return None
        _, srv, var = max(cand)
        lat, per, a, _ = self.option(srv, var, t)
        if srv == "onboard":
            self.sent[tick] = (srv, var, a, t + lat, t + lat, t, 0.0)
        else:                                  # the path is free again once the transfer is acknowledged
            model, res, q = dict(PATH_VARIANTS, **LAPTOP_EXTRA)[var]
            t_send = t + R.ENC_MS[res] / 1e3
            L_ = self.links[srv]
            rest = (L_.remote[model] * O.REM_MEAN + 1.5 * L_.rtt) / 1e3     # after the bytes are through
            self.sent[tick] = (srv, var, a, t + lat, t_send + per, t_send, rest)
        return srv, var


def cmd_run(a):
    from stream_ap import evaluate
    R.NETEM_LEGACY = a.netem == "legacy"
    R.ONB_POWER = getattr(a, "onboard_power", "energy")
    lo, hi = (int(x) for x in a.seeds.split("-"))
    gp = R.load_goodput()
    c, decays, accs, vd = R.load_all()
    labels = json.load(open(R.VID / "labels.json"))
    fp = json.load(open(R.HW / "forecast_tuning_v2.json"))["best"]["params"]
    out = Path(a.out)
    (out / "rows").mkdir(parents=True, exist_ok=True)
    for sc in a.scenario:
        for seed in range(lo, hi + 1):
            for pol in a.policy:
                row_f = out / "rows" / f"{sc}_{a.phase_s:g}s__{pol}__r{seed}.json"
                if row_f.exists():
                    continue
                rp = AccuMOReplay(pol, sc, a.phase_s, seed, gp, c, decays, vd, accs)
                path, m = rp.run(out / "runs")
                ev = evaluate(path, labels, "newest", forecast=fp, extras=True)
                run = json.load(open(path))
                use = defaultdict(int)
                for f in run["frames"]:
                    if f.get("server"):
                        use[f["server"]] += 1
                row = dict(policy=pol, scenario=sc, phase_s=a.phase_s, seed=seed, netem=a.netem,
                           onboard_power=R.ONB_POWER, **m,
                           **{k: ev[k] for k in ("sAP", "fresh_AP", "per_phase_sAP", "age_p95_ms", "longest_stale_s",
                                                 "fresh_share")},
                           sends=dict(use), n_frames=len(run["frames"]))
                if rp.plan_ms:
                    row["plan_ms_median"] = float(np.median(rp.plan_ms))
                    row["plan_ms_p95"] = float(np.percentile(rp.plan_ms, 95))
                json.dump(row, open(row_f, "w"))
                print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()
                                  if k != "per_phase_sAP"}), flush=True)


def paired(d):
    d = np.array(d, float)
    h = t975(len(d) - 1) * d.std(ddof=1) / math.sqrt(len(d)) if len(d) > 1 else float("nan")
    return {"mean": float(d.mean()), "ci95": float(h), "n": len(d), "wins": int((d > 0).sum())}


def cmd_analyze(a):
    rows = [json.load(open(f)) for f in sorted(Path(a.dir).glob("rows/*.json"))]
    by = defaultdict(dict)
    for r in rows:
        by[(r["scenario"], r["phase_s"], r["seed"])][r["policy"]] = r
    out = {}
    for sc, ps in sorted({k[:2] for k in by}):
        allk = sorted(k for k in by if k[:2] == (sc, ps))
        pols = sorted(set().union(*[set(by[k]) for k in allk]))
        ent = {"seeds": [k[2] for k in allk], "policies": {}}
        for p in pols:                         # each policy on the seeds it shares with v41 (extra seeds: some only)
            keys = [k for k in allk if p in by[k] and "v41" in by[k]]
            rs = [by[k][p] for k in keys]
            ent["policies"][p] = {m: float(np.mean([r[m] for r in rs])) for m in
                                  ("sAP", "fresh_AP", "pi_w", "hot_share", "temp_max_c", "fresh_share", "age_p95_ms")}
            ent["policies"][p]["send_share"] = {s: float(np.mean([r["sends"].get(s, 0) / r["n_frames"] for r in rs]))
                                                for s in SERVERS}
            ent["policies"][p]["seeds"] = [k[2] for k in keys]
            if "plan_ms_median" in rs[0]:
                ent["policies"][p]["plan_ms_median"] = float(np.median([r["plan_ms_median"] for r in rs]))
            if p != "v41" and "v41" in pols:
                ent["policies"][p]["v41_minus"] = paired([by[k]["v41"]["sAP"] - by[k][p]["sAP"] for k in keys])
        out[f"{sc}_{ps:g}s"] = ent
    json.dump(out, open(Path(a.dir) / "accumo_summary.json", "w"), indent=1)
    for sc, ent in out.items():
        print(sc, "seeds", ent["seeds"])
        for p, v in sorted(ent["policies"].items(), key=lambda x: -x[1]["sAP"]):
            d = v.get("v41_minus")
            print(f"  {p:22s} sAP {v['sAP']:.4f}  Pi {v['pi_w']:.2f} W  hot {100 * v['hot_share']:4.0f} %  "
                  f"Tmax {v['temp_max_c']:.1f}  fresh {100 * v['fresh_share']:.1f} %  onboard "
                  f"{100 * v['send_share']['onboard']:.1f} %" +
                  (f"  v41 - this {d['mean']:+.4f} ± {d['ci95']:.4f} (v41 ahead {d['wins']}/{d['n']})" if d else
                   f"  n {len(v['seeds'])}"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--policy", nargs="+", default=["v41", "accumo", "accumo_global", "accumo_energy"])
    r.add_argument("--scenario", nargs="+", default=["mission"])
    r.add_argument("--phase-s", type=float, default=20.0)
    r.add_argument("--seeds", default="1-5")
    r.add_argument("--netem", default="reset", choices=["reset", "legacy"])
    r.add_argument("--onboard-power", default="energy", choices=["energy", "power"],
                   help="replay.ONB_POWER: energy reproduces 19.10; power is the corrected model of 19.11")
    r.add_argument("--out", required=True)
    z = sub.add_parser("analyze")
    z.add_argument("dir")
    a = ap.parse_args()
    cmd_run(a) if a.cmd == "run" else cmd_analyze(a)


if __name__ == "__main__":
    main()
