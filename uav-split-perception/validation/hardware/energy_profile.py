#!/usr/bin/env python3
"""Energy and thermal profile of a drone-carried board, for the energy model (energy_model.py).

Every state runs for --state-s seconds while board power (Pi: PMIC rails via vcgencmd pmic_read_adc; Jetson:
INA3221 VDD_IN), SoC temperature (hottest thermal zone) and CPU clock are sampled at 10 Hz. Inference states
run back to back (as an onboard engine that is always busy) and record the time per frame, so energy per
frame = (P_state - P_idle) x time per frame, and absolute power is kept too.
States
  pi:     idle; encode (letterbox + JPEG at 640 q90 / 320 q50, 30 fps); onboard n320 / s320 / s640 (3 torch
          threads, as the controller); forecaster (camera motion every frame at 30 fps + velocity update on
          100 boxes at 15 results/s); radio (JPEG-sized chunks to the laptop at 2, 5, 10 Mbit/s and as fast
          as possible; the laptop connects to --radio-port and drains); thermal (s640 back to back for
          --heat-s, then idle for --cool-s, 1 Hz log of power, temperature, clock)
  jetson: idle with clocks locked (as in the campaigns) and unlocked; inference FP16 n320, s320, s480, s640,
          m640 back to back; inference s640 paced at 15 fps (a busy edge server); radio receive (the laptop
          pushes data) and transmit at 5 Mbit/s and as fast as possible (the laptop drains); thermal (m640 back to back,
          then idle)
Output: results/energy_profile_<device>.json
"""
import argparse
import glob
import json
import os
import re
import socket
import subprocess
import threading
import time

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def read_power(kind):
    if kind == "jetson":
        for b in glob.glob("/sys/class/hwmon/hwmon*/"):
            if open(b + "name").read().strip() == "ina3221":
                return float(open(b + "in1_input").read()) / 1e3 * float(open(b + "curr1_input").read()) / 1e3
        return float("nan")
    out = subprocess.run(["vcgencmd", "pmic_read_adc"], capture_output=True, text=True).stdout
    cur, vol = {}, {}
    for line in out.splitlines():
        mm = re.match(r"\s*(\S+)_([AV]) (?:current|volt)\(\d+\)=([\d.]+)", line)
        if mm:
            (cur if mm.group(2) == "A" else vol)[mm.group(1)] = float(mm.group(3))
    return sum(cur[r] * vol[r] for r in cur if r in vol)


def read_temp():
    t = []
    for z in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
        try:
            t.append(int(open(z).read()) / 1000.0)
        except (OSError, ValueError):
            pass
    return max(t) if t else float("nan")


def read_clock():
    try:
        return int(open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq").read()) / 1000.0
    except (OSError, ValueError):
        return float("nan")


class Sampler(threading.Thread):
    def __init__(self, kind, period=0.1):
        super().__init__(daemon=True)
        self.kind, self.period, self.rows, self.on = kind, period, [], False

    def run(self):
        while True:
            if self.on:
                try:
                    self.rows.append((time.time(), read_power(self.kind), read_temp(), read_clock()))
                except Exception:
                    pass
            time.sleep(self.period)

    def window(self, fn, seconds):
        """Run fn(stop_time) while sampling; return mean power, temperature, clock and fn's result."""
        self.rows = []
        self.on = True
        res = fn(time.time() + seconds)
        self.on = False
        a = np.array([r[1:] for r in self.rows]) if self.rows else np.full((1, 3), np.nan)
        return {"power_w": float(np.nanmean(a[:, 0])), "power_sd_w": float(np.nanstd(a[:, 0])),
                "temp_c": float(np.nanmean(a[:, 1])), "temp_end_c": float(a[-1, 1]),
                "clock_mhz": float(np.nanmean(a[:, 2])), "n": len(self.rows), **(res or {})}


def frames():
    seq = json.load(open(os.path.join(HERE, "visdrone_vid_640", "sequences.json")))[0][0]
    return [cv2.imread(os.path.join(HERE, "visdrone_vid_640", seq, "%07d.jpg" % i)) for i in range(1, 61)]


def paced(stop, fps, work):
    k, t0 = 0, time.time()
    while time.time() < stop:
        work(k)
        k += 1
        time.sleep(max(0.0, t0 + k / fps - time.time()))
    return {"iterations": k}


def back_to_back(stop, work):
    ts = []
    while time.time() < stop:
        t0 = time.perf_counter()
        work(len(ts))
        ts.append((time.perf_counter() - t0) * 1e3)
    return {"frames": len(ts), "ms_per_frame": float(np.median(ts)) if ts else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", required=True, choices=["pi", "jetson"])
    ap.add_argument("--state-s", type=float, default=20.0)
    ap.add_argument("--heat-s", type=float, default=300.0)
    ap.add_argument("--cool-s", type=float, default=150.0)
    ap.add_argument("--radio-port", type=int, default=48120)
    a = ap.parse_args()
    import torch
    from hwbench import fast_nms, load_model
    from ultralytics.data.augment import LetterBox
    torch.set_num_threads(3 if a.device == "pi" else 4)
    dev = torch.device("cuda" if a.device == "jetson" else "cpu")
    half = a.device == "jetson"
    S = Sampler(a.device)
    S.start()
    imgs = frames()
    out, T = {"device": a.device, "states": {}}, a.state_s
    lb = {r: LetterBox((r, r), auto=False) for r in (640, 480, 320)}
    models = {}

    def model(name):
        if name not in models:
            models[name] = load_model(os.path.join(HERE, f"{name}.pt"), dev, half)
        return models[name]

    def infer(name, res):
        m = model(name)

        def work(k):
            im = lb[res](image=imgs[k % len(imgs)])
            x = (torch.from_numpy(np.ascontiguousarray(im[..., ::-1].transpose(2, 0, 1))).float() / 255).unsqueeze(0)
            x = x.to(dev)
            with torch.inference_mode():
                o = m(x.half() if half else x)
                fast_nms(o[0] if isinstance(o, (list, tuple)) else o, 0.01, 0.45, 100)
            if dev.type == "cuda":
                torch.cuda.synchronize()
        work(0)
        work(1)
        return work

    def state(name, fn):
        r = S.window(fn, T)
        out["states"][name] = r
        print(name, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()}, flush=True)
        json.dump(out, open(os.path.join(HERE, "results", f"energy_profile_{a.device}.json"), "w"), indent=1)

    time.sleep(5)
    if a.device == "jetson":
        state("idle_clocks_locked", lambda stop: time.sleep(max(0, stop - time.time())))
    else:
        state("idle", lambda stop: time.sleep(max(0, stop - time.time())))
    if a.device == "pi":
        for res, q in ((640, 90), (640, 50), (320, 50)):
            state(f"encode_{res}q{q}_30fps", lambda stop, res=res, q=q: paced(
                stop, 30, lambda k: cv2.imencode(".jpg", lb[res](image=imgs[k % len(imgs)]),
                                                 [cv2.IMWRITE_JPEG_QUALITY, q])))
        for name, m, res in (("n320", "yolov8n", 320), ("s320", "yolov8s", 320), ("s640", "yolov8s", 640)):
            state(f"onboard_{name}", lambda stop, w=infer(m, res): back_to_back(stop, w))
        # live forecaster: camera motion each frame + velocity update per arriving result
        from egomotion import small_grey, step
        from forecast import Forecaster
        fp = json.load(open(os.path.join(HERE, "forecast_tuning_v2.json")))["best"]["params"]
        fc = Forecaster(**fp)
        rng = np.random.default_rng(0)
        prev = {"g": None}

        def fwork(k):
            g, sc = small_grey(imgs[k % len(imgs)])
            if prev["g"] is not None:
                step(prev["g"], g, sc)
            prev["g"] = g
            if k % 2 == 0:
                xy = rng.uniform(0, 600, (100, 2))
                b = np.concatenate([xy, xy + 30, rng.uniform(0, 1, (100, 1)), rng.integers(0, 10, (100, 1))], 1)
                fc.observe(k, k / 30, "s", b.astype(np.float32))
        state("forecaster_30fps", lambda stop: paced(stop, 30, fwork))
        # radio: the laptop connects and drains
        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", a.radio_port))
        srv.listen(1)
        print("radio: waiting for the laptop", flush=True)
        c, _ = srv.accept()
        c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        chunk = os.urandom(87000)
        for mbps in (2, 5, 10, 0):
            def send(stop, mbps=mbps):
                sent, t0 = 0, time.time()
                while time.time() < stop:
                    c.sendall(chunk)
                    sent += len(chunk)
                    if mbps:
                        time.sleep(max(0.0, t0 + sent * 8 / (mbps * 1e6) - time.time()))
                return {"mbit_s": sent * 8 / 1e6 / max(1e-6, time.time() - t0)}
            state(f"radio_tx_{mbps or 'max'}mbps", send)
        c.close()
        srv.close()
        heat_model, heat_res = "yolov8s", 640
    else:
        for name, m, res in (("n320", "yolov8n", 320), ("s320", "yolov8s", 320), ("s480", "yolov8s", 480),
                             ("s640", "yolov8s", 640), ("m640", "yolov8m", 640)):
            if os.path.exists(os.path.join(HERE, f"{m}.pt")):
                state(f"infer_{name}_fp16", lambda stop, w=infer(m, res): back_to_back(stop, w))
        w = infer("yolov8s", 640)
        state("serve_s640_15fps", lambda stop: paced(stop, 15, w))
        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", a.radio_port))
        srv.listen(1)
        print("radio: waiting for the laptop", flush=True)
        c, _ = srv.accept()

        def recv(stop):
            got, t0 = 0, time.time()
            c.settimeout(1.0)
            while time.time() < stop:
                try:
                    d = c.recv(1 << 16)
                except socket.timeout:
                    continue
                if not d:
                    break
                got += len(d)
            return {"mbit_s": got * 8 / 1e6 / max(1e-6, time.time() - t0)}
        state("radio_rx_max", recv)
        c.close()
        print("radio: waiting for the laptop (transmit test)", flush=True)
        c, _ = srv.accept()
        c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        chunk = os.urandom(87000)
        for mbps in (5, 0):
            def send(stop, mbps=mbps):
                sent, t0 = 0, time.time()
                while time.time() < stop:
                    c.sendall(chunk)
                    sent += len(chunk)
                    if mbps:
                        time.sleep(max(0.0, t0 + sent * 8 / (mbps * 1e6) - time.time()))
                return {"mbit_s": sent * 8 / 1e6 / max(1e-6, time.time() - t0)}
            state(f"radio_tx_{mbps or 'max'}mbps", send)
        c.close()
        srv.close()
        heat_model, heat_res = ("yolov8m" if os.path.exists(os.path.join(HERE, "yolov8m.pt")) else "yolov8s"), 640
    # thermal: heat up under sustained inference, then cool down; 1 Hz log
    w = infer(heat_model, heat_res)
    log = []
    t0 = time.time()
    k = 0
    while time.time() - t0 < a.heat_s + a.cool_s:
        el = time.time() - t0
        if el < a.heat_s:
            w(k)
            k += 1
        else:
            time.sleep(0.2)
        if not log or time.time() - log[-1][0] - t0 >= 1.0:
            log.append((time.time() - t0, read_power(a.device), read_temp(), read_clock(), k))
    out["thermal"] = {"model": f"{heat_model}@{heat_res}", "heat_s": a.heat_s, "cool_s": a.cool_s,
                      "log_t_power_temp_clock_frames": log}
    if a.device == "pi":
        out["throttled"] = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True).stdout.strip()
    json.dump(out, open(os.path.join(HERE, "results", f"energy_profile_{a.device}.json"), "w"), indent=1)
    print("ENERGY_PROFILE_DONE", flush=True)


if __name__ == "__main__":
    main()
