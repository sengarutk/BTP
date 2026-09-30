"""Statistical validation of the synthetic channel generator (simulation/trace_generator.py).

Each test compares an ensemble statistic of the generated process with its textbook value:
  * Rician fading: unit mean power and the configured K-factor (moment estimator);
  * Clarke/Jakes Doppler: autocorrelation of the scattered component equals J0(2 pi fd tau);
  * Gudmundson shadowing: standard deviation sigma and autocorrelation exp(-dx / d_corr);
  * blackouts: the configured depth is applied inside the window;
  * rate, delay and loss columns follow the documented formulas exactly.
"""

import math

import numpy as np
import pytest

from simulation.trace_generator import (PROFILES, SE_MAX, SINR_MIN_DB, ChannelProfile, attenuated_shannon_se,
                                        generate_trace, rician_process, shadowing_db)


def j0(x: np.ndarray) -> np.ndarray:
    """Bessel J0 from its integral definition, J0(x) = (1/pi) int_0^pi cos(x sin t) dt (no scipy needed)."""
    t = np.linspace(0.0, np.pi, 4001)
    return np.trapz(np.cos(np.outer(np.atleast_1d(x), np.sin(t))), t, axis=1) / np.pi


def test_j0_reference_values():
    # J0(0) = 1 and the first zero of J0 at 2.404826 (Abramowitz & Stegun, Table 9.5).
    assert j0(np.array([0.0]))[0] == pytest.approx(1.0, abs=1e-9)
    assert abs(j0(np.array([2.404826]))[0]) < 1e-6


def _k_moment(power: np.ndarray) -> float:
    """Moment estimator of the Rician K-factor from instantaneous power (Greenstein et al., 1999)."""
    g = power.var() / power.mean() ** 2
    r = math.sqrt(max(1.0 - g, 0.0))
    return r / (1.0 - r) if r < 1 else math.inf


@pytest.mark.parametrize("k_db", [9.0, 3.0, 0.0])
def test_rician_power_and_k_factor(k_db):
    powers = np.concatenate([np.abs(rician_process(20000, k_db, 12.0, 3.5e9, np.random.default_rng(s))) ** 2
                             for s in range(40)])
    assert powers.mean() == pytest.approx(1.0, rel=0.03)
    k_hat_db = 10 * math.log10(_k_moment(powers))
    assert k_hat_db == pytest.approx(k_db, abs=0.6)


def test_clarke_doppler_autocorrelation():
    fd = 12.0 * 3.5e9 / 3e8                   # 140 Hz
    lags = np.arange(0, 11)                    # 0..10 ms at 1 kHz
    acf = np.zeros(lags.size)
    n = 4000
    for s in range(300):                       # ensemble over independent ray sets
        h = rician_process(n, -60.0, 12.0, 3.5e9, np.random.default_rng(1000 + s))
        for i, L in enumerate(lags):
            acf[i] += np.real(np.mean(h[L:] * np.conj(h[: n - L])))
    acf /= 300
    theory = j0(2 * np.pi * fd * lags / 1000.0)
    assert np.max(np.abs(acf - theory)) < 0.05


def test_gudmundson_shadowing():
    sigma, d_corr, step = 4.0, 30.0, 0.12      # moderate profile: 12 m/s x 10 ms
    s = np.concatenate([shadowing_db(20000, sigma, step, d_corr, np.random.default_rng(k)) for k in range(20)])
    assert s.std() == pytest.approx(sigma, rel=0.05)
    x = shadowing_db(200000, sigma, step, d_corr, np.random.default_rng(7))
    for lag in (50, 250, 500):                 # 6 m, 30 m, 60 m of travel
        r = np.corrcoef(x[lag:], x[:-lag])[0, 1]
        assert r == pytest.approx(math.exp(-lag * step / d_corr), abs=0.06)


def test_blackout_depth_and_rate_delay_loss_formulas():
    base = PROFILES["blackout"]
    prof = ChannelProfile(**{**base.__dict__, "rician_k_db": 60.0, "shadow_sigma_db": 1e-9})
    tr = generate_trace(prof, duration_s=90, seed=prof.seed)   # canonical seed: fixed blackout windows
    t = np.array([r["timestamp_ms"] for r in tr]) / 1000
    sinr = np.array([r["sinr_db"] for r in tr])
    inside = (t > 30.3) & (t < 32.7)
    outside = (t > 10) & (t < 25)
    assert np.median(sinr[outside]) - np.median(sinr[inside]) == pytest.approx(base.blackout_depth_db, abs=1.0)
    bw = np.array([r["bandwidth_mbps"] for r in tr])
    # The CSV rounds SINR to 0.01 dB; the rate jumps at the -10 dB cut-off, so slots within that
    # rounding band of the cut-off cannot be recomputed from the stored SINR.
    ok = np.abs(sinr - SINR_MIN_DB) > 0.01
    assert np.allclose(bw[ok], attenuated_shannon_se(sinr[ok]) * prof.bandwidth_mhz, atol=0.05)
    loss = np.array([r["packet_loss_pct"] for r in tr])
    expect = np.where(bw <= 0, 100.0, np.clip(0.1 * np.exp(-(sinr - SINR_MIN_DB) / 3.0), 0, 5))
    assert np.allclose(loss, expect, atol=1e-3)
    delay = np.array([r["delay_ms"] for r in tr])
    load = prof.base_delay_ms + 10.0 * (1.0 - np.minimum(bw / (SE_MAX * prof.bandwidth_mhz), 1.0))
    jitter = delay - load
    assert jitter.min() >= -0.01 and jitter.mean() == pytest.approx(2.0, rel=0.1)   # exponential, mean 2 ms
