#!/usr/bin/env python3
"""Recompute the inputs of two prices from each run's own logs (13 Nov 2026). price_rules_check.py checks that
every price update follows its rule GIVEN its logged input; this checks the inputs themselves.
  heat price (v5, v5.1, heat): the 60-s prediction  T_hat = T + (a + b * P_10s - T) * (1 - exp(-60 / tau)),
      P_10s = mean of the logged board power over the last 10 s, tau = 148.83 s; computed with both thermal fits:
      34.43 + 12.73 P (Results Brief Part 16: the fit the v5 runs used) and 37.26 + 11.31 P (the corrected fit).
  Jetson price (v4.2, v5, v5.1): P_extra = measured Jetson power - 4.079 W idle, on the runs that log the Jetson's
      power reports (edge_w_log).
usage: python paper2/price_input_checks.py -> experiments/results/hardware/theory_check/price_input_checks.json
"""
import glob
import json
import math
from pathlib import Path

import numpy as np

HW = Path(__file__).resolve().parent.parent / "experiments" / "results" / "hardware"
FITS = {"part16_34.43+12.73P": (34.43, 12.73), "corrected_37.26+11.31P": (37.258256766379546, 11.312856542249014)}
TAU, IDLE = 148.8346237016964, 4.079200329896906


def main():
    heat = {k: [] for k in FITS}
    edge, n_meas, n_model, runs_h, runs_e = [], 0, 0, 0, 0
    for f in sorted(glob.glob(str(HW / "vid_campaign_*" / "a2_*.json"))):
        if "_superseded" in f:
            continue
        me = json.load(open(f)).get("measured_energy") or {}
        tl, pl = me.get("thermal_log_t_lam_pred_meas"), me.get("log_t_w_c")
        if tl and pl:
            runs_h += 1
            p = np.array([(x[0], x[1]) for x in pl if x[1] == x[1]], float)
            for t, _, that, tp in tl:
                w = p[(p[:, 0] > t - 10) & (p[:, 0] <= t)]
                if len(w):
                    for k, (a, b) in FITS.items():
                        heat[k].append(abs(tp + (a + b * w[:, 1].mean() - tp) * (1 - math.exp(-60 / TAU)) - that))
        ml, ew = me.get("mu_edge_log"), me.get("edge_w_log")
        if ml:
            n_meas += sum(1 for r in ml if r[3] == "measured")
            n_model += sum(1 for r in ml if r[3] != "measured")
        if ml and ew:
            runs_e += 1
            ew = np.array(ew, float)
            for t, _, px, src in ml:
                j = np.searchsorted(ew[:, 0], t, side="right") - 1
                if src == "measured" and j >= 0 and t - ew[j, 0] <= 2.0:
                    edge.append(abs(max(0.0, ew[j, 1] - IDLE) - px))
    out = {"method": __doc__, "heat": {"runs": runs_h}, "edge": {"runs_with_power_log": runs_e,
           "updates_measured": n_meas, "updates_modelled": n_model}}
    for k, v in heat.items():
        v = np.array(v)
        out["heat"][k] = {"predictions": int(len(v)), "median_abs_c": float(np.median(v)),
                          "p95_abs_c": float(np.percentile(v, 95)), "share_within_0.05c": float(np.mean(v < 0.05))}
    e = np.array(edge)
    out["edge"].update({"checked": int(len(e)), "median_abs_w": float(np.median(e)), "p95_abs_w": float(np.percentile(e, 95)),
                        "share_within_0.01w": float(np.mean(e < 0.01))})
    (HW / "theory_check").mkdir(parents=True, exist_ok=True)
    json.dump(out, open(HW / "theory_check" / "price_input_checks.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "method"}, indent=1))


if __name__ == "__main__":
    main()
