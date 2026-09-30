"""Single source of truth for the end-to-end system model used by every simulation.

* ``OffloadConfig``   one way of processing a frame: fully onboard, split at cut k with a
                      given wire precision, or encode-and-offload the image with a codec.
                      All sizes, host timings and accuracies are loaded from measured CSVs.
* ``EdgeHardware``    the onboard computer. Its speed is ONE parameter, t_full_ms (onboard
                      latency of the whole YOLOv8s). Onboard DNN time for cut k is
                      t_full_ms * FLOP fraction(k); other onboard work (quantization,
                      serialization, image encoding) is the host-measured time scaled by
                      t_full_ms / host_full_ms. Results are reported across several t_full_ms.
* ``EnergyModel``     incremental energy per frame and average perception power.
* ``AdaptivePolicy``  chooses a configuration per frame to maximise expected on-time,
                      accuracy-weighted throughput under the current goodput estimate.
"""

import csv
import json
import math
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS = REPO_ROOT / "experiments" / "results"
CAMERA_FPS = 30.0
DEADLINE_MS = 300.0


@dataclass(frozen=True)
class OffloadConfig:
    name: str
    kind: str                    # "onboard" | "split" | "codec"
    cut: int                     # 22 for onboard, -1 for codec
    dtype: str                   # wire precision / codec setting
    payload_bytes: float         # mean bytes on the wire per frame (0 for onboard)
    edge_flop_frac: float        # fraction of YOLOv8s FLOPs executed onboard
    host_edge_proc_ms: float     # non-DNN onboard work measured on the host (quant+serialize / encode)
    cloud_ms: float              # server-side time (deserialize+dequant+cloud DNN+NMS / decode+DNN+NMS)
    map50_95: float
    map50: float
    delta_map50_95: float        # vs. FP32 onboard baseline (negative = worse)


@dataclass(frozen=True)
class EdgeHardware:
    name: str
    t_full_ms: float                       # onboard latency of the full model
    host_full_ms: float                    # the same, measured on the host GPU
    p_idle_w: float = 2.0                  # compute module idle
    p_compute_w: float = 10.0              # compute module while busy (Jetson Nano 10 W mode ceiling)
    p_tx_w: float = 3.8                    # cellular modem while transmitting (assumption)
    p_rx_idle_w: float = 1.2               # cellular modem connected but idle (assumption)
    p_a2a_tx_w: float = 1.5                # Wi-Fi radio while relaying (assumption)

    @property
    def scale(self) -> float:
        return self.t_full_ms / self.host_full_ms

    def onboard_ms(self, cfg: OffloadConfig) -> float:
        if cfg.kind == "onboard":
            return self.t_full_ms
        return self.t_full_ms * cfg.edge_flop_frac + cfg.host_edge_proc_ms * self.scale


HARDWARE_SCENARIOS_MS = [40.0, 90.0, 180.0, 360.0]


def hover_power_w(mass_kg: float = 1.2, disk_area_m2: float = 0.2, rho: float = 1.225,
                  figure_of_merit: float = 0.7, motor_esc_eff: float = 0.75) -> float:
    """Electrical hover power from momentum theory: T*v_i / (FoM * eta), v_i = sqrt(T / (2 rho A)).

    The figure of merit already accounts for rotor profile losses, so no separate profile term is added.
    """
    thrust = mass_kg * 9.81
    v_i = math.sqrt(thrust / (2.0 * rho * disk_area_m2))
    return thrust * v_i / (figure_of_merit * motor_esc_eff)


@dataclass(frozen=True)
class PlatformModel:
    battery_wh: float = 55.5                        # 3S 5000 mAh LiPo
    avionics_w: float = 15.0
    hover_w: float = field(default_factory=hover_power_w)

    def endurance_min(self, perception_w: float) -> float:
        return 60.0 * self.battery_wh / (self.hover_w + self.avionics_w + perception_w)


def _read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"{path} missing; run the benchmark that produces it first")
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_offload_configs(results_dir: Path = RESULTS) -> Dict[str, OffloadConfig]:
    """Builds every candidate configuration from split_pareto_analysis.csv and codec_offload.csv."""
    configs: Dict[str, OffloadConfig] = {}
    for r in _read_csv(results_dir / "split_pareto_analysis.csv"):
        onboard = r["kind"] == "onboard"
        configs[r["config"]] = OffloadConfig(
            name=r["config"], kind=r["kind"], cut=int(r["cut"]), dtype=r["dtype"],
            payload_bytes=float(r["payload_bytes_mean"]),
            edge_flop_frac=float(r["edge_flop_pct"]) / 100.0,
            host_edge_proc_ms=0.0 if onboard else float(r["host_quant_ms"]) + float(r["host_serialize_ms"]),
            cloud_ms=0.0 if onboard else (float(r["host_deserialize_ms"]) + float(r["host_dequant_ms"])
                                          + float(r["host_cloud_ms"]) + float(r["host_nms_ms"])),
            map50_95=float(r["map50_95"]), map50=float(r["map50"]), delta_map50_95=float(r["delta_map50_95"]))
    codec_path = results_dir / "codec_offload.csv"
    if codec_path.exists():
        for r in _read_csv(codec_path):
            configs[r["config"]] = OffloadConfig(
                name=r["config"], kind="codec", cut=-1, dtype=r["setting"],
                payload_bytes=float(r["payload_bytes_mean"]), edge_flop_frac=0.0,
                host_edge_proc_ms=float(r["host_encode_ms"]), cloud_ms=float(r["host_cloud_ms"]),
                map50_95=float(r["map50_95"]), map50=float(r["map50"]), delta_map50_95=float(r["delta_map50_95"]))
    return configs


def host_full_ms(configs: Dict[str, OffloadConfig], results_dir: Path = RESULTS) -> float:
    for r in _read_csv(results_dir / "split_pareto_analysis.csv"):
        if r["kind"] == "onboard":
            return float(r["host_edge_ms"])
    raise KeyError("onboard row missing from split_pareto_analysis.csv")


def make_hardware(t_full_ms: float, results_dir: Path = RESULTS, **power) -> EdgeHardware:
    configs = load_offload_configs(results_dir)
    return EdgeHardware(name=f"t_full={t_full_ms:g}ms", t_full_ms=t_full_ms,
                        host_full_ms=host_full_ms(configs, results_dir), **power)


@dataclass
class EnergyTally:
    compute_j: float = 0.0
    tx_j: float = 0.0
    a2a_j: float = 0.0

    def add_compute(self, hw: EdgeHardware, ms: float) -> None:
        self.compute_j += (hw.p_compute_w - hw.p_idle_w) * ms / 1000.0

    def add_tx(self, hw: EdgeHardware, ms: float) -> None:
        self.tx_j += (hw.p_tx_w - hw.p_rx_idle_w) * ms / 1000.0

    def add_a2a(self, hw: EdgeHardware, ms: float) -> None:
        self.a2a_j += hw.p_a2a_tx_w * ms / 1000.0

    def average_power_w(self, hw: EdgeHardware, duration_s: float) -> float:
        """Idle floor of compute module and modem plus the incremental active energy."""
        return hw.p_idle_w + hw.p_rx_idle_w + (self.compute_j + self.tx_j + self.a2a_j) / duration_s


@dataclass
class PolicyWeights:
    energy_per_frame: float = 0.05   # score units per joule of incremental energy per processed frame
    min_rel_std: float = 0.1         # floor on the goodput uncertainty (fraction of the mean)


def _normal_sf(z: float) -> float:
    """P(Z > z) for a standard normal Z."""
    return 0.5 * math.erfc(z / math.sqrt(2.0))


class AdaptivePolicy:
    """Chooses, per frame, the configuration with the highest expected useful throughput.

    For each candidate c, with goodput modelled as B ~ N(mu, sigma^2) (causal EWMA estimates):
      * t_edge(c)  onboard time;  t_tx(c) = bits / B;  L = t_edge + t_tx + d + t_cloud
      * p_on(c)    = P(L <= T_d) = P(B >= B_req),  B_req = bits / (T_d - t_edge - d - t_cloud)
      * fps(c)     = camera rate / ceil(max(t_edge, t_tx at mu) / camera period)
      * score(c)   = fps * p_on * mAP(c)/mAP(FP32) - w_E * E_frame(c)
    i.e. the expected number of on-time detections per second, weighted by relative accuracy,
    with incremental energy per frame as a small tie-breaker. The score is smooth in mu and sigma.
    A switch requires the new score to exceed the current one by ``hysteresis`` (relative).
    """

    def __init__(self, configs: List[OffloadConfig], hw: EdgeHardware, weights: Optional[PolicyWeights] = None,
                 deadline_ms: float = DEADLINE_MS, hysteresis: float = 0.05, one_way_delay_ms: float = 20.0,
                 camera_fps: float = CAMERA_FPS):
        if not configs:
            raise ValueError("AdaptivePolicy needs at least one configuration")
        self.configs = configs
        self.hw = hw
        self.w = weights or PolicyWeights()
        self.deadline_ms = deadline_ms
        self.hysteresis = hysteresis
        self.delay_ms = one_way_delay_ms
        self.camera_fps = camera_fps
        self.current: Optional[OffloadConfig] = None
        self.switches = 0
        self.base_map = max((c.map50_95 - c.delta_map50_95) for c in configs)

    def predict(self, cfg: OffloadConfig, bw_mbps: float, bw_std_mbps: Optional[float] = None) -> Dict[str, float]:
        period = 1000.0 / self.camera_fps
        t_edge = self.hw.onboard_ms(cfg)
        sigma = max(bw_std_mbps or 0.0, self.w.min_rel_std * bw_mbps)
        if cfg.kind == "onboard":
            t_tx, lat = 0.0, t_edge
            p_on = 1.0 if lat <= self.deadline_ms else 0.0
        elif bw_mbps <= 1e-3:
            t_tx, lat, p_on = math.inf, math.inf, 0.0
        else:
            bits_kb = cfg.payload_bytes * 8.0 / 1e3  # kbit; kbit / Mbps = ms
            t_tx = bits_kb / bw_mbps
            lat = t_edge + t_tx + self.delay_ms + cfg.cloud_ms
            budget = self.deadline_ms - t_edge - self.delay_ms - cfg.cloud_ms
            p_on = 0.0 if budget <= 0 else _normal_sf((bits_kb / budget - bw_mbps) / sigma)
        bottleneck = max(t_edge, 0.0 if math.isinf(t_tx) else t_tx)
        fps = self.camera_fps / max(1, math.ceil(bottleneck / period - 1e-9)) if bottleneck > 0 else self.camera_fps
        e_frame = ((self.hw.p_compute_w - self.hw.p_idle_w) * t_edge
                   + (self.hw.p_tx_w - self.hw.p_rx_idle_w) * (0.0 if math.isinf(t_tx) else t_tx)) / 1000.0
        return {"latency_ms": lat, "fps": fps, "p_on_time": p_on, "t_edge_ms": t_edge, "t_tx_ms": t_tx,
                "energy_j": e_frame}

    def score(self, cfg: OffloadConfig, bw_mbps: float, bw_std_mbps: Optional[float] = None) -> float:
        p = self.predict(cfg, bw_mbps, bw_std_mbps)
        return p["fps"] * p["p_on_time"] * cfg.map50_95 / self.base_map - self.w.energy_per_frame * p["energy_j"]

    def decide(self, bw_mbps: float, bw_std_mbps: Optional[float] = None) -> OffloadConfig:
        scores = {c.name: self.score(c, bw_mbps, bw_std_mbps) for c in self.configs}
        best = max(self.configs, key=lambda c: scores[c.name])
        if self.current is not None and best.name != self.current.name and self.current.name in scores:
            cur = scores[self.current.name]
            if scores[best.name] <= cur + self.hysteresis * abs(cur):
                return self.current
        if self.current is None or best.name != self.current.name:
            self.switches += int(self.current is not None)
            self.current = best
        return best


def save_model_card(path: Path, hw: EdgeHardware, platform: PlatformModel) -> None:
    path.write_text(json.dumps({"hardware": hw.__dict__, "scale": hw.scale,
                                "platform": {**platform.__dict__}}, indent=2), encoding="utf-8")
