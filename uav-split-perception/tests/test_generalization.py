"""Tests for the generalization study: n-bit quantization, the closed-form model and its propositions,
and the extra simulator parameters."""

import math

import numpy as np
import pytest
import torch

from quantization import nbit
from quantization.quantizer import FeatureMapQuantizer
from simulation.analytic import (Option, System, break_even_mbps, dominates, endurance_spread_bound, frame_rate,
                                 required_mbps, utility)


# ------------------------------------------------------------------ n-bit quantization
def test_nbit_eight_equals_int8_mode():
    x = torch.randn(1, 32, 20, 20) * 4
    q, s = nbit.quantize(x, 8)
    q_ref, s_ref = FeatureMapQuantizer.quantize(x, dtype="int8")
    assert torch.equal(q, q_ref) and s == s_ref


@pytest.mark.parametrize("bits", range(2, 9))
def test_nbit_error_bound_and_range(bits):
    x = torch.randn(1, 16, 24, 24) * 3
    q, s = nbit.quantize(x, bits)
    m = nbit.qmax(bits)
    assert int(q.min()) >= -m - 1 and int(q.max()) <= m
    err = float((x - nbit.dequantize(q, s)).abs().max())
    assert err <= s / 2 + 2 * np.finfo(np.float32).eps * float(x.abs().max())


@pytest.mark.parametrize("bits", range(2, 8))
def test_bit_packing_roundtrip(bits):
    rng = np.random.default_rng(bits)
    codes = rng.integers(-(1 << (bits - 1)), 1 << (bits - 1), 1001).astype(np.int8)
    buf = nbit.pack(codes, bits)
    assert len(buf) == math.ceil(bits * codes.size / 8)
    assert np.array_equal(nbit.unpack(buf, bits, codes.size), codes)


def test_wire_size_grows_with_bits():
    x = [torch.randn(1, 64, 40, 40)]
    raw = [nbit.wire_bytes(x, b)["raw"] for b in range(2, 9)]
    assert raw == sorted(raw)
    assert all(nbit.wire_bytes(x, b)["zstd"] <= nbit.wire_bytes(x, b)["raw"] for b in range(2, 9))


def test_nbit_rejects_bad_width():
    with pytest.raises(ValueError):
        nbit.qmax(1)
    with pytest.raises(ValueError):
        nbit.qmax(9)


def test_split_hook_accepts_nbit_modes():
    from evaluation.detection_eval import _quant_roundtrip
    x = torch.randn(1, 8, 10, 10)
    assert torch.equal(_quant_roundtrip(x, "int4"), nbit.roundtrip(x, 4))


# ------------------------------------------------------------------ closed-form model
def _random_pair(rng):
    """A split k and an image option q that satisfy the conditions of Proposition 2 (offload dominance)."""
    k = Option("k", "split", phi=rng.uniform(0.05, 0.9), rho=rng.uniform(0, 0.4), bits=rng.uniform(1e5, 2e7),
               server_ms=rng.uniform(1, 50), acc=rng.uniform(0.3, 0.5))
    q = Option("q", "codec", phi=0.0, rho=rng.uniform(0, 0.05), bits=k.bits * rng.uniform(0.01, 1.0),
               server_ms=k.server_ms + rng.uniform(0, 5), acc=k.acc * rng.uniform(0.9, 1.0))
    return k, q


def test_offload_dominance_on_random_inputs():
    rng = np.random.default_rng(0)
    checked = 0
    for _ in range(3000):
        k, q = _random_pair(rng)
        s = System(t_full_ms=rng.uniform(10, 1000), deadline_ms=rng.uniform(50, 2000),
                   camera_fps=float(rng.choice([10, 30, 60])), delay_ms=rng.uniform(0, 100))
        if not dominates(q, k, s):
            continue
        for bw in rng.uniform(0.1, 500, 5):
            u_q, u_k = utility(q, s, bw, 1.0), utility(k, s, bw, 1.0)
            assert required_mbps(q, s) <= required_mbps(k, s) + 1e-12
            assert frame_rate(q, s, bw) >= frame_rate(k, s, bw)
            if u_q > 0:
                assert u_k / u_q <= k.acc / q.acc + 1e-12
            else:
                assert u_k == 0
            checked += 1
    assert checked > 1000


def test_split_vs_onboard_break_even():
    rng = np.random.default_rng(1)
    onboard = Option("full", "onboard", 1.0, 0.0, 0.0, 0.0, 0.44)
    for _ in range(500):
        k = Option("k", "split", rng.uniform(0.05, 0.6), rng.uniform(0, 0.3), rng.uniform(1e5, 1e7),
                   rng.uniform(1, 30), 0.44)
        s = System(t_full_ms=rng.uniform(20, 280), deadline_ms=300.0, camera_fps=1000.0, delay_ms=rng.uniform(0, 50))
        be = break_even_mbps(k, s)
        if math.isinf(be):
            continue
        # Below the break-even the split cannot beat onboard; well above it, it does.
        # (camera_fps is high so that frame-tick quantization does not blur the comparison.)
        assert utility(k, s, be * 0.99, 0.44) <= utility(onboard, s, be * 0.99, 0.44)
        if be * 1e3 < 1e6 and utility(k, s, be * 1e3, 0.44) > 0:
            assert utility(k, s, be * 1e3, 0.44) > utility(onboard, s, be * 1e3, 0.44)


def test_endurance_bound():
    from simulation.system_model import PlatformModel
    rng = np.random.default_rng(2)
    for _ in range(200):
        pc, p0, ptx, prx = rng.uniform(5, 30), rng.uniform(1, 4), rng.uniform(1.5, 6), rng.uniform(0.5, 1.5)
        plat = PlatformModel(battery_wh=rng.uniform(10, 200), avionics_w=rng.uniform(3, 20), hover_w=rng.uniform(10, 400))
        lo, hi = plat.endurance_min(p0 + prx), plat.endurance_min(pc + ptx)  # idle floor vs everything busy
        bound = endurance_spread_bound(pc, p0, ptx, prx, plat.hover_w, plat.avionics_w)
        assert (lo - hi) / lo <= bound + 1e-12


def test_required_bandwidth_matches_measured_system():
    """B* for k4 INT8+zstd at t_full = 180 ms equals the simulator's crossover input (13.3 Mbit/s)."""
    from simulation.system_model import host_full_ms, load_offload_configs
    cfg = load_offload_configs()
    o = Option.from_config(cfg["k4_int8_zstd"], host_full_ms(cfg))
    assert required_mbps(o, System(180.0)) == pytest.approx(13.3, abs=0.05)


# ------------------------------------------------------------------ simulator parameters
def test_simulator_camera_rate_and_custom_profile():
    from simulation.stream_sim import SimParams, simulate
    from simulation.system_model import load_offload_configs, make_hardware
    from simulation.trace_generator import ChannelProfile
    cfg = load_offload_configs()
    prof = ChannelProfile("custom", "test", 15.0, 3.0, 50.0, 10.0, 40.0, 9.0, 10.0, seed=7)
    r = simulate(SimParams(make_hardware(10.0), cfg, mode="jpeg_q90", profile=prof, duration_s=5, camera_fps=15.0))
    assert r["profile"] == "custom"
    assert r["on_time_fps_per_uav"] <= 15.0 + 1e-9
    assert r["on_time_fps_per_uav"] > 10.0
