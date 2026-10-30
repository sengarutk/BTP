#!/usr/bin/env python3
"""Time the camera-motion step of the live forecaster on this machine at several tracking widths (brief 19.9: 160 px
keeps 98 % of the forecaster's gain at about 0.57x the laptop cost; the Pi's figure is what this measures).

For each width, the frames of the first clips of a VisDrone-VID folder are converted (egomotion.small_grey's resize +
grey) and stepped pair by pair (egomotion.step: corners, Lucas-Kanade, RANSAC), as live_forecast_tick does per frame.
Widths are timed in interleaved order, reps times, single-threaded OpenCV (as in adaptive2.py). Frames are read before
the timing. Runs on a board's flat ~/hwbench copy or in the repo.

usage: egomotion_bench.py VID_DIR [--widths 320 160] [--frames 300] [--reps 3] [--out FILE.json]
"""
import argparse
import json
import os
import platform
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import egomotion as E  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("vid")
    ap.add_argument("--widths", type=int, nargs="+", default=[320, 160])
    ap.add_argument("--frames", type=int, default=300)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    cv2.setNumThreads(1)
    seqs = json.load(open(os.path.join(a.vid, "sequences.json")))
    imgs = []
    for sq, n in seqs:
        for i in range(1, n + 1):
            if len(imgs) >= a.frames:
                break
            imgs.append((sq, cv2.imread(os.path.join(a.vid, sq, "%07d.jpg" % i))))
    t = {w: [] for w in a.widths}
    for _ in range(a.reps):
        for w in a.widths:
            E.W_SMALL = w                            # small_grey reads the module constant at call time
            ms, prev = [], None
            for sq, img in imgs:
                t0 = time.perf_counter()
                g, sc = E.small_grey(img)
                if prev is not None and prev[0] == sq:
                    E.step(prev[1], g, sc)
                ms.append((time.perf_counter() - t0) * 1e3)
                prev = (sq, g)
            t[w].append(float(np.mean(ms[1:])))
    base = float(np.median(t[a.widths[0]]))
    res = {"host": platform.node(), "machine": platform.machine(), "frames": len(imgs), "reps": a.reps,
           "widths": {str(w): {"ms_per_frame_median": float(np.median(v)), "runs": v,
                               "cost_vs_first": float(np.median(v)) / base} for w, v in t.items()}}
    print(json.dumps(res, indent=1))
    if a.out:
        json.dump(res, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
