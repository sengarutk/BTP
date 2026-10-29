#!/usr/bin/env python3
"""Laptop-side link outages during the mesh2 runs (24 Oct 2026). The laptop's own path to pi-sender (Windows/WSL
NAT -> cable) dropped packets at times; this is not a planned impairment, so a run overlapping such an outage is not
a fair measurement of its strategy. Reads the 1 s ping log (ping -D -O to pi-sender, started 01:21 UTC 24 Oct) and,
per run, the run window (first to last camera link event, epoch s). Prints per run: lost pings inside the window and
the longest outage (consecutive lost pings). Runs before the ping log started are reported as "not covered".
usage: mesh2_outage_check.py [--dir vid_campaign_mesh2] [--min-outage-s 5]   (exit code 1 if any run is over)
"""
import argparse
import glob
import json
import re
import sys

from report_rescore import HW


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default="vid_campaign_mesh2")
    ap.add_argument("--ping", default=str(HW / "vid_campaign_mesh2_laptop_ping.txt"))
    ap.add_argument("--min-outage-s", type=float, default=5.0)
    a = ap.parse_args()
    pings = []                      # (epoch, ok)
    for line in open(a.ping):
        m = re.match(r"\[(\d+\.\d+)\] (.*)", line)
        if m:
            pings.append((float(m.group(1)), "no answer" not in m.group(2)))
    t_log = pings[0][0] if pings else float("inf")
    bad = 0
    for f in sorted(glob.glob(str(HW / a.dir / "a2_*__r*.json"))):
        d = json.load(open(f))
        ts = [t for ev in d["link_events"].values() for t, _ in ev]
        t0, t1 = min(ts), max(ts)
        name = f.rsplit("/a2_", 1)[1][:-5]
        if t0 < t_log:
            print(f"{name:30s} not covered (before the ping log)")
            continue
        run, longest, lost = 0, 0, 0
        for t, ok in pings:
            if t0 <= t <= t1:
                lost += not ok
                run = 0 if ok else run + 1
                longest = max(longest, run)
        flag = longest >= a.min_outage_s
        bad += flag
        print(f"{name:30s} lost {lost:3d} pings, longest outage {longest:3d} s{'   <-- OUTAGE' if flag else ''}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
