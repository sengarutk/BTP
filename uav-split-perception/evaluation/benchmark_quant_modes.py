#!/usr/bin/env python3
"""Numerical fidelity of each wire precision on real k4 activations (COCO val2017 frames).

For every mode: SQNR, relative max error, cosine similarity, and -- for the symmetric INT8
modes -- the worst ratio max|X - X_hat| / (S/2), which Proposition 1 of the paper bounds by 1. Accuracy and
payload are merged from accuracy_mAP_results.csv and split_pareto_analysis.csv.
"""

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import torch
from ultralytics import YOLO

from core.dynamic_submodels import DynamicEdgeSubmodel
from evaluation.benchmark_split_pareto import load_frames, to_tensor
from quantization.quantizer import FeatureMapQuantizer, compute_reconstruction_metrics
from utils.logger import get_logger

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS = REPO_ROOT / "experiments" / "results"
logger = get_logger("QuantModes")

MODES = ["fp16", "int8", "int8_per_channel", "uint8", "uint8_clip"]


def bound_ratio(x: torch.Tensor, q: torch.Tensor, s, mode: str) -> float:
    xh = FeatureMapQuantizer.dequantize(q, s, dtype=mode, device=x.device)
    err = (x - xh).abs()
    if mode == "int8":
        return float(err.max() / (float(s) / 2))
    if mode == "int8_per_channel":
        half = (torch.as_tensor(s, device=x.device).view(1, -1, 1, 1) / 2)
        return float((err / half).amax())
    return float("nan")


def run(weights: str, device: str, n_images: int, cut: int = 4) -> List[Dict]:
    frames = load_frames(n_images)
    base = YOLO(weights).model.to(device).eval()
    edge = DynamicEdgeSubmodel(base, cut).to(device)
    with open(RESULTS / "accuracy_mAP_results.csv", newline="", encoding="utf-8") as f:
        acc = {r["config"]: r for r in csv.DictReader(f)}
    with open(RESULTS / "split_pareto_analysis.csv", newline="", encoding="utf-8") as f:
        pareto = {r["config"]: r for r in csv.DictReader(f)}

    per_mode: Dict[str, Dict[str, list]] = {m: {"sqnr": [], "cos": [], "relmax": [], "ratio": []} for m in MODES}
    with torch.no_grad():
        for fr in frames:
            x = edge(to_tensor(fr, device)).float()
            for m in MODES:
                q, s = FeatureMapQuantizer.quantize(x, dtype=m)
                xh = FeatureMapQuantizer.dequantize(q, s, dtype=m, device=device)
                met = compute_reconstruction_metrics(x, xh)
                per_mode[m]["sqnr"].append(met["sqnr_db"])
                per_mode[m]["cos"].append(met["cosine_similarity"])
                per_mode[m]["relmax"].append(met["max_abs_error"] / float(x.abs().max()))
                per_mode[m]["ratio"].append(bound_ratio(x, q, s, m))

    rows = []
    for m in MODES:
        acc_key = f"k{cut}_{m}"
        pay_key = f"k{cut}_{'uint8' if m == 'uint8_clip' else m}"
        a = acc.get(acc_key)
        pr = pareto.get(pay_key)
        d = per_mode[m]
        rows.append({
            "mode": m,
            "sqnr_db_mean": round(float(np.mean(d["sqnr"])), 2), "sqnr_db_min": round(float(np.min(d["sqnr"])), 2),
            "cosine_min": round(float(np.min(d["cos"])), 6),
            "rel_max_error_mean": round(float(np.mean(d["relmax"])), 5),
            "bound_ratio_max": round(float(np.nanmax(d["ratio"])), 4) if m.startswith("int8") else "",
            "payload_kib": round(float(pr["payload_bytes_mean"]) / 1024, 1) if pr else "",
            "host_quant_ms": float(pr["host_quant_ms"]) if pr else "",
            "host_dequant_ms": float(pr["host_dequant_ms"]) if pr else "",
            "map50_95": float(a["map50_95"]) if a else "",
            "delta_map50_95": float(a["delta_map50_95"]) if a else "",
            "delta_map50_95_ci_low": float(a["delta_map50_95_ci_low"]) if a else "",
            "delta_map50_95_ci_high": float(a["delta_map50_95_ci_high"]) if a else "",
            "n_images": n_images,
        })
        logger.info(f"{m:>17}: SQNR {rows[-1]['sqnr_db_mean']:6.2f} dB, bound ratio {rows[-1]['bound_ratio_max']}")
    with open(RESULTS / "quantization_modes_benchmark.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    (RESULTS / "quantization_modes_benchmark.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--weights", default="yolov8s.pt")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--images", type=int, default=200)
    args = ap.parse_args()
    run(args.weights, args.device, args.images)
