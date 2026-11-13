#!/usr/bin/env python3
"""Ways to handle many camera Pis on one Jetson, in the overload model's setting (13 Nov 2026; follows 19.13).

Same measured inputs as overload_model.py (encode, radio and server times with their spreads; deadline 300 ms; cameras
at 30 frames/s; 120 s after a 10 s warm-up; 5 seeds). One shared radio (first come, one frame at a time), then the
server. Methods:
  v41        v4.1's rule: a camera sends its newest frame once its previous frame has left the radio; at the server a
             newer frame of the same camera replaces its waiting one (edge_node.py). Baseline; must reproduce
             overload_model.py's "ackwait".
  coord      a coordinator grants the radio to one camera at a time (first come); the camera then sends its newest
             encoded frame, so nothing waits at the radio. Must reproduce overload_model.py's "latest".
  coord_age  the same, but the turn goes to the camera whose newest delivered detection is oldest (age-of-information
             scheduling).
  ratecap    v4.1's rule, but each camera sends at most C / N frames/s (C the path's capacity): its fair share.
  dropold    v4.1's rule, but the server skips a frame that can no longer meet the deadline (age + server time > D).
  twojet     v4.1's rule with two Jetsons behind the same radio channel (the server stage has two units).
  coord2     coordinator with two Jetsons.
  pull       the coordinator grants a turn only when the server can take the frame at once (the Jetson pulls the
             next frame when a GPU unit is free): nothing waits at the radio or at the server.
  pull_age   pull, with the turn to the camera whose detection is oldest (counting a granted frame from its grant).
  pull2      pull with two Jetsons.
  pull1      pull one frame ahead: a turn is granted while at most one frame waits for each GPU unit, so the radio
             and the GPU work in parallel but no queue builds.
  pull1x2    pull1 with two Jetsons.
  (coord_age counts a granted frame from its grant too: a camera whose frame is on its way is not chosen again.)
Per camera: on-time results per second and the mean age of its newest delivered detection (its age of information,
AoI); reported as the total, the worst camera and the mean over cameras.
usage: overload_handling.py -> experiments/results/hardware/overload_handling/summary.json
"""
import heapq
import json
import random
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import overload_model as M

OUT = M.H / "overload_handling"
METHODS = ("v41", "coord", "coord_age", "pull", "pull_age", "ratecap", "dropold", "twojet", "coord2", "pull2", "pull1", "pull1x2")
PIS = (1, 2, 3, 4, 5, 6, 8, 10)


def sim(n, method, stages, enc, s_enc, seed, cap_fps):
    rng = random.Random(seed)
    per = 1000.0 / 30.0
    (a_name, a_mean, a_sig), (s_name, s_mean, s_sig) = stages
    units = 2 if method in ("twojet", "coord2", "pull2", "pull1x2") else 1
    coord = method in ("coord", "coord_age", "coord2") or method.startswith("pull")
    pull = method.startswith("pull")
    on_air = [0]
    granted = [None] * n          # capture time of the frame granted to each camera (for age-based turns)
    ev, cnt = [], [0]

    def push(t, k, d):
        cnt[0] += 1
        heapq.heappush(ev, (t, cnt[0], k, d))
    ready = [None] * n            # coordinator: each camera's newest encoded frame (capture time)
    want = []                     # coordinator: cameras waiting for a turn, in order of request
    infl = [False] * n            # v4.1 rule: a frame of this camera is in encode or on the radio
    last_send = [-1e9] * n
    radio_busy, radio_q = False, []
    srv_free, srv_q = units, []   # server queue: (camera, capture time), one waiting frame per camera
    last_cap = [None] * n         # capture time of the newest delivered detection
    deliveries = [[] for _ in range(n)]
    for i in range(n):
        push(i * per / n, "cam", i)
    min_gap = 1000.0 * n / cap_fps if method == "ratecap" else 0.0

    def radio_start(t):
        nonlocal radio_busy
        if radio_busy:
            return
        if coord:
            ahead = units if method in ("pull1", "pull1x2") else 0
            if pull and srv_free - len(srv_q) - on_air[0] + ahead <= 0:
                return                                   # pull: only when a GPU unit can take the frame at once
            cand = [c for c in want if ready[c] is not None]
            if not cand:
                return
            if method in ("coord_age", "pull_age"):
                def age_key(c):
                    v = [x for x in (last_cap[c], granted[c]) if x is not None]
                    return max(v) if v else -1e18
                c = min(cand, key=age_key)
            else:
                c = cand[0]
            want.remove(c)
            fr = (c, ready[c])
            granted[c] = ready[c]
            ready[c] = None
        else:
            if not radio_q:
                return
            fr = radio_q.pop(0)
        radio_busy = True
        on_air[0] += 1
        push(t + M.draw(a_mean, a_sig, rng), "air", fr)

    def srv_start(t):
        nonlocal srv_free
        while srv_free > 0 and srv_q:
            c, tc = srv_q.pop(0)
            d = M.draw(s_mean, s_sig, rng)
            if method == "dropold" and (t - tc) + s_mean > M.DL:
                continue                                 # cannot be on time: skip it, keep the GPU for others
            srv_free -= 1
            push(t + d, "srv", (c, tc))
    while ev:
        t, _, k, d = heapq.heappop(ev)
        if t > M.T:
            break
        if k == "cam":
            push(t + per, "cam", d)
            if coord:                                    # encode every frame; the newest replaces the older one
                push(t + M.draw(enc, s_enc, rng), "enc", (d, t))
            elif not infl[d] and t - last_send[d] >= min_gap:
                infl[d] = True
                last_send[d] = t
                push(t + M.draw(enc, s_enc, rng), "enc", (d, t))
        elif k == "enc":
            c, tc = d
            if coord:
                if ready[c] is None or tc > ready[c]:
                    ready[c] = tc
                if c not in want:
                    want.append(c)
            else:
                radio_q.append((c, tc))
            radio_start(t)
        elif k == "air":
            radio_busy = False
            on_air[0] -= 1
            c, tc = d
            if not coord:
                infl[c] = False                          # bytes have left the radio: the camera may send again
            srv_q[:] = [x for x in srv_q if x[0] != c]   # newer frame of the same camera replaces its waiting one
            srv_q.append((c, tc))
            srv_start(t)
            radio_start(t)
        else:                                            # server done
            srv_free += 1
            c, tc = d
            radio_start(t)                               # pull: a unit is free, grant the next turn
            if t > M.WARM:
                deliveries[c].append((t, tc))
            if last_cap[c] is None or tc > last_cap[c]:
                last_cap[c] = tc
            srv_start(t)
    span = (M.T - M.WARM) / 1000.0
    per_cam = []
    for c in range(n):
        dl = deliveries[c]
        on = sum(1 for t, tc in dl if t - tc <= M.DL) / span
        # mean AoI over [WARM, T]: age of the newest delivered capture, piecewise linear between deliveries
        area, cur, t0 = 0.0, None, M.WARM
        for t, tc in sorted(dl):
            if cur is not None:
                area += ((t0 - cur) + (t - cur)) / 2 * (t - t0)
            if cur is None or tc > cur:
                cur = tc
            t0 = t
        if cur is not None:
            area += ((t0 - cur) + (M.T - cur)) / 2 * (M.T - t0)
            aoi = area / (M.T - (sorted(dl)[0][0] if dl else M.WARM)) if dl else float("inf")
        else:
            aoi = float("inf")
        per_cam.append({"on_time_fps": on, "aoi_ms": aoi})
    lat = sorted(t - tc for c in range(n) for t, tc in deliveries[c])
    return {"on_time_fps_total": sum(p["on_time_fps"] for p in per_cam),
            "on_time_fps_worst_cam": min(p["on_time_fps"] for p in per_cam),
            "aoi_mean_ms": sum(p["aoi_ms"] for p in per_cam) / n, "aoi_worst_ms": max(p["aoi_ms"] for p in per_cam),
            "lat_p50_ms": lat[len(lat) // 2] if lat else float("inf"), "delivered_fps": len(lat) / span}


def cell(args):
    case, n, method, stages, enc, s_enc, cap = args
    rs = [sim(n, method, stages, enc, s_enc, s, cap) for s in range(1, M.SEEDS + 1)]
    return f"{case}|{n}|{method}", {k: sum(r[k] for r in rs) / len(rs) for k in rs[0]}


def main():
    inp = M.inputs()
    cases = {k: v for k, v in inp["cases"].items() if k in ("wifi_jetson", "mesh_jetson", "mesh_relayed")}
    jobs = []
    for case, c in cases.items():
        cap = 1000.0 / max(s[1] for s in c["stages"])
        for n in PIS:
            for m in METHODS:
                jobs.append((case, n, m, c["stages"], inp["encode_ms"], inp["sigma_encode"], cap))
    with ProcessPoolExecutor(4) as ex:
        grid = dict(ex.map(cell, jobs))
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump({"method": __doc__, "grid": grid}, open(OUT / "summary.json", "w"), indent=1)
    for case in cases:
        print("==", case)
        for n in PIS:
            print(f"{n:2d} " + " | ".join(f"{m} {grid[f'{case}|{n}|{m}']['on_time_fps_total']:.1f}"
                                          f"/{grid[f'{case}|{n}|{m}']['on_time_fps_worst_cam']:.1f} "
                                          f"AoI {grid[f'{case}|{n}|{m}']['aoi_mean_ms']:.0f}" for m in METHODS))


if __name__ == "__main__":
    main()
