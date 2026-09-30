"""Tests for the ns-3-calibrated link models used by the validation study (validation/)."""

import math
from pathlib import Path

import numpy as np
import pytest

from simulation.trace_generator import PROFILES, attenuated_shannon_se, generate_trace

VAL = Path(__file__).resolve().parent.parent / "experiments" / "results" / "validation"
need_lte = pytest.mark.skipif(not (VAL / "lte_compare.csv").exists(), reason="run validation V2 first")
need_a2a = pytest.mark.skipif(not (VAL / "a2a_compare.csv").exists(), reason="run validation V1 first")


def test_default_rate_model_is_unchanged():
    p = PROFILES["moderate"]
    a = generate_trace(p, duration_s=5, seed=11)
    b = generate_trace(p, duration_s=5, seed=11, rate_model="tr36942")
    assert a == b
    # The CSV stores SINR rounded to 0.01 dB, so recomputing the rate from it agrees to within
    # the rate change of 0.005 dB (well under 0.05 Mbit/s at these bandwidths).
    sinr = np.array([r["sinr_db"] for r in a])
    assert np.allclose([r["bandwidth_mbps"] for r in a], attenuated_shannon_se(sinr) * p.bandwidth_mhz, atol=0.05)


@need_lte
def test_ns3_lte_mapping_interpolates_measurements():
    import csv
    from simulation.trace_generator import ns3_lte_se
    rows = sorted((float(r["sinr_db"]), float(r["ns3_mbps"]) / 20.0) for r in csv.DictReader(open(VAL / "lte_compare.csv")))
    for s, se in rows:
        assert ns3_lte_se(np.array([s]))[0] == pytest.approx(se)
    grid = np.linspace(-20, 40, 241)
    se = ns3_lte_se(grid)
    assert np.all(np.diff(se) >= -1e-12) and se[0] == 0.0
    trace = generate_trace(PROFILES["good"], duration_s=5, seed=3, rate_model="ns3_lte")
    assert all(r["bandwidth_mbps"] >= 0 for r in trace)


@need_a2a
def test_ns3_a2a_model_distance_and_shadowing():
    from simulation.stream_sim import a2a_rate_ns3_mbps
    d = [10, 50, 100, 200, 400, 700, 1000]
    rates = [a2a_rate_ns3_mbps(x) for x in d]
    assert all(a >= b for a, b in zip(rates, rates[1:])) and rates[-1] == 0.0
    # Shadowing is an equivalent distance change under log-distance path loss (exponent 2.2).
    assert a2a_rate_ns3_mbps(120.0, 4.0) == pytest.approx(a2a_rate_ns3_mbps(120.0 * 10 ** (4.0 / 22.0)))
    assert a2a_rate_ns3_mbps(120.0, 4.0) < a2a_rate_ns3_mbps(120.0) < a2a_rate_ns3_mbps(120.0, -4.0)
