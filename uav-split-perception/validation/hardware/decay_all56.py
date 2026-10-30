#!/usr/bin/env python3
"""The staleness decay and the forecaster on all 56 VisDrone-VID train sequences, not 8 (29 Oct 2026).

The decay curve the controller schedules for (staleness_decay_forecast_v2.json) and the forecaster's settings
(forecast_tuning_v2.json) come from 8 of the 56 train sequences. This rebuilds both measurements on all 56 with
the same pipeline and the same frozen forecaster, writing only new files:
  prepare   640-px frames (first MAX_FRAMES of each sequence, as forecast.py uses) and labels, as prepare_vid.py,
            into datasets/visdrone_vid_train56_640/; the 8 sequences already prepared are copied unchanged
  dets      COCO YOLOv8s @640, settings of forecast.py dets; the 8 known sequences reuse forecast_train_dets.npz
            (CPU) -> experiments/results/hardware/forecast_train56_dets.npz  (--part i/n to split). The 48 new ones
            were run on the laptop GPU (--device 0; the CPU was too slow beside other work), and the 8 known ones
            again on the GPU (--with-old) so that decay can report the device's effect on the same 8 sequences
  ego       camera-motion chains (egomotion.step, as on the Pi) -> datasets/visdrone_vid_train56_640/egomotion.npz
  decay     forecast.py decay on all 56, on the 8 and on the 48 new ones (unseen by the forecaster's tuning):
            -> experiments/results/hardware/staleness_decay_train56.json
  replay    v4.1 scheduling with the 56-sequence curve, against the 19.8 replay runs with the stored curve
usage: decay_all56.py prepare [--skip SEQ,SEQ] | dets [--part 0/3] [--only SEQ,SEQ] [--device 0] [--with-old] |
       merge_dets | ego | decay | replay
"""
import json
import multiprocessing as mp
import shutil
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import forecast as F  # noqa: E402

ROOT = HERE.parent.parent
OLD = ROOT / "datasets" / "visdrone_vid_train_640"
FULL = ROOT / "datasets" / "visdrone_vid_full" / "VisDrone2019-VID-train" / "VisDrone2019-VID-train"
DST = ROOT / "datasets" / "visdrone_vid_train56_640"
DETS56 = F.OUT / "forecast_train56_dets.npz"
OUT = F.OUT / "staleness_decay_train56.json"
VISDRONE_TO_COCO = {1: 0, 2: 0, 3: 1, 4: 2, 5: 2, 6: 7, 9: 5, 10: 3}   # = prepare_vid.py


def cmd_prepare(skip=()):
    import cv2
    old = dict(json.load(open(OLD / "sequences.json")))
    old_lab = json.load(open(OLD / "labels.json"))
    DST.mkdir(exist_ok=True)
    labels, seqs = {}, []
    names = {p.name for p in (FULL / "sequences").iterdir() if p.is_dir()} | set(old)
    for sd in sorted(FULL / "sequences" / x for x in names):
        if sd.name in skip:                                  # still downloading: prepared in a later run
            continue
        if sd.name in old:                                   # already prepared: copy the same frames and labels
            n = min(old[sd.name], F.MAX_FRAMES)
            (DST / sd.name).mkdir(exist_ok=True)
            for i in range(1, n + 1):
                shutil.copy2(OLD / sd.name / ("%07d.jpg" % i), DST / sd.name / ("%07d.jpg" % i))
            labels[sd.name] = old_lab[sd.name]
            seqs.append([sd.name, n])
            continue
        frames = sorted(sd.glob("*.jpg"))[:F.MAX_FRAMES]
        h, w = cv2.imread(str(frames[0])).shape[:2]
        s = 640.0 / w
        (DST / sd.name).mkdir(exist_ok=True)
        for f in frames:
            img = cv2.imread(str(f))
            cv2.imwrite(str(DST / sd.name / f.name), cv2.resize(img, (640, round(h * s)), interpolation=cv2.INTER_AREA),
                        [cv2.IMWRITE_JPEG_QUALITY, 95])
        lab = {}
        for line in open(FULL / "annotations" / f"{sd.name}.txt"):
            v = [int(x) for x in line.strip().split(",")[:8]]
            fr, _, x, y, bw, bh, score, cat = v
            if score == 0 or cat not in VISDRONE_TO_COCO or fr > len(frames):
                continue
            lab.setdefault(str(fr), []).append([VISDRONE_TO_COCO[cat], round(x * s, 2), round(y * s, 2),
                                                round((x + bw) * s, 2), round((y + bh) * s, 2)])
        labels[sd.name] = lab
        seqs.append([sd.name, len(frames)])
        print(sd.name, len(frames), "frames", flush=True)
    json.dump(labels, open(DST / "labels.json", "w"))
    json.dump(seqs, open(DST / "sequences.json", "w"))
    print(len(seqs), "sequences,", sum(n for _, n in seqs), "frames")


def cmd_dets(part="0/1", only=None, device="cpu", with_old=False):
    import os
    import torch
    os.nice(19)
    from ultralytics import YOLO
    torch.set_num_threads(4)
    i, k = (int(x) for x in part.split("/"))
    old = set(dict(json.load(open(OLD / "sequences.json"))))
    todo = [(sq, n) for sq, n in json.load(open(DST / "sequences.json")) if (with_old or sq not in old) and (not only or sq in only)][i::k]
    tag = (f"_{'-'.join(sorted(only))}" if only else "") + ("" if device == "cpu" else "_gpu") + ("_withold" if with_old else "")
    m = YOLO(str(F.WEIGHTS))
    out = {}
    for sq, n in todo:
        for j in range(1, n + 1):
            r = m.predict(str(DST / sq / ("%07d.jpg" % j)), imgsz=640, conf=0.01, iou=0.45, max_det=100,
                          verbose=False, device=device)[0]
            b = r.boxes.cpu()
            out[f"{sq}/{j}"] = np.concatenate([b.xyxy.numpy(), b.conf.numpy()[:, None], b.cls.numpy()[:, None]],
                                              1).astype(np.float32)
        print(sq, n, flush=True)
    np.savez_compressed(F.OUT / f"forecast_train56_dets_part{i}of{k}{tag}.npz", **out)


def cmd_merge_dets():
    out = {k: v for k, v in np.load(F.DETS).items()}         # the 8 known sequences, unchanged
    old = set(dict(json.load(open(OLD / "sequences.json"))))
    for f in sorted(F.OUT.glob("forecast_train56_dets_part*.npz")):   # new sequences only (the 8 stay as stored)
        out.update({k: v for k, v in np.load(f).items() if k.split("/")[0] not in old})
    need = {f"{sq}/{j}" for sq, n in json.load(open(DST / "sequences.json")) for j in range(1, n + 1)}
    assert need <= set(out), f"missing {len(need - set(out))} frames"
    np.savez_compressed(DETS56, **{k: out[k] for k in sorted(need)})
    print(len(need), "frames ->", DETS56)


def cmd_ego():
    from egomotion import chain_sequence
    old = np.load(OLD / "egomotion.npz")
    out = {}
    for sq, n in json.load(open(DST / "sequences.json")):
        out[sq] = old[sq][:n + 1] if sq in old.files else chain_sequence(DST / sq, n)
        print(sq, n, flush=True)
    np.savez_compressed(DST / "egomotion.npz", **out)


def _decay_job_seqs(params, lag, seqs, dets=DETS56):
    """forecast._decay_job on a given list of sequences (same code path otherwise)."""
    from stream_ap import Acc
    d = np.load(dets)
    labels = json.load(open(DST / "labels.json"))
    acc = Acc()
    for sq, n in seqs:
        n = min(n, F.MAX_FRAMES)
        fc = F._make(params, DST)
        for c in range(1, n + 1, F.STRIDE):
            if fc:
                fc.observe(c, c / 30.0, sq, d[f"{sq}/{c}"], fidx=c)
            t = c + lag
            if t <= max(F.DECAY_LAGS) or t > n:
                continue
            pred = d[f"{sq}/{c}"]
            if fc:
                pred = fc.predict(c, pred, c / 30.0, t / 30.0, (640, 640), seq=sq, fidx_c=c, fidx_t=t)
            acc.add(pred, np.array(labels[sq].get(str(t), []), np.float32).reshape(-1, 5))
    return acc.ap()[0]


def _job(args):
    params, lag, subset, dets = args
    seqs = [x for x in json.load(open(DST / "sequences.json")) if x[0] in subset]
    return _decay_job_seqs(params, lag, seqs, dets)


def cmd_decay(workers=6):
    best = json.load(open(F.OUT / "forecast_tuning_v2.json"))["best"]["params"]
    allq = [sq for sq, _ in json.load(open(DST / "sequences.json"))]
    old = set(dict(json.load(open(OLD / "sequences.json"))))
    subsets = {"all56": allq, "old8": [s for s in allq if s in old], "new48": [s for s in allq if s not in old]}
    gpu = F.OUT / "forecast_train56_dets_part0of1_gpu_withold.npz"      # device check: the 8 with GPU detections
    dets = {k: DETS56 for k in subsets}
    if gpu.exists():
        subsets["old8_gpu"], dets["old8_gpu"] = subsets["old8"], gpu
    jobs = [(p, lag, tuple(sub), dets[name]) for name, sub in subsets.items() for p in (None, best) for lag in F.DECAY_LAGS]
    with mp.get_context("fork").Pool(workers) as pool:
        res = pool.map(_job, jobs, chunksize=1)
    n = len(F.DECAY_LAGS)
    out = {"lag_frames": F.DECAY_LAGS, "lag_ms": [round(x * 1000 / 30, 1) for x in F.DECAY_LAGS], "forecaster": best,
           "note": "VisDrone-VID train (first %d frames per sequence), YOLOv8s@640 CPU detections, one result every "
                   "%d frames, ratio relative to fresh AP without forecasting" % (F.MAX_FRAMES, F.STRIDE), "subsets": {}}
    for i, (name, sub) in enumerate(subsets.items()):
        plain, fc = res[2 * i * n:(2 * i + 1) * n], res[(2 * i + 1) * n:(2 * i + 2) * n]
        out["subsets"][name] = {"sequences": len(sub), "ap": fc, "ap_no_forecast": plain,
                                "ratio": [a / plain[0] for a in fc], "ratio_no_forecast": [a / plain[0] for a in plain]}
    ref = json.load(open(F.OUT / "staleness_decay_forecast_v2.json"))
    out["stored_8seq_curve"] = {"ratio": ref["ratio"], "ratio_no_forecast": ref["ratio_no_forecast"]}
    json.dump(out, open(OUT, "w"), indent=1)
    print("stored (8 seq)  ", [round(r, 3) for r in ref["ratio"]])
    for name, s in out["subsets"].items():
        print(f"{name:6s} fc       ", [round(r, 3) for r in s["ratio"]])
        print(f"{name:6s} no fc    ", [round(r, 3) for r in s["ratio_no_forecast"]])


def cmd_replay():
    """v4.1 scheduling with the 56-sequence curve against v4.1 with the stored one, in the replay (oracle_oct29_plant
    settings: 4 scenarios x 5 seeds, per-phase reset) -> staleness_decay_train56_replay.json"""
    import replay as R
    from stream_ap import evaluate
    d = json.load(open(OUT))["subsets"]["all56"]
    cur = {"lag_ms": json.load(open(OUT))["lag_ms"], "ratio": d["ratio"]}
    R.NETEM_LEGACY = False
    R.POLICIES["v41_d56"] = dict(R.POLICIES["v41"], decay="train56")
    gp = R.load_goodput()
    c, decays, accs, vd = R.load_all()
    decays["train56"] = cur
    labels = json.load(open(R.VID / "labels.json"))
    fp = json.load(open(R.HW / "forecast_tuning_v2.json"))["best"]["params"]
    rows, base = [], R.HW / "replay" / "oracle_oct29_plant" / "rows"
    for sc in ("mission", "mission_mirror", "random", "static_good"):
        for seed in range(1, 6):
            path, m = R.Replay("v41_d56", sc, 20.0, seed, gp, c, decays, vd, accs).run(R.HW / "replay" / "decay56_oct29")
            s56 = evaluate(path, labels, "newest", forecast=fp)["sAP"]
            ref = json.load(open(base / f"{sc}__v41__r{seed}.json"))
            rows.append({"scenario": sc, "seed": seed, "sAP_d56": s56, "sAP_stored": ref["sAP"],
                         "pi_w_d56": m["pi_w"], "pi_w_stored": ref["pi_w"]})
            print(rows[-1], flush=True)
    dd = np.array([r["sAP_d56"] - r["sAP_stored"] for r in rows])
    from report_rescore import t975
    out = {"rows": rows, "diff_mean": float(dd.mean()), "diff_ci95": float(t975(len(dd) - 1) * dd.std(ddof=1) / np.sqrt(len(dd))),
           "n": len(dd)}
    json.dump(out, open(F.OUT / "staleness_decay_train56_replay.json", "w"), indent=1)
    print(f"v4.1 with the 56-sequence curve - stored curve: {out['diff_mean']:+.4f} +- {out['diff_ci95']:.4f} sAP (n {len(dd)})")


if __name__ == "__main__":
    c = sys.argv[1]
    opt = lambda f: sys.argv[sys.argv.index(f) + 1].split(",") if f in sys.argv else None  # noqa: E731
    if c == "dets":
        cmd_dets(sys.argv[sys.argv.index("--part") + 1] if "--part" in sys.argv else "0/1", opt("--only"),
                 (opt("--device") or ["cpu"])[0], "--with-old" in sys.argv)
    elif c == "prepare":
        cmd_prepare(opt("--skip") or ())
    else:
        {"merge_dets": cmd_merge_dets, "ego": cmd_ego, "decay": cmd_decay, "replay": cmd_replay}[c]()
