#!/usr/bin/env python3
"""O4: air-to-air 802.11ac link, INET 4.5.4 (OMNeT++) against ns-3 and the Python A2A model.

INET has no 802.11ax and its DCF sends one MPDU per channel access, so both simulators run
802.11ac (VHT MCS 0-8, 20 MHz, one stream, 800 ns guard interval) without aggregation, with the
radio assumptions of the Python model: 20 dBm, channel 157, log-distance path loss (exponent 2.2,
free space at 1 m), -95 dBm noise, SNR-limited receiver. The run is a check of the PHY side of the
Python model: for every MCS, the distance up to which the link carries it. The Python model
predicts that range from its per-MCS SNR thresholds (A2A_MCS, PER 10 % at threshold); INET uses the
NIST error model, ns-3 its table-based model.

For each (distance, MCS) the goodput is normalised by the same MCS's goodput at 10 m, which
removes the MAC overhead (which differs between the two simulators and is covered by V1);
Python's counterpart is 1 - PER. The range of an MCS is the largest grid distance at which the
normalised goodput is at least 0.5.

Output: experiments/results/validation/omnet_a2a.csv, omnet_a2a_summary.json
"""

import argparse
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from simulation.stream_sim import A2A_MCS, a2a_per, a2a_snr_db
from validation.run_link_validation import OUT, binary, write_csv
from validation.run_omnetpp_validation import ENV, parse

REPO = Path(__file__).resolve().parent.parent
INETDIR = REPO / "validation" / "omnetpp" / "inet_a2a"
RESULTS = INETDIR / "results"
MEASURE_S = 3.0                      # sim-time-limit 4 s minus warm-up 1 s
VHT_RATES = [6.5, 13, 19.5, 26, 39, 52, 58.5, 65, 78]   # VHT MCS 0-8, 20 MHz, 1 stream, long GI
OPP = f"source {ENV}; cd {INETDIR}; opp_run -l $INET_ROOT/src/INET -n $INET_ROOT/src:. -u Cmdenv -f omnetpp.ini"


def inet(workers):
    out = subprocess.run(["bash", "-c", f"{OPP} -q numruns"], capture_output=True, text=True, check=True).stdout
    n = int(re.search(r"Number of runs:\s*(\d+)", out).group(1))

    def one(r):
        subprocess.run(["bash", "-c", f"{OPP} -r {r} --cmdenv-express-mode=true > /dev/null 2>&1"], check=True)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(one, range(n)))
    res = {}
    for f in RESULTS.glob("General-*.sca"):
        it, sc = parse(f)
        mcs = VHT_RATES.index(it["rate"])
        res[(it["d"], mcs)] = sc.get(("A2A.uav[1].app[0]", "packetReceived:sum(packetBytes)"), 0.0) * 8 / MEASURE_S / 1e6
    return res


def ns3(distances):
    cmd = [binary("a2a_wifi"), "--standard=ac", "--minRssi=-100", "--aggregation=false",
           "--distances=" + ",".join(str(int(d)) for d in distances)]
    res = {}
    for line in subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.splitlines()[1:]:
        d, manager, mcs, gp = line.split(",")
        if manager == "constant":
            res[(float(d), int(mcs))] = float(gp)
    return res


def main(workers):
    gi = inet(workers)
    distances = sorted({d for d, _ in gi})
    gn = ns3(distances)
    rows = []
    for d in distances:
        snr = a2a_snr_db(d, f_ghz=5.785)
        for m, rate in enumerate(VHT_RATES):
            pn = 1.0 - a2a_per(snr, A2A_MCS[m][0])
            rows.append({"distance_m": d, "mcs": m, "phy_mbps": rate, "inet_mbps": round(gi[(d, m)], 3),
                         "ns3_mbps": round(gn[(d, m)], 3), "python_snr_db": round(snr, 2),
                         "inet_norm": round(gi[(d, m)] / gi[(distances[0], m)], 4),
                         "ns3_norm": round(gn[(d, m)] / gn[(distances[0], m)], 4), "python_norm": round(pn, 4)})
    write_csv(OUT / "omnet_a2a.csv", rows, list(rows[0].keys()))

    def rng(key, m):
        ok = [r["distance_m"] for r in rows if r["mcs"] == m and r[key] >= 0.5]
        return max(ok) if ok else 0.0

    ranges = {m: {k: rng(k + "_norm", m) for k in ("inet", "ns3", "python")} for m in range(len(VHT_RATES))}
    a = np.array([r["inet_norm"] for r in rows])
    b = np.array([r["ns3_norm"] for r in rows])
    c = np.array([r["python_norm"] for r in rows])
    at10 = {m: {"inet": round(gi[(distances[0], m)], 2), "ns3": round(gn[(distances[0], m)], 2)} for m in ranges}
    summary = {
        "range_m_by_mcs": ranges,
        "goodput_10m_by_mcs": at10,
        "inet_over_ns3_at_10m": [round(gi[(distances[0], m)] / gn[(distances[0], m)], 3) for m in ranges],
        "mean_abs_norm_diff": {"inet_ns3": round(float(np.mean(np.abs(a - b))), 3),
                               "inet_python": round(float(np.mean(np.abs(a - c))), 3),
                               "ns3_python": round(float(np.mean(np.abs(b - c))), 3)},
        "max_range_m": {k: max(v[k] for v in ranges.values()) for k in ("inet", "ns3", "python")},
    }
    (OUT / "omnet_a2a_summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers", type=int, default=8)
    main(ap.parse_args().workers)
