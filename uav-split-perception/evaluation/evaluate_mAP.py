#!/usr/bin/env python3
"""Detection accuracy of every split point and precision mode on COCO val2017.

For each configuration, exactly the tensors that cross the edge/cloud boundary are
quantized and dequantized (see detection_eval.install_split_quant_hooks); everything else
runs in FP32. Validation uses batch=1 so dynamic scales are computed per image, as they
would be on the drone. Differences to the FP32 baseline carry 95% paired-bootstrap CIs.

FP32 splits are mathematically identical to the monolithic model (verified bit-exact in
core/dynamic_submodels.py); k4-FP32 is still evaluated once as an end-to-end sanity check.
"""

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, List

import torch
from ultralytics import YOLO

from evaluation.detection_eval import DEFAULT_DATASET, paired_bootstrap, run_validation, summary_row
from utils.logger import get_logger

REPO_ROOT = Path(__file__).resolve().parent.parent
logger = get_logger("EvaluateMAP")

CUTS = [2, 4, 5, 7, 9, 12, 15, 18]
SPLIT_DTYPES = ["int8", "fp16"]
EXTRA_K4_MODES = ["int8_per_channel", "uint8", "uint8_clip"]


def configurations() -> List[Dict[str, Any]]:
    cfgs = [{"name": "full_fp32", "split_tag": "full", "cut": 22, "dtype": "fp32"},
            {"name": "k4_fp32", "split_tag": "k4", "cut": 4, "dtype": "fp32"}]
    for k in CUTS:
        for dt in SPLIT_DTYPES:
            cfgs.append({"name": f"k{k}_{dt}", "split_tag": f"k{k}", "cut": k, "dtype": dt})
    for dt in EXTRA_K4_MODES:
        cfgs.append({"name": f"k4_{dt}", "split_tag": "k4", "cut": 4, "dtype": dt})
    return cfgs


def run(weights: str, data: str, device: str, output_dir: Path, n_boot: int) -> List[Dict[str, Any]]:
    yolo = YOLO(weights)
    results: Dict[str, Dict[str, Any]] = {}
    for cfg in configurations():
        hook = None if cfg["split_tag"] == "full" else (cfg["cut"], cfg["dtype"])
        logger.info(f"Validating {cfg['name']} on {data}...")
        res = run_validation(yolo, data, device, name=cfg["name"], split_hook=hook)
        results[cfg["name"]] = {**cfg, **res}
        logger.info(f"  mAP50={res['map50']:.4f}  mAP50-95={res['map50_95']:.4f}  ({res['num_images']} images)")

    base = results["full_fp32"]
    if abs(results["k4_fp32"]["map50_95"] - base["map50_95"]) > 1e-9:
        raise AssertionError("k4-FP32 split differs from the monolithic baseline; split is not exact")

    rows = []
    for name, res in results.items():
        row = {k: v for k, v in summary_row(res).items() if k != "name"}
        row["config"] = name
        if name == "full_fp32":
            row.update({"delta_map50": 0.0, "delta_map50_ci_low": 0.0, "delta_map50_ci_high": 0.0,
                        "delta_map50_95": 0.0, "delta_map50_95_ci_low": 0.0, "delta_map50_95_ci_high": 0.0})
        else:
            row.update(paired_bootstrap(base, res, n_boot=n_boot))
        rows.append(row)
        logger.info(f"{name:>20}: dmAP50-95 = {row['delta_map50_95']:+.4f} "
                    f"[{row['delta_map50_95_ci_low']:+.4f}, {row['delta_map50_95_ci_high']:+.4f}]")

    output_dir.mkdir(parents=True, exist_ok=True)
    fields = ["config", "split_tag", "cut", "dtype", "num_images", "precision", "recall", "map50", "map50_95",
              "delta_map50", "delta_map50_ci_low", "delta_map50_ci_high",
              "delta_map50_95", "delta_map50_95_ci_low", "delta_map50_95_ci_high", "n_boot"]
    with open(output_dir / "accuracy_mAP_results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    (output_dir / "accuracy_mAP_results.json").write_text(json.dumps(
        {"dataset": data, "weights": weights, "batch": 1, "ci": "95% paired image bootstrap", "results": rows},
        indent=2), encoding="utf-8")
    logger.success(f"Wrote {len(rows)} configurations to {output_dir / 'accuracy_mAP_results.csv'}")
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--weights", default="yolov8s.pt")
    ap.add_argument("--data", default=DEFAULT_DATASET, help="coco_val2017 (default), coco128, or a YAML path")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--output-dir", default=str(REPO_ROOT / "experiments" / "results"))
    ap.add_argument("--n-boot", type=int, default=300)
    args = ap.parse_args()
    run(args.weights, args.data, args.device, Path(args.output_dir), args.n_boot)
