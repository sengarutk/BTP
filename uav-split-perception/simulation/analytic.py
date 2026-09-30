"""Closed-form model of onboard / split / offload perception (Section 6.1 of paper/main.tex).

Notation as in the paper (per configuration c; times in ms, rates in Mbit/s, payloads in bits):
  t_full  onboard latency of the full model (hardware parameter)
  phi_c   fraction of the model's FLOPs executed onboard (1 onboard, phi_k split at k, 0 codec)
  rho_c   other onboard work (quantize+serialize, or image encoding) as a fraction of the full-model
          time, measured on the host; it scales with the same hardware factor, so it costs rho_c t_full
  b_c     payload per frame;  s_c server time;  d one-way network delay
  D       deadline;  F camera rate;  B goodput available to this UAV;  A_c accuracy (mAP)
  A_ref   accuracy of the unsplit FP32 model

  onboard time   e_c = t_full (phi_c + rho_c)
  latency        L_c(B) = e_c + b_c / B + d + s_c        (onboard inference: L = t_full, nothing is sent)
  on time        L_c <= D  <=>  B >= B*_c = b_c / (D - e_c - d - s_c)   (B*_c = inf if D <= e_c + d + s_c)
  frame rate     f_c(B) = F / ceil(F * max(e_c, b_c / B))              (edge and link pipelined)
  utility        U_c(B) = f_c(B) * 1[B >= B*_c] * A_c / A_ref          (accuracy-weighted on-time rate)
  energy/frame   E_c(B) = (P_busy - P_idle) e_c + (P_tx - P_rx) b_c / B

Proposition 2 (offload dominance). If b_q <= b_k, e_q <= e_k and e_q + s_q <= e_k + s_k, then for
every B, d, D, F: L_q <= L_k, B*_q <= B*_k, f_q >= f_k, E_q <= E_k, and therefore
U_k / U_q <= A_k / A_q whenever U_q > 0. A split can beat such an offload option only by its
accuracy ratio, whatever the channel, hardware, deadline, frame rate or swarm size (the same holds
for any capacity share that does not decrease with a smaller demand, e.g. water-filling).

Proposition 3 (split versus onboard). With onboard on time (t_full <= D), split k has a higher on-time
rate f_k 1[B >= B*_k] than onboard iff B >= B*_k and ceil(F max(e_k, b_k / B)) < ceil(F t_full). This
needs B > b_k / t_full and phi_k + rho_k < 1, so B_be = max(b_k / t_full, B*_k) is necessary (it is what
break_even_mbps returns). The exact conditions are e_k <= (n - 1) / F and B >= max(B*_k, F b_k / (n - 1))
with n = ceil(F t_full) >= 2. Dimensionless: offloading helps only if beta = B t_full / b_k > 1.

Proposition 4 (swarm capacity). Water-filling a cell of capacity C gives each of N UAVs at least
min(B_i, C / N), B_i its own goodput. If every B_i >= B*_c, configuration c stays on time for
N <= C / B*_c, and keeps its full rate for N <= C / max(B*_c, F_c b_c), with F_c its sustainable
frame rate. Supported swarm sizes of two options satisfy N_q / N_k = (b_k / b_q) (slack_q / slack_k),
slack_c = D - e_c - d - s_c.

Proposition 5 (endurance). Endurance = 60 W_bat / (P_hover + P_av + P_perc) minutes. Any perception
strategy changes P_perc by at most (P_busy - P_idle) + (P_tx - P_rx), so the relative endurance spread
across strategies is bounded by that sum over (P_hover + P_av + P_idle + P_rx).

Proposition 1 of the paper is the INT8 error bound (quantization/quantizer.py).
"""

import math
from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np


@dataclass(frozen=True)
class Option:
    name: str
    kind: str          # onboard | split | codec
    phi: float         # onboard FLOP fraction
    rho: float         # other onboard work / host full-model time
    bits: float        # payload per frame (bits)
    server_ms: float   # server time
    acc: float         # mAP@[.5:.95]

    @staticmethod
    def from_config(cfg, host_full_ms: float) -> "Option":
        return Option(cfg.name, cfg.kind, 1.0 if cfg.kind == "onboard" else cfg.edge_flop_frac,
                      cfg.host_edge_proc_ms / host_full_ms, cfg.payload_bytes * 8.0, cfg.cloud_ms, cfg.map50_95)


@dataclass(frozen=True)
class System:
    t_full_ms: float
    deadline_ms: float = 300.0
    camera_fps: float = 30.0
    delay_ms: float = 20.0
    server_scale: float = 1.0      # server time multiplier (1 = measured host GPU)


def onboard_ms(o: Option, s: System) -> float:
    return s.t_full_ms * (o.phi + (0.0 if o.kind == "onboard" else o.rho))


def required_mbps(o: Option, s: System) -> float:
    """B*_c: goodput needed to meet the deadline (0 for onboard if feasible, inf if impossible)."""
    if o.kind == "onboard":
        return 0.0 if s.t_full_ms <= s.deadline_ms else math.inf
    slack = s.deadline_ms - onboard_ms(o, s) - s.delay_ms - o.server_ms * s.server_scale
    return math.inf if slack <= 0 else o.bits / 1e3 / slack   # kbit / ms = Mbit/s


def frame_rate(o: Option, s: System, bw_mbps: float) -> float:
    period = 1000.0 / s.camera_fps
    tx = 0.0 if o.kind == "onboard" else (math.inf if bw_mbps <= 0 else o.bits / 1e3 / bw_mbps)
    bottleneck = max(onboard_ms(o, s), tx)
    if math.isinf(bottleneck):
        return 0.0
    return s.camera_fps / max(1, math.ceil(bottleneck / period - 1e-9))


def utility(o: Option, s: System, bw_mbps: float, acc_ref: float) -> float:
    if bw_mbps < required_mbps(o, s):
        return 0.0
    return frame_rate(o, s, bw_mbps) * o.acc / acc_ref


def dominates(q: Option, k: Option, s: System) -> bool:
    """Proposition 2 (offload dominance) conditions: q needs no more bits, onboard time, or onboard+server time than k."""
    e_q, e_k = onboard_ms(q, s), onboard_ms(k, s)
    return (q.bits <= k.bits and e_q <= e_k
            and e_q + q.server_ms * s.server_scale <= e_k + k.server_ms * s.server_scale)


def break_even_mbps(k: Option, s: System) -> float:
    """Proposition 3 (split versus onboard): B_be, the goodput below which split k cannot beat onboard.

    Camera-tick rounding can push the actual threshold above B_be (see the module docstring).
    """
    if k.phi + k.rho >= 1.0:
        return math.inf
    return max(k.bits / 1e3 / s.t_full_ms, required_mbps(k, s))


def swarm_capacity(o: Option, s: System, cell_mbps: float, full_rate: bool = False) -> float:
    """Proposition 4 (swarm capacity): how many UAVs a cell supports with option o on time (or at its full rate)."""
    need = required_mbps(o, s)
    if full_rate and o.kind != "onboard":
        rate = frame_rate(o, s, math.inf)
        need = max(need, o.bits / 1e6 * rate)
    return math.inf if need == 0 else (0.0 if math.isinf(need) else cell_mbps / need)


def endurance_spread_bound(p_compute: float, p_idle: float, p_tx: float, p_rx: float,
                           p_hover: float, p_avionics: float) -> float:
    """Proposition 5 (endurance): maximum relative endurance difference between any two strategies."""
    return ((p_compute - p_idle) + (p_tx - p_rx)) / (p_hover + p_avionics + p_idle + p_rx)


def best_option(options: Dict[str, Option], s: System, bw_mbps: float, acc_ref: float) -> Optional[str]:
    scores = {n: utility(o, s, bw_mbps, acc_ref) for n, o in options.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else None


def regime_map(options: Dict[str, Option], s_of_t, t_values: np.ndarray, bw_values: np.ndarray,
               acc_ref: float) -> np.ndarray:
    """Name of the best option on a grid of onboard speed x goodput (rows: t, cols: B)."""
    grid = np.empty((len(t_values), len(bw_values)), dtype=object)
    for i, t in enumerate(t_values):
        s = s_of_t(t)
        for j, b in enumerate(bw_values):
            grid[i, j] = best_option(options, s, b, acc_ref)
    return grid
