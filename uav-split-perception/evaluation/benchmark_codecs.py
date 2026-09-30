#!/usr/bin/env python3
"""Rate-accuracy baselines: offload the (letterboxed) camera frame with a standard codec.

Each validation image is encoded, decoded, and then detected by the unmodified YOLOv8s,
so accuracy reflects only coding loss. Codecs:
  * JPEG (OpenCV/libjpeg) at quality Q
  * WebP (OpenCV/libwebp) at quality Q
  * H.264 (libx264 via ffmpeg, intra-only single frame, preset ultrafast, tune zerolatency) at CRF
Wire size is the encoded bitstream; bits-per-pixel uses the actual encoded resolution.
Encode time is measured in-process for JPEG/WebP; H.264 is run through an ffmpeg process,
so its per-frame time includes process start-up and is reported only as an upper bound.
Single intra frames understate what H.264 achieves on video with inter prediction, so the
H.264 rows are a conservative (pessimistic) baseline.
"""

import argparse
import csv
import json
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np
import torch
from ultralytics import YOLO

from evaluation.detection_eval import DEFAULT_DATASET, paired_bootstrap, run_validation, summary_row
from utils.logger import get_logger

REPO_ROOT = Path(__file__).resolve().parent.parent
logger = get_logger("BenchmarkCodecs")

JPEG_Q = [10, 20, 35, 50, 75, 90, 95]
WEBP_Q = [10, 25, 50, 75, 90]
H264_CRF = [40, 34, 28, 23, 18]


def encode_h264(rgb: np.ndarray, crf: int) -> Tuple[bytes, float]:
    h, w, _ = rgb.shape
    t0 = time.perf_counter()
    enc = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-i", "-",
         "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency", "-crf", str(crf),
         "-pix_fmt", "yuv420p", "-frames:v", "1", "-f", "h264", "-"],
        input=rgb.tobytes(), capture_output=True, check=True)
    return enc.stdout, (time.perf_counter() - t0) * 1000.0


def decode_h264(bitstream: bytes, w: int, h: int) -> np.ndarray:
    dec = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "h264", "-i", "-", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        input=bitstream, capture_output=True, check=True)
    return np.frombuffer(dec.stdout[: w * h * 3], dtype=np.uint8).reshape(h, w, 3)


def make_codec_hook(codec: str, param: int, log: Dict[str, List[float]]):
    """Forward pre-hook on layer 0: replaces the input image by its encode->decode version."""

    def hook(module, args):
        x = args[0]
        out = torch.empty_like(x)
        for b in range(x.shape[0]):
            rgb = (x[b].permute(1, 2, 0).float().cpu().numpy() * 255.0).round().clip(0, 255).astype(np.uint8)
            h, w = rgb.shape[:2]
            if codec in ("JPEG", "WebP"):
                bgr = np.ascontiguousarray(rgb[:, :, ::-1])  # OpenCV codecs expect BGR
                ext, flag = (".jpg", cv2.IMWRITE_JPEG_QUALITY) if codec == "JPEG" else (".webp", cv2.IMWRITE_WEBP_QUALITY)
                t0 = time.perf_counter()
                ok, enc = cv2.imencode(ext, bgr, [flag, int(param)])
                enc_ms = (time.perf_counter() - t0) * 1000.0
                if not ok:
                    raise RuntimeError(f"{codec} encode failed")
                nbytes = len(enc)
                dec = cv2.imdecode(enc, cv2.IMREAD_COLOR)[:, :, ::-1]
            else:
                bitstream, enc_ms = encode_h264(rgb, param)
                nbytes = len(bitstream)
                dec = decode_h264(bitstream, w, h)
            log["bytes"].append(nbytes)
            log["pixels"].append(h * w)
            log["enc_ms"].append(enc_ms)
            out[b] = torch.from_numpy(np.array(dec, copy=True)).permute(2, 0, 1).to(x.device, x.dtype) / 255.0
        return (out,) + tuple(args[1:])

    return hook


def run(weights: str, data: str, device: str, output_dir: Path, n_boot: int) -> List[Dict[str, Any]]:
    yolo = YOLO(weights)
    base = run_validation(yolo, data, device, name="full_fp32")
    configs = ([("JPEG", q) for q in JPEG_Q] + [("WebP", q) for q in WEBP_Q] + [("H.264", c) for c in H264_CRF])
    rows = []
    for codec, param in configs:
        name = f"codec_{codec.replace('.', '').lower()}_{param}"
        log: Dict[str, List[float]] = {"bytes": [], "pixels": [], "enc_ms": []}
        logger.info(f"Validating {codec} ({'CRF' if codec == 'H.264' else 'Q'}={param})...")
        res = run_validation(yolo, data, device, name=name, pre_forward_hook=make_codec_hook(codec, param, log))
        if log["bytes"]:  # fresh run: persist rate statistics next to the accuracy cache
            res["rate"] = {"mean_bytes": float(np.mean(log["bytes"])),
                           "bpp": float(np.sum(np.array(log["bytes"]) * 8) / np.sum(log["pixels"])),
                           "mean_pixels": float(np.mean(log["pixels"])),
                           "enc_ms_median": float(np.median(log["enc_ms"]))}
            rate_file = REPO_ROOT / "experiments" / "cache" / "codec_rates" / f"{name}.json"
            rate_file.parent.mkdir(parents=True, exist_ok=True)
            rate_file.write_text(json.dumps(res["rate"]))
        else:
            res["rate"] = json.loads((REPO_ROOT / "experiments" / "cache" / "codec_rates" / f"{name}.json").read_text())
        row = {"codec_name": codec, "param_type": "crf" if codec == "H.264" else "quality", "param": param,
               "wire_bytes": round(res["rate"]["mean_bytes"], 1),
               "wire_kib": round(res["rate"]["mean_bytes"] / 1024.0, 2),
               "bpp": round(res["rate"]["bpp"], 4),
               "mean_pixels": round(res["rate"]["mean_pixels"]),
               "enc_ms_median": round(res["rate"]["enc_ms_median"], 2),
               "enc_time_includes_process_startup": codec == "H.264",
               **{k: v for k, v in summary_row(res).items() if k in ("map50", "map50_95", "precision", "recall", "num_images")},
               **paired_bootstrap(base, res, n_boot=n_boot)}
        rows.append(row)
        logger.info(f"  {row['wire_kib']:.1f} KiB/frame, mAP50-95={row['map50_95']:.4f} ({row['delta_map50_95']:+.4f})")

    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "codec_baselines.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    (output_dir / "codec_baselines.json").write_text(json.dumps(
        {"dataset": data, "baseline_map50_95": base["map50_95"], "results": rows}, indent=2), encoding="utf-8")
    logger.success(f"Wrote {len(rows)} codec baselines")
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--weights", default="yolov8s.pt")
    ap.add_argument("--data", default=DEFAULT_DATASET)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--output-dir", default=str(REPO_ROOT / "experiments" / "results"))
    ap.add_argument("--n-boot", type=int, default=200)
    args = ap.parse_args()
    run(args.weights, args.data, args.device, Path(args.output_dir), args.n_boot)
