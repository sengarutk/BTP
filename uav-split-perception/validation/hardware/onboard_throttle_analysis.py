#!/usr/bin/env python3
"""YOLOv8s / m / l onboard on the Pi 5: streaming AP, and the effect of thermal throttling on it.

Inputs (all live runs, static_good, one model alone on the Pi, no live forecaster):
  vid_campaign_onboard_{pi2,pi3}/        short runs (4 min), started HOT (back to back)
  vid_campaign_onboard_cool_{pi2,pi3}/   short runs (4 min), started COOL (Pi cooled first: pi2 < 55 C, pi3 < 61 C)
  vid_campaign_onboard_long_{pi2,pi3}/   long runs (24 min = 6 windows of 4 min), started COOL
Per run: sAP (standard 'newest' rule) without and with forecaster v2 (offline camera-motion chain), fresh AP,
median onboard inference time, Pi power, temperature, time >= 80 C; for runs with a clock log (cool + long):
mean ARM clock and the share of samples with the firmware's throttle flag set (bit 2 = throttled now).
Long runs also per 4-minute window: sAP, inference time, temperature, clock, throttled share.
Counterfactual "no throttling": sAP of the same model at its cool inference time, read off the emulation curve
(onboard_sap.py emulate: same detections, same scorer) by interpolating in log-latency.
Full-clock counterfactual per run: inference time x (mean clock / 2400 MHz) = the time at the unthrottled clock,
read off the same emulation curve.
usage: onboard_throttle_analysis.py [--weights visdrone|coco]
  visdrone (default): the VisDrone fine-tuned weights (vid_campaign_onboard*_vd_{b}, *_vd_l_{b})
                      -> onboard_sap/throttle_analysis_visdrone.json
  coco:               the COCO weights (the first set of runs) -> onboard_sap/throttle_analysis.json
"""
import argparse
import glob
import json
import multiprocessing as mp
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
HW = HERE.parent.parent / "experiments" / "results" / "hardware"
VID = HERE.parent.parent / "datasets" / "visdrone_vid_640"
COND = {"short_hot": ["vid_campaign_onboard_{b}"], "short_cool": ["vid_campaign_onboard_cool_{b}"],
        "long_cool": ["vid_campaign_onboard_long_{b}"]}
# VisDrone weights: s and m ran in *_vd_{b}, l (trained last) in *_vd_l_{b}
COND_VD = {c: [p[0].replace("_{b}", "_vd_{b}"), p[0].replace("_{b}", "_vd_l_{b}")] for c, p in COND.items()}
EMU = {"s640": "yolov8s", "m640": "yolov8m", "l640": "yolov8l",
       "s640vd": "yolov8s_vd", "m640vd": "yolov8m_vd", "l640vd": "yolov8l_vd"}
FULL_MHZ = 2400.0


def one(args):
    cond, board, f = args
    from stream_ap import evaluate
    labels = json.load(open(VID / "labels.json"))
    fp = json.load(open(HW / "forecast_tuning_v2.json"))["best"]["params"]
    d = json.load(open(f))
    r0 = evaluate(Path(f), labels, "newest")
    r1 = evaluate(Path(f), labels, "newest", forecast=fp)
    me = d["measured_energy"]
    lg = np.array([x for x in me["log_t_w_c"] if x[1] == x[1] and x[2] == x[2]], float)
    ck = np.array(me.get("clock_log_t_mhz_flags", []), float) if me.get("clock_log_t_mhz_flags") else None
    fr = d["frames"]
    model = Path(f).stem.split("__")[1].replace("onboard_", "").replace("_vd", "vd")
    row = {"cond": cond, "board": board, "model": model, "run": Path(f).stem[3:],
           "sAP": r0["sAP"], "sAP50": r0["sAP50"], "sAP_fc": r1["sAP"], "fresh_AP": r0["fresh_AP"],
           "lat_ms": float(np.median([x["lat_ms"] for x in fr if x.get("lat_ms")])),
           "results": sum(1 for x in fr if x.get("t_res") is not None),
           "pi_w": float(lg[:, 1].mean()), "temp_mean": float(lg[:, 2].mean()), "temp_max": float(lg[:, 2].max()),
           "temp_start": float(lg[:10, 2].mean()), "hot_share": float((lg[:, 2] >= 80).mean())}
    if ck is not None and len(ck):
        ok = ck[:, 2] >= 0
        row["clock_mhz"] = float(np.nanmean(ck[ok, 1]))
        row["throttled_share"] = float(np.mean((ck[ok, 2].astype(int) & 0x4) > 0))
    if cond == "long_cool":
        wins = []
        names = list(d["per_phase"])
        t_end = lg[-1, 0]
        for i, ph in enumerate(names):
            lo, hi = i * t_end / len(names), (i + 1) * t_end / len(names)
            m = (lg[:, 0] >= lo) & (lg[:, 0] < hi)
            w = {"window": i + 1, "minutes": f"{4 * i}-{4 * (i + 1)}", "sAP": r0["per_phase_sAP"].get(ph),
                 "sAP_fc": r1["per_phase_sAP"].get(ph), "fresh_AP": r0["per_phase_fresh_AP"].get(ph),
                 "lat_ms": float(np.median([x["lat_ms"] for x in fr if x.get("lat_ms") and x["phase"] == ph] or [np.nan])),
                 "results": sum(1 for x in fr if x.get("t_res") is not None and x["phase"] == ph),
                 "temp": float(lg[m, 2].mean()), "pi_w": float(lg[m, 1].mean())}
            if ck is not None and len(ck):
                mc = (ck[:, 0] >= lo) & (ck[:, 0] < hi) & (ck[:, 2] >= 0)
                w["clock_mhz"] = float(np.nanmean(ck[mc, 1])) if mc.any() else None
                w["throttled_share"] = float(np.mean((ck[mc, 2].astype(int) & 0x4) > 0)) if mc.any() else None
            wins.append(w)
        row["windows"] = wins
    return row


def counterfactual(emu, model, lat_ms):
    """sAP of `model` at a given inference time, interpolated in log-latency on the emulation grid."""
    g = emu[model]["by_latency_ms"]
    L = np.array(sorted(int(k) for k in g))
    out = {}
    for key, name in (("sAP", "sAP"), ("sAP_fc2", "sAP_fc")):
        v = np.array([g[str(x)][key] for x in L])
        out[name] = float(np.interp(np.log(lat_ms), np.log(L), v))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--weights", choices=["visdrone", "coco"], default="visdrone")
    vd = ap.parse_args().weights == "visdrone"
    cond_dirs = COND_VD if vd else COND
    models = ("s640vd", "m640vd", "l640vd") if vd else ("s640", "m640", "l640")
    out_name = "throttle_analysis_visdrone.json" if vd else "throttle_analysis.json"
    jobs = []
    for cond, pats in cond_dirs.items():
        for b in ("pi2", "pi3"):
            for pat in pats:
                for f in sorted(glob.glob(str(HW / pat.format(b=b) / "a2_*__r*.json"))):
                    jobs.append((cond, b, f))
    with mp.get_context("fork").Pool(4) as pool:
        rows = pool.map(one, jobs, chunksize=1)
    emu = json.load(open(HW / "onboard_sap" / "onboard_sap_emulated.json"))
    for r in rows:   # the same run at the full 2.4 GHz clock (inference time scales with the clock)
        if r.get("clock_mhz") and EMU[r["model"]] in emu:
            r["lat_full_clock_ms"] = r["lat_ms"] * r["clock_mhz"] / FULL_MHZ
            r["emulated_full_clock"] = counterfactual(emu, EMU[r["model"]], r["lat_full_clock_ms"])
            r["emulated_measured"] = counterfactual(emu, EMU[r["model"]], r["lat_ms"])
    summary = {}
    for cond in cond_dirs:
        for m in models:
            rs = [r for r in rows if r["cond"] == cond and r["model"] == m]
            if not rs:
                continue
            s = {"n": len(rs)}
            for k in ("sAP", "sAP50", "sAP_fc", "fresh_AP", "lat_ms", "results", "pi_w", "temp_start", "temp_mean",
                      "temp_max", "hot_share", "clock_mhz", "throttled_share"):
                v = [r[k] for r in rs if r.get(k) is not None]
                if v:
                    s[k] = float(np.mean(v))
                    s[k + "_min"], s[k + "_max"] = float(np.min(v)), float(np.max(v))
            summary.setdefault(cond, {})[m] = s
    # counterfactual: the cool inference time = first long-run window's median latency
    cf = {}
    for m in models:
        rs = [r for r in rows if r["cond"] == "long_cool" and r["model"] == m]
        if not rs:
            continue
        cool = float(np.mean([r["windows"][0]["lat_ms"] for r in rs]))
        hot = float(np.mean([r["windows"][-1]["lat_ms"] for r in rs]))
        model = EMU[m]
        cf[m] = {"lat_cool_ms": cool, "lat_hot_ms": hot, "slowdown": hot / cool,
                 "emulated_at_cool": counterfactual(emu, model, cool), "emulated_at_hot": counterfactual(emu, model, hot)}
    fc_rows = {}
    for cond in cond_dirs:
        for m in models:
            rs = [r for r in rows if r["cond"] == cond and r["model"] == m and "emulated_full_clock" in r]
            if rs:
                fc_rows.setdefault(cond, {})[m] = {
                    "n": len(rs), "lat_ms": float(np.mean([r["lat_ms"] for r in rs])),
                    "lat_full_clock_ms": float(np.mean([r["lat_full_clock_ms"] for r in rs])),
                    **{f"{k}_{w}": float(np.mean([r[f"emulated_{w}"][k] for r in rs]))
                       for k in ("sAP", "sAP_fc") for w in ("measured", "full_clock")}}
    json.dump({"weights": "visdrone" if vd else "coco", "rows": rows, "summary": summary, "counterfactual": cf,
               "counterfactual_full_clock": fc_rows},
              open(HW / "onboard_sap" / out_name, "w"), indent=1, default=float)
    for cond, ms in summary.items():
        print(f"== {cond}")
        for m, s in ms.items():
            print(f"  {m}: n={s['n']} sAP {s['sAP']:.4f} (+fc {s['sAP_fc']:.4f}) freshAP {s['fresh_AP']:.3f}  "
                  f"lat {s['lat_ms']:.0f} ms  start {s['temp_start']:.1f} C  mean {s['temp_mean']:.1f} C  "
                  f">=80C {s['hot_share'] * 100:.0f}%  {s['pi_w']:.2f} W"
                  + (f"  clock {s['clock_mhz']:.0f} MHz  throttled {s['throttled_share'] * 100:.0f}%"
                     if 'clock_mhz' in s else ""))
    print("== long runs by 4-minute window (mean over runs)")
    for m in models:
        rs = [r for r in rows if r["cond"] == "long_cool" and r["model"] == m]
        for i in range(6 if rs else 0):
            ws = [r["windows"][i] for r in rs]
            g = lambda k: np.nanmean([w[k] for w in ws if w.get(k) is not None])  # noqa: E731
            print(f"  {m} min {ws[0]['minutes']:>5s}: sAP {g('sAP'):.4f} (+fc {g('sAP_fc'):.4f})  mAP {g('fresh_AP'):.3f}  lat {g('lat_ms'):5.0f} ms  "
                  f"{g('temp'):.1f} C  clock {g('clock_mhz'):.0f} MHz  throttled {g('throttled_share') * 100:3.0f}%")
    print("== counterfactual (emulation at the cool vs the throttled inference time)")
    for m, c in cf.items():
        print(f"  {m}: {c['lat_cool_ms']:.0f} -> {c['lat_hot_ms']:.0f} ms (x{c['slowdown']:.2f}); "
              f"sAP cool {c['emulated_at_cool']['sAP']:.4f} vs hot {c['emulated_at_hot']['sAP']:.4f}; "
              f"with forecaster {c['emulated_at_cool']['sAP_fc']:.4f} vs {c['emulated_at_hot']['sAP_fc']:.4f}")

    print("== full-clock counterfactual (emulated sAP at the measured vs the 2.4 GHz inference time)")
    for cond, ms in fc_rows.items():
        for m, c in ms.items():
            print(f"  {cond} {m}: {c['lat_ms']:.0f} -> {c['lat_full_clock_ms']:.0f} ms; sAP {c['sAP_measured']:.4f} -> "
                  f"{c['sAP_full_clock']:.4f}; with forecaster {c['sAP_fc_measured']:.4f} -> {c['sAP_fc_full_clock']:.4f}")


if __name__ == "__main__":
    main()
