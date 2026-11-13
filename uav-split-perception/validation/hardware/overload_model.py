#!/usr/bin/env python3
"""What happens when cameras offer an edge computer more frames than it can process (10 Nov 2026, laptop only).

A trace-parameterised queueing model, no new board runs. Every frame passes through shared stages in tandem: the radio
channel into the edge computer (shared by all cameras), then the server that runs the detector. Three cases:

  wifi_jetson     Pi -> Jetson over the access-point Wi-Fi of the 7 Oct testbed
  mesh_jetson     Pi -> Jetson, one hop on the AegisSwarm mesh (batman-adv, one IBSS channel)
  mesh_relayed    Pi -> Jetson -> laptop, both hops on the same mesh channel (the "multihop" scenario)

Inputs, all read from result files:
  placements.csv, rows "pi>jetson" and "pi>laptop" (JPEG): Pi encode, Wi-Fi transfer, server time (stages_ms)
  vid_campaign_mesh2/a2_*.json: per-path goodput samples and per-frame bytes on the mesh -> time on air per frame
    (median bytes x 8 / goodput; its spread is the spread of log goodput)
Calibration targets (also read from result files): live_summary.csv (pi_jetson_jpeg), the median latency of
Jetson-served frames on the mesh, and the multihop fixed-offload row of vid_campaign_mesh2_summary.json.

Sending rules per camera:
  stopwait  one frame in flight (our system): a camera sends its newest frame when its previous result is back
  fifo      open loop at the camera rate into unbounded first-in-first-out queues (a naive system)
  ackwait   v4.1's actual rule (adaptive2.py, added 13 Nov 2026): a camera sends its newest frame once its previous
            frame has LEFT THE RADIO (bytes acknowledged), not when its result is back; the radio is first-come
            (a frame handed to it cannot be recalled); at the server a newer frame of the same camera replaces its
            waiting one (edge_node.py). stopwait, which 19.13 called "our system", waits for the result.
  latest    open loop, but each queue holds one waiting frame per camera and a newer frame replaces it (edge_node.py's
            rule). At the radio this needs a coordinator that grants send slots: a frame already handed to the radio
            cannot be replaced.
Assumptions (stated in the output): server time lognormal with CV 0.25; the radio is one shared first-come queue (no
collisions or rate adaptation modelled); the return of the detections (< 1 KB) is ignored; deadline 300 ms; 120 s per
run after a 10 s warm-up, 5 seeds.

usage: overload_model.py [--out DIR] [--workers 4]   -> DIR/overload_summary.json (default
       experiments/results/hardware/overload_model/)
"""
import argparse
import csv
import glob
import heapq
import json
import math
import random
import statistics as st
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

H = Path(__file__).resolve().parents[2] / "experiments" / "results" / "hardware"
DL, T, WARM, SEEDS, CV_SERVER = 300.0, 120000.0, 10000.0, 5, 0.25
PIS, FPS, MODES = (1, 2, 3, 4, 5, 6, 8, 10), (10, 15, 30), ("stopwait", "fifo", "latest", "ackwait")


def sigma_of_cv(cv):
    return math.sqrt(math.log(1 + cv * cv))


def draw(mean, sigma, rng):
    """Lognormal with the given mean and log-standard deviation."""
    return mean * math.exp(rng.gauss(-sigma * sigma / 2, sigma))


def inputs():
    rows = {(r["chain"], r["cuts"], r["encs"]): r for r in csv.DictReader(open(H / "placements.csv"))}
    pj = [float(x) for x in rows[("pi>jetson", "-1", "jpeg")]["stages_ms"].split(";")]
    pl = [float(x) for x in rows[("pi>laptop", "-1", "jpeg")]["stages_ms"].split(";")]
    enc, wifi_air, jetson_ms = pj
    laptop_ms = pl[2]
    good, nbytes, jlat = {}, {}, []
    for f in sorted(glob.glob(str(H / "vid_campaign_mesh2" / "a2_*__r?.json"))):
        sc = Path(f).name.split("__")[0][3:]
        d = json.load(open(f))
        for p, v in (d.get("link_goodput_samples") or {}).items():
            good.setdefault((sc, p), []).extend(x[1] for x in v if x[1] and x[1] > 0)
        for r in d["frames"]:
            if r.get("server") in ("jetson", "laptop") and r.get("bytes"):
                nbytes.setdefault((sc, r["server"]), []).append(r["bytes"])
                if sc == "static_good" and r["server"] == "jetson" and r.get("lat_ms"):
                    jlat.append(r["lat_ms"])

    def air(sc, p):
        g = good[(sc, p)]
        return {"goodput_mbps_median": st.median(g), "bytes_median": st.median(nbytes[(sc, p)]),
                "air_ms": st.median(nbytes[(sc, p)]) * 8 / st.median(g) / 1e3,
                "log_sigma": st.pstdev([math.log(x) for x in g]), "n_goodput_samples": len(g)}
    mesh_direct, mesh_relay = air("static_good", "jetson"), air("multihop", "laptop")
    live = {r["placement"]: r for r in csv.DictReader(open(H / "live_summary.csv"))}["pi_jetson_jpeg"]
    mh = json.load(open(H / "vid_campaign_mesh2_summary.json"))["cells"]["multihop|fixlap"]
    return {
        "encode_ms": enc, "sigma_encode": sigma_of_cv(CV_SERVER),
        "cases": {
            "wifi_jetson": {"stages": [["wifi_air", wifi_air, sigma_of_cv(CV_SERVER)],
                                       ["jetson_server", jetson_ms, sigma_of_cv(CV_SERVER)]],
                            "source": "placements.csv pi>jetson jpeg stages_ms"},
            "mesh_jetson": {"stages": [["mesh_air", mesh_direct["air_ms"], mesh_direct["log_sigma"]],
                                       ["jetson_server", jetson_ms, sigma_of_cv(CV_SERVER)]],
                            "link": mesh_direct, "source": "vid_campaign_mesh2 static_good, path jetson"},
            "mesh_relayed": {"stages": [["mesh_air_two_hops", mesh_relay["air_ms"], mesh_relay["log_sigma"]],
                                        ["laptop_server", laptop_ms, sigma_of_cv(CV_SERVER)]],
                             "link": mesh_relay, "source": "vid_campaign_mesh2 multihop, path laptop"}},
        "calibration_targets": {
            "wifi_jetson_live_fps": float(live["fps_median"]), "wifi_jetson_live_lat_p50_ms": float(live["lat_p50_ms_median"]),
            "mesh_jetson_live_lat_p50_ms": st.median(jlat), "mesh_jetson_live_frames": len(jlat),
            "mesh_relayed_fixed_live_on_time_share": mh["p_aoi300"][0],
            "mesh_relayed_fixed_live_lat_p50_ms": mh["lat_median_ms"][0],
            "mesh_relayed_fixed_live_on_time_fps": mh["deadline_met_fps"][0], "mesh_relayed_fixed_runs": mh["n"]}}


def sim(n, fps, mode, stages, enc, s_enc, seed):
    rng = random.Random(seed)
    per = 1000.0 / fps
    ev, c = [], [0]

    def push(t, k, d):
        c[0] += 1
        heapq.heappush(ev, (t, c[0], k, d))
    S = [{"busy": False, "q": []} for _ in stages]
    infl, done, work, sent, skipped = [False] * n, [], [0.0, 0.0], 0, 0
    for i in range(n):
        push(i * per / n, "cam", i)

    def start(j, t):
        if S[j]["busy"] or not S[j]["q"]:
            return
        fr = S[j]["q"].pop(0)
        S[j]["busy"] = True
        d = draw(stages[j][1], stages[j][2], rng)
        push(t + d, "end", (j, fr, d))

    def arrive(j, fr, t):
        q = S[j]["q"]
        if mode == "latest" or (mode == "ackwait" and j > 0):
            for f in [f for f in q if f[0] == fr[0]]:
                q.remove(f)
        q.append(fr)
        start(j, t)
    while ev:
        t, _, k, d = heapq.heappop(ev)
        if t > T:
            break
        if k == "cam":
            push(t + per, "cam", d)
            if mode in ("stopwait", "ackwait") and infl[d]:
                skipped += 1
                continue
            infl[d] = True
            sent += 1
            push(t + draw(enc, s_enc, rng), "sent", (d, t))
        elif k == "sent":
            arrive(0, d, t)
        else:
            j, fr, dd = d
            S[j]["busy"] = False
            if j == len(stages) - 1:
                lat = t - fr[1]
                done.append((t, lat))
                if mode != "ackwait":                   # ackwait frees the camera when its bytes leave the radio
                    infl[fr[0]] = False
                if t > WARM:
                    work[0] += dd
                    work[1] += dd * (lat > DL)
            else:
                if mode == "ackwait" and j == 0:       # the bytes have left the radio: the camera may send again
                    infl[fr[0]] = False
                arrive(j + 1, fr, t)
            start(j, t)
    lat = sorted(l for tt, l in done if tt > WARM)
    span = (T - WARM) / 1000
    return {"fps": len(lat) / span, "on_time_fps": sum(l <= DL for l in lat) / span,
            "on_time_share": sum(l <= DL for l in lat) / max(len(lat), 1),
            "lat_p50_ms": lat[len(lat) // 2], "lat_p95_ms": lat[int(0.95 * len(lat)) - 1],
            "server_busy_share": work[0] / (T - WARM), "server_work_late_pct": 100 * work[1] / max(work[0], 1e-9)}


def cell(args):
    case, n, fps, mode, stages, enc, s_enc = args
    rs = [sim(n, fps, mode, stages, enc, s_enc, s) for s in range(1, SEEDS + 1)]
    out = {k: sum(r[k] for r in rs) / SEEDS for k in rs[0]}
    out["per_camera_fps"] = out["fps"] / n
    return f"{case}|{n}|{fps}|{mode}", out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(H / "overload_model"))
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    inp = inputs()
    jobs = [(case, n, fps, mode, c["stages"], inp["encode_ms"], inp["sigma_encode"])
            for case, c in inp["cases"].items() for n in PIS for fps in FPS for mode in MODES]
    with ProcessPoolExecutor(a.workers) as ex:
        grid = dict(ex.map(cell, jobs))
    cap = {}                        # largest number of cameras at 30 fps that keeps >= 95 % of results on time
    for case in inp["cases"]:
        for mode in MODES:
            ok = [n for n in PIS if grid[f"{case}|{n}|30|{mode}"]["on_time_share"] >= 0.95]
            cap[f"{case}|{mode}"] = max(ok) if ok else 0
    srv = {case: 1000.0 / max(s[1] for s in c["stages"]) for case, c in inp["cases"].items()}
    out = {"inputs": inp, "assumptions": {"deadline_ms": DL, "run_ms": T, "warmup_ms": WARM, "seeds": SEEDS,
                                          "server_cv": CV_SERVER, "radio": "one shared first-come queue, no collisions",
                                          "return_path": "ignored (< 1 KB of detections)"},
           "bottleneck_capacity_fps": srv, "max_cameras_at_30fps_95pct_on_time": cap, "grid": grid}
    Path(a.out).mkdir(parents=True, exist_ok=True)
    json.dump(out, open(Path(a.out) / "overload_summary.json", "w"), indent=1)
    print(json.dumps({"capacity_fps": srv, "max_cameras": cap}, indent=1))


if __name__ == "__main__":
    main()
