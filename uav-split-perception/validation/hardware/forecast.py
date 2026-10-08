#!/usr/bin/env python3
"""Motion forecasting of stale detections (counters the staleness decay measured in staleness_decay.py).

A result computed on the frame captured at t_cap is shown at t_now > t_cap. Each of its boxes is moved by
v * (t_now - t_cap), where v is a per-box velocity (pixels/s, box centre) estimated online and causally from
the results that have arrived so far:
  * the new result is associated with the previous-captured result (greedy IoU, same class, previous boxes
    first moved to the new capture time), v = alpha * displacement/dt + (1 - alpha) * v_previous;
  * boxes without a match take the median velocity of the matched ones (camera ego-motion), if `ego`.
Box size is kept. Nothing about the future is used: velocities come only from results already arrived.

Hyper-parameters are tuned on VisDrone-VID *train* (disjoint from the val sequences used by every live run):
  forecast.py dets   - detections of YOLOv8s@640 on the train sequences, on the CPU (the GPU is left to the
                       live campaign), single-label NMS as in the live workers (conf 0.01, IoU 0.45, 100 boxes)
  forecast.py tune   - replays a result stream (one result every STRIDE frames, shown LAG frames late) and
                       picks the setting with the highest mean AP over the lags; writes forecast_tuning.json
The frozen setting is then applied to live runs by stream_ap.py / summarize_vid.py (--forecast).
  forecast.py decay  - staleness decay with and without the frozen forecaster (same train detections): a result
                       is shown exactly LAG frames after its capture (one result every STRIDE frames);
                       writes staleness_decay_forecast.json (same format as staleness_decay.json) for the
                       controller's stream objective (v3 with forecasting)
"""
import itertools
import json
import multiprocessing as mp
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
TRAIN = ROOT / "datasets" / "visdrone_vid_train_640"
OUT = ROOT / "experiments" / "results" / "hardware"
DETS = OUT / "forecast_train_dets.npz"
TUNING = OUT / "forecast_tuning.json"
MAX_FRAMES = 400
STRIDE = 2
LAGS = [0, 3, 5, 8, 12, 18]           # frames at 30 fps: 0-600 ms, the range of live result ages
GRID = {"alpha": [0.3, 0.5, 0.7, 1.0], "iou_thr": [0.1, 0.3], "min_conf": [0.05, 0.25], "ego": [True, False],
        "max_h_s": [0.4, 1.0]}


def _centres(b):
    return np.stack([(b[:, 0] + b[:, 2]) / 2, (b[:, 1] + b[:, 3]) / 2], 1)


def shift(boxes, vel, dt, wh=None):
    if not len(boxes) or dt == 0:
        return boxes
    out = boxes.copy()
    out[:, [0, 2]] += vel[:, :1] * dt
    out[:, [1, 3]] += vel[:, 1:] * dt
    if wh is not None:
        out[:, [0, 2]] = out[:, [0, 2]].clip(0, wh[0])
        out[:, [1, 3]] = out[:, [1, 3]].clip(0, wh[1])
    return out


def _iou(a, b):
    lt = np.maximum(a[:, None, :2], b[None, :, :2])
    rb = np.minimum(a[:, None, 2:4], b[None, :, 2:4])
    inter = np.prod((rb - lt).clip(0), 2)
    area = lambda x: (x[:, 2] - x[:, 0]) * (x[:, 3] - x[:, 1])  # noqa: E731
    return inter / (area(a)[:, None] + area(b)[None] - inter + 1e-9)


class Forecaster:
    """Velocity forecaster; with align=True the camera's own motion is measured from the images (egomotion.py)
    and removed first, so the velocities are the objects' own; with scale_vel=True box size changes are
    extrapolated too. With both off it is the original constant-velocity forecaster."""

    def __init__(self, alpha=0.5, iou_thr=0.1, min_conf=0.05, ego=True, max_h_s=1.0, max_gap_s=0.7,
                 align=False, scale_vel=False, obj_vel=True):
        self.alpha, self.iou_thr, self.min_conf, self.ego = alpha, iou_thr, min_conf, ego
        self.max_h_s, self.max_gap_s = max_h_s, max_gap_s
        self.align, self.scale_vel, self.obj_vel = align, scale_vel, obj_vel
        self.chains = None                          # {seq: cumulative transforms}, set by the caller if align
        self.vel, self.svel, self.last = {}, {}, None   # last: (t_cap, seq, boxes, vel, svel, frame index)

    def _T(self, seq, c, t):
        if not self.align or self.chains is None or seq not in self.chains or c is None or t is None:
            return None
        from egomotion import transform
        C = self.chains[seq]
        if not (0 < c < len(C) and 0 < t < len(C)):
            return None
        return transform(C, c, t)

    def observe(self, rid, t_cap, seq, boxes, fidx=None):
        v = np.zeros((len(boxes), 2), np.float32)
        sv = np.zeros(len(boxes), np.float32)
        L = self.last
        if L is not None and L[1] == seq and 0 < abs(t_cap - L[0]) <= self.max_gap_s and len(boxes) and len(L[2]):
            dt = t_cap - L[0]
            cur = np.nonzero(boxes[:, 4] >= self.min_conf)[0]
            prv = np.nonzero(L[2][:, 4] >= self.min_conf)[0]
            raw_all = []
            if len(cur) and len(prv):
                T = self._T(seq, L[5], fidx)
                base = L[2][prv] if T is None else _warp(L[2][prv], T)      # previous boxes in this frame
                pred = shift(base, L[3][prv], dt)
                if self.scale_vel:
                    pred = _scale(pred, np.exp(L[4][prv] * dt))
                iou = _iou(boxes[cur], pred)
                iou *= boxes[cur, 5][:, None] == L[2][prv, 5][None]
                pairs = np.argwhere(iou >= self.iou_thr)
                pairs = pairs[np.argsort(-iou[pairs[:, 0], pairs[:, 1]])]
                used_c, used_p = set(), set()
                for i, j in pairs:
                    if i in used_c or j in used_p:
                        continue
                    used_c.add(i)
                    used_p.add(j)
                    ci, pj = cur[i], prv[j]
                    raw = (_centres(boxes[ci:ci + 1])[0] - _centres(base[j:j + 1])[0]) / dt
                    raw_all.append(raw)
                    v[ci] = self.alpha * raw + (1 - self.alpha) * L[3][pj]
                    if self.scale_vel:
                        r = np.log(max(_size(boxes[ci:ci + 1])[0], 1e-3) / max(_size(base[j:j + 1])[0], 1e-3)) / dt
                        sv[ci] = self.alpha * r + (1 - self.alpha) * L[4][pj]
                if self.ego and raw_all:
                    matched = np.zeros(len(boxes), bool)
                    matched[[cur[i] for i in used_c]] = True
                    v[~matched] = np.median(np.array(raw_all), 0)
        if not self.obj_vel:
            v[:] = 0.0
        self.vel[rid], self.svel[rid] = v, sv
        if L is None or seq != L[1] or t_cap > L[0]:
            self.last = (t_cap, seq, boxes, v, sv, fidx)

    def predict(self, rid, boxes, t_cap, t_now, wh=None, seq=None, fidx_c=None, fidx_t=None):
        h = min(max(t_now - t_cap, 0.0), self.max_h_s)
        T = self._T(seq, fidx_c, fidx_t)
        out = boxes if T is None else _warp(boxes, T)
        out = shift(out, self.vel[rid], h)
        if self.scale_vel and len(out):
            out = _scale(out, np.exp(np.clip(self.svel[rid] * h, -1.0, 1.0)))
        if wh is not None and len(out):
            out = out.copy()
            out[:, [0, 2]] = out[:, [0, 2]].clip(0, wh[0])
            out[:, [1, 3]] = out[:, [1, 3]].clip(0, wh[1])
        return out


def _warp(boxes, T):
    from egomotion import warp_boxes
    return warp_boxes(boxes, T)


def _size(b):
    return np.sqrt(np.clip((b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1]), 1e-6, None))


def _scale(b, f):
    out = b.copy()
    cx, cy = (b[:, 0] + b[:, 2]) / 2, (b[:, 1] + b[:, 3]) / 2
    hw, hh = (b[:, 2] - b[:, 0]) / 2 * f, (b[:, 3] - b[:, 1]) / 2 * f
    out[:, 0], out[:, 2], out[:, 1], out[:, 3] = cx - hw, cx + hw, cy - hh, cy + hh
    return out


def cmd_dets():
    import os
    import torch
    torch.set_num_threads(4)
    os.nice(19)
    from ultralytics import YOLO
    torch.set_num_threads(4)
    seqs = json.load(open(TRAIN / "sequences.json"))
    m = YOLO(str(ROOT / "yolov8s.pt"))
    out = {}
    for sq, n in seqs:
        for i in range(1, min(n, MAX_FRAMES) + 1):
            r = m.predict(str(TRAIN / sq / ("%07d.jpg" % i)), imgsz=640, conf=0.01, iou=0.45, max_det=100,
                          verbose=False, device="cpu")[0]
            b = r.boxes
            out[f"{sq}/{i}"] = np.concatenate([b.xyxy.numpy(), b.conf.numpy()[:, None], b.cls.numpy()[:, None]],
                                              1).astype(np.float32)
        print(sq, min(n, MAX_FRAMES), flush=True)
    np.savez_compressed(DETS, **out)


def replay(params, lag, dets, labels, seqs):
    """AP of a stream: results for frames 1, 1+STRIDE, ... each shown from LAG frames after capture."""
    from stream_ap import Acc
    acc = Acc()
    for sq, n in seqs:
        n = min(n, MAX_FRAMES)
        fc = _make(params, TRAIN)
        caps = list(range(1, n + 1, STRIDE))
        k, held = 0, None
        for t in range(max(LAGS) + 1, n + 1):
            while k < len(caps) and caps[k] + lag <= t:
                c = caps[k]
                if fc:
                    fc.observe(c, c / 30.0, sq, dets[f"{sq}/{c}"], fidx=c)
                held = c
                k += 1
            if held is None:
                continue
            pred = dets[f"{sq}/{held}"]
            if fc:
                pred = fc.predict(held, pred, held / 30.0, t / 30.0, (640, 640), seq=sq, fidx_c=held, fidx_t=t)
            acc.add(pred, np.array(labels[sq].get(str(t), []), np.float32).reshape(-1, 5))
    return acc.ap()[0]


_CHAINS = {}


def _make(params, dataset):
    """Forecaster from parameters (None: no forecasting); camera-motion chains loaded once per dataset."""
    if not params:
        return None
    fc = Forecaster(**params)
    if params.get("align"):
        if dataset not in _CHAINS:
            z = np.load(Path(dataset) / "egomotion.npz")
            _CHAINS[dataset] = {k: z[k] for k in z.files}
        fc.chains = _CHAINS[dataset]
    return fc


def _job(args):
    params, lag = args
    d = np.load(DETS)
    dets = {k: d[k] for k in d.files}
    return replay(params, lag, dets, json.load(open(TRAIN / "labels.json")), json.load(open(TRAIN / "sequences.json")))


def cmd_tune(workers=6):
    import os
    os.nice(19)
    settings = [dict(zip(GRID, vals)) for vals in itertools.product(*GRID.values())]
    jobs = [(None, lag) for lag in LAGS] + [(s, lag) for s in settings for lag in LAGS]
    with mp.get_context("fork").Pool(workers) as pool:
        res = pool.map(_job, jobs, chunksize=1)
    base = dict(zip(LAGS, res[:len(LAGS)]))
    rows = []
    for i, s in enumerate(settings):
        ap = res[len(LAGS) * (i + 1):len(LAGS) * (i + 2)]
        rows.append({"params": s, "ap": dict(zip(LAGS, ap)), "mean_ap_lagged": float(np.mean(ap[1:]))})
    rows.sort(key=lambda r: -r["mean_ap_lagged"])
    best = rows[0]
    out = {"split": "VisDrone-VID train", "stride_frames": STRIDE, "lags_frames": LAGS,
           "lags_ms": [round(x * 1000 / 30, 1) for x in LAGS], "no_forecast_ap": base, "best": best,
           "recovered_ratio": {lag: best["ap"][lag] / base[0] for lag in LAGS},
           "stale_ratio": {lag: base[lag] / base[0] for lag in LAGS}, "all": rows}
    json.dump(out, open(TUNING, "w"), indent=1)
    print("no forecast", {k: round(v, 4) for k, v in base.items()})
    print("best", best["params"], {k: round(v, 4) for k, v in best["ap"].items()})


DECAY_LAGS = [0, 1, 2, 3, 5, 8, 12, 18, 25, 35]


def _decay_job(args):
    params, lag = args
    from stream_ap import Acc
    d = np.load(DETS)
    labels, seqs = json.load(open(TRAIN / "labels.json")), json.load(open(TRAIN / "sequences.json"))
    acc = Acc()
    for sq, n in seqs:
        n = min(n, MAX_FRAMES)
        fc = _make(params, TRAIN)
        caps = list(range(1, n + 1, STRIDE))
        for c in caps:
            if fc:
                fc.observe(c, c / 30.0, sq, d[f"{sq}/{c}"], fidx=c)
            t = c + lag                       # shown exactly `lag` frames after capture
            if t <= max(DECAY_LAGS) or t > n:  # same target frames for every lag
                continue
            pred = d[f"{sq}/{c}"]
            if fc:
                pred = fc.predict(c, pred, c / 30.0, t / 30.0, (640, 640), seq=sq, fidx_c=c, fidx_t=t)
            acc.add(pred, np.array(labels[sq].get(str(t), []), np.float32).reshape(-1, 5))
    return acc.ap()[0]


GRID2 = {"alpha": [0.3, 0.5, 0.7], "iou_thr": [0.1, 0.3], "min_conf": [0.05], "ego": [False], "max_h_s": [1.0],
         "align": [True], "scale_vel": [False, True], "obj_vel": [True, False]}
TUNING2 = OUT / "forecast_tuning_v2.json"


def cmd_tune2(workers=6):
    """Second stage: camera-motion alignment (egomotion.py), size extrapolation, with/without object velocity.
    The v1 winner is re-run alongside as the reference. Same train replay as cmd_tune."""
    import os
    os.nice(19)
    v1 = json.load(open(TUNING))["best"]["params"]
    settings = [v1] + [dict(zip(GRID2, vals)) for vals in itertools.product(*GRID2.values())]
    jobs = [(None, lag) for lag in LAGS] + [(s, lag) for s in settings for lag in LAGS]
    with mp.get_context("fork").Pool(workers) as pool:
        res = pool.map(_job, jobs, chunksize=1)
    base = dict(zip(LAGS, res[:len(LAGS)]))
    rows = []
    for i, s in enumerate(settings):
        ap = res[len(LAGS) * (i + 1):len(LAGS) * (i + 2)]
        rows.append({"params": s, "ap": dict(zip(LAGS, ap)), "mean_ap_lagged": float(np.mean(ap[1:]))})
    ref = rows[0]
    rows_sorted = sorted(rows, key=lambda r: -r["mean_ap_lagged"])
    best = rows_sorted[0]
    out = {"split": "VisDrone-VID train", "stride_frames": STRIDE, "lags_frames": LAGS, "no_forecast_ap": base,
           "v1_reference": ref, "best": best, "all": rows_sorted}
    json.dump(out, open(TUNING2, "w"), indent=1)
    print("no forecast", {k: round(v, 4) for k, v in base.items()})
    print("v1         ", {k: round(v, 4) for k, v in ref["ap"].items()})
    for r in rows_sorted[:6]:
        print(round(r["mean_ap_lagged"], 4), r["params"])


def cmd_decay(workers=6, version=""):
    import os
    os.nice(19)
    best = json.load(open(TUNING2 if version == "v2" else TUNING))["best"]["params"]
    jobs = [(None, lag) for lag in DECAY_LAGS] + [(best, lag) for lag in DECAY_LAGS]
    with mp.get_context("fork").Pool(workers) as pool:
        res = pool.map(_decay_job, jobs, chunksize=1)
    plain, fc = res[:len(DECAY_LAGS)], res[len(DECAY_LAGS):]
    out = {"lag_frames": DECAY_LAGS, "lag_ms": [round(x * 1000 / 30, 1) for x in DECAY_LAGS], "ap": fc,
           "ratio": [a / plain[0] for a in fc], "ap_no_forecast": plain,
           "ratio_no_forecast": [a / plain[0] for a in plain], "forecaster": best,
           "note": "VisDrone-VID train, YOLOv8s@640 CPU detections, one result every %d frames, ratio relative "
                   "to fresh AP without forecasting" % STRIDE}
    json.dump(out, open(OUT / f"staleness_decay_forecast{'_' + version if version else ''}.json", "w"), indent=1)
    print("no forecast", [round(r, 3) for r in out["ratio_no_forecast"]])
    print("forecast   ", [round(r, 3) for r in out["ratio"]])


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    cmd = sys.argv[1]
    if cmd == "decay":
        cmd_decay(version=sys.argv[2] if len(sys.argv) > 2 else "")
    else:
        {"dets": cmd_dets, "tune": cmd_tune, "tune2": cmd_tune2}[cmd]()
