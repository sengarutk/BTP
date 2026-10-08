#!/usr/bin/env python3
"""Per-device profile of YOLOv8s for multi-device split placement (Raspberry Pi 5, Jetson Orin Nano, laptop GPU).

Runs unchanged on every device, on real COCO val2017 frames letterboxed to 640x640, with the
Conv+BN-fused model (as deployed). Cut k means "layers 0..k ran upstream"; k = -1 is the camera
frame and k = 22 the Detect output. The live set of a cut is every tensor computed at or before k
that a layer after k still reads (one tensor at k4, three at k21).

Measured:
  layer_ms[i]          median time of layer i (synchronised per layer), so the time of any segment
                       (a, b] can be composed; segment_check[] times real segments end to end to
                       validate the composition
  full_ms              whole model, no per-layer synchronisation
  pre_ms / post_ms     letterbox + tensor conversion / NMS
  codec[k][mode]       encode and decode time and bytes of the live set at cut k, for
                         int8_zstd  symmetric INT8 per tensor (S = max|X|/127) + zstd level 1 (repo default)
                         fp16       half precision, raw bytes
                       encode includes the device->host copy, decode the host->device copy
  jpeg                 encode / decode time and bytes of the 640x640 frame at quality 90
  power                board power while idle and during back-to-back full-model inference,
                       from the board's own sensor (Jetson INA3221 VDD_IN; Pi PMIC rail sum, which
                       excludes 5 V conversion losses and USB; laptop nvidia-smi, GPU only)

Output: one JSON file (--out).
"""

import argparse
import glob
import json
import os
import platform
import re
import statistics
import subprocess
import threading
import time

import cv2
import numpy as np
import torch
import zstandard as zstd


def load_model(weights, device, half):
    from ultralytics import YOLO
    m = YOLO(weights).model.eval()
    m = m.fuse(verbose=False) if hasattr(m, "fuse") else m
    m = m.to(device)
    if half:
        m = m.half()
    for p in m.parameters():
        p.requires_grad_(False)
    return m


def sources(layer, i):
    f = layer.f if isinstance(layer.f, (list, tuple)) else [layer.f]
    return [s if s >= 0 else i + s for s in f]


def live_set(layers, k):
    if k < 0:
        return [-1]
    if k >= len(layers) - 1:
        return [len(layers) - 1]
    need = {k}
    for i in range(k + 1, len(layers)):
        need.update(s for s in sources(layers[i], i) if s <= k)
    return sorted(need)


def run_segment(layers, state, a, b, sync=None, times=None):
    """Runs layers a+1..b given the live tensors at cut a; returns the live tensors at cut b."""
    y = dict(state)
    x = y[a]
    for i in range(a + 1, b + 1):
        m = layers[i]
        f = m.f
        if f == -1:
            inp = x
        elif isinstance(f, int):
            inp = y[f]
        else:
            inp = [x if j == -1 else y[j] for j in f]
        if times is not None:
            sync()
            t0 = time.perf_counter()
        x = m(inp)
        if times is not None:
            sync()
            times[i].append((time.perf_counter() - t0) * 1e3)
        y[i] = x
    return {j: y[j] for j in live_set(layers, b)}


def run_segment_all(layers, x):
    """All layer outputs of one forward pass (for timing segments from any cut)."""
    y, out = {-1: x}, {}
    for i, m in enumerate(layers):
        f = m.f
        inp = x if f == -1 else (y[f] if isinstance(f, int) else [x if j == -1 else y[j] for j in f])
        x = m(inp)
        y[i] = out[i] = x
    return out


class PowerSampler(threading.Thread):
    def __init__(self, kind, period=0.05):
        super().__init__(daemon=True)
        self.kind, self.period, self.samples, self.on = kind, period, [], False
        self.stop_flag = False

    def read(self):
        if self.kind == "jetson":
            base = glob.glob("/sys/class/hwmon/hwmon*/")
            for b in base:
                if open(b + "name").read().strip() == "ina3221":
                    v = float(open(b + "in1_input").read()) / 1e3
                    i = float(open(b + "curr1_input").read()) / 1e3
                    return v * i
        if self.kind == "pi":
            out = subprocess.run(["vcgencmd", "pmic_read_adc"], capture_output=True, text=True).stdout
            cur, vol = {}, {}
            for line in out.splitlines():
                mm = re.match(r"\s*(\S+)_([AV]) (?:current|volt)\(\d+\)=([\d.]+)", line)
                if mm:
                    (cur if mm.group(2) == "A" else vol)[mm.group(1)] = float(mm.group(3))
            return sum(cur[r] * vol[r] for r in cur if r in vol)
        if self.kind == "laptop":
            out = subprocess.run(["nvidia-smi", "--query-gpu=power.draw", "--format=csv,noheader,nounits"],
                                 capture_output=True, text=True).stdout
            return float(out.split()[0])
        return float("nan")

    def run(self):
        while not self.stop_flag:
            if self.on:
                try:
                    self.samples.append(self.read())
                except Exception:
                    pass
            time.sleep(self.period)

    def measure(self, seconds=None, fn=None):
        self.samples = []
        self.on = True
        if fn is None:
            time.sleep(seconds)
        else:
            fn()
        self.on = False
        return float(np.mean(self.samples)) if self.samples else float("nan"), len(self.samples)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--half", action="store_true", help="fp16 weights and activations (GPU)")
    ap.add_argument("--threads", type=int, default=0, help="torch CPU threads (0 = all cores)")
    ap.add_argument("--images", required=True, help="folder of COCO val2017 jpgs")
    ap.add_argument("--n", type=int, default=50, help="frames for timing")
    ap.add_argument("--warmup", type=int, default=5)
    ap.add_argument("--power", default="none", choices=["none", "jetson", "pi", "laptop"])
    ap.add_argument("--all-segments", action="store_true", help="time every segment (a, b] directly")
    ap.add_argument("--seg-frames", type=int, default=10)
    ap.add_argument("--preheat", type=float, default=0.0, help="seconds of inference before measuring")
    ap.add_argument("--label", required=True)
    ap.add_argument("--weights", default="yolov8s.pt")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    from ultralytics.data.augment import LetterBox
    try:
        from ultralytics.utils.nms import non_max_suppression
    except ImportError:
        from ultralytics.utils.ops import non_max_suppression

    # ultralytics caps torch at one thread on import; set the thread count afterwards
    threads = a.threads or os.cpu_count()
    torch.set_num_threads(threads)
    dev = torch.device(a.device)
    gpu = dev.type == "cuda"
    sync = (lambda: torch.cuda.synchronize()) if gpu else (lambda: None)
    dtype = torch.float16 if a.half else torch.float32
    model = load_model(a.weights, dev, a.half)
    layers = model.model
    L = len(layers)
    files = sorted(glob.glob(os.path.join(a.images, "*.jpg")))[: a.n + a.warmup]
    lb = LetterBox((640, 640), auto=False)
    raw = [cv2.imread(f) for f in files]

    def prep(img):
        im = lb(image=img)
        t = torch.from_numpy(np.ascontiguousarray(im[..., ::-1].transpose(2, 0, 1))).to(dev)
        return (t.to(dtype) / 255.0).unsqueeze(0), im

    res = {"label": a.label, "host": platform.node(), "device": a.device, "half": a.half, "threads": threads,
           "torch": torch.__version__, "frames": a.n, "warmup": a.warmup, "num_layers": L,
           "live_sets": {k: live_set(layers, k) for k in range(-1, L)}}
    if gpu:
        res["gpu"] = torch.cuda.get_device_name(0)

    with torch.inference_mode():
        # preprocessing + warm-up
        pre, tensors, lbimgs = [], [], []
        for img in raw:
            sync()
            t0 = time.perf_counter()
            x, im = prep(img)
            sync()
            pre.append((time.perf_counter() - t0) * 1e3)
            tensors.append(x)
            lbimgs.append(im)
        for x in tensors[: a.warmup]:
            model(x)
        sync()
        if a.preheat > 0:   # reach the sustained (thermal steady-state) operating point first
            t_end, i = time.time() + a.preheat, 0
            while time.time() < t_end:
                model(tensors[i % len(tensors)])
                i += 1
            sync()
        res["preheat_s"] = a.preheat
        X = tensors[a.warmup:]
        res["pre_ms"] = statistics.median(pre[a.warmup:])

        # whole model, no per-layer sync
        full, outs = [], []
        for x in X:
            sync()
            t0 = time.perf_counter()
            o = model(x)
            sync()
            full.append((time.perf_counter() - t0) * 1e3)
            outs.append(o)
        res["full_ms"] = statistics.median(full)
        res["full_ms_p95"] = float(np.percentile(full, 95))

        # NMS
        post = []
        for o in outs:
            sync()
            t0 = time.perf_counter()
            non_max_suppression(o[0] if isinstance(o, (list, tuple)) else o, 0.25, 0.45)
            sync()
            post.append((time.perf_counter() - t0) * 1e3)
        res["post_ms"] = statistics.median(post)

        # per-layer times
        times = {i: [] for i in range(L)}
        states = []
        for x in X:
            st = run_segment(layers, {-1: x}, -1, L - 1, sync, times)
            states.append(st)
        res["layer_ms"] = [statistics.median(times[i]) for i in range(L)]

        # validation of the composition on real segments
        checks = []
        for a_, b_ in [(-1, 4), (4, 22), (-1, 9), (9, 22), (4, 9), (-1, 15), (15, 22), (-1, 2), (2, 22)]:
            seg = []
            for x in X[: min(len(X), 20)]:
                st = run_segment(layers, {-1: x}, -1, a_) if a_ >= 0 else {-1: x}
                sync()
                t0 = time.perf_counter()
                run_segment(layers, st, a_, b_)
                sync()
                seg.append((time.perf_counter() - t0) * 1e3)
            checks.append({"a": a_, "b": b_, "measured_ms": statistics.median(seg),
                           "composed_ms": sum(res["layer_ms"][a_ + 1: b_ + 1])})
        res["segment_check"] = checks

        # every segment (a, b], timed end to end (GPUs: launch overhead makes per-layer sums inexact)
        if a.all_segments:
            nseg = min(len(X), a.seg_frames)
            ys = []
            for x in X[:nseg]:
                y = {-1: x}
                y.update(run_segment_all(layers, x))
                ys.append(y)
            seg_ms = {}
            for a_ in range(-1, L - 1):
                for b_ in range(a_ + 1, L):
                    tt = []
                    for rep in range(2):
                        for y in ys:
                            st = {j: y[j] for j in live_set(layers, a_)}
                            sync()
                            t0 = time.perf_counter()
                            run_segment(layers, st, a_, b_)
                            sync()
                            tt.append((time.perf_counter() - t0) * 1e3)
                    seg_ms[f"{a_},{b_}"] = statistics.median(tt[len(ys):])  # second pass: warm caches
            res["segment_ms"] = seg_ms
            del ys

        # codecs at every cut
        cctx, dctx = zstd.ZstdCompressor(level=1), zstd.ZstdDecompressor()
        codec = {}
        ncod = min(len(X), 20)
        for k in range(0, L - 1):
            live = live_set(layers, k)
            rec = {m: {"enc": [], "dec": [], "bytes": []} for m in ("int8_zstd", "fp16")}
            for x in X[:ncod]:
                full_state = {-1: x}
                full_state.update(run_segment(layers, {-1: x}, -1, k))
                ts = [full_state[j] for j in live]
                # INT8 + zstd
                sync()
                t0 = time.perf_counter()
                blobs = []
                for t in ts:
                    s = (t.abs().max().float() / 127.0).clamp_min(1e-12)
                    q = torch.round(t.float() / s).clamp_(-127, 127).to(torch.int8).cpu().numpy()
                    blobs.append((float(s), q.shape, cctx.compress(q.tobytes())))
                rec["int8_zstd"]["enc"].append((time.perf_counter() - t0) * 1e3)
                rec["int8_zstd"]["bytes"].append(sum(len(b[2]) + 16 for b in blobs))
                t0 = time.perf_counter()
                for s, shp, b in blobs:
                    q = np.frombuffer(dctx.decompress(b), dtype=np.int8).reshape(shp)
                    torch.from_numpy(q.copy()).to(dev).to(dtype).mul_(s)
                sync()
                rec["int8_zstd"]["dec"].append((time.perf_counter() - t0) * 1e3)
                # FP16
                sync()
                t0 = time.perf_counter()
                hb = [t.half().cpu().numpy().tobytes() for t in ts]
                rec["fp16"]["enc"].append((time.perf_counter() - t0) * 1e3)
                rec["fp16"]["bytes"].append(sum(len(b) + 16 for b in hb))
                t0 = time.perf_counter()
                for t, b in zip(ts, hb):
                    torch.from_numpy(np.frombuffer(b, dtype=np.float16).reshape(t.shape).copy()).to(dev).to(dtype)
                sync()
                rec["fp16"]["dec"].append((time.perf_counter() - t0) * 1e3)
            codec[k] = {m: {"enc_ms": statistics.median(v["enc"]), "dec_ms": statistics.median(v["dec"]),
                            "bytes": float(np.mean(v["bytes"]))} for m, v in rec.items()}
        res["codec"] = codec

        # JPEG of the letterboxed frame
        enc, dec, size = [], [], []
        for im in lbimgs[a.warmup:]:
            t0 = time.perf_counter()
            ok, buf = cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, 90])
            enc.append((time.perf_counter() - t0) * 1e3)
            size.append(len(buf))
            t0 = time.perf_counter()
            cv2.imdecode(buf, cv2.IMREAD_COLOR)
            dec.append((time.perf_counter() - t0) * 1e3)
        res["jpeg"] = {"q": 90, "enc_ms": statistics.median(enc), "dec_ms": statistics.median(dec),
                       "bytes": float(np.mean(size))}

        # power: idle, then back-to-back inference for >= 10 s
        if a.power != "none":
            ps = PowerSampler(a.power, 0.2 if a.power == "pi" else 0.05)
            ps.start()
            time.sleep(1)
            idle, n_idle = ps.measure(seconds=10)

            def load():
                t_end = time.time() + 15
                i = 0
                while time.time() < t_end:
                    model(X[i % len(X)])
                    sync()
                    i += 1
            active, n_act = ps.measure(fn=load)
            ps.stop_flag = True
            res["power"] = {"sensor": a.power, "idle_w": idle, "active_w": active, "samples": [n_idle, n_act]}
        def pi_state():
            try:
                clk = subprocess.run(["vcgencmd", "measure_clock", "arm"], capture_output=True, text=True).stdout
                thr = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True).stdout
                return {"arm_clock_hz": int(clk.strip().split("=")[1]), "throttled": thr.strip().split("=")[1]}
            except Exception:
                return None
        res["pi_state_end"] = pi_state()
        res["temperature_c"] = None
        try:
            tz = glob.glob("/sys/class/thermal/thermal_zone*/temp")
            res["temperature_c"] = max(float(open(t).read()) / 1e3 for t in tz) if tz else None
        except Exception:
            pass

    with open(a.out, "w") as f:
        json.dump(res, f, indent=1)
    print(json.dumps({k: res[k] for k in ("label", "full_ms", "pre_ms", "post_ms")}),
          "sum(layer_ms)=%.2f" % sum(res["layer_ms"]), "jpeg=%s" % res["jpeg"], "power=%s" % res.get("power"))


if __name__ == "__main__":
    main()


def fast_nms(pred, conf=0.25, iou=0.45, max_det=100, topk=1000):
    """Single-label NMS for a raw YOLOv8 output (1, 4 + nc, N), vectorised on the device.

    Same rule as ultralytics.utils.nms.non_max_suppression (multi_label=False, class-aware): each box takes
    its best class score, boxes below `conf` are dropped, class-offset NMS at `iou`, the `max_det` best kept.
    Only the `topk` highest-scoring candidates enter NMS (ultralytics uses 30,000): a box can only be
    suppressed by a higher-scoring box, so every decision inside the top-k is identical. Returns (n, 6):
    x1, y1, x2, y2, score, class.
    """
    import torchvision
    p = pred[0].transpose(0, 1)
    scores, cls = p[:, 4:].float().max(1)
    keep = scores > conf
    p, scores, cls = p[keep], scores[keep], cls[keep]
    if scores.numel() > topk:
        idx = scores.topk(topk).indices
        p, scores, cls = p[idx], scores[idx], cls[idx]
    xy, wh = p[:, :2].float(), p[:, 2:4].float()
    boxes = torch.cat([xy - wh / 2, xy + wh / 2], 1)
    i = torchvision.ops.batched_nms(boxes, scores, cls, iou)[:max_det]
    return torch.cat([boxes[i], scores[i, None], cls[i, None].float()], 1)
