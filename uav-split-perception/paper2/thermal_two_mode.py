#!/usr/bin/env python3
"""Item 9 of the laptop strengthening (16 Nov 2026; predictions: docs/laptop_strengthening_predictions_nov16.md):
Theorem 3's overshoot from a two-time-constant thermal model fitted to the board's own logs.

Model (the die on a slower board): T(t) = a + b_s x_s(t) + b_f x_f(t),  with  tau_s x_s' = P - x_s,  tau_f x_f' = P - x_f,
P the Pi's measured power (the 1-s logger, ~0.24 s samples), T its SoC temperature. Steady state: T = a + (b_s + b_f) P.
Fit: on the five 24-min runs with the 78 C guard (heat_nov, v41guard) only; a grid over tau_f (1-60 s) and tau_s
(60-600 s), and for each pair a, b_s, b_f by least squares; the states start at their steady values for the first
power sample and the first temperature.
Bound: when no onboard inference starts at or above theta_g, the die can still rise after the last one starts. With
power at most P_max during an inference of length d, the fast state adds at most
    delta_fast = b_f (P_max - P_off) (1 - exp(-(d + l) / tau_f)) + q
(P_off: power with no onboard work; l: the guard's reading lag, the logger's sample period; q: the sensor's quantisation
step, by which the true temperature can exceed the reading) above the temperature the slow state reaches, so
peak <= theta_g + delta_fast (Theorem 3 (b) with the fast mode). Each run has its own intercept in the fit (the room).
Test (held out): the 76.5 C guard runs (heat_nov2 v41guard765, heat_final v41final): measured peak - 76.5 against
delta_fast, and the model's simulated peak from each run's measured power trace against its measured peak.
usage: python paper2/thermal_two_mode.py -> experiments/results/hardware/theory_check/thermal_two_mode.json
"""
import glob
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
H = ROOT / "experiments" / "results" / "hardware"
FIT = sorted(glob.glob(str(H / "vid_campaign_heat_nov" / "a2_mission__v41guard__r?.json")))
TEST = {76.5: sorted(glob.glob(str(H / "vid_campaign_heat_nov2" / "a2_mission__v41guard765__r?.json")) +
                     glob.glob(str(H / "vid_campaign_heat_final" / "a2_mission__v41final__r?.json"))),
        78.0: FIT}


def load(f):
    me = json.load(open(f))["measured_energy"]
    L = np.array(me["log_t_w_c"], float)
    return L[:, 0], L[:, 1], L[:, 2], json.load(open(f))


def filt(t, P, tau, x0):
    x = np.empty_like(P)
    x[0] = x0
    for i in range(1, len(P)):
        k = 1 - math.exp(-(t[i] - t[i - 1]) / tau)
        x[i] = x[i - 1] + (P[i - 1] - x[i - 1]) * k
    return x


def design(t, P, ts, tf):
    """slow state started from the run's mean power over its first minute (runs start after a cool-down)"""
    p0 = float(P[t <= 60].mean())
    return filt(t, P, ts, p0), filt(t, P, tf, P[0])


def fit(runs):
    best = None
    for tf in (0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4, 5, 7, 10, 15, 20, 30):
        for ts in (60, 80, 100, 120, 150, 180, 220, 270, 330, 400, 500, 600):
            X, Y = [], []
            for i, (t, P, T, _) in enumerate(runs):
                xs, xf = design(t, P, ts, tf)
                # each run its own intercept (room temperature differs between runs), common slopes
                one = np.zeros((len(xs), len(runs)))
                one[:, i] = 1.0
                X.append(np.c_[one, xs, xf])
                Y.append(T)
            X, Y = np.vstack(X), np.concatenate(Y)
            coef, *_ = np.linalg.lstsq(X, Y, rcond=None)
            rmse = float(np.sqrt(np.mean((X @ coef - Y) ** 2)))
            coef = [float(np.mean(coef[:len(runs)])), coef[-2], coef[-1]]
            if best is None or rmse < best["rmse"]:
                best = {"tau_f": tf, "tau_s": ts, "a": coef[0], "b_s": coef[1], "b_f": coef[2], "rmse": rmse}
    return best


def onboard_bursts(run):
    """onboard inferences: their measured durations (lat_ms of onboard frames)"""
    return [f["lat_ms"] for f in run["frames"] if f.get("server") == "onboard" and f.get("lat_ms")]


def main():
    fr = [load(f) for f in FIT]
    m = fit(fr)
    P_all = np.concatenate([P for _, P, _, _ in fr])
    p_max, p_off = float(np.percentile(P_all, 99)), float(np.percentile(P_all, 10))
    d = float(np.percentile([x for *_, r in fr for x in onboard_bursts(r)], 95)) / 1e3
    t0, _, T0, _ = fr[0]
    lag = float(np.median(np.diff(t0)))                       # the logger's sample period: the guard's reading lag
    steps = np.diff(T0)
    q = float(np.min(np.abs(steps[steps != 0])))               # the sensor's quantisation step
    delta = m["b_f"] * (p_max - p_off) * (1 - math.exp(-(d + lag) / m["tau_f"])) + q
    out = {"reading_lag_s": lag, "quantisation_c": q, "fit": m, "p_max_w_p99": p_max, "p_off_w_p10": p_off, "inference_s_p95": d, "delta_fast_c": delta,
           "steady_slope_c_per_w": m["b_s"] + m["b_f"], "runs": {}}
    for g, files in TEST.items():
        for f in files:
            t, P, T, _ = load(f)
            xs, xf = design(t, P, m["tau_s"], m["tau_f"])
            sim = m["a"] + m["b_s"] * xs + m["b_f"] * xf
            # the model's own peak, anchored to the run's measured start (intercept shift: room temperature differs)
            sim += T[t <= 120].mean() - sim[t <= 120].mean()
            out["runs"][Path(f).parent.name + "/" + Path(f).stem] = {
                "guard_c": g, "held_out": g != 78.0, "measured_peak": float(T.max()), "overshoot": float(T.max() - g),
                "bound_peak": g + delta, "bound_holds": bool(T.max() <= g + delta + 1e-9),
                "model_peak": float(sim.max()), "model_rmse": float(np.sqrt(np.mean((sim - T) ** 2)))}
    json.dump(out, open(H / "theory_check" / "thermal_two_mode.json", "w"), indent=1)
    print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in m.items()},
          f"steady {m['b_s'] + m['b_f']:.2f} C/W  P_max {p_max:.2f} P_off {p_off:.2f} d {d:.2f} s  delta_fast {delta:.2f} C")
    for k, v in out["runs"].items():
        print(f"{k:45s} guard {v['guard_c']} peak {v['measured_peak']:.1f} overshoot {v['overshoot']:.1f} "
              f"bound {v['bound_peak']:.1f} {'ok' if v['bound_holds'] else 'EXCEEDED'}  model peak {v['model_peak']:.1f} "
              f"rmse {v['model_rmse']:.2f}")


if __name__ == "__main__":
    main()
