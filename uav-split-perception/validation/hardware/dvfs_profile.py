#!/usr/bin/env python3
"""Per-frequency power, latency and energy of the camera Pi's onboard work (plan Phase 5, D5: DVFS as a third knob;
16 Nov 2026).

At each pinned CPU frequency (cpufreq scaling_min_freq = scaling_max_freq = f, all cores share policy0) the board runs,
each for --state-s seconds while board power (PMIC rails), temperature and clock are sampled at 10 Hz (energy_profile.py's
Sampler, so the numbers are comparable with energy_constants.json):
  idle                      nothing
  encode_640q90_30fps       letterbox + JPEG 640 q90 at 30 frames/s (the offload path's camera work)
  onboard_<v>               the controller's onboard variants back to back (3 torch threads, fast NMS as the engine)
Energy per inference = (P_onboard - P_idle_at_f) x time per frame (the controller's convention), and the same against the
idle power at the default ondemand setting. Every inference state starts with the board below --cool-c, so heat does not
pass for a frequency effect; the frequencies are run in two passes, the second in reverse order.
The original cpufreq settings are restored on exit, also on error or signal. Needs root (sysfs writes).
usage: sudo python dvfs_profile.py [--freqs 1500,1800,2100,2400] -> results/dvfs_profile_<hostname>.json
"""
import argparse
import atexit
import json
import os
import signal
import socket
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
CF = "/sys/devices/system/cpu/cpu0/cpufreq/"
VARIANTS = {"s320": ("yolov8s_visdrone", 320), "n480y11": ("yolo11n_visdrone", 480)}


def rd(f):
    return open(CF + f).read().strip()


def wr(f, v):
    with open(CF + f, "w") as h:
        h.write(str(v))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--freqs", default="1500,1800,2100,2400", help="MHz")
    ap.add_argument("--state-s", type=float, default=15.0)
    ap.add_argument("--cool-c", type=float, default=55.0)
    ap.add_argument("--passes", type=int, default=2)
    a = ap.parse_args()
    orig = {k: rd(k) for k in ("scaling_governor", "scaling_min_freq", "scaling_max_freq")}

    def restore(*_):
        try:
            wr("scaling_min_freq", orig["scaling_min_freq"])     # widen first, then the governor
            wr("scaling_max_freq", orig["scaling_max_freq"])
            wr("scaling_governor", orig["scaling_governor"])
        except OSError as e:
            print("RESTORE FAILED", e, file=sys.stderr)
        if _ and _[0] in (signal.SIGTERM, signal.SIGINT):
            sys.exit(1)
    atexit.register(restore)
    signal.signal(signal.SIGTERM, restore)
    signal.signal(signal.SIGINT, restore)

    def pin(mhz):
        k = int(mhz) * 1000
        if k < int(rd("scaling_min_freq")):          # order matters: min may not exceed max
            wr("scaling_min_freq", k); wr("scaling_max_freq", k)
        else:
            wr("scaling_max_freq", k); wr("scaling_min_freq", k)

    import cv2
    import torch
    import energy_profile as ep
    from hwbench import fast_nms, load_model
    from ultralytics.data.augment import LetterBox
    torch.set_num_threads(3)
    S = ep.Sampler("pi")
    S.start()
    imgs = ep.frames()
    lb = {r: LetterBox((r, r), auto=False) for r in (640, 480, 320)}
    models = {v: load_model(os.path.join(HERE, f"{m}.pt"), torch.device("cpu"), False) for v, (m, _) in VARIANTS.items()}

    def infer(v):
        m, res = models[v], VARIANTS[v][1]

        def work(k):
            im = lb[res](image=imgs[k % len(imgs)])
            x = (torch.from_numpy(np.ascontiguousarray(im[..., ::-1].transpose(2, 0, 1))).float() / 255).unsqueeze(0)
            with torch.inference_mode():
                o = m(x)
                fast_nms(o[0] if isinstance(o, (list, tuple)) else o, 0.01, 0.45, 100)
        work(0); work(1)
        return work

    def cool():
        t0 = time.time()
        while ep.read_temp() >= a.cool_c and time.time() - t0 < 900:
            time.sleep(5)
        return ep.read_temp()

    host = socket.gethostname()
    out = {"host": host, "orig_cpufreq": orig, "state_s": a.state_s, "cool_c": a.cool_c, "rows": []}
    path = os.path.join(HERE, "results", f"dvfs_profile_{host}.json")

    def state(p, f, name, fn, t_start):
        r = S.window(fn, a.state_s)
        r.update(pass_=p, freq_mhz=f, state=name, temp_start_c=t_start)
        out["rows"].append(r)
        print(p, f, name, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()
                           if k in ("power_w", "temp_c", "clock_mhz", "ms_per_frame", "frames")}, flush=True)
        json.dump(out, open(path, "w"), indent=1)

    wr("scaling_governor", "ondemand")
    time.sleep(3)
    state(0, "ondemand", "idle", lambda stop: time.sleep(max(0, stop - time.time())), ep.read_temp())
    freqs = [int(x) for x in a.freqs.split(",")]
    for p in range(1, a.passes + 1):
        for f in (freqs if p % 2 else freqs[::-1]):
            pin(f)
            time.sleep(2)
            state(p, f, "idle", lambda stop: time.sleep(max(0, stop - time.time())), ep.read_temp())
            state(p, f, "encode_640q90_30fps", lambda stop: ep.paced(
                stop, 30, lambda k: cv2.imencode(".jpg", lb[640](image=imgs[k % len(imgs)]), [cv2.IMWRITE_JPEG_QUALITY, 90])),
                ep.read_temp())
            for v in VARIANTS:
                t0 = cool()
                state(p, f, f"onboard_{v}", lambda stop, w=infer(v): ep.back_to_back(stop, w), t0)
    # summary: per frequency, the mean over passes
    summ = {}
    idle_def = [r["power_w"] for r in out["rows"] if r["freq_mhz"] == "ondemand"][0]
    for f in freqs:
        rows = [r for r in out["rows"] if r["freq_mhz"] == f]
        idle = float(np.mean([r["power_w"] for r in rows if r["state"] == "idle"]))
        s = {"idle_w": idle, "clock_mhz": float(np.mean([r["clock_mhz"] for r in rows]))}
        enc = [r for r in rows if r["state"].startswith("encode")]
        s["encode_640q90_extra_w"] = float(np.mean([r["power_w"] for r in enc])) - idle
        for v in VARIANTS:
            rr = [r for r in rows if r["state"] == f"onboard_{v}"]
            ms = float(np.mean([r["ms_per_frame"] for r in rr]))
            pw = float(np.mean([r["power_w"] for r in rr]))
            s[v] = {"ms": ms, "ms_by_pass": [r["ms_per_frame"] for r in rr], "power_w": pw,
                    "j_per_inference": (pw - idle) * ms / 1e3, "j_vs_default_idle": (pw - idle_def) * ms / 1e3,
                    "temp_end_c": float(np.mean([r["temp_end_c"] for r in rr]))}
        summ[str(f)] = s
    out["summary"] = summ
    out["idle_ondemand_w"] = idle_def
    json.dump(out, open(path, "w"), indent=1)
    print("DVFS_PROFILE_DONE", path)


if __name__ == "__main__":
    main()
