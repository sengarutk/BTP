"""Synthetic uplink channel traces for trace-driven evaluation (10 ms resolution).

These are *synthetic* traces, not measurements. Each trace is generated as:

1. Large-scale SINR: mean + log-normal shadowing, an AR(1) process in dB whose correlation
   decays with distance travelled (Gudmundson model, decorrelation distance d_corr).
2. Small-scale fading: Rician block fading with a Clarke/Jakes Doppler spectrum for a UAV at
   speed v and carrier f_c, simulated at 1 kHz (above the maximum Doppler of ~300 Hz) and
   averaged over each 10 ms slot, i.e. the SINR a scheduler would see per slot.
3. Throughput: the attenuated and truncated Shannon bound of 3GPP TR 36.942 (Annex A.2):
   SE = 0 if SINR < SINR_min, alpha*log2(1+SINR) otherwise, capped at SE_max,
   times the scheduled uplink bandwidth W.
4. Blackouts (profile "blackout"): deep additive fades of `depth_db`. The canonical trace uses fixed
   intervals; every other seed (e.g. each UAV in a swarm) places them at independent random times.

Columns: timestamp_ms, sinr_db, bandwidth_mbps, delay_ms, packet_loss_pct.
Real measured traces in the same CSV format can be dropped into traces/ and used directly.
"""

import csv
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from utils.logger import get_logger

logger = get_logger("TraceGenerator")

REPO_ROOT = Path(__file__).resolve().parent.parent
TRACES_DIR = REPO_ROOT / "traces"
SLOT_MS = 10.0

# 3GPP TR 36.942 Annex A.2 attenuated/truncated Shannon parameters (uplink)
SHANNON_ALPHA = 0.4
SINR_MIN_DB = -10.0
SE_MAX = 2.0


@dataclass
class ChannelProfile:
    name: str
    description: str
    mean_sinr_db: float
    shadow_sigma_db: float
    d_corr_m: float
    speed_mps: float
    bandwidth_mhz: float
    rician_k_db: float
    base_delay_ms: float
    blackouts_s: List[Tuple[float, float]] = field(default_factory=list)
    blackout_depth_db: float = 40.0
    seed: int = 0


PROFILES: Dict[str, ChannelProfile] = {
    "good": ChannelProfile("good", "Strong line-of-sight link", 13.0, 3.0, 50.0, 10.0, 40.0, 9.0, 10.0, seed=1),
    "moderate": ChannelProfile("moderate", "Urban link with moderate shadowing", 8.0, 4.0, 30.0, 12.0, 20.0, 3.0, 20.0, seed=2),
    "blackout": ChannelProfile("blackout", "Moderate link with two 3 s deep fades", 12.0, 3.0, 30.0, 12.0, 20.0, 3.0, 15.0,
                               blackouts_s=[(30.0, 33.0), (75.0, 78.0)], seed=3),
    "vehicular_fading": ChannelProfile("vehicular_fading", "Fast UAV (20-25 m/s) with weak LoS", 6.0, 6.0, 20.0, 22.5, 20.0, 0.0, 20.0, seed=4),
}


def attenuated_shannon_se(sinr_db: np.ndarray) -> np.ndarray:
    """Spectral efficiency (bit/s/Hz) from SINR via TR 36.942 attenuated/truncated Shannon."""
    se = SHANNON_ALPHA * np.log2(1.0 + 10.0 ** (sinr_db / 10.0))
    se = np.minimum(se, SE_MAX)
    return np.where(sinr_db < SINR_MIN_DB, 0.0, se)


def _shadowing_db(n: int, sigma: float, step_m: float, d_corr: float, rng: np.random.Generator) -> np.ndarray:
    rho = math.exp(-step_m / d_corr)
    s = np.empty(n)
    s[0] = rng.normal(0.0, sigma)
    innov = rng.normal(0.0, sigma * math.sqrt(1.0 - rho * rho), n)
    for i in range(1, n):
        s[i] = rho * s[i - 1] + innov[i]
    return s


def rician_process(n_samples: int, k_db: float, speed: float, fc_hz: float, rng: np.random.Generator,
                   sample_hz: float = 1000.0, n_rays: int = 32) -> np.ndarray:
    """Complex Rician channel gain (unit mean power) sampled at sample_hz.

    A line-of-sight ray plus a Clarke/Jakes sum of n_rays scattered rays with uniformly random
    arrival angles and phases; the maximum Doppler shift is speed * fc / c. For K -> 0 the envelope
    is Rayleigh; the scattered part has autocorrelation J0(2 pi fd tau) in the ensemble.
    """
    t = np.arange(n_samples) / sample_hz
    fd = speed * fc_hz / 3.0e8
    theta = rng.uniform(0, 2 * np.pi, n_rays)
    phi = rng.uniform(0, 2 * np.pi, n_rays)
    scat = np.zeros(t.size, dtype=np.complex128)
    for m in range(n_rays):
        scat += np.exp(1j * (2 * np.pi * fd * np.cos(theta[m]) * t + phi[m]))
    scat /= math.sqrt(n_rays)
    k = 10 ** (k_db / 10.0)
    los = np.exp(1j * (2 * np.pi * fd * np.cos(rng.uniform(0, 2 * np.pi)) * t + rng.uniform(0, 2 * np.pi)))
    return math.sqrt(k / (k + 1)) * los + math.sqrt(1 / (k + 1)) * scat


def _rician_slot_gain_db(n_slots: int, k_db: float, speed: float, fc_hz: float, rng: np.random.Generator,
                         sub_hz: float = 1000.0, n_rays: int = 32) -> np.ndarray:
    """Mean Rician power gain per 10 ms slot, from a 1 kHz sum-of-sinusoids simulation."""
    sub = int(round(SLOT_MS * sub_hz / 1000.0))
    h = rician_process(n_slots * sub, k_db, speed, fc_hz, rng, sub_hz, n_rays)
    power = np.abs(h) ** 2
    return 10 * np.log10(power.reshape(n_slots, sub).mean(axis=1))


def shadowing_db(n: int, sigma: float, step_m: float, d_corr: float, rng: np.random.Generator) -> np.ndarray:
    """Public alias of the Gudmundson AR(1) shadowing process (for the statistical tests)."""
    return _shadowing_db(n, sigma, step_m, d_corr, rng)


VALIDATION_DIR = REPO_ROOT / "experiments" / "results" / "validation"
_NS3_LTE_TABLE: Optional[Tuple[np.ndarray, np.ndarray]] = None


def ns3_lte_se(sinr_db: np.ndarray) -> np.ndarray:
    """Spectral efficiency (bit/s/Hz) from ns-3's LTE uplink model, measured by validation V2.

    Linear interpolation of goodput / 20 MHz against the eNB-reported SINR
    (experiments/results/validation/lte_compare.csv); zero below the lowest SINR that carried data,
    and the highest measured value above the measured range. Used only for sensitivity analysis.
    """
    global _NS3_LTE_TABLE
    if _NS3_LTE_TABLE is None:
        path = VALIDATION_DIR / "lte_compare.csv"
        if not path.exists():
            raise FileNotFoundError(f"{path} missing; run python -m validation.run_link_validation --which lte")
        with open(path, newline="", encoding="utf-8") as f:
            rows = sorted((float(r["sinr_db"]), float(r["ns3_mbps"]) / 20.0) for r in csv.DictReader(f))
        _NS3_LTE_TABLE = (np.array([r[0] for r in rows]), np.array([r[1] for r in rows]))
    x, y = _NS3_LTE_TABLE
    return np.interp(sinr_db, x, y, left=0.0, right=float(y[-1]))


RATE_MODELS = {"tr36942": attenuated_shannon_se, "ns3_lte": ns3_lte_se}


def generate_trace(profile: ChannelProfile, duration_s: float = 120.0, seed: Optional[int] = None,
                   fc_hz: float = 3.5e9, rate_model: str = "tr36942") -> List[Dict[str, float]]:
    rng = np.random.default_rng(profile.seed if seed is None else seed)
    n = int(duration_s * 1000.0 / SLOT_MS)
    step_m = profile.speed_mps * SLOT_MS / 1000.0
    sinr = (profile.mean_sinr_db
            + _shadowing_db(n, profile.shadow_sigma_db, step_m, profile.d_corr_m, rng)
            + _rician_slot_gain_db(n, profile.rician_k_db, profile.speed_mps, fc_hz, rng))
    t_s = np.arange(n) * SLOT_MS / 1000.0
    windows = list(profile.blackouts_s)
    if windows and seed is not None and seed != profile.seed:
        # Independent realisations (other seeds / other UAVs) place the same number of equally long
        # fades at random, non-overlapping times: blackouts depend on each UAV's location.
        lengths = [e - b for b, e in windows]
        slots = np.sort(rng.choice(np.arange(int(duration_s // 10) - 1), size=len(lengths), replace=False))
        windows = [(10.0 * k + 5.0, 10.0 * k + 5.0 + L) for k, L in zip(slots, lengths)]
    for start, end in windows:
        ramp = 0.2  # seconds of fade-in / fade-out
        depth = np.clip(np.minimum((t_s - (start - ramp)) / ramp, ((end + ramp) - t_s) / ramp), 0.0, 1.0)
        sinr = sinr - profile.blackout_depth_db * depth
    bw = RATE_MODELS[rate_model](sinr) * profile.bandwidth_mhz
    # One-way delay: base latency plus scheduling/HARQ jitter that grows as the link degrades.
    se_frac = np.minimum(bw / (SE_MAX * profile.bandwidth_mhz), 1.0)  # a no-op for tr36942 (SE <= SE_MAX)
    delay = profile.base_delay_ms + 10.0 * (1.0 - se_frac) + rng.exponential(2.0, n)
    # Residual loss after HARQ, applied per IP packet by the link model.
    loss = np.where(bw <= 0.0, 100.0, np.clip(0.1 * np.exp(-(sinr - SINR_MIN_DB) / 3.0), 0.0, 5.0))
    return [{"timestamp_ms": round(i * SLOT_MS, 1), "sinr_db": round(float(sinr[i]), 2),
             "bandwidth_mbps": round(float(bw[i]), 3), "delay_ms": round(float(delay[i]), 2),
             "packet_loss_pct": round(float(loss[i]), 4)} for i in range(n)]


def export_trace_csv(path: Path, records: List[Dict[str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        w.writeheader()
        w.writerows(records)


def trace_path(name: str) -> Path:
    return TRACES_DIR / f"trace_5g_{name}.csv"


def generate_all_traces(duration_s: float = 120.0) -> Dict[str, Path]:
    out = {}
    for name, prof in PROFILES.items():
        recs = generate_trace(prof, duration_s)
        export_trace_csv(trace_path(name), recs)
        bw = np.array([r["bandwidth_mbps"] for r in recs])
        logger.info(f"{name:>17}: mean {bw.mean():5.1f} Mbps, p5 {np.percentile(bw, 5):5.1f}, "
                    f"p95 {np.percentile(bw, 95):5.1f}, outage {100 * np.mean(bw <= 0):4.1f}%")
        out[name] = trace_path(name)
    return out


if __name__ == "__main__":
    generate_all_traces()
