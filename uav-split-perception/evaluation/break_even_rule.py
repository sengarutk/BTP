#!/usr/bin/env python3
"""When can a split pay off? A break-even rule for any split code against the whole JPEG family, tested on every
measured point (hardening plan, Phase 3; 10 Nov 2026).

The model is the paper's own (simulation/system_model.py, AdaptivePolicy.predict, as in learned_bottleneck_system.py):
an option c has onboard time e_c = t_full * phi_c + host_proc_c * (t_full / t_host), payload b_c, server time s_c,
accuracy A_c; at goodput B its frame rate is F / ceil(F * max(e_c, b_c / B)) and its chance of meeting the deadline D
is p_c(B) = Q((R_c - B) / sigma(B)) with the required rate R_c = b_c / (D - e_c - d - s_c) (one Gaussian sigma for every
option at a given B). Its utility is U_c = f_c * p_c * A_c / A_ref.

Rule (image dominance at goodput B). For a split code k and an image setting q with
    (i)  P * A_q >= A_k,   (ii)  B >= R_q / (1 - z_P s),   (iii) e_q <= m_k  and  b_q <= B * m_k,  m_k = max(e_k, 1/F),
U_q(B) >= U_k(B), where s = sigma(B)/B (the model's relative goodput uncertainty, 0.1) and z_P the standard normal
quantile of P (P = 0.99). [(iii) gives ceil(F max(e_q, b_q/B)) <= ceil(F m_k) = max(1, ceil(F e_k))
<= ceil(F max(e_k, b_k/B)), so f_q >= f_k (the camera rate caps both); (ii) gives p_q >= P;
so U_q >= P f_q A_q >= f_k A_k >= U_k since p_k <= 1.] Taking the best image setting, k can beat the image family only
below the break-even goodput
    B_be(k) = min over q with (i) and e_q <= m_k of  max( b_q / m_k ,  R_q / (1 - z_P s) ),
where b_q / m_k = b_q / max(t_full (phi_k + rho_k), 1/F) falls inversely with the onboard speed until the camera rate
limits,
and not at all if no JPEG setting is at least as accurate (then the paper's Proposition 2 bounds its gain by the
accuracy ratio). A code larger than q* (b_k >= b_q) never beats it beyond that ratio (Proposition 2).

Tested points: every learned code (frozen detector, learned_bottleneck/system.json) and every jointly trained code
(joint_bottleneck/eval_joint_*.json, same architecture: the frozen row's onboard and server times, its own payload and
accuracy), the post-hoc INT8 + zstd splits, on the paper's onboard sweep and the three measured devices (laptop GPU,
Jetson Orin Nano FP16, Pi 5 throttled), at the 31 goodputs of the learned-bottleneck study; and the 43 rows of the
19-detector survey (generalization/model_summary.csv) against Proposition 2.
usage: break_even_rule.py   -> experiments/results/break_even/break_even.json, paper/figures/break_even_map.pdf
"""
import csv
import json
import math
import sys
from dataclasses import fields, replace
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from evaluation.learned_bottleneck_system import GOODPUT, VD, family, measured_configs  # noqa: E402
from simulation.system_model import (HARDWARE_SCENARIOS_MS, AdaptivePolicy, EdgeHardware, OffloadConfig,  # noqa: E402
                                     host_full_ms)

RES = REPO / "experiments" / "results"
P_ON, Z_P = 0.99, 2.3263478740408408   # scipy.stats.norm.ppf(0.99)
OUT = RES / "break_even"
FIG = REPO / "paper" / "figures" / "break_even_map.pdf"


def learned_and_joint():
    sy = json.load(open(RES / "learned_bottleneck" / "system.json"))
    names = {f.name for f in fields(OffloadConfig)}
    frozen = {r["name"]: OffloadConfig(**{k: r[k] for k in names}) for r in sy["learned"]}
    out = list(frozen.values())
    for f in sorted((RES / "joint_bottleneck").glob("eval_joint_*.json")):
        ev = json.load(open(f))
        base = frozen.get("learned_" + ev["config"].replace("joint_", ""))
        if base is None:
            continue
        out.append(replace(base, name=ev["config"], dtype=ev["config"], payload_bytes=ev["payload_bytes_mean"],
                           map50_95=ev["map50_95"], map50=ev["map50"], delta_map50_95=ev["map50_95"] - ev["base_map50_95"]))
    return out


def devices():
    hw = RES / "hardware"
    return ([("sweep", t) for t in HARDWARE_SCENARIOS_MS]
            + [("laptop GPU", json.load(open(hw / "raw" / "laptop_gpu_fp16.json"))["full_ms"]),
               ("Jetson Orin Nano", json.load(open(hw / "raw" / "jetson_gpu_fp16.json"))["full_ms"]),
               ("Pi 5 (throttled)", json.load(open(hw / "placements_summary.json"))["devices"]["pi"]["full_ms"])])


def main():
    cfgs = measured_configs() + learned_and_joint()
    hfull = host_full_ms(None, VD)
    jpeg = [c for c in cfgs if family(c) == "image"]
    splits = [c for c in cfgs if c.kind == "split"]
    rows, viol, checked, wins_total = [], [], 0, 0
    for dev, t in devices():
        pol = AdaptivePolicy(cfgs, EdgeHardware(name=dev, t_full_ms=t, host_full_ms=hfull))
        e = {c.name: pol.hw.onboard_ms(c) for c in cfgs}

        def R(c):
            slack = pol.deadline_ms - e[c.name] - pol.delay_ms - c.cloud_ms
            return math.inf if slack <= 0 else c.payload_bytes * 8 / 1e3 / slack

        def U(c, B):
            p = pol.predict(c, float(B))
            return p["fps"] * p["p_on_time"] * c.map50_95 / pol.base_map
        for k in splits:
            srel = pol.w.min_rel_std
            m_k = max(e[k.name], 1000.0 / pol.camera_fps)
            cand = {q.name: max(q.payload_bytes * 8 / 1e3 / m_k, R(q) / (1 - Z_P * srel))   # kbit/ms = Mbit/s
                    for q in jpeg if P_ON * q.map50_95 >= k.map50_95 and e[q.name] <= m_k}
            qs = next((q for q in jpeg if cand and q.name == min(cand, key=cand.get)), None)
            b_be = cand[qs.name] if qs else None
            win = []
            for B in GOODPUT:
                uk, ui = U(k, B), max(U(q, B) for q in jpeg)
                if uk > ui * (1 + 1e-9):
                    win.append(float(B))
                    wins_total += 1
                    if b_be is not None:
                        checked += 1
                        if not B < b_be:
                            viol.append({"device": dev, "t_full_ms": t, "code": k.name, "goodput": float(B), "b_be": b_be})
            rows.append({"device": dev, "t_full_ms": t, "code": k.name, "family": family(k),
                         "payload_kb": k.payload_bytes / 1e3, "map50_95": k.map50_95, "onboard_ms": e[k.name],
                         "q_star": qs.name if qs else None, "q_star_map50_95": qs.map50_95 if qs else None, "q_star_kb": qs.payload_bytes / 1e3 if qs else None,
                         "b_be_mbps": b_be, "wins_at_mbps": win, "max_win_mbps": max(win) if win else None,
                         "rule_upper_bound_holds": (not win) or b_be is None or max(win) < b_be})
    surv = []
    for r in csv.DictReader(open(RES / "generalization" / "model_summary.csv")):
        bk, bq = float(r["int8_zstd_kib"]), float(r["jpeg_q95_kib"])
        ek, eq = float(r["edge_flop_frac"]) + float(r["rho_split"]), float(r["rho_jpeg"])
        surv.append({"model": r["model"], "imgsz": r["imgsz"], "images": r["images"], "split_kib": bk, "jpeg_q95_kib": bq,
                     "split_onboard_frac": ek, "jpeg_onboard_frac": eq, "prop2_bits_and_onboard": bk >= bq and ek >= eq})
    out = {"model": "simulation/system_model.py AdaptivePolicy.predict (as learned_bottleneck_system.py)",
           "goodput_mbps": GOODPUT.tolist(), "devices": [{"device": d, "t_full_ms": t} for d, t in devices()],
           "rule_check": {"split_win_cells": wins_total, "cells_with_q_star": checked, "violations": viol},
           "codes": rows,
           "survey": {"rows": len(surv), "prop2_holds": sum(s["prop2_bits_and_onboard"] for s in surv),
                      "models": len({s["model"] for s in surv}), "per_row": surv}}
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(OUT / "break_even.json", "w"), indent=1)
    figure(out)
    macros(out)
    print(json.dumps(out["rule_check"], indent=1)[:600])
    print(f"survey: Proposition 2 conditions hold in {out['survey']['prop2_holds']} of {out['survey']['rows']} rows "
          f"({out['survey']['models']} models)")
    for r in rows:
        if r["family"] != "posthoc_split" and r["device"] != "sweep":
            print(f"{r['device']:17s} {r['code']:24s} {r['payload_kb']:6.1f} kB mAP {r['map50_95']:.3f}  q*={r['q_star']}"
                  f"  B_be={r['b_be_mbps'] if r['b_be_mbps'] is None else round(r['b_be_mbps'], 2)}  wins up to {r['max_win_mbps']}")


def macros(out):
    """LaTeX macros for the paper's design-rule subsection (paper/drafts/design_rule.tex)."""
    import numpy as np
    r = [x for x in out["codes"] if x["max_win_mbps"] and x["b_be_mbps"]]

    def tight(dev):
        v = [x["b_be_mbps"] / x["max_win_mbps"] - 1 for x in r if x["device"] == dev]
        return 100 * float(np.median(v)) if v else float("nan")
    pi = next(x for x in out["codes"] if x["device"].startswith("Pi") and x["code"] == "learned_k4_c4_w128_d2")
    m = {"BeCells": str(out["rule_check"]["split_win_cells"]), "BeViolations": str(len(out["rule_check"]["violations"])),
         "BeSurveyRows": str(out["survey"]["rows"]), "BeSurveyModels": str(out["survey"]["models"]),
         "BeSurveyHold": str(out["survey"]["prop2_holds"]),
         "BeTightFast": f"{max(tight('laptop GPU'), tight('Jetson Orin Nano')):.0f}", "BeTightPi": f"{tight('Pi 5 (throttled)'):.0f}",
         "BePiCodeKib": f"{pi['payload_kb'] * 1000 / 1024:.1f}", "BePiBe": f"{pi['b_be_mbps']:.2f}", "BePiWin": f"{pi['max_win_mbps']:.2f}",
         "BePiQstar": pi["q_star"].replace("jpeg_q", "Q"), "BePOn": f"{P_ON:g}",
         "BeCodes": str(len({x["code"] for x in out["codes"] if x["family"] != "posthoc_split"})),
         "BeDevices": str(len(out["devices"]))}
    (OUT / "be_metrics.tex").write_text("% Generated by evaluation/break_even_rule.py -- do not edit.\n"
                                        + "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in m.items()))


def figure(out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    rows = [r for r in out["codes"] if r["family"] != "posthoc_split" and r["b_be_mbps"] is not None]
    codes = sorted({r["code"] for r in rows}, key=lambda c: min(r["payload_kb"] for r in rows if r["code"] == c))
    fig, ax = plt.subplots(figsize=(3.45, 2.6))
    cmap = plt.get_cmap("viridis")
    for i, c in enumerate(codes):
        rr = sorted([r for r in rows if r["code"] == c], key=lambda r: r["t_full_ms"])
        col = cmap(i / max(1, len(codes) - 1))
        ls = "--" if c.startswith("joint") else "-"
        t = np.array([r["t_full_ms"] for r in rr])
        ax.plot(t, [r["b_be_mbps"] for r in rr], ls, color=col, lw=1,
                label=f"{rr[0]['payload_kb'] * 1000 / 1024:.1f} KiB" + (" joint" if c.startswith("joint") else ""))
        for r in rr:
            if r["max_win_mbps"]:
                ax.plot(r["t_full_ms"], r["max_win_mbps"], "o", ms=3, color=col)
    for d in out["devices"]:
        if d["device"] != "sweep":
            ax.axvline(d["t_full_ms"], color="0.6", lw=0.6, ls=":")
            ax.text(d["t_full_ms"] * 1.06, 45, d["device"].split(" (")[0], rotation=90, fontsize=5.5, va="top", color="0.35")
    ax.set_ylim(0.3, 50)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("onboard full-model time (ms)", fontsize=8)
    ax.set_ylabel("goodput (Mbit/s)", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.legend(fontsize=5, ncol=2, loc="lower left", frameon=False, title="code size", title_fontsize=5)
    fig.tight_layout()
    FIG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG)


if __name__ == "__main__":
    main()
