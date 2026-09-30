#!/usr/bin/env python3
"""Generalization, part 2: rate and accuracy across models, bit widths, resolutions and aerial imagery.

Each configuration is validated with Ultralytics (batch 1) exactly as in evaluate_mAP.py /
benchmark_codecs.py, and its wire size is logged on the same images:
  * split  (cut k, n bits): every live tensor is quantized to n bits where the cloud reads it
    (detection_eval.install_split_quant_hooks); size = n-bit codes + best zstd layout (quantization/nbit.py);
  * codec  (JPEG/WebP quality q): the network input is encoded and decoded (benchmark_codecs.make_codec_hook).
Differences are against the same model's FP32 result on the same images (95% paired bootstrap).

Studies (``--study``):
  bits        YOLOv8s, 640, COCO val2017, k4 at 2..8 bits
  models      several detector families and sizes at 640 on COCO: bottleneck cut at 8/6/4 bits vs JPEG
  resolution  YOLOv8s at 320/480/960 on COCO
  aerial      YOLOv8s and YOLO11s on VisDrone val (aerial, COCO-mapped labels) at 640 and 1280
Output: experiments/results/generalization/accuracy.csv (one row per configuration).
"""

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import torch
from ultralytics import YOLO

from core.dynamic_submodels import analyze_split_dependencies
from evaluation.benchmark_codecs import make_codec_hook
from evaluation.detection_eval import paired_bootstrap, run_validation
from evaluation.gen_model_survey import weights_path
from quantization import nbit
from utils.logger import get_logger

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "experiments" / "results" / "generalization"
ROW_CACHE = REPO_ROOT / "experiments" / "cache" / "gen_accuracy"
logger = get_logger("GenAccuracy")

ACC_MODELS = ["yolov8n", "yolov8s", "yolov8m", "yolov8l", "yolo11n", "yolo11s", "yolo11m",
              "yolov5su", "yolov9s", "yolov10s"]


def bottleneck_cut(model: str) -> int:
    path = OUT / "model_summary.csv"
    if path.exists():
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["model"] == model and r["images"] == "coco" and int(r["imgsz"]) == 640:
                    return int(r["bottleneck_cut"])
    raise KeyError(f"Run gen_model_survey.py for {model} first (bottleneck cut unknown)")


def plan(study: str) -> List[Dict]:
    """(model, imgsz, dataset, kind, cut, setting) for every configuration of a study."""
    def cfgs(model, imgsz, data, cut, bits, codecs):
        out = [dict(model=model, imgsz=imgsz, data=data, kind="full", cut=-1, setting=32)]
        out += [dict(model=model, imgsz=imgsz, data=data, kind="split", cut=cut, setting=b) for b in bits]
        out += [dict(model=model, imgsz=imgsz, data=data, kind="jpeg", cut=-1, setting=q) for q in codecs]
        return out

    if study == "bits":
        return cfgs("yolov8s", 640, "coco_val2017", 4, [8, 7, 6, 5, 4, 3, 2], [75, 90, 95])
    if study == "models":
        return [c for m in ACC_MODELS for c in cfgs(m, 640, "coco_val2017", bottleneck_cut(m), [8, 6, 4], [90])]
    if study == "resolution":
        return [c for s in (320, 480, 960) for c in cfgs("yolov8s", s, "coco_val2017", 4, [8, 6, 4], [75, 90])]
    if study == "aerial":
        return [c for m in ("yolov8s", "yolo11s") for s in (640, 1280)
                for c in cfgs(m, s, "visdrone_val", 4 if m == "yolov8s" else bottleneck_cut(m), [8, 6, 4], [75, 90, 95])]
    raise ValueError(study)


def cache_name(c: Dict) -> str:
    """Validation-cache name; YOLOv8s/640/COCO reuses the names of the main accuracy study."""
    main = c["model"] == "yolov8s" and c["imgsz"] == 640 and c["data"] == "coco_val2017"
    if c["kind"] == "full":
        tag = "full_fp32"
    elif c["kind"] == "split":
        tag = f"k{c['cut']}_int{c['setting']}"
    else:
        tag = f"codec_jpeg_{c['setting']}"
    return tag if main else f"{c['model']}_{c['imgsz']}__{tag}"


def size_hooks(model: torch.nn.Module, cut: int, bits: int, log: List[int]) -> List:
    """Records the n-bit wire size of the live set of every image (does not modify activations)."""
    seq = model.model
    _, live = analyze_split_dependencies(seq, cut)
    grabbed: Dict[int, torch.Tensor] = {}
    handles = []
    for i in live:
        def grab(m, inp, out, i=i):
            grabbed[i] = out.detach()
            if i == cut:  # layer k runs last among the live layers
                log.append(nbit.wire_bytes([grabbed[j] for j in live], bits)["zstd"])
        handles.append(seq[i].register_forward_hook(grab))
    return handles


def evaluate(c: Dict, yolo_cache: Dict, n_boot: int, device: str) -> Dict:
    ROW_CACHE.mkdir(parents=True, exist_ok=True)
    name = cache_name(c)
    row_file = ROW_CACHE / f"{c['data']}__{name}.json"
    if row_file.exists():
        return json.loads(row_file.read_text())
    key = (c["model"], c["imgsz"])
    if key not in yolo_cache:
        yolo_cache.clear()
        torch.cuda.empty_cache()
        yolo_cache[key] = YOLO(weights_path(c["model"]))
    yolo = yolo_cache[key]
    base_name = cache_name({**c, "kind": "full"})
    base = run_validation(yolo, c["data"], device, name=base_name, imgsz=c["imgsz"])

    size_file = ROW_CACHE / f"{c['data']}__{name}.sizes"
    sizes: List[int] = []
    rate: Dict[str, List[float]] = {"bytes": [], "pixels": [], "enc_ms": []}
    if c["kind"] == "full":
        res = base
    elif c["kind"] == "split":
        dtype = "int8" if c["setting"] == 8 else f"int{c['setting']}"
        if size_file.exists():  # validation finished earlier; its stats are in the validation cache
            res = run_validation(yolo, c["data"], device, name=name, imgsz=c["imgsz"], split_hook=(c["cut"], dtype))
        else:
            hooks = size_hooks(yolo.model, c["cut"], c["setting"], sizes)
            try:
                res = run_validation(yolo, c["data"], device, name=name, imgsz=c["imgsz"],
                                     split_hook=(c["cut"], dtype), cache=False)
            finally:
                for h in hooks:
                    h.remove()
    else:
        if size_file.exists():
            res = run_validation(yolo, c["data"], device, name=name, imgsz=c["imgsz"])
        else:
            res = run_validation(yolo, c["data"], device, name=name, imgsz=c["imgsz"], cache=False,
                                 pre_forward_hook=make_codec_hook("JPEG", c["setting"], rate))
            sizes = rate["bytes"]
    if c["kind"] != "full":
        if size_file.exists():
            sizes = json.loads(size_file.read_text())
        else:
            size_file.write_text(json.dumps([int(v) for v in sizes]))
    row = {**c, "config": name, "num_images": res["num_images"], "map50": res["map50"], "map50_95": res["map50_95"],
           "base_map50_95": base["map50_95"], "wire_kib": round(float(np.mean(sizes)) / 1024.0, 2) if sizes else 0.0}
    if c["kind"] == "full":
        row.update(delta_map50_95=0.0, delta_map50_95_ci_low=0.0, delta_map50_95_ci_high=0.0, n_boot=0)
    else:
        bs = paired_bootstrap(base, res, n_boot=n_boot)
        row.update({k: bs[k] for k in ("delta_map50_95", "delta_map50_95_ci_low", "delta_map50_95_ci_high", "n_boot")})
    tmp = row_file.with_suffix(".tmp")
    tmp.write_text(json.dumps(row))
    tmp.replace(row_file)
    return row


def run(studies: List[str], n_boot: int, device: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    yolo_cache: Dict = {}
    for study in studies:
        for c in plan(study):
            row = evaluate(c, yolo_cache, n_boot, device)
            logger.info(f"[{study}] {row['config']:>32} {row['data']:>13}: mAP {100 * row['map50_95']:.2f} "
                        f"d {100 * row['delta_map50_95']:+.2f} [{100 * row['delta_map50_95_ci_low']:+.2f}, "
                        f"{100 * row['delta_map50_95_ci_high']:+.2f}]  {row['wire_kib']:.1f} KiB")
    rows = [json.loads(p.read_text()) for p in sorted(ROW_CACHE.glob("*.json"))]
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(OUT / "accuracy.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    logger.success(f"Wrote {len(rows)} rows -> {OUT / 'accuracy.csv'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--study", nargs="+", default=["bits", "models", "resolution", "aerial"])
    ap.add_argument("--n-boot", type=int, default=200)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()
    run(args.study, args.n_boot, args.device)
