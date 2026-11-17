#!/usr/bin/env python3
"""Item 1a of the laptop strengthening (16 Nov 2026; predictions: docs/laptop_strengthening_predictions_nov16.md):
paper 1's timing model (validation/hardware/t10_predict.py, committed before the T10 sweep) against every measured
cell of the sweep on the Pi (6 options x 6 goodputs, netem-serialised link; token-bucket runs excluded).
Predicted on-time rate = fps * p_on of the prediction; measured = on_time_fps of each sweep run (mean over runs).
Best option: the highest accuracy-weighted on-time rate (U), predicted and measured.
usage: python evaluation/t10_model_check.py -> experiments/results/hardware/t10/t10_model_check.json
"""
import glob
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

T10 = Path(__file__).resolve().parent.parent / "experiments" / "results" / "hardware" / "t10"


def main():
    pr = json.load(open(T10 / "t10_prediction.json"))
    meas = defaultdict(list)
    for f in glob.glob(str(T10 / "sweep" / "*.json")):
        if f.endswith("__htb.json"):
            continue
        d = json.load(open(f))
        meas[(float(d["rate_mbit"]), d["option"])].append(d["on_time_fps"])
    O = pr["options"]
    cells, best = [], {}
    for (r, o), v in sorted(meas.items()):
        p = pr["by_rate"].get(f"{r:g}") or pr["by_rate"].get(str(r))
        pred = p[o]["fps"] * p[o]["p_on"]
        m = float(np.mean(v))
        cells.append({"rate": r, "option": o, "pred_on_time_fps": pred, "meas_on_time_fps": m, "runs": len(v)})
    for r in sorted({c["rate"] for c in cells}):
        cs = [c for c in cells if c["rate"] == r]
        w = {c["option"]: O[c["option"]]["map50_95"] / O[c["option"]]["base_map50_95"] for c in cs}
        bp = max(cs, key=lambda c: c["pred_on_time_fps"] * w[c["option"]])["option"]
        bm = max(cs, key=lambda c: c["meas_on_time_fps"] * w[c["option"]])["option"]
        best[r] = {"predicted": bp, "measured": bm, "match": bp == bm}
    big = [c for c in cells if max(c["pred_on_time_fps"], c["meas_on_time_fps"]) >= 1.0]
    rel = [abs(c["pred_on_time_fps"] - c["meas_on_time_fps"]) / max(c["meas_on_time_fps"], 1e-9) for c in big]
    ab = [abs(c["pred_on_time_fps"] - c["meas_on_time_fps"]) for c in cells]
    pm = np.array([[c["pred_on_time_fps"], c["meas_on_time_fps"]] for c in cells])
    out = {"cells": cells, "best": {f"{k:g}": v for k, v in best.items()},
           "n_cells": len(cells), "n_cells_ge1": len(big),
           "median_abs_rel_err_ge1": float(np.median(rel)), "p90_abs_rel_err_ge1": float(np.percentile(rel, 90)),
           "median_abs_err_fps": float(np.median(ab)), "max_abs_err_fps": float(np.max(ab)),
           "pearson_r": float(np.corrcoef(pm[:, 0], pm[:, 1])[0, 1]),
           "best_match": sum(v["match"] for v in best.values()), "rates": len(best)}
    json.dump(out, open(T10 / "t10_model_check.json", "w"), indent=1)
    for c in cells:
        print(f"{c['rate']:5g} {c['option']:15s} pred {c['pred_on_time_fps']:6.2f}  meas {c['meas_on_time_fps']:6.2f}")
    print({k: v for k, v in out.items() if k not in ("cells",)})


if __name__ == "__main__":
    main()
