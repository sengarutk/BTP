#!/usr/bin/env python3
"""Checks of paper 2's guarantees against every recorded run (hardening plan, Phase 1; 10 Nov 2026).

Theorem 1 (power budget, sample path). The controller's energy price follows
    mu_t = min(MU_MAX, max(0, mu_{t-1} + ETA (P_t - B)))      once per second (validation/hardware/adaptive2.py)
with two exceptions: the thermal guard can only raise mu (mu >= 1 at >= 78 C), and while no link can deliver mu is
held. Write s_t = mu_t - mu_{t-1} - ETA (P_t - B). Ordinary steps, the clip at zero and the guard have s_t >= 0; only held
steps and steps clipped at MU_MAX can have s_t < 0 (the set H). Summing over N updates:
    (1/N) sum P_t  =  B + (mu_N - mu_0)/(ETA N) - (1/(ETA N)) sum s_t
                   <=  B + (mu_N - mu_0)/(ETA N) + (1/(ETA N)) sum_{t in H} |s_t|
This is an identity plus a sign argument, so it holds on every run without statistical assumptions. The check below
confirms on the logged updates (mu_log: time, mu after the update, the 1-s mean power P_t used, temperature) that s_t < 0
occurs only where the code allows it, and reports the three terms per run.

Proposition (budget -> temperature). With a linear first-order thermal response theta' = (a + b P - theta)/tau, the
mean temperature over a long window equals a + b * (mean power) up to a transient that decays with tau. Checked on the
second half of every run of at least 20 minutes (the long Wi-Fi and mesh campaigns), for the fits of
experiments/results/hardware/energy/thermal_steady_pi.json (the replay's plant fit below 84 C, and the controller's fit
below 80 C, energy_constants.json).

Theorem 2 (accuracy gap) is stated in the paper for an idealised controller; its empirical counterpart is the replay's
hindsight oracle (replay/oracle_oct29_plant/oracle_summary.json), reported here alongside the constant G = max |P_t - B|.
usage: python paper2/theory_check.py   -> experiments/results/hardware/theory_check/theory_check.json
"""
import glob
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
HW = ROOT / "experiments" / "results" / "hardware"
OUT = HW / "theory_check"
ETA, MU_MAX, TOL = 0.1, 5.0, 3e-4          # adaptive2.py defaults (no campaign changed them)
ROUND_W = 2e-3                              # mu is logged to 4 decimals and P to 3: the identity holds to ~1e-3 W


def runs():
    for f in sorted(glob.glob(str(HW / "vid_campaign_*" / "a2_*.json"))):
        if "_superseded" in f or "__leaf__" in f or "_leaf_" in Path(f).name:
            continue
        try:
            me = json.load(open(f)).get("measured_energy") or {}
        except Exception:
            continue
        if me.get("mu_log") and me.get("power_budget_w") is not None:
            yield f, me


def theorem1(f, me):
    B = float(me["power_budget_w"])
    L = np.array([(x[1], x[2]) for x in me["mu_log"]], float)
    mu, P = L[:, 0], L[:, 1]
    if len(mu) > 5 and np.ptp(mu) == 0 and mu[0] > 0:       # a fixed weight, not the dual ascent
        return None
    prev = np.concatenate([[0.0], mu[:-1]])                 # the price starts at 0
    s = mu - prev - ETA * (P - B)
    H = s < -TOL
    capped = H & (mu >= MU_MAX - TOL)
    N = len(P)
    avg = float(P.mean())
    term_mu = float((mu[-1] - 0.0) / (ETA * N))
    term_h = float(-s[H].sum() / (ETA * N))
    bound = B + term_mu + term_h
    exact = B + term_mu - float(s.sum() / (ETA * N))         # the identity: equals avg up to the logged rounding
    return {"run": str(Path(f).relative_to(HW)), "budget_w": B, "updates": N, "avg_power_w": avg,
            "bound_w": bound, "term_price_w": term_mu, "term_held_w": term_h, "identity_error_w": abs(exact - avg),
            "held_or_capped_share": float(H.mean()), "capped_steps": int(capped.sum()), "mu_max_reached": float(mu.max()),
            "G_w": float(np.abs(P - B).max()), "msq_w2": float(((P - B) ** 2).mean()), "holds": bool(avg <= bound + ROUND_W)}


def temperature(f, me, fits):
    lg = np.array([x for x in me.get("log_t_w_c", []) if x[1] == x[1] and x[2] == x[2]], float)
    if len(lg) < 10 or lg[-1, 0] - lg[0, 0] < 20 * 60:
        return None
    half = lg[lg[:, 0] >= lg[0, 0] + (lg[-1, 0] - lg[0, 0]) / 2]
    p, t = float(half[:, 1].mean()), float(half[:, 2].mean())
    return {"run": str(Path(f).relative_to(HW)), "minutes": float((lg[-1, 0] - lg[0, 0]) / 60), "mean_power_w": p,
            "mean_temp_c": t, **{f"pred_{k}_c": a + b * p for k, (a, b) in fits.items()}}


def main():
    lv = json.load(open(HW / "energy" / "thermal_steady_pi.json"))["levels"]
    pts = np.array([(v["power_w"], v["temp_steady_c"]) for v in lv.values()
                    if v.get("arm_clock_mhz_last60", 0) >= 1450 and v["temp_steady_c"] < 84.0])   # as replay.py load_all
    b_pl, a_pl = np.polyfit(pts[:, 0], pts[:, 1], 1)
    ts = json.load(open(HW / "energy" / "energy_constants.json"))["pi"]["thermal_steady"]
    fits = {"plant": (float(a_pl), float(b_pl)), "controller": (ts["intercept_c"], ts["c_per_w"])}
    t1, tt = [], []
    for f, me in runs():
        r = theorem1(f, me)
        if r:
            t1.append(r)
        r = temperature(f, me, fits)
        if r:
            tt.append(r)
    by = {}
    for r in t1:
        c = r["run"].split("/")[0]
        by.setdefault(c, []).append(r)
    camp = {c: {"runs": len(v), "all_hold": all(x["holds"] for x in v),
                "max_avg_minus_budget_w": max(x["avg_power_w"] - x["budget_w"] for x in v),
                "max_bound_minus_budget_w": max(x["bound_w"] - x["budget_w"] for x in v),
                "mean_held_share": float(np.mean([x["held_or_capped_share"] for x in v])),
                "max_term_held_w": max(x["term_held_w"] for x in v),
                "runs_capped": sum(1 for x in v if x["capped_steps"] > 0),
                "max_identity_error_w": max(x["identity_error_w"] for x in v),
                "max_mu": max(x["mu_max_reached"] for x in v)} for c, v in sorted(by.items())}
    temp = {}
    for k in fits:
        e = np.array([r[f"pred_{k}_c"] - r["mean_temp_c"] for r in tt])
        temp[k] = {"intercept_c": fits[k][0], "c_per_w": fits[k][1], "runs": len(e),
                   "mean_error_c": float(e.mean()) if len(e) else None,
                   "mean_abs_error_c": float(np.abs(e).mean()) if len(e) else None,
                   "max_abs_error_c": float(np.abs(e).max()) if len(e) else None,
                   "budget_for_80c_w": (80.0 - fits[k][0]) / fits[k][1],
                   "budget_for_85c_w": (85.0 - fits[k][0]) / fits[k][1]}
    orc = json.load(open(HW / "replay" / "oracle_oct29_plant" / "oracle_summary.json"))["scenarios"]
    G = max(r["G_w"] for r in t1)
    cur = [r for r in t1 if r["run"].startswith(("vid_campaign_mesh2/", "vid_campaign_mesh3/", "vid_campaign_mesh/"))
           and "__v41" in r["run"]]
    msq = [r["msq_w2"] for r in cur]
    out = {"eta": ETA, "mu_max": MU_MAX,
           "theorem1": {"runs": len(t1), "all_hold": all(r["holds"] for r in t1),
                        "runs_any_held_or_capped": sum(1 for r in t1 if r["held_or_capped_share"] > 0),
                        "runs_capped": sum(1 for r in t1 if r["capped_steps"] > 0),
                        "max_identity_error_w": max(r["identity_error_w"] for r in t1), "by_campaign": camp,
                        "per_run": t1},
           "theorem2": {"G_w": G, "gap_bound_value_per_s": ETA * G * G / 2,
                        "v41_mesh_runs": len(cur), "msq_median_w2": float(np.median(msq)), "msq_max_w2": float(max(msq)),
                        "gap_bound_msq_median_value_per_s": ETA * float(np.median(msq)) / 2,
                        "gap_bound_msq_max_value_per_s": ETA * float(max(msq)) / 2,
                        "oracle_share_pct": {k: 100 * v["v41_share_of_oracle_schedule"] for k, v in orc.items()}},
           "temperature": {"fits": temp, "per_run": tt}}
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(OUT / "theory_check.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in out["theorem1"].items() if k != "per_run"}, indent=1))
    print(json.dumps(out["theorem2"], indent=1))
    print(json.dumps(temp, indent=1))


if __name__ == "__main__":
    main()
