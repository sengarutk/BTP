#!/usr/bin/env python3
"""Jointly trained split (hardening plan, Phase 2; 10 Nov 2026): the learned bottleneck trained together with the
detector's layers after the cut, with labels, instead of distilled against a frozen detector (learned_bottleneck.py).

Question for paper 1: does the strongest practical split, a bottleneck AND a detector tail trained for it, beat sending
the image end to end on the measured drone computers? (Supervised compression / BottleFit fine-tune the student end to
end in the same way.)

Design
  start        the VisDrone YOLOv8s (weights/yolov8s_visdrone.pt) with layer k's output passed through the distilled
               bottleneck of the same configuration (weights/learned_bottleneck/<tag>.pt) as the starting point
  trained      the bottleneck and every layer after the cut (the server side), with the detector's own detection loss
               on VisDrone2019-DET train labels (Ultralytics' trainer: same loss, augmentation and schedule as the
               fine-tuning of the detector itself)
  frozen       layers 0..k (the drone side): its weights do not change, so the Pi's measured prefix timings still hold
               (their batch-norm statistics are frozen too)
  selection    the best epoch is picked on the last 471 DET train images (held out, as in learned_bottleneck.py);
               DET val (548 images) is used only for the final measurement, exactly as for JPEG and the other splits
  measurement  as learned_bottleneck.py eval: zstd-1 of the uint8 code + 8-byte header per image on DET val, batch 1,
               mAP@[.5:.95], paired bootstrap against the unsplit detector
usage: joint_bottleneck.py prepare                                   -> datasets/visdrone_joint.yaml (+ two image lists)
       joint_bottleneck.py train --cut 4 --channels 8 [--stride 2] [--epochs 30] [--fraction 1.0]
       joint_bottleneck.py eval  --cut 4 --channels 8 [--stride 2]   -> experiments/results/joint_bottleneck/
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

from evaluation.learned_bottleneck import (ARCH, CKPT, REPO, WEIGHTS, drop_warmup, files_split, load_bottleneck,
                                           tag)

DATA = REPO / "datasets"
YAML = DATA / "visdrone_joint.yaml"
RUNS = REPO / "experiments" / "joint_bottleneck_runs"
OUT = REPO / "experiments" / "results" / "joint_bottleneck"
JCKPT = REPO / "weights" / "joint_bottleneck"


class CutWithBottleneck(nn.Module):
    """Layer k of the detector followed by the bottleneck (encoder, uint8 quantizer, decoder). Keeps the attributes the
    detector's forward pass needs (f, i, type, np). When `record` is a dict, the payload of every image is logged."""

    def __init__(self, layer, bottleneck):
        super().__init__()
        self.layer, self.bn = layer, bottleneck
        for k in ("f", "i", "type", "np"):
            setattr(self, k, getattr(layer, k))
        self.record = None

    def forward(self, x):
        y = self.layer(x)
        if self.record is None:
            return self.bn(y)[0]
        import zstandard
        cz = self.record.setdefault("_cz", zstandard.ZstdCompressor(level=1))
        rec = []
        for b in range(y.shape[0]):
            t0 = time.perf_counter()
            r, q = self.bn(y[b:b + 1].float())
            self.record["bytes"].append(len(cz.compress(q.cpu().numpy().tobytes())) + 8)
            self.record["enc_ms"].append((time.perf_counter() - t0) * 1e3)
            self.record["values"].append(q.numel())
            rec.append(r.to(y.dtype))
        return torch.cat(rec)


def jtag(a):
    return "joint_" + tag(a)


def cmd_prepare(a):
    tr, ho = files_split()
    (DATA / "visdrone_joint_train.txt").write_text("\n".join(tr) + "\n")
    (DATA / "visdrone_joint_holdout.txt").write_text("\n".join(ho) + "\n")
    YAML.write_text("# Joint bottleneck training (evaluation/joint_bottleneck.py): DET train minus the last 471 images,\n"
                    "# which are the selection set; DET val is not used here.\n"
                    f"path: {DATA}\ntrain: visdrone_joint_train.txt\nval: visdrone_joint_holdout.txt\n"
                    "names:\n  0: person\n  1: bicycle\n  2: car\n  3: motorcycle\n  4: airplane\n  5: bus\n"
                    "  6: train\n  7: truck\n")
    print(f"wrote {YAML}: {len(tr)} training images, {len(ho)} held out")


def build(a, device="cpu"):
    from ultralytics import YOLO
    yolo = YOLO(str(WEIGHTS))
    bn, ck = load_bottleneck(CKPT / f"{tag(a)}.pt", device)
    m = yolo.model
    m.model[a.cut] = CutWithBottleneck(m.model[a.cut], bn.train())
    return yolo, ck


def cmd_train(a):
    from ultralytics.models.yolo.detect import DetectionTrainer
    yolo, _ = build(a)
    model = yolo.model
    for p in model.parameters():
        p.requires_grad_(True)
    drone_side = [model.model[i] for i in range(a.cut)] + [model.model[a.cut].layer]
    for m in drone_side:                          # momentum 0: the running statistics never move, so in eval mode the
        for b in m.modules():                     # drone-side layers compute exactly what the measured detector does
            if isinstance(b, nn.BatchNorm2d):
                b.momentum = 0.0
    name = jtag(a) + (f"_f{a.fraction:g}" if a.fraction < 1 else "")
    ov = dict(model=str(WEIGHTS), data=str(YAML), imgsz=640, epochs=a.epochs, batch=a.batch, device=0, workers=a.workers,
              cache=False, amp=True, patience=a.patience, fraction=a.fraction, seed=0, deterministic=False,
              project=str(RUNS), name=name, exist_ok=True, plots=False, verbose=False, lr0=a.lr0, warmup_epochs=1,
              freeze=[f"{i}" for i in range(a.cut)] + [f"{a.cut}.layer"], val=True)
    tr = DetectionTrainer(overrides=ov)
    tr.model = model                              # the trainer uses a ready nn.Module as it is
    t0 = time.time()
    tr.train()
    best = RUNS / name / "weights" / "best.pt"
    JCKPT.mkdir(parents=True, exist_ok=True)
    if a.fraction == 1.0 and best.exists():
        import shutil
        shutil.copy(best, JCKPT / f"{tag(a)}.pt")
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump({"config": jtag(a), "cut": a.cut, "channels": a.channels, **{k: getattr(a, k) for k in ARCH},
               "epochs": a.epochs, "batch": a.batch, "lr0": a.lr0, "fraction": a.fraction, "patience": a.patience,
               "minutes": (time.time() - t0) / 60, "run_dir": str(RUNS / name)},
              open(OUT / f"train_{name}.json", "w"), indent=1)


def cmd_eval(a):
    from ultralytics import YOLO
    from evaluation.detection_eval import paired_bootstrap, run_validation, summary_row
    dev = "cuda"
    yolo = YOLO(str(JCKPT / f"{tag(a)}.pt"))
    wrap = yolo.model.model[a.cut]
    assert isinstance(wrap, CutWithBottleneck), type(wrap)
    base = run_validation(YOLO(str(WEIGHTS)), "visdrone_val", dev, name="lb_base_yolov8s_visdrone_full_fp32")
    wrap.record = {"bytes": [], "values": [], "enc_ms": []}
    try:
        res = run_validation(yolo, "visdrone_val", dev, name=f"jb_yolov8s_visdrone_{tag(a)}", cache=False)
    finally:
        log, wrap.record = wrap.record, None
    for k in ("bytes", "values", "enc_ms"):
        log[k] = drop_warmup(log[k], res["num_images"])
    pb = paired_bootstrap(base, res, n_boot=a.n_boot)
    row = {"config": jtag(a), "trained": "joint (bottleneck + server-side layers, detection loss)", "cut": a.cut,
           "channels": a.channels, **{k: getattr(a, k) for k in ARCH}, "n": len(log["bytes"]),
           "code_values": int(np.median(log["values"])), "payload_bytes_mean": float(np.mean(log["bytes"])),
           "payload_bytes_p95": float(np.percentile(log["bytes"], 95)),
           "gpu_codec_ms_median": float(np.median(log["enc_ms"])), "base_map50_95": base["map50_95"],
           **{k: v for k, v in summary_row(res).items() if k != "name"}, **{f"boot_{k}": v for k, v in pb.items()}}
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(row, open(OUT / f"eval_{jtag(a)}.json", "w"), indent=1)
    print(json.dumps({k: (round(v, 5) if isinstance(v, float) else v) for k, v in row.items()}))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prepare")
    for name in ("train", "eval"):
        p = sub.add_parser(name)
        p.add_argument("--cut", type=int, default=4, choices=[2, 4])
        p.add_argument("--channels", type=int, default=8)
        p.add_argument("--width", type=int, default=128)
        p.add_argument("--stride", type=int, default=2, choices=[1, 2])
        p.add_argument("--dec-layers", type=int, default=2)
        if name == "train":
            p.add_argument("--epochs", type=int, default=30)
            p.add_argument("--batch", type=int, default=8)
            p.add_argument("--lr0", type=float, default=0.002)
            p.add_argument("--patience", type=int, default=10)
            p.add_argument("--fraction", type=float, default=1.0)
            p.add_argument("--workers", type=int, default=3)
        else:
            p.add_argument("--n-boot", type=int, default=300)
    a = ap.parse_args()
    {"prepare": cmd_prepare, "train": cmd_train, "eval": cmd_eval}[a.cmd](a)


if __name__ == "__main__":
    main()
