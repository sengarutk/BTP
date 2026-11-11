#!/usr/bin/env python3
"""Theorem 3 of paper 2 (hard thermal guard, roadmap P2-1, 11 Nov 2026): its constants on the hardware, and the check
on every replay run with the hard guard.

Model (Proposition prop:temp): d theta/dt = (a + b P - theta) / tau. Split the board's power into P = P_n + P_i, with
P_i >= 0 the extra power of onboard inference, and let theta_n be the temperature the model gives with P_n alone.
  (a) theta(t) >= theta_n(t) for every schedule (inference only adds heat).
  (b) If no inference starts while theta >= theta_g, each inference lasts at most e with P_i <= Pi_hat, theta_lo <=
      theta_n <= theta_f, P_n <= P_hat and H = a + b P_hat > theta_g, then
          theta(t) <= theta_g + d_i + d_n,   d_i = b Pi_hat (1 - exp(-e / tau)),
                                             d_n = (theta_f - theta_lo) (H - theta_g) / (H - theta_lo).
      d_i: the inference already running when the guard trips; d_n: radio bursts (P_n above its mean) after it.
  (c) A room warmer by D shifts theta_n, theta_lo, theta_f and H by D. By (a) no controller keeps theta below theta_g
      once theta_f + D > theta_g; by (b) the guard keeps theta below theta_max as long as
      theta_g + d_i + (theta_f - theta_lo)(H + D - theta_g)/(H - theta_lo) <= theta_max.

Hardware constants: the controller's fit (energy_constants pi.thermal_steady), its tau; theta_g = 78 C (the guard of
v4.1); P_idle, the s640 inference energy and time (energy_constants); the Pi's throttled full-model time
(placements_summary) as e; the floor from the 62 offload-only hardware runs (fixed_laptop_m640q90, no onboard
inference): P_hat = their largest 1-s mean power; theta_f = the highest temperature of their 24-min runs after the
first 2 tau (the floor's own peak; the 2-min runs start at whatever the previous run left, up to 76 C, so the
theorem's start condition theta(0) <= theta_f is stated, not assumed); the 24-min runs' second-half mean temperature
for the converse margin; theta_lo = a + b P_idle.
Replay: its plant (thermal_plant), its floor P_n >= idle + forecaster (theta_lo), P_hat = idle + forecaster + the
radio model at the largest goodput of the replayed traces on both links, theta_f(D) = the highest temperature of the
offload-only replay runs at that room temperature (th_floor_amb*); every th_guard_amb* run is checked against (b).
usage: guard_theorem.py      -> experiments/results/hardware/theory_check/guard_theorem.json
"""
import glob
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
HW = ROOT / "experiments" / "results" / "hardware"
SWEEP = HW / "replay" / "theory_sweep_nov11"
OUT = HW / "theory_check" / "guard_theorem.json"
THETA_G, THROTTLE, HOT = 78.0, 85.0, 80.0


def bound(theta_g, d_i, theta_f, theta_lo, H):
    d_n = (theta_f - theta_lo) * (H - theta_g) / (H - theta_lo) if H > theta_g else 0.0
    return theta_g + d_i + d_n, d_n


def margin(theta_g, d_i, theta_f, theta_lo, H, theta_max):
    """Largest room-temperature rise D with theta_g + d_i + (theta_f - theta_lo)(H + D - theta_g)/(H - theta_lo) <=
    theta_max (the bound is linear in D)."""
    return (theta_max - theta_g - d_i) * (H - theta_lo) / (theta_f - theta_lo) - (H - theta_g)


def hardware(c):
    th = c["pi"]["thermal_steady"]
    a, b, tau = th["intercept_c"], th["c_per_w"], c["pi"]["thermal"]["tau_s"]
    p_idle = c["pi"]["idle_w"]
    p_inf = c["pi"]["infer_j"]["s640"] / (c["pi"]["infer_ms"]["s640"] / 1e3)
    e_s = json.load(open(HW / "placements_summary.json"))["devices"]["pi"]["full_ms"] / 1e3
    p1, tmax, long_mean, late_max, runs = [], [], [], [], 0
    for f in sorted(glob.glob(str(HW / "vid_campaign_*" / "a2_*__fixed_laptop_m640q90__*.json"))):
        if "_superseded" in f:
            continue
        me = json.load(open(f)).get("measured_energy") or {}
        lg = np.array([x for x in me.get("log_t_w_c", []) if x[1] == x[1] and x[2] == x[2]], float)
        if len(lg) < 20:
            continue
        runs += 1
        t = lg[:, 0] - lg[0, 0]
        k = np.floor(t).astype(int)
        p1 += [lg[k == j, 1].mean() for j in np.unique(k)]
        tmax.append(float(lg[:, 2].max()))
        if t[-1] >= 20 * 60:
            long_mean.append(float(lg[t >= t[-1] / 2, 2].mean()))
            late_max.append(float(lg[t >= 2 * tau, 2].max()))   # the floor's own peak, after the start transient
    p_hat, theta_f = float(max(p1)), float(max(late_max))
    theta_lo, H = a + b * p_idle, a + b * p_hat
    d_i = b * p_inf * (1 - math.exp(-e_s / tau))
    B, d_n = bound(THETA_G, d_i, theta_f, theta_lo, H)
    return {"a": a, "b": b, "tau_s": tau, "theta_g": THETA_G, "p_idle_w": p_idle, "p_inf_w": p_inf, "e_s": e_s,
            "floor_runs": runs, "floor_p1s_mean_w": float(np.mean(p1)), "p_hat_w": p_hat, "theta_f_c": theta_f,
            "floor_long_runs": len(late_max), "floor_max_any_c": float(max(tmax)),
            "floor_long_mean_c": long_mean, "theta_lo_c": theta_lo, "H_c": H, "d_i_c": d_i, "d_n_c": d_n,
            "bound_lab_c": B, "margin_throttle_c": margin(THETA_G, d_i, theta_f, theta_lo, H, THROTTLE),
            "margin_hot_c": margin(THETA_G, d_i, theta_f, theta_lo, H, HOT),
            "converse_margin_max_c": THETA_G - theta_f,
            "converse_margin_mean_c": THETA_G - max(long_mean) if long_mean else None}


def replay(c):
    sys.path.insert(0, str(ROOT / "validation" / "hardware"))
    import replay as R
    cc = next(x for x in R.load_all() if isinstance(x, dict) and "pi" in x)
    pl = cc["pi"]["thermal_plant"]
    a, b = pl["intercept_c"], pl["c_per_w"]
    tau = R.TAU_COOL
    gp = R.load_goodput()
    rmax = {p: float(max(s.max() for s in v)) for p, v in gp.items()}
    tx = cc["pi"]["radio_tx_w"]
    p_base = cc["pi"]["idle_w"] + cc["pi"]["forecast_w"]
    p_hat = p_base + sum(tx["a"] + tx["b_per_mbps"] * r for r in rmax.values())
    p_inf = max(cc["pi"]["infer_j"][v] / (cc["pi"]["infer_ms"][v] / 1e3) for v in cc["pi"]["infer_ms"])
    e_s = max(cc["pi"]["infer_ms"].values()) / 1e3
    rows = [json.load(open(f)) for f in sorted(glob.glob(str(SWEEP / "rows" / "*.json")))]
    floor, guard = {}, []
    for r in rows:
        p = r["policy"]
        if p.startswith("th_floor_amb"):
            floor.setdefault(float(p[len("th_floor_amb"):]), []).append(r)
    out = {"a": a, "b": b, "tau_s": tau, "rmax_mbps": rmax, "p_base_w": p_base, "p_hat_w": p_hat,
           "p_inf_w": p_inf, "e_s": e_s, "d_i_c": b * p_inf * (1 - math.exp(-e_s / tau)), "ambient": {}}
    for D, rs in sorted(floor.items()):
        theta_f = max(x["temp_max_c"] for x in rs)
        theta_lo, H = a + D + b * p_base, a + D + b * p_hat
        B, d_n = bound(THETA_G, out["d_i_c"], theta_f, theta_lo, H)
        g = [x for x in rows if x["policy"] == f"th_guard_amb{D:g}"]
        out["ambient"][f"{D:g}"] = {
            "floor_runs": len(rs), "theta_f_c": theta_f, "floor_mean_c": float(np.mean([x["temp_mean_c"] for x in rs])),
            "theta_lo_c": theta_lo, "H_c": H, "d_n_c": d_n, "bound_c": B, "guard_runs": len(g),
            "guard_temp_max_c": max((x["temp_max_c"] for x in g), default=None),
            "guard_hot_share_mean": float(np.mean([x["hot_share"] for x in g])) if g else None,
            "bound_holds_all": all(x["temp_max_c"] <= B + 1e-9 for x in g) if g else None,
            "floor_below_guard": theta_f <= THETA_G}
        guard += g
    out["guard_runs"] = len(guard)
    return out


def main():
    c = json.load(open(HW / "energy" / "energy_constants.json"))
    res = {"method": __doc__.split("\n\n")[1], "hardware": hardware(c), "replay": replay(c)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=1)
    print(json.dumps(res["hardware"], indent=1))
    print(json.dumps({k: v for k, v in res["replay"].items() if k != "ambient"}, indent=1))
    for D, v in res["replay"]["ambient"].items():
        print(D, {k: (round(x, 3) if isinstance(x, float) else x) for k, x in v.items()})


if __name__ == "__main__":
    main()
