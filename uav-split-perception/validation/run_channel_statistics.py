#!/usr/bin/env python3
"""C1: statistics of the synthetic channel generator against their textbook values.

Same estimators and seeds as tests/test_channel_statistics.py, written out as numbers:
  Rician fading   mean power and moment-estimated K-factor for K = 9, 3, 0 dB
  Clarke/Jakes    largest deviation of the scattered component's autocorrelation from J0(2 pi fd tau)
  Gudmundson      shadowing standard deviation (target 4 dB) and autocorrelation after 6, 30, 60 m
                  of travel, measured and exp(-dx / 30 m)
Output: experiments/results/validation/channel_statistics.json
"""

import json
import math

import numpy as np

from simulation.trace_generator import rician_process, shadowing_db
from tests.test_channel_statistics import _k_moment, j0
from validation.run_link_validation import OUT


def main():
    out = {}
    for k_db in (9.0, 3.0, 0.0):
        p = np.concatenate([np.abs(rician_process(20000, k_db, 12.0, 3.5e9, np.random.default_rng(s))) ** 2
                            for s in range(40)])
        out[f"K{k_db:.0f}dB"] = {"mean_power": round(float(p.mean()), 3),
                                 "K_hat_dB": round(10 * math.log10(_k_moment(p)), 2)}
    fd, lags, n = 12.0 * 3.5e9 / 3e8, np.arange(0, 11), 4000
    acf = np.zeros(lags.size)
    for s in range(300):
        h = rician_process(n, -60.0, 12.0, 3.5e9, np.random.default_rng(1000 + s))
        for i, L in enumerate(lags):
            acf[i] += np.real(np.mean(h[L:] * np.conj(h[: n - L])))
    acf /= 300
    out["clarke_acf_max_abs_error"] = round(float(np.max(np.abs(acf - j0(2 * np.pi * fd * lags / 1000.0)))), 4)
    sigma, d_corr, step = 4.0, 30.0, 0.12
    sh = np.concatenate([shadowing_db(20000, sigma, step, d_corr, np.random.default_rng(k)) for k in range(20)])
    out["shadow_std_dB(target 4)"] = round(float(sh.std()), 3)
    x = shadowing_db(200000, sigma, step, d_corr, np.random.default_rng(7))
    out["shadow_acf"] = {f"{lag * step:.0f} m": [round(float(np.corrcoef(x[lag:], x[:-lag])[0, 1]), 3),
                                                 round(math.exp(-lag * step / d_corr), 3)] for lag in (50, 250, 500)}
    (OUT / "channel_statistics.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
