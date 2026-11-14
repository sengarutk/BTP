#!/usr/bin/env python3
"""Predict-then-measure of paper 1's break-even goodput on the mesh (plan T10; 14 Nov 2026).

A camera board sends either a learned split code (YOLOv8s layers 0..k + the bottleneck encoder of
evaluation/learned_bottleneck.py, uint8 + zstd-1, as in that study) or a JPEG of the letterboxed 640 frame; a server
board decodes (bottleneck decoder + layers k+1..22, or the full detector), runs NMS and returns the detections. The
camera measures capture-to-result latency on its own clock.

Sending rule (the model's frame rate F / ceil(F max(e_c, b_c / B))): one thread computes the newest frame's payload
(onboard time e_c), another sends the newest finished payload once the previous one has left the socket (bytes out of
the radio: TIOCOUTQ = 0), so onboard work and transmission overlap and nothing queues; a payload replaced before it is
sent is dropped. At the server, one frame at a time, newest first.

  bench   timing on this board only, no network: onboard time and payload of every option on --n frames; with
          --server also the server-side time  -> JSON on stdout
  serve   --listen PORT  (server board)
  send    --to HOST:PORT --option jpeg_q35|<code tag> --seconds S [--rate-mbit R]  -> JSON on stdout
          --rate-mbit shapes this board's traffic TO THAT PORT ONLY (htb class on --dev, filter on the destination
          port), removed when the run ends, also on error. Other traffic (ssh, batman-adv) is not shaped.
Options: jpeg_qQ (any quality) or a checkpoint tag of weights/learned_bottleneck (e.g. k4_c4_w128_d2). The jointly
trained codes (weights/joint_bottleneck) are pickled whole training models and are not supported. Frames: the VisDrone-VID clip in --frames (as every campaign). Deadline --deadline-ms 300.
"""
import argparse
import fcntl
import glob
import json
import os
import socket
import struct
import subprocess
import termios
import threading
import time

import cv2
import numpy as np
import torch
import torch.nn as nn

HERE = os.path.dirname(os.path.abspath(__file__))


def conv(ci, co, k=3, s=1):
    return nn.Sequential(nn.Conv2d(ci, co, k, s, k // 2, bias=False), nn.BatchNorm2d(co), nn.SiLU())


class Bottleneck(nn.Module):
    """Identical to evaluation/learned_bottleneck.py's Bottleneck (copied so the boards need only this file)."""

    def __init__(self, c_in, c_b, width=64, stride=2, dec_layers=1):
        super().__init__()
        self.enc = nn.Sequential(conv(c_in, width, 3, stride), nn.Conv2d(width, c_b, 3, 1, 1))
        up = [nn.Upsample(scale_factor=2, mode="nearest")] if stride == 2 else []
        self.dec = nn.Sequential(conv(c_b, width), *up, *[conv(width, width) for _ in range(dec_layers)],
                                 nn.Conv2d(width, c_in, 1))


def load_code(tag, dev):
    """tag 'k4_c4_w128_d2' (frozen-detector code) or 'joint:k4_c4_w128_d2' (jointly trained): (bottleneck, cut)."""
    sub, t = ("joint_bottleneck", tag.split(":", 1)[1]) if tag.startswith("joint:") else ("learned_bottleneck", tag)
    for base in (os.path.join(HERE, "weights", sub), os.path.join(HERE, "..", "..", "weights", sub)):
        p = os.path.join(base, f"{t}.pt")
        if os.path.exists(p):
            ck = torch.load(p, map_location=dev)
            bn = Bottleneck(ck["c_in"], ck["channels"], ck.get("width", 64), ck.get("stride", 2),
                            ck.get("dec_layers", 1)).to(dev).eval()
            bn.load_state_dict(ck["state"])
            return bn, int(ck.get("cut", int(t.split("_")[0][1:])))
    raise FileNotFoundError(f"{sub}/{t}.pt")


def load_det(weights, dev, half):
    from ultralytics import YOLO
    det = YOLO(weights).model.to(dev).eval()
    return det.half() if half else det


def letterbox(img, size=640):
    h, w = img.shape[:2]
    r = min(size / h, size / w)
    nh, nw = round(h * r), round(w * r)
    out = np.full((size, size, 3), 114, np.uint8)
    top, left = (size - nh) // 2, (size - nw) // 2
    out[top:top + nh, left:left + nw] = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    return out


def to_tensor(img, dev, half):
    t = torch.from_numpy(np.ascontiguousarray(img[:, :, ::-1].transpose(2, 0, 1))).to(dev).unsqueeze(0)
    t = t.half() if half else t.float()
    return t / 255.0


def run_layers(det, x, first, last, y=None):
    """Layers first..last of the detector (as BaseModel._predict_once). y: the saved outputs so far (list)."""
    y = y if y is not None else []
    for m in det.model[first:last + 1]:
        if m.f != -1:
            x = y[m.f] if isinstance(m.f, int) else [x if j == -1 else y[j] for j in m.f]
        x = m(x)
        y.append(x if m.i in det.save else None)
    return x, y


def nms(out):
    try:
        from ultralytics.utils.nms import non_max_suppression
    except ImportError:
        from ultralytics.utils.ops import non_max_suppression
    p = out[0] if isinstance(out, (list, tuple)) else out
    return non_max_suppression(p.float(), 0.01, 0.45, max_det=300)[0]


class Encoder:
    """Camera side of one option: frame -> payload bytes."""

    def __init__(self, option, det, dev, half):
        import zstandard
        self.option, self.det, self.dev, self.half = option, det, dev, half
        self.cz = zstandard.ZstdCompressor(level=1)
        if option.startswith("jpeg_q"):
            self.q, self.bn, self.cut = int(option[6:]), None, -1
        else:
            self.bn, self.cut = load_code(option, dev)
            if half:
                self.bn = self.bn.half()

    @torch.inference_mode()
    def __call__(self, img):
        lb = letterbox(img)
        if self.bn is None:
            ok, buf = cv2.imencode(".jpg", lb, [cv2.IMWRITE_JPEG_QUALITY, self.q])
            return buf.tobytes()
        x, _ = run_layers(self.det, to_tensor(lb, self.dev, self.half), 0, self.cut)
        z = self.bn.enc(x.to(next(self.bn.parameters()).dtype)).float()
        lo, hi = float(z.min()), float(z.max())
        sc = max(hi - lo, 1e-8) / 255.0
        q = torch.round((z - lo) / sc).clamp(0, 255).to(torch.uint8).cpu().numpy()
        hdr = struct.pack("<ff4H", lo, sc, *q.shape)
        return hdr + self.cz.compress(q.tobytes())


class Decoder:
    """Server side: payload -> detections (count)."""

    def __init__(self, det, dev, half):
        import zstandard
        self.det, self.dev, self.half, self.dz, self.codes = det, dev, half, zstandard.ZstdDecompressor(), {}

    @torch.inference_mode()
    def __call__(self, option, payload):
        if option.startswith("jpeg_q"):
            img = cv2.imdecode(np.frombuffer(payload, np.uint8), cv2.IMREAD_COLOR)
            out, _ = run_layers(self.det, to_tensor(img, self.dev, self.half), 0, len(self.det.model) - 1)
        else:
            if option not in self.codes:
                bn, cut = load_code(option, self.dev)
                self.codes[option] = (bn.half() if self.half else bn, cut)
            bn, cut = self.codes[option]
            lo, sc, *shape = struct.unpack("<ff4H", payload[:16])     # 16-byte header: min, scale, code shape
            q = np.frombuffer(self.dz.decompress(payload[16:]), np.uint8).reshape(shape)
            z = torch.from_numpy(q.copy()).to(self.dev).float() * sc + lo
            x = bn.dec(z.to(next(bn.parameters()).dtype))
            y = [None] * cut + [x if cut in self.det.save else None]
            out, _ = run_layers(self.det, x, cut + 1, len(self.det.model) - 1, y)
        if self.dev.type == "cuda":
            torch.cuda.synchronize()
        return int(nms(out).shape[0])


def frames_of(d):
    fs = sorted(glob.glob(os.path.join(d, "**", "*.jpg"), recursive=True))
    if not fs:
        raise SystemExit(f"no frames in {d}")
    return fs


def send_msg(s, hdr, payload):
    h = json.dumps(hdr).encode()
    s.sendall(struct.pack("<II", len(h), len(payload)) + h + payload)


def recv_exact(s, n):
    b = bytearray()
    while len(b) < n:
        c = s.recv(n - len(b))
        if not c:
            raise ConnectionError("closed")
        b += c
    return bytes(b)


def recv_msg(s):
    lh, lp = struct.unpack("<II", recv_exact(s, 8))
    return json.loads(recv_exact(s, lh)), recv_exact(s, lp)


def outq(s):
    return struct.unpack("i", fcntl.ioctl(s.fileno(), termios.TIOCOUTQ, b"\0\0\0\0"))[0]


def shape(dev, port, rate, on):
    def tc(a):
        return subprocess.run(["sudo", "-n", "tc"] + a.split(), capture_output=True, text=True)
    tc(f"qdisc del dev {dev} root")
    if not on:
        return
    for a in (f"qdisc add dev {dev} root handle 1: htb default 30",
              f"class add dev {dev} parent 1: classid 1:10 htb rate {rate}mbit ceil {rate}mbit burst 15k",
              f"class add dev {dev} parent 1: classid 1:30 htb rate 1000mbit",
              f"filter add dev {dev} parent 1: protocol ip prio 1 u32 match ip dport {port} 0xffff flowid 1:10"):
        r = tc(a)
        if r.returncode:
            tc(f"qdisc del dev {dev} root")
            raise SystemExit(f"tc failed: {a}: {r.stderr.strip()} (needs passwordless sudo for tc, or run as root)")


def cmd_bench(a, dev):
    det = load_det(a.weights, dev, a.half)
    fs = frames_of(a.frames)[: a.n]
    imgs = [cv2.imread(f) for f in fs]
    out = {"device": str(dev), "half": a.half, "n": len(imgs), "options": {}}
    dec = Decoder(det, dev, a.half) if a.server else None
    for opt in a.options.split(","):
        enc = Encoder(opt, det, dev, a.half)
        for im in imgs[:3]:                               # warm-up
            p = enc(im)
            if dec:
                dec(opt, p)
        e_ms, s_ms, kb = [], [], []
        for im in imgs:
            t0 = time.perf_counter()
            p = enc(im)
            if dev.type == "cuda":
                torch.cuda.synchronize()
            e_ms.append((time.perf_counter() - t0) * 1e3)
            kb.append(len(p) / 1024)
            if dec:
                t0 = time.perf_counter()
                dec(opt, p)
                s_ms.append((time.perf_counter() - t0) * 1e3)
        out["options"][opt] = {"onboard_ms_median": float(np.median(e_ms)), "onboard_ms_p90": float(np.percentile(e_ms, 90)),
                               "payload_kb_mean": float(np.mean(kb)), "payload_kb_p95": float(np.percentile(kb, 95)),
                               **({"server_ms_median": float(np.median(s_ms))} if s_ms else {})}
    print(json.dumps(out))


def cmd_serve(a, dev):
    det = load_det(a.weights, dev, a.half)
    dec = Decoder(det, dev, a.half)
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", a.listen))
    srv.listen(1)
    print(f"serving on {a.listen}", flush=True)
    while True:
        s, _ = srv.accept()
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        newest, lock, cv, done = [None], threading.Lock(), threading.Condition(), [False]

        def reader():
            try:
                while True:
                    h, p = recv_msg(s)
                    if h.get("bye"):
                        break
                    with cv:
                        newest[0] = (h, p, time.perf_counter())   # newest first: a waiting frame is replaced
                        cv.notify()
            except (ConnectionError, OSError):
                pass
            with cv:
                done[0] = True
                cv.notify()
        threading.Thread(target=reader, daemon=True).start()
        while True:
            with cv:
                while newest[0] is None and not done[0]:
                    cv.wait()
                if newest[0] is None and done[0]:
                    break
                h, p, t_in = newest[0]
                newest[0] = None
            t0 = time.perf_counter()
            nd = dec(h["opt"], p)
            try:
                with lock:
                    send_msg(s, {"id": h["id"], "ndet": nd, "server_ms": (time.perf_counter() - t0) * 1e3,
                                 "wait_ms": (t0 - t_in) * 1e3}, b"")
            except OSError:
                break
        s.close()
        if a.once:
            break


def cmd_send(a, dev):
    det = load_det(a.weights, dev, a.half)
    enc = Encoder(a.option, det, dev, a.half)
    imgs = [cv2.imread(f) for f in frames_of(a.frames)]
    host, port = a.to.rsplit(":", 1)
    port = int(port)
    for im in imgs[:3]:
        enc(im)
    if a.rate_mbit > 0:
        shape(a.dev, port, a.rate_mbit, True)
    try:
        s = socket.create_connection((host, port), timeout=10)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        s.settimeout(None)
        period, t_start = 1.0 / a.fps, time.perf_counter() + 0.5
        ready, sent, res = [None], {}, {}
        cv, stop = threading.Condition(), [False]

        def computer():                                    # newest frame -> payload, continuously
            while not stop[0]:
                el = time.perf_counter() - t_start
                if el < 0:
                    time.sleep(-el)
                    continue
                if el >= a.seconds:
                    break
                tick = int(el / period)
                cap = t_start + tick * period
                p = enc(imgs[tick % len(imgs)])
                with cv:
                    ready[0] = (tick, cap, p, time.perf_counter() - cap)
                    cv.notify()
                nxt = t_start + (int((time.perf_counter() - t_start) / period) + 1) * period
                time.sleep(max(0.0, nxt - time.perf_counter()))

        def receiver():
            try:
                while True:
                    h, _ = recv_msg(s)
                    res[h["id"]] = (time.perf_counter(), h["server_ms"], h["wait_ms"])
            except (ConnectionError, OSError, struct.error):
                pass
        tc_ = threading.Thread(target=computer, daemon=True)
        tc_.start()
        threading.Thread(target=receiver, daemon=True).start()
        last = -1
        while tc_.is_alive() or ready[0] is not None:
            with cv:
                while ready[0] is None and tc_.is_alive():
                    cv.wait(0.05)
                item, ready[0] = ready[0], None
            if item is None:
                continue
            tick, cap, p, e_s = item
            if tick <= last:
                continue
            while outq(s) > 0:                             # the previous payload has not left the radio yet
                time.sleep(0.0005)
            send_msg(s, {"id": tick, "opt": a.option}, p)
            sent[tick] = (cap, len(p), e_s * 1e3)
            last = tick
        time.sleep(2.0)
        stop[0] = True
        try:
            send_msg(s, {"bye": True}, b"")
            s.close()
        except OSError:
            pass
    finally:
        if a.rate_mbit > 0:
            shape(a.dev, port, a.rate_mbit, False)
    lat = [(res[k][0] - sent[k][0]) * 1e3 for k in sent if k in res]
    on = sum(1 for x in lat if x <= a.deadline_ms)
    print(json.dumps({"option": a.option, "rate_mbit": a.rate_mbit, "seconds": a.seconds, "fps": a.fps,
                      "sent": len(sent), "results": len(lat), "on_time": on, "on_time_fps": on / a.seconds,
                      "lat_p50_ms": float(np.median(lat)) if lat else None,
                      "lat_p90_ms": float(np.percentile(lat, 90)) if lat else None,
                      "payload_kb_mean": float(np.mean([v[1] for v in sent.values()]) / 1024) if sent else None,
                      "onboard_ms_median": float(np.median([v[2] for v in sent.values()])) if sent else None,
                      "server_ms_median": float(np.median([res[k][1] for k in res])) if res else None}))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["bench", "serve", "send"])
    ap.add_argument("--weights", default="yolov8s_visdrone.pt")
    ap.add_argument("--frames", default="visdrone_vid_640")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--half", action="store_true")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--options", default="jpeg_q20,jpeg_q35,jpeg_q90,k4_c4_w128_d2,k4_c8_w128_d2,k2_c8_w128_d2")
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--server", action="store_true", help="bench: also time the server side on this board")
    ap.add_argument("--listen", type=int, default=48190)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--to", default="")
    ap.add_argument("--option", default="jpeg_q35")
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--rate-mbit", type=float, default=0.0)
    ap.add_argument("--dev", default="bat0")
    ap.add_argument("--deadline-ms", type=float, default=300.0)
    a = ap.parse_args()
    torch.set_num_threads(a.threads)
    dev = torch.device(a.device)
    {"bench": cmd_bench, "serve": cmd_serve, "send": cmd_send}[a.cmd](a, dev)


if __name__ == "__main__":
    main()
