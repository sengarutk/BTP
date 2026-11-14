#!/usr/bin/env python3
"""Adaptive multi-server perception scheduling on real hardware (controller v2).

The camera UAV (Raspberry Pi 5) has three servers that can each work on one frame at a time:
  onboard  the Pi CPU (its own thread, 3 cores), variants YOLOv8n@320, YOLOv8s@320, YOLOv8s@640
  laptop   a Wi-Fi path to the laptop GPU, variants JPEG {q90,q50} x {640,480,320} for YOLOv8s,
           and JPEG {q90,q50} @640 for YOLOv8m
  jetson   a Wi-Fi path to the Jetson GPU, variants JPEG {q90,q50} x {640,480,320} for YOLOv8s
  relay    (optional, --paths ...,relay) the laptop GPU reached THROUGH the Jetson: relay.py on the Jetson forwards
           the frame to a laptop worker and the result back (for a camera out of the ground station's range);
           same variants as the laptop path. To the controller it is one more path: its rate is measured on the
           Pi -> Jetson hop, its probe round trip includes both hops
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
Literature baselines (re-implemented under this harness; "-style" = the paper's decision rule with a simple proxy
for its learned estimator):
  conf_trigger        OffloaD-style (Gomez et al., TECS 2024): onboard YOLOv8n-320 continuously; a frame is offloaded
                      (s640q90, best live path) when the newest onboard result looks like a detection failure: mean
                      confidence of its top-5 boxes < --trigger-conf or fewer than 3 boxes >= 0.25
  reward_offload      Qiu-style (SEC 2024): reward of offloading a frame estimated from the newest onboard result
                      (uncertainty mass: sum of (1 - conf) over boxes with 0.1 <= conf < 0.5); offload when it is in the
                      top --reward-share of recent rewards (rolling 10 s), otherwise onboard
  aoi_thr             freshness only: offload s640q90 to the best live path whenever the newest result is older than
                      --aoi-thr-ms; onboard YOLOv8n-320 only when no path can deliver
  jsq                 queue only: every frame to the idle server with the smallest expected latency (paths s640q90,
                      onboard n320), no accuracy or energy term
  LEAF-style fixed energy weight: any A_* policy with --energy-aware --mu-fixed W (no dual ascent)
  accumo              AccuMO-style (Kong et al., MobiCom 2023): model-predictive offloading over --mpc-horizon frames
                      (mpc_planner.py; the replay version is brief 19.10): the plan of one setting per server that
                      maximises the predicted accuracy of the result on screen, decayed with its age; no energy or heat
                      price unless --energy-aware. --mpc-context: the decay curve of the current camera-motion tertile
                      (needs --live-forecast for the live camera motion), else the global --decay curve
Metrics per phase: on-time results/s, accuracy-weighted on-time results/s, results within 1 s,
mean age of information of the newest result (AoI), availability = share of time AoI <= deadline,
Pi perception power (compute + radio, measured powers).

Controllers:
  v2    --objective rate                    accuracy-weighted on-time results/s
  v3    --objective stream                 expected accuracy of the held result (staleness decay)
  v4    --energy-aware                     camera-drone energy priced: value - mu * E_camera, mu by dual
                                             ascent of the measured power against --power-budget
  v4.1  --fresh-target                     + a freshness dual variable lam_F
  v4.2  --edge-energy-aware                + the EDGE drone's energy priced: value(jetson,v) - mu_edge *
        E_edge(v), mu_edge by dual ascent of the Jetson's measured extra power (worker reports it with
        --report-power jetson) against --edge-power-budget; budgets derive from battery + flight power
        with --mission-min. Report to the coordinator gains soc (modelled from measured power) and mu.
  v5    --thermal-aware                    + a predictive heat price lam_T on camera joules (measured thermal model:
        predicted temperature --thermal-horizon-s ahead vs --thermal-target-c), replacing reliance on the hard guard
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

from adaptive import P_COMPUTE_W, P_RADIO_W, PORT, Path, phi, tc, tc_phase, tc_setup, tc_teardown
# Second edge drone (14 Nov 2026, plan S4): path "jetson2" (Nano2's worker connects to the camera's port 48105). Only
# when --paths names it: its netem band (band 4 of a 5-band prio qdisc; the unshaped default band moves to 5) and its
# power log. Without jetson2 the ports, tc layout and every decision are exactly as before.
PORT = dict(PORT, jetson2=48105)
from hwbench import fast_nms, load_model
from pipeline_node import send_msg  # noqa: F401

REF = 0.4440  # YOLOv8s@640 FP32 mAP

ONBOARD_VARIANTS = {"n320": ("yolov8n", 320), "s320": ("yolov8s", 320), "s640": ("yolov8s", 640)}
# larger onboard models, loaded only when named in --onboard-variants (the onboard-model comparison, 20 Oct 2026)
ONBOARD_EXTRA = {"m640": ("yolov8m", 640), "l640": ("yolov8l", 640),
                 # VisDrone fine-tuned weights (scripts/train_visdrone.py; files <model>_visdrone.pt)
                 "s640vd": ("yolov8s_visdrone", 640), "m640vd": ("yolov8m_visdrone", 640),
                 "l640vd": ("yolov8l_visdrone", 640),
                 # YOLO11 n/s/m fine-tuned on VisDrone (25 Oct 2026; the professor's request)
                 "n640y11": ("yolo11n_visdrone", 640), "s640y11": ("yolo11s_visdrone", 640),
                 "m640y11": ("yolo11m_visdrone", 640)}
PATH_VARIANTS = {f"s{r}q{q}": ("yolov8s", r, q) for r in (640, 480, 320) for q in (90, 50)}
LAPTOP_EXTRA = {"m640q90": ("yolov8m", 640, 90), "m640q50": ("yolov8m", 640, 50)}

# priors (measured: experiments/results/hardware/raw/variant_timing_*.json); learned online
PRIOR_ONBOARD_MS = {"n320": 80.0, "s320": 170.0, "s640": 700.0, "m640": 2000.0, "l640": 4000.0,
                    "s640vd": 700.0, "m640vd": 2000.0, "l640vd": 4000.0,  # m/l: estimates, learned online
                    "n640y11": 300.0, "s640y11": 750.0, "m640y11": 2000.0}  # YOLO11: estimates, learned online
PRIOR_BYTES = {640: {90: 87000, 50: 35800}, 480: {90: 50100, 50: 20800}, 320: {90: 25900, 50: 11000}}
PRIOR_REMOTE_MS = {"laptop": {"yolov8s": 18.0, "yolov8m": 24.0}, "jetson": {"yolov8s": 32.0, "yolov8m": 60.0}}  # live worker stage times
PRIOR_REMOTE_MS["relay"] = dict(PRIOR_REMOTE_MS["laptop"])        # the laptop computes; the extra hop is in the RTT
PRIOR_REMOTE_MS["jetson2"] = {"yolov8s": 32.0, "yolov8m": 43.0}  # Nano2 (energy_profile_nano2_20261114.json: s640
# 27.6 ms as Nano1's 29.1, m640 40.3 ms against Nano1's 56.4; Nano1's prior/profile ratio 1.06 applied); the live
# estimate (remote_est) replaces them


def write_json_atomic(obj, path):
    """Write to a temporary file and rename: the result file appears only when complete, so a campaign that copies
    it as soon as it exists never fetches a half-written file (a 24-minute run's file is ~10 MB)."""
    tmp = f"{path}.tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f)
    os.replace(tmp, path)


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
    if name == "out_of_range":         # the camera is beyond the ground station's range: direct Pi -> laptop link cut
        return [(f"oor{i}", {"laptop": "loss 100%"}, .9, phase_s) for i in range(6)]
    if name in ("multihop_loss2", "multihop_loss5"):   # noisy relay (hardening plan Phase 5, 10 Nov 2026): the multihop
        # route of "multihop", with x % packet loss and 5 +- 5 ms delay on both hops: the camera's paths (its air link is
        # shared) and the edge drone's own link to the ground ("uplink", applied by edge_node.py)
        # Equal noise for every strategy (fixed 11 Nov 2026, before any run): the camera's netem sees the whole relayed
        # route to the laptop as one path (batman-adv forwards on the Jetson below bat0, where no qdisc can act), so the
        # laptop path gets the two-hop equivalent: loss 1 - (1 - x)^2 and delay 10 ms with jitter 7 ms (uniform, the
        # standard deviation of the sum of two 5 +- 5 ms hops). The Jetson path is one hop. The hierarchical chain's
        # forwarded frames cross camera -> Jetson ("jetson") and Jetson -> ground ("uplink", edge_node.py): two hops too.
        x = int(name[-1]) / 100
        hop = f"delay 5ms 5ms loss {100 * x:g}%"
        two = f"delay 10ms 7ms loss {100 * (1 - (1 - x) ** 2):.2f}%"
        return [(f"mhn{i}", {"laptop": two, "jetson": hop, "uplink": hop}, .9, phase_s) for i in range(6)]
    if name == "multihop":             # mesh test: links good, but the direct camera <-> ground-radio link is blocked
        # at the batman-adv level during the run (arun_mesh.sh), so all traffic to the ground is relayed by the Jetson
        return [(f"mh{i}", good, .9, phase_s) for i in range(6)]
    if name == "mesh_mission":         # mesh test (23 Oct): "uplink" = the edge drone's own link to the ground station,
        # applied by the hierarchical edge node on the Jetson (edge_node.py); the other keys on this camera as before
        return [("good", good, .9, phase_s),
                ("ground_congested", {"laptop": "rate 3mbit limit 50", "uplink": "rate 3mbit limit 50"}, .8, phase_s),
                ("camera_out_of_range", {"laptop": "loss 100%"}, .7, phase_s),
                ("edge_uplink_cut", {"uplink": "loss 100%"}, .6, phase_s),
                ("edge_link_slow", {"jetson": "rate 2mbit limit 50"}, .5, phase_s),
                ("recovered", good, .4, phase_s)]
    raise ValueError(name)


class Onboard:
    """The Pi's own inference engine, in its own thread (3 torch threads), one frame at a time."""

    def __init__(self, weights_dir, threads, results, log_lock, device="cpu", suffix=""):
        torch.set_num_threads(threads)
        self.dev, self.half = torch.device(device), device == "cuda"
        wf = lambda m: m if m.endswith("_visdrone") else m + suffix  # noqa: E731   (--weight-suffix)
        self.models = {k: load_model(os.path.join(weights_dir, f"{wf(m)}.pt"), self.dev, self.half)
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
    ap.add_argument("--decay-shape", default="measured", choices=["measured", "flat", "linear", "exp"],
                    help="ablation of the value curve rho(age) with everything else unchanged: measured (the "
                         "--decay file), flat (no staleness, rho = 1), linear (generic age-of-information decay "
                         "to 0 at 2 x the deadline), exp (generic exponential, half-life = the deadline)")
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
    ap.add_argument("--power-budget", type=float, default=-1.0,
                    help="sustained camera-board power budget (W); -1: --mission-min derived, else 3.0")
    ap.add_argument("--eta", type=float, default=0.1, help="dual-ascent step for mu (1/J per W-excess per s)")
    ap.add_argument("--mu-max", type=float, default=5.0,
                    help="anti-windup cap on mu (and mu_edge). At 5 an onboard YOLOv8n-320 inference (0.32 J) costs 1.6, "
                         "more than any result is worth, while a JPEG offload (~0.03 J) costs 0.15. mu is also frozen "
                         "while the blackout exemption runs onboard unpriced: the budget cannot be met then, and "
                         "integrating it wound mu up to 41 in a 90-s blackout, pricing out offloading after recovery")
    ap.add_argument("--lam-f-max", type=float, default=2.0, help="anti-windup cap on the freshness price lam_F")
    ap.add_argument("--edge-energy-aware", action="store_true",
                    help="controller v4.2: also price the EDGE drone's energy: value(jetson, v) -= mu_edge * "
                         "E_edge(v) (measured Jetson J per inference + radio receive); mu_edge is its own dual "
                         "variable with its own budget, ascending on the Jetson's measured extra power when the "
                         "worker reports it (--report-power jetson), else on the modelled served energy")
    ap.add_argument("--edge-power-budget", type=float, default=-1.0,
                    help="edge-drone extra-power budget (W above its idle); -1: --mission-min derived, else 1.0. "
                         "Must be > 0: the extra power is never negative, so with a 0 budget mu_edge can only "
                         "rise and the edge path is priced out for the rest of the run after its first use")
    ap.add_argument("--edge-eta", type=float, default=0.1, help="dual-ascent step for mu_edge")
    ap.add_argument("--mission-min", type=float, default=0.0,
                    help="derive both power budgets from battery and flight power for this mission time: "
                         "budget = 60 * usable Wh / mission_min - flight W (clamped >= 0); 0 = use the set budgets")
    ap.add_argument("--camera-drone-class", default="mini_249g",
                    help="drone class of this camera (battery + flight power for --mission-min and the "
                         "coordinator's SoC report)")
    ap.add_argument("--edge-drone-class", default="edge_1.5kg",
                    help="drone class of the edge drone that serves the jetson path (for --mission-min)")
    ap.add_argument("--thermal-guard-c", type=float, default=78.0,
                    help="hard guard: at or above this measured temperature the camera energy price is at least 1")
    ap.add_argument("--hold-max-c", type=float, default=85.0,
                    help="capped hold (brief 19.21): the blackout hold (onboard unpriced while no link can deliver) is "
                         "allowed only below this measured temperature. 85 = the hold as in every run before 14 Nov "
                         "2026; 78 = the capped hold of the replay's th_hold78 policies")
    ap.add_argument("--guard-hard-c", type=float, default=-1.0,
                    help="hard thermal guard (paper 2, Theorem 3): at or above this measured temperature no onboard "
                         "inference starts (its value is set to 0, as replay.py's guard_hard_c); -1 = off")
    ap.add_argument("--jetson2-m", action="store_true",
                    help="the jetson2 path (Nano2) also offers YOLOv8m (m640q90/q50, as the laptop): Nano2 runs it in "
                         "40 ms against Nano1's 56 ms, while YOLOv8s is equally fast on both (plan D1/T6); off = jetson2 "
                         "offers the jetson path's variants only")
    ap.add_argument("--encode-ahead", action="store_true",
                    help="encode ahead (brief 19.13, plan S7): v4.1's decision at each camera tick is unchanged; when it "
                         "sends nothing because the paths it values are busy, the tick's frame is encoded at once for "
                         "the highest-valued busy path and sent the moment that path frees (polled every 1 ms until "
                         "the next tick, which replaces it). Policies A_* only; off = every run before 14 Nov 2026")
    ap.add_argument("--thermal-aware", action="store_true",
                    help="controller v5: a smooth, predictive heat price. The board's temperature --thermal-horizon-s "
                         "ahead is predicted from the measured thermal model (steady T = intercept + c_per_w x P, "
                         "first-order approach with the measured tau), and a dual variable lam_T rises while that "
                         "prediction exceeds --thermal-target-c. Camera joules are priced at mu + lam_T")
    ap.add_argument("--thermal-target-c", type=float, default=75.0, help="v5: keep the predicted temperature below this")
    ap.add_argument("--thermal-horizon-s", type=float, default=60.0, help="v5: prediction horizon")
    ap.add_argument("--eta-t", type=float, default=0.01, help="v5: dual-ascent step for lam_T (per degree C excess per s)")
    ap.add_argument("--lam-t-max", type=float, default=2.0,
                    help="v5: cap on lam_T. At 2 an onboard YOLOv8n-320 inference (0.32 J) costs 0.65 of a full-value "
                         "result, while a JPEG offload (~0.03 J) costs 0.06, so heat can price out onboard work but "
                         "never the cool offloads")
    ap.add_argument("--energy-constants", default="energy_constants.json", help="energy_model.py constants")
    ap.add_argument("--fresh-target", type=float, default=0.0, help="controller v4.1: target share of time the drone "
                    "holds a detection younger than the deadline (e.g. 0.95); 0 = off. A second dual variable lam_F "
                    "rises when the measured share over the last --fresh-window-s falls below the target")
    ap.add_argument("--fresh-window-s", type=float, default=5.0)
    ap.add_argument("--eta-f", type=float, default=2.0, help="dual-ascent step for lam_F (per unit shortfall per s)")
    ap.add_argument("--mu-fixed", type=float, default=-1.0,
                    help="LEAF-style baseline: a constant energy weight mu instead of dual ascent (-1: off)")
    ap.add_argument("--mpc-horizon", type=int, default=30, help="accumo: planning horizon (frames)")
    ap.add_argument("--mpc-context", default="",
                    help="accumo: decay_context_train.json (decay per camera-motion tertile, AccuMO's content "
                         "dependence); needs --live-forecast; empty: the global --decay curve")
    ap.add_argument("--trigger-conf", type=float, default=0.5, help="conf_trigger: failure if top-5 mean conf below")
    ap.add_argument("--reward-share", type=float, default=0.3, help="reward_offload: share of frames worth offloading")
    ap.add_argument("--aoi-thr-ms", type=float, default=150.0, help="aoi_thr: offload when the newest result is older")
    ap.add_argument("--netem-legacy", action="store_true",
                    help="apply phases with netem 'change' as all campaigns up to 13 Oct 2026 did (an earlier phase's rate "
                         "limit persists into later phases that set none); default: each phase replaces the previous one")
    ap.add_argument("--onboard-variants", default="n320,s320,s640",
                    help="onboard models to load (comma list of n320 s320 s640 m640 l640); default: the usual three")
    ap.add_argument("--weight-suffix", default="", help="'_visdrone': every model is its VisDrone fine-tuned version "
                    "(onboard files <model>_visdrone.pt; accuracy keys <model>_visdrone_<res>_<q>, so --acc must hold "
                    "them, e.g. variant_accuracy_visdrone_ft.json; the workers must load the same weights)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    global ONBOARD_VARIANTS
    _all = dict(ONBOARD_VARIANTS, **ONBOARD_EXTRA)
    ONBOARD_VARIANTS = {k: _all[k] for k in a.onboard_variants.split(",")}
    write_out = lambda obj: write_json_atomic(obj, a.out)  # noqa: E731
    acc_tab = json.load(open(a.acc))
    REF_ACC = acc_tab[f"yolov8s{a.weight_suffix}_640_raw"]
    if a.decay:
        _dc = json.load(open(a.decay))
        _lag, _rat = np.array(_dc["lag_ms"], float), np.array(_dc["ratio"], float)
    else:
        _lag, _rat = np.array([0.0, 1e9]), np.array([1.0, 1.0])

    def rho(age_ms):
        if a.decay_shape == "flat":
            return 1.0
        if a.decay_shape == "linear":
            return max(0.0, 1.0 - age_ms / (2.0 * a.deadline))
        if a.decay_shape == "exp":
            return float(0.5 ** (age_ms / a.deadline))
        return float(np.interp(age_ms, _lag, _rat))

    def hold_quality(L, T):
        """mean staleness factor while a result of latency L is held for T ms"""
        return float(np.mean([rho(L + T * f) for f in (0.0, 0.25, 0.5, 0.75, 1.0)]))

    def acc_of(model, res, q=None):
        if not model.endswith("_visdrone"):
            model += a.weight_suffix
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
    onboard = Onboard(a.weights_dir, a.onboard_threads, results, log_lock, a.onboard_device, a.weight_suffix)
    onboard.conf = a.conf
    if a.vid:
        onboard.dets = dets
    cv2.setNumThreads(1)

    servers, paths = {}, {}
    priors = {"laptop": (20.0, 12.0), "jetson": (12.0, 32.0), "relay": (12.0, 20.0), "jetson2": (12.0, 32.0)}
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
        if p in ("laptop", "relay") or (p == "jetson2" and a.jetson2_m):
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
            if (a.energy_aware or a.thermal_aware) and r_override is None:
                v_ -= cam_price() * e_offload(res, q, b, r)
            if a.edge_energy_aware and p == "jetson" and r_override is None:
                v_ -= energy["mu_edge"] * e_edge(var, b, r)   # v4.2: the edge drone's energy has a price too
            if a.fresh_target > 0 and r_override is None and fresh["aoi_ms"] + L >= D:
                v_ += fresh["lam"] * p_on              # restores freshness if it arrives in time
            return v_, p_on
        v_ = acc_of(model, res, q) / REF_ACC * qv / (busy / 1e3)
        # v4.2: energy priced in both objectives; the rate value is per second, so the penalty is the
        # energy per frame times the frames per second this path takes (busy), i.e. a power
        if (a.energy_aware or a.thermal_aware) and r_override is None:
            v_ -= cam_price() * e_offload(res, q, b, r) / (busy / 1e3)
        if a.edge_energy_aware and p == "jetson" and r_override is None:
            v_ -= energy["mu_edge"] * e_edge(var, b, r) / (busy / 1e3)
        return v_, p_on

    def onboard_value(var, penalize=True):
        model, res = ONBOARD_VARIANTS[var]
        t = onboard.ms[var]
        p_on = 1.0 if t <= D else 0.0
        qv = p_on + a.late_value * ((1.0 if t <= a.late_ms else 0.0) - p_on)
        busy = math.ceil(t / (1000 * period) - 1e-9) * 1000 * period
        if a.objective == "stream":
            v_ = acc_of(model, res) / REF_ACC * hold_quality(t, busy / max(1, n_active[0]))
            if (a.energy_aware or a.thermal_aware) and penalize:
                v_ -= cam_price() * e_onboard(var)
            if a.fresh_target > 0 and fresh["aoi_ms"] + t >= D:
                v_ += fresh["lam"] * p_on              # the held detection will be stale before anything else lands
            return v_, p_on
        v_ = acc_of(model, res) / REF_ACC * qv / (busy / 1e3)
        if (a.energy_aware or a.thermal_aware) and penalize:   # a power: J per inference x inferences per s
            v_ -= cam_price() * e_onboard(var) / (busy / 1e3)
        return v_, p_on

    def idle(srv):
        if srv == "onboard":
            return not onboard.busy
        p = paths[srv]
        return p.sock is not None and p.inflight is None and p.slot.item is None

    def path_pred(p, var):
        """What the controller predicts for sending variant var on path p now: the deadline and late-window
        probabilities and the expected latency of path_value, from the same estimates (no side effects; logged per
        frame for the calibration check, 29 Oct 2026)."""
        model, res, q = path_variants(p)[var]
        r, s = paths[p].est_rate()
        if p == "laptop" and coord["share"]:
            r = min(r, coord["share"])
        b = nbytes[(res, q)]
        te, rem, rtt = enc_ms[res], remote_ms[p][model], paths[p].rtt_ms
        p_on = phi((r - b * 8 / ((D - te - rem - rtt) * 1e3)) / s) if D - te - rem - rtt > 0 else 0.0
        lb_ = a.late_ms - te - rem - rtt
        p_late = phi((r - b * 8 / (lb_ * 1e3)) / s) if lb_ > 0 else 0.0
        return {"p_on": round(p_on, 4), "p_late": round(p_late, 4), "r_mbps": round(r, 3), "s_mbps": round(s, 3),
                "L_ms": round(te + b * 8 / (r * 1e3) + rem + rtt, 2)}

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
            return {"t": now, "lap_full": lap(full), "lap_half": lap(full / 2), "other": other, "r": r, "r_full": full,
                    "lap_frac": [lap(full / k) for k in range(1, 9)],
                    "soc": energy.get("soc", 1.0), "mu": energy["mu"],
                    "edge_w": (paths["jetson"].edge_w if "jetson" in paths else None)}

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
                        if "t_sync" not in energy:      # SoC origin common to all cameras: first contact
                            energy["t_sync"], energy["e_perc_j"] = time.time(), 0.0
                        coord["reports"] += 1
                        coord["decisions"].append((time.time(), coord["allowed"], coord["share"]))
                except (OSError, ValueError):
                    pass
                coord["allowed"], coord["share"] = True, None      # coordinator gone: decide alone
                c.close()
        threading.Thread(target=coord_server, daemon=True).start()

    # ------------------------------------------------ energy: measured constants, live power log, price mu
    board = "jetson" if a.onboard_device == "cuda" else "pi"
    _ec_all = json.load(open(a.energy_constants)) if os.path.exists(a.energy_constants) else {}
    dc = _ec_all.get("drone_classes", {})
    # power budgets: hand-set values win; otherwise derive from battery + flight power for the
    # desired mission time: budget = 60 * usable Wh / mission_min - flight W (clamped >= 0)
    if a.power_budget < 0:
        c = dc.get(a.camera_drone_class, {"flight_w": 33.5, "battery_wh": 17.3})
        a.power_budget = max(0.0, 60.0 * c["battery_wh"] / a.mission_min - c["flight_w"]) \
            if a.mission_min > 0 else 3.0
    if a.edge_power_budget < 0:
        c = dc.get(a.edge_drone_class, {"flight_w": 153.6, "battery_wh": 88.8})
        a.edge_power_budget = max(0.0, 60.0 * c["battery_wh"] / a.mission_min - c["flight_w"]) \
            if a.mission_min > 0 else 1.0
    if a.edge_energy_aware and a.edge_power_budget <= 0:
        print(f"warning: edge power budget {a.edge_power_budget} W <= 0: mu_edge can never fall", flush=True)
    ec = _ec_all[board] if (a.energy_aware or a.power_log or a.thermal_aware) and board in _ec_all else None
    th = (ec or {}).get("thermal_steady")           # v5: measured steady-state thermal model of this board
    tau_th = (ec or {}).get("thermal", {}).get("tau_s", 150.0)
    ec_edge = _ec_all["jetson"] if a.edge_energy_aware and "jetson" in _ec_all else None   # the jetson-path server
    energy = {"mu": 0.0, "mu_edge": 0.0, "log": [], "mu_log": [], "mu_edge_log": [], "temp": 50.0,
              "edge_served": [], "soc": 1.0, "clk_log": [], "lam_t": 0.0, "t_log": [], "t0w": time.time(), "e_perc_j": 0.0, "t_last": None}
    fresh = {"lam": 0.0, "aoi_ms": float("inf"), "hist": [], "log": [], "last": 0.0}
    guard_n = [0]                      # decisions at which the hard guard (--guard-hard-c) blocked onboard
    props_now = [None]                 # this tick's path values (A_* policies), for --encode-ahead
    ahead = {"cur": None, "sent": 0, "replaced": 0, "wait_ms": []}   # --encode-ahead: the frame waiting for its path

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

    def read_clock_():
        """Actual ARM clock (MHz) and firmware throttle flags of the Pi (vcgencmd), for the throttling analysis."""
        import subprocess as _sp
        try:
            hz = _sp.run(["vcgencmd", "measure_clock", "arm"], capture_output=True, text=True, timeout=2).stdout
            th = _sp.run(["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=2).stdout
            return float(hz.strip().split("=")[1]) / 1e6, int(th.strip().split("=")[1], 16)
        except Exception:
            return float("nan"), -1

    def power_logger():
        last_mu = time.time()
        last_clk = 0.0
        while True:
            try:
                pw, tp = read_board(), read_temp_()
            except Exception:
                pw, tp = float("nan"), float("nan")
            now = time.time()
            energy["log"].append((now, pw, tp))
            if board == "pi" and now - last_clk >= 1.0:     # clock and throttle flags once per second
                energy["clk_log"].append((now,) + read_clock_())
                last_clk = now
                # the edge drone's measured board power (Jetson worker, --report-power) in EVERY strategy, not only
                # when it is priced, so the Jetson energy of unpriced strategies can be compared (24 Oct 2026)
                jw_ = paths.get("jetson")
                if jw_ is not None and getattr(jw_, "edge_w", None) is not None and now - jw_.edge_w_t <= 2.0:
                    energy.setdefault("edge_w_log", []).append((now, jw_.edge_w))
                jw2 = paths.get("jetson2")
                if jw2 is not None and getattr(jw2, "edge_w", None) is not None and now - jw2.edge_w_t <= 2.0:
                    energy.setdefault("edge2_w_log", []).append((now, jw2.edge_w))
            energy["temp"] = tp
            if pw == pw:                               # measured perception energy since the SoC origin
                if energy["t_last"] is not None:
                    energy["e_perc_j"] += pw * (now - energy["t_last"])
                energy["t_last"] = now
            c = dc.get(a.camera_drone_class)           # modelled SoC (coordinator report): flight energy
            if c:                                      # + measured board energy since the common origin
                t0s = energy.get("t_sync", energy["t0w"])
                energy["soc"] = max(0.0, 1.0 - (c["flight_w"] * (now - t0s) + energy["e_perc_j"])
                                    / 3600.0 / c["battery_wh"])
            if (a.energy_aware or a.edge_energy_aware or a.thermal_aware) and now - last_mu >= 1.0:
                recent = [x[1] for x in energy["log"] if now - x[0] <= 1.0 and x[1] == x[1]]
                if recent:
                    pbar = sum(recent) / len(recent)
                    if a.energy_aware:                 # camera drone: dual ascent on the power budget
                        if a.mu_fixed >= 0:
                            mu = a.mu_fixed            # LEAF-style baseline: fixed weight
                        elif now - energy.get("exempt_t", 0.0) <= 1.0:
                            mu = energy["mu"]          # anti-windup: onboard forced and unpriced, budget not controllable
                        else:
                            mu = min(a.mu_max, max(0.0, energy["mu"] + a.eta * (pbar - a.power_budget)))
                        if tp == tp and tp >= a.thermal_guard_c:  # thermal guard: make onboard work expensive
                            mu = max(mu, 1.0)
                        energy["mu"] = mu
                        energy["mu_log"].append((now, mu, pbar, tp))
                    if a.thermal_aware and th and tp == tp:   # v5: predictive heat price
                        p10 = [x[1] for x in energy["log"] if now - x[0] <= 10.0 and x[1] == x[1]]
                        t_ss = th["intercept_c"] + th["c_per_w"] * (sum(p10) / len(p10))
                        t_hat = tp + (t_ss - tp) * (1.0 - math.exp(-a.thermal_horizon_s / tau_th))
                        energy["lam_t"] = min(a.lam_t_max, max(0.0, energy["lam_t"] + a.eta_t * (t_hat - a.thermal_target_c)))
                        energy["t_log"].append((now, energy["lam_t"], t_hat, tp))
                    if a.edge_energy_aware:            # edge drone (v4.2): dual ascent on its EXTRA power
                        jw = paths.get("jetson")
                        p_extra, src = None, "model"
                        if ec_edge is not None and jw is not None and jw.edge_w is not None \
                                and now - jw.edge_w_t <= 2.0:
                            p_extra, src = max(0.0, jw.edge_w - ec_edge["idle_w"]), "measured"
                        if p_extra is None:            # between reports: modelled rate of served energy
                            served = [(t, j) for t, j in energy["edge_served"] if now - t <= 5.0]
                            p_extra = sum(j for _, j in served) / 5.0
                        energy["mu_edge"] = min(a.mu_max, max(0.0, energy["mu_edge"] + a.edge_eta *
                                                              (p_extra - a.edge_power_budget)))
                        energy["mu_edge_log"].append((now, energy["mu_edge"], p_extra, src))
                last_mu = now
            time.sleep(0.2)
    if a.power_log or a.energy_aware or a.edge_energy_aware or a.thermal_aware:
        threading.Thread(target=power_logger, daemon=True).start()

    def cam_price():
        """Price of one camera-drone joule: energy price mu (v4) + predictive heat price lam_T (v5)."""
        return energy["mu"] + energy["lam_t"]

    def e_onboard(var):
        return ec["infer_j"].get(var, 0.0) if ec else 0.0

    def e_offload(res, q, nb, r_mbps):
        if not ec:
            return 0.0
        enc = ec["encode_j"].get(f"{res}q{q}", ec["encode_j"].get("640q90", 0.0))
        tx = ec.get("radio_tx_w", {"a": 0.2, "b_per_mbps": 0.0})
        r = max(r_mbps, 0.2)
        return enc + max(0.0, tx["a"] + tx["b_per_mbps"] * r) * nb * 8 / (r * 1e6)

    def e_edge(var, nb, r_mbps):
        """Energy the edge drone spends serving one frame (measured constants): J per inference of the
        variant's model@size + radio receive. var like 's640q90' or 'm640q90'."""
        if not ec_edge:
            return 0.0
        j = ec_edge["infer_j"].get(var.split("q")[0], ec_edge["infer_j"].get("s640", 0.0))
        return j + ec_edge.get("radio_rx_w", 0.2) * nb * 8 / (max(r_mbps, 0.2) * 1e6)

    phases = scenario_phases(a.scenario, a.phase_s, a.seed)
    tc_setup(a.wlan)
    if "jetson2" in paths:             # a fifth band for the second edge drone's path (unshaped traffic: band 5)
        tc(f"qdisc del dev {a.wlan} root")
        tc(f"qdisc add dev {a.wlan} root handle 1: prio bands 5 priomap " + " ".join(["4"] * 16))
        for band, pth in ((1, "laptop"), (2, "jetson"), (3, "relay"), (4, "jetson2")):
            tc(f"qdisc add dev {a.wlan} parent 1:{band} handle {band}0: netem")
            tc(f"filter add dev {a.wlan} parent 1: protocol ip prio 1 u32 match ip sport {PORT[pth]} 0xffff flowid 1:{band}")
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
    bl = {"onboard_ids": [], "rewards": []}         # literature baselines' state

    def live_path():
        """the idle path with the highest estimated goodput that can carry a frame (else None)"""
        ok = [p for p in paths if paths[p].sock is not None and idle(p) and paths[p].est_rate()[0] >= 0.5]
        return max(ok, key=lambda p: paths[p].est_rate()[0]) if ok else None

    def newest_onboard():
        ids = [k for k in bl["onboard_ids"][-30:] if k in dets]
        return np.frombuffer(dets[max(ids)], np.float32).reshape(-1, 6) if ids else None

    def baseline_choice(pol):
        if pol == "jsq":
            best, lat = None, float("inf")
            for p in paths:
                if paths[p].sock is not None and idle(p):
                    r = max(paths[p].est_rate()[0], 0.05)
                    lt = enc_ms[640] + nbytes[(640, 90)] * 8 / (r * 1e3) + remote_ms[p]["yolov8s"] + paths[p].rtt_ms
                    if lt < lat:
                        best, lat = (p, "s640q90"), lt
            if idle("onboard") and onboard.ms["n320"] < lat:
                best = ("onboard", "n320")
            return best
        if pol == "aoi_thr":
            while True:                             # results is filled by other threads
                try:
                    ids = list(results)
                    break
                except RuntimeError:
                    pass
            aoi = (time.perf_counter() - (t_start + max(ids) * period)) * 1e3 if ids else float("inf")
            if aoi <= a.aoi_thr_ms:
                return None
            p = live_path()
            if p is not None:
                return (p, "s640q90")
            if not any(paths[q].sock is not None and paths[q].est_rate()[0] >= 0.5 for q in paths) and idle("onboard"):
                return ("onboard", "n320")
            return None
        det = newest_onboard()                      # conf_trigger / reward_offload: decide from the local result
        want = False
        if det is not None:
            cf = np.sort(det[:, 4])[::-1]
            if pol == "conf_trigger":
                want = (cf[:5].mean() if len(cf) else 0.0) < a.trigger_conf or int((cf >= 0.25).sum()) < 3
            else:
                band = cf[(cf >= 0.1) & (cf < 0.5)]
                rw = float((1.0 - band).sum())
                now_ = time.perf_counter()
                bl["rewards"] = [(t_, x) for t_, x in bl["rewards"] if now_ - t_ <= 10.0] + [(now_, rw)]
                thr = np.quantile([x for _, x in bl["rewards"]], 1.0 - a.reward_share)
                want = rw >= thr
        if want:
            p = live_path()
            if p is not None:
                return (p, "s640q90")
        return ("onboard", "n320") if idle("onboard") else None

    mpc = {"sent": {}, "plan_ms": [], "tertile": []}          # accumo: what it sent, planner time per frame
    if pol == "accumo":
        import mpc_planner
        mpc_opts = {"laptop": list(dict(PATH_VARIANTS, **LAPTOP_EXTRA)), "jetson": list(PATH_VARIANTS),
                    "jetson2": list(dict(PATH_VARIANTS, **(LAPTOP_EXTRA if a.jetson2_m else {}))),
                    "relay": list(dict(PATH_VARIANTS, **LAPTOP_EXTRA)), "onboard": list(ONBOARD_VARIANTS)}
        if a.mpc_context:
            from decay_context import ego_speed
            _mc = json.load(open(a.mpc_context))
            mpc["ctx"] = (np.array(_mc["lags_ms"], float), [np.array(_mc["ratio"]["v2"][f"ego{k}"], float)
                                                             for k in range(3)], _mc["cuts"]["ego"])

    def mpc_option(srv, var, now):
        """(latency s, repeat period s, A/A_ref, energy J) of one setting, or None if unusable now."""
        if srv == "onboard":
            model, res = ONBOARD_VARIANTS[var]
            ms = onboard.ms[var]
            return ms / 1e3, mpc_planner.repeat_period(ms, period), acc_of(model, res) / REF_ACC, e_onboard(var)
        path = paths[srv]
        if path.sock is None or (srv == "laptop" and not coord["allowed"]):
            return None
        model, res, q = path_variants(srv)[var]
        r = path.est_rate()[0]
        if srv == "laptop" and coord["share"]:
            r = min(r, coord["share"])
        b = nbytes[(res, q)]
        tx = b * 8 / (r * 1e6)
        if tx + path.rtt_ms / 1e3 > a.stall_s:          # the transfer would stall and drop the link
            return None
        lat = enc_ms[res] / 1e3 + tx + (remote_ms[srv][model] + 1.5 * path.rtt_ms) / 1e3
        return lat, max(tx + path.rtt_ms / 1e3, period), acc_of(model, res, q) / REF_ACC, e_offload(res, q, b, r)

    def mpc_choice(tick, now, img):
        """AccuMO-style receding-horizon choice (mpc_planner.plan) from the live state; times are s since t_start."""
        t0 = time.perf_counter()
        lag, rat = _lag, _rat
        if "ctx" in mpc and lf is not None and frame_keys is not None:      # camera motion up to the last frame
            sq, i = frame_keys[tick % len(frame_keys)]
            C = lf["chains"].get(sq)
            if C is not None and i > 2:
                e = ego_speed(C, i - 1, img.shape[1], img.shape[0])
                if e == e:
                    k = int(np.searchsorted(mpc["ctx"][2], e, side="right"))
                    lag, rat = mpc["ctx"][0], mpc["ctx"][1][k]
                    mpc["tertile"].append(k)
        while True:                                      # results is filled by other threads
            try:
                got = dict(results)
                break
            except RuntimeError:
                pass
        shown = max(got) if got else None
        sent, inflight = mpc["sent"], []
        for k in list(sent):                             # keep the shown result and those still on their way
            srv, var, acc, t_arr, t_free, t_q, rest = sent[k]
            if k == shown:
                continue
            lost = srv != "onboard" and paths[srv].sock is None
            if (shown is not None and k < shown) or k in got or lost or now - t_arr >= a.stall_s:
                del sent[k]
        if shown in sent:
            inflight.append((shown, sent[shown][2], -math.inf))
        for k, (srv, var, acc, t_arr, t_free, t_q, rest) in sorted(sent.items()):
            if k == shown:
                continue
            inf = paths[srv].inflight if srv != "onboard" else None
            if inf is not None and inf[0] - t_start >= t_q - 1e-6 and k == max(x for x in sent if sent[x][0] == srv):
                t_arr = inf[0] - t_start + inf[1] * 8 / (max(paths[srv].est_rate()[0], 1e-3) * 1e6) + rest
            inflight.append((k, acc, mpc_planner.overdue_arrival(t_arr, now, period)))
        idle_ = {s: idle(s) for s in tuple(paths) + ("onboard",)}
        free = {}
        for s in idle_:
            fr = [v[4] for v in sent.values() if v[0] == s and v[4] > now]
            free[s] = now if idle_[s] else (max(fr) if fr else now + period)
        opts = {s: [(v,) + o for v in mpc_opts[s] if (o := mpc_option(s, v, now)) is not None] for s in idle_}
        price = cam_price() if a.energy_aware else 0.0
        if price and not any(opts[p] for p in paths):    # as v4: onboard is not priced while no path can deliver
            price = 0.0
            energy["exempt_t"] = time.time()
        ch = mpc_planner.plan(now, tick, period, a.mpc_horizon, opts, free, idle_, inflight, lag, rat, price)
        if ch is not None:
            srv, var, _ = ch
            lat, per, acc, _ = mpc_option(srv, var, now)
            if srv == "onboard":
                sent[tick] = (srv, var, acc, now + lat, now + lat, now, 0.0)
            else:                                        # the path is free again once the transfer is acknowledged
                model, res, q = path_variants(srv)[var]
                t_send = now + enc_ms[res] / 1e3
                rest = (remote_ms[srv][model] + 1.5 * paths[srv].rtt_ms) / 1e3
                sent[tick] = (srv, var, acc, now + lat, t_send + per, now, rest)
            ch = (srv, var)
        mpc["plan_ms"].append((time.perf_counter() - t0) * 1e3)
        return ch

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
                tc_phase(a.wlan, phases[ph][1], legacy=a.netem_legacy)
                if "jetson2" in paths:         # band 4: the second edge drone's impairment of this phase
                    tc(f"qdisc del dev {a.wlan} parent 1:4 handle 40:")
                    tc(f"qdisc add dev {a.wlan} parent 1:4 handle 40: netem " + (phases[ph][1].get("jetson2") or ""))
                if "jetson" in paths:          # the edge node applies the edge drone's own uplink condition
                    paths["jetson"].hdr_extra = {"edge_impair": phases[ph][1].get("uplink", "")}
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
                    fresh["lam"] = min(a.lam_f_max, max(0.0, fresh["lam"] + a.eta_f * (a.fresh_target - share)))
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
            elif pol in ("conf_trigger", "reward_offload", "aoi_thr", "jsq"):
                choice = baseline_choice(pol)
            elif pol == "accumo":
                choice = mpc_choice(tick, el, img)
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
                props_now[0] = props
                for srv in tuple(paths) + ("onboard",):
                    props[srv] = best_variant(srv)
                n_active[0] = sum(1 for k in props if props[k][2] > 0.2) or 1
                if a.energy_aware and not any(props[p][2] > 0.2 for p in paths) \
                        and not (energy["temp"] == energy["temp"] and energy["temp"] >= a.hold_max_c):
                    # no link can deliver: onboard is the only source of perception, so it is not priced
                    energy["exempt_t"] = time.time()      # (and mu is frozen meanwhile: anti-windup)
                    vals = {v: onboard_value(v, penalize=False) for v in ONBOARD_VARIANTS}
                    bv = max(vals, key=lambda k: vals[k][0])
                    props["onboard"] = (bv, vals[bv][0], vals[bv][1])
                if a.guard_hard_c > 0 and energy["temp"] == energy["temp"] and energy["temp"] >= a.guard_hard_c:
                    props["onboard"] = (props["onboard"][0], 0.0, 0.0)    # hard guard: no onboard start while hot
                    guard_n[0] += 1
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
                    pp.probe(65536 if pol.startswith(("A_", "abr:", "rule_")) or pol in ("conf_trigger", "reward_offload", "aoi_thr", "jsq", "accumo")
                             else 1024)
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
                    bl["onboard_ids"].append(tick)
                else:
                    model, res, q = path_variants(srv)[var]
                    rec["acc"] = acc_of(model, res, q)
                    rec["pred"] = path_pred(srv, var)        # before the encode updates the size and time estimates
                    t0 = time.perf_counter()
                    ok, buf = cv2.imencode(".jpg", lbs[res](image=img), [cv2.IMWRITE_JPEG_QUALITY, q])
                    enc_ms[res] = 0.8 * enc_ms[res] + 0.2 * (time.perf_counter() - t0) * 1e3
                    nbytes[(res, q)] = 0.8 * nbytes[(res, q)] + 0.2 * len(buf)
                    rec["bytes"] = len(buf)
                    if srv == "jetson" and a.edge_energy_aware:      # modelled edge-drone energy served
                        energy["edge_served"].append((time.time(), e_edge(var, len(buf), paths[srv].est_rate()[0])))
                        if len(energy["edge_served"]) > 600:
                            del energy["edge_served"][:300]
                    paths[srv].slot.put(({"id": tick, "t_cap": cap_t, "cut": -1, "model": model, "conf": a.conf,
                                          "res": res, "q": q,
                                          "return_dets": bool(a.vid),
                                          "metas": [{"k": -1, "jpeg": True}]}, [buf.tobytes()]))
            log.append(rec)
            if a.encode_ahead and pol.startswith("A_"):
                if ahead["cur"] is not None:
                    ahead["replaced"] += 1             # a newer frame replaces the one still waiting
                ahead["cur"] = None
                pv = props_now[0]
                if choice is None and pv:
                    busy = [p_ for p_ in paths if p_ in pv and pv[p_][1] > 0 and paths[p_].sock is not None]
                    if busy:
                        srv_a = max(busy, key=lambda k: pv[k][1])
                        var_a = pv[srv_a][0]
                        model_a, res_a, q_a = path_variants(srv_a)[var_a]
                        ok, buf_a = cv2.imencode(".jpg", lbs[res_a](image=img), [cv2.IMWRITE_JPEG_QUALITY, q_a])
                        ahead["cur"] = (srv_a, var_a, model_a, res_a, q_a, buf_a, rec, tick, cap_t, path_pred(srv_a, var_a))
                props_now[0] = None
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
            while ahead["cur"] is not None and time.perf_counter() < nxt - 0.002:
                srv_a, var_a, model_a, res_a, q_a, buf_a, rec_a, tick_a, cap_a, pred_a = ahead["cur"]
                if paths[srv_a].sock is None:
                    ahead["cur"] = None                # the link dropped: nothing to wait for
                    break
                if idle(srv_a):                        # the path just freed: send the waiting frame now
                    rec_a.update(server=srv_a, variant=var_a, res=res_a, acc=acc_of(model_a, res_a, q_a),
                                 pred=pred_a, bytes=len(buf_a), ahead=True)
                    ahead["wait_ms"].append(round((time.perf_counter() - cap_a) * 1e3, 1))
                    paths[srv_a].slot.put(({"id": tick_a, "t_cap": cap_a, "cut": -1, "model": model_a, "conf": a.conf,
                                            "res": res_a, "q": q_a, "return_dets": bool(a.vid),
                                            "metas": [{"k": -1, "jpeg": True}]}, [buf_a.tobytes()]))
                    if lf is not None:
                        lf["rec"][tick_a] = rec_a
                    ahead["sent"] += 1
                    ahead["cur"] = None
                    break
                time.sleep(0.001)
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
            if r["server"] in paths and r["id"] in paths[r["server"]].where:
                r["where"] = paths[r["server"]].where[r["id"]]
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
    out = {"netem": "legacy-persistent-rate" if a.netem_legacy else "per-phase-reset",
           "policy": pol, "objective": a.objective, "acc_table": os.path.basename(a.acc),
           "weight_suffix": a.weight_suffix, "paths": list(paths), "scenario": a.scenario, "seed": a.seed, "deadline_ms": D, "per_phase": per, "total": tot,
           "onboard_ms": onboard.ms, "link_events": {p: paths[p].events for p in paths},
           "link_goodput_samples": {p: paths[p].samples for p in paths},   # (unix time, Mbit/s) per frame/probe
           "frames": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items() if k != "t_cap"} for r in log]}
    if a.encode_ahead:
        w_ = ahead["wait_ms"]
        out["encode_ahead"] = {"sent": ahead["sent"], "replaced": ahead["replaced"],
                               "wait_ms_median": float(np.median(w_)) if w_ else None}
    if a.hold_max_c != 85.0 or a.guard_hard_c > 0:   # recorded only when set (older runs: hold 85, no guard)
        out["thermal_rules"] = {"hold_max_c": a.hold_max_c, "guard_hard_c": a.guard_hard_c, "guard_blocks": guard_n[0]}
    if mpc["plan_ms"]:                 # accumo: planner time per frame on this board
        pm = np.array(mpc["plan_ms"])
        out["mpc"] = {"horizon": a.mpc_horizon, "context": bool(a.mpc_context), "plan_ms_median": float(np.median(pm)),
                      "plan_ms_p95": float(np.percentile(pm, 95)), "plan_ms_max": float(pm.max()), "n": len(pm),
                      "tertile_counts": [mpc["tertile"].count(k) for k in range(3)]}
    # The result JSON is written ONCE, last, after the _dets/_livefc files: the campaign copies the run's files as
    # soon as the JSON exists, so everything else must be complete by then (write_json_atomic makes the JSON itself
    # appear only when whole).
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
        if energy.get("edge_w_log"):       # (t, Jetson board W) once per second, every strategy
            out["measured_energy"]["edge_w_log"] = [(round(x[0] - t0_, 2), round(x[1], 3)) for x in energy["edge_w_log"]]
        if energy.get("edge2_w_log"):      # the same for the second edge drone (jetson2)
            out["measured_energy"]["edge2_w_log"] = [(round(x[0] - t0_, 2), round(x[1], 3)) for x in energy["edge2_w_log"]]
        if energy["clk_log"]:              # (t, ARM MHz, throttle flags) once per second (bit 2 = throttled now,
            out["measured_energy"]["clock_log_t_mhz_flags"] = [   # bit 1 = frequency capped, bit 3 = soft temp limit)
                (round(x[0] - t0_, 2), round(x[1], 1), x[2]) for x in energy["clk_log"]]
        if a.fresh_target > 0:
            out["measured_energy"]["fresh_log_t_lam_share"] = fresh["log"]
            out["measured_energy"]["fresh_target"] = a.fresh_target
        if a.energy_aware:
            out["measured_energy"]["mu_log"] = [(round(x[0] - t0_, 2), round(x[1], 4), round(x[2], 3), round(x[3], 2))
                                                for x in energy["mu_log"]]
            out["measured_energy"]["power_budget_w"] = a.power_budget
        if a.thermal_aware:                           # controller v5: heat price, predicted and measured temperature
            out["measured_energy"]["thermal_log_t_lam_pred_meas"] = [
                (round(x[0] - t0_, 2), round(x[1], 4), round(x[2], 2), round(x[3], 2)) for x in energy["t_log"]]
            out["measured_energy"]["thermal_target_c"] = a.thermal_target_c
        if a.edge_energy_aware:                       # controller v4.2: the edge drone's price and live power
            out["measured_energy"]["mu_edge_log"] = [(round(x[0] - t0_, 2), round(x[1], 4), round(x[2], 3), x[3])
                                                     for x in energy["mu_edge_log"]]
            out["measured_energy"]["edge_budget_w"] = a.edge_power_budget
            jw = paths.get("jetson")
            out["measured_energy"]["edge_reported_w"] = jw.edge_w if jw is not None and jw.edge_w is not None else None
            out["measured_energy"]["soc_model_end"] = energy.get("soc")
    if a.coord_port:
        out["coordination"] = {"reports": coord["reports"], "decisions": coord["decisions"]}
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
    write_out(out)
    print(json.dumps({"policy": pol, "scenario": a.scenario, "total": {k: round(v, 3) for k, v in tot.items()}}))


if __name__ == "__main__":
    main()
