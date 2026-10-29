#!/usr/bin/env python3
"""Measured energy, thermal and endurance model for the drone-carried boards (profiles from energy_profile.py).

Camera drone (Pi 5, or the Jetson when it is a camera), per run:
  E_camera = P_idle * T                                   board floor (measured idle, whole PMIC / VDD_IN)
           + sum over onboard inferences  dE_infer(variant)       = (P_infer - P_idle) * t_infer
           + sum over offloaded frames    dE_enc(res, q)           = (P_encode@30fps - P_idle) / 30
                                        + dP_radio(r) * 8 b / r    radio power above idle at link rate r
                                                                   (linear fit over the paced 2/5/10 Mbit/s
                                                                   and the saturated measurements)
           + dP_forecast * T              when the motion forecaster runs (camera motion every frame)
Edge drone (the Jetson as an airborne edge server), per run:
  E_edge = P_idle(clocks locked) * T + sum over frames it served dE_infer(model, res) + dP_rx(r) * 8 b / r
Ground station (laptop): not drone energy, not counted.
System views (system_views): the same run priced three ways — edge drone flying anyway (count its extra
work only), carried for perception (its whole board incl. idle), or dedicated to perception (board +
flight power). Swarm lifetime (swarm_lifetime_min) = the first drone to land.
Endurance of a drone class = 60 * usable battery Wh / (flight power + perception power)  [min].
Drone classes: 249 g mini (DJI Mini 2 published: 2250 mAh x 7.7 V = 17.3 Wh, 31 min -> 33.5 W, all-in);
1.2 kg quadcopter (hover power from simulation.system_model.hover_power_w; 4S 5000 mAh, 80 % usable);
1.5 kg drone carrying the Jetson (same hover model; 6S 5000 mAh, 80 % usable).
Thermal model: first-order, steady T_ss = T_idle + R (P_avg - P_idle), time constant tau (see _fit_thermal); a
strategy whose sustained average power puts T_ss above the throttle limit (Pi 85 C) would throttle in flight.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
E_DIR = ROOT / "experiments" / "results" / "hardware" / "energy"
sys.path.insert(0, str(ROOT))


def _st(p, k):
    return p["states"][k]


class Board:
    def __init__(self, kind):
        p = json.load(open(E_DIR / f"energy_profile_{kind}.json"))
        self.kind, self.p = kind, p
        idle = _st(p, "idle" if kind == "pi" else "idle_clocks_locked")["power_w"]
        self.idle = idle
        self.infer, self.ms = {}, {}
        for k, v in p["states"].items():
            if k.startswith(("onboard_", "infer_")) and v.get("ms_per_frame"):
                name = k.split("_")[1]                 # n320, s320, s640, s480, m640
                self.ms[name] = v["ms_per_frame"]
                self.infer[name] = max(0.0, v["power_w"] - idle) * v["ms_per_frame"] / 1e3
        self.enc = {}
        for k, v in p["states"].items():
            if k.startswith("encode_"):
                self.enc[k.split("_")[1]] = max(0.0, v["power_w"] - idle) / 30.0
        tx = [(v["mbit_s"], v["power_w"] - idle) for k, v in p["states"].items() if k.startswith("radio_tx_")]
        if tx:
            x, y = np.array(tx).T
            self.tx_b, self.tx_a = np.polyfit(x, y, 1) if len(x) > 1 else (0.0, float(y[0]))
        else:
            self.tx_a, self.tx_b = 0.3, 0.0
        rx = p["states"].get("radio_rx_max")
        self.rx_w = max(0.0, rx["power_w"] - idle) if rx else 0.3
        self.rx_rate = rx["mbit_s"] if rx else 20.0
        fc = p["states"].get("forecaster_30fps")
        self.forecast_w = max(0.0, fc["power_w"] - idle) if fc else 0.0
        self.thermal = self._fit_thermal()
        self.steady = None
        st = E_DIR / f"thermal_steady_{kind}.json"
        if st.exists():                    # long steady-state levels (thermal_steady.py) take precedence
            lv = json.load(open(st))["levels"]
            if "forecaster_30fps" in lv and "idle" in lv:
                # 6-min steady levels; the 20-s profile state followed a hot inference state (leakage) and is
                # biased high
                self.forecast_w = max(0.0, lv["forecaster_30fps"]["power_w"] - lv["idle"]["power_w"])
            # below the firmware's soft throttle limit (80 C) only; until 28 Oct 2026 this was < 84 C, which let
            # in the 50 %-duty level (83.8 C, clock already reduced to 2,070 MHz) and steepened the fit
            pts = [(v["power_w"], v["temp_steady_c"]) for k, v in lv.items()
                   if v.get("arm_clock_mhz_last60", 0) >= 1450 and v["temp_steady_c"] < 80.0]
            if len(pts) >= 3:
                x, y = np.array(pts).T
                slope, icpt = np.polyfit(x, y, 1)
                self.steady = {"c_per_w": float(slope), "intercept_c": float(icpt), "points": pts,
                               "p_at_85c_w": float((85.0 - icpt) / slope) if slope > 0 else None,
                               "method": "linear fit of 6-min steady temperatures against mean power, "
                                         "levels below the throttle limit"}

    def enc_j(self, res, q):
        key = f"{res}q{q}"
        if key in self.enc:
            return self.enc[key]
        if q == 90:
            return self.enc.get("640q90", 0.0)
        return float(np.mean([self.enc.get("640q50", 0.0), self.enc.get("320q50", 0.0)]))

    def tx_j(self, nbytes, rate_mbps):
        r = max(rate_mbps, 0.2)
        return max(0.0, self.tx_a + self.tx_b * r) * nbytes * 8 / (r * 1e6)

    def rx_j(self, nbytes, rate_mbps):
        r = max(rate_mbps, 0.2)
        return self.rx_w * nbytes * 8 / (r * 1e6)

    def _fit_thermal(self):
        """First-order thermal model T_ss(P) = T_idle + R (P - P_idle), time constant tau.
        tau: exponential fit of the cool-down (idle) towards the idle temperature; R: from the initial heating
        rate under sustained inference, dT/dt = (T_ss - T) / tau, with that inference state's power measured by
        the 10 Hz sampler (the 1 Hz log's power column is sampled between inferences and is not used)."""
        th = self.p.get("thermal")
        if not th:
            return None
        log = np.array(th["log_t_power_temp_clock_frames"], float)
        heat = th["heat_s"]
        idle_st = self.p["states"]["idle" if self.kind == "pi" else "idle_clocks_locked"]
        t_idle, p_idle = idle_st["temp_c"], idle_st["power_w"]
        cool = log[log[:, 0] >= heat]
        y = cool[:, 2] - t_idle
        ok = y > 0.5
        tau = float(-1.0 / np.polyfit(cool[ok, 0] - cool[0, 0], np.log(y[ok]), 1)[0]) if ok.sum() > 5 else 120.0
        h = log[log[:, 0] < heat]
        k = max(2, int(np.searchsorted(h[:, 2], h[0, 2] + 8.0)))  # first ~8 C of heating (before throttling)
        k = min(k, len(h) - 1)
        rate = (h[k, 2] - h[0, 2]) / max(h[k, 0] - h[0, 0], 1e-6)
        st = "onboard_s640" if self.kind == "pi" else "infer_m640_fp16"
        p_heat = self.p["states"][st]["power_w"] if st in self.p["states"] else p_idle
        t_mid = (h[0, 2] + h[k, 2]) / 2
        t_ss = t_mid + rate * tau
        r_th = (t_ss - t_idle) / max(p_heat - p_idle, 1e-6)
        return {"tau_s": tau, "t_idle_c": t_idle, "p_idle_w": p_idle, "r_c_per_w": float(r_th),
                "heat_rate_c_per_s": float(rate), "heat_power_w": p_heat, "peak_c": float(log[:, 2].max()),
                "throttle_c": 85.0 if self.kind == "pi" else 97.0,
                "p_at_throttle_w": float(p_idle + ((85.0 if self.kind == "pi" else 97.0) - t_idle) / max(r_th, 1e-6)),
                "method": "two-point: idle anchor, heating rate at measured inference power, cool-down tau"}

    def steady_temp(self, p_avg):
        if self.steady:                    # measured steady-state curve; above ~85 C the Pi throttles instead
            return self.steady["intercept_c"] + self.steady["c_per_w"] * p_avg
        th = self.thermal
        return th["t_idle_c"] + th["r_c_per_w"] * (p_avg - th["p_idle_w"]) if th else float("nan")


def drone_classes():
    from simulation.system_model import hover_power_w
    return {"mini_249g": {"flight_w": 33.5, "battery_wh": 17.3},
            "quad_1.2kg": {"flight_w": hover_power_w(1.2), "battery_wh": 74.0 * 0.8},
            "edge_1.5kg": {"flight_w": hover_power_w(1.5), "battery_wh": 111.0 * 0.8}}


def endurance_min(cls, perception_w):
    c = drone_classes()[cls]
    return 60.0 * c["battery_wh"] / (c["flight_w"] + perception_w)


ONB = {"n320": "n320", "s320": "s320", "s640": "s640"}


def _rates(run):
    """Median measured goodput per path over the run (Mbit/s)."""
    out = {}
    for p, s in (run.get("link_goodput_samples") or {}).items():
        v = [x[1] for x in s if x[1] and x[1] > 0]
        out[p] = float(np.median(v)) if v else 10.0
    return out


def run_energy(run, pi, jet, camera="pi", forecast=False):
    """Energy of one adaptive2-format run. camera: 'pi' or 'jetson' (the Jetson as a camera drone)."""
    cam = pi if camera == "pi" else jet
    fr = run["frames"]
    dur = (fr[-1]["id"] + 1) / 30.0 if fr else 0.0
    rates = _rates(run)
    br = {"idle": cam.idle * dur, "onboard": 0.0, "encode": 0.0, "radio": 0.0,
          "forecast": cam.forecast_w * dur if forecast else 0.0}
    if forecast and camera == "jetson" and cam.forecast_w == 0.0:
        br["forecast"] = pi.forecast_w * dur * 0.25        # not measured on the Jetson: a quarter of the Pi's
    edge = {"idle": jet.idle * dur, "infer": 0.0, "radio": 0.0}
    n_on = n_off = n_edge = 0
    for f in fr:
        srv = f.get("server")
        if not srv:
            continue
        v = f["variant"]
        if srv == "onboard":
            br["onboard"] += cam.infer.get(ONB.get(v, v), 0.0)
            n_on += 1
            continue
        res = f.get("res") or int(v[1:].split("q")[0])
        q = int(v.split("q")[1])
        b = f.get("bytes") or 0
        br["encode"] += cam.enc_j(res, q)
        br["radio"] += cam.tx_j(b, rates.get(srv, 10.0))
        n_off += 1
        if srv == "jetson" and camera == "pi":
            key = f"{v[0]}{res}"
            edge["infer"] += jet.infer.get(key, jet.infer.get("s640", 0.0))
            edge["radio"] += jet.rx_j(b, rates.get("jetson", 10.0))
            n_edge += 1
    e_cam = sum(br.values())
    e_edge = sum(edge.values())
    return {"duration_s": dur, "camera_j": e_cam, "camera_w": e_cam / dur if dur else 0.0,
            "camera_breakdown_j": br, "edge_j": e_edge, "edge_w": e_edge / dur if dur else 0.0,
            "edge_used": n_edge > 0, "edge_breakdown_j": edge, "frames_onboard": n_on, "frames_offloaded": n_off,
            "frames_edge": n_edge}


V1_ACT = {"lap_j90": ("laptop", 640, 90), "lap_j50": ("laptop", 640, 50), "jet_j90": ("jetson", 640, 90),
          "jet_j50": ("jetson", 640, 50)}


def run_energy_v1(run, pi, jet):
    """Energy of a controller-v1 run (adaptive.py format: one action per frame)."""
    fr = run["frames"]
    dur = (fr[-1]["id"] + 1) / 30.0 if fr else 0.0
    rates = {p: float(np.median([x[1] for x in s if x[1] > 0])) if s else 10.0
             for p, s in (run.get("rate_samples") or {}).items()} if isinstance(run.get("rate_samples"), dict) else {}
    br = {"idle": pi.idle * dur, "onboard": 0.0, "encode": 0.0, "radio": 0.0, "split_compute": 0.0}
    edge = {"idle": jet.idle * dur, "infer": 0.0, "radio": 0.0}
    k1_ms = 95.0                                         # Pi layers 0-1 (docs/hardware_results.md)
    s640_w = pi.infer["s640"] / (pi.ms["s640"] / 1e3)   # Pi dynamic power while inferring
    for f in fr:
        a = f.get("action")
        if a == "onboard":
            if f.get("lat_ms") is not None:
                br["onboard"] += pi.infer["s640"]
            continue
        b = f.get("bytes")
        if not b:
            continue
        path = "laptop" if a.startswith("lap") else "jetson"
        r = rates.get(path, 10.0)
        if a.endswith("k1"):
            br["split_compute"] += s640_w * k1_ms / 1e3
        else:
            br["encode"] += pi.enc_j(640, V1_ACT[a][2])
        br["radio"] += pi.tx_j(b, r)
        if path == "jetson":
            edge["infer"] += jet.infer.get("s640", 0.0)
            edge["radio"] += jet.rx_j(b, r)
    e = sum(br.values())
    return {"duration_s": dur, "camera_j": e, "camera_w": e / dur if dur else 0.0, "camera_breakdown_j": br,
            "edge_j": sum(edge.values()), "edge_w": sum(edge.values()) / dur if dur else 0.0,
            "edge_breakdown_j": edge, "edge_used": edge["infer"] > 0}


def system_views(re, jet, edge_class="edge_1.5kg"):
    """Three explicitly-labelled system-level views of one run's energy (never mixed):
      extra     — the edge drone flies anyway (its idle and flight belong to the flight mission):
                  system = camera drone + the Jetson's extra work only (infer + rx);
      board     — the Jetson is carried for perception: add its whole board power incl. the idle floor;
      dedicated — the edge drone flies only for perception: add board + its flight power.
    A run that never used the edge drone (fixed laptop / onboard: edge_used False) needs no edge drone, so
    every view is the camera drone alone — charging such a run the Jetson's idle and flight would price a
    drone its system does not have (and contradict its edge_w = 0 in the rescored rows).
    re: a run_energy()/run_energy_v1() result dict. Returns joules and mean watts for each view."""
    dur = re["duration_s"]
    eb = re.get("edge_breakdown_j") or {"idle": jet.idle * dur, "infer": 0.0, "radio": 0.0}
    used = re.get("edge_used", True)
    ex = eb["infer"] + eb["radio"] if used else 0.0    # the Jetson's extra work above idle
    board_j = eb["idle"] + ex if used else 0.0
    flight_j = drone_classes()[edge_class]["flight_w"] * dur if used else 0.0
    cam_j = re["camera_j"]
    out = {}
    for name, j in (("extra", cam_j + ex), ("board", cam_j + board_j),
                    ("dedicated", cam_j + board_j + flight_j)):
        out[f"system_j_{name}"] = j
        out[f"system_w_{name}"] = j / dur if dur else 0.0
    return out


def swarm_lifetime_min(power_by_drone):
    """Per-drone endurance and swarm lifetime (the first drone to land).
    power_by_drone: {drone_name: (drone_class, mean perception power W)} from measured run data."""
    per = {d: endurance_min(c, p) for d, (c, p) in power_by_drone.items()}
    return {"per_drone_min": per, "swarm_lifetime_min": min(per.values()) if per else None}


def summary_constants(pi, jet):
    return {"pi": {"idle_w": pi.idle, "infer_j": pi.infer, "infer_ms": pi.ms, "encode_j": pi.enc,
                   "radio_tx_w": {"a": pi.tx_a, "b_per_mbps": pi.tx_b}, "forecast_w": pi.forecast_w,
                   "thermal": pi.thermal, "thermal_steady": pi.steady},
            "jetson": {"idle_w": jet.idle, "infer_j": jet.infer, "infer_ms": jet.ms,
                       "radio_rx_w": jet.rx_w, "radio_tx_w": {"a": jet.tx_a, "b_per_mbps": jet.tx_b},
                       "thermal": jet.thermal},
            "drone_classes": drone_classes()}


if __name__ == "__main__":
    pi, jet = Board("pi"), Board("jetson")
    c = summary_constants(pi, jet)
    json.dump(c, open(E_DIR / "energy_constants.json", "w"), indent=1, default=float)
    print(json.dumps(c, indent=1, default=lambda x: round(x, 4) if isinstance(x, float) else x))
