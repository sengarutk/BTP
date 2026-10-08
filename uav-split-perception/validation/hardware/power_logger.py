#!/usr/bin/env python3
"""Live board power and temperature logger for a run (used on the Jetson, the edge drone, by tools/arun.sh).

Samples whole-board power (Jetson INA3221 VDD_IN; Pi PMIC rails) and the hottest thermal zone at 5 Hz for
--duration seconds; writes the trace and its integral (energy) to --out, rewriting the file every 10 s so a
dropped connection loses at most 10 s.
"""
import argparse
import json
import time

from energy_profile import read_power, read_temp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="jetson", choices=["jetson", "pi"])
    ap.add_argument("--duration", type=float, required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    log, t0, last = [], time.time(), 0.0

    def dump():
        ok = [x for x in log if x[1] == x[1]]
        e = sum((b[0] - a_[0]) * (a_[1] + b[1]) / 2 for a_, b in zip(ok, ok[1:]))
        dur = ok[-1][0] - ok[0][0] if len(ok) > 1 else 0.0
        temps = [x[2] for x in ok if x[2] == x[2]]
        json.dump({"device": a.device, "energy_j": e, "mean_w": e / dur if dur else None, "duration_s": dur,
                   "temp_max_c": max(temps) if temps else None,
                   "temp_mean_c": sum(temps) / len(temps) if temps else None,
                   "t0_unix": t0, "log_t_w_c": [(round(x[0], 2), round(x[1], 3), round(x[2], 2)) for x in ok]},
                  open(a.out, "w"))

    while time.time() - t0 < a.duration:
        try:
            log.append((time.time() - t0, read_power(a.device), read_temp()))
        except Exception:
            pass
        if time.time() - last >= 10.0:
            dump()
            last = time.time()
        time.sleep(0.2)
    dump()


if __name__ == "__main__":
    main()
