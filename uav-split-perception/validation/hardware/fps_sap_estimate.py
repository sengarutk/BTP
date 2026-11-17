#!/usr/bin/env python3
"""Streaming AP at other camera frame rates, estimated (17 Nov 2026; the T7 runs at 15 and 60 fps cannot be scored by
stream_ap.py, which assumes the dataset's 30-fps timeline: the camera plays one clip frame per tick, so at 60 fps the
video ran twice as fast, and rescoring at 1/60 s per frame would score a scene moving twice as fast).

Estimate: what the drone holds at each instant of real time. From a run's log (capture time = frame id x its own
period, arrival = t_res), the newest-captured result that has arrived is held; its value is acc(variant) x r(age),
with r the measured accuracy-vs-age curve after forecasting (staleness_decay_forecast_v2.json: VisDrone-VID train,
the dataset's own motion). The time average E of that value is proportional to sAP if the proxy is right, so:
  1. calibrate sAP_fc = k E on 30-fps runs of several campaigns, and check the proxy there (correlation, k's spread);
  2. apply it to the 15- and 60-fps runs: their estimated sAP is what a camera at that rate would score on scenes that
     move as VisDrone's do.
usage: python validation/hardware/fps_sap_estimate.py -> experiments/results/hardware/fps_sap_estimate.json
"""
import glob
import json
import re
from pathlib import Path

import numpy as np

H = Path(__file__).resolve().parents[2] / "experiments" / "results" / "hardware"
DEC = json.load(open(H / "staleness_decay_forecast_v2.json"))
LAG, RAT = np.array(DEC["lag_ms"]), np.array(DEC["ratio"])
CAL = [("fps_nov", "static_good", ("v41_f30", "v41ea_f30")), ("topology_nov", "static_good", ("v41", "hier")),
       ("energy_nov", "static_good", ("v41", "v41b36", "freshonly")), ("mesh4", "static_good", ("v41", "accumo", "leaf")),
       ("relaynoise_nov", "multihop_loss2", ("v41", "hier", "fixlap")), ("final_nov", "mesh_mission", ("v41", "v41final"))]


def r(age_ms):
    return np.interp(age_ms, LAG, RAT, right=0.0)


def proxy(run, fps):
    per = 1.0 / fps
    arr = sorted((f["t_res"], f["id"] * per, f["acc"]) for f in run["frames"] if f.get("t_res") is not None and "acc" in f)
    T = max(f["id"] for f in run["frames"]) * per
    ts = np.arange(1.0, T, 1.0 / 30.0)           # real time, sampled at 30 Hz for every frame rate (skip the first second)
    out, i, cap, acc = [], 0, None, 0.0
    ages = []
    for t in ts:
        while i < len(arr) and arr[i][0] <= t:
            if cap is None or arr[i][1] > cap:
                cap, acc = arr[i][1], arr[i][2]
            i += 1
        if cap is None:
            out.append(0.0)
            continue
        age = (t - cap) * 1e3
        ages.append(age)
        out.append(acc * float(r(age)))
    ages = np.array(ages)
    return float(np.mean(out)), float(np.median(ages)), float(np.mean(ages <= 300.0))


def main():
    cal = []
    for camp, sc, sts in CAL:
        c = json.load(open(H / f"vid_campaign_{camp}" / "_eval_cache_mesh.json"))
        for st in sts:
            for f in sorted(glob.glob(str(H / f"vid_campaign_{camp}" / f"a2_{sc}__{st}__r[0-9].json"))):
                key = Path(f).stem[3:]
                fps = 30.0
                e, a50, fr = proxy(json.load(open(f)), fps)
                cal.append({"run": f"{camp}/{key}", "E": e, "sAP_fc": c[key]["sAP_fc"], "age_median_ms": a50, "fresh": fr})
    E = np.array([x["E"] for x in cal])
    S = np.array([x["sAP_fc"] for x in cal])
    k = float(np.sum(E * S) / np.sum(E * E))                   # least squares through the origin
    rel = S / (k * E) - 1
    out = {"k": k, "calibration_runs": len(cal), "pearson_r": float(np.corrcoef(E, S)[0, 1]),
           "rel_err_median_pct": float(100 * np.median(np.abs(rel))), "rel_err_p90_pct": float(100 * np.percentile(np.abs(rel), 90)),
           "calibration": cal, "fps_runs": {}}
    c = json.load(open(H / "vid_campaign_fps_nov" / "_eval_cache_mesh.json"))
    for f in sorted(glob.glob(str(H / "vid_campaign_fps_nov" / "a2_static_good__*__r[0-9].json"))):
        st = re.match(r"a2_static_good__(.+?)__r\d", Path(f).name).group(1)
        fps = float(st.rsplit("_f", 1)[1])
        run = json.load(open(f))
        e, a50, fr = proxy(run, fps)
        out["fps_runs"][Path(f).stem[3:]] = {"fps": fps, "E": e, "sAP_fc_est": k * e,
                                             "sAP_fc_est_range": [k * e * (1 - out["rel_err_p90_pct"] / 100),
                                                                  k * e * (1 + out["rel_err_p90_pct"] / 100)],
                                             "sAP_fc_scored": c[Path(f).stem[3:]]["sAP_fc"], "age_median_ms": a50,
                                             "fresh_share": fr, "on_time_fps": run["total"]["on_time_fps"]}
    by = {}
    for key, v in out["fps_runs"].items():
        by.setdefault(key.split("__")[1], []).append(v)
    out["by_strategy"] = {st: {m: float(np.mean([x[m] for x in L])) for m in ("fps", "sAP_fc_est", "sAP_fc_scored",
                                                                             "age_median_ms", "fresh_share", "on_time_fps")}
                          for st, L in by.items()}
    json.dump(out, open(H / "fps_sap_estimate.json", "w"), indent=1)
    print(f"proxy check on {len(cal)} 30-fps runs: r = {out['pearson_r']:.3f}, k = {k:.3f}, median |error| "
          f"{out['rel_err_median_pct']:.1f} %, p90 {out['rel_err_p90_pct']:.1f} %")
    for st, v in sorted(out["by_strategy"].items(), key=lambda x: x[1]["fps"]):
        print(f"{st:10s} {v['fps']:4.0f} fps  sAP_fc est {v['sAP_fc_est']:.4f} (scored at 30-fps timeline: "
              f"{v['sAP_fc_scored']:.4f})  held age median {v['age_median_ms']:.0f} ms  fresh {100 * v['fresh_share']:.1f} %"
              f"  on-time {v['on_time_fps']:.1f}/s")


if __name__ == "__main__":
    main()
