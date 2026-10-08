#!/usr/bin/env python3
"""Per-device time of each perception variant (model x input size): letterbox + forward + NMS,
median over --n real COCO frames after warm-up; and JPEG bytes / encode time at each quality and size.
Output: JSON (--out)."""
import argparse
import glob
import json
import os
import statistics
import time

import cv2
import numpy as np
import torch

from hwbench import load_model


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--half", action="store_true")
    ap.add_argument("--threads", type=int, default=0)
    ap.add_argument("--models", default="yolov8n.pt:320,yolov8s.pt:320,yolov8s.pt:640")
    ap.add_argument("--images", default="frames")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--jpeg", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    from ultralytics.data.augment import LetterBox
    try:
        from ultralytics.utils.nms import non_max_suppression
    except ImportError:
        from ultralytics.utils.ops import non_max_suppression
    torch.set_num_threads(a.threads or os.cpu_count())
    dev = torch.device(a.device)
    gpu = dev.type == "cuda"
    sync = torch.cuda.synchronize if gpu else (lambda: None)
    dt = torch.float16 if a.half else torch.float32
    imgs = [cv2.imread(f) for f in sorted(glob.glob(os.path.join(a.images, "*.jpg")))[: a.n + 3]]
    res = {"device": a.device, "half": a.half, "threads": torch.get_num_threads(), "models": {}, "jpeg": {}}
    for spec in a.models.split(","):
        w, sz = spec.split(":")
        sz = int(sz)
        m = load_model(w, dev, a.half)
        lb = LetterBox((sz, sz), auto=False)
        tt = []
        with torch.inference_mode():
            for i, img in enumerate(imgs):
                sync()
                t0 = time.perf_counter()
                im = lb(image=img)
                x = (torch.from_numpy(np.ascontiguousarray(im[..., ::-1].transpose(2, 0, 1))).to(dev).to(dt) / 255).unsqueeze(0)
                o = m(x)
                non_max_suppression(o[0] if isinstance(o, (list, tuple)) else o, 0.25, 0.45)
                sync()
                if i >= 3:
                    tt.append((time.perf_counter() - t0) * 1e3)
        res["models"][f"{os.path.basename(w)[:-3]}_{sz}"] = {"median_ms": statistics.median(tt), "p95_ms": float(np.percentile(tt, 95))}
        print(spec, round(statistics.median(tt), 1), flush=True)
    if a.jpeg:
        for sz in (640, 480, 320):
            lb = LetterBox((sz, sz), auto=False)
            for q in (90, 50, 35):
                b, e = [], []
                for img in imgs[3:]:
                    t0 = time.perf_counter()
                    im = lb(image=img)
                    ok, buf = cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, q])
                    e.append((time.perf_counter() - t0) * 1e3)
                    b.append(len(buf))
                res["jpeg"][f"{sz}_q{q}"] = {"bytes": float(np.mean(b)), "enc_ms": statistics.median(e)}
        print(json.dumps(res["jpeg"]))
    json.dump(res, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
