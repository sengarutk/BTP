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
  nvenc       h264_nvenc low latency (p1, no B-frames, constant quality), the hardware encoder of Jetson-class boards
  codes       the learned (uint8 + zstd) and entropy-coded split codes at k4, on the raw frames
Payload: mean bytes per frame (video: per-packet sizes from ffprobe; p95 also kept, since a frame must arrive by its
deadline). Encode time: single-thread wall time per frame on this laptop's CPU, for JPEG and the software video
encoders alike (the rule scales host times to each device's speed, as it does for every option); decode time likewise.
The video options assume an error-free stream (a lost frame would corrupt the frames that reference it); this favours
video and is stated.
usage: video_codecs.py prepare | jpeg | video | codes | analyse        -> experiments/results/video_codecs/
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


def evaluate(opt, name, hook=None, layer=None):
    """mAP of the decoded frames of option `opt` (cached per-image stats under the given name)."""
    from ultralytics import YOLO
    from evaluation.detection_eval import run_validation
    yolo = YOLO(str(REPO / "weights" / "yolov8s_visdrone.pt"))
    h = yolo.model.model[layer].register_forward_hook(hook) if hook else None
    try:
        return run_validation(yolo, str(yaml_for(opt)), "cuda", name=name, cache=hook is None)
    finally:
        if h:
            h.remove()


def timed(fn, reps=1):
    t0 = time.perf_counter()
    for _ in range(reps):
        r = fn()
    return r, (time.perf_counter() - t0) / reps * 1e3


def cmd_jpeg(a):
    cv2.setNumThreads(1)
    for q in a.q or JPEG_Q:
        opt = f"jpeg_q{q}"
        f_out = OUT / f"{opt}.json"
        if f_out.exists():
            continue
        d = WORK / opt / "images"
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
                bs = tmp / f"{seq}.bit"
                t0 = time.perf_counter()
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-threads", "1", "-framerate", "30", "-start_number", "1",
                                "-i", str(SRC / seq / "%07d.jpg"), *encode_args(codec, preset, crf), str(bs)], check=True)
                enc_s += time.perf_counter() - t0
                s = ffprobe_sizes(bs)
                assert len(s) == nf, (seq, len(s), nf)
                t0 = time.perf_counter()
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-threads", "1", "-i", str(bs), "-start_number", "1",
                                "-compression_level", "1", str(tmp / f"{seq}_%07d.png")], check=True)
                dec_s += time.perf_counter() - t0
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
                   "timing_note": "single-thread wall time incl. ffmpeg start-up and PNG I/O for decode (upper bound)",
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
    for kind, tag in [("learned", t) for t in tags] + [("entropy", t) for t in ecs]:
        f_out = OUT / f"code_{tag}.json"
        if f_out.exists():
            continue
        sizes = []
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
    a = ap.parse_args()
    {"prepare": cmd_prepare, "raw": cmd_raw, "jpeg": cmd_jpeg, "video": cmd_video, "codes": cmd_codes}[a.cmd](a)


if __name__ == "__main__":
    main()
