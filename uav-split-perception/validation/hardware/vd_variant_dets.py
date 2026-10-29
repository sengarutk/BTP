#!/usr/bin/env python3
"""VisDrone-trained detections of every perception variant on every test frame, for replaying the earlier
campaigns with the VisDrone weights (report_rescore.py --visdrone).

Each variant is reproduced exactly as the live system computes it: onboard variants letterbox the camera frame and
run FP32 (as the Pi's Onboard engine); path variants letterbox, JPEG-encode at the variant's quality with cv2 (as the
camera), decode (as the worker) and run FP16 on the GPU (as the workers). NMS is the system's fast_nms (conf 0.01,
the campaigns' setting, IoU 0.45, 100 boxes). Boxes stay in the variant's letterboxed input coordinates, the same
format as the runs' recorded _dets.npz, so stream_ap.evaluate unletterboxes them identically.
The models are the VisDrone fine-tuned weights/<model>_visdrone.pt (same architectures as the COCO models the
campaigns ran, hence the same timing; only the detections differ).
usage: vd_variant_dets.py [--variants n320,s640q90,...]   -> experiments/results/hardware/vd_variant_dets/<variant>.npz
"""
import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from hwbench import fast_nms, load_model  # noqa: E402

ROOT = HERE.parent.parent
VID = ROOT / "datasets" / "visdrone_vid_640"
OUT = ROOT / "experiments" / "results" / "hardware" / "vd_variant_dets"
ONBOARD = {"n320": ("yolov8n", 320), "s320": ("yolov8s", 320), "s640": ("yolov8s", 640)}
PATHV = {f"s{r}q{q}": ("yolov8s", r, q) for r in (640, 480, 320) for q in (90, 50)}
PATHV.update({"m640q90": ("yolov8m", 640, 90), "m640q50": ("yolov8m", 640, 50)})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variants", default=",".join(list(ONBOARD) + list(PATHV)))
    ap.add_argument("--device", default="cuda")
    a = ap.parse_args()
    from ultralytics.data.augment import LetterBox
    OUT.mkdir(parents=True, exist_ok=True)
    dev = torch.device(a.device)
    keys = [(sq, i) for sq, n in json.load(open(VID / "sequences.json")) for i in range(1, n + 1)]
    frames = {k: cv2.imread(str(VID / k[0] / ("%07d.jpg" % k[1]))) for k in keys}
    models = {}
    for var in a.variants.split(","):
        f = OUT / f"{var}.npz"
        if f.exists():
            continue
        onb = var in ONBOARD
        model, res, q = (ONBOARD[var] + (None,)) if onb else PATHV[var]
        half = not onb and dev.type == "cuda"
        w = ROOT / "weights" / f"{model}_visdrone.pt"
        if not w.exists():
            print(f"{var}: {w.name} missing, skipped", flush=True)
            continue
        if (model, half) not in models:
            models[(model, half)] = load_model(str(w), dev, half)
        m = models[(model, half)]
        lb = LetterBox((res, res), auto=False)
        out = {}
        with torch.inference_mode():
            for k in keys:
                im = lb(image=frames[k])
                if q is not None:
                    ok, buf = cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, q])
                    im = cv2.imdecode(buf, cv2.IMREAD_COLOR)
                x = torch.from_numpy(np.ascontiguousarray(im[..., ::-1].transpose(2, 0, 1))).to(dev)
                x = (x.half() if half else x.float()) / 255.0
                o = m(x.unsqueeze(0))
                det = fast_nms(o[0] if isinstance(o, (list, tuple)) else o, 0.01, 0.45, 100)
                out[f"{k[0]}/{k[1]}"] = det.float().cpu().numpy().astype(np.float32)
        np.savez_compressed(f, **out)
        print(var, "done", len(out), "frames", flush=True)


if __name__ == "__main__":
    main()
