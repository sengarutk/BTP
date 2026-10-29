#!/usr/bin/env python3
"""Hierarchical edge node (runs on the Jetson): the professor's chain Pi -> Jetson -> laptop, with a decision at
EACH tier.

The camera (adaptive2.py --paths jetson) decides per frame between its onboard models and sending the frame here,
with controller v4.1's objective (accuracy x staleness, energy price, heat guard, freshness price). This node then
decides, per frame, between
  local    detect on the Jetson GPU (YOLOv8s VisDrone, at the frame's input size), or
  forward  send the frame over the edge drone's own link to the ground station, where a laptop worker runs YOLOv8m
           VisDrone (YOLOv8s for frames smaller than 640 px), and pass the result back to the camera,
by the same kind of value the camera uses:
  value(option) = acc(option) / acc_ref x rho(L(option)) - mu_e x E(option) - heat penalty
  acc       VisDrone accuracy of the model at the frame's size and JPEG quality (variant_accuracy_visdrone_ft.json)
  L         expected delay from now: local = wait for the GPU + measured inference time; forward = measured
            per-KB transfer time of this node's ground link x frame size + the laptop's reported compute time
  rho       staleness decay of forecaster v2 (staleness_decay_forecast_v2.json), the camera's curve
  E         edge-drone energy: measured inference joules (energy_constants.json) or radio-transmit joules
  mu_e      a fixed energy weight (J -> value units), --edge-mu
  heat      local inference loses value at or above --heat-c (Jetson temperature, max of its thermal zones)
Rules: never forward over a ground link that is down or stalled (no reply within --stall-s: backed off --backoff-s);
one frame at a time on the GPU and one in flight on the ground link; a newer frame replaces a waiting older one.
The camera's probes are answered here (they measure the camera -> Jetson hop). Its "edge_impair" header carries the
current phase's ground-link condition, applied with netem to this node's ground traffic (needs root).
Every decision, the ground-link estimates, power and temperature are logged to --log (JSON, written at the end).
usage (root): edge_node.py --camera CAM_IP:48102 [--listen 48104] [--wlan bat0] --log results/edge_<label>.json
A laptop worker connects to --listen (adaptive.py worker --camera <jetson>:48104 --weights yolov8s_visdrone.pt,
yolov8m_visdrone.pt).
"""
import argparse
import json
import socket
import subprocess
import threading
import time

import cv2
import numpy as np
import torch

from hwbench import fast_nms, load_model
from pipeline_node import recv_msg, send_msg

T0 = time.time()


def now_ms():
    return (time.time() - T0) * 1e3


class Ground:
    """This node's link to the ground station: a laptop worker connects here; at most one frame in flight."""

    def __init__(self, port, stall_s, backoff_s, on_result):
        self.sock, self.lock = None, threading.Lock()
        self.inflight = None                    # (id, t_send, nbytes, camera header)
        self.ms_per_kb, self.laptop_ms = 2.0, 25.0   # learned online (priors: ~4 Mbit/s, YOLOv8m on the laptop)
        self.bad_until, self.stall_s, self.backoff_s = 0.0, stall_s, backoff_s
        self.on_result, self.events = on_result, []
        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", port))
        srv.listen(1)
        threading.Thread(target=self._accept, args=(srv,), daemon=True).start()
        threading.Thread(target=self._watch, daemon=True).start()

    def up(self):
        return self.sock is not None and time.time() >= self.bad_until

    def free(self):
        return self.up() and self.inflight is None

    def _accept(self, srv):
        while True:
            s, _ = srv.accept()
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            old, self.sock = self.sock, s
            self.inflight = None
            if old is not None:
                try:
                    old.close()
                except OSError:
                    pass
            self.events.append((round(now_ms()), "ground connected"))
            threading.Thread(target=self._recv, args=(s,), daemon=True).start()

    def _recv(self, s):
        while True:
            try:
                h, blobs = recv_msg(s)
            except (ConnectionError, OSError, ValueError):
                if self.sock is s:
                    self.sock, self.inflight = None, None
                    self.events.append((round(now_ms()), "ground lost"))
                return
            inf = self.inflight
            if h.get("probe"):
                if inf is not None and inf[0] == "probe":
                    rt = (time.time() - inf[1]) * 1e3
                    self.ms_per_kb = 0.7 * self.ms_per_kb + 0.3 * rt / (inf[2] / 1e3)
                    self.inflight = None
                continue
            if inf is None or inf[0] != h.get("id"):
                continue                        # a reply after a stall was declared: dropped
            rt = (time.time() - inf[1]) * 1e3
            rem = float(h.get("remote_ms", self.laptop_ms))
            self.laptop_ms = 0.8 * self.laptop_ms + 0.2 * rem
            self.ms_per_kb = 0.7 * self.ms_per_kb + 0.3 * max(rt - rem, 1.0) / (inf[2] / 1e3)
            self.inflight = None
            self.on_result(h, blobs, inf[3])

    def _watch(self):
        """Stall rule: no reply within stall_s -> the link is treated as down for backoff_s; probe when idle."""
        last_probe = 0.0
        while True:
            time.sleep(0.05)
            inf = self.inflight
            if inf is not None and time.time() - inf[1] > self.stall_s:
                self.inflight = None
                self.bad_until = time.time() + self.backoff_s
                self.ms_per_kb = max(self.ms_per_kb, 1e3 * self.stall_s / max(inf[2] / 1e3, 1.0))
                self.events.append((round(now_ms()), f"ground stalled ({inf[0]})"))
            elif inf is None and self.sock is not None and time.time() - last_probe > 1.0:
                last_probe = time.time()
                self.send({"probe": True, "id": -1, "t_cap": 0.0, "t_send": time.time()}, [b"\0" * 16000], "probe", None)

    def send(self, h, blobs, fid, cam_h):
        """Mark the frame in flight and send it from its own thread: over a cut uplink the send can block, and it
        must never block the decision loop (local detection goes on); the stall rule then frees the slot."""
        s = self.sock
        if s is None:
            return False
        self.inflight = (fid, time.time(), sum(len(b) for b in blobs), cam_h)

        def run():
            try:
                send_msg(s, h, blobs, self.lock)
            except OSError:
                if self.inflight is not None and self.inflight[0] == fid:
                    self.inflight = None
        threading.Thread(target=run, daemon=True).start()
        return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--camera", required=True)
    ap.add_argument("--listen", type=int, default=48104)
    ap.add_argument("--wlan", default="bat0")
    ap.add_argument("--weights", default="yolov8s_visdrone.pt")
    ap.add_argument("--acc", default="variant_accuracy_visdrone_ft.json")
    ap.add_argument("--decay", default="staleness_decay_forecast_v2.json")
    ap.add_argument("--energy-constants", default="energy_constants.json")
    ap.add_argument("--edge-mu", type=float, default=0.5, help="value units per joule of edge-drone energy")
    ap.add_argument("--heat-c", type=float, default=80.0)
    ap.add_argument("--stall-s", type=float, default=1.5)
    ap.add_argument("--backoff-s", type=float, default=3.0)
    ap.add_argument("--log", required=True)
    a = ap.parse_args()
    dev = torch.device("cuda")
    model = load_model(a.weights, dev, True)
    with torch.inference_mode():
        for sz in (640, 480, 320):
            for _ in range(3):            # model AND NMS: NMS's first call takes seconds (found in the mesh smoke test)
                o = model(torch.zeros(1, 3, sz, sz, device=dev, dtype=torch.float16))
                fast_nms(o[0] if isinstance(o, (list, tuple)) else o, 0.01, 0.45, 100)
        torch.cuda.synchronize()
    acc_tab = json.load(open(a.acc))
    dc = json.load(open(a.decay))
    lag, rat = np.array(dc["lag_ms"], float), np.array(dc["ratio"], float)
    rho = lambda ms: float(np.interp(ms, lag, rat))  # noqa: E731
    ec = json.load(open(a.energy_constants)).get("jetson", {})
    infer_j, infer_ms = ec.get("infer_j", {}), dict(ec.get("infer_ms", {}))
    tx = ec.get("radio_tx_w", {"a": 0.07, "b_per_mbps": 0.003})
    ref = acc_tab["yolov8s_visdrone_640_raw"]
    try:
        from adaptive import _pw_reader
        pw = _pw_reader("jetson")
    except Exception:
        pw = None
    zones = [f"/sys/devices/virtual/thermal/thermal_zone{i}/temp" for i in range(10)]

    def temp_c():
        v = []
        for z in zones:
            try:
                v.append(int(open(z).read()) / 1e3)
            except OSError:
                pass
        return max(v) if v else float("nan")

    def acc(model_name, res, q):
        return acc_tab.get(f"{model_name}_visdrone_{res}_q{q}", acc_tab.get(f"yolov8s_visdrone_{res}_q{q}", ref))

    cam = {"sock": None, "lock": threading.Lock()}
    log = {"decisions": [], "env": [], "args": vars(a)}
    st = {"gpu_busy_until": 0.0, "pending": None, "impair": None, "bye": False}
    cv = threading.Condition()

    def to_camera(h, blobs):
        s = cam["sock"]
        if s is not None:
            try:
                send_msg(s, h, blobs, cam["lock"])
            except OSError:
                pass

    def on_ground_result(h, blobs, cam_h):
        """A forwarded frame's result from the laptop, passed back to the camera."""
        out = {"id": cam_h["id"], "remote_ms": (time.time() - cam_h["_t_recv"]) * 1e3, "ndet": h.get("ndet"),
               "model": cam_h.get("model", "yolov8s"), "where": "laptop", "served": h.get("model"),
               "board_w": pw() if pw else None}
        to_camera(out, blobs if cam_h.get("return_dets") else [])
        with cv:
            cv.notify()

    ground = Ground(a.listen, a.stall_s, a.backoff_s, on_ground_result)

    def apply_impair(args):
        """The phase's condition on this node's own ground link (netem on its traffic from port --listen)."""
        if args == st["impair"]:
            return
        st["impair"] = args
        tc = lambda c: subprocess.run(["tc"] + c.split(), capture_output=True)  # noqa: E731
        tc(f"qdisc del dev {a.wlan} root")
        if args:
            tc(f"qdisc add dev {a.wlan} root handle 1: prio bands 4 priomap 3 3 3 3 3 3 3 3 3 3 3 3 3 3 3 3")
            tc(f"qdisc add dev {a.wlan} parent 1:1 handle 10: netem {args}")
            tc(f"filter add dev {a.wlan} parent 1: protocol ip prio 1 u32 match ip sport {a.listen} 0xffff flowid 1:1")
        ground.events.append((round(now_ms()), f"uplink impair '{args}'"))

    def local_job(h, blobs):
        """Detect on the Jetson GPU; the result goes straight back to the camera."""
        t0 = time.time()
        img = cv2.imdecode(np.frombuffer(blobs[0], np.uint8), cv2.IMREAD_COLOR)
        with torch.inference_mode():
            x = torch.from_numpy(np.ascontiguousarray(img[..., ::-1].transpose(2, 0, 1))).to(dev).half() / 255.0
            o = model(x.unsqueeze(0))
            det = fast_nms(o[0] if isinstance(o, (list, tuple)) else o, h.get("conf", 0.25), 0.45, 100)
            torch.cuda.synchronize()
        ms = (time.time() - t0) * 1e3
        key = f"s{h.get('res', 640)}"
        infer_ms[key] = 0.8 * infer_ms.get(key, ms) + 0.2 * ms
        out = {"id": h["id"], "remote_ms": (time.time() - h["_t_recv"]) * 1e3, "ndet": int(det.shape[0]),
               "model": h.get("model", "yolov8s"), "where": "jetson", "served": "yolov8s", "board_w": pw() if pw else None}
        to_camera(out, [det.float().cpu().numpy().tobytes()] if h.get("return_dets") else [])
        with cv:
            st["gpu_busy_until"] = 0.0
            cv.notify()

    def scheduler():
        """Decide for the newest waiting frame as soon as an option is free."""
        while True:
            with cv:
                while st["pending"] is None:
                    cv.wait(0.05)
                h, blobs = st["pending"]
                res, q = int(h.get("res", 640)), int(h.get("q", 90))
                nb = sum(len(b) for b in blobs)
                gpu_free = st["gpu_busy_until"] == 0.0
                wait_ms = 0.0 if gpu_free else max(0.0, (st["gpu_busy_until"] - time.time()) * 1e3)
                l_local = wait_ms + infer_ms.get(f"s{res}", 30.0)
                fwd_model = "yolov8m" if res == 640 else "yolov8s"
                l_fwd = ground.ms_per_kb * nb / 1e3 + ground.laptop_ms
                e_local = infer_j.get(f"s{res}", 0.16)
                mbps = 8.0 / max(ground.ms_per_kb, 1e-3)
                e_fwd = (tx["a"] + tx["b_per_mbps"] * mbps) * ground.ms_per_kb * nb / 1e6
                t = temp_c()
                heat = 0.5 if t == t and t >= a.heat_c else 1.0
                v_local = acc("yolov8s", res, q) / ref * rho(l_local) * heat - a.edge_mu * e_local
                v_fwd = acc(fwd_model, res, q) / ref * rho(l_fwd) - a.edge_mu * e_fwd if ground.free() else -1e9
                if v_fwd > v_local:
                    choice = "laptop"
                elif gpu_free:
                    choice = "jetson"
                else:
                    cv.wait(0.005)              # the GPU is the better option: wait for it (a newer frame may arrive)
                    continue
                st["pending"] = None
                log["decisions"].append([h["id"], choice, round(now_ms()), round(l_local, 1), round(l_fwd, 1),
                                         round(v_local, 4), round(v_fwd, 4) if v_fwd > -1e8 else None, nb])
                if choice == "jetson":
                    st["gpu_busy_until"] = time.time() + l_local / 1e3
            if choice == "jetson":
                threading.Thread(target=local_job, args=(h, blobs), daemon=True).start()
            else:
                fh = {k: v for k, v in h.items() if not k.startswith("_") and k != "edge_impair"}
                fh["model"] = fwd_model
                if not ground.send(fh, blobs, h["id"], h):
                    with cv:
                        st["pending"] = st["pending"] or (h, blobs)

    def env_logger():
        while not st["bye"]:
            log["env"].append([round(now_ms()), pw() if pw else None, temp_c(), round(ground.ms_per_kb, 3),
                               round(ground.laptop_ms, 1), ground.up()])
            time.sleep(1.0)

    threading.Thread(target=scheduler, daemon=True).start()
    threading.Thread(target=env_logger, daemon=True).start()
    host, port = a.camera.rsplit(":", 1)
    print("edge node ready", flush=True)
    while not st["bye"]:
        try:
            s = socket.create_connection((host, int(port)), timeout=1)
        except OSError:
            time.sleep(0.2)
            continue
        s.settimeout(None)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        cam["sock"] = s
        try:
            while True:
                h, blobs = recv_msg(s)
                if "edge_impair" in h:
                    apply_impair(h["edge_impair"] or "")
                if h.get("bye"):
                    st["bye"] = True
                    break
                if h.get("probe"):          # the camera measures its link to this node
                    send_msg(s, {"probe": True, "t_send": h["t_send"], "remote_ms": 0.0}, [], cam["lock"])
                    continue
                h["_t_recv"] = time.time()
                with cv:
                    st["pending"] = (h, blobs)  # newest wins
                    cv.notify()
        except (ConnectionError, OSError, ValueError):
            pass
        cam["sock"] = None
        try:
            s.close()
        except OSError:
            pass
    if ground.sock is not None:
        try:
            send_msg(ground.sock, {"bye": True}, [], ground.lock)
        except OSError:
            pass
    apply_impair("")
    d = log["decisions"]
    log["summary"] = {"frames": len(d), "jetson": sum(1 for x in d if x[1] == "jetson"),
                      "laptop": sum(1 for x in d if x[1] == "laptop"), "events": ground.events}
    json.dump(log, open(a.log, "w"))
    print(json.dumps(log["summary"]), flush=True)


if __name__ == "__main__":
    main()
