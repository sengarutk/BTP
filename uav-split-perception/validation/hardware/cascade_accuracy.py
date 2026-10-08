#!/usr/bin/env python3
"""Accuracy of multi-hop placements: quantization at two cuts, or JPEG followed by a split.

A three-device placement Pi -> Jetson -> laptop sends tensors over two links, so it may encode
twice: the first boundary (k1) as INT8+zstd or JPEG (k1 = -1), the second (k2) as INT8+zstd or
FP16. This evaluates mAP@[.5:.95] on COCO val2017 (all 5,000 images, batch 1, per-image scales)
with both boundaries applied, using the hooks of evaluation/detection_eval.py (a tensor that
crosses both cuts is re-quantized at the second), and a paired bootstrap against the FP32 model.
Single-boundary results are already in experiments/cache/val_stats (k*_int8, k*_fp16, codec_jpeg_90).
Output: experiments/results/hardware/cascade_accuracy.csv
"""

import argparse
import csv
from pathlib import Path

from ultralytics import YOLO

from evaluation.benchmark_codecs import make_codec_hook
from evaluation.detection_eval import install_split_quant_hooks, paired_bootstrap, run_validation

OUT = Path(__file__).resolve().parent.parent.parent / "experiments" / "results" / "hardware"
CASCADES = [("jpeg90", 4, "int8"), ("jpeg90", 9, "int8"), ("jpeg90", 15, "int8"),
            ("int8", (2, 9), "int8"), ("int8", (4, 9), "int8"), ("int8", (4, 15), "int8"),
            ("int8", (4, 18), "int8"), ("int8", (9, 15), "int8"), ("int8", (9, 18), "int8"),
            ("int8", (4, 9), "fp16"), ("int8", (4, 15), "fp16"), ("int8", (9, 15), "fp16")]


def main(device, n_boot):
    yolo = YOLO("yolov8s.pt")
    base = run_validation(yolo, "coco_val2017", device, name="full_fp32")
    rows = []
    for first, cuts, second in CASCADES:
        if first == "jpeg90":
            k1, k2 = -1, cuts
            name = f"cascade_jpeg90_k{k2}_{second}"
            pre = make_codec_hook("JPEG", 90, {"bytes": [], "pixels": [], "enc_ms": []})
            res = run_validation(yolo, "coco_val2017", device, name=name, pre_forward_hook=pre, split_hook=(k2, second))
        else:
            k1, k2 = cuts
            name = f"cascade_k{k1}_int8_k{k2}_{second}"
            handles = install_split_quant_hooks(yolo.model, k1, "int8")
            try:
                res = run_validation(yolo, "coco_val2017", device, name=name, split_hook=(k2, second))
            finally:
                for h in handles:
                    h.remove()
        ci = paired_bootstrap(base, res, n_boot=n_boot)
        row = {"config": name, "first": first, "k1": k1, "k2": k2, "second": second,
               "map50_95": round(res["map50_95"], 5), "map50": round(res["map50"], 5),
               "delta_pts": round(100 * (res["map50_95"] - base["map50_95"]), 3),
               "ci_low_pts": round(100 * ci["delta_map50_95_ci_low"], 3),
               "ci_high_pts": round(100 * ci["delta_map50_95_ci_high"], 3), "images": res["num_images"]}
        print(row, flush=True)
        rows.append(row)
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "cascade_accuracy.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--device", default="0")
    ap.add_argument("--boot", type=int, default=300)
    a = ap.parse_args()
    main(a.device, a.boot)
