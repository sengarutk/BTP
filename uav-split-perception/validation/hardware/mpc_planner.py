#!/usr/bin/env python3
"""AccuMO-style model-predictive offloading planner, the core shared by the board (adaptive2.py --policy accumo) and
its benchmark (bench_planner.py). The replay version (replay_accumo.py, brief 19.10) computes the same thing; the
equivalence is checked in tests/test_mpc_planner.py.

A plan fixes one setting, or none, per server for the next H frames. A server with setting v starts as soon as it is
free and repeats every per(v); each start uses the newest captured frame and its result arrives lat(v) later. The
value of a plan is the mean over the horizon of A(shown)/A_ref x rho(age of shown), where shown is the newest capture
that has arrived by that frame (results already in flight and the one on screen count in every plan), minus the
priced energy of its starts. Every combination is evaluated at once by broadcasting (laptop 9 x Jetson 7 x onboard 4
= 252 plans). The action is receding-horizon: of the best plan's servers that are idle now, start the one whose
removal would cost the plan most.
"""
import math

import numpy as np

NONE = -1e9


def plan(now, tick, period, H, options, free, idle, inflight, lag, rat, price=0.0):
    """Choose what to start now.

    now       seconds (any clock, the same one as free and the arrivals)
    tick      capture index of the newest frame (the frame at `now`)
    options   {server: [(setting, latency s, repeat period s, A/A_ref, energy J), ...]} usable settings
    free      {server: time it is free next}
    idle      {server: True if it can take a frame now}
    inflight  [(capture tick, A/A_ref, expected arrival s)]: the result on screen (arrival <= now) and those on their way
    lag, rat  the decay curve: accuracy ratio at age lag (ms)
    price     energy price (per J); 0 = AccuMO's objective
    returns   (server, setting, gain) or None
    """
    fut = tick + np.arange(1, H + 1)
    base_cap, base_acc = np.full(H, NONE), np.zeros(H)
    for k, a, t_arr in sorted(inflight):                 # sorted by capture: a newer one overrides
        m = fut >= t_arr / period
        base_cap[m], base_acc[m] = k, a
    servers = list(options)
    caps, accs, costs, meta = [], [], [], []
    for srv in servers:
        c_l, a_l, e_l, m_l = [np.full(H, NONE)], [np.zeros(H)], [0.0], [None]
        for var, lat, per, a, e in options[srv]:
            starts = free[srv] + per * np.arange(0, int(H * period / per) + 2)
            starts = starts[starts < now + H * period]
            cap_k = np.ceil(starts / period - 1e-9)      # a send uses the newest frame at its start
            arr_k = (starts + lat) / period
            c = np.full(H, NONE)
            for ck, ak in zip(cap_k, arr_k):
                c[fut >= ak] = ck
            c_l.append(c)
            a_l.append(np.where(c > NONE / 10, a, 0.0))
            e_l.append(price * e * len(starts))
            m_l.append(var)
        caps.append(np.array(c_l))
        accs.append(np.array(a_l))
        costs.append(np.array(e_l))
        meta.append(m_l)
    n = len(servers)

    def put(x, i):                                       # server i's options on axis i, the horizon last
        sh = [1] * n + [H]
        sh[i] = x.shape[0]
        return x.reshape(sh)

    C = np.stack(np.broadcast_arrays(*[put(caps[i], i) for i in range(n)], base_cap.reshape([1] * n + [H])))
    A = np.stack(np.broadcast_arrays(*[put(accs[i], i) for i in range(n)], base_acc.reshape([1] * n + [H])))
    w = np.argmax(C, axis=0)
    cw = np.take_along_axis(C, w[None], 0)[0]
    aw = np.take_along_axis(A, w[None], 0)[0]
    age_ms = np.where(cw > NONE / 10, (fut - cw) * period * 1e3, 1e9)
    val = (aw * np.interp(age_ms, lag, rat, right=0.0)).sum(-1) / H
    for i in range(n):
        sh = [1] * n
        sh[i] = costs[i].shape[0]
        val = val - costs[i].reshape(sh) / H
    best = np.unravel_index(int(np.argmax(val)), val.shape)
    cand = []
    for i, srv in enumerate(servers):
        if best[i] == 0 or not idle.get(srv, False):
            continue
        alt = list(best)
        alt[i] = 0
        cand.append((float(val[best] - val[tuple(alt)]), srv, meta[i][best[i]]))
    if not cand:
        return None
    g, srv, var = max(cand)
    return srv, var, g


def overdue_arrival(t_arr, now, period):
    """Expected arrival of a result: as predicted, or, once it is late, the longer it is late the later it is expected
    (soon beyond the horizon, i.e. given up)."""
    return t_arr if t_arr > now else now + max(period, now - t_arr)


def repeat_period(ms, period):
    """Onboard: the inference occupies whole camera ticks."""
    return math.ceil(ms / (1000 * period) - 1e-9) * period
