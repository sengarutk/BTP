#!/usr/bin/env python3
"""Adaptive multi-server perception scheduling on real hardware (controller v2).

The camera UAV (Raspberry Pi 5) has three servers that can each work on one frame at a time:
  onboard  the Pi CPU (its own thread, 3 cores), variants YOLOv8n@320, YOLOv8s@320, YOLOv8s@640
  laptop   a Wi-Fi path to the laptop GPU, variants JPEG {q90,q50} x {640,480,320} for YOLOv8s,
           and JPEG {q90,q50} @640 for YOLOv8m
  jetson   a Wi-Fi path to the Jetson GPU, variants JPEG {q90,q50} x {640,480,320} for YOLOv8s
Every camera frame (30 fps) goes to at most one server. Accuracy of every variant is the measured
COCO mAP@[.5:.95] (experiments/results/hardware/variant_accuracy.json); timings are learned online
from priors measured on the devices; paths are estimated as in adaptive.py (goodput EWMA and
variance, in-flight stall detection, probes on idle paths, reconnection after a stall).

Scheduler (A_*): for the newest frame, every idle server s proposes its best variant
    v*(s) = argmax_v  value(s, v) = (mAP_v / mAP_ref) * q(s, v) / T(s, v)
where q = P(on time) + w_late * (P(within late_ms) - P(on time)) under Gaussian goodput
uncertainty, and T = the time s stays busy with the frame (onboard: compute; path: transfer),
i.e. the rate of accuracy-weighted on-time results s adds. The frame goes to the idle server with
the highest value (if > 0).
  A_full    all servers, variant adaptation
  A_paths   the two paths; onboard only when no path has P(on time) > 0.2 (fallback)
  A_single  one server at a time (the best overall), variant adaptation
Baselines:
  static_multi        laptop s640q50, jetson s640q50, onboard n320, each idle server in turn
  fixed:<srv>:<var>   one server, one variant, always (e.g. fixed:jetson:s640q50)
Metrics per phase: on-time results/s, accuracy-weighted on-time results/s, results within 1 s,
mean age of information of the newest result (AoI), availability = share of time AoI <= deadline,
Pi perception power (compute + radio, measured powers).
"""

import argparse
import glob
import json
import math
import os
import random
import socket
import statistics
import threading
import time

import cv2
import numpy as np
import torch

from adaptive import P_COMPUTE_W, P_RADIO_W, PORT, Path, phi, tc_phase, tc_setup, tc_teardown
from hwbench import fast_nms, load_model
from pipeline_node import send_msg  # noqa: F401

REF = 0.4440  # YOLOv8s@640 FP32 mAP

ONBOARD_VARIANTS = {"n320": ("yolov8n", 320), "s320": ("yolov8s", 320), "s640": ("yolov8s", 640)}
PATH_VARIANTS = {f"s{r}q{q}": ("yolov8s", r, q) for r in (640, 480, 320) for q in (90, 50)}
LAPTOP_EXTRA = {"m640q90": ("yolov8m", 640, 90), "m640q50": ("yolov8m", 640, 50)}

# priors (measured: experiments/results/hardware/raw/variant_timing_*.json); learned online
PRIOR_ONBOARD_MS = {"n320": 80.0, "s320": 170.0, "s640": 700.0}
PRIOR_BYTES = {640: {90: 87000, 50: 35800}, 480: {90: 50100, 50: 20800}, 320: {90: 25900, 50: 11000}}
PRIOR_REMOTE_MS = {"laptop": {"yolov8s": 18.0, "yolov8m": 24.0}, "jetson": {"yolov8s": 32.0, "yolov8m": 60.0}}  # live worker stage times


def scenario_phases(name, phase_s, seed):
    """[(name, {path: netem args}, soc, duration)] ; the same list for every policy."""
    good = {}
    if name == "mission":
        return [("good", good, .9, phase_s), ("ground_congested", {"laptop": "rate 3mbit limit 50"}, .8, phase_s),
                ("ground_blackout", {"laptop": "loss 100%"}, .7, phase_s),
                ("both_degraded", {"laptop": "rate 2mbit limit 50", "jetson": "rate 1.5mbit limit 50"}, .5, phase_s),
                ("total_blackout", {"laptop": "loss 100%", "jetson": "loss 100%"}, .3, phase_s),
                ("recovered_low_battery", good, .12, phase_s)]
    if name == "mission_mirror":       # the Jetson path fails first
        return [("good", good, .9, phase_s), ("edge_congested", {"jetson": "rate 3mbit limit 50"}, .8, phase_s),
                ("edge_blackout", {"jetson": "loss 100%"}, .7, phase_s),
                ("both_degraded", {"laptop": "rate 1.5mbit limit 50", "jetson": "rate 2mbit limit 50"}, .5, phase_s),
                ("total_blackout", {"laptop": "loss 100%", "jetson": "loss 100%"}, .3, phase_s),
                ("recovered_low_battery", good, .12, phase_s)]
    if name == "random":               # each path: Markov chain over 5 states, 4 s steps, fixed seed
        states = [None, "rate 6mbit limit 50", "rate 3mbit limit 50", "rate 1.5mbit limit 50", "loss 100%"]
        rng = random.Random(seed)
        cur = {"laptop": 0, "jetson": 0}
        out, n = [], int(6 * phase_s / 4)
        for i in range(n):
            for p in cur:
                if rng.random() < 0.5:
                    cur[p] = min(4, max(0, cur[p] + rng.choice([-2, -1, 1, 2])))
            imp = {p: states[s] for p, s in cur.items() if states[s]}
            out.append((f"r{i:02d}_L{cur['laptop']}J{cur['jetson']}", imp, 0.9 - 0.75 * i / n, 4.0))
        return out
    if name == "static_good":
        return [(f"good{i}", good, .9, phase_s) for i in range(6)]
    raise ValueError(name)


class Onboard:
    """The Pi's own inference engine, in its own thread (3 torch threads), one frame at a time."""

    def __init__(self, weights_dir, threads, results, log_lock, device="cpu"):
        torch.set_num_threads(threads)
        self.dev, self.half = torch.device(device), device == "cuda"
        self.models = {k: load_model(os.path.join(weights_dir, f"{m}.pt"), self.dev, self.half)
                       for k, (m, _) in ONBOARD_VARIANTS.items()}
        from ultralytics.data.augment import LetterBox
        try:
            from ultralytics.utils.nms import non_max_suppression
        except ImportError:
            from ultralytics.utils.ops import non_max_suppression
        self.nms = non_max_suppression
        self.lb = {k: LetterBox((s, s), auto=False) for k, (_, s) in ONBOARD_VARIANTS.items()}
        self.ms = dict(PRIOR_ONBOARD_MS)
        self.conf, self.dets = 0.25, None
        self.busy = False
        self.results, self.log_lock = results, log_lock
        self.cv = threading.Condition()
        self.job = None
        with torch.inference_mode():
            for k, m in self.models.items():
                s = ONBOARD_VARIANTS[k][1]
                z = torch.zeros(1, 3, s, s, device=self.dev)
                m(z.half() if self.half else z)
        if self.dev.type == "cuda":           # a GPU camera (Jetson): time each variant instead of the Pi priors
            img = np.zeros((360, 640, 3), np.uint8)
            for k in ONBOARD_VARIANTS:
                ts = []
                for _ in range(6):
                    t0 = time.perf_counter()
                    self._infer(img, k)
                    ts.append((time.perf_counter() - t0) * 1e3)
                self.ms[k] = float(np.median(ts[1:]))
        threading.Thread(target=self._run, daemon=True).start()

    def _infer(self, img, var):
        with torch.inference_mode():
            im = self.lb[var](image=img)
            x = (torch.from_numpy(np.ascontiguousarray(im[..., ::-1].transpose(2, 0, 1))).float() / 255).unsqueeze(0)
            x = x.to(self.dev)
            o = self.models[var](x.half() if self.half else x)
            det = fast_nms(o[0] if isinstance(o, (list, tuple)) else o, self.conf, 0.45, 100)
        return det.float().cpu()

    def submit(self, fid, img, var):
        with self.cv:
            self.busy = True
            self.job = (fid, img, var)
            self.cv.notify()

    def _run(self):
        while True:
            with self.cv:
                while self.job is None:
                    self.cv.wait()
                fid, img, var = self.job
                self.job = None
            t0 = time.perf_counter()
            det = self._infer(img, var)
            done = time.perf_counter()
            if self.dets is not None:
                self.dets[fid] = det.float().numpy().tobytes()
            self.ms[var] = 0.7 * self.ms[var] + 0.3 * (done - t0) * 1e3
            with self.log_lock:
                self.results[fid] = done
            self.busy = False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--policy", required=True)
    ap.add_argument("--scenario", default="mission")
    ap.add_argument("--phase-s", type=float, default=20.0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--deadline", type=float, default=300.0)
    ap.add_argument("--late-ms", type=float, default=1000.0)
    ap.add_argument("--late-value", type=float, default=0.25)
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--onboard-threads", type=int, default=3)
    ap.add_argument("--stall-s", type=float, default=1.5)
    ap.add_argument("--wlan", default="wlan0")
    ap.add_argument("--images", default="frames")
    ap.add_argument("--vid", default="", help="VisDrone-VID folder from prepare_vid.py: stream its sequences in order "
                                              "and record every detection for streaming-AP evaluation")
    ap.add_argument("--conf", type=float, default=0.25, help="NMS confidence threshold (use a low one for AP)")
    ap.add_argument("--weights-dir", default=".")
    ap.add_argument("--acc", default="variant_accuracy.json", help="accuracy table (COCO, or VisDrone-DET for aerial)")
    ap.add_argument("--decay", default="", help="staleness_decay.json (VisDrone-VID train): enables --objective stream")
    ap.add_argument("--objective", default="rate", choices=["rate", "stream"],
                    help="rate: accuracy-weighted on-time results/s (v2); stream: expected accuracy of the held "
                         "result, accuracy x staleness decay over its holding window (v3)")
    ap.add_argument("--live-forecast", default="", help="forecast_tuning*.json: run the motion forecaster live in the "
                    "camera loop (camera motion every frame, velocities on every arriving result, forecast of the held "
                    "result every frame) and save its inputs to <out>_livefc.npz (needs --vid)")
    ap.add_argument("--paths", default="laptop,jetson", help="offload paths of this camera (a Jetson camera: laptop)")
    ap.add_argument("--onboard-device", default="cpu", help="cpu (Pi) or cuda (a Jetson as a camera, FP16)")
    ap.add_argument("--coord-port", type=int, default=0, help="listen for the swarm coordinator (coordinator.py) "
                    "on this port; it may revoke or cap this camera's use of the laptop path per window")
    ap.add_argument("--power-log", action="store_true", help="log measured board power (Pi PMIC / Jetson INA3221), "
                    "temperature and clock at 5 Hz for the whole run (results: measured energy per run)")
    ap.add_argument("--energy-aware", action="store_true", help="controller v4: value minus mu x energy per frame; mu "
                    "follows the measured power against --power-budget (dual ascent) and rises above --thermal-guard-c")
    ap.add_argument("--power-budget", type=float, default=3.0, help="sustained camera-board power budget (W)")
    ap.add_argument("--eta", type=float, default=0.1, help="dual-ascent step for mu (1/J per W-excess per s)")
    ap.add_argument("--thermal-guard-c", type=float, default=78.0)
    ap.add_argument("--energy-constants", default="energy_constants.json", help="energy_model.py constants")
    ap.add_argument("--fresh-target", type=float, default=0.0, help="controller v4.1: target share of time the drone "
                    "holds a detection younger than the deadline (e.g. 0.95); 0 = off. A second dual variable lam_F "
                    "rises when the measured share over the last --fresh-window-s falls below the target")
    ap.add_argument("--fresh-window-s", type=float, default=5.0)
    ap.add_argument("--eta-f", type=float, default=2.0, help="dual-ascent step for lam_F (per unit shortfall per s)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    acc_tab = json.load(open(a.acc))
    REF_ACC = acc_tab["yolov8s_640_raw"]
    if a.decay:
        _dc = json.load(open(a.decay))
        _lag, _rat = np.array(_dc["lag_ms"], float), np.array(_dc["ratio"], float)
    else:
        _lag, _rat = np.array([0.0, 1e9]), np.array([1.0, 1.0])

    def rho(age_ms):
        return float(np.interp(age_ms, _lag, _rat))

    def hold_quality(L, T):
        """mean staleness factor while a result of latency L is held for T ms"""
        return float(np.mean([rho(L + T * f) for f in (0.0, 0.25, 0.5, 0.75, 1.0)]))

    def acc_of(model, res, q=None):
        return acc_tab[f"{model}_{res}_{'raw' if q is None else 'q%d' % q}"]

    from ultralytics.data.augment import LetterBox
    lbs = {r: LetterBox((r, r), auto=False) for r in (640, 480, 320)}
    frame_keys = None
    if a.vid:
        seqs = json.load(open(os.path.join(a.vid, "sequences.json")))
        frame_keys = [(sq, i) for sq, n in seqs for i in range(1, n + 1)]
        frames = [cv2.imread(os.path.join(a.vid, sq, "%07d.jpg" % i)) for sq, i in frame_keys]
    else:
        frames = [cv2.imread(f) for f in sorted(glob.glob(os.path.join(a.images, "*.jpg")))]
    results, log_lock, dets = {}, threading.Lock(), {}
    onboard = Onboard(a.weights_dir, a.onboard_threads, results, log_lock, a.onboard_device)
    onboard.conf = a.conf
    if a.vid:
        onboard.dets = dets
    cv2.setNumThreads(1)

    servers, paths = {}, {}
    priors = {"laptop": (20.0, 12.0), "jetson": (12.0, 32.0)}
    for p in a.paths.split(","):
        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", PORT[p]))
        srv.listen(1)
        servers[p] = srv
        paths[p] = Path(p, srv, *priors[p], results, log_lock, a.stall_s)
        paths[p].dets = dets if a.vid else None
    for p in paths.values():
        p.connected.wait()
    remote_ms = {p: dict(PRIOR_REMOTE_MS[p]) for p in paths}
    nbytes = {(r, q): float(PRIOR_BYTES[r][q]) for r in PRIOR_BYTES for q in PRIOR_BYTES[r]}
    enc_ms = {r: {640: 3.5, 480: 2.2, 320: 1.2}[r] for r in (640, 480, 320)}
    print("workers connected", flush=True)

    D, period = a.deadline, 1.0 / a.fps
    n_active = [1]                 # servers currently able to deliver (for the holding-window estimate)
    pol = a.policy

    def path_variants(p):
        v = dict(PATH_VARIANTS)
        if p == "laptop":
            v.update(LAPTOP_EXTRA)
        return v

    coord = {"allowed": True, "share": None, "decisions": [], "reports": 0}

    def path_value(p, var, r_override=None):
        path = paths[p]
        if path.sock is None:
            return -1.0, 0.0
        if p == "laptop" and not coord["allowed"] and r_override is None:
            return -1.0, 0.0
        model, res, q = path_variants(p)[var]
        r, s = path.est_rate()
        if r_override is not None:
            r = r_override
        elif p == "laptop" and coord["share"]:
            r = min(r, coord["share"])
        b = nbytes[(res, q)]
        te, rem, rtt = enc_ms[res], remote_ms[p][model], path.rtt_ms
        tx = b * 8 / (r * 1e3)
        p_on = phi((r - b * 8 / ((D - te - rem - rtt) * 1e3)) / s) if D - te - rem - rtt > 0 else 0.0
        lb_ = a.late_ms - te - rem - rtt
        p_late = phi((r - b * 8 / (lb_ * 1e3)) / s) if lb_ > 0 else 0.0
        qv = p_on + a.late_value * max(0.0, p_late - p_on)
        busy = max(tx + rtt, 1000 * period)            # the path takes at most one frame per camera tick
        if a.objective == "stream":
            L = te + tx + rem + rtt
            T = busy / max(1, n_active[0])
            v_ = acc_of(model, res, q) / REF_ACC * hold_quality(L, T) * (p_late if p_late > 0 else 0.0)
            if a.energy_aware and r_override is None:
                v_ -= energy["mu"] * e_offload(res, q, b, r)
            if a.fresh_target > 0 and r_override is None and fresh["aoi_ms"] + L >= D:
                v_ += fresh["lam"] * p_on              # restores freshness if it arrives in time
            return v_, p_on
        return acc_of(model, res, q) / REF * qv / (busy / 1e3), p_on

    def onboard_value(var, penalize=True):
        model, res = ONBOARD_VARIANTS[var]
        t = onboard.ms[var]
        p_on = 1.0 if t <= D else 0.0
        qv = p_on + a.late_value * ((1.0 if t <= a.late_ms else 0.0) - p_on)
        busy = math.ceil(t / (1000 * period) - 1e-9) * 1000 * period
        if a.objective == "stream":
            v_ = acc_of(model, res) / REF_ACC * hold_quality(t, busy / max(1, n_active[0]))
            if a.energy_aware and penalize:
                v_ -= energy["mu"] * e_onboard(var)
            if a.fresh_target > 0 and fresh["aoi_ms"] + t >= D:
                v_ += fresh["lam"] * p_on              # the held detection will be stale before anything else lands
            return v_, p_on
        return acc_of(model, res) / REF * qv / (busy / 1e3), p_on

    def idle(srv):
        if srv == "onboard":
            return not onboard.busy
        p = paths[srv]
        return p.sock is not None and p.inflight is None and p.slot.item is None

    def best_variant(srv):
        if srv == "onboard":
            vals = {v: onboard_value(v) for v in ONBOARD_VARIANTS}
        else:
            vals = {v: path_value(srv, v) for v in path_variants(srv)}
        v = max(vals, key=lambda k: vals[k][0])
        return v, vals[v][0], vals[v][1]

    if a.coord_port and "laptop" in paths:
        rmax = {"t": [], "r": []}

        def report():
            """Value of this camera's laptop path at the full and at half the link it has seen alone recently,
            and the value of its other servers (they run in parallel with the laptop path)."""
            now = time.time()
            r, _ = paths["laptop"].est_rate()
            rmax["t"].append(now)
            rmax["r"].append(r)
            while rmax["t"] and now - rmax["t"][0] > 10.0:
                rmax["t"].pop(0)
                rmax["r"].pop(0)
            full = max(rmax["r"]) if rmax["r"] else r
            lap = lambda rate: max([path_value("laptop", v, rate)[0] for v in path_variants("laptop")] + [0.0])  # noqa
            other = sum(max(0.0, best_variant(sv)[1]) for sv in list(paths) + ["onboard"] if sv != "laptop")
            return {"t": now, "lap_full": lap(full), "lap_half": lap(full / 2), "other": other, "r": r, "r_full": full}

        def coord_server():
            srv = socket.socket()
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("0.0.0.0", a.coord_port))
            srv.listen(1)
            while True:
                c, _ = srv.accept()
                c.settimeout(3.0)
                f = c.makefile("rwb")
                try:
                    while True:
                        f.write((json.dumps(report()) + "\n").encode())
                        f.flush()
                        line = f.readline()
                        if not line:
                            break
                        d = json.loads(line)
                        coord["allowed"], coord["share"] = bool(d.get("allowed", True)), d.get("share")
                        coord["reports"] += 1
                        coord["decisions"].append((time.time(), coord["allowed"], coord["share"]))
                except (OSError, ValueError):
                    pass
                coord["allowed"], coord["share"] = True, None      # coordinator gone: decide alone
                c.close()
        threading.Thread(target=coord_server, daemon=True).start()

    # ------------------------------------------------ energy: measured constants, live power log, price mu
    board = "jetson" if a.onboard_device == "cuda" else "pi"
    ec = json.load(open(a.energy_constants))[board] if (a.energy_aware or a.power_log) and \
        os.path.exists(a.energy_constants) else None
    energy = {"mu": 0.0, "log": [], "mu_log": [], "temp": 50.0}
    fresh = {"lam": 0.0, "aoi_ms": float("inf"), "hist": [], "log": [], "last": 0.0}

    def read_board():
        import glob as _g
        import re as _re
        import subprocess as _sp
        if board == "jetson":
            for b in _g.glob("/sys/class/hwmon/hwmon*/"):
                if open(b + "name").read().strip() == "ina3221":
                    return float(open(b + "in1_input").read()) / 1e3 * float(open(b + "curr1_input").read()) / 1e3
            return float("nan")
        out_ = _sp.run(["vcgencmd", "pmic_read_adc"], capture_output=True, text=True).stdout
        cur, vol = {}, {}
        for line in out_.splitlines():
            mm = _re.match(r"\s*(\S+)_([AV]) (?:current|volt)\(\d+\)=([\d.]+)", line)
            if mm:
                (cur if mm.group(2) == "A" else vol)[mm.group(1)] = float(mm.group(3))
        return sum(cur[r] * vol[r] for r in cur if r in vol)

    def read_temp_():
        import glob as _g
        t = []
        for z in _g.glob("/sys/class/thermal/thermal_zone*/temp"):
            try:
                t.append(int(open(z).read()) / 1000.0)
            except (OSError, ValueError):
                pass
        return max(t) if t else float("nan")

    def power_logger():
        last_mu = time.time()
        while True:
            try:
                pw, tp = read_board(), read_temp_()
            except Exception:
                pw, tp = float("nan"), float("nan")
            now = time.time()
            energy["log"].append((now, pw, tp))
            energy["temp"] = tp
            if a.energy_aware and now - last_mu >= 1.0:          # dual ascent on the power budget
                recent = [x[1] for x in energy["log"] if now - x[0] <= 1.0 and x[1] == x[1]]
                if recent:
                    pbar = sum(recent) / len(recent)
                    mu = max(0.0, energy["mu"] + a.eta * (pbar - a.power_budget))
                    if tp == tp and tp >= a.thermal_guard_c:      # thermal guard: make onboard work expensive
                        mu = max(mu, 1.0)
                    energy["mu"] = mu
                    energy["mu_log"].append((now, mu, pbar, tp))
                last_mu = now
            time.sleep(0.2)
    if a.power_log or a.energy_aware:
        threading.Thread(target=power_logger, daemon=True).start()

    def e_onboard(var):
        return ec["infer_j"].get(var, 0.0) if ec else 0.0

    def e_offload(res, q, nb, r_mbps):
        if not ec:
            return 0.0
        enc = ec["encode_j"].get(f"{res}q{q}", ec["encode_j"].get("640q90", 0.0))
        tx = ec.get("radio_tx_w", {"a": 0.2, "b_per_mbps": 0.0})
        r = max(r_mbps, 0.2)
        return enc + max(0.0, tx["a"] + tx["b_per_mbps"] * r) * nb * 8 / (r * 1e6)

    phases = scenario_phases(a.scenario, a.phase_s, a.seed)
    tc_setup(a.wlan)
    t_start = time.perf_counter() + 1.0
    bounds = np.cumsum([0.0] + [ph[3] for ph in phases])
    total = bounds[-1]
    log, cur_phase, last_probe, rr = [], -1, {p: 0.0 for p in paths}, 0
    lf = None
    if a.live_forecast and a.vid:                    # live motion forecasting (forecast.py, egomotion.py)
        from egomotion import small_grey, step
        from forecast import Forecaster
        fparams = json.load(open(a.live_forecast))["best"]["params"]
        lf = {"fc": Forecaster(**fparams), "chains": {}, "prev": None, "seen": set(), "rec": {}, "held": None,
              "ego_ms": [], "obs_ms": [], "pred_ms": [], "vel": {}, "params": fparams}
        lf["fc"].chains = lf["chains"] if fparams.get("align") else None
        lens = dict((sq, n) for sq, n in seqs)

        def unlb(det, res, h, w):              # letterboxed res x res input -> h x w frame (as stream_ap.unletterbox)
            r = min(res / h, res / w)
            pw, ph_ = (res - round(w * r)) / 2, (res - round(h * r)) / 2
            d = det.copy()
            d[:, [0, 2]] = ((d[:, [0, 2]] - pw) / r).clip(0, w)
            d[:, [1, 3]] = ((d[:, [1, 3]] - ph_) / r).clip(0, h)
            return d

        def live_forecast_tick(tick, img, key):
            t0 = time.perf_counter()
            sq, i = key
            C = lf["chains"].setdefault(sq, np.full((lens[sq] + 1, 3, 3), np.nan))
            g, sc = small_grey(img)
            pv = lf["prev"]
            C[i] = step(pv[1], g, sc) @ pv[2] if pv is not None and pv[0] == sq else np.eye(3)
            lf["prev"] = (sq, g, C[i])
            lf["ego_ms"].append((time.perf_counter() - t0) * 1e3)
            # newly arrived results, in arrival order: update velocities
            while True:                         # results is filled by other threads
                try:
                    ks = list(results)
                    break
                except RuntimeError:
                    pass
            new = sorted((results[k], k) for k in ks if k not in lf["seen"] and k in dets and k in lf["rec"])
            for _, k in new:
                lf["seen"].add(k)
                r = lf["rec"][k]
                t1 = time.perf_counter()
                h, w = img.shape[:2]
                b = unlb(np.frombuffer(dets[k], np.float32).reshape(-1, 6), r["res"], h, w)
                lf["fc"].observe(k, k * period, r["frame"][0], b, fidx=r["frame"][1])
                lf["obs_ms"].append((time.perf_counter() - t1) * 1e3)
                lf["vel"][k] = np.concatenate([lf["fc"].vel[k], lf["fc"].svel[k][:, None]], 1)
                if lf["held"] is None or k > lf["held"][0]:
                    lf["held"] = (k, b)
            if lf["held"] is not None:          # what the drone would show now: the held result, forecast to now
                k, b = lf["held"]
                t2 = time.perf_counter()
                fk = lf["rec"][k]["frame"]
                lf["fc"].predict(k, b, k * period, tick * period, (img.shape[1], img.shape[0]), seq=fk[0],
                                 fidx_c=fk[1], fidx_t=i if fk[0] == sq else None)
                lf["pred_ms"].append((time.perf_counter() - t2) * 1e3)
    a_single_cur = None
    try:
        while True:
            el = time.perf_counter() - t_start
            if el >= total:
                break
            if el < 0:
                time.sleep(-el)
                continue
            ph = int(np.searchsorted(bounds, el, side="right") - 1)
            if ph != cur_phase:
                cur_phase = ph
                tc_phase(a.wlan, phases[ph][1])
            tick = int(el / period)
            if a.fresh_target > 0:                    # measured age of the newest held detection, and lam_F
                now_pc = time.perf_counter()
                ids = [k for k in list(results)]
                if ids:
                    fresh["aoi_ms"] = (now_pc - (t_start + max(ids) * period)) * 1e3
                fresh["hist"].append((now_pc, fresh["aoi_ms"] <= D))
                while fresh["hist"] and now_pc - fresh["hist"][0][0] > a.fresh_window_s:
                    fresh["hist"].pop(0)
                if now_pc - fresh["last"] >= 1.0 and len(fresh["hist"]) > 10:
                    share = sum(f_ for _, f_ in fresh["hist"]) / len(fresh["hist"])
                    fresh["lam"] = max(0.0, fresh["lam"] + a.eta_f * (a.fresh_target - share))
                    fresh["log"].append((round(now_pc - t_start, 2), round(fresh["lam"], 4), round(share, 3)))
                    fresh["last"] = now_pc
            cap_t = t_start + tick * period
            img = frames[tick % len(frames)]
            choice = None                                   # (server, variant)
            if pol.startswith("fixed:"):
                _, srv, var = pol.split(":")
                if idle(srv):
                    choice = (srv, var)
            elif pol.startswith("abr:"):
                # literature baseline: per-frame configuration adaptation on one fixed path (Chameleon/AWStream-style)
                srv = pol.split(":")[1]
                if idle(srv):
                    v, val, _ = best_variant(srv)
                    if val > 0:
                        choice = (srv, v)
            elif pol == "rule_fallback":
                # common UAV practice: threshold rules, one server at a time; ground if its link is up, else the
                # edge, else onboard
                lr = paths["laptop"].est_rate()[0] if "laptop" in paths else 0.0
                jr = paths["jetson"].est_rate()[0] if "jetson" in paths else 0.0
                if lr >= 2.0 and paths["laptop"].sock is not None:
                    srv, var = "laptop", "s640q90"
                elif jr >= 2.0 and paths["jetson"].sock is not None:
                    srv, var = "jetson", "s640q90"
                else:
                    srv, var = "onboard", "n320"
                busy_any = any(not idle(p) and paths[p].sock is not None for p in paths) or not idle("onboard")
                if idle(srv) and not busy_any:
                    choice = (srv, var)
            elif pol == "static_multi":
                order = list(paths) + ["onboard"]
                for i in range(len(order)):
                    srv = order[(rr + i) % len(order)]
                    if idle(srv):
                        choice = (srv, "n320" if srv == "onboard" else "s640q50")
                        rr = (rr + i + 1) % len(order)
                        break
            else:
                props = {}
                for srv in tuple(paths) + ("onboard",):
                    props[srv] = best_variant(srv)
                n_active[0] = sum(1 for k in props if props[k][2] > 0.2) or 1
                if a.energy_aware and not any(props[p][2] > 0.2 for p in paths) \
                        and not (energy["temp"] == energy["temp"] and energy["temp"] >= 85.0):
                    # no link can deliver: onboard is the only source of perception, so it is not priced
                    vals = {v: onboard_value(v, penalize=False) for v in ONBOARD_VARIANTS}
                    bv = max(vals, key=lambda k: vals[k][0])
                    props["onboard"] = (bv, vals[bv][0], vals[bv][1])
                if pol == "A_paths":
                    if max(props["laptop"][2], props["jetson"][2]) > 0.2:
                        props.pop("onboard")
                if pol == "A_single":
                    best = max(props, key=lambda k: props[k][1])
                    if a_single_cur is None or props[best][1] > props[a_single_cur][1] * 1.10 \
                            or props[a_single_cur][1] <= 0:
                        a_single_cur = best
                    cand = [a_single_cur] if idle(a_single_cur) else []
                else:
                    cand = [s for s in props if idle(s)]
                cand = [s for s in cand if props[s][1] > 0]
                if cand:
                    srv = max(cand, key=lambda k: props[k][1])
                    choice = (srv, props[srv][0])
            # keep idle paths alive / measured (probes are 64 KB for adaptive, 1 KB keepalive otherwise)
            for p in paths:
                pp = paths[p]
                if pp.sock is not None and pp.inflight is None and pp.slot.item is None \
                        and time.perf_counter() - last_probe[p] > 0.8 and (choice is None or choice[0] != p):
                    pp.probe(65536 if pol.startswith(("A_", "abr:", "rule_")) else 1024)
                    last_probe[p] = time.perf_counter()
            rec = {"id": tick, "t_cap": cap_t, "phase": phases[ph][0], "soc": phases[ph][2]}
            if frame_keys is not None:
                rec["frame"] = list(frame_keys[tick % len(frame_keys)])
            if choice is not None:
                srv, var = choice
                rec.update(server=srv, variant=var,
                           res=ONBOARD_VARIANTS[var][1] if srv == "onboard" else path_variants(srv)[var][1])
                if srv == "onboard":
                    model, res = ONBOARD_VARIANTS[var]
                    rec["acc"] = acc_of(model, res)
                    onboard.submit(tick, img, var)
                else:
                    model, res, q = path_variants(srv)[var]
                    rec["acc"] = acc_of(model, res, q)
                    t0 = time.perf_counter()
                    ok, buf = cv2.imencode(".jpg", lbs[res](image=img), [cv2.IMWRITE_JPEG_QUALITY, q])
                    enc_ms[res] = 0.8 * enc_ms[res] + 0.2 * (time.perf_counter() - t0) * 1e3
                    nbytes[(res, q)] = 0.8 * nbytes[(res, q)] + 0.2 * len(buf)
                    rec["bytes"] = len(buf)
                    paths[srv].slot.put(({"id": tick, "t_cap": cap_t, "cut": -1, "model": model, "conf": a.conf,
                                          "return_dets": bool(a.vid),
                                          "metas": [{"k": -1, "jpeg": True}]}, [buf.tobytes()]))
            log.append(rec)
            if lf is not None:
                if "server" in rec:
                    lf["rec"][tick] = rec
                try:
                    live_forecast_tick(tick, img, tuple(rec["frame"]))
                except Exception as e:          # never let the forecaster stop a run; count and report
                    lf.setdefault("errors", []).append(repr(e)[:200])
            # remote compute estimates (per model) from the worker-reported times
            for p in paths:
                for m in remote_ms[p]:
                    remote_ms[p][m] = paths[p].remote_est(m, PRIOR_REMOTE_MS[p][m])
            nxt = t_start + (int((time.perf_counter() - t_start) / period) + 1) * period
            time.sleep(max(0.0, nxt - time.perf_counter()))
        time.sleep(3.0)
    finally:
        tc_teardown(a.wlan)
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

    # ---------------------------------------------------------------- metrics
    for r in log:
        if "server" in r and r["id"] in results:
            r["lat_ms"] = (results[r["id"]] - r["t_cap"]) * 1e3
            r["t_res"] = results[r["id"]] - t_start
    per = {}
    for i, (name, imp, soc, dur) in enumerate(phases):
        lo, hi = bounds[i], bounds[i + 1]
        rs = [r for r in log if r["phase"] == name]
        got = [r for r in rs if r.get("lat_ms") is not None]
        ont = [r for r in got if r["lat_ms"] <= D]
        # age of information: results ordered by arrival; AoI(t) = t - capture time of newest result so far
        events = sorted((r["t_res"], r["t_cap"] - t_start) for r in log if r.get("t_res") is not None)
        grid = np.arange(lo, hi, 0.01)
        newest, j, aoi = -np.inf, 0, []
        for t in grid:
            while j < len(events) and events[j][0] <= t:
                newest = max(newest, events[j][1])
                j += 1
            aoi.append(t - newest if newest > -np.inf else np.inf)
        aoi = np.array(aoi)
        servers_used = {}
        for r in rs:
            if "server" in r:
                k = f"{r['server']}:{r['variant']}"
                servers_used[k] = servers_used.get(k, 0) + 1
        e_onb = sum(onboard.ms[r["variant"]] / 1e3 * P_COMPUTE_W for r in rs if r.get("server") == "onboard")
        e_rad = sum(r["bytes"] * 8 / (max(paths[r["server"]].rate, 0.5) * 1e6) * P_RADIO_W for r in rs if r.get("bytes"))
        per[name] = {"on_time_fps": len(ont) / dur, "acc_on_time_fps": sum(r["acc"] / REF for r in ont) / dur,
                     "within_1s_fps": sum(r["lat_ms"] <= 1000 for r in got) / dur,
                     "aoi_mean_ms": float(np.mean(np.minimum(aoi, 10.0)) * 1e3),
                     "availability": float(np.mean(aoi <= D / 1e3)),
                     "lat_p50_ms": statistics.median([r["lat_ms"] for r in got]) if got else None,
                     "pi_power_w": (e_onb + e_rad) / dur, "dispatch": servers_used, "impair": imp, "soc": soc}
    keys = ["on_time_fps", "acc_on_time_fps", "within_1s_fps", "aoi_mean_ms", "availability", "pi_power_w"]
    w = np.array([ph[3] for ph in phases]) / total
    tot = {k: float(sum(wi * per[ph[0]][k] for wi, ph in zip(w, phases))) for k in keys}
    out = {"policy": pol, "objective": a.objective, "acc_table": os.path.basename(a.acc), "scenario": a.scenario, "seed": a.seed, "deadline_ms": D, "per_phase": per, "total": tot,
           "onboard_ms": onboard.ms, "link_events": {p: paths[p].events for p in paths},
           "link_goodput_samples": {p: paths[p].samples for p in paths},   # (unix time, Mbit/s) per frame/probe
           "frames": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items() if k != "t_cap"} for r in log]}
    json.dump(out, open(a.out, "w"))
    if a.vid:                          # detections of every result, keyed by frame id (tick)
        np.savez_compressed(a.out[:-5] + "_dets.npz",
                            **{str(k): np.frombuffer(v, np.float32).reshape(-1, 6) for k, v in dets.items()})
    if energy["log"]:
        lg = [x for x in energy["log"] if x[1] == x[1]]
        t0_ = lg[0][0] if lg else 0.0
        e_j = sum((b_[0] - a_[0]) * (a_[1] + b_[1]) / 2 for a_, b_ in zip(lg, lg[1:]))
        dur_ = (lg[-1][0] - lg[0][0]) if len(lg) > 1 else 0.0
        temps = [x[2] for x in lg if x[2] == x[2]]
        out["measured_energy"] = {"board": board, "energy_j": e_j, "mean_w": e_j / dur_ if dur_ else None,
                                  "duration_s": dur_, "temp_max_c": max(temps) if temps else None,
                                  "temp_mean_c": sum(temps) / len(temps) if temps else None,
                                  "log_t_w_c": [(round(x[0] - t0_, 2), round(x[1], 3), round(x[2], 2)) for x in lg]}
        if a.fresh_target > 0:
            out["measured_energy"]["fresh_log_t_lam_share"] = fresh["log"]
            out["measured_energy"]["fresh_target"] = a.fresh_target
        if a.energy_aware:
            out["measured_energy"]["mu_log"] = [(round(x[0] - t0_, 2), round(x[1], 4), round(x[2], 3), round(x[3], 2))
                                                for x in energy["mu_log"]]
            out["measured_energy"]["power_budget_w"] = a.power_budget
        json.dump(out, open(a.out, "w"))
    if a.coord_port:
        out["coordination"] = {"reports": coord["reports"], "decisions": coord["decisions"]}
        json.dump(out, open(a.out, "w"))
    if lf is not None:                 # live forecaster inputs and timings
        z = {f"C_{sq}": C for sq, C in lf["chains"].items()}
        z.update({f"v_{k}": v for k, v in lf["vel"].items()})
        z.update(ego_ms=np.array(lf["ego_ms"]), obs_ms=np.array(lf["obs_ms"]), pred_ms=np.array(lf["pred_ms"]))
        np.savez_compressed(a.out[:-5] + "_livefc.npz", **z)
        out["live_forecast"] = {"params": lf["params"], "ego_ms_median": float(np.median(lf["ego_ms"])),
                                "obs_ms_median": float(np.median(lf["obs_ms"])) if lf["obs_ms"] else None,
                                "pred_ms_median": float(np.median(lf["pred_ms"])) if lf["pred_ms"] else None,
                                "results_observed": len(lf["seen"]), "errors": lf.get("errors", [])[:5],
                                "n_errors": len(lf.get("errors", []))}
        json.dump(out, open(a.out, "w"))
    print(json.dumps({"policy": pol, "scenario": a.scenario, "total": {k: round(v, 3) for k, v in tot.items()}}))


if __name__ == "__main__":
    main()
