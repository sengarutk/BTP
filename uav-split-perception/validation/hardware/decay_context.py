#!/usr/bin/env python3
"""Staleness decay of aerial detections, conditioned on context (publication plan, Phase 1).

forecast.py measures one global decay curve rho(age) per forecaster. This script asks whether the decay
depends on the situation the drone is in, using only context a drone can compute live at the moment it
decides (the capture frame c), never the future:
  ego    camera ego-motion speed, px/s: mean displacement of the image under the last 5 per-frame steps of the
         camera-motion chain (egomotion.npz, what forecaster v2 already computes on the Pi)
  crowd  number of confident detections (conf >= 0.25) in the result for frame c
  small  share of those detections smaller than 20 px (sqrt of box area, 640-px frame)
Each feature is cut into tertiles on VisDrone-VID TRAIN (thresholds stored and reused unchanged on val).
Separately, the decay by OBJECT SIZE: ground truth and predictions filtered to one size class (sqrt area
< 16 / 16-32 / > 32 px), the usual small/medium/large split applied to this 640-px aerial footage.

Protocol (as forecast.py decay): one result every STRIDE frames; the result for capture c is shown exactly LAG
frames later and scored against the ground truth of frame c + LAG; the same captures (c + max lag <= n) for
every lag, so every lag scores the same frames. Forecasters: none, v1 (forecast_tuning.json), v2
(forecast_tuning_v2.json), frozen as tuned on train. ratio = AP(lag, forecaster, stratum) / AP(0, none, stratum).

usage:
  decay_context.py dets val     YOLOv8s@640 CPU detections of the val sequences (as forecast.py dets on train)
  decay_context.py run train|val
  decay_context.py compare      does the per-stratum train curve predict val better than the global curve?
Output: experiments/results/hardware/decay_context_{train,val}.json, decay_context_compare.json
"""
import json
import multiprocessing as mp
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from forecast import MAX_FRAMES, STRIDE, TUNING, TUNING2, _make  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "experiments" / "results" / "hardware"
DS = {"train": ROOT / "datasets" / "visdrone_vid_train_640", "val": ROOT / "datasets" / "visdrone_vid_640"}
DETS = {"train": OUT / "forecast_train_dets.npz", "val": OUT / "forecast_val_dets.npz"}
LAGS = [0, 1, 2, 3, 5, 8, 12, 18, 25, 35]
FEATURES = ["ego", "crowd", "small"]
SIZES = {"small": (0, 16), "medium": (16, 32), "large": (32, 1e9)}
CONF_CTX, SMALL_PX, EGO_STEPS = 0.25, 20.0, 5


def _sz(b):
    return np.sqrt(np.clip((b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1]), 0, None))


def ego_speed(C, c, w, h):
    """Mean displacement (px/s at 30 fps) of 5 image points under the last EGO_STEPS camera steps up to c."""
    pts = np.array([[w / 2, h / 2, 1], [0, 0, 1], [w, 0, 1], [0, h, 1], [w, h, 1]], float).T
    d = []
    for k in range(max(2, c - EGO_STEPS + 1), c + 1):
        S = C[k] @ np.linalg.inv(C[k - 1])
        q = S @ pts
        d.append(np.mean(np.hypot(q[0] - pts[0], q[1] - pts[1])))
    return float(np.mean(d)) * 30.0 if d else 0.0


def contexts(split):
    """Context features of every capture frame used by the protocol: {seq: {c: {ego, crowd, small}}}."""
    d = np.load(DETS[split])
    seqs = json.load(open(DS[split] / "sequences.json"))
    z = np.load(DS[split] / "egomotion.npz")
    out = {}
    for sq, n in seqs:
        n = min(n, MAX_FRAMES)
        C = z[sq]
        out[sq] = {}
        for c in range(1, n + 1, STRIDE):
            if c + max(LAGS) > n:
                break
            det = d[f"{sq}/{c}"]
            conf = det[det[:, 4] >= CONF_CTX]
            s = _sz(conf)
            out[sq][c] = {"ego": ego_speed(C, c, 640, 360), "crowd": float(len(conf)),
                          "small": float(np.mean(s < SMALL_PX)) if len(conf) else 0.0}
    return out


def _job(args):
    split, fname, params, lag, ctx, cuts = args
    import torch
    torch.set_num_threads(1)
    from stream_ap import Acc
    d = np.load(DETS[split])
    labels = json.load(open(DS[split] / "labels.json"))
    seqs = json.load(open(DS[split] / "sequences.json"))
    accs = {"all": Acc()}
    for f in FEATURES:
        for b in range(3):
            accs[f"{f}{b}"] = Acc()
    for s in SIZES:
        accs[f"size_{s}"] = Acc()
    for sq, n in seqs:
        n = min(n, MAX_FRAMES)
        fc = _make(params, DS[split])
        for c in range(1, n + 1, STRIDE):
            if fc:
                fc.observe(c, c / 30.0, sq, d[f"{sq}/{c}"], fidx=c)
            if c + max(LAGS) > n:
                continue
            t = c + lag
            pred = d[f"{sq}/{c}"]
            if fc:
                pred = fc.predict(c, pred, c / 30.0, t / 30.0, (640, 640), seq=sq, fidx_c=c, fidx_t=t)
            gt = np.array(labels[sq].get(str(t), []), np.float32).reshape(-1, 5)
            accs["all"].add(pred, gt)
            x = ctx[sq][str(c)] if str(c) in ctx[sq] else ctx[sq][c]
            for f in FEATURES:
                accs[f"{f}{int(np.searchsorted(cuts[f], x[f], side='right'))}"].add(pred, gt)
            ps, gs = _sz(pred), _sz(gt[:, 1:5])
            for s, (lo, hi) in SIZES.items():
                accs[f"size_{s}"].add(pred[(ps >= lo) & (ps < hi)], gt[(gs >= lo) & (gs < hi)])
    return fname, lag, {k: a.ap()[0] for k, a in accs.items()}


def cmd_run(split, workers=3):
    os.nice(19)
    ctx = contexts(split)
    if split == "train":
        allv = {f: [v[f] for s in ctx.values() for v in s.values()] for f in FEATURES}
        cuts = {f: [float(np.quantile(allv[f], 1 / 3)), float(np.quantile(allv[f], 2 / 3))] for f in FEATURES}
    else:                                        # the train thresholds, unchanged
        cuts = json.load(open(OUT / "decay_context_train.json"))["cuts"]
    fcs = {"none": None, "v1": json.load(open(TUNING))["best"]["params"],
           "v2": json.load(open(TUNING2))["best"]["params"]}
    jobs = [(split, fn, p, lag, ctx, cuts) for fn, p in fcs.items() for lag in LAGS]
    with mp.get_context("fork").Pool(workers) as pool:
        res = pool.map(_job, jobs, chunksize=1)
    ap = {fn: {} for fn in fcs}
    for fn, lag, r in res:
        ap[fn][lag] = r
    strata = list(res[0][2])
    out = {"split": split, "lags_frames": LAGS, "lags_ms": [round(x * 1000 / 30, 1) for x in LAGS], "cuts": cuts,
           "counts": {f"{f}{b}": int(sum(int(np.searchsorted(cuts[f], v[f], side="right")) == b
                                         for s in ctx.values() for v in s.values()))
                      for f in FEATURES for b in range(3)},
           "ap": {fn: {k: [ap[fn][lag][k] for lag in LAGS] for k in strata} for fn in fcs},
           "ratio": {fn: {k: [ap[fn][lag][k] / ap["none"][0][k] if ap["none"][0][k] else None for lag in LAGS]
                          for k in strata} for fn in fcs},
           "context_def": {"ego": "camera motion px/s (last 5 steps)", "crowd": f"detections conf>={CONF_CTX}",
                           "small": f"share of those < {SMALL_PX} px", "sizes_px": SIZES},
           "note": "VisDrone-VID, YOLOv8s@640 CPU detections, one result every %d frames, capture-anchored; "
                   "context from the capture frame only (live-computable)" % STRIDE}
    json.dump(out, open(OUT / f"decay_context_{split}.json", "w"), indent=1)
    for fn in fcs:
        print(fn)
        for k in strata:
            print(f"  {k:12s}", " ".join(f"{r:.2f}" if r is not None else "  - " for r in out["ratio"][fn][k]))


def cmd_compare():
    """Prediction error of the val decay (ratio vs lag, per stratum) by the train curves: global vs per-stratum."""
    tr, va = (json.load(open(OUT / f"decay_context_{s}.json")) for s in ("train", "val"))
    out = {}
    for fn in tr["ratio"]:
        g = np.array(tr["ratio"][fn]["all"], float)
        rows = {}
        for f in FEATURES:
            eg, ec = [], []
            for b in range(3):
                k = f"{f}{b}"
                v, s = np.array(va["ratio"][fn][k], float), np.array(tr["ratio"][fn][k], float)
                eg.append(np.nanmean(np.abs(v[1:] - g[1:])))
                ec.append(np.nanmean(np.abs(v[1:] - s[1:])))
            rows[f] = {"mae_global": float(np.mean(eg)), "mae_conditioned": float(np.mean(ec)),
                       "spread_train": float(np.nanmax([np.nanmax(np.abs(np.array(tr["ratio"][fn][f"{f}{b}"], float)
                                                                         - g)) for b in range(3)]))}
        out[fn] = rows
        print(fn, {f: {k: round(v, 3) for k, v in r.items()} for f, r in rows.items()})
    json.dump(out, open(OUT / "decay_context_compare.json", "w"), indent=1)


def cmd_dets(split):
    import torch
    os.nice(19)
    torch.set_num_threads(2)
    from ultralytics import YOLO
    seqs = json.load(open(DS[split] / "sequences.json"))
    m = YOLO(str(ROOT / "yolov8s.pt"))
    out = {}
    for sq, n in seqs:
        for i in range(1, min(n, MAX_FRAMES) + 1):
            r = m.predict(str(DS[split] / sq / ("%07d.jpg" % i)), imgsz=640, conf=0.01, iou=0.45, max_det=100,
                          verbose=False, device="cpu")[0]
            b = r.boxes
            out[f"{sq}/{i}"] = np.concatenate([b.xyxy.numpy(), b.conf.numpy()[:, None], b.cls.numpy()[:, None]],
                                              1).astype(np.float32)
        print(sq, min(n, MAX_FRAMES), flush=True)
    np.savez_compressed(DETS[split], **out)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "dets":
        cmd_dets(sys.argv[2])
    elif cmd == "run":
        cmd_run(sys.argv[2])
    else:
        cmd_compare()
