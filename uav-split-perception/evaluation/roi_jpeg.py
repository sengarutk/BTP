#!/usr/bin/env python3
"""Region-of-interest JPEG with server feedback as the image family (paper 1, roadmap P1-9, 12 Nov 2026).

Why. A camera that knows where the objects are can spend its bits there (AccMPEG, DDS). It needs no onboard network
if the server sends back what it detected (DDS-style feedback): this is the strongest image family that costs the
drone only JPEG encodes.

Method. VisDrone-VID validation frames (video_codecs.py's sequences, 640 x 360), every frame in order, in a closed loop.
- The server runs the YOLOv8s on each frame it reconstructs (conf 0.25, the predictor's default) and returns the boxes.
- The camera uses the boxes of frame t - LAG (LAG = 2 frames: about 67 ms at 30 fps, for the up-link, the server and
  the down-link). Each box is grown by MARGIN pixels and snapped outward to the 16-pixel MCU grid; this is the mask.
- Two JPEGs per frame (OpenCV, single thread): the whole frame at the background quality q_b, and the frame at the
  region quality q_r with every pixel outside the mask set to mid-grey. Flat MCUs cost almost nothing in JPEG.
- The server knows the boxes it sent, so it rebuilds the mask without any side information. The reconstruction is the
  q_r layer inside the mask and the q_b layer outside it. Payload = the two JPEGs.
- The first LAG frames of a sequence have no feedback, so only the q_b layer is sent.
The frames scored are the scored frames of video_codecs.py (9 of 10; the tenth is coded but not scored, since it is in
the loop). Accuracy: the validator on the reconstructions, as for every image option. Timings: both encodes and the
mask (camera), both decodes and the compositing (server), single thread, this laptop.
usage: roi_jpeg.py eval [--qb Q ...] [--qr Q ...] | analyse  -> experiments/results/roi_jpeg/
"""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
OUT = REPO / "experiments" / "results" / "roi_jpeg"
LAG, MARGIN, MCU = 2, 16, 16
QB, QR = (10, 20, 30), (50, 70, 90)


def mask_from(boxes, h, w):
    m = np.zeros((h, w), bool)
    for x0, y0, x1, y1 in boxes:
        x0 = max(0, int(x0 - MARGIN) // MCU * MCU)
        y0 = max(0, int(y0 - MARGIN) // MCU * MCU)
        x1 = min(w, -(-int(np.ceil(x1 + MARGIN)) // MCU) * MCU)
        y1 = min(h, -(-int(np.ceil(y1 + MARGIN)) // MCU) * MCU)
        m[y0:y1, x0:x1] = True
    return m


def cmd_eval(a):
    from ultralytics import YOLO
    from evaluation import video_codecs as V
    cv2.setNumThreads(1)
    OUT.mkdir(parents=True, exist_ok=True)
    det = YOLO(str(REPO / "weights" / "yolov8s_visdrone.pt"))
    for qb in a.qb or QB:
        for qr in a.qr or QR:
            opt = f"roi_qb{qb}_qr{qr}"
            f_out = OUT / f"{opt}.json"
            if f_out.exists():
                continue
            d = V.WORK / opt / "images"
            d.mkdir(parents=True, exist_ok=True)
            sizes, enc_ms, dec_ms, frac = [], [], [], []
            for seq, nf in V.sequences():
                hist = []                      # the server's boxes per frame
                for f in range(1, nf + 1):
                    img = cv2.imread(str(V.SRC / seq / f"{f:07d}.jpg"))
                    h, w = img.shape[:2]
                    t0 = time.perf_counter()
                    boxes = hist[f - 1 - LAG] if f - 1 - LAG >= 0 else None
                    _, b1 = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, qb])
                    b2, m = None, None
                    if boxes is not None and len(boxes):
                        m = mask_from(boxes, h, w)
                        roi = np.where(m[..., None], img, np.uint8(128))
                        _, b2 = cv2.imencode(".jpg", roi, [cv2.IMWRITE_JPEG_QUALITY, qr])
                    te = (time.perf_counter() - t0) * 1e3
                    t0 = time.perf_counter()
                    rec = cv2.imdecode(b1, cv2.IMREAD_COLOR)
                    if b2 is not None:
                        rec = np.where(m[..., None], cv2.imdecode(b2, cv2.IMREAD_COLOR), rec)
                    td = (time.perf_counter() - t0) * 1e3
                    r = det.predict(rec, imgsz=640, conf=0.25, verbose=False, device="cuda")[0]
                    hist.append(r.boxes.xyxy.cpu().numpy() if r.boxes is not None else np.zeros((0, 4)))
                    if not V.scored(f):
                        continue
                    sizes.append(len(b1) + (len(b2) if b2 is not None else 0))
                    enc_ms.append(te)
                    dec_ms.append(td)
                    frac.append(float(m.mean()) if m is not None else 0.0)
                    cv2.imwrite(str(d / f"{seq}_{f:07d}.png"), rec, [cv2.IMWRITE_PNG_COMPRESSION, 1])
            res = V.evaluate(opt, f"vc_{opt}")
            row = {"option": opt, "family": "roi", "qb": qb, "qr": qr, "lag": LAG, "margin": MARGIN,
                   "frames": len(sizes), "payload_bytes_mean": float(np.mean(sizes)),
                   "payload_bytes_p95": float(np.percentile(sizes, 95)), "encode_ms_median": float(np.median(enc_ms)),
                   "decode_ms_median": float(np.median(dec_ms)), "roi_area_mean": float(np.mean(frac)),
                   "map50_95": res["map50_95"], "map50": res["map50"], "num_images": res["num_images"]}
            assert row["frames"] == res["num_images"]
            json.dump(row, open(f_out, "w"), indent=1)
            shutil.rmtree(d)
            print(json.dumps(row), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("eval")
    e.add_argument("--qb", type=int, nargs="+")
    e.add_argument("--qr", type=int, nargs="+")
    a = ap.parse_args()
    {"eval": cmd_eval}[a.cmd](a)


if __name__ == "__main__":
    main()
