#!/usr/bin/env python3
"""O5: the two-hop relay path in ns-3 (validation/ns3/relay.cc) against the Python relay model.

Hop 1 (A2A): time to move one frame from the weak UAV A to its neighbour B over 802.11ax with TCP,
    against payload / a2a_rate_mbps(distance) in simulation/stream_sim.py.
Whole path: frame latency A -> B -> server when B's uplink (rate R, one-way delay D) is idle, or
    also carries B's own saturated flow, against the Python model's
        payload / a2a_rate + payload / (R_goodput / flows on B) + D,
    where R_goodput = R x 1400 / 1454 (TCP/IP/PPP headers per 1400-byte segment). The Python model
    forwards whole frames; ns-3 forwards packet by packet, so its hops overlap and the Python sum is
    an upper bound; max(hop 1, hop 2) + D, the pipelined counterpart, is reported beside it.

Output: experiments/results/validation/relay_hop1.csv, relay_path.csv, relay_summary.json
"""

import argparse
import csv
import io
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from simulation.stream_sim import a2a_rate_mbps
from validation.run_link_validation import OUT, binary, env, write_csv

PAYLOADS = {"split_k4_int8_zstd": 318122, "jpeg_q90": 93211}
HOP1_DISTANCES = [25, 50, 100, 200, 300, 400, 500, 600]
PATH_DISTANCES = [100, 300, 500]
UPLINK_MBPS, DELAY_MS = 20.0, 20.0
HEADER_EFF = 1400 / 1454
DEADLINE_MS = 300.0


def run(args):
    out = subprocess.run([binary("relay")] + [f"--{k}={v}" for k, v in args.items()],
                         capture_output=True, text=True, check=True, env=env()).stdout
    return next(csv.DictReader(io.StringIO(out)))


def main(workers, frames):
    hop_jobs = [dict(distance=d, payload=p, sink="b", frames=frames) for d in HOP1_DISTANCES for p in PAYLOADS.values()]
    path_jobs = [dict(distance=d, payload=p, sink="s", bOwn=str(own).lower(), frames=frames,
                      uplinkMbps=UPLINK_MBPS, delayMs=DELAY_MS)
                 for d in PATH_DISTANCES for p in PAYLOADS.values() for own in (False, True)]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        hop = list(ex.map(run, hop_jobs))
        path = list(ex.map(run, path_jobs))
    name = {v: k for k, v in PAYLOADS.items()}

    hop_rows = []
    for r in hop:
        d, p = float(r["distance_m"]), int(r["payload_bytes"])
        py = p * 8 / (a2a_rate_mbps(d) * 1e3)
        ns = float(r["lat_mean_ms"])
        hop_rows.append({"distance_m": d, "payload": name[p], "ns3_ms": round(ns, 2), "python_ms": round(py, 2),
                         "ns3_goodput_mbps": round(p * 8 / (ns * 1e3), 2), "python_goodput_mbps": round(a2a_rate_mbps(d), 2),
                         "python_over_ns3": round(py / ns, 3), "ns3_p95_ms": round(float(r["lat_p95_ms"]), 2)})
    write_csv(OUT / "relay_hop1.csv", hop_rows, list(hop_rows[0].keys()))

    path_rows = []
    for r in path:
        d, p, own = float(r["distance_m"]), int(r["payload_bytes"]), r["b_own"] == "1"
        h1 = p * 8 / (a2a_rate_mbps(d) * 1e3)
        h2 = p * 8 / (UPLINK_MBPS * HEADER_EFF / (2 if own else 1) * 1e3)
        ns = float(r["lat_mean_ms"])
        path_rows.append({"distance_m": d, "payload": name[p], "b_own_flow": own, "ns3_ms": round(ns, 2),
                          "ns3_p95_ms": round(float(r["lat_p95_ms"]), 2),
                          "python_ms": round(h1 + h2 + DELAY_MS, 2), "pipelined_ms": round(max(h1, h2) + DELAY_MS, 2),
                          "python_over_ns3": round((h1 + h2 + DELAY_MS) / ns, 3),
                          "ns3_within_deadline": ns + 0 <= DEADLINE_MS, "python_within_deadline": h1 + h2 + DELAY_MS <= DEADLINE_MS})
    write_csv(OUT / "relay_path.csv", path_rows, list(path_rows[0].keys()))

    ratio_h = [r["python_over_ns3"] for r in hop_rows]
    ratio_p = [r["python_over_ns3"] for r in path_rows]
    pipe = [abs(r["pipelined_ms"] - r["ns3_ms"]) / r["ns3_ms"] for r in path_rows]
    summary = {
        "hop1_python_over_ns3_range": [min(ratio_h), max(ratio_h)],
        "hop1_python_conservative_all": all(x >= 1.0 for x in ratio_h),
        "path_python_over_ns3_range": [min(ratio_p), max(ratio_p)],
        "path_python_conservative_all": all(x >= 1.0 for x in ratio_p),
        "path_pipelined_mean_abs_rel_err": round(float(np.mean(pipe)), 3),
        "deadline_verdict_agree": sum(r["ns3_within_deadline"] == r["python_within_deadline"] for r in path_rows),
        "deadline_cases": len(path_rows),
        "split_relayed_with_b_own_ns3_ms": {int(r["distance_m"]): r["ns3_ms"] for r in path_rows
                                            if r["payload"] == "split_k4_int8_zstd" and r["b_own_flow"]},
    }
    (OUT / "relay_summary.json").write_text(json.dumps(summary, indent=1))
    for r in hop_rows + path_rows:
        print(r)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--frames", type=int, default=30)
    a = ap.parse_args()
    main(a.workers, a.frames)
