#!/usr/bin/env python3
"""Audit of the receiver fault (fixed 23 Oct 2026, adaptive.py SO_SNDTIMEO): before the fix the camera's receiver
thread could end on a live link (settimeout race), so results of a path were lost until the next reconnect while
frames kept going out. Signature: results lost on a path in a phase where that path is NOT impaired.

Per run and remote path: frames sent and results lost in clean phases (no netem impairment on that path; the first
3 s of each phase skipped, a reconnect after a blackout is normal), and "dead streaks": >= 30 consecutive frames
sent on that path in clean phases without a result (>= 1 s at 30 fps). A run is AFFECTED if any path has a dead
streak. Per campaign x policy: runs, affected runs, clean-phase loss.
usage: receiver_fault_audit.py [campaign dirs...]   -> receiver_fault_audit.json / .md
"""
import collections
import glob
import json
import multiprocessing as mp
import sys

from report_rescore import HW

CAMPAIGNS = ["vid_campaign_main", "vid_campaign_energy", "vid_campaign_v42", "vid_campaign_wifi", "vid_campaign_wifi_fc",
             "vid_campaign_wifi_fc2", "vid_campaign_table", "vid_campaign_long", "vid_campaign_b", "vid_campaign_mesh",
             "vid_campaign_mesh2", "vid_campaign_mesh2_long"]
SKIP = 90          # frames at the start of each phase
STREAK = 30


def audit(f):
    d = json.load(open(f))
    imp = {ph: v.get("impair", {}) or {} for ph, v in d["per_phase"].items()}
    out = {}
    start, prev = {}, None
    for i, x in enumerate(d["frames"]):
        if x.get("phase") != prev:
            prev = x.get("phase")
            start[i] = True
    paths = {x["server"] for x in d["frames"] if x.get("server") and x["server"] != "onboard"}
    for p in paths:
        sent = lost = run = longest = streaks = 0
        since = 0
        for i, x in enumerate(d["frames"]):
            since = 0 if i in start else since + 1
            if p in imp.get(x.get("phase"), {}) or since < SKIP:
                run = 0
                continue
            if x.get("server") != p:
                continue
            sent += 1
            if x.get("lat_ms") is None:
                lost += 1
                run += 1
                if run == STREAK:
                    streaks += 1
                longest = max(longest, run)
            else:
                run = 0
        out[p] = {"sent": sent, "lost": lost, "streaks": streaks, "longest": longest}
    stem = f.rsplit("/", 1)[1][:-5]
    return f.split("/")[-2], stem, d.get("policy"), out


def main():
    camps = sys.argv[1:] or CAMPAIGNS
    files = [f for c in camps for f in sorted(glob.glob(str(HW / c / "a2_*.json")))]
    with mp.get_context("fork").Pool(8) as pool:
        res = pool.map(audit, files, chunksize=4)
    runs = [{"campaign": c, "run": s, "policy": pol, "paths": o,
             "affected": any(v["streaks"] for v in o.values())} for c, s, pol, o in res]
    cells = collections.defaultdict(lambda: {"runs": 0, "affected": 0, "sent": 0, "lost": 0})
    for r in runs:
        name = r["run"].split("__")[1] if r["run"].count("__") >= 2 else r["policy"]
        for key in ((r["campaign"], name), (r["campaign"], "ALL")):
            c = cells[key]
            c["runs"] += 1
            c["affected"] += r["affected"]
            c["sent"] += sum(v["sent"] for v in r["paths"].values())
            c["lost"] += sum(v["lost"] for v in r["paths"].values())
    out = {"runs": runs, "cells": {f"{c}|{p}": v for (c, p), v in sorted(cells.items())}}
    json.dump(out, open(HW / "receiver_fault_audit.json", "w"), indent=1)
    md = ["# Receiver fault audit (results lost on unimpaired paths)\n",
          "| campaign | strategy | runs | affected runs (>= 1 s dead streak) | clean-phase results lost |", "|---|---|---|---|---|"]
    for (c, p), v in sorted(cells.items()):
        md.append(f"| {c} | {p} | {v['runs']} | {v['affected']} | {100 * v['lost'] / max(v['sent'], 1):.2f} % |")
    (HW / "receiver_fault_audit.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
