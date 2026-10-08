#!/usr/bin/env python3
"""Steady-state temperature of the Pi 5 (no cooler) against sustained average power: the thermal model behind
"would this strategy throttle in flight". Each load level is held for --level-s seconds; power (PMIC, 10 Hz),
SoC temperature and the actual ARM clock (vcgencmd measure_clock arm, which shows firmware throttling) are
logged. The steady value is the mean over the last 60 s of each level.
Levels: idle; the motion forecaster at 30 fps; JPEG 640 q90 encode at 30 fps; YOLOv8n-320 onboard at duty
cycles 0.15, 0.3, 0.5 and 1.0 (3 torch threads), i.e. the average loads the strategies put on the camera drone.
Output: results/thermal_steady_pi.json
"""
import argparse
import json
import os
import subprocess
import threading
import time

import cv2
import numpy as np

from energy_profile import HERE, frames, read_power, read_temp


def arm_clock():
    out = subprocess.run(["vcgencmd", "measure_clock", "arm"], capture_output=True, text=True).stdout
    try:
        return int(out.strip().split("=")[1]) / 1e6
    except (IndexError, ValueError):
        return float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level-s", type=float, default=360.0)
    a = ap.parse_args()
    import torch
    from hwbench import fast_nms, load_model
    from ultralytics.data.augment import LetterBox
    torch.set_num_threads(3)
    imgs = frames()
    lb = {r: LetterBox((r, r), auto=False) for r in (640, 320)}
    m = load_model(os.path.join(HERE, "yolov8n.pt"), torch.device("cpu"), False)

    def infer(k):
        im = lb[320](image=imgs[k % len(imgs)])
        x = (torch.from_numpy(np.ascontiguousarray(im[..., ::-1].transpose(2, 0, 1))).float() / 255).unsqueeze(0)
        with torch.inference_mode():
            o = m(x)
            fast_nms(o[0] if isinstance(o, (list, tuple)) else o, 0.01, 0.45, 100)
    infer(0)
    from egomotion import small_grey, step
    from forecast import Forecaster
    fp = json.load(open(os.path.join(HERE, "forecast_tuning_v2.json")))["best"]["params"]

    def level(name, work):
        stop = {"v": False}
        th = threading.Thread(target=work, args=(stop,), daemon=True)
        th.start()
        rows, t0 = [], time.time()
        while time.time() - t0 < a.level_s:
            rows.append((time.time() - t0, read_power("pi"), read_temp(), arm_clock()))
            time.sleep(0.1)
        stop["v"] = True
        th.join(timeout=5)
        r = np.array(rows)
        last = r[r[:, 0] >= a.level_s - 60]
        res = {"power_w": float(r[:, 1].mean()), "temp_steady_c": float(last[:, 2].mean()),
               "temp_end_c": float(r[-1, 2]), "arm_clock_mhz_last60": float(np.nanmean(last[:, 3])),
               "arm_clock_min_mhz": float(np.nanmin(r[:, 3])), "trace_10s": r[::100].round(3).tolist()}
        out["levels"][name] = res
        print(name, {k: round(v, 2) for k, v in res.items() if k != "trace_10s"}, flush=True)
        json.dump(out, open(os.path.join(HERE, "results", "thermal_steady_pi.json"), "w"), indent=1)

    out = {"level_s": a.level_s, "levels": {}}

    def idle(stop):
        while not stop["v"]:
            time.sleep(0.2)

    def forecaster(stop):
        fc, prev, k, rng = Forecaster(**fp), None, 0, np.random.default_rng(0)
        t0 = time.time()
        while not stop["v"]:
            g, sc = small_grey(imgs[k % len(imgs)])
            if prev is not None:
                step(prev, g, sc)
            prev = g
            if k % 2 == 0:
                xy = rng.uniform(0, 600, (100, 2))
                b = np.concatenate([xy, xy + 30, rng.uniform(0, 1, (100, 1)), rng.integers(0, 10, (100, 1))], 1)
                fc.observe(k, k / 30, "s", b.astype(np.float32))
            k += 1
            time.sleep(max(0.0, t0 + k / 30 - time.time()))

    def encode(stop):
        k, t0 = 0, time.time()
        while not stop["v"]:
            cv2.imencode(".jpg", lb[640](image=imgs[k % len(imgs)]), [cv2.IMWRITE_JPEG_QUALITY, 90])
            k += 1
            time.sleep(max(0.0, t0 + k / 30 - time.time()))

    def duty(d):
        def run(stop):
            k = 0
            while not stop["v"]:
                t0 = time.perf_counter()
                infer(k)
                k += 1
                busy = time.perf_counter() - t0
                if d < 1.0:
                    time.sleep(busy * (1 - d) / d)
        return run

    level("idle", idle)
    level("forecaster_30fps", forecaster)
    level("encode_640q90_30fps", encode)
    for d in (0.15, 0.3, 0.5, 1.0):
        level(f"onboard_n320_duty{d}", duty(d))
    print("THERMAL_STEADY_DONE", flush=True)


if __name__ == "__main__":
    main()
