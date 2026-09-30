import math

import numpy as np
import pytest

from simulation.stream_sim import SimParams, StreamSimulator, _waterfill, a2a_rate_mbps, simulate
from simulation.system_model import AdaptivePolicy, EdgeHardware, OffloadConfig, PlatformModel, hover_power_w
from simulation.trace_generator import PROFILES, SE_MAX, attenuated_shannon_se, generate_trace

CFGS = {
    "onboard": OffloadConfig("onboard", "onboard", 22, "fp32", 0, 1.0, 0.0, 0.0, 0.444, 0.611, 0.0),
    "split": OffloadConfig("split", "split", 4, "int8", 800_000, 0.214, 0.4, 6.0, 0.444, 0.611, -0.0001),
    "small": OffloadConfig("small", "codec", -1, "q90", 60_000, 0.0, 1.0, 9.0, 0.440, 0.60, -0.004),
}
HW = EdgeHardware("test", t_full_ms=180.0, host_full_ms=7.5)


def test_attenuated_shannon_mapping():
    se = attenuated_shannon_se(np.array([-20.0, -10.0, 0.0, 50.0]))
    assert se[0] == 0.0 and se[3] == SE_MAX and 0 < se[2] < SE_MAX
    assert np.all(np.diff(attenuated_shannon_se(np.linspace(-9, 40, 100))) >= 0)


def test_traces_are_reproducible_and_seed_dependent():
    a = generate_trace(PROFILES["moderate"], 5.0, seed=1)
    b = generate_trace(PROFILES["moderate"], 5.0, seed=1)
    c = generate_trace(PROFILES["moderate"], 5.0, seed=2)
    assert a == b and a != c


def test_onboard_throughput_is_compute_bound():
    r = simulate(SimParams(HW, CFGS, mode="onboard", duration_s=30))
    period = 1000.0 / 30.0
    effective = math.ceil(180.0 / period) * period  # the next frame starts on a camera tick
    assert r["delivered_fps_per_uav"] == pytest.approx(1000.0 / effective, rel=0.01)
    assert r["latency_p95_ms"] == pytest.approx(180.0)


def test_link_capacity_is_never_exceeded():
    sim = StreamSimulator(SimParams(HW, CFGS, mode="split", profile="moderate", duration_s=60))
    r = sim.run()
    u = sim.uavs[0]
    capacity_bits = float(np.sum(u.bw * (1 - u.loss)) * 1e3 * 10.0)  # Mbps * 10 ms per slot
    sent_bits = sum(f.cfg.payload_bytes * 8 for f in u.frames if f.status == "delivered")
    assert sent_bits <= capacity_bits
    assert r["delivered_fps_per_uav"] < 30.0


def test_deadline_and_statuses():
    r = simulate(SimParams(HW, CFGS, mode="split", profile="blackout", duration_s=60))
    assert r["captured"] == sum(r["status_counts"].values())
    sim = StreamSimulator(SimParams(HW, CFGS, mode="split", profile="blackout", duration_s=60))
    sim.run()
    for f in sim.uavs[0].frames:
        if f.status == "delivered":
            assert f.tx_start_ms - f.capture_ms <= 300.0 + 1e-6


def test_waterfill_respects_capacity_and_demands():
    alloc = _waterfill({0: 10.0, 1: 80.0, 2: 80.0}, 100.0)
    assert sum(alloc.values()) == pytest.approx(100.0)
    assert alloc[0] == 10.0 and alloc[1] == pytest.approx(45.0)
    assert _waterfill({0: 10.0}, None) == {0: 10.0}


def test_policy_score_is_smooth_across_the_deadline():
    p = AdaptivePolicy(list(CFGS.values()), HW)
    c = CFGS["split"]
    budget = 300.0 - HW.onboard_ms(c) - p.delay_ms - c.cloud_ms
    bw_req = c.payload_bytes * 8 / 1e3 / budget  # goodput at which the mean latency hits the deadline
    near = [p.score(c, bw_req * f, 5.0) for f in (0.999, 1.0, 1.001)]
    assert max(near) - min(near) < 0.05
    assert p.predict(c, bw_req, 5.0)["p_on_time"] == pytest.approx(0.5, abs=1e-6)
    scores = [p.score(c, b, 5.0) for b in (10, 30, 60, 120, 400)]
    assert all(a <= b + 1e-9 for a, b in zip(scores, scores[1:]))


def test_policy_prefers_reliable_option_under_uncertainty():
    p = AdaptivePolicy(list(CFGS.values()), HW)
    c = CFGS["split"]
    bw = c.payload_bytes * 8 / 1e3 / (300.0 - HW.onboard_ms(c) - p.delay_ms - c.cloud_ms) * 1.2
    assert p.predict(c, bw, 1.0)["p_on_time"] > p.predict(c, bw, 20.0)["p_on_time"]


def test_policy_prefers_onboard_without_link_and_offload_with_fast_link():
    p = AdaptivePolicy(list(CFGS.values()), HW)
    assert p.decide(0.0).name == "onboard"
    p.current = None
    assert p.decide(500.0).kind != "onboard"


def test_hover_power_matches_momentum_theory():
    t = 1.2 * 9.81
    vi = math.sqrt(t / (2 * 1.225 * 0.2))
    assert hover_power_w() == pytest.approx(t * vi / (0.7 * 0.75))
    assert hover_power_w(mass_kg=2.0) > hover_power_w(mass_kg=1.2)
    assert PlatformModel().endurance_min(10.0) < PlatformModel().endurance_min(0.0)


def test_a2a_rate_decreases_with_distance():
    rates = [a2a_rate_mbps(d) for d in (10, 50, 150, 300, 2000)]
    assert all(a >= b for a, b in zip(rates, rates[1:])) and rates[-1] == 0.0


def test_swarm_statuses_are_conserved_with_relaying():
    r = simulate(SimParams(HW, CFGS, mode="split", profile="blackout", n_uavs=4, relay=True,
                           cell_capacity_mbps=100.0, duration_s=40))
    assert r["captured"] == sum(r["status_counts"].values())
    assert r["relayed_on_time"] <= r["relayed_frames"]


def test_modem_is_never_busy_longer_than_the_run():
    """Own and relayed frames share one modem: its busy time is charged once, never above 100 %."""
    sim = StreamSimulator(SimParams(HW, CFGS, mode="split", profile="vehicular_fading", n_uavs=10, relay=True,
                                    cell_capacity_mbps=100.0, duration_s=30))
    sim.run()
    busy_s = [u.energy.tx_j / (HW.p_tx_w - HW.p_rx_idle_w) for u in sim.uavs]
    assert max(busy_s) <= 30.0 + 1e-9
    assert sum(r is not None for u in sim.uavs for r in (f.relayed_via for f in u.frames)) > 0  # relaying happened


def test_radio_busy_time_is_the_union_of_transmissions():
    from simulation.stream_sim import _union_increments
    assert _union_increments([(0.0, 3.0), (3.0, 2.0)]) == [3.0, 2.0]   # one flow: its exact durations
    assert sum(_union_increments([(0.0, 5.0), (0.0, 10.0)])) == 10.0   # two flows at once: counted once
    assert sum(_union_increments([(4.0, 4.0), (0.0, 5.0), (9.0, 1.0)])) == 9.0
    assert _union_increments([]) == []


def test_a2a_per_model():
    from simulation.stream_sim import A2A_PER_AT_THRESHOLD, a2a_per
    assert a2a_per(14.0, 14.0) == pytest.approx(A2A_PER_AT_THRESHOLD)
    assert a2a_per(16.0, 14.0) == pytest.approx(A2A_PER_AT_THRESHOLD / 10)  # one decade per 2 dB
    assert a2a_per(10.0, 14.0) == 1.0
    snrs = np.linspace(-5, 45, 101)
    assert all(a >= b for a, b in zip([a2a_per(x, 14.0) for x in snrs], [a2a_per(x, 14.0) for x in snrs][1:]))


def test_a2a_link_adaptation_and_shadowing():
    from simulation.stream_sim import A2A_MAC_EFFICIENCY, A2A_MCS, a2a_per, a2a_snr_db
    d = 120.0
    snr = a2a_snr_db(d)
    expected = max(r * (1 - a2a_per(snr, t)) for t, r in A2A_MCS) * A2A_MAC_EFFICIENCY
    assert a2a_rate_mbps(d) == pytest.approx(expected)
    assert a2a_rate_mbps(d, shadow_db=6.0) < a2a_rate_mbps(d) < a2a_rate_mbps(d, shadow_db=-6.0)
    sim = StreamSimulator(SimParams(HW, CFGS, mode="split", profile="moderate", n_uavs=5, duration_s=1))
    sh = sim.a2a_shadow_db
    assert np.allclose(sh, sh.T) and np.all(np.diag(sh) == 0)


def test_packet_forwarding_never_delivers_before_the_a2a_hop_ends():
    """A relay that forwards packets overlaps the hops but cannot send bytes it has not yet received."""
    sim = StreamSimulator(SimParams(HW, CFGS, mode="split", profile="vehicular_fading", n_uavs=10, relay=True,
                                    relay_forwarding="packet", duration_s=60))
    sim.run()
    relayed = [f for u in sim.uavs for f in u.frames if f.relayed_via is not None]
    assert relayed
    for f in relayed:
        if f.status == "delivered":
            assert f.result_ms >= f.a2a_end_ms - 1e-6


def test_packet_forwarding_relayed_frames_are_not_stuck():
    """Once the A2A hop has ended, a relayed frame is limited only by the uplink (no frame may stall)."""
    sim = StreamSimulator(SimParams(HW, CFGS, mode="split", profile="blackout", n_uavs=5, relay=True,
                                    relay_forwarding="packet", cell_capacity_mbps=100.0, duration_s=60))
    sim.run()
    for f in (f for u in sim.uavs for f in u.frames if f.relayed_via is not None and f.status == "aborted"):
        assert f.bits_left > 1.0
