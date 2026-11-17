#!/usr/bin/env python3
"""Item 8a of the laptop strengthening (16 Nov 2026; predictions: docs/laptop_strengthening_predictions_nov16.md):
can the controller's deadline probability p_on be recalibrated from the board logs, and does it hold on new days?

Data: every offloaded frame of the 16 mesh campaigns of 14-16 Nov with a logged prediction (calib_hw.py's frames:
pred.p_on against arrival within 300 ms). Split by the day the run was recorded (the run file's date): fit on
14-15 Nov, test on 16 Nov (held out). Mappings of the logged p_on, fitted on the training days only:
  isotonic   pool-adjacent-violators regression of the outcome on p_on (monotone, no parametric form)
  platt      logistic regression of the outcome on logit(p_on) (two parameters)
  binning    the training days' on-time share in each of 10 equal-width bins of p_on
Reported on the held-out day: ECE (10 equal-width bins, calib_hw.calib_table's definition), Brier score, the reliability
table, overall and per destination (Jetson, laptop), and an isotonic map fitted per destination. Also: the share of held-out frames below p_on 0.5 (the late-path
skip's threshold) whose recalibrated probability is >= 0.5, i.e. the frames a recalibrated skip would keep.
usage: python validation/hardware/calib_recal.py  -> experiments/results/hardware/calibration/calib_recal_nov16.json
"""
import datetime as dt
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from calib_hw import calib_table  # noqa: E402

H = HERE.parent.parent / "experiments" / "results" / "hardware"
CAMPS = ("mesh4 energy_nov relaynoise_nov topology_nov fps_nov heat_nov heat_nov2 plus_nov2 two_nov two_cap final_nov "
         "heat_final dvfs_heat dvfs_short budget_nov fix_nov").split()
TEST_DAY = dt.date(2026, 11, 16)
EPS = 1e-4


def frames():
    rows = []      # (day, server, p_on, on_time)
    for c in CAMPS:
        for f in sorted((H / f"vid_campaign_{c}").glob("a2_*.json")):
            day = dt.date.fromtimestamp(f.stat().st_mtime)
            run = json.load(open(f))
            for fr in run.get("frames", []):
                pr = fr.get("pred")
                if not pr:
                    continue
                lat = fr.get("lat_ms")
                rows.append((day, fr.get("server"), float(pr["p_on"]),
                             float(lat is not None and lat <= run.get("deadline_ms", 300.0))))
    return rows


def pav(x, y):
    """isotonic (non-decreasing) fit of y on x: returns the breakpoints (x, fitted value) for interpolation"""
    o = np.argsort(x, kind="mergesort")
    xs, ys = x[o], y[o]
    ux, idx = np.unique(xs, return_index=True)          # pool ties first
    sums = np.add.reduceat(ys, idx)
    cnts = np.diff(np.r_[idx, len(xs)]).astype(float)
    vals, wts, xl = [], [], []
    for xv, s, n in zip(ux, sums, cnts):
        vals.append(s / n)
        wts.append(n)
        xl.append(xv)
        while len(vals) > 1 and vals[-2] > vals[-1]:
            w = wts[-2] + wts[-1]
            v = (vals[-2] * wts[-2] + vals[-1] * wts[-1]) / w
            vals[-2:], wts[-2:] = [v], [w]
            xl.pop()           # the block keeps its first x
    # each block covers [x_first, next x_first): step function
    return np.array(xl), np.array(vals)


def iso_apply(model, p):
    xl, v = model
    i = np.searchsorted(xl, p, side="right") - 1
    return v[np.clip(i, 0, len(v) - 1)]


def platt_fit(p, y):
    z = np.log(np.clip(p, EPS, 1 - EPS) / (1 - np.clip(p, EPS, 1 - EPS)))

    def nll(a, b):
        u = a * z + b
        return float(np.sum(np.logaddexp(0, u) - y * u))
    a, b = 1.0, 0.0
    for _ in range(200):       # Newton with step halving on the log-likelihood
        q = 1 / (1 + np.exp(-np.clip(a * z + b, -500, 500)))
        g = np.array([np.sum((y - q) * z), np.sum(y - q)])
        w = q * (1 - q) + 1e-12
        Hm = np.array([[np.sum(w * z * z), np.sum(w * z)], [np.sum(w * z), np.sum(w)]])
        step = np.linalg.solve(Hm, g)
        f0, t = nll(a, b), 1.0
        while nll(a + t * step[0], b + t * step[1]) > f0 and t > 1e-8:
            t /= 2
        a, b = a + t * step[0], b + t * step[1]
        if np.abs(t * step).max() < 1e-10:
            break
    return a, b


def platt_apply(m, p):
    z = np.log(np.clip(p, EPS, 1 - EPS) / (1 - np.clip(p, EPS, 1 - EPS)))
    return 1 / (1 + np.exp(-(m[0] * z + m[1])))


def bin_fit(p, y):
    e = np.linspace(0, 1, 11)
    i = np.clip(np.digitize(p, e) - 1, 0, 9)
    return np.array([y[i == k].mean() if (i == k).any() else (e[k] + e[k + 1]) / 2 for k in range(10)])


def bin_apply(m, p):
    return m[np.clip(np.digitize(p, np.linspace(0, 1, 11)) - 1, 0, 9)]


def main():
    rows = frames()
    day = np.array([r[0] for r in rows])
    srv = np.array([r[1] for r in rows])
    p = np.array([r[2] for r in rows])
    y = np.array([r[3] for r in rows])
    tr, te = day < TEST_DAY, day == TEST_DAY
    models = {"isotonic": (pav(p[tr], y[tr]), iso_apply), "platt": (platt_fit(p[tr], y[tr]), platt_apply),
              "binning": (bin_fit(p[tr], y[tr]), bin_apply)}
    out = {"train_days": sorted({str(d) for d in day[tr]}), "test_day": str(TEST_DAY),
           "n_train": int(tr.sum()), "n_test": int(te.sum()), "groups": {}}
    out["platt"] = {"a": models["platt"][0][0], "b": models["platt"][0][1]}
    for g, m in (("all", te), ("jetson", te & (srv == "jetson")), ("laptop", te & (srv == "laptop"))):
        if not m.any():
            continue
        ent = {"raw": calib_table(list(zip(p[m], y[m])))}
        for name, (mod, f) in models.items():
            q = f(mod, p[m])
            ent[name] = calib_table(list(zip(q, y[m])))
            low = p[m] < 0.5
            ent[name]["below_half_raised_to_half"] = float(np.mean(q[low] >= 0.5)) if low.any() else None
        ent["below_half_share"] = float(np.mean(p[m] < 0.5))
        ent["below_half_observed"] = float(y[m][p[m] < 0.5].mean()) if (p[m] < 0.5).any() else None
        out["groups"][g] = ent
        print(f"{g:7s} n {int(m.sum()):9,d}  ECE raw {ent['raw']['ece']:.4f}  " +
              "  ".join(f"{k} {ent[k]['ece']:.4f}" for k in models) +
              f"  | p_on<0.5: {100 * ent['below_half_share']:.1f} % of frames, on time {100 * (ent['below_half_observed'] or 0):.0f} %")
    # per destination: an isotonic map fitted per path on the training days (the late-path skip acts per path)
    out["per_path"] = {}
    for g in ("jetson", "laptop"):
        mt, ms = tr & (srv == g), te & (srv == g)
        mod = pav(p[mt], y[mt])
        q = iso_apply(mod, p[ms])
        tab = calib_table(list(zip(q, y[ms])))
        low = p[ms] < 0.5
        tab["below_half_raised_to_half"] = float(np.mean(q[low] >= 0.5))
        out["per_path"][g] = {"isotonic": tab, "map": {f"{x:.2f}": float(iso_apply(mod, np.array([x]))[0])
                                                       for x in np.linspace(0, 1, 11)}}
        print(f"per-path isotonic {g}: ECE {tab['ece']:.4f}; frames below 0.5 raised to >= 0.5: "
              f"{100 * tab['below_half_raised_to_half']:.0f} %; map {out['per_path'][g]['map']}")
    iso = models["isotonic"][0]
    out["isotonic_map"] = {f"{x:.2f}": float(iso_apply(iso, np.array([x]))[0]) for x in np.linspace(0, 1, 11)}
    print("isotonic map (train days):", out["isotonic_map"])
    json.dump(out, open(H / "calibration" / "calib_recal_nov16.json", "w"), indent=1)


if __name__ == "__main__":
    main()
