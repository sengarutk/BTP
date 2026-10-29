#!/usr/bin/env python3
"""Task R3 input (25 Oct 2026): mAP of every image-codec offload setting of the swarm study (codec_offload.csv:
JPEG q50/75/90/95, WebP q50/75/90) with the VisDrone fine-tuned YOLOv8s at 640 on VisDrone2019-DET val, with the
same evaluator and codec pre-hook as variant_accuracy.py (results cached in experiments/cache/val_stats/visdrone_val).
Output: experiments/results/visdrone_ft_split/codec_accuracy.json  {"jpeg_q90": {"map50_95": .., "map50": ..}, ...}
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from ultralytics import YOLO  # noqa: E402

from evaluation.benchmark_codecs import make_codec_hook  # noqa: E402
from evaluation.detection_eval import run_validation  # noqa: E402

SETTINGS = [("jpeg", "JPEG", q) for q in (50, 75, 90, 95)] + [("webp", "WebP", q) for q in (50, 75, 90)]


def main():
    w = str(ROOT / "weights" / "yolov8s_visdrone.pt")
    out = {}
    base = run_validation(YOLO(w), "visdrone_val", "0", name="yolov8s_visdrone_640__full_fp32", imgsz=640)
    out["full_fp32"] = {"map50_95": float(base["map50_95"]), "map50": float(base["map50"])}
    for tag, codec, q in SETTINGS:
        hook = make_codec_hook(codec, q, {"bytes": [], "pixels": [], "enc_ms": []})
        r = run_validation(YOLO(w), "visdrone_val", "0", name=f"yolov8s_visdrone_640__codec_{tag}_{q}", imgsz=640,
                           pre_forward_hook=hook)
        out[f"{tag}_q{q}"] = {"map50_95": float(r["map50_95"]), "map50": float(r["map50"])}
        print(f"{tag}_q{q}", round(out[f"{tag}_q{q}"]["map50_95"], 4), flush=True)
    d = ROOT / "experiments" / "results" / "visdrone_ft_split"
    d.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(d / "codec_accuracy.json", "w"), indent=1)


if __name__ == "__main__":
    main()
