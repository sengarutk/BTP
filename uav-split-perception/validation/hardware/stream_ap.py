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
VID_RAW = ROOT / "datasets" / "visdrone_vid" / "VisDrone2019-VID-val"
SIZE_BINS = {"small": (0, 32 ** 2), "medium": (32 ** 2, 96 ** 2), "large": (96 ** 2, 1e12)}   # COCO, in 640-px frame pixels
_ign = {}


def frame_shape(seq):
    if seq not in _shapes:
        _shapes[seq] = cv2.imread(str(next((VID / seq).glob("*.jpg")))).shape[:2]
    return _shapes[seq]


def ignored_regions():
    """VisDrone ignored regions (category 0) per val frame, scaled to the 640-px frames like prepare_vid.py:
    {seq: {frame: [[x0, y0, x1, y1], ...]}}; built from the raw annotations once, cached as ignored.json."""
    if not _ign:
        f = VID / "ignored.json"
        if not f.exists():
            ann_root = next(VID_RAW.rglob("annotations"))
            out = {}
            for seq, _ in json.load(open(VID / "sequences.json")):
                w = cv2.imread(str(next(next(VID_RAW.rglob("sequences")).joinpath(seq).glob("*.jpg")))).shape[1]
                s = 640.0 / w
                reg = {}
                for line in open(ann_root / f"{seq}.txt"):
                    fr, _, x, y, bw, bh, score, cat = (int(v) for v in line.strip().split(",")[:8])
                    if cat == 0:
                        reg.setdefault(str(fr), []).append([x * s, y * s, (x + bw) * s, (y + bh) * s])
                out[seq] = reg
            json.dump(out, open(f, "w"))
        _ign.update(json.load(open(f)))
    return _ign


def drop_ignored(boxes, regions, h, w, thr=0.5):
    """Boxes (rows starting x0, y0, x1, y1) with more than `thr` of their area inside the union of the ignored
    regions removed (VisDrone toolkit rule, applied to detections and ground truth alike)."""
    if not regions or not len(boxes):
        return boxes
    m = np.zeros((h + 1, w + 1), np.int32)
    for x0, y0, x1, y1 in regions:
        m[int(max(y0, 0)) + 1:int(min(y1, h)) + 1, int(max(x0, 0)) + 1:int(min(x1, w)) + 1] = 1
    ii = m.cumsum(0).cumsum(1)
    x0, y0, x1, y1 = (np.clip(np.round(boxes[:, i]).astype(int), 0, (w, h, w, h)[i]) for i in range(4))
    inside = ii[y1, x1] - ii[y0, x1] - ii[y1, x0] + ii[y0, x0]
    area = np.maximum((x1 - x0) * (y1 - y0), 1)
    return boxes[inside / area <= thr]


def size_split(pred, gt, lo, hi):
    """COCO-style area range: ground truth outside [lo, hi) is ignored, and so is a detection that matches no
    in-range object (IoU >= 0.5) and is itself outside the range or matches an out-of-range object."""
    ga = (gt[:, 3] - gt[:, 1]) * (gt[:, 4] - gt[:, 2])
    gin = (ga >= lo) & (ga < hi)
    if not len(pred):
        return pred, gt[gin]
    pa = (pred[:, 2] - pred[:, 0]) * (pred[:, 3] - pred[:, 1])
    if len(gt):
        iou = box_iou(torch.tensor(pred[:, :4]), torch.tensor(gt[:, 1:5])).numpy()
        m_in = (iou[:, gin] >= 0.5).any(1) if gin.any() else np.zeros(len(pred), bool)
        m_out = (iou[:, ~gin] >= 0.5).any(1) if (~gin).any() else np.zeros(len(pred), bool)
    else:
        m_in = m_out = np.zeros(len(pred), bool)
    keep = m_in | (((pa >= lo) & (pa < hi)) & ~m_out)
    return pred[keep], gt[gin]


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


def variant_key(f, suffix=""):
    """Accuracy-table key of a result's variant; suffix '_visdrone' for runs made with --weight-suffix _visdrone."""
    v, srv = f["variant"], f["server"]
    if srv == "onboard":
        k = {"n320": "yolov8n_320_raw", "s320": "yolov8s_320_raw", "s640": "yolov8s_640_raw",
                "m640": "yolov8m_640_raw", "l640": "yolov8l_640_raw", "s640vd": "yolov8s_visdrone_640_raw",
                "m640vd": "yolov8m_visdrone_640_raw", "l640vd": "yolov8l_visdrone_640_raw"}[v]
        return k if "_visdrone" in k else k.replace("_", suffix + "_", 1)
    model = {"s": "yolov8s", "m": "yolov8m"}[v[0]] + suffix
    res, q = v[1:].split("q")
    return f"{model}_{res}_q{q}"


def evaluate(run_path, labels, hold="newest", acc_tab=None, decay=None, forecast=None, live=False,
             exclude_servers=(), extras=False, deadline_ms=300.0, subst=None):
    """hold: 'newest' keeps the newest-captured arrived result; 'quality' keeps the arrived result with the
    highest expected quality acc(variant) x decay(age) at each instant (acc and decay from non-test data).
    forecast: Forecaster parameters (forecast.py, tuned on train); the held boxes are moved to the display time.
    live: use the camera-motion chain the Pi computed live during the run (<run>_livefc.npz) instead of the
    offline one.
    exclude_servers: drop results from these servers (counterfactual: what the drone would hold without them).
    extras: also return the official-protocol scores with VisDrone's ignored regions masked (sAP_masked, sAP50_masked,
    fresh_AP_masked, sAP_size_masked by COCO area range) and worst-case freshness of the held result (age = capture
    time of the current frame minus that of the held result's frame; before the first result, the time since the
    start): age_p95_ms, age_max_ms, longest_stale_s (longest stretch with age > deadline_ms) and fresh_share.
    subst: {variant: {"seq/frame": dets}} (vd_variant_dets.py): every recorded result keeps its frame, variant and
    arrival time but its detections are replaced by that variant's detections from other weights (the run replayed
    with the VisDrone-trained detectors)."""
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
        src = subst[f["variant"]][f"{seq}/{f['frame'][1]}"] if subst is not None else dets[str(fid)]
        mapped[fid] = unletterbox(src, f["res"], h, w)
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
    if extras:
        ign = ignored_regions()
        mtot, msize, mfresh, ages = Acc(), {k: Acc() for k in SIZE_BINS}, Acc(), []
        reg_of = lambda fr: ign.get(fr[0], {}).get(str(fr[1]), [])  # noqa: E731
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
            newest = max(pool, key=lambda c: acc_tab[variant_key(frames[c], run.get("weight_suffix", ""))] *
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
        if extras:
            h, w = frame_shape(f["frame"][0])
            reg = reg_of(f["frame"])
            pm = drop_ignored(pred, reg, h, w)
            gm = gt[:, [1, 2, 3, 4, 0]] if len(gt) else np.zeros((0, 5), np.float32)
            gm = drop_ignored(gm, reg, h, w)[:, [4, 0, 1, 2, 3]] if len(gm) else gt
            mtot.add(pm, gm)
            for k, (lo, hi) in SIZE_BINS.items():
                msize[k].add(*size_split(pm, gm, lo, hi))
            ages.append((fid - newest) * period * 1e3 if newest is not None else (fid - min(frames)) * period * 1e3)
    fresh_phase = defaultdict(Acc)
    for fid, d in mapped.items():
        fresh.add(d, gt_of(frames[fid]))
        fresh_phase[frames[fid]["phase"]].add(d, gt_of(frames[fid]))
    s_ap, s_ap50 = total.ap()
    ext = {}
    if extras:
        for fid, d in mapped.items():
            fr = frames[fid]["frame"]
            h, w = frame_shape(fr[0])
            g = gt_of(frames[fid])
            g = drop_ignored(g[:, [1, 2, 3, 4, 0]], reg_of(fr), h, w)[:, [4, 0, 1, 2, 3]] if len(g) else g
            mfresh.add(drop_ignored(d, reg_of(fr), h, w), g)
        a = np.array(ages)
        stale = a > deadline_ms
        run_len, longest = 0, 0
        for x in stale:
            run_len = run_len + 1 if x else 0
            longest = max(longest, run_len)
        ma, ma50 = mtot.ap()
        ext = {"sAP_masked": ma, "sAP50_masked": ma50, "fresh_AP_masked": mfresh.ap()[0],
               "sAP_size_masked": {k: v.ap()[0] for k, v in msize.items()},
               "age_p95_ms": float(np.percentile(a, 95)), "age_max_ms": float(a.max()),
               "longest_stale_s": longest * period, "fresh_share": float(1 - stale.mean())}
    return {**ext, "policy": run["policy"], "scenario": run["scenario"], "hold": hold, "forecast": forecast is not None, "sAP": s_ap, "sAP50": s_ap50,
            "fresh_AP": fresh.ap()[0], "results": len(mapped), "frames": len(frames),
            "per_phase_sAP": {k: v.ap()[0] for k, v in per_phase.items()},
            "per_phase_fresh_AP": {k: v.ap()[0] for k, v in fresh_phase.items()}}


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
