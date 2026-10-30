#!/usr/bin/env python3
"""Time the AccuMO-style planner (mpc_planner.plan) on this machine, without the testbed: no workers, links or camera.

The states are drawn around the board's priors: goodput 0.2-40 Mbit/s per path (some paths down), current onboard
times with throttling (x 1-1.53), random results in flight and on screen, the measured decay curve. The same planner
runs every camera frame under adaptive2.py --policy accumo, so its time here bounds the controller's added work.
Single-threaded numpy (as on the Pi beside the inference thread) unless --threads is given.

usage: bench_planner.py [--n 3000] [--horizon 30] [--price] [--out FILE.json]
"""
import argparse
import json
import os
import platform
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=3000)
    ap.add_argument("--horizon", type=int, default=30)
    ap.add_argument("--price", action="store_true", help="with an energy price (accumo + --energy-aware)")
    ap.add_argument("--threads", default="1")
    ap.add_argument("--decay", default=str(HERE.parent.parent / "experiments" / "results" / "hardware" /
                                           "staleness_decay_forecast_v2.json"))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[v] = a.threads
    import numpy as np
    import mpc_planner as M
    from adaptive2 import LAPTOP_EXTRA, ONBOARD_VARIANTS, PATH_VARIANTS, PRIOR_BYTES, PRIOR_REMOTE_MS

    if os.path.exists(a.decay):
        d = json.load(open(a.decay))
        lag, rat = np.array(d["lag_ms"], float), np.array(d["ratio"], float)
    else:                                              # the shape of the measured curve, if the file is not here
        lag, rat = np.array([0.0, 100, 300, 1000, 3000]), np.array([1.0, 0.95, 0.8, 0.45, 0.2])
    rng = np.random.default_rng(a.seed)
    period, enc = 1 / 30, {640: 3.5, 480: 2.2, 320: 1.2}
    onb_ms = {"n320": 96.0, "s320": 595.0, "s640": 700.0}
    acc = {"n320": 0.28, "s320": 0.36, "s640": 1.0}
    opts_all = {"laptop": dict(PATH_VARIANTS, **LAPTOP_EXTRA), "jetson": dict(PATH_VARIANTS)}
    times, chosen = [], {}
    for i in range(a.n):
        now, tick = i * period, i
        opts, free, idle = {}, {}, {}
        for p, vs in opts_all.items():
            r = float(rng.choice([rng.uniform(0.2, 2), rng.uniform(2, 40)])) if rng.random() > 0.1 else 0.0
            idle[p] = bool(rng.random() < 0.5)
            free[p] = now if idle[p] else now + float(rng.uniform(0.01, 0.3))
            o = []
            if r > 0:
                rtt = {"laptop": 4.9, "jetson": 2.7}[p] / 1e3
                for v, (m, res, q) in vs.items():
                    tx = PRIOR_BYTES[res][q] * 8 / (r * 1e6)
                    if tx + rtt > 1.5:
                        continue
                    lat = enc[res] / 1e3 + tx + (PRIOR_REMOTE_MS[p][m] / 1e3 + 1.5 * rtt)
                    o.append((v, lat, max(tx + rtt, period), 0.6 + 0.4 * rng.random(), 0.05 + 0.1 * tx))
            opts[p] = o
        f = 1 + 0.53 * rng.random()
        opts["onboard"] = [(v, onb_ms[v] * f / 1e3, M.repeat_period(onb_ms[v] * f, period), acc[v], 0.4)
                           for v in ONBOARD_VARIANTS if v in onb_ms]
        idle["onboard"] = bool(rng.random() < 0.3)
        free["onboard"] = now if idle["onboard"] else now + float(rng.uniform(0.03, 0.7))
        inflight = [(tick - int(rng.integers(1, 20)), 0.8, -1e9)]
        for _ in range(int(rng.integers(0, 4))):
            inflight.append((tick - int(rng.integers(0, 8)), 0.8, now + float(rng.uniform(-0.2, 0.5))))
        t0 = time.perf_counter()
        ch = M.plan(now, tick, period, a.horizon, opts, free, idle, inflight, lag, rat, 0.05 if a.price else 0.0)
        times.append((time.perf_counter() - t0) * 1e3)
        k = "none" if ch is None else ch[0]
        chosen[k] = chosen.get(k, 0) + 1
    t = np.array(times[50:])                           # the first calls warm numpy up
    res = {"host": platform.node(), "machine": platform.machine(), "python": platform.python_version(),
           "numpy": np.__version__, "threads": a.threads, "horizon": a.horizon, "price": a.price, "n": len(t),
           "ms_median": float(np.median(t)), "ms_p95": float(np.percentile(t, 95)), "ms_p99": float(np.percentile(t, 99)),
           "ms_max": float(t.max()), "frame_budget_ms": period * 1e3, "chosen": chosen}
    print(json.dumps(res, indent=1))
    if a.out:
        json.dump(res, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
