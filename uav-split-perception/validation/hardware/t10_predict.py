#!/usr/bin/env python3
"""Plan T10 (14 Nov 2026): the PREDICTION step of predict-then-measure, from board-measured inputs only.

Inputs: split_live.py bench JSONs from the camera board (onboard time e_c, payload b_c of each option) and from the
server board (--server: its server time s_c), plus the accuracy of each option on VisDrone2019-DET val (the learned-
bottleneck study's eval JSONs and its JPEG rows: experiments/results/learned_bottleneck/). The utility is paper 1's
model exactly (simulation/system_model.py SystemModel.predict / score, energy weight 0):
    U_c(B) = f_c(B) * p_c(B) * A_c / A_ref,   f_c = F / ceil(max(e_c, t_tx) / (1000 / F)),  t_tx = 8 b_c / B,
    p_c = Q((R_c - B) / sigma),  R_c = 8 b_c / (D - e_c - d - s_c),  sigma = max(measured std, 0.1 B)
with F = 30 frames/s, D = 300 ms, d the measured one-way delay. Printed: U of every option at each tested goodput,
the best option per goodput, and each code's predicted break-even goodput against the JPEG family (the highest tested
goodput at which the code still has the highest U). Commit the output before the sweep is run.
usage: t10_predict.py CAMERA_BENCH.json SERVER_BENCH.json [--delay-ms 3] [--rates 0.25,0.5,...]  -> JSON on stdout
"""
import argparse
import json
import math
import os

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LB = os.path.join(REPO, "experiments", "results", "learned_bottleneck")


def q_sf(x):
    return 0.5 * math.erfc(x / math.sqrt(2.0))


def accuracy(opt):
    """mAP@[.5:.95] on DET val: eval_<tag>.json (codes) or jpeg_qQ.json / jpeg_fine/ (JPEG), and the unsplit base."""
    if opt.startswith("jpeg_q"):
        for p in (os.path.join(LB, f"{opt}.json"), os.path.join(LB, "jpeg_fine", f"{opt}.json")):
            if os.path.exists(p):
                d = json.load(open(p))
                return d.get("map50_95"), d.get("base_map50_95")
        return None, None
    d = json.load(open(os.path.join(LB, f"eval_{opt}.json")))
    return d["map50_95"], d["base_map50_95"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("camera")
    ap.add_argument("server")
    ap.add_argument("--delay-ms", type=float, default=3.0, help="one-way network delay (measured ping RTT / 2)")
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--deadline-ms", type=float, default=300.0)
    ap.add_argument("--rates", default="0.25,0.5,0.75,1,1.5,2,3,4,6,8,12")
    a = ap.parse_args()
    cam, srv = json.load(open(a.camera))["options"], json.load(open(a.server))["options"]
    period = 1000.0 / a.fps
    opts, out = {}, {"inputs": {"camera": a.camera, "server": a.server, "delay_ms": a.delay_ms}, "options": {},
                     "by_rate": {}}
    for o in cam:
        acc, base = accuracy(o)
        if acc is None or o not in srv:
            continue
        opts[o] = (cam[o]["onboard_ms_median"], cam[o]["payload_kb_mean"] * 1024, srv[o]["server_ms_median"], acc, base)
        out["options"][o] = dict(zip(("onboard_ms", "payload_bytes", "server_ms", "map50_95", "base_map50_95"), opts[o]))
    ref = max(v[4] for v in opts.values())
    for B in [float(x) for x in a.rates.split(",")]:
        row = {}
        for o, (e, b, s, acc, _) in opts.items():
            kbit = b * 8 / 1e3
            t_tx = kbit / B
            budget = a.deadline_ms - e - a.delay_ms - s
            p = 0.0 if budget <= 0 else q_sf((kbit / budget - B) / max(0.1 * B, 1e-9))
            f = a.fps / max(1, math.ceil(max(e, t_tx) / period - 1e-9))
            row[o] = {"U": f * p * acc / ref, "fps": f, "p_on": p, "lat_ms": e + t_tx + a.delay_ms + s}
        best = max(row, key=lambda k: row[k]["U"])
        out["by_rate"][str(B)] = {"best": best, **{o: {k: round(v, 4) for k, v in r.items()} for o, r in row.items()}}
    codes = [o for o in opts if not o.startswith("jpeg_q")]
    out["predicted_break_even_mbit"] = {}
    for c in codes:
        wins = [float(B) for B, r in out["by_rate"].items() if r["best"] == c]
        out["predicted_break_even_mbit"][c] = {"wins_at": wins, "highest_win": max(wins) if wins else None}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
