#!/usr/bin/env python3
"""FCM-style feature coding with HEVC as a split option (paper 1, roadmap L5, 12 Nov 2026).

MPEG's Feature Coding for Machines codes the tensor at the split with a standard video codec (VVC in its test model).
Here HEVC (x265 via ffmpeg) is used, the generation before VVC (building an open VVC encoder needs external code).
On the 548 VisDrone-DET val frames with the VisDrone YOLOv8s, mAP@[.5:.95], batch 1:
  posthoc  the k4 cut (128 channels, the only tensor that crosses there) quantised per image (min-max) to 10 bits,
           tiled into one monochrome picture (16 x 8 channels), x265 intra (keyint 1, preset medium, fixed QP),
           decoded, untiled, dequantised; the detector continues. FCM without its learned reduction.
  learned  the frozen learned codes (k4, 4-32 channels, uint8 at 40 x 40) tiled the same way and coded 8-bit with
           x265 intra instead of zstd; the decoder of the bottleneck continues. FCTM's structure: a learned reduction
           followed by a standard codec.
Payload: the HEVC bitstream + 8 bytes (min and max, or the bottleneck's lo and scale). Timing: x265 single-threaded
(pools=1, frame-threads=1) on this CPU, the mean over 40 of the run's own pictures coded in one call (no process start
per frame), and the decode likewise; host times are scaled to each device by break_even_rule like every host time.
usage: feature_hevc.py eval [--kind posthoc|learned] [--qp Q ...] | analyse -> experiments/results/feature_hevc/
"""
import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
OUT = REPO / "experiments" / "results" / "feature_hevc"
QP_POST = (22, 27, 32, 37, 42, 47)
QP_LEARNED = (17, 22, 27, 32, 37)
CODES = ("k4_c4_w128_d2", "k4_c8_w128_d2", "k4_c16_w128_d2", "k4_c32_w128_d2")
X265 = "keyint=1:log-level=error"


def grid(c):
    cols = 2 ** math.ceil(math.log2(math.sqrt(c)))
    return cols, math.ceil(c / cols)


def tile(a):
    """(C, h, w) array -> (rows*h, cols*w) mosaic, padded to multiples of 8 by edge replication."""
    c, h, w = a.shape
    cols, rows = grid(c)
    m = np.zeros((rows * h, cols * w), a.dtype)
    for i in range(c):
        r, k = divmod(i, cols)
        m[r * h:(r + 1) * h, k * w:(k + 1) * w] = a[i]
    H, W = -(-m.shape[0] // 8) * 8, -(-m.shape[1] // 8) * 8
    return np.pad(m, ((0, H - m.shape[0]), (0, W - m.shape[1])), mode="edge"), (c, h, w)


def untile(m, shape):
    c, h, w = shape
    cols, _ = grid(c)
    return np.stack([m[(i // cols) * h:(i // cols + 1) * h, (i % cols) * w:(i % cols + 1) * w] for i in range(c)])


def hevc(m, qp, bits, single_thread=False):
    fmt, dt = ("gray10le", "<u2") if bits == 10 else ("gray", "u1")
    par = X265 + f":qp={qp}" + (":pools=1:frame-threads=1" if single_thread else "")
    H, W = m.shape
    enc = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", fmt, "-s",
                          f"{W}x{H}", "-i", "-", "-c:v", "libx265", "-preset", "medium", "-x265-params", par,
                          "-f", "hevc", "-"], input=m.astype(dt).tobytes(), capture_output=True, check=True).stdout
    dec = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "hevc", "-i", "-", "-f", "rawvideo",
                          "-pix_fmt", fmt, "-"], input=enc, capture_output=True, check=True).stdout
    return enc, np.frombuffer(dec, dtype=dt).reshape(H, W).copy()


def time_hevc(mosaics, qp, bits):
    """Single-thread encode and decode time per picture: the pictures coded as one intra-only sequence."""
    fmt, dt = ("gray10le", "<u2") if bits == 10 else ("gray", "u1")
    H, W = mosaics[0].shape
    same = [m for m in mosaics if m.shape == (H, W)]
    raw = b"".join(m.astype(dt).tobytes() for m in same)
    par = X265 + f":qp={qp}:pools=1:frame-threads=1"
    t0 = time.perf_counter()
    enc = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", fmt, "-s",
                          f"{W}x{H}", "-i", "-", "-c:v", "libx265", "-preset", "medium", "-x265-params", par,
                          "-f", "hevc", "-"], input=raw, capture_output=True, check=True).stdout
    te = (time.perf_counter() - t0) * 1e3 / len(same)
    t0 = time.perf_counter()
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-threads", "1", "-f", "hevc", "-i", "-", "-f",
                    "rawvideo", "-pix_fmt", fmt, "-"], input=enc, capture_output=True, check=True)
    td = (time.perf_counter() - t0) * 1e3 / len(same)
    return te, td, len(same)


def cmd_eval(a):
    from ultralytics import YOLO
    from evaluation import learned_bottleneck as L
    from evaluation.detection_eval import run_validation
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = ([("posthoc", None, q) for q in (a.qp or QP_POST)] if a.kind in (None, "posthoc") else []) + \
           ([("learned", c, q) for c in CODES for q in (a.qp or QP_LEARNED)] if a.kind in (None, "learned") else [])
    for kind, code, qp in jobs:
        tag = f"posthoc_k4_qp{qp}" if kind == "posthoc" else f"learned_{code}_qp{qp}"
        f_out = OUT / f"{tag}.json"
        if f_out.exists():
            try:
                json.load(open(f_out))
                continue
            except json.JSONDecodeError:          # left empty by a restart mid-write: redo it
                pass
        yolo = YOLO(str(REPO / "weights" / "yolov8s_visdrone.pt"))
        sizes, mosaics = [], []
        if kind == "posthoc":
            def hook(m, i, out):
                rec = []
                for b in range(out.shape[0]):
                    x = out[b].float().cpu().numpy()
                    lo, hi = float(x.min()), float(x.max())
                    sc = (hi - lo) / 1023.0 if hi > lo else 1.0
                    q = np.round((x - lo) / sc).clip(0, 1023).astype(np.uint16)
                    mos, shp = tile(q)
                    enc, dec = hevc(mos, qp, 10)
                    sizes.append(len(enc) + 8)
                    if len(mosaics) < 41:
                        mosaics.append(mos)
                    r = untile(dec, shp).astype(np.float32) * sc + lo
                    rec.append(torch.from_numpy(r).to(out.device, out.dtype))
                return torch.stack(rec)
            layer = 4
        else:
            bn, ck = L.load_bottleneck(L.CKPT / f"{code}.pt", "cuda")
            layer = ck["cut"]

            def hook(m, i, out):
                rec = []
                with torch.no_grad():
                    for b in range(out.shape[0]):
                        z = bn.enc(out[b:b + 1].float())
                        _, q, lo, sc = bn.quantize(z)
                        mos, shp = tile(q[0].cpu().numpy())
                        enc, dec = hevc(mos, qp, 8)
                        sizes.append(len(enc) + 8)
                        if len(mosaics) < 41:
                            mosaics.append(mos)
                        qh = torch.from_numpy(untile(dec, shp).astype(np.float32))[None].to(z.device)
                        rec.append(bn.dec(qh * sc + lo).to(out.dtype))
                return torch.cat(rec)
        h = yolo.model.model[layer].register_forward_hook(hook)
        try:
            res = run_validation(yolo, "visdrone_val", "cuda", name=f"fh_{tag}", cache=False)
        finally:
            h.remove()
        sizes = L.drop_warmup(sizes, res["num_images"])
        te, td, nt = time_hevc(mosaics[1:], qp, 10 if kind == "posthoc" else 8)   # mosaics[0]: the warm-up pass
        row = {"option": tag, "kind": kind, "code": code, "qp": qp, "n": len(sizes),
               "payload_bytes_mean": float(np.mean(sizes)), "payload_bytes_p95": float(np.percentile(sizes, 95)),
               "picture": list(mosaics[1].shape), "encode_ms_single_thread": te, "decode_ms_single_thread": td,
               "timed_pictures": nt, "map50_95": res["map50_95"], "map50": res["map50"],
               "base_map50_95": None, "num_images": res["num_images"]}
        json.dump(row, open(f_out, "w"), indent=1)
        print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()}), flush=True)
        del yolo
        torch.cuda.empty_cache()


def cmd_analyse(a):
    """B_be of the HEVC-coded options against the JPEG grid (break_even_rule.analyse), next to the zstd codes."""
    from dataclasses import replace
    from evaluation import break_even_rule as b
    from evaluation.learned_bottleneck_system import family, measured_configs
    from simulation.system_model import load_offload_configs
    from evaluation.learned_bottleneck_system import VD
    rows = {f.stem: json.load(open(f)) for f in OUT.glob("*_qp*.json")}
    base = measured_configs()
    jpeg = b.jpeg_grid(base)
    codes = {c.name: c for c in b.learned_and_joint()}
    ph = load_offload_configs(VD)["k4_int8_zstd"]
    ph = next((c for c in base if c.name == "k4_int8_zstd"), ph)
    full = next(c for c in base if family(c) == "onboard")
    opts = []
    for n, r in sorted(rows.items()):
        if r["kind"] == "posthoc":
            proto = ph
        else:
            proto = codes[f"learned_{r['code']}"]
        opts.append(replace(proto, name=f"hevc_{n}", dtype=f"hevc_{n}", payload_bytes=r["payload_bytes_mean"],
                            host_edge_proc_ms=r["encode_ms_single_thread"],
                            cloud_ms=proto.cloud_ms + r["decode_ms_single_thread"], map50_95=r["map50_95"],
                            map50=r["map50"], delta_map50_95=r["map50_95"] - full.map50_95))
    others = [c for c in base if family(c) != "image"] + list(codes.values()) + opts
    ar, viol, checked, wins = b.analyse(jpeg, others)
    by = {(x["device"], x["code"]): x for x in ar}
    out = {"method": cmd_analyse.__doc__, "options": [{"name": o.name, "payload_bytes": o.payload_bytes,
           "map50_95": o.map50_95, "host_edge_proc_ms": o.host_edge_proc_ms} for o in opts],
           "rows": ar, "violations": viol, "wins_checked": checked, "wins_total": wins}
    m = {"FhWins": str(wins), "FhExc": str(len(viol))}
    hevc_rows = [x for x in ar if x["code"].startswith("hevc_")]
    m["FhWinsHevc"] = str(sum(len(x["wins_at_mbps"]) for x in hevc_rows))
    post = sorted((o for o in opts if "posthoc" in o.name), key=lambda o: -o.map50_95)
    if post:
        m["FhPostKibMin"] = f"{min(o.payload_bytes for o in post) / 1024:.1f}"
        m["FhPostKibMax"] = f"{max(o.payload_bytes for o in post) / 1024:.0f}"
        m["FhPostMapMax"] = f"{post[0].map50_95:.3f}"
        m["FhPostMapMin"] = f"{post[-1].map50_95:.3f}"
        m["FhPostEncMs"] = f"{np.median([o.host_edge_proc_ms for o in post]):.0f}"
        for dn, dev in (("Pi", "Pi 5 (throttled)"), ("Fast", "Jetson Orin Nano")):
            w = [max(by[(dev, o.name)]["wins_at_mbps"]) for o in post if by[(dev, o.name)]["wins_at_mbps"]]
            m[f"FhPost{dn}WinMax"] = f"{max(w):.2f}" if w else "--"
    # learned codes: bytes saved by HEVC over zstd at equal or higher accuracy, and B_be against the zstd code
    sv, same_be = [], 0
    for c in CODES:
        z = codes[f"learned_{c}"]
        for o in opts:
            if f"learned_{c}_" in o.name and o.map50_95 >= z.map50_95 - 1e-9:
                sv.append(1 - o.payload_bytes / z.payload_bytes)
    m["FhLearnedSaveMax"] = f"{100 * max(sv):.0f}" if sv else "--"
    m["FhLearnedSaveN"] = str(len(sv))
    out["learned_saving_at_equal_accuracy"] = sv
    json.dump(out, open(OUT / "analysis.json", "w"), indent=1)
    (OUT / "fh_metrics.tex").write_text("% Generated by evaluation/feature_hevc.py analyse -- do not edit.\n"
                                        + "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in m.items()))
    print(f"wins {wins} (HEVC options {m['FhWinsHevc']}), exceptions {len(viol)}")
    for k, v in m.items():
        print(k, v)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("eval")
    e.add_argument("--kind", choices=["posthoc", "learned"])
    e.add_argument("--qp", type=int, nargs="+")
    sub.add_parser("analyse")
    a = ap.parse_args()
    {"eval": cmd_eval, "analyse": cmd_analyse}[a.cmd](a)


if __name__ == "__main__":
    main()
