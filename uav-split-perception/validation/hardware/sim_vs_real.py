#!/usr/bin/env python3
"""Simulator against the hardware: does simulation/stream_sim.py predict what the live runs measured?

For every live run of a fixed single-path strategy (JPEG q90 to the laptop or to the Jetson), the run's own
link is rebuilt as a simulator trace, without any fitting:
  * unimpaired phases: the median goodput the camera measured on that path during the run's unimpaired phases
  * netem "rate X" phases: min(X, that goodput); "loss 100%": 0
  * payload: the run's median JPEG size; onboard time: JPEG encoding (3.5 ms); server time: the measured
    priors of adaptive2.py (decode + model + NMS); one-way delay: half the path's measured round trip
  * protocol: the live controller hands a path its next frame only after the previous result has returned
    (one frame in flight per path). With --stop-and-wait the simulator holds the link for server time + round
    trip after each frame (release_extra_ms); without it, the simulator pipelines (its default).
Also reported, from the runs themselves: how long after a blackout the first result arrives again.
The simulator (one UAV, newest-frame-wins buffer, 300 ms deadline, 30 fps camera) predicts on-time frames/s
per phase, which is compared with the measured value. Phases are grouped as unimpaired, rate-limited,
blackout, and unimpaired-after-a-blackout (where TCP recovery matters, which the simulator does not model).
usage: sim_vs_real.py RUN_DIR [RUN_DIR ...]  -> experiments/results/hardware/sim_vs_real.json
"""
import glob
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from simulation.stream_sim import SimParams, StreamSimulator  # noqa: E402
from simulation.system_model import EdgeHardware, OffloadConfig  # noqa: E402

POLICIES = {"fixed:laptop:m640q90": ("laptop", 24.0), "fixed:jetson:s640q90": ("jetson", 32.0)}
RTT_MS = {"laptop": 4.9, "jetson": 2.7}           # measured round trips (docs/hardware_results.md)
ENC_MS, SLOT = 3.5, 10.0


def rate_of(imp, base):
    if not imp:
        return base
    if "loss 100%" in imp:
        return 0.0
    m = re.search(r"rate ([\d.]+)mbit", imp)
    return min(float(m.group(1)), base) if m else base


STOP_AND_WAIT = "--stop-and-wait" in sys.argv
# --netem-persist: the phases' TRUE conditions. adaptive.tc_phase changes each path's netem qdisc with only the new
# phase's arguments; netem then resets loss but KEEPS the previous rate limit (checked on the Pi, 12 Oct 2026), so a
# phase without a "rate" keeps the last one. Without this flag the phases are taken as described (the original check).
PERSIST = "--netem-persist" in sys.argv


def effective_impairments(phases, path):
    """Per phase, the netem state the path really had: (loss 100 %?, rate cap in Mbit/s or None)."""
    out, cap = [], None
    for _, ph in phases:
        imp = ph["impair"].get(path) or ""
        m = re.search(r"rate ([\d.]+)mbit", imp)
        if m:
            cap = float(m.group(1))
        out.append(("loss 100%" in imp, cap if PERSIST else (float(m.group(1)) if m else None)))
    return out


def eff_rate(loss, cap, base):
    return 0.0 if loss else (min(cap, base) if cap else base)


def one(run_path):
    r = json.load(open(run_path))
    if r["policy"] not in POLICIES:
        return None
    path, server_ms = POLICIES[r["policy"]]
    phases = list(r["per_phase"].items())
    durs = [20.0 if not k.startswith("r") or "_L" not in k else 4.0 for k, _ in phases]
    # unimpaired goodput of this path, measured by the camera during the run's unimpaired phases
    t0 = r["link_goodput_samples"][path][0][0] if r["link_goodput_samples"][path] else 0
    good_t, edges = [], np.cumsum([0.0] + durs)
    eff = effective_impairments(phases, path)
    for (loss, cap), lo, hi in zip(eff, edges[:-1], edges[1:]):
        if not loss and cap is None:
            good_t.append((lo, hi))
    samp = [v for t, v in r["link_goodput_samples"][path] if any(lo <= t - t0 < hi for lo, hi in good_t)]
    base = float(np.median(samp)) if samp else 20.0
    bytes_ = float(np.median([f["bytes"] for f in r["frames"] if f.get("bytes")]))
    cfg = OffloadConfig(name="hw", kind="codec", cut=-1, dtype="jpeg", payload_bytes=bytes_, edge_flop_frac=0.0,
                        host_edge_proc_ms=ENC_MS, cloud_ms=server_ms, map50_95=0.44, map50=0.6, delta_map50_95=0.0)
    hw = EdgeHardware(name="pi5", t_full_ms=758.0, host_full_ms=758.0)
    total = float(edges[-1])
    p = SimParams(hw=hw, configs={"hw": cfg}, mode="hw", n_uavs=1, duration_s=total, seed=0,
                  release_extra_ms=(server_ms + RTT_MS[path]) if STOP_AND_WAIT else 0.0)
    sim = StreamSimulator(p)
    n = int(total * 1000 / SLOT)
    bw = np.zeros(n)
    for (loss, cap), lo, hi in zip(eff, edges[:-1], edges[1:]):
        bw[int(lo * 100):int(hi * 100)] = eff_rate(loss, cap, base)
    u = sim.uavs[0]
    u.bw, u.delay, u.loss = bw, np.full(n, RTT_MS[path] / 2), np.zeros(n)
    sim.run()
    out = []
    after_blackout = False
    t_res = sorted(f["t_res"] for f in r["frames"] if f.get("t_res") is not None and f.get("server") == path)
    for (name, ph), (loss, cap), lo, hi in zip(phases, eff, edges[:-1], edges[1:]):
        fr = [f for f in u.frames if lo * 1e3 <= f.capture_ms < hi * 1e3]
        pred = sum(f.status == "delivered" and f.latency_ms <= 300 for f in fr) / (hi - lo)
        imp = ph["impair"].get(path)
        kind = ("blackout" if loss else "rate_limited" if cap else
                "unimpaired_after_blackout" if after_blackout else "unimpaired")
        # measured on-time frames/s of this path only (the fixed policies use one path)
        row = {"run": f"{Path(run_path).parent.name}/{Path(run_path).stem}", "policy": r["policy"], "phase": name, "kind": kind,
               "measured": ph["on_time_fps"], "predicted": pred, "rate_mbps": eff_rate(loss, cap, base)}
        if kind == "unimpaired_after_blackout" and after_blackout and out and out[-1]["kind"] == "blackout":
            nxt = [t for t in t_res if t >= lo]          # first result after the link came back
            row["recovery_s"] = float(nxt[0] - lo) if nxt and nxt[0] < hi else float(hi - lo)
        out.append(row)
        after_blackout = after_blackout or kind == "blackout"
    return out


def main(dirs):
    dirs = [d for d in dirs if not d.startswith("--")]
    rows = []
    for d in dirs:
        for f in sorted(glob.glob(f"{d}/a2_*__r*.json")):
            res = one(f)
            if res:
                rows += res
    summ = {}
    for kind in ("unimpaired", "rate_limited", "blackout", "unimpaired_after_blackout", "all", "all_but_recovery"):
        sel = [x for x in rows if kind == "all" or x["kind"] == kind or
               (kind == "all_but_recovery" and x["kind"] != "unimpaired_after_blackout")]
        if not sel:
            continue
        m, pr = np.array([x["measured"] for x in sel]), np.array([x["predicted"] for x in sel])
        summ[kind] = {"n": len(sel), "measured_mean": float(m.mean()), "predicted_mean": float(pr.mean()),
                      "mae_fps": float(np.abs(m - pr).mean()),
                      "corr": float(np.corrcoef(m, pr)[0, 1]) if len(sel) > 2 and m.std() > 0 and pr.std() > 0 else None}
    rec = [x["recovery_s"] for x in rows if "recovery_s" in x]
    if rec:
        summ["recovery_after_blackout_s"] = {"n": len(rec), "median": float(np.median(rec)),
                                             "p90": float(np.percentile(rec, 90)),
                                             "never_within_phase": int(sum(x >= 19.9 for x in rec))}
        print("recovery after blackout (s):", summ["recovery_after_blackout_s"])
    name = ("sim_vs_real_stopwait" if STOP_AND_WAIT else "sim_vs_real") + ("_persist" if PERSIST else "") + ".json"
    json.dump({"rows": rows, "summary": summ}, open(ROOT / "experiments/results/hardware" / name, "w"), indent=1)
    summ["runs"] = len({x["run"] for x in rows})
    print("runs:", summ["runs"], "phases:", len(rows))
    for k, v in summ.items():
        if not isinstance(v, dict) or "mae_fps" not in v:
            continue
        print(f"{k:28s} n={v['n']:3d} measured {v['measured_mean']:6.2f}  predicted {v['predicted_mean']:6.2f}  "
              f"MAE {v['mae_fps']:5.2f} fps  r={v['corr'] if v['corr'] is None else round(v['corr'], 3)}")


if __name__ == "__main__":
    main(sys.argv[1:])
