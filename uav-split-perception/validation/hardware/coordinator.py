#!/usr/bin/env python3
"""Live swarm coordinator for several camera drones sharing the ground station (the laptop path).

Runs on the laptop and connects out to every camera's coordination port (adaptive2.py --coord-port; the
laptop sits behind WSL2 NAT, so it always connects out). Once per window each camera reports the value of
its laptop path with the link it has seen alone recently (lap_full) and with half of it (lap_half), and the
value of its other servers (other; onboard and the Jetson path run in parallel with the laptop path).
Mode "admission" (as coordination="admission" in simulation/stream_sim.py, for a ground link):
  * K = number of cameras that may use the laptop path in the next window, chosen to maximise the expected
    swarm value: K cameras sharing the link (value lap at full / K, with lap_half for K >= 2) plus every
    camera's other servers; the admitted set rotates round-robin, so on average each camera gets K/N windows.
  * Admitted cameras get no cap; the others may not use the laptop path for that window.
Mode "none": the same reports and messages, every camera always admitted (the uncoordinated baseline with
identical overhead). Every report and decision is logged.
usage: coordinator.py --cameras HOST:PORT,HOST:PORT [--mode admission|none] --duration S --out log.json
"""
import argparse
import json
import socket
import threading
import time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cameras", required=True)
    ap.add_argument("--mode", default="admission", choices=["admission", "none"])
    ap.add_argument("--window", type=float, default=1.0)
    ap.add_argument("--duration", type=float, required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cams = a.cameras.split(",")
    conns = {}
    for c in cams:                                   # cameras start their port once they are up: retry
        h, p = c.split(":")
        for _ in range(240):
            try:
                s = socket.create_connection((h, int(p)), timeout=2.0)
                s.settimeout(5.0)
                conns[c] = s.makefile("rwb")
                break
            except OSError:
                time.sleep(0.5)
        else:
            raise SystemExit(f"camera {c} unreachable")
    log, rr, t_end = [], 0, time.time() + a.duration
    lock = threading.Lock()
    while time.time() < t_end and conns:
        t0 = time.time()
        reps = {}
        for c, f in list(conns.items()):
            try:
                line = f.readline()
                if not line:
                    raise OSError("closed")
                reps[c] = json.loads(line)
            except (OSError, ValueError):
                conns.pop(c, None)
        n = len(reps)
        if not n:
            break
        order = [c for c in cams if c in reps]
        if a.mode == "none":
            k = n
        else:
            def value(k):
                if k == 0:
                    return sum(r["other"] for r in reps.values())
                lap = "lap_full" if k == 1 else "lap_half"
                # k cameras admitted on rotation: each camera is admitted k/n of the windows
                return sum(r["other"] + k / n * max(0.0, r[lap]) for r in reps.values())
            k = max(range(0, n + 1), key=lambda kk: (value(kk), kk))
        admitted = {order[(rr + i) % n] for i in range(k)}
        rr = (rr + k) % n if k else rr
        for c in order:
            try:
                conns[c].write((json.dumps({"allowed": c in admitted, "share": None}) + "\n").encode())
                conns[c].flush()
            except OSError:
                conns.pop(c, None)
        with lock:
            log.append({"t": t0, "k": k, "admitted": sorted(admitted), "reports": reps})
        time.sleep(max(0.0, a.window - (time.time() - t0)))
    json.dump({"mode": a.mode, "cameras": cams, "window_s": a.window, "log": log}, open(a.out, "w"))
    print(json.dumps({"mode": a.mode, "windows": len(log),
                      "mean_k": sum(x["k"] for x in log) / max(1, len(log))}))


if __name__ == "__main__":
    main()
