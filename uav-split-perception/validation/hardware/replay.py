#!/usr/bin/env python3
"""Trace-driven replay of the live system (publication plan, Phase 1, item 4).

Scores controller and baseline variants offline, with the same scorer as the hardware runs, so that ideas can be
screened (and long missions explored) before spending board time. Everything comes from measurements:
  links      per-frame goodput drawn as consecutive stretches of the live goodput samples of the unimpaired
             static_good runs (vid_campaign_main), so bursts and fades keep their real persistence; netem phases
             of adaptive2.scenario_phases applied as on the Pi: "rate X" caps the goodput at X and the cap persists
             into later phases until another rate is set; "loss 100%" stalls the link for its phase only; a frame
             stuck 1.5 s drops the connection (as adaptive.Path), which comes back 1.2 s after the impairment ends
             (the measured recovery time, docs: Part 13); round trips 4.9 / 2.7 ms; server times as measured
  estimator  the live one: goodput EWMA (alpha 0.15) of transfers > 20 KB, in-flight stall check, 64 KB probes
             on idle paths every 0.8 s, optimistic restart after a reconnect
  onboard    measured live times (YOLOv8n-320 96 ms, YOLOv8s-320 595 ms, YOLOv8s-640 700 ms, with the forecaster
             running), slowed by thermal throttling: x 2400/1568 at 85 C, linearly from 80 C
  power/heat Pi: idle 1.894 W + forecaster 0.294 W + measured J per inference spread over the inference + encode
             J + radio (0.211 + 0.016 r) W while sending; temperature: first-order approach to the measured steady
             fit T = 34.43 + 12.73 P with one time constant, 148.8 s (cool-down fit; the clean heating steps of the
             24-min heat run fit 137-146 s); measured noise (sd 0.07 W). Jetson: idle 4.079 W + J per inference + receive power.
  detections the real detections of every variant on every val frame (variant_dets.py); scored by stream_ap.evaluate
             with forecaster v2, exactly as the live runs (offline camera-motion chain).
The controllers are the formulas of docs/controller_formulas.md (v2, v3, v4, v4.1, v4.2, v5, v5.1 and the
--decay-shape ablations) and the baselines fixed / jsq / aoi_thr / conf_trigger / reward_offload.

usage: replay.py --policy v5 --scenario mission --phase-s 20 --seeds 1-5 [--out DIR]
       replay.py --validate     replay the main campaign's policies and compare with the hardware results
Output: DIR/a2_<scenario>__<policy>__r<seed>.json + _dets.npz (the live run format) and a summary line.
Limits: one camera; no CPU contention between the forecaster and onboard inference beyond the measured times;
link recovery is a fixed 1.2 s; the Jetson never throttles (measured: 61 C at full load).
"""
import argparse
import json
import math
import random
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from adaptive2 import (LAPTOP_EXTRA, ONBOARD_VARIANTS, PATH_VARIANTS, PRIOR_BYTES, PRIOR_REMOTE_MS,  # noqa: E402
                       scenario_phases)

ROOT = HERE.parent.parent
HW = ROOT / "experiments" / "results" / "hardware"
VID = ROOT / "datasets" / "visdrone_vid_640"
PERIOD, D, LATE_MS, W_LATE = 1.0 / 30.0, 300.0, 1000.0, 0.25
RTT = {"laptop": 4.9, "jetson": 2.7}
ONB_MS = {"n320": 96.0, "s320": 595.0, "s640": 700.0}
ENC_MS = {640: 3.5, 480: 2.2, 320: 1.2}
STALL_S, RECOVER_S, PROBE_B = 1.5, 1.2, 65536
T0_C = 70.0   # starting Pi temperature: campaign runs are back to back, measured run-mean temperatures 68-81 C
TAU_HEAT, TAU_COOL, P_SD = 148.8, 148.8, 0.07   # one time constant: heating steps of the 24-min heat run fit 137-146 s

POLICIES = {   # name -> controller settings (the same switches as adaptive2.py)
    "v2": dict(obj="rate"),
    "stream_fc2": dict(obj="stream"),            # v3 + forecaster v2
    "v4": dict(obj="stream", energy=2.8),
    "v41": dict(obj="stream", energy=2.8, fresh=0.95),
    "v42": dict(obj="stream", energy=2.8, edge=0.5),
    "v5": dict(obj="stream", energy=2.8, edge=0.5, heat=75.0),
    "v51": dict(obj="stream", energy=2.8, edge=0.5, heat=75.0, fresh=0.95),
    "v5_flat": dict(obj="stream", energy=2.8, edge=0.5, heat=75.0, shape="flat"),
    "v5_lin": dict(obj="stream", energy=2.8, edge=0.5, heat=75.0, shape="linear"),
    "v5_exp": dict(obj="stream", energy=2.8, edge=0.5, heat=75.0, shape="exp"),
    "v5_nofc": dict(obj="stream", energy=2.8, edge=0.5, heat=75.0, decay="staleness_decay.json"),
    "leaf": dict(obj="stream", energy=2.8, mu_fixed=2.0),
    "fixed_laptop_m640q90": dict(fixed=("laptop", "m640q90")),
    "onboard_n320": dict(fixed=("onboard", "n320")),
    "jsq": dict(base="jsq"), "aoi_thr": dict(base="aoi_thr"),
    "conf_trigger": dict(base="conf_trigger"), "reward_offload": dict(base="reward_offload"),
}


def phi(x):
    return 0.5 * math.erfc(-x / math.sqrt(2))


def load_goodput():
    import glob
    seqs = {"laptop": [], "jetson": []}
    for f in sorted(glob.glob(str(HW / "vid_campaign_main" / "a2_static_good__*__r*.json"))):
        d = json.load(open(f))
        for p in seqs:
            s = [x[1] for x in d["link_goodput_samples"].get(p, [])]
            if len(s) > 50:
                seqs[p].append(np.array(s))
    return seqs


class Link:
    """One path: real goodput stretches, netem impairment, stalls, reconnection, the live estimator."""

    def __init__(self, name, gp, rng, prior_mbps, prior_rem):
        self.name, self.gp, self.rng = name, gp, rng
        self.seq, self.k = None, 0
        self.rate, self.var, self.last_good = prior_mbps, (prior_mbps / 3) ** 2, prior_mbps
        self.up, self.down_until = True, 0.0
        self.busy_until, self.inflight, self.slot_free_at = 0.0, None, 0.0
        self.rtt = RTT[name]
        self.remote = dict(prior_rem)
        self.imp, self.imp_end = None, None
        self.rate_cap = None      # netem keeps a phase's rate limit until a later phase sets another (as on the Pi)
        self.last_probe = -1.0
        self.edge_w = None

    def sample(self):
        if self.seq is None or self.k >= len(self.seq):
            self.seq = self.gp[self.rng.randrange(len(self.gp))]
            self.k = self.rng.randrange(len(self.seq))
        g = float(self.seq[self.k])
        self.k += 1
        return g

    def set_phase(self, imp):
        """Apply a phase as adaptive.tc_phase does: netem 'change' with the phase's arguments only, which resets the
        loss but keeps an earlier rate limit unless the phase sets a new one (verified on the Pi, 12 Oct 2026)."""
        self.imp = imp
        if imp and imp.startswith("rate"):
            self.rate_cap = float(imp.split()[1].replace("mbit", ""))

    def cap(self, t):
        if self.imp and "loss 100%" in self.imp:
            return 0.0
        return self.rate_cap

    def est(self, t):
        r, s = self.rate, math.sqrt(max(self.var, 1e-6))
        if self.inflight is not None:
            t0, n, t_done = self.inflight
            el = t - t0
            if el > 0.05 and el > max(3 * n * 8 / (r * 1e6), 0.3):
                ach = n * min(1.0, el / max(t_done - t0, 1e-6)) * 8 / (el * 1e6) if t_done != float("inf") else 0.0
                r = min(r, ach)
        return max(r, 1e-3), max(s, 0.1 * r)

    def idle(self, t):
        return self.up and self.inflight is None

    def send(self, t, nbytes):
        """Start a transfer at t; returns the time the bytes are acknowledged (inf if the link is cut)."""
        c = self.cap(t)
        g = self.sample()
        if c is not None:
            g = min(g, c)
        t_done = float("inf") if g <= 0 else t + nbytes * 8 / (g * 1e6) + self.rtt / 1e3
        self.inflight = (t, nbytes, t_done)
        return t_done

    def tick(self, t):
        """Advance: finish or stall the in-flight transfer, reconnect after an outage."""
        if not self.up:
            if self.cap(t) == 0.0:                 # still cut: recovery starts only once the impairment ends
                self.down_until = t + RECOVER_S
            elif t >= self.down_until:
                self.up = True
                self.rate = max(self.rate, 0.5 * self.last_good)
            return None
        if self.inflight is None:
            return None
        t0, n, t_done = self.inflight
        if t_done <= t:
            self.inflight = None
            dt = t_done - t0
            if n > 20000:
                mb = n * 8 / (max(dt - self.rtt / 1e3, 0.3 * dt) * 1e6)
                d = mb - self.rate
                self.rate += 0.15 * d
                self.var = 0.85 * (self.var + 0.15 * d * d)
                self.last_good = mb if mb > 0.5 else self.last_good
            return t_done
        if t - t0 > STALL_S:                       # stalled: the live sender drops the connection
            self.inflight, self.up, self.rate = None, False, 1e-3
            self.down_until = t + RECOVER_S
        return None


class Replay:
    def __init__(self, pol, scenario, phase_s, seed, gp, consts, decays, vdets, accs):
        self.cfg = POLICIES[pol]
        self.pol, self.scenario, self.seed = pol, scenario, seed
        # common random numbers: every policy sees the same link draws and the same noise for a given seed (separate
        # streams per path and for power noise), so policies are compared on identical conditions and runs are
        # reproducible (Python's hash() of a string is randomised per process and must not seed anything)
        self.rng = random.Random(seed * 7919 + 17)
        self.phases = scenario_phases(scenario, phase_s, seed)
        self.c, self.vdets, self.acc = consts, vdets, accs
        self.ref = accs["yolov8s_640_raw"]
        dec = decays[self.cfg.get("decay", "staleness_decay_forecast_v2.json")]
        self.lag, self.rat = np.array(dec["lag_ms"], float), np.array(dec["ratio"], float)
        self.links = {p: Link(p, gp[p], random.Random(seed * 7919 + {"laptop": 1, "jetson": 2}[p]),
                              {"laptop": 20.0, "jetson": 12.0}[p], PRIOR_REMOTE_MS[p]) for p in ("laptop", "jetson")}
        seqs = json.load(open(VID / "sequences.json"))
        self.keys = [(sq, i) for sq, n in seqs for i in range(1, n + 1)]
        self.nbytes = {(r, q): float(PRIOR_BYTES[r][q]) for r in PRIOR_BYTES for q in PRIOR_BYTES[r]}

    # ---------------------------------------------------------------- value functions (controller_formulas.md)
    def rho(self, age):
        sh = self.cfg.get("shape", "measured")
        if sh == "flat":
            return 1.0
        if sh == "linear":
            return max(0.0, 1.0 - age / (2 * D))
        if sh == "exp":
            return 0.5 ** (age / D)
        return float(np.interp(age, self.lag, self.rat))

    def H(self, L, T):
        return float(np.mean([self.rho(L + T * f) for f in (0.0, 0.25, 0.5, 0.75, 1.0)]))

    def acc_of(self, model, res, q=None):
        return self.acc[f"{model}_{res}_{'raw' if q is None else 'q%d' % q}"]

    def e_onb(self, v):
        return self.c["pi"]["infer_j"][v]

    def e_off(self, res, q, b, r):
        enc = self.c["pi"]["encode_j"].get(f"{res}q{q}", self.c["pi"]["encode_j"]["640q90"])
        tx = self.c["pi"]["radio_tx_w"]
        r = max(r, 0.2)
        return enc + max(0.0, tx["a"] + tx["b_per_mbps"] * r) * b * 8 / (r * 1e6)

    def e_edge(self, v, b, r):
        j = self.c["jetson"]["infer_j"].get(v.split("q")[0], self.c["jetson"]["infer_j"]["s640"])
        return j + self.c["jetson"].get("radio_rx_w", 0.211) * b * 8 / (max(r, 0.2) * 1e6)

    def cam_price(self):
        return self.mu + self.lam_t

    def path_value(self, p, var, t):
        L_ = self.links[p]
        if not L_.up:
            return -1.0, 0.0
        model, res, q = (dict(PATH_VARIANTS, **(LAPTOP_EXTRA if p == "laptop" else {})))[var]
        r, s = L_.est(t)
        b = self.nbytes[(res, q)]
        te, rem, rtt = ENC_MS[res], L_.remote[model], L_.rtt
        tx = b * 8 / (r * 1e3)
        p_on = phi((r - b * 8 / ((D - te - rem - rtt) * 1e3)) / s) if D - te - rem - rtt > 0 else 0.0
        lb = LATE_MS - te - rem - rtt
        p_late = phi((r - b * 8 / (lb * 1e3)) / s) if lb > 0 else 0.0
        busy = max(tx + rtt, 1000 * PERIOD)
        cf = self.cfg
        if cf["obj"] == "stream":
            L = te + tx + rem + rtt
            v = self.acc_of(model, res, q) / self.ref * self.H(L, busy / max(1, self.n_active)) * p_late
            if "energy" in cf:
                v -= self.cam_price() * self.e_off(res, q, b, r)
            if "edge" in cf and p == "jetson":
                v -= self.mu_e * self.e_edge(var, b, r)
            if "fresh" in cf and self.aoi + L >= D:
                v += self.lam_f * p_on
            return v, p_on
        qv = p_on + W_LATE * max(0.0, p_late - p_on)
        return self.acc_of(model, res, q) / self.ref * qv / (busy / 1e3), p_on

    def onboard_ms(self, var):
        f = 1.0 + max(0.0, min(1.0, (self.temp - 80.0) / 5.0)) * (2400.0 / 1568.0 - 1.0)
        return ONB_MS[var] * f

    def onboard_value(self, var, penalize=True):
        model, res = ONBOARD_VARIANTS[var]
        t = self.onboard_ms(var)
        p_on = 1.0 if t <= D else 0.0
        busy = math.ceil(t / (1000 * PERIOD) - 1e-9) * 1000 * PERIOD
        cf = self.cfg
        if cf["obj"] == "stream":
            v = self.acc_of(model, res) / self.ref * self.H(t, busy / max(1, self.n_active))
            if "energy" in cf and penalize:
                v -= self.cam_price() * self.e_onb(var)
            if "fresh" in cf and self.aoi + t >= D:
                v += self.lam_f * p_on
            return v, p_on
        qv = p_on + W_LATE * ((1.0 if t <= LATE_MS else 0.0) - p_on)
        return self.acc_of(model, res) / self.ref * qv / (busy / 1e3), p_on

    def best(self, srv, t):
        if srv == "onboard":
            vals = {v: self.onboard_value(v) for v in ONBOARD_VARIANTS}
        else:
            vv = dict(PATH_VARIANTS, **(LAPTOP_EXTRA if srv == "laptop" else {}))
            vals = {v: self.path_value(srv, v, t) for v in vv}
        v = max(vals, key=lambda k: vals[k][0])
        return v, vals[v][0], vals[v][1]

    # ---------------------------------------------------------------- baselines
    def baseline(self, t):
        b = self.cfg["base"]
        live = [p for p in self.links if self.links[p].idle(t) and self.links[p].est(t)[0] >= 0.5]
        best_live = max(live, key=lambda p: self.links[p].est(t)[0]) if live else None
        if b == "jsq":
            best, lat = None, float("inf")
            for p, L_ in self.links.items():
                if L_.idle(t):
                    r = max(L_.est(t)[0], 0.05)
                    lt = ENC_MS[640] + self.nbytes[(640, 90)] * 8 / (r * 1e3) + L_.remote["yolov8s"] + L_.rtt
                    if lt < lat:
                        best, lat = (p, "s640q90"), lt
            if self.onb_free <= t and self.onboard_ms("n320") < lat:
                best = ("onboard", "n320")
            return best
        if b == "aoi_thr":
            if self.aoi <= 150.0:
                return None
            if best_live:
                return (best_live, "s640q90")
            if not any(L_.up and L_.est(t)[0] >= 0.5 for L_ in self.links.values()) and self.onb_free <= t:
                return ("onboard", "n320")
            return None
        det = self.last_onboard_det
        want = False
        if det is not None:
            cf = np.sort(det[:, 4])[::-1]
            if b == "conf_trigger":
                want = (cf[:5].mean() if len(cf) else 0.0) < 0.5 or int((cf >= 0.25).sum()) < 3
            else:
                band = cf[(cf >= 0.1) & (cf < 0.5)]
                rw = float((1.0 - band).sum())
                self.rewards = [(t_, x) for t_, x in self.rewards if t - t_ <= 10.0] + [(t, rw)]
                want = rw >= np.quantile([x for _, x in self.rewards], 0.7)
        if want and best_live:
            return (best_live, "s640q90")
        return ("onboard", "n320") if self.onb_free <= t else None

    # ---------------------------------------------------------------- the run
    def run(self, out_dir):
        cf, c = self.cfg, self.c
        self.mu, self.mu_e, self.lam_t, self.lam_f = (cf.get("mu_fixed", 0.0) or 0.0), 0.0, 0.0, 0.0
        self.temp, self.n_active, self.aoi = T0_C, 1, float("inf")
        self.onb_free, self.last_onboard_det, self.rewards, self.exempt_t = 0.0, None, [], -10.0
        bounds = np.cumsum([0] + [ph[3] for ph in self.phases])
        total = bounds[-1]
        frames, pending, results = [], [], {}       # pending: (t_arrive, id, srv, var)
        fresh_hist, p_log, e_j, edge_j, last_dual, temps = [], [], 0.0, 0.0, 0.0, []
        onb_until, onb_power, radio_until = 0.0, 0.0, {}
        n_ticks = int(total / PERIOD)
        for tick in range(n_ticks):
            t = tick * PERIOD
            ph = int(np.searchsorted(bounds, t, side="right") - 1)
            for p, L_ in self.links.items():          # apply the phase's impairment
                if ph != getattr(L_, "phase_idx", None):
                    L_.set_phase(self.phases[ph][1].get(p))
                    L_.phase_idx = ph
                L_.tick(t)
            while pending and pending[0][0] <= t:      # results that have arrived
                ta, fid, srv, var = pending.pop(0)
                results[fid] = ta
                if srv == "onboard":
                    self.last_onboard_det = self.vdets[var][f"{self.keys[fid % len(self.keys)][0]}/{self.keys[fid % len(self.keys)][1]}"]
            if results:
                self.aoi = (t - max(results) * PERIOD) * 1e3
            fresh_hist.append((t, self.aoi <= D))
            # ---- power, temperature, prices (5 Hz in the live logger; here every tick, prices every 1 s)
            p = c["pi"]["idle_w"] + c["pi"]["forecast_w"] + (onb_power if t < onb_until else 0.0)
            for p_, until in radio_until.items():
                if t < until[0]:
                    p += until[1]
            p_meas = p + self.rng.gauss(0.0, P_SD)
            th = c["pi"]["thermal_steady"]
            t_ss = th["intercept_c"] + th["c_per_w"] * p
            tau = TAU_HEAT if t_ss > self.temp else TAU_COOL
            self.temp += (t_ss - self.temp) * (1 - math.exp(-PERIOD / tau))
            temps.append(self.temp)
            e_j += p * PERIOD
            edge_j += c["jetson"]["idle_w"] * PERIOD
            p_log.append((t, p_meas))
            if t - last_dual >= 1.0:
                last_dual = t
                pbar = float(np.mean([x[1] for x in p_log[-30:]]))
                if "energy" in cf and "mu_fixed" not in cf and t - self.exempt_t > 1.0:   # anti-windup
                    self.mu = min(5.0, max(0.0, self.mu + 0.1 * (pbar - cf["energy"])))
                    if self.temp >= (84.0 if "heat" in cf else 78.0):
                        self.mu = max(self.mu, 1.0)
                if "heat" in cf:
                    p10 = float(np.mean([x[1] for x in p_log[-300:]]))
                    t_hat = self.temp + (th["intercept_c"] + th["c_per_w"] * p10 - self.temp) * \
                        (1 - math.exp(-60.0 / TAU_COOL))
                    self.lam_t = min(2.0, max(0.0, self.lam_t + 0.01 * (t_hat - cf["heat"])))
                if "edge" in cf:
                    served = [j for (ts, j) in getattr(self, "edge_served", []) if t - ts <= 5.0]
                    self.mu_e = min(5.0, max(0.0, self.mu_e + 0.1 * (sum(served) / 5.0 - cf["edge"])))
                if "fresh" in cf:
                    win = [f for ts, f in fresh_hist[-150:]]
                    self.lam_f = min(2.0, max(0.0, self.lam_f + 2.0 * (cf["fresh"] - sum(win) / len(win))))
            # ---- decide
            choice = None
            if "fixed" in cf:
                srv, var = cf["fixed"]
                if (srv == "onboard" and self.onb_free <= t) or (srv != "onboard" and self.links[srv].idle(t)):
                    choice = (srv, var)
            elif "base" in cf:
                choice = self.baseline(t)
            else:
                props = {s: self.best(s, t) for s in ("laptop", "jetson", "onboard")}
                self.n_active = sum(1 for s in props if props[s][2] > 0.2) or 1
                if "energy" in cf and not any(props[s][2] > 0.2 for s in self.links) and self.temp < 85.0:
                    self.exempt_t = t
                    vals = {v: self.onboard_value(v, penalize=False) for v in ONBOARD_VARIANTS}
                    bv = max(vals, key=lambda k: vals[k][0])
                    props["onboard"] = (bv, vals[bv][0], vals[bv][1])
                cand = [s for s in props if props[s][1] > 0 and
                        (self.onb_free <= t if s == "onboard" else self.links[s].idle(t))]
                if cand:
                    s = max(cand, key=lambda k: props[k][1])
                    choice = (s, props[s][0])
            # ---- probes on idle paths (64 KB, every 0.8 s, not the chosen one)
            for pn, L_ in self.links.items():
                if L_.idle(t) and t - L_.last_probe > 0.8 and (choice is None or choice[0] != pn):
                    L_.send(t, PROBE_B)
                    L_.last_probe = t
            rec = {"id": tick, "phase": self.phases[ph][0], "frame": list(self.keys[tick % len(self.keys)])}
            if choice is not None:
                srv, var = choice
                if srv == "onboard":
                    dur = self.onboard_ms(var) / 1e3
                    self.onb_free = t + dur
                    onb_until, onb_power = t + dur, c["pi"]["infer_j"][var] / dur
                    pending.append((t + dur, tick, srv, var))
                    rec.update(server=srv, variant=var, res=ONBOARD_VARIANTS[var][1])
                else:
                    model, res, q = (dict(PATH_VARIANTS, **(LAPTOP_EXTRA if srv == "laptop" else {})))[var]
                    L_ = self.links[srv]
                    b = self.nbytes[(res, q)]
                    t_ack = L_.send(t + ENC_MS[res] / 1e3, b)
                    e_j += c["pi"]["encode_j"].get(f"{res}q{q}", 0.006)
                    r_ = L_.est(t)[0]
                    radio_until[srv] = (min(t_ack, t + STALL_S), c["pi"]["radio_tx_w"]["a"] +
                                        c["pi"]["radio_tx_w"]["b_per_mbps"] * r_)
                    rec.update(server=srv, variant=var, res=res)
                    if t_ack != float("inf"):
                        rem = L_.remote[model] * (1 + 0.1 * self.rng.random())
                        pending.append((t_ack + rem / 1e3 + L_.rtt / 2e3, tick, srv, var))
                        if srv == "jetson":
                            ej = self.e_edge(var, b, r_)
                            edge_j += ej
                            self.edge_served = [x for x in getattr(self, "edge_served", []) if t - x[0] <= 5] + [(t, ej)]
                    pending.sort()
            frames.append(rec)
        for f in frames:
            if f["id"] in results:
                f["t_res"] = results[f["id"]]
        name = f"{self.scenario}__{self.pol}__r{self.seed}"
        out_dir.mkdir(parents=True, exist_ok=True)
        dets = {str(f["id"]): self.vdets[f["variant"]][f"{f['frame'][0]}/{f['frame'][1]}"]
                for f in frames if "t_res" in f}
        np.savez_compressed(out_dir / f"a2_{name}_dets.npz", **dets)
        avail = float(np.mean([x[1] for x in fresh_hist]))
        tt = np.array(temps)
        out = {"policy": self.pol, "scenario": self.scenario, "seed": self.seed, "frames": frames,
               "replay": {"pi_w": e_j / total, "edge_w": edge_j / total, "availability": avail,
                          "temp_mean_c": float(tt.mean()), "temp_max_c": float(tt.max()),
                          "hot_share": float((tt >= 80.0).mean()), "duration_s": float(total)}}
        json.dump(out, open(out_dir / f"a2_{name}.json", "w"))
        return out_dir / f"a2_{name}.json", out["replay"]


def load_all():
    c = json.load(open(HW / "energy" / "energy_constants.json"))
    decays = {k: json.load(open(HW / k)) for k in ("staleness_decay_forecast_v2.json", "staleness_decay.json")}
    accs = json.load(open(HW / "variant_accuracy_visdrone.json"))
    vd = {}
    for f in (HW / "variant_dets").glob("*.npz"):
        z = np.load(f)
        vd[f.stem] = {k: z[k] for k in z.files}
    return c, decays, accs, vd


def score(path):
    from stream_ap import evaluate
    labels = json.load(open(VID / "labels.json"))
    fp = json.load(open(HW / "forecast_tuning_v2.json"))["best"]["params"]
    return evaluate(Path(path), labels, "newest", forecast=fp)["sAP"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--policy", nargs="+", default=["v5"])
    ap.add_argument("--scenario", nargs="+", default=["mission"])
    ap.add_argument("--phase-s", type=float, default=20.0)
    ap.add_argument("--seeds", default="1-5")
    ap.add_argument("--out", default=str(HW / "replay"))
    a = ap.parse_args()
    lo, hi = (int(x) for x in a.seeds.split("-"))
    gp = load_goodput()
    c, decays, accs, vd = load_all()
    rows = []
    for sc in a.scenario:
        for seed in range(lo, hi + 1):
            for pol in a.policy:
                path, m = Replay(pol, sc, a.phase_s, seed, gp, c, decays, vd, accs).run(Path(a.out))
                m["sAP"] = score(path)
                rows.append(dict(policy=pol, scenario=sc, seed=seed, **m))
                print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in rows[-1].items()}),
                      flush=True)
    json.dump(rows, open(Path(a.out) / f"replay_summary_{a.phase_s:g}s.json", "w"), indent=1)


if __name__ == "__main__":
    main()
