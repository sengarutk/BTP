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
  optimizer    AdamW set explicitly (lr0 1e-4, cosine decay to lrf x lr0, 1 warm-up epoch, no early stopping). Run 1
               (10 Nov) used optimizer=auto, which silently ignored lr0 and fine-tuned at 8.3e-4: the held-out mAP fell
               after epoch 1 for 3 of 4 codes; those results are in _superseded/ (see the README there).
  selection    the best epoch is picked on 288 frames of the VisDrone2019-VID val clips (every 10th frame, 640 px wide,
               --sel vidval, the default): images neither the detector nor the bottleneck ever saw. The starting point
               (the distilled bottleneck, "epoch 0") is a candidate too, so joint training can never be reported worse
               than its start on the selection set. (--sel holdout: the last 471 DET train images, run 1's choice; the
               detector was fine-tuned on them, which inflates their mAP.) DET val (548 images) is used only for the
               final measurement, exactly as for JPEG and the other splits
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
SEL_YAML = DATA / "visdrone_joint_vidsel.yaml"
SEL_DIR = DATA / "visdrone_joint_sel"          # scripts/prepare_visdrone_finetune.vid_train(VID val, stride 10)
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
    if not (SEL_DIR / "images").exists():
        import sys
        sys.path.insert(0, str(REPO / "scripts"))
        import prepare_visdrone_finetune as pv
        pv.VID_STRIDE = 10
        print("selection set (VID val, every 10th frame):",
              pv.vid_train(DATA / "visdrone_vid" / "VisDrone2019-VID-val", SEL_DIR), "(images, boxes)")
    SEL_YAML.write_text("# Joint bottleneck: training on DET train minus 471; epoch selection on VID val frames (never seen\n"
                        "# by the detector or the bottleneck). DET val is not used here.\n"
                        f"path: {DATA}\ntrain: visdrone_joint_train.txt\nval: {SEL_DIR.name}/images\nnames:\n"
                        + "".join(f"  {i}: {n}\n" for i, n in enumerate(
                            ("person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck"))))


def build(a, device="cpu"):
    from ultralytics import YOLO
    yolo = YOLO(str(WEIGHTS))
    bn, ck = load_bottleneck(CKPT / f"{tag(a)}.pt", device)
    m = yolo.model
    m.model[a.cut] = CutWithBottleneck(m.model[a.cut], bn.train())
    return yolo, ck


def sel_map(yolo, data):
    r = yolo.val(data=str(data), imgsz=640, batch=8, device=0, plots=False, verbose=False, workers=1)
    return float(r.box.map), float(r.box.map50)


def cmd_train(a):
    from ultralytics.models.yolo.detect import DetectionTrainer
    data = SEL_YAML if a.sel == "vidval" else YAML
    yolo, _ = build(a)
    init_map, init_map50 = sel_map(yolo, data)         # "epoch 0": the distilled bottleneck with the detector as it is
    yolo, _ = build(a)                                 # fresh copy (val may change module state)
    model = yolo.model
    for p in model.parameters():
        p.requires_grad_(True)
    drone_side = [model.model[i] for i in range(a.cut)] + [model.model[a.cut].layer]
    for m in drone_side:                          # momentum 0: the running statistics never move, so in eval mode the
        for b in m.modules():                     # drone-side layers compute exactly what the measured detector does
            if isinstance(b, nn.BatchNorm2d):
                b.momentum = 0.0
    name = jtag(a) + f"_{a.run}" + (f"_f{a.fraction:g}" if a.fraction < 1 else "")
    ov = dict(model=str(WEIGHTS), data=str(data), imgsz=640, epochs=a.epochs, batch=a.batch, device=0,
              workers=a.workers, cache=False, amp=True, patience=a.patience or a.epochs + 1, fraction=a.fraction,
              seed=0, deterministic=False, project=str(RUNS), name=name, exist_ok=True, plots=False, verbose=False,
              optimizer="AdamW", lr0=a.lr0, lrf=a.lrf, cos_lr=True, warmup_epochs=1, momentum=0.9,
              freeze=[f"{i}" for i in range(a.cut)] + [f"{a.cut}.layer"], val=True)
    tr = DetectionTrainer(overrides=ov)
    tr.model = model                              # the trainer uses a ready nn.Module as it is
    t0 = time.time()
    tr.train()
    import csv
    rows = list(csv.DictReader(open(RUNS / name / "results.csv")))
    curve = [float(r[[k for k in r if "mAP50-95" in k][0]]) for r in rows]
    best_ep = int(np.argmax(curve)) + 1
    chosen = "trained" if max(curve) > init_map else "start"
    best = RUNS / name / "weights" / "best.pt"
    if a.fraction == 1.0 and a.save:
        JCKPT.mkdir(parents=True, exist_ok=True)
        if chosen == "trained":
            import shutil
            shutil.copy(best, JCKPT / f"{tag(a)}.pt")
        else:                                     # no epoch beat the start: the joint code IS the distilled one
            yolo0, _ = build(a)
            yolo0.save(str(JCKPT / f"{tag(a)}.pt"))
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump({"config": jtag(a), "run": a.run, "cut": a.cut, "channels": a.channels,
               **{k: getattr(a, k) for k in ARCH}, "epochs": a.epochs, "batch": a.batch, "optimizer": "AdamW",
               "lr0": a.lr0, "lrf": a.lrf, "fraction": a.fraction, "selection_set": a.sel,
               "selection_map50_95_start": init_map, "selection_map50_95_per_epoch": curve, "best_epoch": best_ep,
               "chosen": chosen, "minutes": (time.time() - t0) / 60, "run_dir": str(RUNS / name)},
              open(OUT / f"train_{name}.json", "w"), indent=1)
    print(f"start {init_map:.4f}  best epoch {best_ep} {max(curve):.4f}  -> {chosen}")


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
            p.add_argument("--lr0", type=float, default=1e-4)
            p.add_argument("--lrf", type=float, default=0.1)
            p.add_argument("--patience", type=int, default=0, help="0: no early stopping")
            p.add_argument("--sel", choices=["vidval", "holdout"], default="vidval")
            p.add_argument("--run", default="r2", help="run name suffix")
            p.add_argument("--save", type=int, default=1, help="copy the chosen weights to weights/joint_bottleneck")
            p.add_argument("--fraction", type=float, default=1.0)
            p.add_argument("--workers", type=int, default=3)
        else:
            p.add_argument("--n-boot", type=int, default=300)
    a = ap.parse_args()
    {"prepare": cmd_prepare, "train": cmd_train, "eval": cmd_eval}[a.cmd](a)


if __name__ == "__main__":
    main()
