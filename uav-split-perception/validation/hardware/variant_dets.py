#!/usr/bin/env python3
"""Detections of every controller variant on every VisDrone-VID val frame, for the offline replay evaluator
(publication plan, Phase 1: score decay-curve and baseline variants from recorded runs before spending
hardware nights).

Variants exactly as the live system produces them (adaptive2.py): onboard n320 / s320 / s640 on the raw frame,
offloaded s{640,480,320} and m640 on a JPEG of the letterboxed frame at quality 90 or 50. Boxes are kept in the
variant's letterboxed input coordinates, as in the live runs' _dets.npz (stream_ap.unletterbox maps them back).
CPU only, nice 19, 2 threads (the GPU and the network belong to a running campaign). Resumable per variant.
usage: variant_dets.py [VARIANT ...]     -> experiments/results/hardware/variant_dets/<variant>.npz
"""
import os
import sys
import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
VID = ROOT / "datasets" / "visdrone_vid_640"
OUT = ROOT / "experiments" / "results" / "hardware" / "variant_dets"
VARIANTS = {"n320": ("yolov8n", 320, None), "s320": ("yolov8s", 320, None), "s640": ("yolov8s", 640, None)}
VARIANTS.update({f"s{r}q{q}": ("yolov8s", r, q) for r in (640, 480, 320) for q in (90, 50)})
VARIANTS.update({f"m640q{q}": ("yolov8m", 640, q) for q in (90, 50)})
WEIGHTS = {"yolov8n": ROOT / "weights" / "yolov8n.pt", "yolov8s": ROOT / "yolov8s.pt", "yolov8m": ROOT / "weights" / "yolov8m.pt"}


def main(names):
    import torch
    os.nice(19)
    torch.set_num_threads(2)
    from ultralytics import YOLO
    from ultralytics.data.augment import LetterBox
    OUT.mkdir(parents=True, exist_ok=True)
    seqs = json.load(open(VID / "sequences.json"))
    for name in names:
        f = OUT / f"{name}.npz"
        if f.exists():
            continue
        model, res, q = VARIANTS[name]
        m = YOLO(str(WEIGHTS[model] if WEIGHTS[model].exists() else ROOT / f"{model}.pt"))
        lb = LetterBox((res, res), auto=False)
        out = {}
        for sq, n in seqs:
            for i in range(1, n + 1):
                img = lb(image=cv2.imread(str(VID / sq / ("%07d.jpg" % i))))
                if q is not None:
                    _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, q])
                    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
                b = m.predict(img, imgsz=res, conf=0.01, iou=0.45, max_det=100, verbose=False, device="cpu")[0].boxes
                out[f"{sq}/{i}"] = np.concatenate([b.xyxy.numpy(), b.conf.numpy()[:, None], b.cls.numpy()[:, None]],
                                                  1).astype(np.float32)
        np.savez_compressed(f, **out)
        print(name, "done", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:] or list(VARIANTS))
