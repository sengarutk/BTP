#!/usr/bin/env python3
"""Cross-validates the link models of the Python simulator against ns-3 (V1 and V2).

V1  air-to-air 802.11ax goodput versus distance: ns-3 (full PHY/MAC, best fixed MCS and
    IdealWifiManager) against simulation.stream_sim.a2a_rate_mbps.
V2  cellular uplink goodput versus SINR: ns-3 LTE (20 MHz uplink, MI error model, HARQ)
    against the 3GPP TR 36.942 mapping of simulation.trace_generator (same bandwidth).

ns-3 is not a Python dependency: set NS3_DIR to an ns-3.48 tree in which validation/ns3/*.cc are
linked into scratch/ and built (see validation/README.md). Raw ns-3 output is kept so the
comparison can be recomputed without ns-3.

Outputs (experiments/results/validation/): a2a_ns3.csv, a2a_compare.csv, lte_ns3.csv,
lte_compare.csv.
"""

import argparse
import csv
import glob
import math
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from simulation.stream_sim import a2a_rate_mbps
from simulation.trace_generator import attenuated_shannon_se

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "experiments" / "results" / "validation"
NS3_DIR = Path(os.environ.get("NS3_DIR", REPO.parent / "ns3" / "ns-allinone-3.48" / "ns-3.48"))
LTE_BANDWIDTH_MHZ = 20.0  # 100 resource blocks
# ns-3 preamble-detection threshold: the 802.11 minimum sensitivity, and an SNR-limited receiver
# (as assumed by the Python model, whose only limit is the SNR).
RX_SENSITIVITY = {-82.0: "std_min", -100.0: "snr_limited"}


def binary(name: str) -> str:
    hits = sorted(glob.glob(str(NS3_DIR / "build" / "scratch" / f"*{name}*")))
    hits = [h for h in hits if os.access(h, os.X_OK) and not h.endswith(".cc")]
    if not hits:
        raise FileNotFoundError(f"ns-3 binary for {name} not found under {NS3_DIR}/build/scratch; build ns-3 first")
    return hits[0]


def env() -> dict:
    e = dict(os.environ)
    libdirs = [str(NS3_DIR / "build" / "lib")]
    e["LD_LIBRARY_PATH"] = ":".join(libdirs + [e.get("LD_LIBRARY_PATH", "")])
    return e


def write_csv(path: Path, rows, fields) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def run_a2a(distances, seeds, sim_time) -> None:
    raw = OUT / "a2a_ns3.csv"
    if not raw.exists():
        exe = binary("a2a_wifi")

        def one(args):
            d, s, rssi = args
            out = subprocess.run([exe, f"--distances={d}", f"--seed={s}", f"--simTime={sim_time}", f"--minRssi={rssi}"],
                                 capture_output=True, text=True, check=True, env=env()).stdout
            rows = list(csv.DictReader(out.strip().splitlines()))
            for r in rows:
                r["seed"], r["min_rssi_dbm"] = s, rssi
            return rows

        jobs = [(d, s, rssi) for rssi in RX_SENSITIVITY for d in distances for s in range(1, seeds + 1)]
        with ThreadPoolExecutor(max_workers=8) as ex:
            rows = [r for part in ex.map(one, jobs) for r in part]
        write_csv(raw, rows, ["distance_m", "manager", "mcs", "goodput_mbps", "seed", "min_rssi_dbm"])
    rows = list(csv.DictReader(open(raw)))
    cmp_rows = []
    for d in sorted({float(r["distance_m"]) for r in rows}):
        row = {"distance_m": d, "model_mbps": round(a2a_rate_mbps(d), 2)}
        for rssi, tag in RX_SENSITIVITY.items():
            at = [r for r in rows if float(r["distance_m"]) == d and float(r["min_rssi_dbm"]) == rssi]
            best = np.mean([max(float(r["goodput_mbps"]) for r in at if r["manager"] == "constant" and r["seed"] == s)
                            for s in {r["seed"] for r in at}])
            row[f"ns3_{tag}_best_mbps"] = round(best, 2)
            row[f"ns3_{tag}_ideal_mbps"] = round(np.mean([float(r["goodput_mbps"]) for r in at if r["manager"] == "ideal"]), 2)
        cmp_rows.append(row)
    write_csv(OUT / "a2a_compare.csv", cmp_rows, list(cmp_rows[0].keys()))
    for r in cmp_rows:
        print("A2A " + "  ".join(f"{k}={v}" for k, v in r.items()))


def run_lte(distances, seeds, sim_time) -> None:
    raw = OUT / "lte_ns3.csv"
    if not raw.exists():
        exe = binary("lte_uplink")

        def one(args):
            d, s = args
            out = subprocess.run([exe, f"--distance={d}", f"--seed={s}", f"--simTime={sim_time}"],
                                 capture_output=True, text=True, check=True, env=env()).stdout.strip().splitlines()[-1]
            dist, sinr, gp = out.split(",")
            return {"distance_m": float(dist), "seed": s, "sinr_db": float(sinr), "goodput_mbps": float(gp)}

        jobs = [(d, s) for d in distances for s in range(1, seeds + 1)]
        with ThreadPoolExecutor(max_workers=6) as ex:
            rows = list(ex.map(one, jobs))
        write_csv(raw, rows, ["distance_m", "seed", "sinr_db", "goodput_mbps"])
    rows = list(csv.DictReader(open(raw)))
    cmp_rows = []
    for d in sorted({float(r["distance_m"]) for r in rows}):
        at = [r for r in rows if float(r["distance_m"]) == d]
        sinr = np.mean([float(r["sinr_db"]) for r in at])
        gp = np.mean([float(r["goodput_mbps"]) for r in at])
        model = float(attenuated_shannon_se(np.array([sinr]))[0]) * LTE_BANDWIDTH_MHZ
        cmp_rows.append({"distance_m": d, "sinr_db": round(sinr, 2), "ns3_mbps": round(gp, 2),
                         "tr36942_mbps": round(model, 2),
                         "model_over_ns3": round(model / gp, 3) if gp > 0 else (1.0 if model == 0 else math.inf)})
    write_csv(OUT / "lte_compare.csv", cmp_rows, list(cmp_rows[0].keys()))
    for r in cmp_rows:
        print(f"LTE {r['distance_m']:>7.0f} m  SINR {r['sinr_db']:6.1f} dB  ns-3 {r['ns3_mbps']:6.2f}"
              f"  TR36.942 {r['tr36942_mbps']:6.2f}  ratio {r['model_over_ns3']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--which", nargs="+", default=["a2a", "lte"], choices=["a2a", "lte"])
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--sim-time", type=float, default=3.0)
    args = ap.parse_args()
    if "a2a" in args.which:
        run_a2a([10, 25, 50, 100, 150, 200, 300, 400, 500, 600, 700, 800, 900, 1000], args.seeds, args.sim_time)
    if "lte" in args.which:
        run_lte([200, 500, 1000, 2000, 3000, 5000, 8000, 12000, 16000, 20000, 25000, 30000], args.seeds, 2.0)
