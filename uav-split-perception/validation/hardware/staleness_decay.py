#!/usr/bin/env python3
"""How fast detections go stale on aerial video: AP of detections computed on frame t - d, scored against
the ground truth of frame t, relative to d = 0. Measured on VisDrone2019-VID *train* sequences (disjoint
from the val sequences used to test the controller), with YOLOv8s@640, single-label NMS (conf 0.01).
Output: experiments/results/hardware/staleness_decay.json  {"lag_frames": [...], "ap": [...], "ratio": [...]}
"""
import json
from pathlib import Path

import cv2
import numpy as np
import torch
from ultralytics import YOLO

from stream_ap import Acc

ROOT = Path(__file__).resolve().parent.parent.parent
TRAIN = ROOT / "datasets" / "visdrone_vid_train_640"
LAGS = [0, 1, 2, 3, 5, 8, 12, 18, 25, 35]


def main():
    labels = json.load(open(TRAIN / "labels.json"))
    seqs = json.load(open(TRAIN / "sequences.json"))
    m = YOLO(str(ROOT / "yolov8s.pt"))
    acc = {d: Acc() for d in LAGS}
    for sq, n in seqs:
        n = min(n, 200)
        preds = []
        for i in range(1, n + 1):
            r = m.predict(str(TRAIN / sq / ("%07d.jpg" % i)), imgsz=640, conf=0.01, iou=0.7, max_det=100,
                          verbose=False, device=0)[0]
            b = r.boxes
            preds.append(np.concatenate([b.xyxy.cpu().numpy(), b.conf.cpu().numpy()[:, None],
                                         b.cls.cpu().numpy()[:, None]], 1))
        for d in LAGS:
            for t in range(max(LAGS), n):          # same target frames for every lag
                gt = np.array(labels[sq].get(str(t + 1), []), np.float32).reshape(-1, 5)
                acc[d].add(preds[t - d], gt)
        print(sq, n, flush=True)
    ap = [acc[d].ap()[0] for d in LAGS]
    out = {"lag_frames": LAGS, "lag_ms": [round(d * 1000 / 30, 1) for d in LAGS], "ap": ap,
           "ratio": [a / ap[0] for a in ap], "sequences": [s for s, _ in seqs]}
    json.dump(out, open(ROOT / "experiments" / "results" / "hardware" / "staleness_decay.json", "w"), indent=1)
    print(json.dumps({k: (np.round(v, 3).tolist() if k in ("ap", "ratio") else v) for k, v in out.items()}))


if __name__ == "__main__":
    main()
