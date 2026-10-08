#!/usr/bin/env python3
"""VisDrone2019-VID val -> the camera stream and labels of the live streaming-perception tests.

Each of the 7 validation sequences is resized to 640 px wide (the detectors letterbox to <= 640 anyway;
this is the camera resolution of the experiments) and re-encoded as JPEG q95; boxes are scaled
accordingly and mapped to COCO class ids with the paper's mapping (scripts/prepare_datasets.py:
ignored regions, score 0, "others" and tricycles are dropped).
Output: datasets/visdrone_vid_640/<seq>/<frame>.jpg, labels.json {seq: {frame: [[cls, x0, y0, x1, y1], ...]}},
sequences.json [[seq, n_frames], ...]
"""
import json
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent.parent
SPLIT = "val"
SRC = ROOT / "datasets" / "visdrone_vid" / "VisDrone2019-VID-val"
DST = ROOT / "datasets" / "visdrone_vid_640"
VISDRONE_TO_COCO = {1: 0, 2: 0, 3: 1, 4: 2, 5: 2, 6: 7, 9: 5, 10: 3}   # = scripts/prepare_datasets.py


def find(sub):
    hits = list(SRC.rglob(sub))
    return hits[0] if hits else None


def main():
    seq_root, ann_root = find("sequences"), find("annotations")
    labels, seqs = {}, []
    for sd in sorted(p for p in seq_root.iterdir() if p.is_dir()):
        frames = sorted(sd.glob("*.jpg"))
        img0 = cv2.imread(str(frames[0]))
        h, w = img0.shape[:2]
        s = 640.0 / w
        out = DST / sd.name
        out.mkdir(parents=True, exist_ok=True)
        for f in frames:
            img = cv2.imread(str(f))
            cv2.imwrite(str(out / f.name), cv2.resize(img, (640, round(h * s)), interpolation=cv2.INTER_AREA),
                        [cv2.IMWRITE_JPEG_QUALITY, 95])
        lab = {}
        for line in open(ann_root / f"{sd.name}.txt"):
            v = [int(x) for x in line.strip().split(",")[:8]]
            fr, _, x, y, bw, bh, score, cat = v
            if score == 0 or cat not in VISDRONE_TO_COCO:
                continue
            lab.setdefault(fr, []).append([VISDRONE_TO_COCO[cat], round(x * s, 2), round(y * s, 2),
                                           round((x + bw) * s, 2), round((y + bh) * s, 2)])
        labels[sd.name] = {int(k): v for k, v in lab.items()}
        seqs.append([sd.name, len(frames)])
        print(sd.name, len(frames), "frames", sum(len(v) for v in lab.values()), "boxes", flush=True)
    json.dump(labels, open(DST / "labels.json", "w"))
    json.dump(seqs, open(DST / "sequences.json", "w"))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="val", choices=["val", "train"])
    a = ap.parse_args()
    if a.split == "train":
        SRC = ROOT / "datasets" / "visdrone_vid" / "VisDrone2019-VID-train"
        DST = ROOT / "datasets" / "visdrone_vid_train_640"
    main()
