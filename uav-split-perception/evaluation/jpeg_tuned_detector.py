#!/usr/bin/env python3
"""The fair counterpart of the jointly trained split (independent audit of paper 1's v2 drafts, 11 Nov 2026): the
detector fine-tuned on JPEG-compressed images.

Why. joint_bottleneck.py trains a split's server side (the bottleneck and every layer after the cut) for 30 epochs,
while the image path keeps the unmodified detector. With JPEG every layer is on the server, so the counterpart trains
every layer on JPEG-decoded images, with the same recipe. Comparing joint codes against this detector removes the
training asymmetry from the break-even rule (evaluation/break_even_rule.py --jpeg-tuned).

Design (as joint_bottleneck.py, so the two are like for like)
  model        the VisDrone YOLOv8s (weights/yolov8s_visdrone.pt); layer 0 is wrapped by JpegInput, which replaces each
               image by its JPEG encode -> decode (OpenCV, as benchmark_codecs.make_codec_hook, the hook that measured
               the paper's JPEG rows) before the first convolution, in training and in validation
  qualities    --q mix: each training image gets a quality drawn uniformly from 10, 15, ..., 95 (one detector for every
               JPEG setting, what a deployment would run); --q N: every image at quality N (the most generous case)
  data         VisDrone2019-DET train minus the last 471 images (datasets/visdrone_joint.yaml), Ultralytics' trainer,
               loss and augmentation; the JPEG round trip is applied to the augmented image the network sees
  optimizer    AdamW, lr0 1e-3 (the joint codes' pilot), cosine to 0.1 x lr0, 1 warm-up epoch, 30 epochs, batch 8,
               no early stopping, all layers trainable (all are server-side for an image)
  selection    the 288 VisDrone-VID val frames (datasets/visdrone_joint_vidsel.yaml), JPEG'd the same way: fixed N, or
               for mix a quality fixed per image (from a hash of its pixels, so every validation pass sees the same
               assignment). The untuned detector ("epoch 0") is a candidate.
  measurement  each quality of the grid on the 548 VisDrone-DET val frames, batch 1, mAP@[.5:.95]; the payload is
               logged and must equal the untuned JPEG row of the same quality (same encoder, same frames); paired
               bootstrap against the untuned detector at the same quality (cached jpeg rows of learned_bottleneck.py)
usage: jpeg_tuned_detector.py train --q mix|N [--epochs 30] [--lr0 1e-3]
       jpeg_tuned_detector.py eval  --q mix|N                -> experiments/results/jpeg_tuned/eval_<run>_q<Q>.json
       jpeg_tuned_detector.py compare --q N   paired bootstrap of the dedicated quality-N detector against the
              mixed-quality one at quality N (cached per-image stats)  -> paired_dedicated_vs_mix_q<N>.json
"""
import argparse
import json
import random
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn

REPO = Path(__file__).resolve().parent.parent
WEIGHTS = REPO / "weights" / "yolov8s_visdrone.pt"
DATA = REPO / "datasets"
SEL_YAML = DATA / "visdrone_joint_vidsel.yaml"
RUNS = REPO / "experiments" / "jpeg_tuned_runs"
OUT = REPO / "experiments" / "results" / "jpeg_tuned"
CKPT = REPO / "weights" / "jpeg_tuned"
GRID = tuple(range(10, 100, 5))                  # 10, 15, ..., 95: every quality measured for the break-even rule


def jpeg_roundtrip(img_chw, q):
    """One image (3 x H x W, RGB in [0, 1]) -> its JPEG encode/decode at quality q, and the payload in bytes. Identical
    to benchmark_codecs.make_codec_hook (round to uint8, BGR for OpenCV, decode, back to RGB / 255)."""
    rgb = (img_chw.permute(1, 2, 0).float().cpu().numpy() * 255.0).round().clip(0, 255).astype(np.uint8)
    ok, enc = cv2.imencode(".jpg", np.ascontiguousarray(rgb[:, :, ::-1]), [cv2.IMWRITE_JPEG_QUALITY, int(q)])
    if not ok:
        raise RuntimeError("JPEG encode failed")
    dec = cv2.imdecode(enc, cv2.IMREAD_COLOR)[:, :, ::-1]
    return torch.from_numpy(np.array(dec, copy=True)).permute(2, 0, 1), len(enc)


class JpegInput(nn.Module):
    """Layer 0 of the detector preceded by a JPEG round trip of every image. q: an int (fixed quality) or "mix".
    In training with "mix" each image draws a quality from GRID; in evaluation it is fixed per image by a hash of its
    pixels. `record` (a dict with "bytes") logs every payload."""

    def __init__(self, layer, q):
        super().__init__()
        self.layer, self.q, self.record = layer, q, None
        for k in ("f", "i", "type", "np"):
            setattr(self, k, getattr(layer, k))

    def quality(self, img):
        if self.q != "mix":
            return int(self.q)
        if self.training:
            return random.choice(GRID)
        h = int((img[:, ::7, ::7].float() * 255).round().sum().item())
        return GRID[h % len(GRID)]

    def forward(self, x):
        with torch.no_grad():
            # Ultralytics' warm-up passes an uninitialised tensor (it can hold NaN); real images are already in [0, 1]
            x = torch.nan_to_num(x, nan=0.0, posinf=1.0, neginf=0.0).clamp_(0.0, 1.0)
            out = torch.empty_like(x)
            for b in range(x.shape[0]):
                dec, n = jpeg_roundtrip(x[b], self.quality(x[b]))
                out[b] = dec.to(x.device, x.dtype) / 255.0
                if self.record is not None:
                    self.record["bytes"].append(n)
        return self.layer(out)


def run_name(q, run):
    return f"jpegtuned_q{q}_{run}"


def build(q):
    from ultralytics import YOLO
    yolo = YOLO(str(WEIGHTS))
    yolo.model.model[0] = JpegInput(yolo.model.model[0], q)
    return yolo


def parse_q(s):
    return s if s == "mix" else int(s)


def cmd_train(a):
    from ultralytics.models.yolo.detect import DetectionTrainer
    q = parse_q(a.q)
    yolo = build(q)
    r = yolo.val(data=str(SEL_YAML), imgsz=640, batch=8, device=0, plots=False, verbose=False, workers=1)
    init_map = float(r.box.map)                  # "epoch 0": the untuned detector on the same JPEG'd selection frames
    yolo = build(q)
    model = yolo.model
    for p in model.parameters():
        p.requires_grad_(True)
    name = run_name(a.q, a.run) + (f"_f{a.fraction:g}" if a.fraction < 1 else "")
    ov = dict(model=str(WEIGHTS), data=str(SEL_YAML), imgsz=640, epochs=a.epochs, batch=a.batch, device=0,
              workers=a.workers, cache=False, amp=True, patience=a.epochs + 1, seed=0, deterministic=False,
              project=str(RUNS), name=name, exist_ok=True, plots=False, verbose=False, optimizer="AdamW", lr0=a.lr0,
              lrf=a.lrf, cos_lr=True, warmup_epochs=1, momentum=0.9, freeze=0, val=True, fraction=a.fraction)
    tr = DetectionTrainer(overrides=ov)
    tr.model = model
    t0 = time.time()
    tr.train()
    import csv
    import shutil
    rows = list(csv.DictReader(open(RUNS / name / "results.csv")))
    curve = [float(r[[k for k in r if "mAP50-95" in k][0]]) for r in rows]
    best_ep = int(np.argmax(curve)) + 1
    chosen = "trained" if max(curve) > init_map else "start"
    CKPT.mkdir(parents=True, exist_ok=True)
    if a.fraction < 1:
        print(f"smoke run: start {init_map:.4f}, curve {curve}", flush=True)
        return
    if chosen == "trained":
        shutil.copy(RUNS / name / "weights" / "best.pt", CKPT / f"{name}.pt")
    else:
        build(q).save(str(CKPT / f"{name}.pt"))
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump({"run": name, "q": a.q, "epochs": a.epochs, "batch": a.batch, "optimizer": "AdamW", "lr0": a.lr0,
               "lrf": a.lrf, "trainable": "all layers", "data": "datasets/visdrone_joint.yaml train list via SEL_YAML",
               "selection_set": "VID val, 288 frames", "selection_map50_95_start": init_map,
               "selection_map50_95_per_epoch": curve, "best_epoch": best_ep, "chosen": chosen,
               "minutes": (time.time() - t0) / 60, "run_dir": str(RUNS / name)},
              open(OUT / f"train_{name}.json", "w"), indent=1)
    print(f"start {init_map:.4f}  best epoch {best_ep} {max(curve):.4f}  -> {chosen}", flush=True)


def cmd_eval(a):
    from ultralytics import YOLO
    from evaluation.detection_eval import paired_bootstrap, run_validation
    name = run_name(a.q, a.run)
    yolo = YOLO(str(CKPT / f"{name}.pt"))
    wrap = yolo.model.model[0]
    assert isinstance(wrap, JpegInput), type(wrap)
    lb = REPO / "experiments" / "results" / "learned_bottleneck"
    OUT.mkdir(parents=True, exist_ok=True)
    for q in (GRID if a.q == "mix" else [int(a.q)]):
        f = lb / f"jpeg_q{q}.json"
        f = f if f.exists() else lb / "jpeg_fine" / f"jpeg_q{q}.json"
        ref = json.load(open(f))
        from evaluation.detection_eval import STATS_CACHE
        import pickle
        base = pickle.load(open(STATS_CACHE / "visdrone_val" / f"lb_jpeg_q{q}_yolov8s_visdrone.pkl", "rb"))
        assert abs(base["map50_95"] - ref["map50_95"]) < 1e-9, (q, base["map50_95"], ref["map50_95"])
        wrap.q, wrap.record = q, {"bytes": []}
        try:
            res = run_validation(yolo, "visdrone_val", "cuda", name=f"jt_{name}_q{q}", cache=False)
        finally:
            log, wrap.record = wrap.record, None
        # the trainer's validator runs a warm-up pass; keep the last num_images payloads (one per DET val frame)
        nb = log["bytes"][-res["num_images"]:]
        pay = float(np.mean(nb))
        pb = paired_bootstrap(base, res, n_boot=a.n_boot, workers=a.workers)
        row = {"run": name, "q": q, "n": len(nb), "payload_bytes_mean": pay,
               "payload_bytes_untuned": ref["payload_bytes_mean"],
               "payload_matches_untuned": bool(abs(pay - ref["payload_bytes_mean"]) < 1e-6 * ref["payload_bytes_mean"]),
               "map50_95_untuned": ref["map50_95"], "map50_95": res["map50_95"], "map50": res["map50"],
               "gain": res["map50_95"] - ref["map50_95"], **{f"boot_{k}": v for k, v in pb.items()}}
        json.dump(row, open(OUT / f"eval_{name}_q{q}.json", "w"), indent=1)
        print(f"q{q}: untuned {ref['map50_95']:.4f} tuned {res['map50_95']:.4f} gain {row['gain']:+.4f} "
              f"CI [{row['boot_delta_map50_95_ci_low']:+.4f}, {row['boot_delta_map50_95_ci_high']:+.4f}] "
              f"payload {pay:.0f} (untuned {ref['payload_bytes_mean']:.0f})", flush=True)


def cmd_compare(a):
    import pickle
    from evaluation.detection_eval import STATS_CACHE, map_from_stats, paired_bootstrap
    q = int(a.q)
    res = {}
    for kind in ("mix", str(q)):
        name = run_name(kind, a.run)
        r = pickle.load(open(STATS_CACHE / "visdrone_val" / f"jt_{name}_q{q}.pkl", "rb"))
        ev = json.load(open(OUT / f"eval_{name}_q{q}.json"))
        assert abs(map_from_stats(r["stats"])[1] - ev["map50_95"]) < 1e-6 and r["num_images"] == ev["n"], name
        res[kind] = r
    pb = paired_bootstrap(res["mix"], res[str(q)], n_boot=a.n_boot, workers=a.workers)
    row = {"method": f"paired image-level bootstrap, dedicated Q{q} detector minus the mixed-quality detector at Q{q}, "
                     "same VisDrone-DET val frames; cached stats checked against the eval files",
           "map50_95_mix": res["mix"]["map50_95"], "map50_95_dedicated": res[str(q)]["map50_95"],
           "gain": res[str(q)]["map50_95"] - res["mix"]["map50_95"], "n_boot": a.n_boot,
           **{f"boot_{k}": v for k, v in pb.items()}}
    row["significant"] = bool(row["boot_delta_map50_95_ci_low"] > 0 or row["boot_delta_map50_95_ci_high"] < 0)
    json.dump(row, open(OUT / f"paired_dedicated_vs_mix_q{q}.json", "w"), indent=1)
    print(f"Q{q}: mix {row['map50_95_mix']:.4f} dedicated {row['map50_95_dedicated']:.4f} gain {row['gain']:+.4f} CI "
          f"[{row['boot_delta_map50_95_ci_low']:+.4f}, {row['boot_delta_map50_95_ci_high']:+.4f}]", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("train", "eval", "compare"):
        p = sub.add_parser(name)
        p.add_argument("--q", default="mix", help="mix or a JPEG quality")
        p.add_argument("--run", default="r1")
        if name == "train":
            p.add_argument("--epochs", type=int, default=30)
            p.add_argument("--batch", type=int, default=8)
            p.add_argument("--lr0", type=float, default=1e-3)
            p.add_argument("--lrf", type=float, default=0.1)
            p.add_argument("--workers", type=int, default=2)
            p.add_argument("--fraction", type=float, default=1.0, help="< 1: smoke test, nothing saved")
        else:
            p.add_argument("--n-boot", type=int, default=300 if name == "eval" else 1000)
            p.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    {"train": cmd_train, "eval": cmd_eval, "compare": cmd_compare}[a.cmd](a)


if __name__ == "__main__":
    main()
