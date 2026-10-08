#!/usr/bin/env python3
"""One node of a live, distributed YOLOv8s pipeline (validation of the placement model).

A placement is a chain of devices; each holds a contiguous segment (a, b] of the 23 layers
(cut k = layers 0..k done; -1 = camera frame, 22 = Detect output). The first node is the camera
(UAV), which captures at --fps and processes one frame at a time (a frame captured while it is busy
is skipped). Every node decodes what it receives, runs its segment, and forwards the live tensors
of its output cut, encoded as int8_zstd (symmetric per-tensor INT8 + zstd-1), fp16, or jpeg (only
for the camera frame, quality 90). Each link buffers one frame, newest first. The last node runs
NMS and sends the detections back along the chain, so the camera measures capture-to-result
latency on its own clock.

Links are TCP; on each link the upstream node listens and the downstream node connects
(the laptop sits behind NAT and can only connect out).

  pipeline_node.py --role source --seg -1:4 --enc int8_zstd --listen 47800 --images frames ...
  pipeline_node.py --role mid    --seg 4:9  --enc int8_zstd --up HOST:47800 --listen 47801 ...
  pipeline_node.py --role sink   --seg 9:22 --up HOST:47801 ...
A single-device placement is --role solo --seg -1:22.
"""

import argparse
import fcntl
import glob
import json
import os
import queue
import socket
import statistics
import struct
import termios
import threading
import time

import cv2
import numpy as np
import torch
import zstandard as zstd

from hwbench import live_set, load_model, run_segment


# ---------------------------------------------------------------- wire format
def send_msg(sock, header, blobs, lock):
    h = json.dumps(header).encode()
    parts = [struct.pack("!I", len(h)), h, struct.pack("!I", len(blobs))]
    for b in blobs:
        parts += [struct.pack("!I", len(b)), b]
    with lock:
        sock.sendall(b"".join(parts))


def recv_exact(sock, n):
    buf = bytearray(n)
    view, got = memoryview(buf), 0
    while got < n:
        r = sock.recv_into(view[got:], min(n - got, 1 << 20))
        if r == 0:
            raise ConnectionError("closed")
        got += r
    return bytes(buf)


def recv_msg(sock):
    h = json.loads(recv_exact(sock, struct.unpack("!I", recv_exact(sock, 4))[0]))
    blobs = [recv_exact(sock, struct.unpack("!I", recv_exact(sock, 4))[0])
             for _ in range(struct.unpack("!I", recv_exact(sock, 4))[0])]
    return h, blobs


class Slot:
    """One-frame buffer, newest wins."""

    def __init__(self):
        self.cv, self.item, self.dropped = threading.Condition(), None, 0

    def put(self, item):
        with self.cv:
            if self.item is not None:
                self.dropped += 1
            self.item = item
            self.cv.notify()

    def get(self):
        with self.cv:
            while self.item is None:
                self.cv.wait()
            it, self.item = self.item, None
            return it


# ---------------------------------------------------------------- codecs
CCTX, DCTX = zstd.ZstdCompressor(level=1), zstd.ZstdDecompressor()


def encode(state, keys, enc, img_bgr=None):
    if enc == "jpeg":
        ok, buf = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
        return [{"k": -1, "jpeg": True}], [buf.tobytes()]
    metas, blobs = [], []
    for j in keys:
        t = state[j]
        if enc == "int8_zstd":
            s = (t.abs().max().float() / 127.0).clamp_min(1e-12)
            q = torch.round(t.float() / s).clamp_(-127, 127).to(torch.int8).cpu().numpy()
            metas.append({"k": j, "shape": list(q.shape), "s": float(s), "dt": "i8"})
            blobs.append(CCTX.compress(q.tobytes()))
        else:
            h = t.half().cpu().numpy()
            metas.append({"k": j, "shape": list(h.shape), "dt": "f16"})
            blobs.append(h.tobytes())
    return metas, blobs


def decode(metas, blobs, dev, dtype, prep):
    state = {}
    for m, b in zip(metas, blobs):
        if m.get("jpeg"):
            state[-1] = prep(cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_COLOR), letterboxed=True)[0]
        elif m["dt"] == "i8":
            q = np.frombuffer(DCTX.decompress(b), np.int8).reshape(m["shape"])
            state[m["k"]] = torch.from_numpy(q.copy()).to(dev).to(dtype).mul_(m["s"])
        else:
            state[m["k"]] = torch.from_numpy(np.frombuffer(b, np.float16).reshape(m["shape"]).copy()).to(dev).to(dtype)
    return state


# ---------------------------------------------------------------- node
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--role", choices=["source", "mid", "sink", "solo"], required=True)
    ap.add_argument("--seg", required=True, help="a:b, layers a+1..b")
    ap.add_argument("--enc", default="int8_zstd", choices=["int8_zstd", "fp16", "jpeg"])
    ap.add_argument("--up", default="", help="HOST:PORT of the upstream node")
    ap.add_argument("--listen", type=int, default=0, help="port for the downstream node")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--half", action="store_true")
    ap.add_argument("--threads", type=int, default=0)
    ap.add_argument("--images", default="frames")
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--duration", type=float, default=60.0)
    ap.add_argument("--deadline", type=float, default=300.0)
    ap.add_argument("--weights", default="yolov8s.pt")
    ap.add_argument("--label", default="")
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    from ultralytics.data.augment import LetterBox
    try:
        from ultralytics.utils.nms import non_max_suppression
    except ImportError:
        from ultralytics.utils.ops import non_max_suppression

    torch.set_num_threads(a.threads or os.cpu_count())
    dev = torch.device(a.device)
    gpu = dev.type == "cuda"
    sync = (lambda: torch.cuda.synchronize()) if gpu else (lambda: None)
    dtype = torch.float16 if a.half else torch.float32
    seg_a, seg_b = map(int, a.seg.split(":"))
    model = load_model(a.weights, dev, a.half)
    layers = model.model
    L = len(layers)
    lb = LetterBox((640, 640), auto=False)

    def prep(img, letterboxed=False):
        im = img if letterboxed else lb(image=img)
        t = torch.from_numpy(np.ascontiguousarray(im[..., ::-1].transpose(2, 0, 1))).to(dev)
        return (t.to(dtype) / 255.0).unsqueeze(0), im

    stage = {"decode": [], "compute": [], "encode": [], "nms": []}
    lock_up, lock_down = threading.Lock(), threading.Lock()

    # warm-up of this node's segment
    with torch.inference_mode():
        x0 = torch.zeros(1, 3, 640, 640, device=dev, dtype=dtype)
        full = {-1: x0}
        if seg_a >= 0:
            full.update(run_segment(layers, {-1: x0}, -1, seg_a))
        for _ in range(3):
            if seg_b > seg_a:
                run_segment(layers, {j: full[j] for j in live_set(layers, seg_a)}, seg_a, seg_b)
        sync()

    up = down = None
    if a.up:
        host, port = a.up.rsplit(":", 1)
        for _ in range(600):
            try:
                up = socket.create_connection((host, int(port)), timeout=10)
                break
            except OSError:
                time.sleep(0.5)
        up.settimeout(None)
        up.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    if a.listen:
        ls = socket.socket()
        ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        ls.bind(("0.0.0.0", a.listen))
        ls.listen(1)
        down, _ = ls.accept()
        down.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    stop = threading.Event()
    out_slot = Slot()

    def compute(state_in, frame_hdr, img_bgr=None):
        """Runs this node's segment; returns (header, blobs) for downstream, or detections."""
        with torch.inference_mode():
            sync()
            t0 = time.perf_counter()
            st = state_in
            if seg_b > seg_a:
                st = run_segment(layers, {j: state_in[j] for j in live_set(layers, seg_a)}, seg_a, seg_b)
            sync()
            stage["compute"].append((time.perf_counter() - t0) * 1e3)
            if seg_b == L - 1:
                t0 = time.perf_counter()
                o = st[L - 1]
                det = non_max_suppression(o[0] if isinstance(o, (list, tuple)) else o, 0.25, 0.45)[0]
                sync()
                stage["nms"].append((time.perf_counter() - t0) * 1e3)
                return dict(frame_hdr, det=True), [det.float().cpu().numpy().tobytes()]
            t0 = time.perf_counter()
            metas, blobs = encode(st, live_set(layers, seg_b), a.enc, img_bgr)
            stage["encode"].append((time.perf_counter() - t0) * 1e3)
            return dict(frame_hdr, metas=metas, bytes=sum(map(len, blobs))), blobs

    def outq(sock):
        try:
            return struct.unpack("i", fcntl.ioctl(sock.fileno(), termios.TIOCOUTQ, b"\0\0\0\0"))[0]
        except OSError:
            return 0

    def sender():
        # one frame on the link at a time: the next is taken from the newest-wins slot only after
        # the previous one has left the socket (as the simulator's uplink rule), so stale frames
        # are dropped instead of queueing in the kernel's send buffer
        while not stop.is_set():
            h, blobs = out_slot.get()
            if h is None:
                return
            send_msg(down, h, blobs, lock_down)
            while outq(down) > 0 and not stop.is_set():
                time.sleep(0.0005)

    # results that come back from downstream go further upstream (or are logged at the source)
    results = []

    def result_relay():
        while not stop.is_set():
            try:
                h, blobs = recv_msg(down)
            except (ConnectionError, OSError):
                return
            if a.role == "source":
                h["t_result"] = time.perf_counter()
                results.append(h)
            else:
                send_msg(up, h, blobs, lock_up)

    if down is not None:
        threading.Thread(target=sender, daemon=True).start()
        threading.Thread(target=result_relay, daemon=True).start()

    report = {"label": a.label, "role": a.role, "seg": a.seg, "enc": a.enc, "host": socket.gethostname(),
              "device": a.device, "half": a.half}
    if a.role in ("source", "solo"):
        frames = [cv2.imread(f) for f in sorted(glob.glob(os.path.join(a.images, "*.jpg")))]
        period = 1.0 / a.fps
        t_start = time.perf_counter() + 1.0
        captured = processed = 0
        local = []           # solo: (capture, done)
        while True:
            now = time.perf_counter()
            if now - t_start > a.duration:
                break
            if now < t_start:
                time.sleep(t_start - now)
                continue
            tick = int((now - t_start) / period)        # newest camera frame at this instant
            cap_t = t_start + tick * period
            captured = tick + 1
            img = frames[tick % len(frames)]
            t0 = time.perf_counter()
            x, im = prep(img)
            hdr = {"id": tick, "t_cap": cap_t}
            if a.role == "solo":
                compute({-1: x}, hdr)
                local.append((cap_t, time.perf_counter()))
            elif seg_b == -1 and a.enc == "jpeg":
                t1 = time.perf_counter()
                metas, blobs = encode({}, [], "jpeg", im)
                stage["encode"].append((time.perf_counter() - t1) * 1e3)
                out_slot.put((dict(hdr, metas=metas, bytes=len(blobs[0])), blobs))
            else:
                out_slot.put(compute({-1: x}, hdr, im))
            processed += 1
            # wait for the next camera frame (a frame arriving while busy was skipped)
            nxt = t_start + (int((time.perf_counter() - t_start) / period) + 1) * period
            time.sleep(max(0.0, nxt - time.perf_counter()))
        time.sleep(3.0)                                  # let in-flight results return
        stop.set()
        if a.role == "solo":
            lat = [(d - c) * 1e3 for c, d in local]
        else:
            out_slot.put((None, None))
            lat = [(h["t_result"] - h["t_cap"]) * 1e3 for h in results]
        on_time = sum(l <= a.deadline for l in lat)
        report.update({"captured": captured, "processed_at_source": processed, "results": len(lat),
                       "fps_results": len(lat) / a.duration, "fps_on_time": on_time / a.duration,
                       "lat_p50_ms": statistics.median(lat) if lat else None,
                       "lat_p95_ms": float(np.percentile(lat, 95)) if lat else None,
                       "lat_mean_ms": float(np.mean(lat)) if lat else None,
                       "dropped_at_link": out_slot.dropped})
    else:
        # mid / sink: receive, decode, compute, forward
        in_slot = Slot()

        def receiver():
            while not stop.is_set():
                try:
                    h, blobs = recv_msg(up)
                except (ConnectionError, OSError):
                    in_slot.put((None, None))
                    return
                if h.get("det"):          # never happens upstream-bound
                    continue
                in_slot.put((h, blobs))

        threading.Thread(target=receiver, daemon=True).start()
        n = 0
        while True:
            h, blobs = in_slot.get()
            if h is None:
                break
            if a.role == "mid" and seg_a == seg_b:      # relay: forward the received bytes unchanged
                out_slot.put((h, blobs))
                n += 1
                continue
            t0 = time.perf_counter()
            st = decode(h["metas"], blobs, dev, dtype, prep)
            sync()
            stage["decode"].append((time.perf_counter() - t0) * 1e3)
            hdr = {"id": h["id"], "t_cap": h["t_cap"]}
            res_h, res_b = compute(st, hdr)
            if a.role == "sink":
                send_msg(up, res_h, res_b, lock_up)
            else:
                out_slot.put((res_h, res_b))
            n += 1
        stop.set()
        report.update({"frames_in": n, "dropped_in": in_slot.dropped})
    report["stage_ms_median"] = {k: (statistics.median(v) if v else None) for k, v in stage.items()}
    report["stage_n"] = {k: len(v) for k, v in stage.items()}
    print(json.dumps(report))
    if a.out:
        json.dump(report, open(a.out, "w"), indent=1)
    for s in (up, down):
        if s is not None:
            try:
                s.close()
            except OSError:
                pass


if __name__ == "__main__":
    main()
