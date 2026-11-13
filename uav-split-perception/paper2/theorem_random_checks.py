#!/usr/bin/env python3
"""Randomised checks of paper 2's mathematics, independent of the hardware data (13 Nov 2026).

A proof can be read; these test the statements on thousands of random cases that meet each result's assumptions.
A violation would mean the statement (or its proof) is wrong.
  thm1   Theorem 1: random power sequences and random holds, caps, clips and guard raises in the price update
         (the coded rule); the bound must hold on every sequence.
  prop   Proposition (budget and temperature): random power profiles, first-order model integrated finely; the mean
         temperature identity must hold to integration error.
  thm3   Theorem 3: random load P_n(t) <= P_hat, random inference schedules that obey the guard (one at a time, none
         started at or above theta_g, each at most e long, P_i <= P_hat_i); theta from the model; checks (a) and (b).
  thm2   Theorem 2: random finite i.i.d. problems; the greedy controller with a plain projected dual step; U* of the
         best power-feasible randomised stationary policy by Lagrangian duality; checks the gap bound in expectation.
  rule   paper 1's Proposition (break-even goodput): random options in the paper's model; a qualifying image setting
         must never lose to the code at any goodput at or above B_be.
usage: python paper2/theorem_random_checks.py -> experiments/results/hardware/theory_check/random_checks.json
"""
import json
import math
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent.parent / "experiments" / "results" / "hardware" / "theory_check" / "random_checks.json"
rng = np.random.default_rng(20261113)


def thm1(n_cases=20000):
    worst, bad = -1e9, 0
    for _ in range(n_cases):
        N, eta, B, mu_max = int(rng.integers(5, 400)), float(rng.uniform(0.01, 1.0)), float(rng.uniform(1, 5)), \
            float(rng.uniform(1.0, 20))
        P = rng.uniform(0, 8, N)
        mu, s_neg_H, prev = 0.0, 0.0, 0.0
        for t in range(N):
            r = rng.random()
            raw = prev + eta * (P[t] - B)
            if r < 0.15:                                   # held
                mu = prev
            else:
                mu = min(mu_max, max(0.0, raw))           # projected step, clip at 0, cap
                if rng.random() < 0.1:                    # thermal guard can only raise
                    mu = max(mu, 1.0)
            s = mu - raw
            in_H = (r < 0.15) or (raw > mu_max)            # H defined by the update type only, never by the sign
            if in_H:
                s_neg_H += max(0.0, -s)
            elif s < -1e-12:
                bad += 1                                   # outside H every departure must be >= 0
            prev = mu
        lhs = P.mean()
        rhs = B + mu / (eta * N) + s_neg_H / (eta * N)
        worst = max(worst, lhs - rhs)
        bad += int(lhs > rhs + 1e-9)
    return {"cases": n_cases, "violations": bad, "largest_lhs_minus_rhs": worst}


def prop(n_cases=2000):
    worst = 0.0
    for _ in range(n_cases):
        a, b, tau = rng.uniform(20, 45), rng.uniform(5, 15), rng.uniform(50, 300)
        W, dt = rng.uniform(100, 2000), 0.05
        n = int(W / dt)
        P = np.repeat(rng.uniform(0, 6, n // 100 + 1), 100)[:n]
        th = np.empty(n + 1)
        th[0] = rng.uniform(30, 90)
        for k in range(n):                                  # exact step for piecewise-constant power
            ss = a + b * P[k]
            th[k + 1] = ss + (th[k] - ss) * math.exp(-dt / tau)
        # mean over the window of the continuous solution, by the exact integral on each step
        means = []
        for k in range(n):
            ss = a + b * P[k]
            means.append(ss + (th[k] - ss) * tau / dt * (1 - math.exp(-dt / tau)))
        lhs = float(np.mean(means))
        rhs = a + b * float(P.mean()) - tau * (th[-1] - th[0]) / (n * dt)
        worst = max(worst, abs(lhs - rhs))
    return {"cases": n_cases, "largest_abs_error_c": worst}


def thm3(n_cases=3000):
    bad_a, bad_b, worst_gap = 0, 0, -1e9
    for _ in range(n_cases):
        a, b, tau = rng.uniform(25, 45), rng.uniform(8, 14), rng.uniform(60, 250)
        P_idle = rng.uniform(1.0, 2.5)
        P_hat = P_idle + rng.uniform(0.5, 3.0)
        Pi_hat, e = rng.uniform(1.0, 4.0), rng.uniform(0.1, 3.0)
        H = a + b * P_hat
        theta_lo = a + b * P_idle
        theta_g = rng.uniform(theta_lo + 0.5, H - 0.5) if H - theta_lo > 1.0 else None
        if theta_g is None:
            continue
        dt, T = 0.01, rng.uniform(200, 1500)
        n = int(T / dt)
        Pn = np.repeat(rng.uniform(P_idle, P_hat, n // 500 + 1), 500)[:n]     # load without inference
        th0 = rng.uniform(theta_lo, theta_g)                                  # theta(0) <= theta_g
        th_n = np.empty(n + 1)
        th_n[0] = th0
        for k in range(n):
            ss = a + b * Pn[k]
            th_n[k + 1] = ss + (th_n[k] - ss) * math.exp(-dt / tau)
        theta_f = float(th_n.max())                       # the bound's floor: the max of theta_n (assumption)
        if not (th_n.min() >= theta_lo - 1e-9):
            continue
        th_i, th, k, busy_until, Pi = 0.0, th0, 0, -1, 0.0
        tmax, viol_a = th0, False
        for k in range(n):
            t = k * dt
            if t >= busy_until:                           # free: maybe start, only below the guard
                Pi = 0.0
                if th < theta_g and rng.random() < 0.02:
                    busy_until = t + rng.uniform(0.0, e)
                    Pi = rng.uniform(0.0, Pi_hat)
            th_i = b * Pi + (th_i - b * Pi) * math.exp(-dt / tau)
            th = th_n[k + 1] + th_i
            tmax = max(tmax, th)
            viol_a |= th < th_n[k + 1] - 1e-9
        bound = theta_g + b * Pi_hat * (1 - math.exp(-e / tau)) + (theta_f - theta_lo) * (H - theta_g) / (H - theta_lo)
        bad_a += int(viol_a)
        bad_b += int(tmax > bound + 1e-6)
        worst_gap = max(worst_gap, tmax - bound)
    return {"cases": n_cases, "violations_a": bad_a, "violations_b": bad_b, "largest_peak_minus_bound_c": worst_gap,
            "note": "the guard is checked on the model temperature every 10 ms; an inference that has started runs "
                    "to its end"}


def thm2(n_cases=100, T=3000, reps=10):
    bad, worst = 0, -1e9
    for _ in range(n_cases):
        K, A = int(rng.integers(2, 6)), int(rng.integers(2, 6))
        pk = rng.dirichlet(np.ones(K))
        U = rng.uniform(0, 1, (K, A))
        P = rng.uniform(0, 5, (K, A))
        B = float(rng.uniform(P.min(axis=1).mean() + 0.1, P.max(axis=1).mean()))
        eta = float(rng.uniform(0.01, 0.5))
        # U* = min over mu >= 0 of  E_k max_a (U - mu P) + mu B   (randomised stationary policies: strong duality)
        # the dual is convex and piecewise linear in mu: its minimum is at 0 or at a breakpoint where some state's
        # best action changes, mu = (U_a - U_b) / (P_a - P_b) > 0 (exact, no grid)
        cand = [0.0] + [float((U[k, x] - U[k, y]) / (P[k, x] - P[k, y])) for k in range(K) for x in range(A)
                        for y in range(A) if P[k, x] != P[k, y] and (U[k, x] - U[k, y]) / (P[k, x] - P[k, y]) > 0]
        Ustar = float(min((pk * (U - m * P).max(axis=1)).sum() + m * B for m in cand))
        lhs, gapterm = [], []
        for _ in range(reps):
            mu, su, sq = 0.0, 0.0, 0.0
            ks = rng.choice(K, size=T, p=pk)
            for k in ks:
                act = int(np.argmax(U[k] - mu * P[k]))
                su += U[k, act]
                sq += (P[k, act] - B) ** 2
                mu = max(0.0, mu + eta * (P[k, act] - B))
            lhs.append(su / T)
            gapterm.append(eta / 2 * sq / T)
        m_l, m_g = float(np.mean(lhs)), float(np.mean(gapterm))
        se = float(np.std(lhs, ddof=1) / math.sqrt(reps))
        d = (Ustar - m_g) - m_l                            # should be <= 0 (up to sampling error)
        worst = max(worst, d / max(se, 1e-9))
        bad += int(d > 4 * se + 1e-3)                      # beyond sampling error and the dual grid's resolution
    return {"cases": n_cases, "violations": bad, "largest_excess_in_standard_errors": worst}


def rule(n_cases=20000):
    """Paper 1's proposition on random options: U = F/ceil(F max(e, b/B)) * Q((R - B)/sigma) * A, sigma <= s B."""
    from statistics import NormalDist
    nd = NormalDist()
    bad = 0
    for _ in range(n_cases):
        F, D, d, s = float(rng.choice([10, 15, 24, 30, 60])), rng.uniform(100, 1000), rng.uniform(5, 100), \
            rng.uniform(0.01, 0.5)
        P = rng.uniform(0.5, 0.999)
        zP = nd.inv_cdf(P)
        if zP * s >= 1:
            continue
        e_k, b_k, A_k, sv_k = rng.uniform(1, 1000), rng.uniform(0.001, 1.0), rng.uniform(0.05, 0.4), rng.uniform(1, 50)
        e_q, b_q, sv_q = rng.uniform(0, 100), rng.uniform(0.001, 1.0), rng.uniform(1, 50)
        A_q = A_k / P * rng.uniform(1.0, 1.5)              # P A_q >= A_k
        m_k = max(e_k, 1000 / F)
        if e_q > m_k:
            continue

        def util(e, b, A, sv, B, sig):
            fr = F / math.ceil(F * max(e, b * 1000 / B) / 1000 - 1e-12)      # b in Mbit, B in Mbit/s, e in ms
            slack = D - e - d - sv
            if slack <= 0:
                return 0.0
            R = b * 1000 / slack
            return fr * (1 - nd.cdf((R - B) / max(sig, 1e-12))) * A
        R_q = b_q * 1000 / (D - e_q - d - sv_q) if D - e_q - d - sv_q > 0 else math.inf
        b_be = max(b_q * 1000 / m_k, R_q / (1 - zP * s))
        if not math.isfinite(b_be):
            continue
        for B in b_be * rng.uniform(1.0, 20.0, 5):
            sig = rng.uniform(0, s * B)                    # any spread up to s B
            if util(e_q, b_q, A_q, sv_q, B, sig) < util(e_k, b_k, A_k, sv_k, B, sig) - 1e-12:
                bad += 1
    return {"cases": n_cases, "violations": bad}


def main():
    out = {"method": __doc__, "seed": 20261113}
    for name, f in (("thm1", thm1), ("prop", prop), ("thm3", thm3), ("thm2", thm2), ("rule", rule)):
        out[name] = f()
        print(name, out[name], flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=1)


if __name__ == "__main__":
    main()
