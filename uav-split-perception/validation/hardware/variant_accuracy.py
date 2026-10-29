#!/usr/bin/env python3
"""mAP@[.5:.95] (COCO val2017, 5,000 images, or VisDrone2019-DET val with --data visdrone_val; batch 1) of every perception variant the adaptive
controller may use: model x input size x JPEG quality (or the raw frame, for onboard inference).
Values already in experiments/cache/val_stats are reused; missing ones are evaluated with the repo's
validation code (evaluation/detection_eval.py) and the JPEG pre-hook of evaluation/benchmark_codecs.py.
Output: experiments/results/hardware/variant_accuracy.json  {"yolov8s_640_q50": 0.4092, ...}
"""
import json
import pickle
from pathlib import Path

from ultralytics import YOLO

from evaluation.benchmark_codecs import make_codec_hook
from evaluation.detection_eval import run_validation

ROOT = Path(__file__).resolve().parent.parent.parent
CACHE = ROOT / "experiments" / "cache" / "val_stats" / "coco_val2017"
VARIANTS = [("yolov8s", 640, None), ("yolov8s", 640, 90), ("yolov8s", 640, 50), ("yolov8s", 640, 35),
            ("yolov8s", 320, None), ("yolov8s", 320, 90), ("yolov8s", 320, 50),
            ("yolov8s", 480, 90), ("yolov8s", 480, 50),
            ("yolov8n", 640, None), ("yolov8n", 320, None),
            ("yolov8m", 640, None), ("yolov8m", 640, 90), ("yolov8m", 640, 50),
            ("yolov8l", 640, None)]                                     # onboard-model comparison (20 Oct)
# the same variants with the VisDrone fine-tuned weights (weights/<model>_visdrone.pt, scripts/train_visdrone.py)
VARIANTS += [(m + "_visdrone", r, q) for m, r, q in VARIANTS if m in ("yolov8n", "yolov8s", "yolov8m", "yolov8l")]
# YOLO11 n/s/m fine-tuned on VisDrone (25 Oct 2026, the professor's request), raw frame at 640 for onboard inference
VARIANTS += [(m, 640, None) for m in ("yolo11n_visdrone", "yolo11s_visdrone", "yolo11m_visdrone")]


def cache_name(model, imgsz, q, data):
    tail = "full_fp32" if q is None else f"codec_jpeg_{q}"
    if data == "coco_val2017" and (model, imgsz) == ("yolov8s", 640):
        return tail
    return f"{model}_{imgsz}__{tail}"


def main(data, out_name):
    out = {}
    cache = ROOT / "experiments" / "cache" / "val_stats" / ("coco_val2017" if data == "coco_val2017" else data)
    for model, imgsz, q in VARIANTS:
        name = cache_name(model, imgsz, q, data)
        f = cache / f"{name}.pkl"
        if f.exists():
            m = pickle.load(open(f, "rb"))["map50_95"]
        else:
            w = str(ROOT / ("yolov8s.pt" if model == "yolov8s" else f"weights/{model}.pt"))
            if not Path(w).exists():             # e.g. a model still training: left out of this table
                print("skipped (no weights):", model, imgsz, q, flush=True)
                continue
            hook = None if q is None else make_codec_hook("JPEG", q, {"bytes": [], "pixels": [], "enc_ms": []})
            m = run_validation(YOLO(w), data, "0", name=name, imgsz=imgsz, pre_forward_hook=hook)["map50_95"]
        key = f"{model}_{imgsz}_{'raw' if q is None else 'q%d' % q}"
        out[key] = round(float(m), 4)
        print(key, out[key], flush=True)
    (ROOT / "experiments" / "results" / "hardware").mkdir(parents=True, exist_ok=True)
    json.dump(out, open(ROOT / "experiments" / "results" / "hardware" / out_name, "w"), indent=1)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="coco_val2017", help="coco_val2017 or visdrone_val (VisDrone2019-DET val, 548 images)")
    ap.add_argument("--out", default="variant_accuracy.json")
    a = ap.parse_args()
    main(a.data, a.out)
