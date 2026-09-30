#!/usr/bin/env python3
"""Cross-validation with OMNeT++ 6.3 / INET 4.5.4 / Simu5G 1.5.2 (O1, O2, O2b; O3 in run_omnetpp_stream.py).

O1  5G NR uplink goodput versus the uplink SINR (single UAV, distance sweep), compared with the
    TR 36.942 mapping of the traces and with ns-3 LTE (V2).
O2  N saturated UAVs sharing one gNB uplink with a proportional-fair scheduler: per-UAV goodput,
    Jain fairness, and the water-filling prediction C/N (C = measured cell goodput).
O2b 5 UAVs with a small constant demand and 5 saturated UAVs: water-filling predicts the small
    demands are served in full and the saturated UAVs share the rest equally.

Needs the three frameworks built as in validation/README.md and OMNET_ENV pointing at a shell file
that sets them up (default /home/sengar/BTP/omnet/env.sh). Raw .sca files are parsed directly.
Output: experiments/results/validation/omnet_{rate_vs_sinr,cell_sharing,cell_sharing_mixed}.csv
"""

import argparse
import csv
import os
import re
import shlex
import subprocess
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from simulation.trace_generator import attenuated_shannon_se
from validation.run_link_validation import OUT, write_csv

REPO = Path(__file__).resolve().parent.parent
SIMDIR = REPO / "validation" / "omnetpp" / "simu5g"
ENV = os.environ.get("OMNET_ENV", "/home/sengar/BTP/omnet/env.sh")
MEASURE_S = 5.0          # sim-time-limit 6 s minus warm-up 1 s
BANDWIDTH_MHZ = 20.0


def runs_of(config: str) -> int:
    out = subprocess.run(["bash", "-c", f"source {ENV}; cd {SIMDIR}; simu5g -f omnetpp.ini -c {config} -q numruns"],
                         capture_output=True, text=True, check=True).stdout
    return int(re.search(r"Number of runs:\s*(\d+)", out).group(1))


def run(config: str, r: int) -> None:
    """One run; a marker file makes interrupted batches resume where they stopped."""
    marker = SIMDIR / "results" / "done" / f"{config}-{r}"
    if marker.exists():
        return
    # A 4 GB address-space cap per run: a runaway simulation fails on its own instead of exhausting
    # the machine's memory.
    subprocess.run(["bash", "-c", f"source {ENV}; cd {SIMDIR}; ulimit -v 4000000; simu5g -u Cmdenv -f omnetpp.ini "
                                  f"-c {config} -r {r} --cmdenv-express-mode=true > /dev/null 2>&1"], check=True)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.touch()


def parse(sca: Path):
    itervars, scal = {}, {}
    for line in sca.read_text().splitlines():
        try:
            p = shlex.split(line)  # scalar names may contain quoted spaces
        except ValueError:
            continue
        if p[:1] == ["itervar"]:
            itervars[p[1]] = float(p[2])
        elif p[:1] == ["attr"] and p[1] == "repetition":
            itervars["rep"] = int(p[2])
        elif p[:1] == ["scalar"] and len(p) >= 4:
            try:
                scal[(p[1], p[2])] = float(p[3])
            except ValueError:
                scal[(p[1], p[2])] = float("nan")
    return itervars, scal


def execute(config: str, workers: int, rerun: bool = True):
    n = runs_of(config) if rerun else 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(lambda r: run(config, r), range(n)))
    return [parse(f) for f in sorted((SIMDIR / "results").glob(f"{config}-*.sca"))]


def app_mbps(scal, i):
    return scal[(f"SingleCell_Standalone.server.app[{i}]", "packetReceived:sum(packetBytes)")] * 8 / MEASURE_S / 1e6


def o1(workers):
    res = execute("RateVsSinr", workers)
    by = defaultdict(list)
    for it, sc in res:
        sinr = sc[("SingleCell_Standalone.ue[0].cellularNic.nrChannelModel[0]", "rcvdSinrUl:mean")]
        by[it["d"]].append((sinr, app_mbps(sc, 0)))
    ns3 = {}
    lte = OUT / "lte_compare.csv"
    if lte.exists():
        rows = sorted((float(r["sinr_db"]), float(r["ns3_mbps"])) for r in csv.DictReader(open(lte)))
        xs, ys = np.array([a for a, _ in rows]), np.array([b for _, b in rows])
        ns3 = lambda s: float(np.interp(s, xs, ys, left=0.0, right=float(ys[-1])))  # noqa: E731
    out = []
    for d in sorted(by):
        sinr = float(np.nanmean([a for a, _ in by[d]]))
        gp = float(np.mean([b for _, b in by[d]]))
        model = float(attenuated_shannon_se(np.array([sinr]))[0]) * BANDWIDTH_MHZ
        out.append({"distance_m": d, "sinr_db": round(sinr, 2), "simu5g_nr_mbps": round(gp, 2),
                    "tr36942_mbps": round(model, 2), "ns3_lte_mbps_at_sinr": round(ns3(sinr), 2) if ns3 else "",
                    "reps": len(by[d])})
    write_csv(OUT / "omnet_rate_vs_sinr.csv", out, list(out[0].keys()))
    for r in out:
        print("O1", r)


def o2(workers):
    res = execute("CellSharing", workers)
    by = defaultdict(list)
    for it, sc in res:
        n = int(it["N"])
        by[n].append([app_mbps(sc, i) for i in range(n)])
    out = []
    for n in sorted(by):
        per = np.array(by[n])                 # reps x UAVs
        total = per.sum(axis=1).mean()
        mean_ue = per.mean()
        jain = float(np.mean([(r.sum() ** 2) / (len(r) * (r ** 2).sum()) for r in per]))
        out.append({"n_uavs": n, "cell_goodput_mbps": round(float(total), 2), "per_uav_mean_mbps": round(float(mean_ue), 2),
                    "per_uav_min_mbps": round(float(per.min()), 2), "per_uav_max_mbps": round(float(per.max()), 2),
                    "waterfill_prediction_mbps": round(float(total) / n, 2), "jain_fairness": round(jain, 4)})
    write_csv(OUT / "omnet_cell_sharing.csv", out, list(out[0].keys()))
    for r in out:
        print("O2", r)


def o2b(workers):
    res = execute("CellSharingMixed", workers)
    sharing = {int(r["n_uavs"]): float(r["cell_goodput_mbps"]) for r in csv.DictReader(open(OUT / "omnet_cell_sharing.csv"))}
    capacity = sharing[10]                    # all 10 saturated: the cell's goodput at this SINR
    by = defaultdict(list)
    for it, sc in res:
        by[it["rate"]].append([app_mbps(sc, i) for i in range(10)])
    out = []
    for rate in sorted(by):
        per = np.array(by[rate])
        small, big = per[:, :5].mean(), per[:, 5:].mean()
        predicted_big = (capacity - 5 * min(rate, capacity / 10)) / 5
        out.append({"small_demand_mbps": rate, "small_got_mbps": round(float(small), 3),
                    "saturated_got_mbps": round(float(big), 2), "waterfill_saturated_mbps": round(predicted_big, 2),
                    "cell_capacity_mbps": round(capacity, 2)})
    write_csv(OUT / "omnet_cell_sharing_mixed.csv", out, list(out[0].keys()))
    for r in out:
        print("O2b", r)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--which", nargs="+", default=["o1", "o2", "o2b"])
    ap.add_argument("--workers", type=int, default=2)  # keeps several 20-UAV runs within memory
    a = ap.parse_args()
    for w in a.which:
        {"o1": o1, "o2": o2, "o2b": o2b}[w](a.workers)
