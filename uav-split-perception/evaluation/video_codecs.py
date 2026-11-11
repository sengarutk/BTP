#!/usr/bin/env python3
"""Video codecs as the image family of the break-even rule (paper 1, roadmap P1-1, 11 Nov 2026).

Why. A drone streams video. Per-frame JPEG ignores the redundancy between frames that H.264/H.265 exploit, so a
reviewer can ask whether the image side was given its strongest codec. Proposition prop:be-family holds for any image
family with per-option payload b_q, onboard time e_q and accuracy A_q, so the rule can be evaluated with video codecs.

Frames. The 7 VisDrone2019-VID val sequences at 640 x 360 (datasets/visdrone_vid_640, 2846 frames, labels mapped to
COCO ids by prepare_vid.py). Every 10th frame (1, 11, ...) is one of the 288 frames used to select the epochs of the
jointly trained and the JPEG-tuned detectors, so those frames are encoded (the video needs them) but never scored:
2558 scored frames, the same for every option.
Options (every one decoded to lossless PNG, then scored by the VisDrone YOLOv8s, batch 1, mAP@[.5:.95]):
  raw         the frames as stored (the reference)
  jpeg_qQ     OpenCV JPEG at the 18 qualities of the rule (as benchmark_codecs.make_codec_hook), per frame
  x264 / x265 libx264 / libx265, low delay: -tune zerolatency, no B-frames, periodic intra refresh instead of key
              frames (keyint 60, no I-frame bursts), 30 fps, constant quality (CRF grid); presets ultrafast and medium
  nvenc       h264_nvenc low latency (p1, no B-frames, constant quality): the laptop GPU's hardware encoder, a
              stand-in for a dedicated encoder (neither the Pi 5 nor the Jetson Orin Nano has one)
  codes       the learned (uint8 + zstd) and entropy-coded split codes at k4, on the raw frames
  tuned       the JPEG-tuned detector (mixed qualities) on the same JPEG frames (jpeg_tuned)
  joint       the jointly trained codes (their own server side). Their epoch, like the tuned detector's, was chosen
              on the 288 excluded frames, which come from the same 7 sequences: these two are not fully held out here
Payload: mean bytes per frame (video: per-packet sizes from ffprobe; p95 also kept, since a frame must arrive by its
deadline). Encode time: single-thread wall time per frame on this laptop's CPU (video: from raw YUV, so the source
JPEG decode is not counted; decode to no output), for JPEG and the software video
encoders alike (the rule scales host times to each device's speed, as it does for every option); decode time likewise.
The video options assume an error-free stream (a lost frame would corrupt the frames that reference it); this favours
video and is stated.
usage: video_codecs.py prepare | raw | jpeg | video | codes | jpeg_tuned | analyse  -> experiments/results/video_codecs/
"""
import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "datasets" / "visdrone_vid_640"
WORK = REPO / "experiments" / "video_codecs_work"          # decoded frames (temporary, not in git)
OUT = REPO / "experiments" / "results" / "video_codecs"
LABELS = WORK / "labels"
JPEG_Q = tuple(range(10, 100, 5))
CRF = (18, 23, 28, 33, 38, 43)
VIDEO = {"x264_ultrafast": ("libx264", "ultrafast"), "x264_medium": ("libx264", "medium"),
         "x265_ultrafast": ("libx265", "ultrafast"), "x265_medium": ("libx265", "medium"), "nvenc": ("h264_nvenc", "p1")}
NAMES = {0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 4: "airplane", 5: "bus", 6: "train", 7: "truck"}


def sequences():
    return json.load(open(SRC / "sequences.json"))


def scored(f):
    return (f - 1) % 10 != 0


def yaml_for(opt):
    d = WORK / opt
    y = d / "data.yaml"
    names = json.load(open(REPO / "experiments" / "results" / "video_codecs" / "names.json"))
    y.write_text(f"path: {d}\ntrain: images\nval: images\nnames:\n" + "".join(f"  {k}: {v}\n" for k, v in names.items()))
    lab = d / "labels"
    if not lab.exists():
        lab.symlink_to(LABELS, target_is_directory=True)
    return y


def cmd_prepare(a):
    """YOLO labels of the scored frames and the raw option (symlinks)."""
    from ultralytics import YOLO
    names = YOLO(str(REPO / "weights" / "yolov8s_visdrone.pt")).model.names
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump({str(k): v for k, v in names.items()}, open(OUT / "names.json", "w"))
    labels = json.load(open(SRC / "labels.json"))
    LABELS.mkdir(parents=True, exist_ok=True)
    raw = WORK / "raw" / "images"
    raw.mkdir(parents=True, exist_ok=True)
    n = 0
    for seq, nf in sequences():
        for f in range(1, nf + 1):
            if not scored(f):
                continue
            stem = f"{seq}_{f:07d}"
            img = SRC / seq / f"{f:07d}.jpg"
            h, w = cv2.imread(str(img)).shape[:2]
            rows = []
            for cls, x0, y0, x1, y1 in labels[seq].get(str(f), []):
                x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
                if x1 > x0 and y1 > y0:
                    rows.append(f"{int(cls)} {(x0 + x1) / 2 / w:.6f} {(y0 + y1) / 2 / h:.6f} {(x1 - x0) / w:.6f} "
                                f"{(y1 - y0) / h:.6f}")
            (LABELS / f"{stem}.txt").write_text("\n".join(rows) + ("\n" if rows else ""))
            dst = raw / f"{stem}.png"
            if not dst.exists():
                cv2.imwrite(str(dst), cv2.imread(str(img)), [cv2.IMWRITE_PNG_COMPRESSION, 1])
            n += 1
    yaml_for("raw")
    print(f"{n} scored frames", flush=True)


def evaluate(opt, name, hook=None, layer=None, weights=None, prep=None):
    """mAP of the decoded frames of option `opt` (cached per-image stats under the given name). weights: another
    checkpoint (the JPEG-tuned or a jointly trained detector); prep(yolo): adapts its model before scoring."""
    from ultralytics import YOLO
    from evaluation.detection_eval import run_validation
    yolo = YOLO(str(weights or REPO / "weights" / "yolov8s_visdrone.pt"))
    if prep:
        prep(yolo)
    h = yolo.model.model[layer].register_forward_hook(hook) if hook else None
    try:
        return run_validation(yolo, str(yaml_for(opt)), "cuda", name=name, cache=hook is None and prep is None)
    finally:
        if h:
            h.remove()


def timed(fn, reps=1):
    t0 = time.perf_counter()
    for _ in range(reps):
        r = fn()
    return r, (time.perf_counter() - t0) / reps * 1e3


def jpeg_frames(q, d):
    """Encode every scored frame at quality q (OpenCV, single thread), decode, write the decoded PNGs to d."""
    d.mkdir(parents=True, exist_ok=True)
    sizes, enc_ms, dec_ms = [], [], []
    for seq, nf in sequences():
        for f in range(1, nf + 1):
            if not scored(f):
                continue
            img = cv2.imread(str(SRC / seq / f"{f:07d}.jpg"))
            (ok, buf), te = timed(lambda: cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, q]))
            dec, td = timed(lambda: cv2.imdecode(buf, cv2.IMREAD_COLOR))
            sizes.append(len(buf))
            enc_ms.append(te)
            dec_ms.append(td)
            cv2.imwrite(str(d / f"{seq}_{f:07d}.png"), dec, [cv2.IMWRITE_PNG_COMPRESSION, 1])
    return sizes, enc_ms, dec_ms


def cmd_jpeg_tuned(a):
    """The JPEG-tuned detector (jpeg_tuned_detector.py, mixed qualities) on the same JPEG frames. Its first layer's
    in-model JPEG round trip is removed: the frames are already the decoded JPEGs, as for the untuned rows."""
    from evaluation.jpeg_tuned_detector import CKPT as JT, JpegInput
    import __main__                    # saved by jpeg_tuned_detector.py run as a script: its layer-0 wrapper is
    __main__.JpegInput = JpegInput     # pickled as __main__.JpegInput
    run = "jpegtuned_qmix_r1"

    def prep(yolo):
        w = yolo.model.model[0]
        assert isinstance(w, JpegInput), type(w)
        yolo.model.model[0] = w.layer
    cv2.setNumThreads(1)
    for q in a.q or JPEG_Q:
        opt, f_out = f"jpeg_q{q}", OUT / f"tuned_jpeg_q{q}.json"
        if f_out.exists():
            continue
        ref = json.load(open(OUT / f"{opt}.json"))
        sizes, _, _ = jpeg_frames(q, WORK / opt / "images")
        assert abs(np.mean(sizes) - ref["payload_bytes_mean"]) < 1e-6 * ref["payload_bytes_mean"], q
        res = evaluate(opt, f"vc_tuned_{opt}", weights=JT / f"{run}.pt", prep=prep)
        row = {"option": opt, "detector": run, "q": q, "payload_bytes_mean": float(np.mean(sizes)),
               "map50_95": res["map50_95"], "map50": res["map50"], "map50_95_untuned": ref["map50_95"],
               "num_images": res["num_images"]}
        json.dump(row, open(f_out, "w"), indent=1)
        shutil.rmtree(WORK / opt / "images")
        print(json.dumps(row), flush=True)


def cmd_jpeg(a):
    cv2.setNumThreads(1)
    for q in a.q or JPEG_Q:
        opt = f"jpeg_q{q}"
        f_out = OUT / f"{opt}.json"
        if f_out.exists():
            continue
        d = WORK / opt / "images"
        sizes, enc_ms, dec_ms = jpeg_frames(q, d)
        res = evaluate(opt, f"vc_{opt}")
        row = {"option": opt, "family": "jpeg", "q": q, "frames": len(sizes), "payload_bytes_mean": float(np.mean(sizes)),
               "payload_bytes_p95": float(np.percentile(sizes, 95)), "encode_ms_median": float(np.median(enc_ms)),
               "decode_ms_median": float(np.median(dec_ms)), "map50_95": res["map50_95"], "map50": res["map50"],
               "num_images": res["num_images"]}
        json.dump(row, open(f_out, "w"), indent=1)
        shutil.rmtree(d)
        print(json.dumps(row), flush=True)


def ffprobe_sizes(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=size", "-of",
                          "csv=p=0", str(path)], capture_output=True, text=True, check=True).stdout.split()
    return [int(x) for x in out]


def encode_args(codec, preset, crf):
    if codec == "libx264":
        return ["-c:v", "libx264", "-preset", preset, "-tune", "zerolatency", "-crf", str(crf),
                "-x264-params", "bframes=0:keyint=60:intra-refresh=1:threads=1", "-f", "h264"]
    if codec == "libx265":
        return ["-c:v", "libx265", "-preset", preset, "-tune", "zerolatency", "-crf", str(crf),
                "-x265-params", "bframes=0:keyint=60:intra-refresh=1:pools=1:frame-threads=1:log-level=error",
                "-f", "hevc"]
    return ["-c:v", "h264_nvenc", "-preset", preset, "-tune", "ll", "-rc", "vbr", "-cq", str(crf), "-b:v", "0",
            "-bf", "0", "-g", "60", "-f", "h264"]


def cmd_video(a):
    for opt_base, (codec, preset) in VIDEO.items():
        if a.only and opt_base not in a.only:
            continue
        for crf in a.crf or CRF:
            opt = f"{opt_base}_crf{crf}"
            f_out = OUT / f"{opt}.json"
            if f_out.exists():
                continue
            d = WORK / opt / "images"
            d.mkdir(parents=True, exist_ok=True)
            tmp = WORK / opt / "tmp"
            tmp.mkdir(exist_ok=True)
            sizes, enc_s, dec_s, frames_all = [], 0.0, 0.0, 0
            for seq, nf in sequences():
                bs, y4m = tmp / f"{seq}.bit", tmp / f"{seq}.y4m"
                # the source frames as raw YUV first (untimed), so the timed encode does not include decoding the
                # stored JPEGs; the timed decode writes nothing (-f null), the PNGs for scoring come from a third pass
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", "30", "-start_number", "1",
                                "-i", str(SRC / seq / "%07d.jpg"), "-pix_fmt", "yuv420p", str(y4m)], check=True)
                t0 = time.perf_counter()
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-threads", "1", "-i", str(y4m),
                                *encode_args(codec, preset, crf), str(bs)], check=True)
                enc_s += time.perf_counter() - t0
                y4m.unlink()
                s = ffprobe_sizes(bs)
                assert len(s) == nf, (seq, len(s), nf)
                t0 = time.perf_counter()
                subprocess.run(["ffmpeg", "-v", "error", "-threads", "1", "-i", str(bs), "-f", "null", "-"], check=True)
                dec_s += time.perf_counter() - t0
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-threads", "1", "-i", str(bs), "-start_number", "1",
                                "-compression_level", "1", str(tmp / f"{seq}_%07d.png")], check=True)
                for f in range(1, nf + 1):
                    p = tmp / f"{seq}_{f:07d}.png"
                    if scored(f):
                        sizes.append(s[f - 1])
                        p.rename(d / p.name)
                    else:
                        p.unlink()
                frames_all += nf
            res = evaluate(opt, f"vc_{opt}")
            row = {"option": opt, "family": opt_base, "codec": codec, "preset": preset, "crf": crf,
                   "frames_scored": len(sizes), "frames_encoded": frames_all,
                   "payload_bytes_mean": float(np.mean(sizes)), "payload_bytes_p95": float(np.percentile(sizes, 95)),
                   "payload_bytes_max": int(np.max(sizes)),
                   "encode_ms_per_frame": 1e3 * enc_s / frames_all, "decode_ms_per_frame": 1e3 * dec_s / frames_all,
                   "timing_note": "single-thread wall time per frame, from raw YUV input (encode) and to no output (decode), "
                                  "incl. one ffmpeg start-up per sequence (upper bound)",
                   "map50_95": res["map50_95"], "map50": res["map50"], "num_images": res["num_images"]}
            json.dump(row, open(f_out, "w"), indent=1)
            shutil.rmtree(WORK / opt / "images")
            shutil.rmtree(tmp)
            print(json.dumps(row), flush=True)


def cmd_codes(a):
    """The learned (uint8 + zstd) and entropy-coded codes on the raw frames: payload and mAP."""
    import torch
    import zstandard
    from evaluation import entropy_bottleneck as E
    from evaluation import learned_bottleneck as L
    cz = zstandard.ZstdCompressor(level=1)
    lb = REPO / "experiments" / "results" / "learned_bottleneck"
    tags = [json.load(open(f))["config"] for f in sorted(lb.glob("eval_k4_*.json"))
            if json.load(open(f)).get("width") == 128 and json.load(open(f)).get("dec_layers") == 2]
    ecs = [json.load(open(f))["config"] for f in sorted((REPO / "experiments" / "results" / "entropy_bottleneck")
                                                        .glob("eval_ec_*.json"))]
    from evaluation import joint_bottleneck as J
    import __main__                    # the joint checkpoints were saved by joint_bottleneck.py run as a script, so
    __main__.CutWithBottleneck = J.CutWithBottleneck      # their wrapper is pickled as __main__.CutWithBottleneck
    joints = [json.load(open(f))["config"] for f in sorted((REPO / "experiments" / "results" / "joint_bottleneck")
                                                           .glob("eval_joint_*.json"))]
    for kind, tag in ([("learned", t) for t in tags] + [("entropy", t) for t in ecs]
                      + [("joint", t) for t in joints]):
        f_out = OUT / f"code_{tag}.json"
        if f_out.exists():
            continue
        sizes = []
        if kind == "joint":       # the whole detector of the joint run (bottleneck + its trained server side)
            ck_path = J.JCKPT / f"{tag[len('joint_'):]}.pt"
            rec = {"bytes": [], "values": [], "enc_ms": []}

            def prep(yolo, rec=rec):
                w = [m for m in yolo.model.model if isinstance(m, J.CutWithBottleneck)]
                assert len(w) == 1
                w[0].record = rec
            res = evaluate("raw", f"vc_code_{tag}", weights=ck_path, prep=prep)
            sizes = L.drop_warmup(rec["bytes"], res["num_images"])
            row = {"option": tag, "family": kind, "frames": len(sizes), "payload_bytes_mean": float(np.mean(sizes)),
                   "payload_bytes_p95": float(np.percentile(sizes, 95)), "map50_95": res["map50_95"],
                   "map50": res["map50"], "num_images": res["num_images"]}
            json.dump(row, open(f_out, "w"), indent=1)
            print(json.dumps(row), flush=True)
            continue
        if kind == "learned":
            bn, ck = L.load_bottleneck(L.CKPT / f"{tag}.pt", "cuda")

            def hook(m, i, out):
                with torch.no_grad():
                    rec = []
                    for b in range(out.shape[0]):
                        r, q = bn(out[b:b + 1].float())
                        sizes.append(len(cz.compress(q.cpu().numpy().tobytes())) + 8)
                        rec.append(r.to(out.dtype))
                    return torch.cat(rec)
        else:
            code, ck = E.load_code(E.CKPT / f"{tag}.pt", "cuda")
            coder = E.Coder(code)

            def hook(m, i, out):
                with torch.no_grad():
                    rec = []
                    for b in range(out.shape[0]):
                        y = code.latent(out[b:b + 1].float()).float()
                        sym = torch.round(y)[0].to(torch.int64).cpu().numpy()
                        data = coder.encode(sym)
                        assert np.array_equal(coder.decode(data, sym.shape), sym)
                        sizes.append(len(data))
                        rec.append(code.dec(torch.round(y) * torch.exp(-code.log_gain)).to(out.dtype))
                    return torch.cat(rec)
        res = evaluate("raw", f"vc_code_{tag}", hook=hook, layer=ck["cut"])
        sizes = L.drop_warmup(sizes, res["num_images"])
        row = {"option": tag if kind == "entropy" else f"learned_{tag}", "family": kind, "frames": len(sizes),
               "payload_bytes_mean": float(np.mean(sizes)), "payload_bytes_p95": float(np.percentile(sizes, 95)),
               "map50_95": res["map50_95"], "map50": res["map50"], "num_images": res["num_images"]}
        json.dump(row, open(f_out, "w"), indent=1)
        print(json.dumps(row), flush=True)


def cmd_analyse(a):
    """Break-even goodput (Proposition prop:be-family, break_even_rule.analyse) on these frames with three image
    families: per-frame JPEG, low-delay video (x264/x265), and both. Options are the rule's configurations with the
    payload and accuracy measured here. Timings: JPEG and video encode = this laptop's single-thread CPU time, scaled
    to each device like every host time in the rule ("scaled"); server side = the rule's JPEG server time with the
    decode measured here. Second timing ("free"): encode costs nothing onboard (a dedicated encoder; NVENC joins),
    the most favourable case for the image side. Codes keep the rule's timings (same network, same 640 input)."""
    import math
    from dataclasses import replace
    from evaluation import break_even_rule as b
    from evaluation.learned_bottleneck_system import measured_configs
    raw = json.load(open(OUT / "raw.json"))
    rows = {f.stem: json.load(open(f)) for f in OUT.glob("*.json") if f.stem not in ("raw", "names", "analysis")}
    base = measured_configs()
    det_jpeg = {c.name: c for c in b.jpeg_grid(base)}
    det_codes = {c.name: c for c in b.learned_and_joint() + b.entropy_codes()}
    onboard = next(c for c in base if c.kind == "onboard")
    A0 = raw["map50_95"]

    def opt(c, r, **kw):   # an option with this run's payload and accuracy, deltas against the raw frames
        return replace(c, payload_bytes=r["payload_bytes_mean"], map50_95=r["map50_95"], map50=r["map50"],
                       delta_map50_95=r["map50_95"] - A0, **kw)
    jp = {r["option"]: r for k, r in rows.items() if k.startswith("jpeg_q")}
    tuned = {r["option"]: r for k, r in rows.items() if k.startswith("tuned_jpeg_q")}
    vids = {k: r for k, r in rows.items() if "_crf" in k}
    codes = {r["option"]: r for k, r in rows.items() if k.startswith("code_")}
    q50 = jp["jpeg_q50"]

    def image_family(mode, which, best_tuned=False):
        out = []
        if which in ("jpeg", "both"):
            for n, r in jp.items():
                c = det_jpeg[n]
                if best_tuned and n in tuned and tuned[n]["map50_95"] > r["map50_95"]:
                    r = {**r, "map50_95": tuned[n]["map50_95"], "map50": tuned[n]["map50"]}
                out.append(opt(c, r, host_edge_proc_ms=r["encode_ms_median"] if mode == "scaled" else 0.0,
                               cloud_ms=c.cloud_ms - q50["decode_ms_median"] + r["decode_ms_median"]))
        if which in ("video", "both"):
            proto = det_jpeg["jpeg_q50"]
            for n, r in vids.items():
                if r["codec"] == "h264_nvenc" and mode == "scaled":
                    continue
                out.append(opt(proto, r, name=n, dtype=n,
                               host_edge_proc_ms=r["encode_ms_per_frame"] if mode == "scaled" else 0.0,
                               cloud_ms=proto.cloud_ms - q50["decode_ms_median"] + r["decode_ms_per_frame"]))
        return out
    splits = [opt(det_codes[n], r) for n, r in codes.items() if n in det_codes]
    others = [opt(onboard, raw | {"payload_bytes_mean": 0.0})] + splits
    res = {"frames": raw["num_images"], "raw_map50_95": A0, "method": cmd_analyse.__doc__, "cases": {}}
    for mode in ("scaled", "free"):
        for which in ("jpeg", "video", "both"):
            for bt in ((False, True) if tuned and which != "video" else (False,)):
                key = f"{which}_{mode}" + ("_best_of_both" if bt else "")
                fam_ = image_family(mode, which, bt)
                ar, viol, checked, wins = b.analyse(fam_, others)
                res["cases"][key] = {"rows": ar, "violations": viol, "wins_checked": checked, "wins_total": wins,
                                     "image_options": [c.name for c in fam_]}
                print(f"{key:28s} wins {wins:4d} exceptions {len(viol)}", flush=True)
    # rate-accuracy: the bytes each family needs for the accuracy of each JPEG quality (lower envelope of each family)
    env = {}
    fams = {"jpeg": list(jp.values())} | {f: [r for r in vids.values() if r["family"] == f] for f in VIDEO}
    for f, rs in fams.items():
        env[f] = {}
        for qn, rq in sorted(jp.items(), key=lambda kv: kv[1]["q"]):
            ok = [r["payload_bytes_mean"] for r in rs if r["map50_95"] >= rq["map50_95"]]
            env[f][qn] = min(ok) if ok else None
    res["bytes_for_jpeg_accuracy"] = env
    json.dump(res, open(OUT / "analysis.json", "w"), indent=1)
    by = lambda key: {(r["device"], r["code"]): r for r in res["cases"][key]["rows"]}
    m = {"VcFrames": str(raw["num_images"]), "VcRawMap": f"{A0:.3f}", "VcSeqs": str(len(sequences()))}
    pi = "Pi 5 (throttled)"
    for tag, key in (("Jpeg", "jpeg_scaled"), ("Video", "video_scaled"), ("Both", "both_scaled"),
                     ("BothFree", "both_free"), ("JpegTuned", "jpeg_scaled_best_of_both"),
                     ("BothTuned", "both_scaled_best_of_both")):
        if key not in res["cases"]:
            continue
        r_ = by(key)
        c = res["cases"][key]
        m[f"Vc{tag}Wins"], m[f"Vc{tag}Exc"] = str(c["wins_total"]), str(len(c["violations"]))
        for dn, dev in (("Pi", pi), ("Fast", "Jetson Orin Nano")):
            for cn, code in (("Joint", "joint_k4_c4_w128_d2"), ("Frozen", "learned_k4_c4_w128_d2")):
                r = r_.get((dev, code))
                if r is None:
                    continue
                m[f"Vc{tag}{cn}{dn}Be"] = "--" if r["b_be_mbps"] is None else f"{r['b_be_mbps']:.2f}"
                m[f"Vc{tag}{cn}{dn}Qstar"] = str(r["q_star"]).replace("jpeg_q", "Q").replace("_", " ")
                m[f"Vc{tag}{cn}{dn}Win"] = "--" if r["max_win_mbps"] is None else f"{r['max_win_mbps']:.2f}"
    for f in VIDEO:      # median byte saving over JPEG at equal accuracy, across the JPEG qualities each family reaches
        sv = [1 - env[f][q] / env["jpeg"][q] for q in env["jpeg"] if env[f].get(q) and env["jpeg"][q]]
        m["VcSave" + {"x264_ultrafast": "HtfUltra", "x264_medium": "HtfMedium", "x265_ultrafast": "HfvUltra",
                      "x265_medium": "HfvMedium", "nvenc": "Nvenc"}[f]] = \
            f"{100 * float(np.median(sv)):.0f}" if sv else "--"
    (OUT / "video_metrics.tex").write_text("% Generated by evaluation/video_codecs.py analyse -- do not edit.\n"
                                          + "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in m.items()))
    for k, v in m.items():
        print(k, v)


def cmd_raw(a):
    res = evaluate("raw", "vc_raw")
    row = {"option": "raw", "map50_95": res["map50_95"], "map50": res["map50"], "num_images": res["num_images"]}
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(row, open(OUT / "raw.json", "w"), indent=1)
    print(json.dumps(row), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prepare")
    sub.add_parser("raw")
    j = sub.add_parser("jpeg")
    j.add_argument("--q", type=int, nargs="+")
    v = sub.add_parser("video")
    v.add_argument("--only", nargs="+")
    v.add_argument("--crf", type=int, nargs="+")
    sub.add_parser("codes")
    t = sub.add_parser("jpeg_tuned")
    t.add_argument("--q", type=int, nargs="+")
    sub.add_parser("analyse")
    a = ap.parse_args()
    {"prepare": cmd_prepare, "raw": cmd_raw, "jpeg": cmd_jpeg, "video": cmd_video, "codes": cmd_codes,
     "jpeg_tuned": cmd_jpeg_tuned, "analyse": cmd_analyse}[a.cmd](a)


if __name__ == "__main__":
    main()
