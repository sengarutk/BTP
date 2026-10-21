#!/usr/bin/env python3
"""Fine-tune a COCO-pretrained YOLOv8 on VisDrone (datasets/visdrone_ft.yaml; scripts/prepare_visdrone_finetune.py).

Starts from the COCO weights the project used so far (so the comparison is "same model, drone-trained"), trains at
640 px (the camera stream's resolution), nc = 8 with COCO ids, selects the best epoch on VisDrone2019-DET val
(never on the VID val clips used for the live tests), and copies the best weights to weights/<model>_visdrone.pt.
usage: train_visdrone.py MODEL EPOCHS [--batch N] [--fraction F]   e.g. train_visdrone.py yolov8s 80
Runs: experiments/finetune/<model>_e<EPOCHS>/
"""
import argparse
import shutil
from pathlib import Path

from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent.parent
INIT = {"yolov8n": ROOT / "weights" / "yolov8n.pt", "yolov8s": ROOT / "yolov8s.pt",
        "yolov8m": ROOT / "weights" / "yolov8m.pt", "yolov8l": ROOT / "weights" / "yolov8l.pt"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model", choices=list(INIT))
    ap.add_argument("epochs", type=int)
    ap.add_argument("--batch", type=float, default=-1, help="-1: AutoBatch (fits the 6 GB GPU)")
    ap.add_argument("--fraction", type=float, default=1.0, help="share of the training images (timing runs)")
    ap.add_argument("--name", default="")
    a = ap.parse_args()
    name = a.name or f"{a.model}_e{a.epochs}"
    m = YOLO(str(INIT[a.model]))
    m.train(data=str(ROOT / "datasets" / "visdrone_ft.yaml"), imgsz=640, epochs=a.epochs,
            batch=int(a.batch) if a.batch >= 1 else a.batch, device=0, workers=4, cache=False, amp=True,
            patience=max(15, a.epochs // 4), fraction=a.fraction, seed=0, deterministic=False,
            project=str(ROOT / "experiments" / "finetune"), name=name, exist_ok=True, plots=True, verbose=False)
    best = ROOT / "experiments" / "finetune" / name / "weights" / "best.pt"
    if a.fraction == 1.0 and best.exists():
        shutil.copy(best, ROOT / "weights" / f"{a.model}_visdrone.pt")
        print("best weights ->", ROOT / "weights" / f"{a.model}_visdrone.pt")


if __name__ == "__main__":
    main()
