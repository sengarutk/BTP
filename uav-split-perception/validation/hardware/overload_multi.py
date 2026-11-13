#!/usr/bin/env python3
"""Many camera Pis and several Jetsons (13 Nov 2026; follows overload_handling.py).

Mesh-hop timings of overload_model.py (radio 22.1 ms per Q90 frame with its measured spread, Jetson 38.0 ms, encode
7.7 ms), cameras at 30 frames/s, deadline 300 ms, 120 s after a 10 s warm-up, 5 seeds. Two radio settings:
  shared     all drones on one channel (the testbed's mesh, channel 6): one transmission at a time in total
  clustered  each Jetson has its own channel (or area); a transmission uses the channel of the Jetson it goes to
Strategies:
  static     v4.1's rule; Pis split evenly among the Jetsons, each Pi always uses its own Jetson
  jsq        v4.1's rule; at each send the Pi picks the Jetson with the fewest frames waiting or on air to it
             (load-aware choice; v4.1 chooses among servers by its estimates in the same spirit)
  pull1      each Jetson pulls one frame ahead from its own Pis (the best single-Jetson method of overload_handling)
  gpull      global pull one ahead: whenever a Jetson can take a frame, it takes the newest frame of the Pi whose
             detection is oldest among ALL Pis (a shared coordinator; frames go to whichever Jetson is free)
Per Pi: on-time detections per second, and the mean age of its newest detection (AoI).
usage: overload_multi.py -> experiments/results/hardware/overload_multi/summary.json
"""
import heapq
import json
import random
from concurrent.futures import ProcessPoolExecutor

import overload_model as M

OUT = M.H / "overload_multi"
JETS, PIS = (1, 2, 3, 4), (2, 4, 6, 8, 12, 16)
STRATS, RADIOS = ("static", "jsq", "pull1", "gpull"), ("shared", "clustered")


def sim(n, m, strat, radio, air, srv, enc, s_enc, seed):
    rng = random.Random(seed)
    per = 1000.0 / 30.0
    ev, cnt = [], [0]

    def push(t, k, d):
        cnt[0] += 1
        heapq.heappush(ev, (t, cnt[0], k, d))
    home = [i % m for i in range(n)]
    nch = 1 if radio == "shared" else m
    ch_busy, ch_q = [False] * nch, [[] for _ in range(nch)]
    srv_busy, srv_q = [False] * m, [[] for _ in range(m)]
    toward = [0] * m                              # frames on air or waiting at the radio toward each Jetson
    infl, ready, granted = [False] * n, [None] * n, [None] * n
    last_cap, dl = [None] * n, [[] for _ in range(n)]
    pull = strat in ("pull1", "gpull")

    def ch(j):
        return 0 if radio == "shared" else j

    def grants(t):
        """Pull one ahead: a Jetson with fewer than 2 frames in its pipe (waiting at it or on air to it) asks for one."""
        for j in range(m):
            while (srv_busy[j] + len(srv_q[j]) + toward[j]) < 2:
                cand = [c for c in range(n) if ready[c] is not None and (strat == "gpull" or home[c] == j)]
                if not cand:
                    break
                def age(c):
                    v = [x for x in (last_cap[c], granted[c]) if x is not None]
                    return max(v) if v else -1e18
                c = min(cand, key=age)
                granted[c], fr = ready[c], (c, ready[c], j)
                ready[c] = None
                toward[j] += 1
                ch_q[ch(j)].append(fr)
                radio_start(ch(j), t)

    def radio_start(k, t):
        if ch_busy[k] or not ch_q[k]:
            return
        fr = ch_q[k].pop(0)
        ch_busy[k] = True
        push(t + M.draw(air[0], air[1], rng), "air", (k, fr))

    def srv_start(j, t):
        if srv_busy[j] or not srv_q[j]:
            return
        c, tc = srv_q[j].pop(0)
        srv_busy[j] = True
        push(t + M.draw(srv[0], srv[1], rng), "srv", (j, c, tc))
    for i in range(n):
        push(i * per / n, "cam", i)
    while ev:
        t, _, k, d = heapq.heappop(ev)
        if t > M.T:
            break
        if k == "cam":
            push(t + per, "cam", d)
            if pull or not infl[d]:
                if not pull:
                    infl[d] = True
                push(t + M.draw(enc, s_enc, rng), "enc", (d, t))
        elif k == "enc":
            c, tc = d
            if pull:
                if ready[c] is None or tc > ready[c]:
                    ready[c] = tc
                grants(t)
            else:
                j = home[c] if strat == "static" else min(range(m), key=lambda j: (srv_busy[j] + len(srv_q[j])
                                                                                    + toward[j], j))
                toward[j] += 1
                ch_q[ch(j)].append((c, tc, j))
                radio_start(ch(j), t)
        elif k == "air":
            kk, (c, tc, j) = d
            ch_busy[kk] = False
            toward[j] -= 1
            if not pull:
                infl[c] = False
            srv_q[j][:] = [x for x in srv_q[j] if x[0] != c]   # a newer frame of the same Pi replaces its waiting one
            srv_q[j].append((c, tc))
            srv_start(j, t)
            radio_start(kk, t)
            if pull:
                grants(t)
        else:
            j, c, tc = d
            srv_busy[j] = False
            if t > M.WARM:
                dl[c].append((t, tc))
            if last_cap[c] is None or tc > last_cap[c]:
                last_cap[c] = tc
            srv_start(j, t)
            if pull:
                grants(t)
    span = (M.T - M.WARM) / 1000.0
    on = [sum(1 for t, tc in x if t - tc <= M.DL) / span for x in dl]
    aoi = []
    for x in dl:
        if not x:
            aoi.append(float("inf"))
            continue
        x = sorted(x)
        area, cur, t0 = 0.0, x[0][1], x[0][0]
        for t, tc in x[1:]:
            area += ((t0 - cur) + (t - cur)) / 2 * (t - t0)
            cur, t0 = max(cur, tc), t
        area += ((t0 - cur) + (M.T - cur)) / 2 * (M.T - t0)
        aoi.append(area / (M.T - x[0][0]))
    return {"on_time_total": sum(on), "on_time_worst": min(on), "on_time_per_pi": sum(on) / n,
            "aoi_mean_ms": sum(aoi) / n, "aoi_worst_ms": max(aoi)}


def cell(a):
    n, m, s, r, air, srv, enc, s_enc = a
    rs = [sim(n, m, s, r, air, srv, enc, s_enc, k) for k in range(1, M.SEEDS + 1)]
    return f"{r}|{m}|{n}|{s}", {k: sum(x[k] for x in rs) / len(rs) for k in rs[0]}


def main():
    inp = M.inputs()
    st = inp["cases"]["mesh_jetson"]["stages"]
    air, srv = (st[0][1], st[0][2]), (st[1][1], st[1][2])
    jobs = [(n, m, s, r, air, srv, inp["encode_ms"], inp["sigma_encode"])
            for r in RADIOS for m in JETS for n in PIS for s in STRATS]
    with ProcessPoolExecutor(4) as ex:
        grid = dict(ex.map(cell, jobs))
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump({"method": __doc__, "grid": grid}, open(OUT / "summary.json", "w"), indent=1)
    for r in RADIOS:
        for m in JETS:
            print(f"== {r}, {m} Jetson(s): on-time total / worst Pi / mean AoI ms")
            for n in PIS:
                print(f"{n:2d} Pis " + " | ".join(
                    f"{s} {grid[f'{r}|{m}|{n}|{s}']['on_time_total']:.1f}/{grid[f'{r}|{m}|{n}|{s}']['on_time_worst']:.1f}"
                    f"/{grid[f'{r}|{m}|{n}|{s}']['aoi_mean_ms']:.0f}" for s in STRATS))


if __name__ == "__main__":
    main()
