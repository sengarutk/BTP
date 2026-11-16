#!/usr/bin/env python3
"""Paper 1's second detector (YOLO11s) on the Pi with MEASURED onboard times (16 Nov 2026; Y.1-Y.2).
Options from evaluation/second_detector.configs(); for the Pi device only, every option's onboard time is set to its
measured time (host processing chosen so the rule's formula returns it): the four YOLO11s codes from the Pi bench
(experiments/results/hardware/t11/y11_bench_camera2.json; prefix + encoder + uint8 + zstd), JPEG from the Pi benches
(Q50 from the same bench, Q20/Q35/Q90 from T10; other qualities = laptop encode x the median Pi/laptop ratio of
those). Output: experiments/results/second_detector/yolo11s/break_even_pi_measured.json (break_even.json untouched)."""
import json, sys
from dataclasses import replace
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from evaluation import break_even_rule as b      # noqa: E402
from evaluation import second_detector as sd     # noqa: E402

HW = REPO / "experiments" / "results" / "hardware"


def main():
    jpeg, others, devs, hf11, extra, prof = sd.configs()
    pi, t_pi = next((d, t) for d, t in devs if d.startswith("Pi"))
    scale = t_pi / hf11
    y11 = json.load(open(HW / "t11" / "y11_bench_camera2.json"))["options"]
    t10 = json.load(open(HW / "t10" / "t10_bench_camera2.json"))["options"]
    meas_j = {"jpeg_q50": y11["jpeg_q50"]["onboard_ms_median"]} | {q: t10[q]["onboard_ms_median"] for q in ("jpeg_q20", "jpeg_q35", "jpeg_q90")}
    lap = {c.name: c.host_edge_proc_ms for c in jpeg}
    ratio = float(np.median([meas_j[q] / lap[q] for q in meas_j if lap.get(q)]))
    at = lambda c, ms: max(0.0, (ms - t_pi * c.edge_flop_frac) / scale)      # noqa: E731
    jpeg_m = [replace(c, host_edge_proc_ms=at(c, meas_j.get(c.name, lap[c.name] * ratio))) for c in jpeg]
    oth_m = []
    for c in others:
        tag = c.name.replace("learned_", "y11:")
        oth_m.append(replace(c, host_edge_proc_ms=at(c, y11[tag]["onboard_ms_median"])) if tag in y11 else c)
    rows, viol, checked, wins = b.analyse(jpeg_m, oth_m, devs=[(pi, t_pi)], hfull=hf11)
    old = {r["code"]: r for r in json.load(open(sd.OUT / "break_even.json"))["rows"] if r["device"] == pi}
    out = {"device": pi, "t_full_ms": t_pi, "scale": scale, "jpeg_pi_over_laptop": ratio, "wins_total": wins,
           "violations": len(viol),
           "rows": [{"code": r["code"], "onboard_ms_measured": r["onboard_ms"], "onboard_ms_rule": old[r["code"]]["onboard_ms"],
                     "b_be_mbps_measured": r["b_be_mbps"], "b_be_mbps_rule": old[r["code"]]["b_be_mbps"],
                     "max_win_measured": r["max_win_mbps"], "max_win_rule": old[r["code"]]["max_win_mbps"]} for r in rows]}
    json.dump(out, open(sd.OUT / "break_even_pi_measured.json", "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
