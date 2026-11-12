#!/usr/bin/env python3
"""Do the logged freshness, heat and edge-energy prices follow the update rules paper 2 states? (12 Nov 2026)

theory_check.py checks the camera energy price mu on every logged update. This checks the other three prices the
paper writes out (Section "Controller"), from the values each run logged, exactly as adaptive2.py computes them:
  lam_F <- min(2, max(0, lam_F + 2 (target - share)))      fresh_log_t_lam_share: (t, lam_F after, share of last 5 s)
  lam_T <- min(2, max(0, lam_T + 0.01 (theta_hat - 75)))   thermal_log_t_lam_pred_meas: (t, lam_T after, theta_hat, theta)
  mu_e  <- min(5, max(0, mu_e + 0.1 (P_extra - B_e)))      mu_edge_log: (t, mu_e after, P_extra, source)
Steps and caps are the code's defaults (the runs do not store their arguments); targets and budgets are logged per run.
The logs are rounded (prices 4 decimals, share 3, theta_hat 2, P_extra 3), so an update counts as following the rule
when it is within the rounding tolerance. Every other update is "unexplained" and listed.
The caps on lam_F and mu_e were added on 13 Oct 2026, 10:47 IST (commit 9c0e9759, "anti-windup"); the campaigns run
before it (PRE_CAP, all of 8-12 Oct) may have run either version: each such run is checked against the capped rule and, if that fails, against the same
rule without the cap, and it must follow one of them on every update (runs_pre_cap counts those that ran uncapped).
usage: python paper2/price_rules_check.py -> experiments/results/hardware/theory_check/price_rules_check.json
"""
import glob
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HW = REPO / "experiments" / "results" / "hardware"
OUT = HW / "theory_check" / "price_rules_check.json"
RULES = {   # log key, step, cap, target or budget key in measured_energy, tolerance from the log's rounding
    "lam_F": ("fresh_log_t_lam_share", 2.0, 2.0, "fresh_target", 2.0 * 0.0005 + 0.0001 + 1e-9),
    "lam_T": ("thermal_log_t_lam_pred_meas", 0.01, 2.0, "thermal_target_c", 0.01 * 0.005 + 0.0001 + 1e-9),
    "mu_e": ("mu_edge_log", 0.1, 5.0, "edge_budget_w", 0.1 * 0.0005 + 0.0001 + 1e-9),
}


PRE_CAP = {"vid_campaign_energy", "vid_campaign_wifi", "vid_campaign_wifi_fc", "vid_campaign_wifi_fc2",
           "vid_campaign_v42", "vid_campaign_main", "vid_campaign_long", "vid_campaign_table"}


def check(log, step, cap, target, tol, sign):
    """sign = +1: price rises when x exceeds the target (heat, edge power); -1: rises when x falls short (freshness)."""
    prev, res = 0.0, {"updates": 0, "plain": 0, "clipped_zero": 0, "capped": 0, "unexplained": []}
    for row in log:
        lam, x = float(row[1]), float(row[2])
        want_raw = prev + step * sign * (x - target)
        want = min(cap, max(0.0, want_raw))
        res["updates"] += 1
        if abs(lam - want) <= tol:
            res["plain" if 0.0 < want_raw < cap else ("clipped_zero" if want_raw <= 0 else "capped")] += 1
        else:
            res["unexplained"].append({"t": row[0], "logged": lam, "rule": round(want, 4), "prev": prev, "x": x})
        prev = lam
    return res


def main():
    out = {"method": __doc__, "prices": {}}
    for name, (key, step, cap, tkey, tol) in RULES.items():
        sign = -1.0 if name == "lam_F" else 1.0
        tot = {"runs_pre_cap": 0, "runs": 0, "updates": 0, "plain": 0, "clipped_zero": 0, "capped": 0, "unexplained": 0,
               "unexplained_runs": [], "campaigns": set()}
        for f in sorted(glob.glob(str(HW / "vid_campaign_*" / "a2_*.json"))):
            try:
                me = json.load(open(f)).get("measured_energy", {})
            except (json.JSONDecodeError, OSError):
                continue
            if "_superseded" in f:
                continue
            log = me.get(key)
            if not log or me.get(tkey) is None:
                continue
            # each run must follow ONE version of the rule from start to end: the capped one, or (only for runs of
            # the campaigns before the cap was committed) the uncapped one
            r = check(log, step, cap, float(me[tkey]), tol, sign)
            if r["unexplained"] and Path(f).parent.name in PRE_CAP and name != "lam_T":
                r2 = check(log, step, float("inf"), float(me[tkey]), tol, sign)
                if len(r2["unexplained"]) < len(r["unexplained"]):
                    r = r2
                    tot["runs_pre_cap"] += 1
            tot["runs"] += 1
            tot["campaigns"].add(Path(f).parent.name)
            for k in ("updates", "plain", "clipped_zero", "capped"):
                tot[k] += r[k]
            if r["unexplained"]:
                tot["unexplained"] += len(r["unexplained"])
                tot["unexplained_runs"].append({"run": str(Path(f).relative_to(HW)), "n": len(r["unexplained"]),
                                                "first": r["unexplained"][:3]})
        tot["campaigns"] = sorted(tot["campaigns"])
        out["prices"][name] = tot
        print(f"{name}: {tot['runs']} runs ({tot['runs_pre_cap']} before the cap) in {len(tot['campaigns'])} campaigns, {tot['updates']} updates: "
              f"plain {tot['plain']}, clipped at 0 {tot['clipped_zero']}, at cap {tot['capped']}, "
              f"unexplained {tot['unexplained']} (in {len(tot['unexplained_runs'])} runs)")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=1)


if __name__ == "__main__":
    main()
