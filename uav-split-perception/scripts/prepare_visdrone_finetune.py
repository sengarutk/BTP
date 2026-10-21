#!/usr/bin/env python3
"""Training data for fine-tuning YOLOv8 on drone imagery (VisDrone), with the class ids the whole project uses.

Train: VisDrone2019-DET train (6,471 aerial still images) + VisDrone2019-VID train (the clips on disk, every 5th
frame, resized to 640 px wide exactly as prepare_vid.py makes the camera stream). Validation (model selection):
VisDrone2019-DET val. The VisDrone2019-VID VAL clips - the test stream of every live run - are NOT used.
Labels: VisDrone categories mapped to COCO ids exactly as scripts/prepare_datasets.py (pedestrian, people -> person 0;
bicycle -> 1; car, van -> car 2; truck -> 7; bus -> 5; motor -> motorcycle 3; ignored regions (score 0), tricycles
and "others" dropped). The detector is trained with nc = 8 (COCO ids 0-7; 4 airplane and 6 train never occur), so its
class ids equal the COCO ids the scorer, the VID labels and every controller already use: nothing downstream changes.
Output: datasets/visdrone_ft/{vid_train/images,labels}, datasets/visdrone_ft.yaml
"""
import json
import sys
import zipfile
from pathlib import Path

import cv2
import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "datasets"
sys.path.insert(0, str(ROOT / "scripts"))
from prepare_datasets import VISDRONE_TO_COCO  # noqa: E402

NAMES = {0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 4: "airplane", 5: "bus", 6: "train", 7: "truck"}
VID_STRIDE = 5


def det_labels(root):
    """VisDrone-DET annotations -> YOLO labels with COCO ids (as prepare_visdrone_val)."""
    lbl = root / "labels"
    lbl.mkdir(exist_ok=True)
    n_img = n_box = 0
    for ann in sorted((root / "annotations").glob("*.txt")):
        with Image.open(root / "images" / f"{ann.stem}.jpg") as im:
            w, h = im.size
        lines = []
        for row in ann.read_text().strip().splitlines():
            x, y, bw, bh, score, cat = (int(v) for v in row.split(",")[:6])
            if score == 0 or cat not in VISDRONE_TO_COCO:
                continue
            x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + bw, w), min(y + bh, h)
            if x1 <= x0 or y1 <= y0:
                continue
            lines.append(f"{VISDRONE_TO_COCO[cat]} {(x0 + x1) / 2 / w:.6f} {(y0 + y1) / 2 / h:.6f} "
                         f"{(x1 - x0) / w:.6f} {(y1 - y0) / h:.6f}")
        (lbl / ann.name).write_text("\n".join(lines) + ("\n" if lines else ""))
        n_img += 1
        n_box += len(lines)
    return n_img, n_box


def vid_train(src, dst):
    """VisDrone-VID train clips -> every VID_STRIDE-th frame at 640 px wide + YOLO labels (COCO ids)."""
    seq_root = next(src.rglob("sequences"))
    ann_root = next(src.rglob("annotations"))
    (dst / "images").mkdir(parents=True, exist_ok=True)
    (dst / "labels").mkdir(parents=True, exist_ok=True)
    n_img = n_box = 0
    for sd in sorted(p for p in seq_root.iterdir() if p.is_dir()):
        boxes = {}
        for row in (ann_root / f"{sd.name}.txt").read_text().strip().splitlines():
            v = [int(x) for x in row.split(",")[:8]]
            fr, x, y, bw, bh, score, cat = v[0], v[2], v[3], v[4], v[5], v[6], v[7]
            if score == 0 or cat not in VISDRONE_TO_COCO:
                continue
            boxes.setdefault(fr, []).append((VISDRONE_TO_COCO[cat], x, y, x + bw, y + bh))
        for f in sorted(sd.glob("*.jpg"))[::VID_STRIDE]:
            fr = int(f.stem)
            img = cv2.imread(str(f))
            h, w = img.shape[:2]
            s = 640.0 / w
            out = cv2.resize(img, (640, round(h * s)), interpolation=cv2.INTER_AREA)
            name = f"{sd.name}_{f.stem}"
            cv2.imwrite(str(dst / "images" / f"{name}.jpg"), out, [cv2.IMWRITE_JPEG_QUALITY, 95])
            lines = []
            for c, x0, y0, x1, y1 in boxes.get(fr, []):
                x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, w), min(y1, h)
                if x1 <= x0 or y1 <= y0:
                    continue
                lines.append(f"{c} {(x0 + x1) / 2 / w:.6f} {(y0 + y1) / 2 / h:.6f} {(x1 - x0) / w:.6f} {(y1 - y0) / h:.6f}")
            (dst / "labels" / f"{name}.txt").write_text("\n".join(lines) + ("\n" if lines else ""))
            n_img += 1
            n_box += len(lines)
    return n_img, n_box


def main():
    det = DATA / "visdrone" / "VisDrone2019-DET-train"
    if not (det / "images").exists():
        with zipfile.ZipFile(DATA / "visdrone" / "VisDrone2019-DET-train.zip") as z:
            z.extractall(DATA / "visdrone")
    print("DET train:", det_labels(det), "(images, boxes)", flush=True)
    val = DATA / "visdrone" / "VisDrone2019-DET-val"
    print("DET val (labels exist):", len(list((val / "labels").glob("*.txt"))), flush=True)
    vt = DATA / "visdrone_ft" / "vid_train"
    print("VID train:", vid_train(DATA / "visdrone_vid" / "VisDrone2019-VID-train", vt), "(images, boxes)", flush=True)
    cfg = {"path": str(DATA.resolve()),
           "train": [str((det / "images").relative_to(DATA)), str((vt / "images").relative_to(DATA))],
           "val": str((val / "images").relative_to(DATA)), "names": NAMES}
    (DATA / "visdrone_ft.yaml").write_text(
        "# Fine-tuning on VisDrone (DET train + VID train clips), COCO ids 0-7 (scripts/prepare_visdrone_finetune.py).\n"
        "# The VID val clips (the live test stream) are not used.\n" + yaml.safe_dump(cfg, sort_keys=False))
    print("wrote", DATA / "visdrone_ft.yaml")


if __name__ == "__main__":
    main()
