#!/usr/bin/env python3
"""V5: real-stack emulation under Linux traffic control, compared with the Python simulator.

Everything that can be real is real: COCO frames, the edge DNN prefix on the GPU, INT8 quantization
with zstd and the authenticated packet format (or OpenCV JPEG encoding), a TCP connection through the
kernel on the loopback interface shaped by ``tc netem`` (rate, delay, loss), packet parsing,
dequantization, the cloud DNN suffix (or JPEG decoding and the full model) and NMS on the GPU.
The UAV side follows the simulator's frame logic: camera ticks, a sequential onboard processor whose
time is padded to the modelled onboard time for t_full, newest-frame-wins buffering, one frame on
the link at a time, a deadline test, and abandonment at the deadline. The server acknowledges each
frame after NMS; a frame is on time if its acknowledgement shows the result within 300 ms of capture.

The same settings are then simulated by simulation/stream_sim.py with a constant channel of the same
rate and delay (and, for the trace case, the same trace). Needs root for tc (password via SUDO_PASS or
an interactive sudo). Output: experiments/results/validation/emulation.csv.
"""

import argparse
import fcntl
import termios
import json
import os
import socket
import struct
import subprocess
import threading
import time
from pathlib import Path

import cv2
import numpy as np
import torch

REPO = Path(__file__).resolve().parent.parent
PORT = [47000]  # incremented per run, so consecutive runs never share a listening port
HDR = struct.Struct("!IdI")          # frame id, capture time (s), payload length
ACK = struct.Struct("!Id")           # frame id, result time (s)


def sudo(cmd: list) -> None:
    pw = os.environ.get("SUDO_PASS")
    full = ["sudo", "-S", "-p", ""] + cmd if pw else ["sudo"] + cmd
    subprocess.run(full, input=(pw + "\n") if pw else None, text=True, check=True, capture_output=True)


def netem(rate_mbps: float, delay_ms: float, loss_pct: float = 0.0) -> None:
    # Loopback carries both directions; the delay is applied once per direction, so the round trip
    # has twice the delay, as on a real uplink/downlink pair.
    cmd = ["tc", "qdisc", "replace", "dev", "lo", "root", "netem", "delay", f"{delay_ms:.2f}ms",
           "rate", f"{max(rate_mbps, 0.01):.3f}mbit", "limit", "100000"]
    if loss_pct > 0:
        cmd += ["loss", f"{loss_pct:.3f}%"]
    sudo(cmd)


def netem_clear() -> None:
    try:
        sudo(["tc", "qdisc", "del", "dev", "lo", "root"])
    except subprocess.CalledProcessError:
        pass


def recv_exact(sock, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(min(1 << 20, n - len(buf)))
        if not chunk:
            raise ConnectionError("closed")
        buf += chunk
    return bytes(buf)


class Models:
    def __init__(self, kind: str, device: str):
        from ultralytics import YOLO
        from core.dynamic_submodels import DynamicCloudSubmodel, DynamicEdgeSubmodel
        base = YOLO(str(REPO / "yolov8s.pt")).model.to(device).eval()
        self.kind, self.device = kind, device
        self.base = base
        if kind == "split":
            self.edge = DynamicEdgeSubmodel(base, 4).to(device)
            self.cloud = DynamicCloudSubmodel(base, 4).to(device)


def to_tensor(bgr, device):
    return torch.from_numpy(np.ascontiguousarray(bgr[:, :, ::-1])).permute(2, 0, 1)[None].float().div(255.0).to(device)


def server(models: Models, ready: threading.Event, stop: threading.Event, stats: dict):
    from protocol.packet import AegisPacketProtocol
    from quantization.quantizer import FeatureMapQuantizer
    from ultralytics.utils import nms
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", PORT[0]))
    srv.listen(1)
    ready.set()
    conn, _ = srv.accept()
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    try:
        while not stop.is_set():
            fid, cap, n = HDR.unpack(recv_exact(conn, HDR.size))
            payload = recv_exact(conn, n)
            with torch.no_grad():
                if models.kind == "split":
                    parsed = AegisPacketProtocol.deserialize(payload, device=models.device)
                    x = FeatureMapQuantizer.dequantize(parsed["reconstructed_data"], parsed["scales"],
                                                       dtype="int8_zstd", device=models.device)
                    out = models.cloud(x)
                else:
                    img = cv2.imdecode(np.frombuffer(payload, np.uint8), cv2.IMREAD_COLOR)
                    out = models.base(to_tensor(img, models.device))
                nms.non_max_suppression(out[0] if isinstance(out, (list, tuple)) else out, conf_thres=0.25, iou_thres=0.45)
                if models.device.startswith("cuda"):
                    torch.cuda.synchronize()
            conn.sendall(ACK.pack(fid, time.time()))
            stats["served"] = stats.get("served", 0) + 1
    except (ConnectionError, OSError):
        pass
    finally:
        conn.close()
        srv.close()


def uav(models: Models, frames, onboard_ms: float, duration_s: float, deadline_ms: float = 300.0, fps: float = 30.0):
    from protocol.packet import AegisPacketProtocol
    from quantization.quantizer import FeatureMapQuantizer
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 << 20)
    sock.connect(("127.0.0.1", PORT[0]))
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    period = 1.0 / fps
    lock = threading.Lock()
    state = {"pending": None, "busy_until": 0.0, "in_flight": None, "done": False}
    results = {}          # fid -> (capture, result time)
    counts = {"captured": 0, "skipped": 0, "superseded": 0, "sent": 0, "stale": 0}
    wake = threading.Condition(lock)

    def encode(img, fid, cap):
        with torch.no_grad():
            if models.kind == "split":
                q, s = FeatureMapQuantizer.quantize(models.edge(to_tensor(img, models.device)), dtype="int8_zstd")
                return AegisPacketProtocol.serialize(fid, int(cap * 1000), 4, "int8_zstd", q, s)
            ok, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
            return enc.tobytes()

    def acks():
        try:
            while True:
                fid, t = ACK.unpack(recv_exact(sock, ACK.size))
                with wake:
                    results[fid] = t
        except (ConnectionError, OSError):
            pass

    def sender():
        while True:
            with wake:
                while not state["done"] and state["pending"] is None:
                    wake.wait(0.005)
                if state["done"]:
                    return
                fid, cap, pkt = state["pending"]
                state["pending"] = None
                if time.time() - cap > deadline_ms / 1000:
                    counts["stale"] += 1
                    continue
                counts["sent"] += 1
            # One frame on the link at a time: the next frame is taken once the kernel reports no
            # unacknowledged bytes (TIOCOUTQ = 0), i.e. about one round trip after the last byte was sent;
            # the simulator releases the link at the end of transmission, so this is slightly conservative.
            # Unlike the simulator, a frame being sent is not aborted at its deadline.
            sock.sendall(HDR.pack(fid, cap, len(pkt)) + pkt)
            while struct.unpack("i", fcntl.ioctl(sock.fileno(), termios.TIOCOUTQ, b"\0\0\0\0"))[0] > 0:
                time.sleep(0.0005)

    threading.Thread(target=acks, daemon=True).start()
    tx = threading.Thread(target=sender, daemon=True)
    tx.start()
    t0 = time.time()
    fid = 0
    captures = {}
    next_tick = t0
    while time.time() - t0 < duration_s:
        now = time.time()
        if now < next_tick:
            time.sleep(next_tick - now)
        cap = next_tick
        next_tick += period
        counts["captured"] += 1
        if cap < state["busy_until"]:
            counts["skipped"] += 1
            continue
        fid += 1
        captures[fid] = cap
        img = frames[fid % len(frames)]
        t_start = time.time()
        pkt = encode(img, fid, cap)
        if models.device.startswith("cuda"):
            torch.cuda.synchronize()
        # pad real edge compute to the modelled onboard time (t_full scaling), like the simulator
        done_at = cap + onboard_ms / 1000.0
        state["busy_until"] = done_at
        wait = done_at - time.time()
        if wait > 0:
            time.sleep(wait)
        with wake:
            if state["pending"] is not None:
                counts["superseded"] += 1
            state["pending"] = (fid, cap, pkt)
            wake.notify_all()
        _ = t_start
    time.sleep(0.5)
    with wake:
        state["done"] = True
        wake.notify_all()
    sock.close()
    on_time = sum(1 for f, t in results.items() if (t - captures[f]) * 1000 <= deadline_ms)
    lat = sorted((t - captures[f]) * 1000 for f, t in results.items())
    return {"on_time_fps": on_time / duration_s, "delivered": len(results), "on_time": on_time,
            "lat_p50_ms": lat[len(lat) // 2] if lat else float("nan"), **counts,
            "bytes_per_frame": float(np.mean([len(encode(frames[i], 0, 0.0)) for i in range(5)]))}


def emulate(kind, onboard_ms, rate, delay_ms, duration, device, frames):
    models = Models(kind, device)
    for img in frames[:5]:          # warm-up
        with torch.no_grad():
            (models.edge(to_tensor(img, device)) if kind == "split" else models.base(to_tensor(img, device)))
    PORT[0] += 1
    netem(rate, delay_ms)
    ready, stop, stats = threading.Event(), threading.Event(), {}
    th = threading.Thread(target=server, args=(models, ready, stop, stats), daemon=True)
    th.start()
    ready.wait()
    try:
        res = uav(models, frames, onboard_ms, duration)
    finally:
        stop.set()
        netem_clear()
    return res


def simulate_same(cfg_name, t_full, rate, delay_ms, duration, seeds=3, payload_bytes=None, release_extra_ms=0.0):
    from simulation.stream_sim import SimParams, simulate
    from simulation.system_model import load_offload_configs, make_hardware
    from simulation.trace_generator import ChannelProfile
    from dataclasses import replace
    configs = load_offload_configs()
    if payload_bytes:  # simulate the frame size the emulation actually sent
        configs[cfg_name] = replace(configs[cfg_name], payload_bytes=float(payload_bytes))
    hw = make_hardware(t_full)
    # Constant channel: high SINR, no shadowing or fading, bandwidth chosen so the capped rate equals `rate`;
    # base delay chosen so the trace delay (base + jitter mean 2 ms) equals `delay_ms`.
    prof = ChannelProfile("const", "emulation", 40.0, 1e-9, 50.0, 0.0, rate / 2.0, 60.0, max(delay_ms - 2.0, 0.0), seed=1)
    vals = [simulate(SimParams(hw, configs, mode=cfg_name, profile=prof, duration_s=duration, seed=k,
                               release_extra_ms=release_extra_ms))["on_time_fps_per_uav"]
            for k in range(seeds)]
    return float(np.mean(vals)), hw.onboard_ms(configs[cfg_name])


def main(duration, rates, delay_ms, t_full, device):
    from evaluation.gen_model_survey import load_frames
    frames = load_frames("coco", 60, 640)
    rows = []
    for cfg, kind in (("k4_int8_zstd", "split"), ("jpeg_q90", "jpeg")):
        for rate in rates:
            _, onboard_ms = simulate_same(cfg, t_full, rate, delay_ms, 5.0, seeds=1)
            em = emulate(kind, onboard_ms, rate, delay_ms, duration, device, frames)
            # Same frame size as emulated; the link is held one round trip after each frame (2 x delay),
            # as the emulation waits for TCP acknowledgements before sending the next frame.
            sim_fps, _ = simulate_same(cfg, t_full, rate, delay_ms, duration, payload_bytes=em["bytes_per_frame"],
                                       release_extra_ms=2 * delay_ms)
            sim_plain, _ = simulate_same(cfg, t_full, rate, delay_ms, duration, payload_bytes=em["bytes_per_frame"])
            row = {"config": cfg, "t_full_ms": t_full, "rate_mbps": rate, "delay_ms": delay_ms, "duration_s": duration,
                   "onboard_ms": round(onboard_ms, 2), "sim_on_time_fps": round(sim_fps, 2),
                   "sim_no_ack_wait_on_time_fps": round(sim_plain, 2),
                   "emu_on_time_fps": round(em["on_time_fps"], 2), **{f"emu_{k}": v for k, v in em.items() if k != "on_time_fps"}}
            rows.append(row)
            print(json.dumps(row), flush=True)
    from validation.run_link_validation import OUT, write_csv
    path = OUT / "emulation.csv"
    old = []
    if path.exists():
        import csv
        old = [r for r in csv.DictReader(open(path)) if (r["config"], float(r["rate_mbps"])) not in
               {(r2["config"], r2["rate_mbps"]) for r2 in rows}]
    write_csv(path, old + rows, list(rows[0].keys()))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--duration", type=float, default=30.0)
    ap.add_argument("--rates", type=float, nargs="+", default=[5.0, 15.0, 40.0])
    ap.add_argument("--delay-ms", type=float, default=20.0)
    ap.add_argument("--t-full", type=float, default=180.0)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    a = ap.parse_args()
    main(a.duration, a.rates, a.delay_ms, a.t_full, a.device)
