#!/usr/bin/env python3
"""Item 10 of the laptop strengthening (16 Nov 2026; predictions: docs/laptop_strengthening_predictions_nov16.md):
the overload model (overload_handling.py, grid committed 13 Nov, before the pull bench of 15 Nov) against the measured
two-host pull bench (pull_nov_fair: 1-8 JPEG streams on two camera Pis, one Jetson, one channel), then extrapolated
(model only) to 12 and 16 streams, i.e. 3-4 camera hosts with 4 streams each. Model case: mesh_jetson.
usage: python validation/hardware/pull_model_check.py -> experiments/results/hardware/overload_handling/pull_model_check.json
"""
import glob
import json
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import overload_handling as OH  # noqa: E402
import overload_model as M  # noqa: E402

H = HERE.parent.parent / "experiments" / "results" / "hardware"


def main():
    grid = json.load(open(H / "overload_handling" / "summary.json"))["grid"]
    meas = {}
    for f in glob.glob(str(H / "pull_nov_fair" / "*.jsonl")):
        mo, n, r = re.match(r"(pull1|v41)_s(\d)_r(\d)_", Path(f).name).groups()
        last = [json.loads(l) for l in open(f) if "on_time_total" in l][-1]
        meas.setdefault((mo, int(n), r), 0.0)
        meas[(mo, int(n), r)] += last["on_time_total"]
    rows = []
    for mo in ("v41", "pull1"):
        for n in (1, 2, 4, 6, 8):
            m = [v for (a, b, _), v in meas.items() if a == mo and b == n]
            pred = grid[f"mesh_jetson|{n}|{mo}"]["on_time_fps_total"]
            rows.append({"method": mo, "streams": n, "model_on_time_fps": pred, "measured": m,
                         "measured_mean": float(np.mean(m)), "rel_err": (pred - np.mean(m)) / np.mean(m)})
    inp = M.inputs()
    c = inp["cases"]["mesh_jetson"]
    cap = 1000.0 / max(s[1] for s in c["stages"])
    extra = {f"{mo}|{n}": OH.cell(("mesh_jetson", n, mo, c["stages"], inp["encode_ms"], inp["sigma_encode"], cap))[1]
             for mo in ("v41", "pull1") for n in (12, 16)}
    ratio = float(np.mean([r["measured_mean"] / r["model_on_time_fps"] for r in rows if r["method"] == "pull1"]))
    out = {"rows": rows, "extrapolation_model": extra, "pull1_measured_over_model": ratio,
           "pull1_extrapolated_scaled": {n: extra[f"pull1|{n}"]["on_time_fps_total"] * ratio for n in (12, 16)}}
    json.dump(out, open(H / "overload_handling" / "pull_model_check.json", "w"), indent=1)
    for r in rows:
        print(f"{r['method']:6s} {r['streams']} model {r['model_on_time_fps']:5.1f} measured {r['measured_mean']:5.1f} "
              f"({', '.join(f'{x:.1f}' for x in r['measured'])}) err {100 * r['rel_err']:+.0f} %")
    print("extrapolation (model):", {k: round(v["on_time_fps_total"], 1) for k, v in extra.items()},
          "pull1 measured/model", round(ratio, 3))


if __name__ == "__main__":
    main()
