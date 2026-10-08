#!/usr/bin/env python3
"""Live test of an adaptive perception controller against fixed strategies, on real hardware.

camera (Raspberry Pi 5): captures at 30 fps and, for every frame it can take, picks one action:
  onboard   YOLOv8s on the Pi CPU
  lap_j90   JPEG q90 -> laptop GPU        lap_j50  JPEG q50 -> laptop GPU
  jet_j90   JPEG q90 -> Jetson GPU        jet_j50  JPEG q50 -> Jetson GPU
  lap_k1    layers 0-1 on the Pi, INT8+zstd -> laptop GPU (the best split measured)
worker (laptop, Jetson): connects to the camera, finishes the model on any payload, returns detections.

Each path carries one frame at a time (newest wins). Path state is estimated online from the data
itself: goodput of every frame from send start until the socket's unacknowledged bytes reach zero
(EWMA mean and variance), while a frame is in flight its achieved rate so far (so a stalled link is
noticed within one frame), RTT and remote compute time from the returned results, and a 64 KB probe
once per second on each path the controller is not using (to notice recovery).

Controller (--policy adaptive), every frame:
  U(a) = fps(a) * (p_on(a) + eps) * mAP(a)/mAP_fp32 - lambda(SoC) * E(a) * fps(a)
  offload: t = t_edge + bytes/r + t_remote + rtt;  p_on = Phi((r - B_req)/sigma),
           B_req = bytes / (D - t_edge - t_remote - rtt)   (the paper's uncertainty-aware rule)
           fps = min(camera, frame-quantised 1/t_edge, 1/(bytes/r + rtt), 1/t_remote)
  onboard: t = measured Pi time (EWMA, so thermal throttling is tracked); p_on = 1 if t <= D
  eps = 0.05 keeps late results above none (graceful degradation when nothing meets D);
  lambda(SoC) = lambda0 * (1 + (0.15/SoC)^2); E = Pi compute and radio energy per frame (measured powers);
  switch only if the best action beats the current one by more than 5 % (hysteresis).
Fixed policies (--policy lap_j90 etc.) always take that action.

Network scenario (--scenario): phases applied with tc netem on the Pi's Wi-Fi to the data ports
only (per path), each --phase-s seconds; the simulated battery SoC is set per phase.
Output: JSON with every frame (action, phase, latency) and per-phase metrics.
"""

import argparse
import json
import math
import os
import socket
import statistics
import subprocess
import threading
import time

import numpy as np
import torch

from hwbench import fast_nms, live_set, load_model, run_segment
from pipeline_node import CCTX, DCTX, Slot, recv_msg, send_msg  # noqa: F401

ACC = {"onboard": 0.4440, "lap_j90": 0.4407, "jet_j90": 0.4407, "lap_j50": 0.4092, "jet_j50": 0.4092,
       "lap_k1": 0.4439}
ACC0 = 0.4440
PATH_OF = {"lap_j90": "laptop", "lap_j50": "laptop", "lap_k1": "laptop", "jet_j90": "jetson", "jet_j50": "jetson"}
PORT = {"laptop": 48101, "jetson": 48102}
P_COMPUTE_W = 2.7      # Pi compute rails, active - idle (measured, docs/hardware_results.md)
P_RADIO_W = 0.31       # Pi Wi-Fi rail while transmitting, minus idle (measured)

SCENARIOS = {
    # (name, {path: netem args or None}, battery SoC)
    "mission": [("good", {}, 0.90),
                ("ground_congested", {"laptop": "rate 3mbit limit 50"}, 0.80),
                ("ground_blackout", {"laptop": "loss 100%"}, 0.70),
                ("both_degraded", {"laptop": "rate 2mbit limit 50", "jetson": "rate 1.5mbit limit 50"}, 0.50),
                ("total_blackout", {"laptop": "loss 100%", "jetson": "loss 100%"}, 0.30),
                ("recovered_low_battery", {}, 0.12)],
    "none": [("good", {}, 0.90)],
}


def tc(args):
    subprocess.run(["tc"] + args.split(), check=False, capture_output=True)


def tc_setup(dev):
    tc(f"qdisc del dev {dev} root")
    tc(f"qdisc add dev {dev} root handle 1: prio bands 4 priomap 3 3 3 3 3 3 3 3 3 3 3 3 3 3 3 3")
    for band, path in ((1, "laptop"), (2, "jetson")):
        tc(f"qdisc add dev {dev} parent 1:{band} handle {band}0: netem")
        tc(f"filter add dev {dev} parent 1: protocol ip prio 1 u32 match ip sport {PORT[path]} 0xffff flowid 1:{band}")


def tc_phase(dev, impair):
    for band, path in ((1, "laptop"), (2, "jetson")):
        tc(f"qdisc change dev {dev} parent 1:{band} handle {band}0: netem " + (impair.get(path) or ""))


def tc_teardown(dev):
    tc(f"qdisc del dev {dev} root")


def outq(sock):
    import fcntl
    import struct
    import termios
    try:
        return struct.unpack("i", fcntl.ioctl(sock.fileno(), termios.TIOCOUTQ, b"\0\0\0\0"))[0]
    except (OSError, ValueError):       # closed socket (fd -1): treated as a failed link by callers
        return -1


class Path:
    """One camera->worker link. A frame stuck for more than stall_s closes the connection; the
    worker reconnects (a fresh TCP connection does not inherit the retransmission back-off)."""

    def __init__(self, name, server, prior_mbps, prior_remote_ms, results, log_lock, stall_s):
        self.name, self.server, self.slot, self.stall_s = name, server, Slot(), stall_s
        self.sock, self.gen = None, 0
        self.lock = threading.Lock()
        self.rate, self.var = prior_mbps, (0.3 * prior_mbps) ** 2
        self.last_good = prior_mbps
        self.remote_ms, self.rtt_ms = prior_remote_ms, 5.0
        self.remote_by_model, self.remote_t = {}, {}

        self.inflight = None              # (t_start, nbytes)
        self.results, self.log_lock = results, log_lock
        self.samples, self.events = [], []
        self.connected = threading.Event()
        threading.Thread(target=self._acceptor, daemon=True).start()
        threading.Thread(target=self._sender, daemon=True).start()

    def remote_est(self, model, prior_ms, hold_s=1.0, tau_s=2.0):
        """Remote compute estimate; one not refreshed for more than hold_s relaxes toward the measured prior
        (otherwise a server that looked slow once, e.g. during warm-up, would never be tried again)."""
        if model not in self.remote_by_model:
            return prior_ms
        age = time.time() - self.remote_t.get(model, 0.0)
        w = math.exp(-max(0.0, age - hold_s) / tau_s)
        return prior_ms + (self.remote_by_model[model] - prior_ms) * w

    def _acceptor(self):
        while True:
            try:
                s, _ = self.server.accept()
            except OSError:
                return
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            old = self.sock
            self.gen += 1
            self.sock = s
            if old is not None:
                try:
                    old.close()
                except OSError:
                    pass
            # optimistic restart from the last good estimate; the next frames correct it
            self.rate = max(self.rate, 0.5 * self.last_good)
            self.events.append((time.time(), "connected"))
            self.connected.set()
            threading.Thread(target=self._receiver, args=(s,), daemon=True).start()

    def drop(self, why):
        s, self.sock = self.sock, None
        self.inflight = None
        self.rate = 1e-3
        self.events.append((time.time(), why))
        if s is not None:
            try:
                s.shutdown(socket.SHUT_RDWR)
                s.close()
            except OSError:
                pass

    def _update(self, mbps):
        a = 0.15
        d = mbps - self.rate
        self.rate += a * d
        self.var = (1 - a) * (self.var + a * d * d)

    def _sender(self):
        while True:
            h, blobs = self.slot.get()
            if h is None:
                return
            s = self.sock
            if s is None:
                continue                       # link down: the frame is lost
            n = sum(len(b) for b in blobs)
            t0 = time.perf_counter()
            self.inflight = (t0, n)
            h["t_send"] = t0
            try:
                s.settimeout(self.stall_s)
                send_msg(s, h, blobs, self.lock)
                s.settimeout(None)
                # stalled = no newly acknowledged bytes for stall_s (independent of the frame size)
                last_q, last_prog = outq(s), time.perf_counter()
                if last_q < 0:
                    raise OSError("socket closed")
                while last_q > 0:
                    time.sleep(0.0005)
                    q = outq(s)
                    if q < 0:
                        raise OSError("socket closed")
                    if q < last_q:
                        last_q, last_prog = q, time.perf_counter()
                    elif time.perf_counter() - last_prog > self.stall_s:
                        raise TimeoutError
            except (OSError, TimeoutError, ValueError):
                if self.sock is s:
                    self.drop("stalled")
                self.inflight = None
                continue
            except Exception as e:              # never let the sender thread die
                self.events.append((time.time(), f"sender_error:{type(e).__name__}"))
                self.inflight = None
                continue
            dt = time.perf_counter() - t0
            self.inflight = None
            if n > 20000:
                # bandwidth part of the transfer: the fixed per-frame latency (~RTT) is tracked separately
                mb = n * 8 / (max(dt - self.rtt_ms / 1e3, 0.3 * dt) * 1e6)
                self._update(mb)
                self.last_good = mb if mb > 0.5 else self.last_good
                self.samples.append((time.time(), mb))

    def _receiver(self, s):
        while True:
            try:
                h, blobs = recv_msg(s)
            except (ConnectionError, OSError):
                return
            now = time.perf_counter()
            if blobs and getattr(self, "dets", None) is not None and not h.get("probe"):
                self.dets[h["id"]] = blobs[0]          # detections (n x 6 float32, input-tensor coordinates)
            if h.get("probe"):
                self.rtt_ms = 0.8 * self.rtt_ms + 0.2 * max(0.5, (now - h["t_send"]) * 1e3 - h.get("remote_ms", 0))
                continue
            self.remote_ms = 0.8 * self.remote_ms + 0.2 * h["remote_ms"]
            m = h.get("model", "yolov8s")
            self.remote_by_model[m] = 0.8 * self.remote_by_model.get(m, h["remote_ms"]) + 0.2 * h["remote_ms"]
            self.remote_t[m] = time.time()
            with self.log_lock:
                self.results[h["id"]] = now

    def est_rate(self):
        """Mean and sigma of goodput (Mbit/s); a frame in flight longer than expected lowers it."""
        r, s = self.rate, math.sqrt(max(self.var, 1e-6))
        inf = self.inflight
        if inf is not None:
            t0, n = inf
            el = time.perf_counter() - t0
            if el > 0.05:
                sent = max(0, n - max(outq(self.sock), 0)) if self.sock is not None else 0
                achieved = sent * 8 / (el * 1e6)
                if el > max(3 * n * 8 / (r * 1e6), 0.3):      # far slower than the estimate says
                    r = min(r, achieved)
        return max(r, 1e-3), max(s, 0.1 * r)

    def probe(self, nbytes=65536):
        self.slot.put(({"probe": True, "id": -1, "t_cap": 0.0}, [b"\0" * nbytes]))


def phi(x):
    return 0.5 * math.erfc(-x / math.sqrt(2))


def camera(a):
    torch.set_num_threads(4)
    from ultralytics.data.augment import LetterBox
    try:
        from ultralytics.utils.nms import non_max_suppression
    except ImportError:
        from ultralytics.utils.ops import non_max_suppression
    import cv2
    model = load_model(a.weights, torch.device("cpu"), False)
    layers = model.model
    lb = LetterBox((640, 640), auto=False)
    frames = [cv2.imread(f) for f in sorted(__import__("glob").glob(os.path.join(a.images, "*.jpg")))]

    def prep(img):
        im = lb(image=img)
        return (torch.from_numpy(np.ascontiguousarray(im[..., ::-1].transpose(2, 0, 1))).float() / 255.0).unsqueeze(0), im

    with torch.inference_mode():
        x0, _ = prep(frames[0])
        model(x0)

    # accept both workers
    results, log_lock, paths = {}, threading.Lock(), {}
    priors = {"laptop": (20.0, 15.0), "jetson": (12.0, 40.0)}
    servers = {}
    for p in ("laptop", "jetson"):
        ls = socket.socket()
        ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        ls.bind(("0.0.0.0", PORT[p]))
        ls.listen(1)
        servers[p] = ls
    for p in ("laptop", "jetson"):
        paths[p] = Path(p, servers[p], *priors[p], results, log_lock, a.stall_s)
    for p in paths.values():
        p.connected.wait()
    print("workers connected", flush=True)

    phases = SCENARIOS[a.scenario]
    dev = a.wlan
    if a.scenario != "none":
        tc_setup(dev)
    D = a.deadline
    period = 1.0 / a.fps
    # priors from the per-device measurements (docs/hardware_results.md); updated online
    t_edge = {"onboard": 650.0, "j90": 8.0, "j50": 7.0, "k1": 95.0}
    nbytes = {"j90": 86000.0, "j50": 36000.0, "k1": 437000.0}
    current = a.policy if a.policy != "adaptive" else "lap_j90"
    log, decisions, switches = [], [], 0

    def utility(act, soc):
        lam = a.lambda0 * (1 + (0.15 / max(soc, 0.01)) ** 2)
        if act == "onboard":
            t = t_edge["onboard"]
            fps = 1000.0 / (math.ceil(t / (1000 * period) - 1e-9) * 1000 * period)
            p_on = 1.0 if t <= D else 0.0
            p_late = 1.0 if t <= a.late_ms else 0.0
            e = P_COMPUTE_W * t / 1e3
            return fps * (p_on + a.late_value * (p_late - p_on)) * ACC[act] / ACC0 - lam * e * fps, t, p_on
        kind = act.split("_")[1]
        p = paths[PATH_OF[act]]
        if p.sock is None:
            return -1.0, float("inf"), 0.0
        r, s = p.est_rate()
        b = nbytes[kind]
        te = t_edge[kind]
        tnet = b * 8 / (r * 1e3)
        t = te + tnet + p.remote_ms + p.rtt_ms
        budget = D - te - p.remote_ms - p.rtt_ms
        p_on = phi((r - b * 8 / (budget * 1e3)) / s) if budget > 0 else 0.0
        budget_l = a.late_ms - te - p.remote_ms - p.rtt_ms
        p_late = phi((r - b * 8 / (budget_l * 1e3)) / s) if budget_l > 0 else 0.0
        fps = min(a.fps, 1000.0 / (math.ceil(te / (1000 * period) - 1e-9) * 1000 * period),
                  1000.0 / max(tnet + p.rtt_ms, 1e-3), 1000.0 / max(p.remote_ms, 1e-3))
        e = P_COMPUTE_W * te / 1e3 + P_RADIO_W * tnet / 1e3
        return fps * (p_on + a.late_value * max(0.0, p_late - p_on)) * ACC[act] / ACC0 - lam * e * fps, t, p_on

    t_start = time.perf_counter() + 1.0
    total = len(phases) * a.phase_s
    cur_phase = -1
    last_switch = -1e9
    last_probe = {p: 0.0 for p in paths}
    try:
        while True:
            now = time.perf_counter()
            el = now - t_start
            if el >= total:
                break
            if el < 0:
                time.sleep(-el)
                continue
            ph = int(el // a.phase_s)
            if ph != cur_phase:
                cur_phase = ph
                if a.scenario != "none":
                    tc_phase(dev, phases[ph][1])
                print("phase", phases[ph][0], flush=True)
            soc = phases[ph][2]
            tick = int(el / period)
            cap_t = t_start + tick * period
            img = frames[tick % len(frames)]
            # decide
            if a.policy == "adaptive":
                scores = {act: utility(act, soc) for act in ACC}
                best = max(scores, key=lambda k: scores[k][0])
                cur_u = scores[current][0]
                cur_path = paths.get(PATH_OF.get(current, ""), None)
                emergency = cur_u <= 0.0 or (cur_path is not None and cur_path.sock is None)
                if best != current and scores[best][0] > cur_u + abs(cur_u) * a.hysteresis + 1e-9 \
                        and (emergency or el - last_switch >= a.dwell_s):
                    current = best
                    switches += 1
                    last_switch = el
                decisions.append({"t": round(el, 3), "phase": phases[ph][0], "chosen": current,
                                  "u": {k: round(v[0], 3) for k, v in scores.items()},
                                  "rate": {p: round(paths[p].est_rate()[0], 2) for p in paths}})
                # probe unused paths about once a second (detects recovery)
                for p in paths:
                    used = current in PATH_OF and PATH_OF[current] == p
                    if not used and paths[p].sock is not None and paths[p].inflight is None \
                            and time.perf_counter() - last_probe[p] > 0.8:
                        paths[p].probe()
                        last_probe[p] = time.perf_counter()
            else:
                # fixed policies: 1 KB keepalive on the paths they do not use
                for p in paths:
                    used = current in PATH_OF and PATH_OF[current] == p
                    if not used and paths[p].sock is not None and paths[p].inflight is None \
                            and time.perf_counter() - last_probe[p] > 0.8:
                        paths[p].probe(1024)
                        last_probe[p] = time.perf_counter()
            act = current
            rec = {"id": tick, "t_cap": cap_t, "phase": phases[ph][0], "action": act, "soc": soc}
            t0 = time.perf_counter()
            with torch.inference_mode():
                if act == "onboard":
                    x, _ = prep(img)
                    o = model(x)
                    non_max_suppression(o[0] if isinstance(o, (list, tuple)) else o, 0.25, 0.45)
                    done = time.perf_counter()
                    t_edge["onboard"] = 0.7 * t_edge["onboard"] + 0.3 * (done - t0) * 1e3
                    rec["t_done"] = done
                else:
                    kind = act.split("_")[1]
                    x, im = prep(img)
                    if kind in ("j90", "j50"):
                        ok, buf = cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, 90 if kind == "j90" else 50])
                        metas, blobs = [{"k": -1, "jpeg": True}], [buf.tobytes()]
                    else:
                        st = run_segment(layers, {-1: x}, -1, 1)
                        metas, blobs = [], []
                        for j in live_set(layers, 1):
                            t = st[j]
                            sc = (t.abs().max().float() / 127.0).clamp_min(1e-12)
                            q = torch.round(t / sc).clamp_(-127, 127).to(torch.int8).numpy()
                            metas.append({"k": j, "shape": list(q.shape), "s": float(sc), "dt": "i8"})
                            blobs.append(CCTX.compress(q.tobytes()))
                    te = (time.perf_counter() - t0) * 1e3
                    t_edge[kind] = 0.8 * t_edge[kind] + 0.2 * te
                    nbytes[kind] = 0.8 * nbytes[kind] + 0.2 * sum(map(len, blobs))
                    paths[PATH_OF[act]].slot.put(({"id": tick, "t_cap": cap_t, "cut": -1 if kind != "k1" else 1,
                                                   "metas": metas}, blobs))
                    rec["bytes"] = sum(map(len, blobs))
            log.append(rec)
            nxt = t_start + (int((time.perf_counter() - t_start) / period) + 1) * period
            time.sleep(max(0.0, nxt - time.perf_counter()))
        time.sleep(3.0)
    finally:
        if a.scenario != "none":
            tc_teardown(dev)
    for p in paths.values():
        p.slot.put((None, None))
    for srv in servers.values():
        srv.close()
    for p in paths.values():
        if p.sock is not None:
            try:
                send_msg(p.sock, {"bye": True}, [], p.lock)
            except OSError:
                pass
    # results
    for rec in log:
        if "t_done" not in rec and rec["id"] in results:
            rec["t_done"] = results[rec["id"]]
        rec["lat_ms"] = (rec["t_done"] - rec["t_cap"]) * 1e3 if "t_done" in rec else None
    per_phase = {}
    for name, _, _ in phases:
        rs = [r for r in log if r["phase"] == name]
        lat = [r["lat_ms"] for r in rs if r["lat_ms"] is not None]
        acts = {}
        for r in rs:
            acts[r["action"]] = acts.get(r["action"], 0) + 1
        energy = sum(P_COMPUTE_W * (r["lat_ms"] if r["action"] == "onboard" and r["lat_ms"] else 0) / 1e3 for r in rs)
        per_phase[name] = {"frames_taken": len(rs), "delivered_fps": len(lat) / a.phase_s,
                           "on_time_fps": sum(l <= D for l in lat) / a.phase_s,
                           "within_1s_fps": sum(l <= 1000 for l in lat) / a.phase_s,
                           "acc_weighted_on_time": sum(ACC[r["action"]] / ACC0 for r in rs
                                                       if r["lat_ms"] is not None and r["lat_ms"] <= D) / a.phase_s,
                           "lat_p50_ms": statistics.median(lat) if lat else None,
                           "actions": acts, "onboard_energy_j": energy}
    out = {"policy": a.policy, "scenario": a.scenario, "phase_s": a.phase_s, "deadline_ms": D,
           "switches": switches, "per_phase": per_phase,
           "total": {k: sum(v[k] for v in per_phase.values()) / len(per_phase)
                     for k in ("delivered_fps", "on_time_fps", "within_1s_fps", "acc_weighted_on_time")},
           "rate_samples": {p: paths[p].samples for p in paths}, "link_events": {p: paths[p].events for p in paths},
           "decisions": decisions[::5],
           "frames": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items() if k not in ("t_cap", "t_done")}
                      for r in log]}
    json.dump(out, open(a.out, "w"))
    print(json.dumps({"policy": a.policy, "total": out["total"], "switches": switches,
                      "per_phase": {k: (round(v["on_time_fps"], 2), v["actions"]) for k, v in per_phase.items()}}))


def worker(a):
    dev = torch.device(a.device)
    dtype = torch.float16 if a.half else torch.float32
    from ultralytics.data.augment import LetterBox  # noqa: F401
    try:
        from ultralytics.utils.nms import non_max_suppression
    except ImportError:
        from ultralytics.utils.ops import non_max_suppression
    import cv2
    from pipeline_node import decode
    models = {os.path.basename(w)[:-3]: load_model(w, dev, a.half) for w in a.weights.split(",")}
    model = models[next(iter(models))]
    layers = models
    sync = torch.cuda.synchronize if dev.type == "cuda" else (lambda: None)

    def prep(im, letterboxed=True):
        t = torch.from_numpy(np.ascontiguousarray(im[..., ::-1].transpose(2, 0, 1))).to(dev)
        return (t.to(dtype) / 255.0).unsqueeze(0), im

    with torch.inference_mode():
        for m in models.values():
            for sz in (640, 480, 320):          # every input size a variant may use (first calls are slow)
                for _ in range(5):
                    o = m(torch.zeros(1, 3, sz, sz, device=dev, dtype=dtype))
                    fast_nms(o[0] if isinstance(o, (list, tuple)) else o, 0.01, 0.45, 100)
        if dev.type == "cuda":
            torch.cuda.synchronize()

    def serve(s):
        return _serve_conn(s, layers, dev, dtype, prep, sync, non_max_suppression)
    host, port = a.camera.rsplit(":", 1)
    n, connected_once, fails = 0, False, 0
    while True:                                   # reconnect until the camera says bye
        try:
            s = socket.create_connection((host, int(port)), timeout=1)
        except OSError:
            fails += 1
            if connected_once and fails > 60:      # ~ the camera has finished
                break
            time.sleep(0.2)
            continue
        fails, connected_once = 0, True
        s.settimeout(None)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        bye = serve(s)
        try:
            s.close()
        except OSError:
            pass
        if bye:
            break
    st = [x for x in _stage if len(x) == 4]
    med = [round(float(np.median([x[i] for x in st])), 1) for i in range(4)] if st else None
    print(json.dumps({"worker": a.label, "frames": _served[0], "stage_ms_median_dec_inf_nms_send": med}))


_served = [0]
_stage = []      # per frame: decode, inference, NMS, send (ms)


def _serve_conn(s, layers, dev, dtype, prep, sync, non_max_suppression):
    from pipeline_node import decode
    slot, lock = Slot(), threading.Lock()

    def rx():
        # the camera sends a frame or a probe at least once a second; silence means the link is dead
        s.settimeout(2.5)
        while True:
            try:
                slot.put(recv_msg(s))
            except (ConnectionError, OSError):
                slot.put((None, None))
                return

    threading.Thread(target=rx, daemon=True).start()
    while True:
        h, blobs = slot.get()
        if h is None:
            return False
        if h.get("bye"):
            return True
        if h.get("probe"):
            try:
                send_msg(s, {"probe": True, "t_send": h["t_send"], "remote_ms": 0.0}, [], lock)
            except OSError:
                return False
            continue
        t0 = time.perf_counter()
        with torch.inference_mode():
            st = decode(h["metas"], blobs, dev, dtype, prep)
            sync()
            t_dec = time.perf_counter()
            k = h["cut"]
            mname = h.get("model", "yolov8s")
            lay = (layers[mname] if mname in layers else next(iter(layers.values()))).model
            st = run_segment(lay, {j: st[j] for j in live_set(lay, k)}, k, len(lay) - 1)
            o = st[len(lay) - 1]
            sync()
            t_inf = time.perf_counter()
            det = fast_nms(o[0] if isinstance(o, (list, tuple)) else o, h.get("conf", 0.25), 0.45, 100)
            sync()
        t_nms = time.perf_counter()
        _stage.append(((t_dec - t0) * 1e3, (t_inf - t_dec) * 1e3, (t_nms - t_inf) * 1e3))
        try:
            blobs = [det.float().cpu().numpy().tobytes()] if h.get("return_dets") else []
            send_msg(s, {"id": h["id"], "remote_ms": (time.perf_counter() - t0) * 1e3, "ndet": int(det.shape[0]),
                         "model": mname}, blobs, lock)
        except OSError:
            return False
        _served[0] += 1
        _stage[-1] = _stage[-1] + ((time.perf_counter() - t_nms) * 1e3,)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("role", choices=["camera", "worker"])
    ap.add_argument("--policy", default="adaptive", choices=["adaptive"] + list(ACC))
    ap.add_argument("--scenario", default="mission", choices=list(SCENARIOS))
    ap.add_argument("--phase-s", type=float, default=30.0)
    ap.add_argument("--deadline", type=float, default=300.0)
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--late-ms", type=float, default=1500.0, help="results later than the deadline but within this still count")
    ap.add_argument("--late-value", type=float, default=0.25, help="value of such a late result relative to an on-time one")
    ap.add_argument("--lambda0", type=float, default=0.01, help="energy weight per W of Pi perception power")
    ap.add_argument("--hysteresis", type=float, default=0.10)
    ap.add_argument("--dwell-s", type=float, default=1.0)
    ap.add_argument("--stall-s", type=float, default=1.5, help="a path whose frame is stuck this long is reconnected")
    ap.add_argument("--wlan", default="wlan0")
    ap.add_argument("--images", default="frames")
    ap.add_argument("--weights", default="yolov8s.pt")
    ap.add_argument("--camera", default="", help="HOST:PORT of the camera (worker)")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--half", action="store_true")
    ap.add_argument("--label", default="")
    ap.add_argument("--out", default="adaptive.json")
    a = ap.parse_args()
    (camera if a.role == "camera" else worker)(a)


if __name__ == "__main__":
    main()
