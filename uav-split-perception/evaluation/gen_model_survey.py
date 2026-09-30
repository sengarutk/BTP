#!/usr/bin/env python3
"""Generalization, part 1: split payloads across detector families, sizes, resolutions and image content.

For every model x input size x image set (COCO val2017 ground-level photos, VisDrone aerial frames):
  * exactness: edge->cloud output equals the monolithic output (torch.equal) at every cut;
  * per cut k: onboard FLOP fraction, live set, INT8 elements, and the INT8+zstd wire size of real
    packets (protocol/packet.py) averaged over real letterboxed frames;
  * the bottleneck cut (smallest INT8+zstd payload), and there: n-bit sizes for n = 2..7
    (quantization/nbit.py), zstd level 19, and host timings (full model, edge part, quantize+serialize);
  * codec sizes on the same frames (JPEG, WebP, PNG), which do not depend on the model.
Accuracy is measured separately (gen_accuracy.py); this script needs no labels.

Outputs (experiments/results/generalization/): model_cuts.csv, model_summary.csv, codec_sizes.csv.
"""

import argparse
import csv
import time
from pathlib import Path
from typing import Dict, List

import cv2
import numpy as np
import thop
import torch
from ultralytics import YOLO
from ultralytics.data.augment import LetterBox
from ultralytics.utils import nms

from core.dynamic_submodels import DynamicCloudSubmodel, DynamicEdgeSubmodel, analyze_split_dependencies
from protocol.packet import AegisPacketProtocol
from quantization import nbit
from quantization.quantizer import FeatureMapQuantizer
from utils.logger import get_logger

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "experiments" / "results" / "generalization"
logger = get_logger("ModelSurvey")

IMAGE_SETS = {
    "coco": REPO_ROOT / "datasets" / "coco" / "images" / "val2017",
    "visdrone": REPO_ROOT / "datasets" / "visdrone" / "VisDrone2019-DET-val" / "images",
}
DEFAULT_MODELS = ["yolov5nu", "yolov5su", "yolov5mu", "yolov8n", "yolov8s", "yolov8m", "yolov8l", "yolov8x",
                  "yolov9t", "yolov9s", "yolov9m", "yolov10n", "yolov10s", "yolov10m",
                  "yolo11n", "yolo11s", "yolo11m", "yolo11l", "yolo11x"]
CODECS = [("jpeg", q) for q in (50, 75, 90, 95)] + [("webp", q) for q in (50, 75, 90)] + [("png", 3)]
BITS = [2, 3, 4, 5, 6, 7]


def weights_path(model: str) -> str:
    for p in (REPO_ROOT / f"{model}.pt", REPO_ROOT / "weights" / f"{model}.pt"):
        if p.exists():
            return str(p)
    return f"{model}.pt"  # let Ultralytics download it


def load_frames(image_set: str, n: int, imgsz: int) -> List[np.ndarray]:
    files = sorted(IMAGE_SETS[image_set].glob("*.jpg"))[:n]
    if len(files) < n:
        raise FileNotFoundError(f"{IMAGE_SETS[image_set]} has {len(files)} images, need {n}")
    lb = LetterBox((imgsz, imgsz), auto=False)
    return [lb(image=cv2.imread(str(f))) for f in files]


def to_tensor(bgr: np.ndarray, device: str) -> torch.Tensor:
    return torch.from_numpy(np.ascontiguousarray(bgr[:, :, ::-1])).permute(2, 0, 1)[None].float().div(255.0).to(device)


def codec_sizes(frames: List[np.ndarray]) -> Dict[str, Dict[str, float]]:
    out = {}
    for codec, q in CODECS:
        ext, params = {"jpeg": (".jpg", [cv2.IMWRITE_JPEG_QUALITY, q]), "webp": (".webp", [cv2.IMWRITE_WEBP_QUALITY, q]),
                       "png": (".png", [cv2.IMWRITE_PNG_COMPRESSION, q])}[codec]
        sizes, times = [], []
        for fr in frames:
            t0 = time.perf_counter()
            ok, enc = cv2.imencode(ext, fr, params)
            times.append((time.perf_counter() - t0) * 1000.0)
            sizes.append(len(enc))
        out[f"{codec}_q{q}"] = {"bytes": float(np.mean(sizes)), "enc_ms": float(np.median(times))}
    return out


def _as_tensors(acts) -> List[torch.Tensor]:
    return list(acts.values()) if isinstance(acts, dict) else [acts]


def check_parity(base: torch.nn.Module, n_layers: int) -> int:
    """Number of cuts whose split output is bit-identical to the monolithic model (CPU, 320x320 input)."""
    x = torch.rand(1, 3, 320, 320, generator=torch.Generator().manual_seed(0))
    with torch.no_grad():
        ref = base(x)
        ref = ref[0] if isinstance(ref, (list, tuple)) else ref
        exact = 0
        for k in range(n_layers - 1):
            out = DynamicCloudSubmodel(base, k, share_modules=True)(DynamicEdgeSubmodel(base, k)(x))
            out = out[0] if isinstance(out, (list, tuple)) else out
            exact += int(torch.equal(out, ref))
    return exact


class Timer:
    def __init__(self, device: str):
        self.cuda = device.startswith("cuda")

    def __call__(self, fn):
        if self.cuda:
            torch.cuda.synchronize()
        t0 = time.perf_counter()
        out = fn()
        if self.cuda:
            torch.cuda.synchronize()
        return out, (time.perf_counter() - t0) * 1000.0


def survey_model(model: str, imgsz: int, image_set: str, frames: List[np.ndarray], codecs: Dict,
                 device: str, parity: bool) -> (List[Dict], Dict):
    yolo = YOLO(weights_path(model))
    base_cpu = yolo.model.float().eval()
    seq = base_cpu.model
    n_layers = len(seq)
    params = sum(p.numel() for p in base_cpu.parameters())
    exact = check_parity(base_cpu, n_layers) if parity else -1

    x0 = torch.zeros(1, 3, imgsz, imgsz)
    cum_macs = [float(thop.profile(DynamicEdgeSubmodel(base_cpu, k), inputs=(x0,), verbose=False)[0])
                for k in range(n_layers)]
    total_macs = cum_macs[-1]

    base = base_cpu.to(device)
    xs = [to_tensor(f, device) for f in frames]
    timer = Timer(device)

    def post(o):
        return nms.non_max_suppression(o[0] if isinstance(o, (list, tuple)) else o, conf_thres=0.25, iou_thres=0.45)

    rows = []
    with torch.no_grad():
        for x in xs[:5]:
            post(base(x))
        t_full = float(np.mean([timer(lambda x=x: post(base(x)))[1] for x in xs]))
        for k in range(1, n_layers - 1):
            edge = DynamicEdgeSubmodel(base, k).to(device)
            _, live = analyze_split_dependencies(seq, k)
            try:
                first = _as_tensors(edge(xs[0]))
            except Exception as e:  # e.g. a layer whose output is not a tensor
                logger.warning(f"{model} k={k}: {e}")
                continue
            if not all(isinstance(t, torch.Tensor) and t.dim() == 4 and t.shape[0] == 1 for t in first):
                continue
            elems = sum(t.numel() for t in first)
            sizes = []
            for i, x in enumerate(xs):  # one image at a time keeps GPU memory flat at large input sizes
                q, s = FeatureMapQuantizer.quantize(edge(x), dtype="int8_zstd")
                sizes.append(len(AegisPacketProtocol.serialize(i, 0, k, "int8_zstd", q, s)))
            rows.append({"model": model, "imgsz": imgsz, "images": image_set, "cut": k, "n_layers": n_layers,
                         "live": " ".join(map(str, live)), "edge_flop_frac": round(cum_macs[k] / total_macs, 4),
                         "elements": elems, "int8_kib": round(elems / 1024.0, 1),
                         "int8_zstd_kib": round(float(np.mean(sizes)) / 1024.0, 2)})
            del edge, first

        best = min(rows, key=lambda r: r["int8_zstd_kib"])
        k = best["cut"]
        edge = DynamicEdgeSubmodel(base, k).to(device)
        t_edge, t_q, bit_sizes, z19 = [], [], {b: [] for b in BITS}, []
        for i, x in enumerate(xs):
            a, te = timer(lambda x=x: edge(x))
            _, tq = timer(lambda a=a, i=i: AegisPacketProtocol.serialize(
                i, 0, k, "int8_zstd", *FeatureMapQuantizer.quantize(a, dtype="int8_zstd")))
            t_edge.append(te)
            t_q.append(tq)
            for b in BITS:
                bit_sizes[b].append(nbit.wire_bytes(_as_tensors(a), b)["zstd"])
            if i < 10:  # level 19 is slow; 10 frames suffice for its mean size
                z19.append(nbit.wire_bytes(_as_tensors(a), 8, zstd_level=19)["zstd"])
        bits = {b: float(np.mean(v)) / 1024.0 for b, v in bit_sizes.items()}
        z19 = float(np.mean(z19)) / 1024.0

    summary = {"model": model, "imgsz": imgsz, "images": image_set, "params_m": round(params / 1e6, 2),
               "gflops": round(2 * total_macs / 1e9, 2), "n_layers": n_layers, "cuts_exact": exact,
               "cuts_total": n_layers - 1, "bottleneck_cut": k, "bottleneck_live": best["live"],
               "edge_flop_frac": best["edge_flop_frac"], "int8_kib": best["int8_kib"],
               "int8_zstd_kib": best["int8_zstd_kib"], "int8_zstd19_kib": round(z19, 2),
               **{f"int{b}_zstd_kib": round(v, 2) for b, v in bits.items()},
               "host_full_ms": round(t_full, 3), "host_edge_ms": round(float(np.mean(t_edge)), 3),
               "host_quant_ser_ms": round(float(np.mean(t_q[2:])), 3),
               "raw_kib": round(3 * imgsz * imgsz / 1024.0, 1),
               **{f"{c}_kib": round(v["bytes"] / 1024.0, 2) for c, v in codecs.items()},
               "jpeg_enc_ms": round(codecs["jpeg_q90"]["enc_ms"], 3)}
    summary["rho_split"] = round((summary["host_quant_ser_ms"]) / t_full, 4)
    summary["rho_jpeg"] = round(summary["jpeg_enc_ms"] / t_full, 4)
    for q in (75, 90, 95):
        summary[f"ratio_jpeg_q{q}"] = round(summary["int8_zstd_kib"] / summary[f"jpeg_q{q}_kib"], 3)
    return rows, summary


def append_csv(path: Path, rows: List[Dict]) -> None:
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        if new:
            w.writeheader()
        w.writerows(rows)


def done_keys(path: Path) -> set:
    if not path.exists():
        return set()
    with open(path, newline="", encoding="utf-8") as f:
        return {(r["model"], int(r["imgsz"]), r["images"]) for r in csv.DictReader(f)}


def run(models: List[str], sizes: List[int], image_sets: List[str], n_images: int, device: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    done = done_keys(OUT / "model_summary.csv")  # resumable: one row per finished (model, size, images)
    for image_set in image_sets:
        for imgsz in sizes:
            frames = load_frames(image_set, n_images, imgsz)
            codecs = codec_sizes(frames)
            if (image_set, imgsz) not in {(i, s) for _, s, i in done} or not (OUT / "codec_sizes.csv").exists():
                append_csv(OUT / "codec_sizes.csv", [{"images": image_set, "imgsz": imgsz, "codec": c,
                                                       "kib": round(v["bytes"] / 1024.0, 2),
                                                       "enc_ms": round(v["enc_ms"], 3)} for c, v in codecs.items()])
            for model in models:
                if (model, imgsz, image_set) in done:
                    continue
                t0 = time.time()
                try:
                    rows, summary = survey_model(model, imgsz, image_set, frames, codecs, device,
                                                 parity=(image_set == image_sets[0] and imgsz == sizes[0]))
                except Exception as e:
                    logger.error(f"{model} @ {imgsz} ({image_set}) failed: {e}")
                    continue
                append_csv(OUT / "model_cuts.csv", rows)
                append_csv(OUT / "model_summary.csv", [summary])
                done.add((model, imgsz, image_set))
                torch.cuda.empty_cache()
                logger.info(f"{model:>9} {imgsz} {image_set}: k*={summary['bottleneck_cut']} "
                            f"{summary['int8_zstd_kib']:.0f} KiB vs JPEG90 {summary['jpeg_q90_kib']:.0f} "
                            f"(x{summary['ratio_jpeg_q90']:.2f}), exact {summary['cuts_exact']}/{summary['cuts_total']} "
                            f"[{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    ap.add_argument("--sizes", type=int, nargs="+", default=[640])
    ap.add_argument("--images", nargs="+", default=["coco"], choices=list(IMAGE_SETS))
    ap.add_argument("--n-images", type=int, default=50)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()
    run(args.models, args.sizes, args.images, args.n_images, args.device)
