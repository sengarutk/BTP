#!/usr/bin/env python3
"""Bootstrap intervals on the break-even goodput B_be (paper 1, roadmap P1-11, 11 Nov 2026).

B_be (Proposition prop:be-family, break_even_rule.analyse) depends on measured accuracies: the code's A_k and, through
the choice of the matching JPEG setting q*, the JPEG curve. Both are estimates on the 548 VisDrone-DET val frames.
Here each bootstrap resample draws the images once and recomputes the mAP of every option on that same resample (so
the options stay paired, as in detection_eval.paired_bootstrap), then recomputes q* and B_be for every code and device.
Payloads and timings are held at their measured means (their sampling error is far smaller: payloads are means over
548 frames, timings medians of 50 runs).

Before any resample the script checks that its B_be equals break_even_rule.analyse's value for every row (same
formula, same inputs), so the intervals belong to the published numbers.
JPEG detectors: "untuned" (the frozen detector) and "best_of_both" (per quality the better of the untuned and the
JPEG-tuned detector, chosen on the point estimate, as in break_even_rule.tuned_jpeg).
usage: break_even_ci.py [--n-boot 200]   -> experiments/results/break_even/b_be_ci.json, b_be_ci_metrics.tex
"""
import argparse
import json
import math
import pickle
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from evaluation import break_even_rule as b  # noqa: E402
from evaluation.detection_eval import map_from_stats  # noqa: E402
from evaluation.learned_bottleneck_system import VD, family, measured_configs  # noqa: E402
from simulation.system_model import AdaptivePolicy, EdgeHardware, host_full_ms  # noqa: E402

CACHE = REPO / "experiments" / "cache" / "val_stats" / "visdrone_val"
OUT = REPO / "experiments" / "results" / "break_even"


def stats_file(c):
    """The cached per-image statistics of an option (the evaluation that produced its mAP)."""
    n = c.name
    if n.startswith("jpeg_q"):
        return CACHE / f"lb_jpeg_q{n[len('jpeg_q'):]}_yolov8s_visdrone.pkl"
    if n.startswith("learned_"):
        return CACHE / f"lb_yolov8s_visdrone_{n[len('learned_'):]}.pkl"
    if n.startswith("joint_"):
        return CACHE / f"jb_yolov8s_visdrone_{n[len('joint_'):]}.pkl"
    if n.startswith("ec_"):
        return CACHE / f"ec_yolov8s_visdrone_{n}.pkl"
    raise KeyError(n)


def tuned_file(q):
    return CACHE / f"jt_jpegtuned_qmix_r1_q{q}.pkl"


def b_be(pol, e, k, jpeg):
    """break_even_rule.analyse's B_be and q* for code k (same formula)."""
    def R(c):
        slack = pol.deadline_ms - e[c.name] - pol.delay_ms - c.cloud_ms
        return math.inf if slack <= 0 else c.payload_bytes * 8 / 1e3 / slack
    srel = pol.w.min_rel_std
    m_k = max(e[k.name], 1000.0 / pol.camera_fps)
    cand = {q.name: max(q.payload_bytes * 8 / 1e3 / m_k, R(q) / (1 - b.Z_P * srel))
            for q in jpeg if b.P_ON * q.map50_95 >= k.map50_95 and e[q.name] <= m_k}
    if not cand:
        return None, None
    qs = min(cand, key=cand.get)
    return cand[qs], qs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-boot", type=int, default=200)
    a = ap.parse_args()
    base = measured_configs()
    jpeg = b.jpeg_grid(base)
    codes = [c for c in b.learned_and_joint() + b.entropy_codes()]
    best = b.tuned_jpeg(jpeg, b.TUNED_RUNS[0], best=True)
    tuned_q = {c.name for c, u in zip(best, jpeg) if c.map50_95 != u.map50_95}   # qualities where tuned is used
    stats = {c.name: pickle.load(open(stats_file(c), "rb")) for c in jpeg + codes}
    tstats = {c.name: pickle.load(open(tuned_file(c.name[len("jpeg_q"):]), "rb")) for c in jpeg if c.name in tuned_q}
    point = {c.name: c.map50_95 for c in jpeg + codes}
    point_t = {c.name: c.map50_95 for c in best if c.name in tuned_q}
    for n, s in stats.items():               # the cache reproduces every option's published mAP
        assert abs(map_from_stats(s["stats"])[1] - point[n]) < 1e-6, (n, point[n])
    for n, s in tstats.items():
        assert abs(map_from_stats(s["stats"])[1] - point_t[n]) < 1e-6, (n, point_t[n])
    n_img = next(iter(stats.values()))["num_images"]
    assert all(s["num_images"] == n_img for s in list(stats.values()) + list(tstats.values()))
    hf = host_full_ms(None, VD)
    others = [c for c in base if family(c) != "image"] + codes
    devs = [(d, t) for d, t in b.devices() if d != "sweep"]
    setups = {}
    for d, t in devs:
        pol = AdaptivePolicy(others + jpeg, EdgeHardware(name=d, t_full_ms=t, host_full_ms=hf))
        setups[(d, t)] = (pol, {c.name: pol.hw.onboard_ms(c) for c in others + jpeg})
    # consistency with break_even_rule.analyse on the point estimates
    rows = {}
    for key, jp in (("untuned", jpeg), ("best_of_both", best)):
        ar, *_ = b.analyse(jp, others)
        ref = {(r["device"], r["code"]): r for r in ar}
        for (d, t), (pol, e) in setups.items():
            for k in codes:
                v, qs = b_be(pol, e, k, jp)
                r = ref[(d, k.name)]
                assert (v is None and r["b_be_mbps"] is None) or abs(v - r["b_be_mbps"]) < 1e-9, (key, d, k.name, v, r)
                rows[(key, d, k.name)] = {"b_be": v, "q_star": qs, "boot": []}
    print(f"consistency: {len(rows)} code-device-detector rows equal break_even_rule.analyse", flush=True)
    for r_ in range(a.n_boot):
        idx = np.random.default_rng(r_).integers(0, n_img, n_img)
        m = {n: map_from_stats(s["stats"], idx)[1] for n, s in stats.items()}
        mt = {n: map_from_stats(s["stats"], idx)[1] for n, s in tstats.items()}
        jp_u = [replace(c, map50_95=m[c.name]) for c in jpeg]
        jp_b = [replace(c, map50_95=max(m[c.name], mt[c.name]) if c.name in mt else m[c.name]) for c in jpeg]
        ks = [replace(k, map50_95=m[k.name]) for k in codes]
        for key, jp in (("untuned", jp_u), ("best_of_both", jp_b)):
            for (d, t), (pol, e) in setups.items():
                for k in ks:
                    v, qs = b_be(pol, e, k, jp)
                    rows[(key, d, k.name)]["boot"].append((v, qs))
        if (r_ + 1) % 50 == 0:
            print(f"{r_ + 1} resamples", flush=True)
    out = []
    for (key, d, kn), r in rows.items():
        vals = [v for v, _ in r["boot"] if v is not None]
        qcount = {}
        for _, qs in r["boot"]:
            qcount[qs] = qcount.get(qs, 0) + 1
        out.append({"detector": key, "device": d, "code": kn, "b_be_mbps": r["b_be"], "q_star": r["q_star"],
                    "ci_low": float(np.percentile(vals, 2.5)) if vals else None,
                    "ci_high": float(np.percentile(vals, 97.5)) if vals else None,
                    "share_defined": len(vals) / a.n_boot, "q_star_share": r["boot"] and
                    max(qcount.values()) / a.n_boot, "q_star_counts": {str(k): v for k, v in qcount.items()}})
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump({"n_boot": a.n_boot, "images": n_img, "method": __doc__.split("\n\n")[1], "rows": out},
              open(OUT / "b_be_ci.json", "w"), indent=1)
    by = {(r["detector"], r["device"], r["code"]): r for r in out}
    pi = next(d for d, _ in devs if d.startswith("Pi"))
    m_ = {}
    for tag, key in (("", "untuned"), ("Tuned", "best_of_both")):
        for name, dev, code in (("JointPi", pi, "joint_k4_c4_w128_d2"), ("FrozenPi", pi, "learned_k4_c4_w128_d2"),
                                ("JointFast", "Jetson Orin Nano", "joint_k4_c4_w128_d2"),
                                ("EcPairFast", "Jetson Orin Nano", "ec_k4_c32_l0.03")):
            r = by[(key, dev, code)]
            m_[f"BeCi{tag}{name}Lo"] = f"{r['ci_low']:.2f}"
            m_[f"BeCi{tag}{name}Hi"] = f"{r['ci_high']:.2f}"
            m_[f"BeCi{tag}{name}QShare"] = f"{100 * r['q_star_share']:.0f}"
    widths = [(r["ci_high"] - r["ci_low"]) / r["b_be_mbps"] for r in out if r["b_be_mbps"] and r["ci_low"] is not None]
    m_["BeCiBoot"] = str(a.n_boot)
    m_["BeCiRelWidthMedian"] = f"{100 * float(np.median(widths)):.0f}"
    m_["BeCiRelWidthMax"] = f"{100 * float(np.max(widths)):.0f}"
    (OUT / "b_be_ci_metrics.tex").write_text("% Generated by evaluation/break_even_ci.py -- do not edit.\n"
                                            + "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in m_.items()))
    for k, v in m_.items():
        print(k, v)


if __name__ == "__main__":
    main()
