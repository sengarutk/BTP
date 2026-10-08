#!/usr/bin/env python3
"""Aggregates the live distributed-pipeline runs (experiments/results/hardware/live/) across repetitions.

For each placement: number of 60 s runs, and median / min / max over runs of delivered frames/s,
on-time (<= 300 ms) frames/s, and the per-run median and p95 capture-to-result latency measured
on the camera device. Output: experiments/results/hardware/live_summary.csv
"""
import csv
import glob
import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np

LIVE = Path(__file__).resolve().parent.parent.parent / "experiments" / "results" / "hardware" / "live"
DESC = {
    "pi_solo": "Pi 5 CPU alone",
    "jetson_solo": "Jetson GPU alone (camera on Jetson)",
    "pi_laptop_jpeg": "Pi JPEG -> laptop",
    "pi_jetson_jpeg": "Pi JPEG -> Jetson",
    "jetson_laptop_jpeg": "Jetson JPEG -> laptop (camera on Jetson)",
    "pi_laptop_k1": "Pi k1 INT8 -> laptop",
    "pi_laptop_k2": "Pi k2 INT8 -> laptop",
    "pi_laptop_k4": "Pi k4 INT8 -> laptop",
    "pi_jetson_k4": "Pi k4 INT8 -> Jetson (detections on Jetson)",
    "tier3_jpeg_relay": "Pi JPEG -> Jetson relay -> laptop",
    "tier3_jpeg_j9": "Pi JPEG -> Jetson k9 INT8 -> laptop",
    "tier3_k4_j9": "Pi k4 INT8 -> Jetson k9 INT8 -> laptop",
}


def main():
    runs = defaultdict(list)
    for f in glob.glob(str(LIVE / "live_*.json")):
        r = json.load(open(f))
        if r["role"] not in ("source", "solo"):
            continue
        name = re.sub(r"_r\d+$", "", r["label"])
        runs[name].append(r)
    rows = []
    for name, rs in runs.items():
        def stat(key):
            v = [x[key] for x in rs if x.get(key) is not None]
            return (float(np.median(v)), float(min(v)), float(max(v))) if v else (float("nan"),) * 3
        fps, ont, p50, p95 = stat("fps_results"), stat("fps_on_time"), stat("lat_p50_ms"), stat("lat_p95_ms")
        rows.append({"placement": name, "description": DESC.get(name, name), "runs": len(rs),
                     "fps_median": round(fps[0], 2), "fps_min": round(fps[1], 2), "fps_max": round(fps[2], 2),
                     "on_time_fps_median": round(ont[0], 2), "on_time_fps_min": round(ont[1], 2),
                     "on_time_fps_max": round(ont[2], 2), "lat_p50_ms_median": round(p50[0], 1),
                     "lat_p95_ms_median": round(p95[0], 1)})
    rows.sort(key=lambda r: -r["on_time_fps_median"])
    out = LIVE.parent / "live_summary.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(f"{r['description']:46s} runs={r['runs']} fps={r['fps_median']:5.2f} [{r['fps_min']:5.2f},{r['fps_max']:5.2f}] "
              f"on-time={r['on_time_fps_median']:5.2f} [{r['on_time_fps_min']:5.2f},{r['on_time_fps_max']:5.2f}] "
              f"p50={r['lat_p50_ms_median']:7.1f} p95={r['lat_p95_ms_median']:7.1f}")


if __name__ == "__main__":
    main()
