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
where b_q / m_k = b_q / max(t_full (phi_k + rho_k), 1/F) grows with the onboard speed (shorter e_k) until the camera
rate (m_k = 1/F) or the deadline term R_q / (1 - z_P s) binds; B_be is infinite if no JPEG setting is at least as accurate (then the paper's Proposition 2 bounds its gain by the
accuracy ratio). A code larger than q* (b_k >= b_q) never beats it beyond that ratio (Proposition 2).

Tested points: every learned code (frozen detector, learned_bottleneck/system.json) and every jointly trained code
(joint_bottleneck/eval_joint_*.json, same architecture: the frozen row's onboard and server times, its own payload and
accuracy), the post-hoc INT8 + zstd splits, on the paper's onboard sweep and the three measured devices (laptop GPU,
Jetson Orin Nano FP16, Pi 5 throttled), at the 31 goodputs of the learned-bottleneck study; and the 43 rows of the
19-detector survey (generalization/model_summary.csv) against Proposition 2.
JPEG options (11 Nov 2026, after an independent audit): the 7 qualities of the paper (10, 20, 35, 50, 75, 90, 95) plus
the finer grid of learned_bottleneck/jpeg_fine/ (every 5 from 15 to 85), measured on the same frames with the same
detector. Encode and server times of a quality not in the VisDrone codec table are interpolated in quality between
its rows (50, 75, 90, 95; they differ by < 0.4 ms); below 50 they are q50's, as the paper's q10-q35 rows already are
(slightly too slow for JPEG, so the error favours the split). With experiments/results/jpeg_tuned/ present, the rule is
also evaluated against the detector fine-tuned on JPEG (evaluation/jpeg_tuned_detector.py), the fair counterpart of
the jointly trained codes -> break_even.json "jpeg_tuned".
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
                                     load_offload_configs,
                                     host_full_ms)

RES = REPO / "experiments" / "results"
TUNED_RUNS = ("jpegtuned_qmix_r1",)            # evaluation/jpeg_tuned_detector.py run names
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


def fam(c):
    return "joint" if c.name.startswith("joint_") else "entropy" if c.name.startswith("ec_") else family(c)


def entropy_codes():
    """The entropy-coded codes of evaluation/entropy_bottleneck.py (eval_ec_*.json, smoke runs excluded) as options:
    the encoder and decoder of the k4_c32 code they start from (same MACs, same decoder time), its server time, plus
    the measured range-coding times (encode onboard, decode on the server; host CPU, as the uint8 + zstd time of the
    learned rows)."""
    ec = RES / "entropy_bottleneck"
    if not ec.exists():
        return []
    frozen = {c.name: c for c in learned_and_joint()}
    out = []
    for f in sorted(ec.glob("eval_ec_*.json")):
        ev = json.load(open(f))
        if "smoke" in ev["config"]:
            continue
        b = frozen["learned_" + ev["init"]]
        out.append(replace(b, name=ev["config"], dtype=ev["config"], payload_bytes=ev["payload_bytes_mean"],
                           host_edge_proc_ms=ev["host_range_encode_ms_median"],
                           cloud_ms=b.cloud_ms + ev["host_range_decode_ms_median"], map50_95=ev["map50_95"],
                           map50=ev["map50"], delta_map50_95=ev["map50_95"] - ev["base_map50_95"]))
    return out


def jpeg_grid(base_cfgs):
    """The paper's JPEG rows plus the finer grid (learned_bottleneck/jpeg_fine/jpeg_q*.json), timings interpolated."""
    jp = {c.name: c for c in base_cfgs if family(c) == "image"}
    tab = load_offload_configs(VD)
    ref = sorted((int(n[len("jpeg_q"):]), c) for n, c in tab.items() if n.startswith("jpeg_q"))

    def timing(q):
        if q <= ref[0][0]:
            c = ref[0][1]
            return c.host_edge_proc_ms, c.cloud_ms
        for (q0, c0), (q1, c1) in zip(ref, ref[1:]):
            if q0 <= q <= q1:
                w = (q - q0) / (q1 - q0)
                return (c0.host_edge_proc_ms + w * (c1.host_edge_proc_ms - c0.host_edge_proc_ms),
                        c0.cloud_ms + w * (c1.cloud_ms - c0.cloud_ms))
        c = ref[-1][1]
        return c.host_edge_proc_ms, c.cloud_ms
    proto = jp["jpeg_q50"]
    for f in sorted((RES / "learned_bottleneck" / "jpeg_fine").glob("jpeg_q*.json")):
        m = json.load(open(f))
        if m["config"] in jp:
            continue
        hp, cl = timing(m["q"])
        jp[m["config"]] = replace(proto, name=m["config"], dtype=f"q{m['q']}", payload_bytes=m["payload_bytes_mean"],
                                  map50_95=m["map50_95"], map50=m["map50"],
                                  delta_map50_95=m["map50_95"] - m["base_map50_95"], host_edge_proc_ms=hp, cloud_ms=cl)
    return sorted(jp.values(), key=lambda c: int(c.name[len("jpeg_q"):]))


def tuned_jpeg(jpeg, run, best=False):
    """The same JPEG options with the accuracy of the detector fine-tuned on JPEG (jpeg_tuned/eval_<run>_q<Q>.json);
    payload and timings unchanged (the eval checks that the payload equals the untuned row's). best: at each quality the
    better of the tuned and the untuned detector (the server knows the quality it receives, so it can run either)."""
    out = []
    for c in jpeg:
        f = RES / "jpeg_tuned" / f"eval_{run}_q{c.name[len('jpeg_q'):]}.json"
        if not f.exists():
            return None
        ev = json.load(open(f))
        assert ev["payload_matches_untuned"], f
        if best and ev["map50_95"] <= c.map50_95:
            out.append(c)
            continue
        out.append(replace(c, map50_95=ev["map50_95"], map50=ev["map50"],
                           delta_map50_95=c.delta_map50_95 + ev["gain"]))
    return out


def devices():
    hw = RES / "hardware"
    return ([("sweep", t) for t in HARDWARE_SCENARIOS_MS]
            + [("laptop GPU", json.load(open(hw / "raw" / "laptop_gpu_fp16.json"))["full_ms"]),
               ("Jetson Orin Nano", json.load(open(hw / "raw" / "jetson_gpu_fp16.json"))["full_ms"]),
               ("Pi 5 (throttled)", json.load(open(hw / "placements_summary.json"))["devices"]["pi"]["full_ms"])])


def b_be_fading(dev_t, k, jpeg, rel_std, hfull, cfgs):
    """Fading version of B_be (11 Nov 2026, from evaluation/break_even_sim.py): with a goodput that varies with relative
    spread rel_std (std / mean of the trace), both terms are discounted by the low quantile (1 - z_P rel_std):
        B_be,f(k) = min over P of  min over q with P A_q >= A_k, e_q <= m_k of  max(b_q / m_k, R_q) / (1 - z_P rel_std).
    Not proved for fading channels (the frame rate under a varying goodput has no closed form in the model); it is an
    empirical rule, checked in the simulator. Returns (B_be,f, P) or None."""
    from statistics import NormalDist
    pol = AdaptivePolicy(cfgs, EdgeHardware(name="d", t_full_ms=dev_t, host_full_ms=hfull))
    e = {c.name: pol.hw.onboard_ms(c) for c in cfgs}

    def R(c):
        slack = pol.deadline_ms - e[c.name] - pol.delay_ms - c.cloud_ms
        return math.inf if slack <= 0 else c.payload_bytes * 8 / 1e3 / slack
    m_k = max(e[k.name], 1000.0 / pol.camera_fps)
    best = None
    for P in [0.5 + 0.005 * i for i in range(100)] + [0.999]:
        z = NormalDist().inv_cdf(P)
        if z * rel_std >= 1:
            continue
        c = [max(q.payload_bytes * 8 / 1e3 / m_k, R(q)) / (1 - z * rel_std) for q in jpeg
             if P * q.map50_95 >= k.map50_95 and e[q.name] <= m_k]
        if c and (best is None or min(c) < best[0]):
            best = (min(c), P)
    return best


def analyse(jpeg, others):
    """Break-even goodput of every split in `others` against the JPEG options `jpeg`, on every device and goodput."""
    cfgs = others + jpeg
    hfull = host_full_ms(None, VD)
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
            rows.append({"device": dev, "t_full_ms": t, "code": k.name, "family": fam(k),
                         "payload_kb": k.payload_bytes / 1e3, "map50_95": k.map50_95, "onboard_ms": e[k.name],
                         "q_star": qs.name if qs else None, "q_star_map50_95": qs.map50_95 if qs else None, "q_star_kb": qs.payload_bytes / 1e3 if qs else None,
                         "b_be_mbps": b_be, "wins_at_mbps": win, "max_win_mbps": max(win) if win else None,
                         "rule_upper_bound_holds": (not win) or b_be is None or max(win) < b_be})
    return rows, viol, checked, wins_total


def main():
    base = measured_configs()
    jpeg = jpeg_grid(base)
    others = [c for c in base if family(c) != "image"] + learned_and_joint()
    rows, viol, checked, wins_total = analyse(jpeg, others)
    surv = []
    for r in csv.DictReader(open(RES / "generalization" / "model_summary.csv")):
        bk, bq = float(r["int8_zstd_kib"]), float(r["jpeg_q95_kib"])
        ek, eq = float(r["edge_flop_frac"]) + float(r["rho_split"]), float(r["rho_jpeg"])
        surv.append({"model": r["model"], "imgsz": r["imgsz"], "images": r["images"], "split_kib": bk, "jpeg_q95_kib": bq,
                     "split_onboard_frac": ek, "jpeg_onboard_frac": eq, "prop2_bits_and_onboard": bk >= bq and ek >= eq})
    out = {"model": "simulation/system_model.py AdaptivePolicy.predict (as learned_bottleneck_system.py)",
           "goodput_mbps": GOODPUT.tolist(), "devices": [{"device": d, "t_full_ms": t} for d, t in devices()],
           "rule_check": {"split_win_cells": wins_total, "cells_with_q_star": checked, "violations": viol},
           "jpeg_options": [{"config": c.name, "payload_kb": c.payload_bytes / 1e3, "map50_95": c.map50_95,
                             "host_edge_proc_ms": c.host_edge_proc_ms, "cloud_ms": c.cloud_ms} for c in jpeg],
           "codes": rows,
           "survey": {"rows": len(surv), "prop2_holds": sum(s["prop2_bits_and_onboard"] for s in surv),
                      "models": len({s["model"] for s in surv}), "per_row": surv}}
    # the paper's 7 JPEG qualities only, to show what the finer grid changes
    cr, cv, cc, cw = analyse([c for c in base if family(c) == "image"], others)
    out["coarse_jpeg_grid"] = {"jpeg_options": [c.name for c in base if family(c) == "image"],
                               "rule_check": {"split_win_cells": cw, "cells_with_q_star": cc, "violations": cv},
                               "codes": [{k: r[k] for k in ("device", "t_full_ms", "code", "q_star", "b_be_mbps",
                                                            "max_win_mbps")} for r in cr]}
    for run in TUNED_RUNS:                        # against the detector fine-tuned on JPEG, if evaluated
        for best in (False, True):
            tj = tuned_jpeg(jpeg, run, best)
            if tj is not None:
                tr, tv, tc, tw = analyse(tj, others)
                out.setdefault("jpeg_tuned", {})[run + ("_best_of_both" if best else "")] = {
                    "jpeg_options": [{"config": c.name, "map50_95": c.map50_95} for c in tj],
                    "rule_check": {"split_win_cells": tw, "cells_with_q_star": tc, "violations": tv}, "codes": tr}
    ec = entropy_codes()                          # entropy-coded codes, a separate analysis (main cells unchanged)
    if ec:
        out["entropy_codes"] = {"codes": [c.name for c in ec]}
        for key, jp in (("untuned", jpeg), ("best_of_both", tuned_jpeg(jpeg, TUNED_RUNS[0], best=True))):
            if jp is None:
                continue
            er, ev_, ec_, ew = analyse(jp, others + ec)
            out["entropy_codes"][key] = {"rule_check": {"split_win_cells": ew, "violations": ev_},
                                         "codes": [r for r in er if r["family"] in ("entropy", "learned", "joint")]}
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
    def tight_f(dev, fam):
        v = [x["b_be_mbps"] / x["max_win_mbps"] - 1 for x in r if x["device"] == dev and x["family"] == fam]
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
    # jointly trained codes (joint_bottleneck/eval_joint_*.json) against the same code trained on the frozen detector
    by = {(x["device"], x["code"]): x for x in out["codes"]}
    jt = [(x, by[(x["device"], "learned_" + x["code"][len("joint_"):])]) for x in out["codes"] if x["family"] == "joint"]
    if jt:
        dev_pi = next(d["device"] for d in out["devices"] if d["device"].startswith("Pi"))
        g = [j["map50_95"] - f["map50_95"] for j, f in jt if j["device"] == dev_pi]
        jpi = by[(dev_pi, "joint_k4_c4_w128_d2")]
        k2 = by[(dev_pi, "joint_k2_c8_w128_d2")]
        jfast = by[("Jetson Orin Nano", "joint_k4_c4_w128_d2")]
        ffast = by[("Jetson Orin Nano", "learned_k4_c4_w128_d2")]
        wins = lambda fam: sum(len(x["wins_at_mbps"]) for x in out["codes"] if x["family"] == fam and x["device"] != "sweep")  # noqa: E731
        m.update({"BeJointCodes": str(len(g)), "BeJointGainMin": f"{min(g):.3f}", "BeJointGainMax": f"{max(g):.3f}",
                  "BeJointSmallMap": f"{jpi['map50_95']:.3f}", "BeFrozenSmallMap": f"{by[(dev_pi, 'learned_k4_c4_w128_d2')]['map50_95']:.3f}",
                  "BeJointPiCodeKib": f"{jpi['payload_kb'] * 1000 / 1024:.1f}", "BeJointPiBe": f"{jpi['b_be_mbps']:.2f}",
                  "BeJointPiWin": f"{jpi['max_win_mbps']:.2f}", "BeJointPiQstar": jpi["q_star"].replace("jpeg_q", "Q"),
                  "BeJointKtwoKib": f"{k2['payload_kb'] * 1000 / 1024:.1f}",
                  "BeJointKtwoPiWin": f"{k2['max_win_mbps']:.2f}" if k2["max_win_mbps"] else "none",
                  "BeJointKtwoPiBe": f"{k2['b_be_mbps']:.2f}",
                  "BeJointFastBe": f"{jfast['b_be_mbps']:.2f}", "BeFrozenFastBe": f"{ffast['b_be_mbps']:.2f}",
                  "BeJointFastWin": f"{jfast['max_win_mbps']:.2f}", "BeFrozenFastWin": f"{ffast['max_win_mbps']:.2f}",
                  "BeTightPiFrozen": f"{tight_f(dev_pi, 'learned'):.0f}",
                  "BeJointShift": f"{100 * (jpi['b_be_mbps'] / by[(dev_pi, 'learned_k4_c4_w128_d2')]['b_be_mbps'] - 1):.0f}"})
    # what the numbers rest on (independent audit, 11 Nov 2026): grid resolution, how many codes win, speeds that are
    # measured devices rather than sweep values, the JPEG qualities, and the bootstrap half-width of the joint codes
    fast = [x for x in r if x["device"] in ("laptop GPU", "Jetson Orin Nano")]
    gp = np.array(out["goodput_mbps"])
    halfw = []
    for f in sorted((RES / "joint_bottleneck").glob("eval_joint_*.json")):
        ev = json.load(open(f))
        halfw.append((ev["boot_delta_map50_95_ci_high"] - ev["boot_delta_map50_95_ci_low"]) / 2)
    m.update({"BeGridStepPct": f"{100 * float(np.median(gp[1:] / gp[:-1] - 1)):.0f}",
              "BeTightFastN": str(len(fast)),
              "BeTightFastMax": f"{100 * max(x['b_be_mbps'] / x['max_win_mbps'] - 1 for x in fast):.0f}",
              "BePiWinCodesFrozen": str(sum(1 for x in r if x["device"].startswith("Pi") and x["family"] == "learned")),
              "BePiWinCodesJoint": str(sum(1 for x in r if x["device"].startswith("Pi") and x["family"] == "joint")),
              "BeSweepSpeeds": str(sum(1 for d in out["devices"] if d["device"] == "sweep")),
              "BeMeasuredDevices": str(sum(1 for d in out["devices"] if d["device"] != "sweep")),
              "BeJpegQualities": str(len(out["jpeg_options"])),
              "BeJointHalfCi": f"{max(halfw):.3f}" if halfw else "nan"})
    pf = RES / "joint_bottleneck" / "paired_joint_vs_frozen.json"     # evaluation/joint_vs_frozen.py
    if pf.exists():
        pr = json.load(open(pf))["rows"]
        ns = [x for x in pr if not x["significant"]]
        m.update({"BeJointPairedSig": str(sum(x["significant"] for x in pr)), "BeJointPairedN": str(len(pr)),
                  "BeJointPairedBoot": str(pr[0]["n_boot"]),
                  "BeJointNsGain": f"{ns[0]['gain']:.3f}" if ns else "none",
                  "BeJointNsLo": f"{ns[0]['boot_delta_map50_95_ci_low']:.3f}".replace("-", "\\textminus{}") if ns else "",
                  "BeJointNsHi": f"{ns[0]['boot_delta_map50_95_ci_high']:.3f}" if ns else "",
                  "BeJointSigMinGain": f"{min(x['gain'] for x in pr if x['significant']):.3f}",
                  "BeJointSigMinLo": f"{min((x for x in pr if x['significant']), key=lambda x: x['gain'])['boot_delta_map50_95_ci_low']:.3f}"})
    m["BeTightFastMedian"] = m["BeTightFast"]
    if "coarse_jpeg_grid" in out:
        co = out["coarse_jpeg_grid"]
        ck = next(x for x in co["codes"] if x["device"].startswith("Pi") and x["code"] == "joint_k2_c8_w128_d2")
        m.update({"BeCellsCoarse": str(co["rule_check"]["split_win_cells"]),
                  "BeViolationsCoarse": str(len(co["rule_check"]["violations"])),
                  "BeJpegQualitiesCoarse": str(len(co["jpeg_options"])),
                  "BeJointKtwoPiWinCoarse": f"{ck['max_win_mbps']:.2f}" if ck["max_win_mbps"] else "none"})
    m.update(tuned_macros(out))
    (OUT / "be_metrics.tex").write_text("% Generated by evaluation/break_even_rule.py -- do not edit.\n"
                                        + "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in m.items()))


def tuned_macros(out):
    """Macros for the comparison against the detector fine-tuned on JPEG (evaluation/jpeg_tuned_detector.py).
    The fair baseline is "best of both": at each quality the server runs the tuned or the untuned detector, whichever
    is more accurate (it knows the quality it receives); the tuned detector alone is weaker than the untuned one at
    high quality, which would leave the large codes without a qualifying JPEG setting."""
    run = TUNED_RUNS[0]
    if "jpeg_tuned" not in out or run + "_best_of_both" not in out["jpeg_tuned"]:
        return {}
    jt = RES / "jpeg_tuned"
    tr = json.load(open(jt / f"train_{run}.json"))
    ev = {int(f.stem.rsplit("_q", 1)[1]): json.load(open(f)) for f in jt.glob(f"eval_{run}_q*.json")}
    sig_pos = [q for q, e in ev.items() if e["boot_delta_map50_95_ci_low"] > 0]
    sig_neg = [q for q, e in ev.items() if e["boot_delta_map50_95_ci_high"] < 0]
    ded = json.load(open(jt / "eval_jpegtuned_q35_r1_q35.json"))
    ded_tr = json.load(open(jt / "train_jpegtuned_q35_r1.json"))
    dp = json.load(open(jt / "paired_dedicated_vs_mix_q35.json"))      # jpeg_tuned_detector.py compare --q 35
    bb, mix = out["jpeg_tuned"][run + "_best_of_both"], out["jpeg_tuned"][run]
    by = {(x["device"], x["code"]): x for x in bb["codes"]}
    pi = next(d["device"] for d in out["devices"] if d["device"].startswith("Pi"))
    jpi, fpi = by[(pi, "joint_k4_c4_w128_d2")], by[(pi, "learned_k4_c4_w128_d2")]
    jf = by[("Jetson Orin Nano", "joint_k4_c4_w128_d2")]
    q = lambda c: c.replace("jpeg_q", "Q")  # noqa: E731
    f2 = lambda v: f"{v:.2f}"  # noqa: E731
    f3 = lambda v: f"{v:.3f}".replace("-", "\\textminus{}")  # noqa: E731
    n_meas = lambda o: sum(len(x["wins_at_mbps"]) for x in o["codes"] if x["device"] != "sweep")  # noqa: E731
    return {"BeTunedEpochs": str(tr["epochs"]), "BeTunedBestEpoch": str(tr["best_epoch"]),
            "BeTunedSelStart": f3(tr["selection_map50_95_start"]), "BeTunedSelBest": f3(max(tr["selection_map50_95_per_epoch"])),
            "BeTunedGainQten": f3(ev[10]["gain"]), "BeTunedGainQthirtyfive": f3(ev[35]["gain"]),
            "BeTunedGainQninetyfive": f3(ev[95]["gain"]), "BeTunedMapQninetyfive": f3(ev[95]["map50_95"]),
            "BeTunedSigPosMax": f"Q{max(sig_pos)}", "BeTunedSigNegMin": f"Q{min(sig_neg)}",
            "BeTunedQualities": str(len(ev)),
            "BeTunedDedMap": f3(ded["map50_95"]), "BeTunedMixMapQthirtyfive": f3(ev[35]["map50_95"]),
            "BeTunedDedExtra": f3(ded["map50_95"] - ev[35]["map50_95"]), "BeTunedDedBestEpoch": str(ded_tr["best_epoch"]),
            "BeTunedDedLo": f3(dp["boot_delta_map50_95_ci_low"]), "BeTunedDedHi": f3(dp["boot_delta_map50_95_ci_high"]),
            "BeTunedDedSig": "significant" if dp["significant"] else "not significant",
            "BeTunedCells": str(bb["rule_check"]["split_win_cells"]), "BeTunedViolations": str(len(bb["rule_check"]["violations"])),
            "BeTunedCellsDropPct": f"{100 * (1 - bb['rule_check']['split_win_cells'] / out['rule_check']['split_win_cells']):.0f}",
            "BeTunedMeasCells": str(n_meas(bb)), "BeUntunedMeasCells": str(n_meas(out)),
            "BeTunedMixNoQ": str(sum(1 for x in mix["codes"] if x["device"] == pi and x["family"] != "posthoc_split" and x["b_be_mbps"] is None)),
            "BeTunedJointPiQstar": q(jpi["q_star"]), "BeTunedJointPiBe": f2(jpi["b_be_mbps"]), "BeTunedJointPiWin": f2(jpi["max_win_mbps"]),
            "BeTunedFrozenPiQstar": q(fpi["q_star"]), "BeTunedFrozenPiBe": f2(fpi["b_be_mbps"]), "BeTunedFrozenPiWin": f2(fpi["max_win_mbps"]),
            "BeTunedJointFastBe": f2(jf["b_be_mbps"]), "BeTunedJointFastWin": f2(jf["max_win_mbps"]),
            "BeTunedJointShift": f"{100 * (jpi['b_be_mbps'] / fpi['b_be_mbps'] - 1):.0f}",
            "BeTunedPiWinCodes": str(sum(1 for x in bb["codes"] if x["device"] == pi and x["max_win_mbps"]))}


def figure(out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    rows = [r for r in out["codes"] if r["family"] != "posthoc_split" and r["b_be_mbps"] is not None]
    base = lambda c: "learned_" + c[len("joint_"):] if c.startswith("joint_") else c  # noqa: E731
    frozen = sorted({r["code"] for r in rows if not r["code"].startswith("joint")},
                    key=lambda c: min(r["payload_kb"] for r in rows if r["code"] == c))
    codes = frozen + sorted({r["code"] for r in rows if r["code"].startswith("joint")})
    fig, ax = plt.subplots(figsize=(3.45, 3.3))
    cmap = plt.get_cmap("viridis")
    for c in codes:
        rr = sorted([r for r in rows if r["code"] == c], key=lambda r: r["t_full_ms"])
        col = cmap(frozen.index(base(c)) / max(1, len(frozen) - 1) * 0.92)
        joint = c.startswith("joint")
        t = np.array([r["t_full_ms"] for r in rr])
        ax.plot(t, [r["b_be_mbps"] for r in rr], "--" if joint else "-", color=col, lw=1.1 if joint else 0.9,
                label=None if joint else f"{c.split('_')[1]}{' s1' if '_s1_' in c else ''}, {rr[0]['payload_kb'] * 1000 / 1024:.1f} KiB")
        for r in rr:
            if r["max_win_mbps"]:
                ax.plot(r["t_full_ms"], r["max_win_mbps"], "o", ms=3.2, color=col,
                        mfc="none" if joint else col, mew=0.8)
    ax.plot([], [], "--", color="0.3", lw=1.1, label="jointly trained")
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
    ax.legend(fontsize=5.5, ncol=4, loc="upper center", bbox_to_anchor=(0.45, -0.2), frameon=False,
              columnspacing=0.8, handlelength=1.6)
    fig.tight_layout()
    FIG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG)


if __name__ == "__main__":
    main()
