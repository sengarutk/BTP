"""Slotted (10 ms) trace-driven simulator for one or many UAVs streaming perception frames.

Per UAV:
  * camera: frames every 1000/30 ms;
  * onboard processor: one frame at a time; a frame captured while it is busy is skipped;
  * uplink buffer: newest-frame-wins (a frame waiting to be sent is replaced by a newer one);
  * uplink: goodput = trace bandwidth x (1 - residual loss), shared with other transmitting UAVs
    by water-filling the cell capacity; a transfer is dropped once its frame is older than the deadline;
    own and relayed frames share the UAV's one modem, which is charged energy once while either is sent;
  * optional relaying: when the UAV's bandwidth estimate falls below a threshold, a ready frame
    is sent over an 802.11ax air-to-air link (log-distance path loss, per-link log-normal shadowing,
    goodput-maximising MCS with packet errors) to the neighbour with the best estimate, and then
    competes for that neighbour's uplink.
Optional swarm coordination (``coordination="admission"``): a coordinator that knows the shared capacity
and every UAV's reported goodput estimate decides, once per window, how many UAVs K may offload at the same
time (the K that maximises the swarm's expected value, each admitted UAV planning with min(own estimate,
headroom x capacity / expected number sending at once, i.e. K x the duty cycle of its chosen configuration));
the admitted set rotates round-robin over the UAVs whose links can carry a frame. An admitted UAV keeps
choosing per frame (as the uncoordinated policy) among the onboard configurations and the offload
configurations that are admissible for K (K UAVs sending them at the predicted rate fit the capacity).
In a window without contention (every UAV that can usefully offload is admitted and each one's uncoordinated
choice is admissible), coordination is off.
A UAV that is not admitted runs onboard if that scores above zero, and otherwise skips the frame.
A frame is *on time* if its result is available at the ground server within the deadline of
its capture (latency = onboard + queueing + transmission + one-way delay + server time).
"""

import csv
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np

from simulation.system_model import (CAMERA_FPS, DEADLINE_MS, AdaptivePolicy, EdgeHardware, EnergyTally,
                                     OffloadConfig, PlatformModel, PolicyWeights)
from simulation.trace_generator import PROFILES, SLOT_MS, ChannelProfile, generate_trace

# 802.11ax, 20 MHz, 1 spatial stream, 0.8 us GI: (SNR threshold dB, PHY rate Mbps) for MCS 0..11.
A2A_MCS = [(5.0, 8.6), (8.0, 17.2), (11.0, 25.8), (14.0, 34.4), (18.0, 51.6), (22.0, 68.8),
           (24.0, 77.4), (26.0, 86.0), (30.0, 103.2), (32.0, 114.7), (35.0, 129.0), (37.0, 143.4)]
A2A_MAC_EFFICIENCY = 0.65      # MAC/PHY overhead (preamble, IFS, block ACK) at full aggregation
A2A_PER_AT_THRESHOLD = 0.10    # 802.11 receiver-sensitivity criterion: PER <= 10 % at the MCS threshold
A2A_PER_DB_PER_DECADE = 2.0    # waterfall slope of the PER curve around the threshold (assumption)
A2A_SHADOW_SIGMA_DB = 3.0      # log-normal shadowing of each air-to-air link


def a2a_per(snr_db: float, threshold_db: float) -> float:
    """Packet error rate of one MCS: 10 % at its threshold, one decade per 2 dB either side, capped at 1."""
    return min(1.0, A2A_PER_AT_THRESHOLD * 10.0 ** (-(snr_db - threshold_db) / A2A_PER_DB_PER_DECADE))


def a2a_snr_db(dist_m: float, shadow_db: float = 0.0, tx_dbm: float = 20.0, f_ghz: float = 5.8,
               n_exp: float = 2.2, noise_dbm: float = -95.0) -> float:
    """Log-distance path loss (free space at 1 m, exponent n) plus a shadowing term, against the noise floor."""
    pl_1m = 20.0 * math.log10(4.0 * math.pi * f_ghz * 1e9 / 3e8)
    return tx_dbm - (pl_1m + 10.0 * n_exp * math.log10(max(dist_m, 1.0)) + shadow_db) - noise_dbm


_NS3_A2A_TABLE: Optional[Tuple[np.ndarray, np.ndarray]] = None


def a2a_rate_ns3_mbps(dist_m: float, shadow_db: float = 0.0, n_exp: float = 2.2) -> float:
    """A2A goodput from ns-3's 802.11ax model (validation V1, SNR-limited receiver, best MCS).

    Shadowing is applied as the equivalent change of distance under log-distance path loss,
    d_eff = d * 10^(shadow / (10 n)); goodput is interpolated in log-distance. Sensitivity analysis only.
    """
    global _NS3_A2A_TABLE
    if _NS3_A2A_TABLE is None:
        path = Path(__file__).resolve().parent.parent / "experiments" / "results" / "validation" / "a2a_compare.csv"
        if not path.exists():
            raise FileNotFoundError(f"{path} missing; run python -m validation.run_link_validation --which a2a")
        with open(path, newline="", encoding="utf-8") as f:
            rows = sorted((float(r["distance_m"]), float(r["ns3_snr_limited_best_mbps"])) for r in csv.DictReader(f))
        _NS3_A2A_TABLE = (np.log10([r[0] for r in rows]), np.array([r[1] for r in rows]))
    x, y = _NS3_A2A_TABLE
    d_eff = max(dist_m, 1.0) * 10.0 ** (shadow_db / (10.0 * n_exp))
    return float(np.interp(math.log10(d_eff), x, y, left=float(y[0]), right=0.0))


def a2a_rate_mbps(dist_m: float, shadow_db: float = 0.0, **radio) -> float:
    """Mean A2A goodput: link adaptation picks the MCS maximising rate x (1 - PER), times MAC efficiency.

    Retransmissions of errored packets are what the (1 - PER) factor accounts for.
    """
    snr = a2a_snr_db(dist_m, shadow_db, **radio)
    best = max(r * (1.0 - a2a_per(snr, thr)) for thr, r in A2A_MCS)
    return best * A2A_MAC_EFFICIENCY


@dataclass
class Frame:
    uav: int
    capture_ms: float
    cfg: Optional[OffloadConfig]
    ready_ms: float = math.inf
    status: str = "processing"
    bits_left: float = 0.0
    tx_start_ms: float = math.nan
    result_ms: float = math.nan
    relayed_via: Optional[int] = None
    a2a_start_ms: float = math.nan   # A2A transfer interval of a relayed frame ("packet" forwarding)
    a2a_end_ms: float = math.nan

    @property
    def latency_ms(self) -> float:
        return self.result_ms - self.capture_ms


@dataclass
class Flow:
    """One transmit queue on a UAV's uplink (its own frames, or frames relayed for others)."""
    pending: Optional[Frame] = None
    current: Optional[Frame] = None
    blocked_until: float = 0.0   # the link is held until this time after a frame (release_extra_ms)


@dataclass
class UAV:
    idx: int
    pos: np.ndarray
    bw: np.ndarray        # Mbps per slot
    delay: np.ndarray     # ms per slot
    loss: np.ndarray      # fraction per slot
    policy: Optional[AdaptivePolicy]
    fixed: Optional[OffloadConfig]
    est_mbps: float = 0.0
    est_var: float = 0.0
    compute_free_ms: float = 0.0
    a2a_free_ms: float = 0.0
    own: Flow = field(default_factory=Flow)
    relay: Flow = field(default_factory=Flow)
    energy: EnergyTally = field(default_factory=EnergyTally)
    frames: List[Frame] = field(default_factory=list)
    processing: List[Frame] = field(default_factory=list)
    in_a2a: List[Tuple[float, Frame, int]] = field(default_factory=list)

    def slot(self, s: int) -> int:
        return s % len(self.bw)


@dataclass
class SimParams:
    hw: EdgeHardware
    configs: Dict[str, OffloadConfig]
    mode: str = "adaptive"                  # "adaptive" or a config name
    candidates: Optional[List[str]] = None  # configs the adaptive policy may choose from
    profile: Union[str, ChannelProfile] = "moderate"   # a PROFILES name or a custom profile
    n_uavs: int = 1
    duration_s: float = 120.0
    seed: int = 0
    deadline_ms: float = DEADLINE_MS
    cell_capacity_mbps: Optional[float] = None
    relay: bool = False
    relay_threshold_mbps: float = 5.0
    relay_neighbor_min_mbps: float = 15.0
    spacing_m: float = 50.0
    est_tau_ms: float = 200.0
    camera_fps: float = CAMERA_FPS
    hysteresis: float = 0.05
    policy_weights: Optional[PolicyWeights] = None
    platform: Optional[PlatformModel] = None
    carrier_hz: float = 3.5e9
    policy_delay_ms: float = 20.0           # one-way delay the adaptive policy assumes
    a2a_shadow_sigma_db: float = A2A_SHADOW_SIGMA_DB
    rate_model: str = "tr36942"             # cellular SINR->rate mapping ("ns3_lte": calibrated, V2)
    a2a_model: str = "analytic"             # air-to-air goodput ("ns3": calibrated, V1)
    sharing: str = "waterfill"              # cell sharing: "waterfill", "capped", "weighted" (see share_cell)
    sharing_k: int = 7                      # UAVs served at once under "capped" (Simu5G PF, validation O2)
    release_extra_ms: float = 0.0           # hold the link this long after each frame (e.g. an ack round trip)
    relay_forwarding: str = "frame"         # "frame": the relay sends a frame once it has all of it;
                                            # "packet": forwards bytes as they arrive (hops overlap; validation O5)
    coordination: str = "none"              # "none": every UAV decides alone; "admission": see module docstring
    coord_window_ms: float = 1000.0         # admission decision / rotation period
    coord_feedback: str = "none"            # learn from the last window (see _feedback): "kcap" admitted UAVs that
                                            # got nothing through cap K; "full" also shared lateness -> AIMD capacity;
                                            # "rssi" as "full" but link health from the radio's instantaneous capacity
    coord_headroom: float = 1.1             # capacity multiple planned with (tuned on seeds 100-101, not the study seeds)


def _formation(n: int, spacing: float) -> List[np.ndarray]:
    cols = max(1, math.ceil(math.sqrt(n)))
    return [np.array([(i % cols) * spacing, (i // cols) * spacing, 80.0]) for i in range(n)]


def _union_increments(intervals: List[Tuple[float, float]]) -> List[float]:
    """Lengths that (start, duration) intervals add to their union, in time order.

    Non-overlapping intervals contribute their exact durations, so a modem used by one flow is charged
    exactly as if each transmission were added on its own; overlapping time is counted once.
    """
    out, end = [], -math.inf
    for start, dur in sorted(intervals, key=lambda iv: iv[0]):
        if start >= end:
            out.append(dur)
            end = start + dur
        elif start + dur > end:
            out.append(start + dur - end)
            end = start + dur
    return out


def _waterfill(demands: Dict[int, float], capacity: Optional[float]) -> Dict[int, float]:
    if capacity is None or sum(demands.values()) <= capacity:
        return dict(demands)
    alloc, remaining, left = {}, capacity, dict(demands)
    while left:
        share = remaining / len(left)
        capped = {u: d for u, d in left.items() if d <= share}
        if not capped:
            alloc.update({u: share for u in left})
            break
        for u, d in capped.items():
            alloc[u] = d
            remaining -= d
            del left[u]
    return alloc


def _waterfill_weighted(demands: Dict[int, float], capacity: Optional[float],
                        weights: Dict[int, float]) -> Dict[int, float]:
    """Weighted max-min sharing: capacity split in proportion to the weights, no UAV above its demand."""
    if capacity is None or sum(demands.values()) <= capacity:
        return dict(demands)
    alloc, remaining, left = {}, capacity, dict(demands)
    while left:
        wsum = sum(weights[u] for u in left)
        capped = {u: d for u, d in left.items() if d <= remaining * weights[u] / wsum}
        if not capped:
            alloc.update({u: remaining * weights[u] / wsum for u in left})
            break
        for u, d in capped.items():
            alloc[u] = d
            remaining -= d
            del left[u]
    return alloc


def share_cell(demands: Dict[int, float], capacity: Optional[float], model: str, k: int,
               priority: Dict[int, float], weights: Dict[int, float]) -> Dict[int, float]:
    """Cell capacity allocation among UAVs with traffic.

    waterfill  max-min fair (the paper's model; exact against Simu5G for N <= 5 and mixed demands)
    capped     only the k highest-priority UAVs with traffic are served (persistent priority), the rest
               get nothing: the starvation Simu5G's proportional-fair uplink scheduler shows with >= 10
               saturated UAVs (k = 7 there)
    weighted   everyone is served, in proportion to persistent random weights (unequal, like MAX-C/I)
    """
    if model == "waterfill" or capacity is None:
        return _waterfill(demands, capacity)
    if model == "capped":
        # UAVs whose demand fits within the max-min fair share are always served in full (as in
        # validation O2b); among the bottlenecked ones only the k highest-priority are served.
        fair = _waterfill(demands, capacity)
        light = {u for u, a in fair.items() if a >= demands[u] - 1e-9}
        heavy = sorted((u for u in demands if u not in light), key=lambda u: priority[u])
        served = light | set(heavy[:k])
        alloc = _waterfill({u: demands[u] for u in served}, capacity)
        alloc.update({u: 0.0 for u in demands if u not in alloc})
        return alloc
    if model == "weighted":
        return _waterfill_weighted(demands, capacity, weights)
    raise ValueError(f"unknown sharing model {model}")


class StreamSimulator:
    def __init__(self, p: SimParams):
        self.p = p
        prof = PROFILES[p.profile] if isinstance(p.profile, str) else p.profile
        pos = _formation(p.n_uavs, p.spacing_m)
        self.uavs: List[UAV] = []
        cand = [p.configs[c] for c in (p.candidates or p.configs)]
        for u in range(p.n_uavs):
            recs = generate_trace(prof, duration_s=p.duration_s, seed=prof.seed * 100_003 + p.seed * 1_009 + u,
                                  fc_hz=p.carrier_hz, rate_model=p.rate_model)
            policy = (AdaptivePolicy(cand, p.hw, weights=p.policy_weights, deadline_ms=p.deadline_ms,
                                     hysteresis=p.hysteresis, camera_fps=p.camera_fps,
                                     one_way_delay_ms=p.policy_delay_ms)
                      if p.mode == "adaptive" else None)
            fixed = None if p.mode == "adaptive" else p.configs[p.mode]
            self.uavs.append(UAV(
                u, pos[u],
                np.array([r["bandwidth_mbps"] for r in recs]),
                np.array([r["delay_ms"] for r in recs]),
                np.array([r["packet_loss_pct"] for r in recs]) / 100.0,
                policy, fixed))
        self.decisions: List[Tuple[float, int, str]] = []
        # Persistent scheduler priorities / weights for the non-default cell-sharing models.
        srng = np.random.default_rng(prof.seed * 100_003 + p.seed * 1_009 + 104_729)
        self._priority = {u: float(x) for u, x in enumerate(srng.permutation(p.n_uavs))}
        self._weights = {u: float(w) for u, w in enumerate(srng.lognormal(0.0, 1.0, p.n_uavs))}
        # Static log-normal shadowing per unordered UAV pair (links are reciprocal).
        rng = np.random.default_rng(prof.seed * 100_003 + p.seed * 1_009 + 7_919)
        sh = rng.normal(0.0, p.a2a_shadow_sigma_db, (p.n_uavs, p.n_uavs))
        self.a2a_shadow_db = np.triu(sh, 1) + np.triu(sh, 1).T

    # ------------------------------------------------------------------ helpers
    def _feedback(self, t0: float) -> None:
        """Outcome of the window that just ended (frames captured in it that have finished): a UAV whose
        offloaded frames were mostly late although its own link was healthy signals hidden contention (with
        "full", when at least two UAVs show it); admitted UAVs that delivered nothing
        while sending signal a scheduler that serves fewer UAVs than planned. K_cap: multiplicative cut to
        the number served, then +1 per window. The planned capacity is scaled by an AIMD factor: x0.8 after a
        window with late offloads, +0.05 (up to 1) after one without."""
        w0, n_late, served, starved = t0 - self.p.coord_window_ms, 0, 0, 0
        for u in self.uavs:
            fr = [f for f in u.frames if w0 <= f.capture_ms < t0 and f.cfg is not None and f.cfg.kind != "onboard"
                  and f.status in ("delivered", "aborted", "stale")]
            if len(fr) < 3:
                continue
            ok = sum(f.status == "delivered" and f.latency_ms <= self.p.deadline_ms for f in fr)
            # late although the UAV's own link is healthy (a blackout on its own link is not contention). "full":
            # the smoothed goodput estimate; "rssi": the radio's own instantaneous link capacity over the window
            # (what a modem's signal level gives), its worst slot
            if self.p.coord_feedback == "rssi":
                s0, s1 = int(w0 / SLOT_MS), int(t0 / SLOT_MS)
                own = min(u.bw[u.slot(k)] * (1.0 - u.loss[u.slot(k)]) for k in range(max(0, s0), max(s0 + 1, s1)))
            else:
                own = u.est_mbps
            n_late += ok < 0.7 * len(fr) and own >= self.p.cell_capacity_mbps / max(1, self.p.n_uavs)
            if self._contended and u.idx in self._admitted:
                got = any(f.status == "delivered" for f in fr)
                healthy = self.p.coord_feedback != "rssi" or own >= self.p.cell_capacity_mbps / max(1, self.p.n_uavs)
                served += got
                starved += (not got) and healthy      # "rssi": a UAV in its own blackout is not starved
        if self.p.coord_feedback in ("full", "rssi"):   # contention: several healthy-link UAVs late together
            late = n_late >= 2
            self._force = late
            self._capf = max(0.3, self._capf * 0.8) if late else min(1.0, self._capf + 0.05)   # AIMD on capacity
        if starved:
            self._kcap = max(1, served)
        else:
            self._kcap += 1

    def _coordinate(self) -> None:
        """Admission decision for the next window (coordination == "admission")."""
        p, cap = self.p, self.p.cell_capacity_mbps * self.p.coord_headroom * self._capf
        pol = [u.policy for u in self.uavs]
        on = [max(0.0, max((pl.score(c, 0.0) for c in pl.configs if c.kind == "onboard"), default=0.0)) for pl in pol]
        off_cfgs = [c for c in pol[0].configs if c.kind != "onboard"]

        def plan(u, k):
            """(value, {admissible configuration: planning share}) of UAV u when k UAVs offload. For each
            configuration: its duty cycle d
            on the UAV's own link, a share of capacity / (k x d) (the expected number sending at once), and
            it is admissible only if k UAVs sending it at the predicted rate fit within the capacity."""
            std, best, allowed = math.sqrt(u.est_var), 0.0, {}
            for c in off_cfgs:
                bits = c.payload_bytes * 8e-6
                d = min(1.0, u.policy.predict(c, u.est_mbps, std)["fps"] * bits / max(u.est_mbps, 1e-6))
                share = min(u.est_mbps, cap / max(1.0, k * d))
                if k * u.policy.predict(c, share, std)["fps"] * bits > cap:
                    continue
                allowed[c.name] = share
                best = max(best, u.policy.score(c, share, std))
            return best, allowed
        elig = [u for u in self.uavs if plan(u, 1)[0] > on[u.idx]]
        best_k, best_v, shares = 0, sum(on), {}
        for k in range(1, min(len(elig), self._kcap) + 1):
            pk = {u.idx: plan(u, k) for u in elig}
            v = sum(on) + sum(k / len(elig) * (pk[u.idx][0] - on[u.idx]) for u in elig)
            if v > best_v + 1e-9:
                best_k, best_v, shares = k, v, {i: x[1] for i, x in pk.items()}
        order = sorted(elig, key=lambda u: (u.idx - self._rr) % self.p.n_uavs)
        self._admitted = {u.idx for u in order[:best_k]}
        self._shares = shares
        # Contention: someone is held back, or someone's uncoordinated choice would not fit. Otherwise every
        # UAV decides alone, exactly as without coordination.
        def alone(u):
            sh = min(u.est_mbps, self.p.cell_capacity_mbps / max(1, len(elig)))
            return max(u.policy.configs, key=lambda c: u.policy.score(c, sh, math.sqrt(u.est_var)))
        self._contended = best_k < len(elig) or self._force or any(
            alone(u).kind != "onboard" and alone(u).name not in shares.get(u.idx, {}) for u in elig)
        self._k = max(1, best_k)
        if order[:best_k]:
            self._rr = (order[best_k - 1].idx + 1) % self.p.n_uavs
        self.coord_log.append((best_k, len(elig)))

    def _choose(self, uav: UAV, t_ms: float) -> Optional[OffloadConfig]:
        if uav.fixed is not None:
            return uav.fixed
        if self.p.coordination == "admission" and self.p.cell_capacity_mbps is not None and self._contended:
            pl = uav.policy
            onb = [c for c in pl.configs if c.kind == "onboard"]
            if uav.idx in self._admitted:      # per-frame choice among the admissible configurations and onboard
                std = math.sqrt(uav.est_var)
                cand = {c.name: (c, pl.score(c, min(uav.est_mbps, sh), std))
                        for c in pl.configs for sh in [self._shares[uav.idx].get(c.name)] if sh is not None}
                cand.update({c.name: (c, pl.score(c, 0.0)) for c in onb})
                cfg, sc = max(cand.values(), key=lambda x: x[1])
                cur = cand.get(pl.current.name) if pl.current is not None else None
                if cur is not None and cfg is not cur[0] and sc <= cur[1] + pl.hysteresis * abs(cur[1]):
                    cfg = cur[0]
                elif cfg is not pl.current:
                    pl.switches += int(pl.current is not None)
                    pl.current = cfg
            else:
                cfg = max(onb, key=lambda c: pl.score(c, 0.0)) if onb else None
                if cfg is None or pl.score(cfg, 0.0) <= 0:
                    return None
            if not self.decisions or self.decisions[-1][1:] != (uav.idx, cfg.name):
                self.decisions.append((t_ms, uav.idx, cfg.name))
            return cfg
        share = uav.est_mbps
        if self.p.cell_capacity_mbps is not None:
            share = min(share, self.p.cell_capacity_mbps / max(1, self._active_radios))
        cfg = uav.policy.decide(share, math.sqrt(uav.est_var))
        if not self.decisions or self.decisions[-1][1:] != (uav.idx, cfg.name):
            self.decisions.append((t_ms, uav.idx, cfg.name))
        return cfg

    def _relay_target(self, uav: UAV, now_ms: float) -> Optional[Tuple[int, float]]:
        best = None
        for other in self.uavs:
            # a neighbour is busy while a whole relayed frame waits in its queue; under packet
            # forwarding a frame still crossing the A2A link does not count yet, as under frame forwarding
            waiting = other.relay.pending is not None and not (self.p.relay_forwarding == "packet"
                                                               and other.relay.pending.a2a_end_ms > now_ms)
            if other is uav or other.est_mbps < self.p.relay_neighbor_min_mbps or waiting:
                continue
            a2a = a2a_rate_ns3_mbps if self.p.a2a_model == "ns3" else a2a_rate_mbps
            rate = a2a(float(np.linalg.norm(uav.pos - other.pos)), float(self.a2a_shadow_db[uav.idx, other.idx]))
            if rate > 0 and (best is None or other.est_mbps > self.uavs[best[0]].est_mbps):
                best = (other.idx, rate)
        return best

    def _enqueue(self, flow: Flow, frame: Frame) -> None:
        if flow.pending is not None:
            flow.pending.status = "superseded"
        flow.pending = frame
        frame.status = "queued"

    # ------------------------------------------------------------------ main loop
    def run(self) -> Dict:
        p = self.p
        n_slots = int(p.duration_s * 1000.0 / SLOT_MS)
        frame_period = 1000.0 / p.camera_fps
        next_capture = [0.0] * p.n_uavs
        alpha = 1.0 - math.exp(-SLOT_MS / p.est_tau_ms)
        self._active_radios = 1
        self._admitted, self._k, self._rr, self._shares, self.coord_log = set(), 1, 0, {}, []
        self._contended, self._force, self._kcap, self._capf = False, False, 10 ** 6, 1.0
        next_window = 0.0

        for s in range(n_slots):
            t0, t1 = s * SLOT_MS, (s + 1) * SLOT_MS
            for u in self.uavs:  # causal EWMA mean/variance of the previous slot's goodput
                prev = u.slot(max(s - 1, 0))
                obs = u.bw[prev] * (1.0 - u.loss[prev])
                if s == 0:
                    u.est_mbps, u.est_var = obs, 0.0
                else:
                    diff = obs - u.est_mbps
                    u.est_mbps += alpha * diff
                    u.est_var = (1.0 - alpha) * (u.est_var + alpha * diff * diff)

            if p.coordination == "admission" and p.mode == "adaptive" and t0 >= next_window:
                if p.coord_feedback != "none" and t0 > 0:
                    self._feedback(t0)
                self._coordinate()
                next_window += p.coord_window_ms

            # 1) captures and onboard processing
            for u in self.uavs:
                while next_capture[u.idx] < t1:
                    tc = next_capture[u.idx]
                    next_capture[u.idx] += frame_period
                    if u.compute_free_ms > tc:
                        u.frames.append(Frame(u.idx, tc, None, status="skipped_busy"))
                        continue
                    cfg = self._choose(u, tc)
                    if cfg is None:
                        u.frames.append(Frame(u.idx, tc, None, status="skipped_admission"))
                        continue
                    f = Frame(u.idx, tc, cfg)
                    u.frames.append(f)
                    u.processing.append(f)
                    t_on = p.hw.onboard_ms(cfg)
                    u.energy.add_compute(p.hw, t_on)
                    f.ready_ms = tc + t_on
                    u.compute_free_ms = f.ready_ms

            # 2) frames becoming ready: deliver onboard results or queue for the uplink / relay
            for u in self.uavs:
                for f in [f for f in u.processing if f.ready_ms < t1]:
                    u.processing.remove(f)
                    if f.cfg.kind == "onboard":
                        f.status, f.result_ms = "delivered", f.ready_ms
                        continue
                    target = None
                    if p.relay and p.n_uavs > 1 and u.est_mbps < p.relay_threshold_mbps:
                        target = self._relay_target(u, f.ready_ms)
                    if target is None:
                        self._enqueue(u.own, f)
                    else:
                        j, rate = target
                        start = max(f.ready_ms, u.a2a_free_ms)
                        a2a_ms = f.cfg.payload_bytes * 8.0 / (rate * 1e3)
                        u.a2a_free_ms = start + a2a_ms
                        u.energy.add_a2a(p.hw, a2a_ms)
                        f.status, f.relayed_via = "in_a2a", j
                        f.a2a_start_ms, f.a2a_end_ms = start, start + a2a_ms
                        # packet forwarding: the relay may start once the first bytes have arrived
                        u.in_a2a.append((start if p.relay_forwarding == "packet" else start + a2a_ms, f, j))
                for arrival, f, j in list(u.in_a2a):
                    if arrival < t1:
                        u.in_a2a.remove((arrival, f, j))
                        f.ready_ms = arrival
                        self._enqueue(self.uavs[j].relay, f)

            # 3) uplink capacity allocation (water-filling across UAVs with traffic)
            demands = {}
            for u in self.uavs:
                busy = any(fl.current is not None or (fl.pending is not None and fl.pending.ready_ms < t1)
                           for fl in (u.own, u.relay))
                if busy:
                    k = u.slot(s)
                    demands[u.idx] = u.bw[k] * (1.0 - u.loss[k])
            self._active_radios = max(1, len(demands))
            alloc = share_cell(demands, p.cell_capacity_mbps, p.sharing, p.sharing_k, self._priority, self._weights)

            # 4) transmission within the slot
            for u in self.uavs:
                if u.idx not in alloc:
                    continue
                flows = [fl for fl in (u.own, u.relay)
                         if fl.current is not None or (fl.pending is not None and fl.pending.ready_ms < t1)]
                rate = alloc[u.idx] / len(flows)  # Mbps == bits per microsecond; per ms: *1e3
                spare_bits = 0.0
                if p.relay_forwarding == "packet" and len(flows) == 2:
                    flows = [u.relay, u.own]      # the relay flow first: what it cannot use goes to the own flow
                k = u.slot(s)
                on_air: List[Tuple[float, float]] = []  # (start, duration) of every transmission in this slot
                for fl in flows:
                    if fl is u.own and spare_bits > 0:
                        rate += spare_bits / (1e3 * (t1 - t0))
                    t = t0
                    sent_bits = 0.0
                    while t < t1:
                        if fl.current is None:
                            if fl.pending is None or fl.pending.ready_ms >= t1 or fl.blocked_until >= t1:
                                break
                            f = fl.pending
                            fl.pending = None
                            t = max(t, f.ready_ms, fl.blocked_until)
                            if t - f.capture_ms > p.deadline_ms:
                                f.status = "stale"
                                continue
                            f.status, f.tx_start_ms = "sending", t
                            f.bits_left = f.cfg.payload_bytes * 8.0
                            fl.current = f
                        f = fl.current
                        if t - f.capture_ms > p.deadline_ms:  # cannot be on time any more
                            f.status, fl.current = "aborted", None
                            continue
                        cap_bits = rate * 1e3 * (t1 - t)
                        if p.relay_forwarding == "packet" and fl is u.relay and f.a2a_end_ms > t1:
                            # cannot forward bytes that have not yet arrived over the A2A link
                            total = f.cfg.payload_bytes * 8.0
                            got = total * (t1 - f.a2a_start_ms) / max(f.a2a_end_ms - f.a2a_start_ms, 1e-9)
                            cap_bits = min(cap_bits, got - (total - f.bits_left))
                        if rate <= 0 or cap_bits < f.bits_left:
                            f.bits_left -= max(cap_bits, 0.0)
                            sent_bits += max(cap_bits, 0.0)
                            on_air.append((t, t1 - t))
                            break
                        sent_bits += f.bits_left
                        dt = f.bits_left / (rate * 1e3)
                        if p.relay_forwarding == "packet" and fl is u.relay:
                            dt = max(dt, f.a2a_end_ms - t)  # the last byte leaves after it has arrived
                        on_air.append((t, dt))
                        t += dt
                        f.result_ms = t + u.delay[k] + f.cfg.cloud_ms
                        f.status, fl.current = "delivered", None
                        fl.blocked_until = t + p.release_extra_ms
                    if p.relay_forwarding == "packet" and fl is u.relay:
                        spare_bits = max(0.0, rate * 1e3 * (t1 - t0) - sent_bits)
                # Both flows share one modem: charge the time either is on air, not the sum.
                for busy_ms in _union_increments(on_air):
                    u.energy.add_tx(p.hw, busy_ms)

        return self._summary(n_slots * SLOT_MS / 1000.0)

    # ------------------------------------------------------------------ metrics
    def _summary(self, duration_s: float) -> Dict:
        p = self.p
        platform = p.platform or PlatformModel()
        per_uav, lat, acc_on_time = [], [], []
        totals: Dict[str, int] = {}
        usage: Dict[str, int] = {}
        relayed = relayed_on_time = 0
        for u in self.uavs:
            counts: Dict[str, int] = {}
            on_time = 0
            for f in u.frames:
                if f.status in ("processing", "queued", "sending", "in_a2a"):
                    f.status = "unfinished"
                counts[f.status] = counts.get(f.status, 0) + 1
                if f.cfg is not None:
                    usage[f.cfg.name] = usage.get(f.cfg.name, 0) + 1
                if f.status == "delivered":
                    lat.append(f.latency_ms)
                    if f.latency_ms <= p.deadline_ms:
                        on_time += 1
                        acc_on_time.append(f.cfg.map50_95)
                if f.relayed_via is not None:
                    relayed += 1
                    relayed_on_time += int(f.status == "delivered" and f.latency_ms <= p.deadline_ms)
            power = u.energy.average_power_w(p.hw, duration_s)
            per_uav.append({"uav": u.idx, "on_time_fps": on_time / duration_s, "perception_power_w": power,
                            "endurance_min": platform.endurance_min(power), **counts})
            for k, v in counts.items():
                totals[k] = totals.get(k, 0) + v
        captured = sum(len(u.frames) for u in self.uavs)
        lat_arr = np.array(lat) if lat else None
        return {
            "mode": p.mode, "profile": p.profile if isinstance(p.profile, str) else p.profile.name, "n_uavs": p.n_uavs, "seed": p.seed, "t_full_ms": p.hw.t_full_ms,
            "relay": p.relay, "cell_capacity_mbps": p.cell_capacity_mbps,
            "captured": captured,
            "delivered_fps_per_uav": totals.get("delivered", 0) / duration_s / p.n_uavs,
            "on_time_fps_per_uav": float(np.mean([r["on_time_fps"] for r in per_uav])),
            "on_time_fraction": sum(r["on_time_fps"] for r in per_uav) * duration_s / captured,
            "latency_p50_ms": float(np.percentile(lat_arr, 50)) if lat_arr is not None else math.nan,
            "latency_p95_ms": float(np.percentile(lat_arr, 95)) if lat_arr is not None else math.nan,
            "mean_map50_95_on_time": float(np.mean(acc_on_time)) if acc_on_time else math.nan,
            "perception_power_w": float(np.mean([r["perception_power_w"] for r in per_uav])),
            "endurance_min": float(np.mean([r["endurance_min"] for r in per_uav])),
            "relayed_frames": relayed,
            "relayed_on_time": relayed_on_time,
            "policy_switches": sum(u.policy.switches for u in self.uavs if u.policy),
            "admitted_mean": float(np.mean([k for k, _ in self.coord_log])) if self.coord_log else math.nan,
            "status_counts": totals,
            "config_usage": usage,
            "per_uav": per_uav,
        }


def simulate(params: SimParams) -> Dict:
    return StreamSimulator(params).run()
