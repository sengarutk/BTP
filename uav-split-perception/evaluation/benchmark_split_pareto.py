#!/usr/bin/env python3
"""Measures, on real COCO val2017 frames, everything the system model needs per configuration.

For every cut k in {2,4,5,7,9,12,15,18} and wire precision, on N letterboxed 640x640 images:
  * wire size of the actual packet (mean and p95; entropy-coded modes vary per image),
  * host timings, each stage timed separately with CUDA synchronisation after warm-up:
    edge DNN prefix, quantization, serialization, deserialization, dequantization,
    cloud DNN suffix, NMS; plus the full model + NMS for onboard inference.
For JPEG/WebP offload: encoded size and host encode / decode time on the same frames.
Accuracy is merged from accuracy_mAP_results.csv and codec_baselines.csv (never assumed).

Outputs: split_pareto_analysis.csv (split + onboard configs) and codec_offload.csv.
"""

import argparse
import csv
import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, List

import cv2
import numpy as np
import torch
from ultralytics import YOLO
from ultralytics.data.augment import LetterBox
from ultralytics.utils import nms

from core.dynamic_submodels import DynamicCloudSubmodel, DynamicEdgeSubmodel
from protocol.packet import AegisPacketProtocol
from quantization.quantizer import FeatureMapQuantizer
from utils.logger import get_logger

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS = REPO_ROOT / "experiments" / "results"
logger = get_logger("SplitPareto")

CUTS = [2, 4, 5, 7, 9, 12, 15, 18]
DTYPES = ["int8", "fp16", "fp32", "int8_zstd"]
K4_EXTRA = ["int8_per_channel", "uint8", "uint8_zstd"]
CODECS = [("JPEG", q) for q in (50, 75, 90, 95)] + [("WebP", q) for q in (50, 75, 90)]
# Accuracy source for each wire mode: zstd is lossless, so it inherits the un-compressed mode.
ACCURACY_ALIAS = {"int8_zstd": "int8", "uint8_zstd": "uint8"}


def load_frames(n: int, imgsz: int = 640) -> List[np.ndarray]:
    img_dir = REPO_ROOT / "datasets" / "coco" / "images" / "val2017"
    files = sorted(img_dir.glob("*.jpg"))[:n]
    if len(files) < n:
        raise FileNotFoundError("COCO val2017 not prepared; run scripts/prepare_datasets.py")
    lb = LetterBox((imgsz, imgsz), auto=False)
    return [lb(image=cv2.imread(str(f))) for f in files]


def to_tensor(bgr: np.ndarray, device: str) -> torch.Tensor:
    rgb = np.ascontiguousarray(bgr[:, :, ::-1])
    return torch.from_numpy(rgb).permute(2, 0, 1)[None].float().div(255.0).to(device)


class Timer:
    def __init__(self, device: str):
        self.cuda = device.startswith("cuda")

    def __call__(self, fn: Callable[[], Any]):
        if self.cuda:
            torch.cuda.synchronize()
        t0 = time.perf_counter()
        out = fn()
        if self.cuda:
            torch.cuda.synchronize()
        return out, (time.perf_counter() - t0) * 1000.0


def stats(values: List[float], prefix: str, rng: np.random.Generator) -> Dict[str, float]:
    a = np.asarray(values, dtype=float)
    boots = [a[rng.integers(0, a.size, a.size)].mean() for _ in range(1000)]
    return {f"{prefix}_mean": round(float(a.mean()), 4), f"{prefix}_p50": round(float(np.median(a)), 4),
            f"{prefix}_p95": round(float(np.percentile(a, 95)), 4),
            f"{prefix}_ci_low": round(float(np.percentile(boots, 2.5)), 4),
            f"{prefix}_ci_high": round(float(np.percentile(boots, 97.5)), 4)}


def load_accuracy() -> Dict[str, Dict[str, str]]:
    with open(RESULTS / "accuracy_mAP_results.csv", newline="", encoding="utf-8") as f:
        return {r["config"]: r for r in csv.DictReader(f)}


def accuracy_for(acc: Dict[str, Dict[str, str]], cut: int, dtype: str) -> Dict[str, Any]:
    key = f"k{cut}_{ACCURACY_ALIAS.get(dtype, dtype)}"
    if dtype == "fp32":
        key = "full_fp32"  # FP32 splits are bit-identical to the monolithic model (verified)
    if key not in acc:
        raise KeyError(f"No measured accuracy for {key}; run evaluation/evaluate_mAP.py")
    r = acc[key]
    return {"accuracy_source": key, "map50": float(r["map50"]), "map50_95": float(r["map50_95"]),
            "delta_map50_95": float(r["delta_map50_95"]),
            "delta_map50_95_ci_low": float(r["delta_map50_95_ci_low"]),
            "delta_map50_95_ci_high": float(r["delta_map50_95_ci_high"])}


def run(weights: str, device: str, n_images: int, warmup: int) -> None:
    rng = np.random.default_rng(0)
    frames = load_frames(n_images)
    xs = [to_tensor(f, device) for f in frames]
    base = YOLO(weights).model.to(device).eval()
    topo = json.loads((RESULTS / "yolov8s_graph_topology.json").read_text())["splits"]
    acc = load_accuracy()
    timer = Timer(device)
    rows: List[Dict[str, Any]] = []

    def postprocess(out):
        return nms.non_max_suppression(out[0] if isinstance(out, (list, tuple)) else out, conf_thres=0.25, iou_thres=0.45)

    # Onboard (monolithic) configuration.
    with torch.no_grad():
        for x in xs[:warmup]:
            postprocess(base(x))
        full = [timer(lambda x=x: postprocess(base(x)))[1] for x in xs]
    full_row = {"config": "full_fp32", "kind": "onboard", "cut": 22, "dtype": "fp32",
                "edge_flop_pct": topo["full"]["edge_flop_pct"], "edge_param_pct": 100.0,
                "payload_bytes_mean": 0.0, "payload_bytes_p95": 0.0, "payload_kib_mean": 0.0,
                "host_edge_ms": round(float(np.mean(full)), 4), **stats(full, "host_full", rng),
                **{k: 0.0 for k in ("host_quant_ms", "host_serialize_ms", "host_deserialize_ms",
                                    "host_dequant_ms", "host_cloud_ms", "host_nms_ms")},
                **accuracy_for(acc, 22, "fp32")}
    full_row["accuracy_source"] = "full_fp32"
    rows.append(full_row)
    logger.info(f"Onboard full model + NMS on host: {full_row['host_edge_ms']:.2f} ms")

    for cut in CUTS:
        edge = DynamicEdgeSubmodel(base, cut).to(device)
        cloud = DynamicCloudSubmodel(base, cut).to(device)
        with torch.no_grad():
            for x in xs[:warmup]:
                postprocess(cloud(edge(x)))
            acts, t_edge = zip(*[timer(lambda x=x: edge(x)) for x in xs])
            outs, t_cloud = zip(*[timer(lambda a=a: cloud(a)) for a in acts])
            _, t_nms = zip(*[timer(lambda o=o: postprocess(o)) for o in outs])
        for dtype in DTYPES + (K4_EXTRA if cut == 4 else []):
            sizes, tq, ts, td, tdq = [], [], [], [], []
            for i, a in enumerate(acts):
                (q, s), t1 = timer(lambda a=a: FeatureMapQuantizer.quantize(a, dtype=dtype))
                pkt, t2 = timer(lambda q=q, s=s, i=i: AegisPacketProtocol.serialize(i, 0, cut, dtype, q, s))
                parsed, t3 = timer(lambda pkt=pkt: AegisPacketProtocol.deserialize(pkt, device=device))
                _, t4 = timer(lambda p=parsed: FeatureMapQuantizer.dequantize(
                    p["reconstructed_data"], p["scales"], dtype=dtype, device=device))
                if i >= warmup or len(acts) <= warmup:
                    sizes.append(len(pkt)); tq.append(t1); ts.append(t2); td.append(t3); tdq.append(t4)
            row = {"config": f"k{cut}_{dtype}", "kind": "split", "cut": cut, "dtype": dtype,
                   "edge_flop_pct": topo[f"k{cut}"]["edge_flop_pct"], "edge_param_pct": topo[f"k{cut}"]["edge_param_pct"],
                   "payload_bytes_mean": round(float(np.mean(sizes)), 1),
                   "payload_bytes_p95": round(float(np.percentile(sizes, 95)), 1),
                   "payload_kib_mean": round(float(np.mean(sizes)) / 1024.0, 2),
                   "host_edge_ms": round(float(np.mean(t_edge)), 4),
                   "host_quant_ms": round(float(np.mean(tq)), 4), "host_serialize_ms": round(float(np.mean(ts)), 4),
                   "host_deserialize_ms": round(float(np.mean(td)), 4), "host_dequant_ms": round(float(np.mean(tdq)), 4),
                   "host_cloud_ms": round(float(np.mean(t_cloud)), 4), "host_nms_ms": round(float(np.mean(t_nms)), 4),
                   **stats([e + q + s + d + dq + c + n for e, q, s, d, dq, c, n in
                            zip(t_edge, tq, ts, td, tdq, t_cloud, t_nms)], "host_e2e", rng),
                   **accuracy_for(acc, cut, dtype)}
            rows.append(row)
            logger.info(f"k{cut:<2} {dtype:<16} {row['payload_kib_mean']:8.1f} KiB  edge {row['host_edge_ms']:.2f} ms  "
                        f"cloud {row['host_cloud_ms']:.2f} ms  dmAP {row['delta_map50_95']:+.4f}")
        del edge, cloud, acts, outs

    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(RESULTS / "split_pareto_analysis.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    (RESULTS / "split_pareto_analysis.json").write_text(json.dumps(
        {"n_images": n_images, "device": device, "gpu": torch.cuda.get_device_name(0) if device.startswith("cuda") else "cpu",
         "rows": rows}, indent=2), encoding="utf-8")

    # Codec offload: size and host encode/decode time on the same letterboxed frames.
    with open(RESULTS / "codec_baselines.csv", newline="", encoding="utf-8") as f:
        codec_acc = {(r["codec_name"], int(r["param"])): r for r in csv.DictReader(f)}
    codec_rows = []
    for codec, q in CODECS:
        ext, flag = (".jpg", cv2.IMWRITE_JPEG_QUALITY) if codec == "JPEG" else (".webp", cv2.IMWRITE_WEBP_QUALITY)
        sizes, t_enc, t_dec = [], [], []
        for i, fr in enumerate(frames):
            t0 = time.perf_counter(); ok, enc = cv2.imencode(ext, fr, [flag, q]); te = (time.perf_counter() - t0) * 1000
            t0 = time.perf_counter(); cv2.imdecode(enc, cv2.IMREAD_COLOR); tdc = (time.perf_counter() - t0) * 1000
            if i >= warmup:
                sizes.append(len(enc)); t_enc.append(te); t_dec.append(tdc)
        r = codec_acc[(codec, q)]
        codec_rows.append({
            "config": f"{codec.lower()}_q{q}", "codec": codec, "setting": f"q{q}",
            "payload_bytes_mean": round(float(np.mean(sizes)), 1), "payload_kib_mean": round(float(np.mean(sizes)) / 1024, 2),
            "host_encode_ms": round(float(np.mean(t_enc)), 4), "host_decode_ms": round(float(np.mean(t_dec)), 4),
            "host_cloud_ms": round(float(np.mean(t_dec)) + full_row["host_edge_ms"], 4),
            "map50": float(r["map50"]), "map50_95": float(r["map50_95"]), "delta_map50_95": float(r["delta_map50_95"]),
            "delta_map50_95_ci_low": float(r["delta_map50_95_ci_low"]),
            "delta_map50_95_ci_high": float(r["delta_map50_95_ci_high"])})
        logger.info(f"{codec} q{q}: {codec_rows[-1]['payload_kib_mean']:.1f} KiB, encode {codec_rows[-1]['host_encode_ms']:.2f} ms")
    with open(RESULTS / "codec_offload.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(codec_rows[0].keys()))
        w.writeheader()
        w.writerows(codec_rows)
    logger.success(f"Wrote {len(rows)} split/onboard and {len(codec_rows)} codec configurations")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--weights", default="yolov8s.pt")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--images", type=int, default=200)
    ap.add_argument("--warmup", type=int, default=10)
    args = ap.parse_args()
    run(args.weights, args.device, args.images, args.warmup)
