#!/usr/bin/env python3
"""Streaming AP of YOLOv8s / m / l running ONBOARD on the Pi 5, on VisDrone2019-VID val.

Step 1 (laptop GPU, `dets`): detections of each model at 640 px on every val frame, exactly as the Pi's onboard
engine produces them (letterboxed 640 input, conf 0.01, NMS IoU 0.45, 100 boxes), stored like the live runs'
_dets.npz. Offline ("fresh") AP of each model = its accuracy with zero delay, the ceiling for streaming AP.

Step 2 (`emulate`): what the Pi would hold. A single onboard engine processes the newest camera frame, takes L ms,
then immediately takes the newest frame again (as adaptive2.py's Onboard thread with a fixed onboard policy); the
drone holds the newest result until the next one arrives. Every camera frame (30 fps) is scored against its own
ground truth with stream_ap.evaluate, the same scorer as every live campaign (standard 'newest' rule), without and
with forecaster v2 (offline camera-motion chain). Computed for a grid of latencies, so the Pi's measured inference
time can be read off once it is measured (step 3: live runs on the Pi with `fixed:onboard:<model>`).

usage: onboard_sap.py dets            (laptop GPU)
       onboard_sap.py emulate [--lat-ms 300,600,...]
Output: experiments/results/hardware/onboard_sap/  (dets_<model>.npz, onboard_sap_emulated.json)
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ROOT = HERE.parent.parent
VID = ROOT / "datasets" / "visdrone_vid_640"
HW = ROOT / "experiments" / "results" / "hardware"
OUT = HW / "onboard_sap"
MODELS = {"yolov8s": ROOT / "yolov8s.pt", "yolov8m": ROOT / "weights" / "yolov8m.pt",
          "yolov8l": ROOT / "weights" / "yolov8l.pt",
          # VisDrone fine-tuned (scripts/train_visdrone.py); only those already trained are used
          "yolov8s_vd": ROOT / "weights" / "yolov8s_visdrone.pt", "yolov8m_vd": ROOT / "weights" / "yolov8m_visdrone.pt",
          "yolov8l_vd": ROOT / "weights" / "yolov8l_visdrone.pt"}
MODELS = {k: v for k, v in MODELS.items() if v.exists()}
PERIOD = 1.0 / 30.0


def keys():
    seqs = json.load(open(VID / "sequences.json"))
    return [(sq, i) for sq, n in seqs for i in range(1, n + 1)]


def cmd_dets(device):
    import cv2
    from ultralytics import YOLO
    from ultralytics.data.augment import LetterBox
    OUT.mkdir(parents=True, exist_ok=True)
    lb = LetterBox((640, 640), auto=False)
    for name, w in MODELS.items():
        f = OUT / f"dets_{name}.npz"
        if f.exists():
            continue
        m = YOLO(str(w))
        out = {}
        for sq, i in keys():
            img = lb(image=cv2.imread(str(VID / sq / ("%07d.jpg" % i))))
            b = m.predict(img, imgsz=640, conf=0.01, iou=0.45, max_det=100, verbose=False, device=device)[0].boxes
            out[f"{sq}/{i}"] = np.concatenate([b.xyxy.cpu().numpy(), b.conf.cpu().numpy()[:, None],
                                               b.cls.cpu().numpy()[:, None]], 1).astype(np.float32)
        np.savez_compressed(f, **out)
        print(name, "detections done", flush=True)


def synth_run(name, lat_ms, dets, ks, path):
    """A run file in the live format: one onboard engine, latency lat_ms per result, newest frame each time."""
    n = len(ks)
    frames, t_free, rid = [], 0.0, {}
    for tick in range(n):
        t = tick * PERIOD
        rec = {"id": tick, "phase": "onboard", "frame": list(ks[tick])}
        if t >= t_free - 1e-9:                     # engine free: take this (the newest) frame
            t_free = t + lat_ms / 1e3
            rec.update(server="onboard", variant=name, res=640, t_res=round(t_free, 4))
            rid[str(tick)] = dets[f"{ks[tick][0]}/{ks[tick][1]}"]
        frames.append(rec)
    json.dump({"policy": f"onboard:{name}", "scenario": "static", "frames": frames}, open(path, "w"))
    np.savez_compressed(str(path)[:-5] + "_dets.npz", **rid)


def cmd_emulate(lats):
    from stream_ap import evaluate
    labels = json.load(open(VID / "labels.json"))
    fp = json.load(open(HW / "forecast_tuning_v2.json"))["best"]["params"]
    ks = keys()
    res = {}
    tmp = OUT / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    for name in MODELS:
        z = np.load(OUT / f"dets_{name}.npz")
        dets = {k: z[k] for k in z.files}
        res[name] = {"fresh_AP": None, "by_latency_ms": {}}
        for L in lats:
            p = tmp / f"a2_{name}_{L}.json"
            synth_run(name, L, dets, ks, p)
            r0 = evaluate(p, labels, "newest")
            r1 = evaluate(p, labels, "newest", forecast=fp)
            res[name]["fresh_AP"] = r0["fresh_AP"]
            res[name]["by_latency_ms"][L] = {"sAP": r0["sAP"], "sAP50": r0["sAP50"], "sAP_fc2": r1["sAP"],
                                             "sAP50_fc2": r1["sAP50"], "results": r0["results"]}
            print(f"{name} L={L:5d} ms  fresh AP {r0['fresh_AP']:.4f}  sAP {r0['sAP']:.4f} (AP50 {r0['sAP50']:.4f})"
                  f"  with forecaster {r1['sAP']:.4f} (AP50 {r1['sAP50']:.4f})", flush=True)
    json.dump(res, open(OUT / "onboard_sap_emulated.json", "w"), indent=1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["dets", "emulate"])
    ap.add_argument("--device", default="0")
    ap.add_argument("--lat-ms", default="33,100,300,600,1000,1500,2000,3000,4000,6000")
    a = ap.parse_args()
    if a.cmd == "dets":
        cmd_dets(a.device)
    else:
        cmd_emulate([int(x) for x in a.lat_ms.split(",")])
