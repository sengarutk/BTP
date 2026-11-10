#!/usr/bin/env python3
"""How much does the camera Pi's clock speed matter on the mesh? (10 Nov 2026, laptop only, from recorded runs)

Every mesh run (campaigns 1-3) logs the Pi's ARM clock and throttle flags about once a second
(measured_energy.clock_log_t_mhz_flags), its power and temperature about four times a second (log_t_w_c), and every
frame's latency and server. Each sample and frame is put in one of three clock classes, by the nearest clock sample:
  full       2,400 MHz (the Pi 5's full clock)
  governor   below full and not currently throttled: the frequency governor slowing an idle CPU
  throttled  a current throttle or soft-temperature-limit flag set (bits 0-3 of the flags)
Note: a frame's class is a correlation, not a cause: the CPU idles (low clock) exactly when there is less to do, which
is also when links are slow, so latency differences between classes are an upper bound on the clock's own effect.

Also read: the Pi 5 benchmark at full clock and when throttled (raw/pi5_cpu_4t.json, raw/pi5_cpu_4t_sustained.json),
v4.1's on-time shares (vid_campaign_mesh2_summary.json), and the measured staleness decay with the forecaster
(staleness_decay_forecast_v2.json) for an estimate of what a fixed full clock could add to accuracy.
usage: clock_effect_analysis.py [--out DIR]   -> DIR/clock_effect.json (default experiments/results/hardware/clock_effect/)
"""
import argparse
import bisect
import collections
import glob
import json
import statistics as st
from pathlib import Path

H = Path(__file__).resolve().parents[2] / "experiments" / "results" / "hardware"
CAMPAIGNS = ("vid_campaign_mesh", "vid_campaign_mesh2", "vid_campaign_mesh3")
FULL_MHZ = 2400


def cls(mhz, flags):
    if flags & 0xF:
        return "throttled"
    return "full" if mhz >= FULL_MHZ else "governor"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(H / "clock_effect"))
    a = ap.parse_args()
    share = collections.defaultdict(collections.Counter)
    lat = collections.defaultdict(list)
    pw = collections.defaultdict(list)
    tc = collections.defaultdict(list)
    served = collections.Counter()
    runs = 0
    for c in CAMPAIGNS:
        for f in sorted(glob.glob(str(H / c / "a2_*__r?.json"))):
            d = json.load(open(f))
            cl = (d.get("measured_energy") or {}).get("clock_log_t_mhz_flags")
            if not cl:
                continue
            runs += 1
            name = Path(f).name
            sc, pol = name.split("__")[0][3:], name.split("__")[1]
            ts = [x[0] for x in cl]

            def at(t):
                i = min(bisect.bisect_left(ts, t), len(ts) - 1)
                return cls(cl[i][1], cl[i][2])
            for _, mhz, fl in cl:
                share[pol][cls(mhz, fl)] += 1
            for t, w, temp in d["measured_energy"].get("log_t_w_c") or []:
                k = at(t)
                pw[(pol, k)].append(w)
                tc[k].append(temp)
            for r in d["frames"]:
                if r.get("lat_ms") and r.get("server"):
                    lat[(sc, r["server"], at(r["id"] / 30.0))].append(r["lat_ms"])
                    if pol == "v41":
                        served[r["server"]] += 1
    out = {"runs": runs, "campaigns": CAMPAIGNS, "full_mhz": FULL_MHZ,
           "clock_share_by_strategy": {p: {k: v / sum(c.values()) for k, v in c.items()} | {"n": sum(c.values())}
                                       for p, c in share.items()},
           "latency_ms_by_scenario_server_class": {"|".join(k): {"median": st.median(v), "n": len(v)}
                                                   for k, v in lat.items() if len(v) >= 200},
           "power_w_by_strategy_class": {"|".join(k): {"mean": st.mean(v), "n": len(v)} for k, v in pw.items() if len(v) >= 50},
           "temp_c_by_class": {k: {"mean": st.mean(v), "n": len(v)} for k, v in tc.items()},
           "v41_served_share": {k: v / sum(served.values()) for k, v in served.items()}}
    bench = {}
    for lab, f in (("full_clock", "pi5_cpu_4t.json"), ("throttled", "pi5_cpu_4t_sustained.json")):
        b = json.load(open(H / "raw" / f))
        p = b["power"]
        bench[lab] = {"yolov8s_ms": b["full_ms"], "jpeg_q90_enc_ms": b["jpeg"]["enc_ms"], "temperature_c": b["temperature_c"],
                      "idle_w": p["idle_w"], "active_w": p["active_w"],
                      "energy_per_frame_j": (p["active_w"] - p["idle_w"]) * b["full_ms"] / 1000,
                      "end_state": b.get("pi_state_end"), "source": f"raw/{f}"}
    out["bench"] = bench
    m2 = json.load(open(H / "vid_campaign_mesh2_summary.json"))["cells"]
    out["v41_on_time_share"] = {sc: m2[f"{sc}|v41"]["p_aoi300"][0] for sc in ("static_good", "mesh_mission", "multihop")}
    out["v41_sAP_fc"] = {sc: m2[f"{sc}|v41"]["sAP_fc"][0] for sc in ("static_good", "mesh_mission", "multihop", "ALL")}
    dec = json.load(open(H / "staleness_decay_forecast_v2.json"))
    loss_per_ms = (1 - dec["ratio"][1]) / dec["lag_ms"][1]
    L = out["latency_ms_by_scenario_server_class"]
    saving = L["static_good|laptop|governor"]["median"] - L["static_good|laptop|full"]["median"]
    rel = loss_per_ms * saving * out["v41_served_share"].get("laptop", 0.0)
    out["accuracy_estimate"] = {
        "laptop_latency_gap_ms": saving, "decay_loss_per_ms": loss_per_ms, "v41_laptop_share": out["v41_served_share"].get("laptop"),
        "relative_sap_gain_upper": rel, "absolute_sap_gain_upper": rel * out["v41_sAP_fc"]["ALL"],
        "note": "upper bound: assumes the whole governor-vs-full latency gap on laptop-served frames is caused by the clock "
                "and that every laptop-served frame is affected; the bench shows JPEG encoding itself unchanged"}
    Path(a.out).mkdir(parents=True, exist_ok=True)
    json.dump(out, open(Path(a.out) / "clock_effect.json", "w"), indent=1)
    print(json.dumps({"runs": runs, "accuracy_estimate": out["accuracy_estimate"], "bench": bench}, indent=1))


if __name__ == "__main__":
    main()
