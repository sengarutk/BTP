#!/usr/bin/env python3
"""A cheaper camera-motion tracker for the live forecaster: what does it cost in accuracy? (29 Oct 2026)

The live forecaster slows the Pi's onboard inference (Part 9) and most of its time is the camera-motion step
(egomotion.step: Shi-Tomasi corners + pyramidal Lucas-Kanade + RANSAC on the frame downscaled to 320 px, every
frame). Variants of that step, everything else (forecaster v2 settings, detections) unchanged:
  base      320 px wide, up to 200 corners, every frame (what runs on the Pi)
  w240/w160 smaller tracking image
  c100/c50  fewer corners
  skip2     one step every second frame, over two frames (the odd frames keep the last transform)
  w160_skip2, w240_c100   combinations
Accuracy: forecast.replay (one result every 2 frames, shown LAG frames late, the setting of forecast_tuning_v2.json)
on VisDrone-VID train (forecast_train_dets.npz, where the forecaster was tuned; the choice is made here) and val
(forecast_val_dets.npz, the live test clips; reported). Cost: mean time of the step on this laptop, relative to
base (the Pi's absolute time differs; the ratio is a guide, the Pi measurement is still needed).
Nothing existing is changed: chains are computed here and injected into forecast's cache.
usage: forecast_cheap.py          -> experiments/results/hardware/forecast_cheap_oct29.json
       forecast_cheap.py --time   -> forecast_cheap_oct29_timing.json (timing only, run on an idle machine)
"""
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import forecast as F  # noqa: E402
from egomotion import small_grey  # noqa: E402

ROOT = HERE.parent.parent
DS = {"train": ROOT / "datasets" / "visdrone_vid_train_640", "val": ROOT / "datasets" / "visdrone_vid_640"}
DETS = {"train": F.OUT / "forecast_train_dets.npz", "val": F.OUT / "forecast_val_dets.npz"}
VARIANTS = {"base": (320, 200, 1), "w240": (240, 200, 1), "w160": (160, 200, 1), "c100": (320, 100, 1),
            "c50": (320, 50, 1), "skip2": (320, 200, 2), "w160_skip2": (160, 200, 2), "w240_c100": (240, 100, 1)}
N_MAX = F.MAX_FRAMES


def grey(img, w):
    s = w / img.shape[1]
    return cv2.cvtColor(cv2.resize(img, (w, round(img.shape[0] * s)), interpolation=cv2.INTER_AREA),
                        cv2.COLOR_BGR2GRAY), 1.0 / s


def step(prev, cur, scale, corners, min_dist):
    """egomotion.step with the corner budget as a parameter (base: identical to egomotion.step)."""
    pts = cv2.goodFeaturesToTrack(prev, maxCorners=corners, qualityLevel=0.01, minDistance=min_dist, blockSize=7)
    if pts is None or len(pts) < 12:
        return np.eye(3)
    nxt, st, _ = cv2.calcOpticalFlowPyrLK(prev, cur, pts, None, winSize=(21, 21), maxLevel=3)
    ok = st.ravel() == 1
    if ok.sum() < 12:
        return np.eye(3)
    A, inl = cv2.estimateAffinePartial2D(pts[ok], nxt[ok], method=cv2.RANSAC, ransacReprojThreshold=1.0,
                                         maxIters=500, confidence=0.99)
    if A is None or inl is None or inl.sum() < 10:
        return np.eye(3)
    S = np.eye(3)
    S[:2] = A
    D = np.diag([scale, scale, 1.0])
    return D @ S @ np.linalg.inv(D)


def chains(split, w, corners, every):
    """Cumulative transforms per sequence (as egomotion.chain_sequence) and the per-step times (ms)."""
    seqs = json.load(open(DS[split] / "sequences.json"))
    out, ms = {}, []
    md = max(2, round(8 * w / 320))                  # minimum corner distance scales with the image
    for sq, n in seqs:
        n = min(n, N_MAX)
        C = np.zeros((n + 1, 3, 3))
        C[1] = np.eye(3)
        prev_i = 1
        prev, scale = grey(cv2.imread(str(DS[split] / sq / ("%07d.jpg" % 1))), w)
        for k in range(2, n + 1):
            if (k - 1) % every:                      # skipped frame: keep the last transform
                C[k] = C[k - 1]
                continue
            img = cv2.imread(str(DS[split] / sq / ("%07d.jpg" % k)))
            t0 = time.perf_counter()
            cur, _ = grey(img, w)
            S = step(prev, cur, scale, corners, md)
            ms.append((time.perf_counter() - t0) * 1e3)
            C[k] = S @ C[prev_i]
            prev, prev_i = cur, k
        out[sq] = C
    return out, ms


def main():
    cv2.setNumThreads(1)
    params = json.load(open(F.OUT / "forecast_tuning_v2.json"))["best"]["params"]
    res = {"forecaster": params, "lags_ms": [round(x * 1000 / 30, 1) for x in F.LAGS], "variants": {}}
    data = {s: ({k: v for k, v in np.load(DETS[s]).items()}, json.load(open(DS[s] / "labels.json")),
                json.load(open(DS[s] / "sequences.json"))) for s in DS}
    # check: the base variant must reproduce the stored chains (egomotion.npz) on the frames used
    for name, (w, c, e) in VARIANTS.items():
        row = {"width": w, "corners": c, "every": e}
        for split in DS:
            ch, ms = chains(split, w, c, e)
            if name == "base":
                z = np.load(DS[split] / "egomotion.npz")
                row[f"{split}_max_diff_vs_stored"] = float(max(np.abs(ch[k][1:] - z[k][1:len(ch[k])]).max() for k in ch))
            F._CHAINS[F.TRAIN] = ch                  # forecast.replay reads the chains from this cache
            dets, labels, seqs = data[split]
            ap = {lag: float(F.replay(params, lag, dets, labels, seqs)) for lag in F.LAGS}
            row[split] = {"ap": ap, "mean_ap_lagged": float(np.mean([ap[x] for x in F.LAGS[1:]])),
                          "step_ms_per_frame": float(np.sum(ms) / sum(min(n, N_MAX) - 1 for _, n in seqs))}
            print(name, split, {k: round(v, 4) for k, v in ap.items()}, f"{row[split]['step_ms_per_frame']:.2f} ms/frame",
                  flush=True)
        res["variants"][name] = row
    nf = {s: {lag: float(F.replay(None, lag, *data[s])) for lag in F.LAGS} for s in DS}
    res["no_forecast"] = {s: {"ap": nf[s], "mean_ap_lagged": float(np.mean([nf[s][x] for x in F.LAGS[1:]]))} for s in DS}
    b = res["variants"]["base"]
    for name, row in res["variants"].items():
        for s in DS:
            row[s]["vs_base_mean_ap_lagged"] = row[s]["mean_ap_lagged"] - b[s]["mean_ap_lagged"]
            row[s]["cost_vs_base"] = row[s]["step_ms_per_frame"] / b[s]["step_ms_per_frame"]
            g = b[s]["mean_ap_lagged"] - res["no_forecast"][s]["mean_ap_lagged"]
            row[s]["share_of_forecaster_gain_kept"] = (row[s]["mean_ap_lagged"] - res["no_forecast"][s]["mean_ap_lagged"]) / g
    json.dump(res, open(F.OUT / "forecast_cheap_oct29.json", "w"), indent=1)
    print("base vs stored chains:", {s: b[f"{s}_max_diff_vs_stored"] for s in DS})
    for name, row in res["variants"].items():
        print(f"{name:11s} " + "  ".join(
            f"{s}: lagged AP {row[s]['mean_ap_lagged']:.4f} ({row[s]['vs_base_mean_ap_lagged']:+.4f}, keeps "
            f"{100 * row[s]['share_of_forecaster_gain_kept']:.0f} % of the gain) cost x{row[s]['cost_vs_base']:.2f}"
            for s in DS))


def time_only(reps=3):
    """Step time per frame on the val clips, each variant timed reps times in interleaved order (run on an idle
    machine; the times in main() were taken beside other jobs) -> forecast_cheap_oct29_timing.json."""
    cv2.setNumThreads(1)
    t = {k: [] for k in VARIANTS}
    nfr = sum(min(n, N_MAX) - 1 for _, n in json.load(open(DS["val"] / "sequences.json")))
    for _ in range(reps):
        for name, (w, c, e) in VARIANTS.items():
            t[name].append(float(np.sum(chains("val", w, c, e)[1]) / nfr))
    res = {k: {"ms_per_frame_median": float(np.median(v)), "runs": v,
               "cost_vs_base": float(np.median(v) / np.median(t["base"]))} for k, v in t.items()}
    json.dump(res, open(F.OUT / "forecast_cheap_oct29_timing.json", "w"), indent=1)
    for k, v in res.items():
        print(f"{k:11s} {v['ms_per_frame_median']:.2f} ms/frame  x{v['cost_vs_base']:.2f}")


if __name__ == "__main__":
    time_only() if "--time" in sys.argv else main()
