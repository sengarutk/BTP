#!/usr/bin/env python3
"""A learned feature-compression baseline for the split result (30 Oct 2026): does a trained bottleneck at a cut of
the frozen detector beat sending the image? (paper Discussion; brief Part 20, section 1 "Limit")

Design (BottleFit / supervised compression, Matsubara et al. 2022; here with the detector frozen):
  cut k        layer k's output is the only tensor that crosses (k = 1, 2, 4 for YOLOv8s), so the bottleneck replaces
               exactly the split payload of the toolkit
  encoder E    conv3x3 stride 2 (C_k -> 64) + BN + SiLU, conv3x3 (64 -> C_b): C_b channels at half the resolution
  quantizer    per-tensor min-max to uint8 (8 bytes of header: min and scale as float32); straight-through in training
  decoder D    conv3x3 (C_b -> 64) + BN + SiLU, x2 nearest upsampling, conv3x3 (64 -> 64) + BN + SiLU, conv1x1 -> C_k
  training     head distillation: the frozen detector's own neck outputs (layers 15, 18, 21, the detection head's
               inputs) and layer k's output, MSE normalised by each teacher tensor's variance; no labels. Images:
               VisDrone2019-DET train (letterboxed to 640, horizontal flips), the last 471 held out for monitoring;
               DET val (548 images) is never seen in training.
  rate         zstd level 1 of the uint8 code (the toolkit's coder, protocol/packet.py) + the 8-byte header, measured
               per image on DET val
  accuracy     mAP@[.5:.95] on VisDrone2019-DET val with the VisDrone YOLOv8s, batch 1 (evaluation/detection_eval.py),
               paired bootstrap against the unsplit model
The detector's weights never change, so the comparison with JPEG (benchmark_codecs.py, same images, same detector) and
with the post-hoc INT8 splits (evaluate_mAP.py) is like for like.

usage: learned_bottleneck.py train --cut 4 --channels 8 [--epochs 12] [--batch 8]
       learned_bottleneck.py eval  --cut 4 --channels 8          -> experiments/results/learned_bottleneck/
       learned_bottleneck.py summary                             -> experiments/results/learned_bottleneck/summary.json
"""
import argparse
import glob
import json
import math
import random
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

REPO = Path(__file__).resolve().parent.parent
WEIGHTS = REPO / "weights" / "yolov8s_visdrone.pt"
TRAIN_DIR = REPO / "datasets" / "visdrone" / "VisDrone2019-DET-train" / "images"
OUT = REPO / "experiments" / "results" / "learned_bottleneck"
CKPT = REPO / "weights" / "learned_bottleneck"
NECK = (15, 18, 21)
N_HOLD = 471


def conv(ci, co, k=3, s=1):
    return nn.Sequential(nn.Conv2d(ci, co, k, s, k // 2, bias=False), nn.BatchNorm2d(co), nn.SiLU())


class Bottleneck(nn.Module):
    """stride 2 (default) codes at half the cut's resolution, stride 1 at full; dec_layers extra 3x3 convs in the
    decoder. The defaults (width 64, stride 2, 1 extra layer) are the first configuration (k4_c8)."""

    def __init__(self, c_in, c_b, width=64, stride=2, dec_layers=1):
        super().__init__()
        self.enc = nn.Sequential(conv(c_in, width, 3, stride), nn.Conv2d(width, c_b, 3, 1, 1))
        up = [nn.Upsample(scale_factor=2, mode="nearest")] if stride == 2 else []
        self.dec = nn.Sequential(conv(c_b, width), *up, *[conv(width, width) for _ in range(dec_layers)],
                                 nn.Conv2d(width, c_in, 1))

    @staticmethod
    def quantize(z):
        """Per-tensor min-max uint8 (per image); straight-through gradient. Returns (dequantized z, uint8 codes)."""
        lo = z.amin(dim=(1, 2, 3), keepdim=True)
        sc = (z.amax(dim=(1, 2, 3), keepdim=True) - lo).clamp_min(1e-8) / 255.0
        q = torch.round((z - lo) / sc).clamp(0, 255)
        zq = q * sc + lo
        return z + (zq - z).detach(), q.to(torch.uint8), lo, sc

    def forward(self, x):
        zq, q, lo, sc = self.quantize(self.enc(x))
        return self.dec(zq), q


def load_detector(device):
    from ultralytics import YOLO
    det = YOLO(str(WEIGHTS)).model.to(device).eval()
    for p in det.parameters():
        p.requires_grad_(False)
    return det


def run_detector(det, x, cut, bottleneck=None):
    """The detector's forward pass (BaseModel._predict_once without the head's post-processing need), with layer cut's
    output replaced by the bottleneck's reconstruction; returns {layer: output} for the cut and the neck layers."""
    y, keep = [], {}
    for i, m in enumerate(det.model):
        if m.f != -1:
            x = y[m.f] if isinstance(m.f, int) else [x if j == -1 else y[j] for j in m.f]
        if i == len(det.model) - 1:              # the Detect head is not needed for distillation
            break
        x = m(x)
        if i == cut:
            keep["cut"] = x
            if bottleneck is not None:
                x, _ = bottleneck(x)
                keep["cut_rec"] = x
        y.append(x if m.i in det.save else None)
        if i in NECK:
            keep[i] = x
    return keep


def letterbox(img, size=640):
    h, w = img.shape[:2]
    r = min(size / h, size / w)
    nh, nw = round(h * r), round(w * r)
    img = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    out = np.full((size, size, 3), 114, np.uint8)
    top, left = (size - nh) // 2, (size - nw) // 2
    out[top:top + nh, left:left + nw] = img
    return out


class Images(torch.utils.data.Dataset):
    def __init__(self, files, flip):
        self.files, self.flip = files, flip

    def __len__(self):
        return len(self.files)

    def __getitem__(self, i):
        img = letterbox(cv2.imread(self.files[i]))[:, :, ::-1]
        if self.flip and random.random() < 0.5:
            img = img[:, ::-1]
        return torch.from_numpy(np.ascontiguousarray(img.transpose(2, 0, 1))).float() / 255.0


def files_split():
    fs = sorted(glob.glob(str(TRAIN_DIR / "*.jpg")))
    return fs[:-N_HOLD], fs[-N_HOLD:]


ARCH = ("width", "stride", "dec_layers")
ARCH_DEFAULT = {"width": 64, "stride": 2, "dec_layers": 1}


def drop_warmup(samples, n_images):
    """Ultralytics' validator runs one warm-up pass on a dummy 640 x 640 input before the images; hooks see it too.
    Drop it so averages cover the real images only (checked: 549 calls for 548 images, the first at 80 x 80 at k4)."""
    assert len(samples) in (n_images, n_images + 1), (len(samples), n_images)
    return samples[len(samples) - n_images:]


def tag(a):
    t = f"k{a.cut}_c{a.channels}"
    for k, short in (("width", "w"), ("stride", "s"), ("dec_layers", "d")):
        if getattr(a, k) != ARCH_DEFAULT[k]:
            t += f"_{short}{getattr(a, k)}"
    return t


def load_bottleneck(path, device):
    ck = torch.load(path, map_location=device)
    bn = Bottleneck(ck["c_in"], ck["channels"], **{k: ck.get(k, ARCH_DEFAULT[k]) for k in ARCH}).to(device).eval()
    bn.load_state_dict(ck["state"])
    return bn, ck


def distill_loss(t, s):
    return sum(F.mse_loss(s[k].float(), t[k].float()) / t[k].float().var().clamp_min(1e-6) for k in t)


def cmd_train(a):
    torch.manual_seed(a.seed)
    random.seed(a.seed)
    np.random.seed(a.seed)
    dev = torch.device("cuda")
    det = load_detector(dev)
    c_in = run_detector(det, torch.zeros(1, 3, 64, 64, device=dev), a.cut)["cut"].shape[1]
    bn = Bottleneck(c_in, a.channels, a.width, a.stride, a.dec_layers).to(dev)
    tr, ho = files_split()
    dl = torch.utils.data.DataLoader(Images(tr, True), batch_size=a.batch, shuffle=True, num_workers=a.workers,
                                     drop_last=True, persistent_workers=True)
    dh = torch.utils.data.DataLoader(Images(ho, False), batch_size=a.batch, shuffle=False, num_workers=a.workers)
    opt = torch.optim.AdamW(bn.parameters(), lr=a.lr, weight_decay=1e-4)
    steps = a.epochs * len(dl)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=steps, pct_start=0.05)
    scaler = torch.amp.GradScaler()
    CKPT.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    log = {"cut": a.cut, "channels": a.channels, "c_in": c_in, **{k: getattr(a, k) for k in ARCH}, "epochs": a.epochs, "batch": a.batch, "lr": a.lr,
           "seed": a.seed, "n_train": len(tr), "n_holdout": len(ho), "epochs_log": []}
    t0 = time.time()
    for ep in range(a.epochs):
        bn.train()
        tot, n = 0.0, 0
        for x in dl:
            x = x.to(dev, non_blocking=True)
            with torch.autocast("cuda", dtype=torch.float16):
                with torch.no_grad():
                    t = run_detector(det, x, a.cut)
                s = run_detector(det, x, a.cut, bn)
                loss = distill_loss({k: t[k] for k in NECK}, {k: s[k] for k in NECK}) \
                    + a.w_cut * F.mse_loss(s["cut_rec"].float(), t["cut"].float()) / t["cut"].float().var().clamp_min(1e-6)
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            sched.step()
            tot, n = tot + loss.item(), n + 1
        bn.eval()
        hl, hn = 0.0, 0
        with torch.no_grad(), torch.autocast("cuda", dtype=torch.float16):
            for x in dh:
                x = x.to(dev)
                t = run_detector(det, x, a.cut)
                s = run_detector(det, x, a.cut, bn)
                hl += float(distill_loss({k: t[k] for k in NECK}, {k: s[k] for k in NECK})) * len(x)
                hn += len(x)
        e = {"epoch": ep + 1, "train_loss": tot / n, "holdout_neck_loss": hl / hn, "minutes": (time.time() - t0) / 60}
        log["epochs_log"].append(e)
        print(json.dumps({k: round(v, 5) if isinstance(v, float) else v for k, v in e.items()}), flush=True)
        torch.save({"state": bn.state_dict(), "c_in": c_in, "channels": a.channels, "cut": a.cut,
                    **{k: getattr(a, k) for k in ARCH}}, CKPT / f"{tag(a)}.pt")
    json.dump(log, open(OUT / f"train_{tag(a)}.json", "w"), indent=1)


def cmd_eval(a):
    import zstandard
    from ultralytics import YOLO
    from evaluation.detection_eval import paired_bootstrap, run_validation, summary_row
    dev = "cuda"
    bn, ck = load_bottleneck(CKPT / f"{tag(a)}.pt", dev)
    yolo = YOLO(str(WEIGHTS))
    cz = zstandard.ZstdCompressor(level=1)
    log = {"bytes": [], "values": [], "enc_ms": []}

    def hook(module, inp, out):
        with torch.no_grad():
            rec = []
            for b in range(out.shape[0]):           # batch 1 in validation: per image, as on the drone
                t0 = time.perf_counter()
                r, q = bn(out[b:b + 1].float())
                code = q.cpu().numpy().tobytes()
                log["bytes"].append(len(cz.compress(code)) + 8)
                log["enc_ms"].append((time.perf_counter() - t0) * 1e3)
                log["values"].append(q.numel())
                rec.append(r.to(out.dtype))
            return torch.cat(rec)

    base = run_validation(yolo, "visdrone_val", dev, name="lb_base_yolov8s_visdrone_full_fp32")
    h = yolo.model.model[a.cut].register_forward_hook(hook)
    try:
        res = run_validation(yolo, "visdrone_val", dev, name=f"lb_yolov8s_visdrone_{tag(a)}", cache=False)
    finally:
        h.remove()
    for k in log:
        log[k] = drop_warmup(log[k], res["num_images"])
    pb = paired_bootstrap(base, res, n_boot=a.n_boot)
    row = {"config": tag(a), "cut": a.cut, "channels": a.channels, **{k: ck.get(k, ARCH_DEFAULT[k]) for k in ARCH},
           "n": len(log["bytes"]), "code_values": int(np.median(log["values"])),
           "payload_bytes_mean": float(np.mean(log["bytes"])), "payload_bytes_p95": float(np.percentile(log["bytes"], 95)),
           "gpu_codec_ms_median": float(np.median(log["enc_ms"])), "base_map50_95": base["map50_95"],
           **{k: v for k, v in summary_row(res).items() if k != "name"}, **{f"boot_{k}": v for k, v in pb.items()}}
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(row, open(OUT / f"eval_{tag(a)}.json", "w"), indent=1)
    print(json.dumps({k: (round(v, 5) if isinstance(v, float) else v) for k, v in row.items()}))


def cmd_jpeg(a):
    """JPEG at low qualities on the same images with the same detector, for the low-rate end of the curve (the
    VisDrone codec table, visdrone_ft_split/codec_offload.csv, starts at q50). Uses benchmark_codecs' hook; cache
    names are unique to this script (the shared cache is keyed by name only). q50 is re-measured as a check."""
    from ultralytics import YOLO
    from evaluation.benchmark_codecs import make_codec_hook
    from evaluation.detection_eval import paired_bootstrap, run_validation
    yolo = YOLO(str(WEIGHTS))
    base = run_validation(yolo, "visdrone_val", "cuda", name="lb_base_yolov8s_visdrone_full_fp32")
    OUT.mkdir(parents=True, exist_ok=True)
    for q in a.q:
        log = {"bytes": [], "pixels": [], "enc_ms": []}
        res = run_validation(yolo, "visdrone_val", "cuda", name=f"lb_jpeg_q{q}_yolov8s_visdrone",
                             pre_forward_hook=make_codec_hook("JPEG", q, log), cache=False)
        pb = paired_bootstrap(base, res, n_boot=a.n_boot)
        log["bytes"] = drop_warmup(log["bytes"], res["num_images"])
        row = {"config": f"jpeg_q{q}", "q": q, "payload_bytes_mean": float(np.mean(log["bytes"])), "n": len(log["bytes"]),
               "map50": res["map50"], "map50_95": res["map50_95"], "base_map50_95": base["map50_95"],
               **{f"boot_{k}": v for k, v in pb.items()}}
        out = Path(a.out) if a.out else OUT
        out.mkdir(parents=True, exist_ok=True)
        json.dump(row, open(out / f"jpeg_q{q}.json", "w"), indent=1)
        print(json.dumps({k: (round(v, 5) if isinstance(v, float) else v) for k, v in row.items()}), flush=True)


def cmd_posthoc(a):
    """Wire size of the post-hoc INT8 + zstd splits (the toolkit's quantizer and packet format, benchmark_split_pareto.py)
    on the same VisDrone DET val frames as the learned codes; the detector output is not changed (their accuracy is
    lossless, 19.6 R4), so only the bytes are measured."""
    from ultralytics import YOLO
    from evaluation.detection_eval import run_validation
    from protocol.packet import AegisPacketProtocol
    from quantization.quantizer import FeatureMapQuantizer
    yolo = YOLO(str(WEIGHTS))
    OUT.mkdir(parents=True, exist_ok=True)
    for cut in a.cuts:
        sizes = []

        def hook(module, inp, out, cut=cut):
            for b in range(out.shape[0]):
                q, sc = FeatureMapQuantizer.quantize(out[b:b + 1].float(), dtype="int8_zstd")
                sizes.append(len(AegisPacketProtocol.serialize(len(sizes), 0, cut, "int8_zstd", q, sc)))
            return out

        h = yolo.model.model[cut].register_forward_hook(hook)
        try:
            res = run_validation(yolo, "visdrone_val", "cuda", name=f"lb_posthoc_k{cut}_bytes", cache=False)
        finally:
            h.remove()
        sizes = drop_warmup(sizes, res["num_images"])
        row = {"config": f"k{cut}_int8_zstd", "cut": cut, "payload_bytes_mean": float(np.mean(sizes)),
               "payload_bytes_p95": float(np.percentile(sizes, 95)), "n": len(sizes),
               "map50_95_unchanged_check": res["map50_95"]}
        json.dump(row, open(OUT / f"posthoc_k{cut}_int8_zstd.json", "w"), indent=1)
        print(json.dumps(row), flush=True)


def cmd_figure(a):
    """Rate-accuracy on VisDrone DET val, every payload measured on the same frames: JPEG q10-q95, the learned codes,
    the post-hoc INT8 + zstd splits -> paper/figures/learned_bottleneck.pdf and docs/figs/learned_bottleneck.svg (the
    style of evaluation/make_figures.py)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": "serif", "font.size": 8, "axes.labelsize": 8, "legend.fontsize": 6.5, "xtick.labelsize": 7,
        "ytick.labelsize": 7, "axes.grid": True, "grid.alpha": 0.3, "grid.linewidth": 0.5, "lines.linewidth": 1.2,
        "lines.markersize": 3.5, "savefig.bbox": "tight", "savefig.pad_inches": 0.02, "pdf.fonttype": 42,
        "axes.spines.top": False, "axes.spines.right": False})
    jp = sorted((json.load(open(f)) for f in OUT.glob("jpeg_q*.json")), key=lambda r: r["payload_bytes_mean"])
    lb = [r for r in (json.load(open(f)) for f in OUT.glob("eval_*.json"))
          if r.get("width") == 128 and r.get("dec_layers") == 2]     # the family (not the width-64 pilot)
    ph = [json.load(open(f)) for f in OUT.glob("posthoc_k*_int8_zstd.json")]
    base = 100 * jp[0]["base_map50_95"]
    kib = lambda r: r["payload_bytes_mean"] / 1024  # noqa: E731   payloads in KiB (1 KiB = 1024 bytes), as in the paper
    pts = lambda r: 100 * r["map50_95"]  # noqa: E731              mAP in points, as in the paper
    # Label offsets (points), one per marker, chosen so no two labels or markers overlap at column width.
    jpeg_off = {10: (4, -4), 20: (-14, 1), 35: (4, -6), 50: (4, -6), 75: (-2, -10), 90: (-4, -10), 95: (5, -1)}
    lb_off = {(4, 4, 2): (-9, -1), (4, 8, 2): (-9, -1), (4, 16, 2): (-11, -1), (4, 32, 2): (-2, -9),
              (4, 8, 1): (-13, 1), (4, 16, 1): (-15, 2), (4, 64, 2): (5, -3), (4, 32, 1): (4, -9),
              (2, 8, 2): (5, -2), (2, 16, 2): (-2, 4)}
    fig, ax = plt.subplots(figsize=(3.45, 2.5))
    ax.plot([kib(r) for r in jp], [pts(r) for r in jp], "o-", color="#D55E00", label="JPEG (q10-q95)")
    for r in jp:
        ax.annotate(f"q{r['q']}", (kib(r), pts(r)), textcoords="offset points", xytext=jpeg_off.get(r["q"], (4, -6)),
                    fontsize=5.5, color="#D55E00")
    for cut, mk, col in ((4, "s", "#0072B2"), (2, "^", "#009E73")):
        rs = sorted((r for r in lb if r["cut"] == cut), key=lambda r: r["payload_bytes_mean"])
        if rs:
            ax.plot([kib(r) for r in rs], [pts(r) for r in rs], mk, color=col, label=f"learned bottleneck at k{cut}")
            for r in rs:                         # labels: channels (f = full resolution)
                off = lb_off.get((cut, r["channels"], r.get("stride", 2)), (4, -6))
                ax.annotate(f"{r['channels']}{'f' if r.get('stride') == 1 else ''}", (kib(r), pts(r)),
                            textcoords="offset points", xytext=off, fontsize=5.5, color=col)
    ax.plot([kib(r) for r in ph], [base for _ in ph], "D", color="#56B4E9", label="post-hoc INT8+zstd (k2, k4)")
    ax.axhline(base, color="#000000", lw=0.6, ls="--", label="unsplit model")
    ax.set_xscale("log")
    ax.set_ylim(min(pts(r) for r in jp + lb) - 1.5, base + 0.8)
    ax.set_xlim(min(kib(r) for r in jp + lb) / 1.6, max(kib(r) for r in ph) * 1.4)
    ax.set_xlabel("Payload per frame (KiB, VisDrone DET val)")
    ax.set_ylabel("mAP@[.5:.95] (points)")
    ax.legend(loc="lower right", frameon=False)
    (REPO / "paper" / "figures").mkdir(parents=True, exist_ok=True)
    (REPO / "docs" / "figs").mkdir(parents=True, exist_ok=True)
    fig.savefig(REPO / "paper" / "figures" / "learned_bottleneck.pdf")
    fig.savefig(REPO / "docs" / "figs" / "learned_bottleneck.svg")
    plt.close(fig)
    print("paper/figures/learned_bottleneck.pdf, docs/figs/learned_bottleneck.svg")


def cmd_summary(a):
    """Every payload measured on the same VisDrone DET val frames. For each learned code: the JPEG accuracy at its size
    and the JPEG size of its accuracy, interpolated on the measured JPEG curve (linear in log size; none outside the
    measured range), and the training curve's last held-out loss."""
    rows = sorted((json.load(open(f)) for f in OUT.glob("eval_*.json")), key=lambda r: r["payload_bytes_mean"])
    jp = sorted((json.load(open(f)) for f in OUT.glob("jpeg_q*.json")), key=lambda r: r["payload_bytes_mean"])
    ph = [json.load(open(f)) for f in sorted(OUT.glob("posthoc_k*_int8_zstd.json"))]
    lx = np.log([r["payload_bytes_mean"] for r in jp])
    ya = np.array([r["map50_95"] for r in jp])
    assert np.all(np.diff(ya) > 0), "JPEG accuracy must rise with quality for the inverse interpolation"
    for r in rows:
        x = np.log(r["payload_bytes_mean"])
        r["jpeg_map_at_same_bytes"] = float(np.interp(x, lx, ya)) if lx[0] <= x <= lx[-1] else None
        r["jpeg_bytes_for_same_map"] = float(np.exp(np.interp(r["map50_95"], ya, lx))) \
            if ya[0] <= r["map50_95"] <= ya[-1] else None
        r["bytes_saving_vs_jpeg_pct"] = None if r["jpeg_bytes_for_same_map"] is None else \
            100 * (1 - r["payload_bytes_mean"] / r["jpeg_bytes_for_same_map"])
        tr = OUT / f"train_{r['config']}.json"
        r["holdout_neck_loss_last"] = json.load(open(tr))["epochs_log"][-1]["holdout_neck_loss"] if tr.exists() else None
    out = {"learned": rows, "jpeg": jp, "posthoc_splits": ph}
    json.dump(out, open(OUT / "summary.json", "w"), indent=1)
    for r in rows:
        jm, jb = r["jpeg_map_at_same_bytes"], r["jpeg_bytes_for_same_map"]
        print(f"{r['config']:18s} {r['payload_bytes_mean'] / 1e3:7.1f} kB  mAP {r['map50_95']:.4f}  JPEG at same bytes "
              f"{'—' if jm is None else f'{jm:.4f}'}  JPEG bytes for same mAP {'—' if jb is None else f'{jb / 1e3:.1f} kB'}")
    for r in jp + ph:
        print(f"{r['config']:18s} {r['payload_bytes_mean'] / 1e3:7.1f} kB  mAP "
              f"{r.get('map50_95', r.get('map50_95_unchanged_check')):.4f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("train", "eval"):
        p = sub.add_parser(name)
        p.add_argument("--cut", type=int, default=4, choices=[1, 2, 4])
        p.add_argument("--channels", type=int, default=8)
        p.add_argument("--width", type=int, default=64)
        p.add_argument("--stride", type=int, default=2, choices=[1, 2])
        p.add_argument("--dec-layers", type=int, default=1)
        if name == "train":
            p.add_argument("--epochs", type=int, default=12)
            p.add_argument("--batch", type=int, default=8)
            p.add_argument("--lr", type=float, default=2e-3)
            p.add_argument("--w-cut", type=float, default=0.1, help="weight of the reconstruction loss at the cut")
            p.add_argument("--workers", type=int, default=3)
            p.add_argument("--seed", type=int, default=0)
        else:
            p.add_argument("--n-boot", type=int, default=300)
    jp = sub.add_parser("jpeg")
    jp.add_argument("--q", type=int, nargs="+", default=[10, 20, 35, 50])
    jp.add_argument("--n-boot", type=int, default=300)
    jp.add_argument("--out", default=None, help="output directory (default: the results directory; the finer grid of "
                    "the break-even rule, 11 Nov 2026, goes to learned_bottleneck/jpeg_fine/ so the paper's files stay)")
    ph = sub.add_parser("posthoc")
    ph.add_argument("--cuts", type=int, nargs="+", default=[2, 4])
    sub.add_parser("figure")
    sub.add_parser("summary")
    a = ap.parse_args()
    {"train": cmd_train, "eval": cmd_eval, "jpeg": cmd_jpeg, "posthoc": cmd_posthoc, "figure": cmd_figure,
     "summary": cmd_summary}[a.cmd](a)


if __name__ == "__main__":
    main()
