#!/usr/bin/env python3
"""Streaming AP (Li, Wang, Ramanan, "Towards Streaming Perception", ECCV 2020) of live runs on VisDrone-VID.

At the capture instant of every camera frame t, the UAV holds the newest-captured result that has
arrived by then (results can arrive out of order when several servers work in parallel; the UAV keeps
the freshest). Those detections - possibly computed on an older frame - are scored against the ground
truth of frame t. AP is COCO-style mAP@[.5:.95] (101-point, ultralytics ap_per_class) pooled over all
frames of the run, and per phase. A frame with no result yet scores all its objects as missed.
Also reported: "fresh AP", each result scored against its own frame (accuracy without staleness).
Boxes are mapped from the variant's letterboxed input back to the 640-px camera frame.

usage: stream_ap.py RUN.json [RUN.json ...]   (each with RUN_dets.npz next to it)
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
import torch
from ultralytics.utils.metrics import ap_per_class, box_iou

ROOT = Path(__file__).resolve().parent.parent.parent
VID = ROOT / "datasets" / "visdrone_vid_640"
IOUV = torch.linspace(0.5, 0.95, 10)
_shapes = {}


def frame_shape(seq):
    if seq not in _shapes:
        _shapes[seq] = cv2.imread(str(next((VID / seq).glob("*.jpg")))).shape[:2]
    return _shapes[seq]


def unletterbox(det, res, h, w):
    """Boxes from a res x res letterboxed input (ultralytics LetterBox, centred) to the h x w frame."""
    r = min(res / h, res / w)
    pw, ph = (res - round(w * r)) / 2, (res - round(h * r)) / 2
    d = det.copy()
    d[:, [0, 2]] = (d[:, [0, 2]] - pw) / r
    d[:, [1, 3]] = (d[:, [1, 3]] - ph) / r
    d[:, [0, 2]] = d[:, [0, 2]].clip(0, w)
    d[:, [1, 3]] = d[:, [1, 3]].clip(0, h)
    return d


def match(pred, gt):
    """tp matrix (n_pred x 10) as in ultralytics DetectionValidator.match_predictions."""
    tp = np.zeros((len(pred), len(IOUV)), bool)
    if len(pred) == 0 or len(gt) == 0:
        return tp
    iou = box_iou(torch.tensor(gt[:, 1:5]), torch.tensor(pred[:, :4])).numpy()
    correct_class = gt[:, :1] == pred[:, 5][None]
    iou = iou * correct_class
    for i, thr in enumerate(IOUV.tolist()):
        m = np.array(np.nonzero(iou >= thr)).T
        if m.shape[0]:
            if m.shape[0] > 1:
                m = m[iou[m[:, 0], m[:, 1]].argsort()[::-1]]
                m = m[np.unique(m[:, 1], return_index=True)[1]]
                m = m[np.unique(m[:, 0], return_index=True)[1]]
            tp[m[:, 1].astype(int), i] = True
    return tp


class Acc:
    def __init__(self):
        self.tp, self.conf, self.pcls, self.tcls = [], [], [], []

    def add(self, pred, gt):
        self.tp.append(match(pred, gt))
        self.conf.append(pred[:, 4] if len(pred) else np.zeros(0))
        self.pcls.append(pred[:, 5] if len(pred) else np.zeros(0))
        self.tcls.append(gt[:, 0] if len(gt) else np.zeros(0))

    def ap(self):
        tp = np.concatenate(self.tp) if self.tp else np.zeros((0, 10), bool)
        if not len(tp) or not sum(len(t) for t in self.tcls):
            return 0.0, 0.0
        res = ap_per_class(tp, np.concatenate(self.conf), np.concatenate(self.pcls), np.concatenate(self.tcls))
        ap = res[5]                       # (n_classes, 10)
        return float(ap.mean()), float(ap[:, 0].mean())


def variant_key(f):
    v, srv = f["variant"], f["server"]
    if srv == "onboard":
        return {"n320": "yolov8n_320_raw", "s320": "yolov8s_320_raw", "s640": "yolov8s_640_raw",
                "m640": "yolov8m_640_raw", "l640": "yolov8l_640_raw"}[v]
    model = {"s": "yolov8s", "m": "yolov8m"}[v[0]]
    res, q = v[1:].split("q")
    return f"{model}_{res}_q{q}"


def evaluate(run_path, labels, hold="newest", acc_tab=None, decay=None, forecast=None, live=False,
             exclude_servers=()):
    """hold: 'newest' keeps the newest-captured arrived result; 'quality' keeps the arrived result with the
    highest expected quality acc(variant) x decay(age) at each instant (acc and decay from non-test data).
    forecast: Forecaster parameters (forecast.py, tuned on train); the held boxes are moved to the display time.
    live: use the camera-motion chain the Pi computed live during the run (<run>_livefc.npz) instead of the
    offline one.
    exclude_servers: drop results from these servers (counterfactual: what the drone would hold without them)."""
    run = json.load(open(run_path))
    dets = np.load(str(run_path)[:-5] + "_dets.npz")
    period = 1.0 / 30.0
    frames = {f["id"]: f for f in run["frames"]}
    arrived = sorted((f["t_res"], f["id"]) for f in run["frames"] if f.get("t_res") is not None and str(f["id"]) in dets
                     and f.get("server") not in exclude_servers)
    mapped = {}
    for _, fid in arrived:
        f = frames[fid]
        seq = f["frame"][0]
        h, w = frame_shape(seq)
        mapped[fid] = unletterbox(dets[str(fid)], f["res"], h, w)
    gt_of = lambda f: np.array(labels[f["frame"][0]].get(str(f["frame"][1]), []), np.float32).reshape(-1, 5)  # noqa: E731
    total, per_phase, fresh = Acc(), defaultdict(Acc), Acc()
    j, newest, pool = 0, None, []
    fc = None
    if forecast is not None:
        from forecast import _make
        fc = _make(forecast, VID)
        if live and forecast.get("align"):
            z = np.load(str(run_path)[:-5] + "_livefc.npz")
            fc.chains = {k[2:]: z[k] for k in z.files if k.startswith("C_")}
    lag, rat = (np.array(decay["lag_ms"]), np.array(decay["ratio"])) if decay else (None, None)
    for fid in sorted(frames):
        t = fid * period
        while j < len(arrived) and arrived[j][0] <= t:
            cand = arrived[j][1]
            if newest is None or cand > newest:
                newest = cand
            pool.append(cand)
            if fc:
                fc.observe(cand, cand * period, frames[cand]["frame"][0], mapped[cand], fidx=frames[cand]["frame"][1])
            j += 1
        if hold == "quality" and pool:
            pool = sorted(pool)[-20:]           # older results can never win against 20 newer ones
            newest = max(pool, key=lambda c: acc_tab[variant_key(frames[c])] *
                         float(np.interp((fid - c) * period * 1e3, lag, rat)))
        f = frames[fid]
        gt = gt_of(f)
        pred = mapped[newest] if newest is not None else np.zeros((0, 6), np.float32)
        if fc and newest is not None:
            h, w = frame_shape(frames[newest]["frame"][0])
            fr_c, fr_t = frames[newest]["frame"], f["frame"]
            pred = fc.predict(newest, pred, newest * period, t, (w, h), seq=fr_c[0], fidx_c=fr_c[1],
                              fidx_t=fr_t[1] if fr_t[0] == fr_c[0] else None)
        total.add(pred, gt)
        per_phase[f["phase"]].add(pred, gt)
    for fid, d in mapped.items():
        fresh.add(d, gt_of(frames[fid]))
    s_ap, s_ap50 = total.ap()
    return {"policy": run["policy"], "scenario": run["scenario"], "hold": hold, "forecast": forecast is not None, "sAP": s_ap, "sAP50": s_ap50,
            "fresh_AP": fresh.ap()[0], "results": len(mapped), "frames": len(frames),
            "per_phase_sAP": {k: v.ap()[0] for k, v in per_phase.items()}}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--hold", default="newest", choices=["newest", "quality"])
    ap.add_argument("--forecast", action="store_true", help="apply the train-tuned forecaster (forecast_tuning.json)")
    a = ap.parse_args()
    labels = json.load(open(VID / "labels.json"))
    hw = ROOT / "experiments" / "results" / "hardware"
    acc_tab = json.load(open(hw / "variant_accuracy_visdrone.json")) if a.hold == "quality" else None
    decay = json.load(open(hw / "staleness_decay.json")) if a.hold == "quality" else None
    for p in a.runs:
        fp = json.load(open(hw / "forecast_tuning.json"))["best"]["params"] if a.forecast else None
        r = evaluate(Path(p), labels, a.hold, acc_tab, decay, fp)
        print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items() if k != "per_phase_sAP"}),
              {k: round(v, 3) for k, v in r["per_phase_sAP"].items()})


if __name__ == "__main__":
    main()
