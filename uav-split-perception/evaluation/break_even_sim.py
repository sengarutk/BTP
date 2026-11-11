#!/usr/bin/env python3
"""Does the break-even rule hold in the simulator, not only in the closed-form model it is derived from? (independent
audit of paper 1's v2 drafts, 11 Nov 2026)

evaluation/break_even_rule.py checks the rule with AdaptivePolicy.predict, the same model the proposition comes from,
so its "0 exceptions" only confirms the derivation. Here every option runs in the slotted stream simulator
(simulation/stream_sim.py, fixed mode, one UAV) on fading channel traces, which break the model's assumptions:
the goodput varies slot by slot (shadowing, Rician fading, residual loss), the one-way delay jitters, and frames queue.

Setup
  options     every split code of the rule (post-hoc INT8 splits, the learned codes, the jointly trained codes) and every
              JPEG setting of the rule (break_even_rule.jpeg_grid: the paper's 7 qualities plus the finer grid), with the
              same payloads, accuracies and timings as the rule
  devices     the rule's onboard speeds (4 of the paper's sweep, laptop GPU, Jetson Orin Nano, Pi 5 throttled)
  channel     the trace generator's "moderate" profile (urban, 4 dB shadowing, 12 m/s, Rician K 3 dB) and
              "vehicular_fading" (6 dB shadowing, 22.5 m/s, no line of sight), no blackouts; 3 independent 60-s
              realisations each. A realisation is rescaled in bandwidth so that its mean goodput is each of the rule's
              31 goodputs; every option sees the same realisation (common random numbers)
  utility     on-time detections per second x accuracy / the full model's accuracy, as the rule, mean over realisations
  test        a split code "wins" at a goodput if its simulated utility beats every JPEG setting's; the rule predicts
              that it can only win below its B_be (computed by break_even_rule.analyse from the mean goodput)
  result      (11 Nov 2026) the constant-goodput B_be fails under fading: on fast devices, where the camera rate binds,
              JPEG's larger frames fall behind whenever the goodput dips, so small codes win above B_be. The fading
              version break_even_rule.b_be_fading, which discounts both terms by the trace's own measured spread, is
              checked here too (no parameter is fitted: the spread is the std / mean of the traces)
usage: break_even_sim.py [--workers 3] [--seeds 3] [--duration 60]   -> experiments/results/break_even/sim_check.json
       break_even_sim.py --analyse-only     (re-derives the summary and sim_metrics.tex from the stored per-cell wins)
       break_even_sim.py --tuned jpegtuned_qmix_r1   against the detector fine-tuned on JPEG (at each quality the better
              of tuned and untuned, break_even_rule.tuned_jpeg(best=True)) -> sim_check_tuned.json, sim_tuned_metrics.tex
              (macros BeSimT...)
"""
import argparse
import json
import multiprocessing as mp
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "experiments" / "results" / "break_even"
PROFILES_ = ("moderate", "vehicular_fading")
_STATE = {}


def jpeg_options(base, tuned):
    from evaluation import break_even_rule as b
    jpeg = b.jpeg_grid(base)
    return jpeg if not tuned else b.tuned_jpeg(jpeg, tuned, best=True)


def _setup(seeds, duration, tuned=None, entropy=False):
    import simulation.stream_sim as ss
    from evaluation import break_even_rule as b
    from evaluation.learned_bottleneck_system import VD, family, measured_configs
    from simulation.system_model import host_full_ms
    from simulation.trace_generator import PROFILES, generate_trace
    base = measured_configs()
    jpeg = jpeg_options(base, tuned)
    splits = [c for c in base if c.kind == "split"] + b.learned_and_joint() + (b.entropy_codes() if entropy else [])
    full = next(c for c in base if family(c) == "onboard")
    traces = {}
    for prof in PROFILES_:
        pr = PROFILES[prof]
        for k in range(seeds):
            rec = generate_trace(pr, duration_s=duration, seed=pr.seed * 100_003 + 7_919 * (k + 1))
            g = np.array([r["bandwidth_mbps"] * (1 - r["packet_loss_pct"] / 100) for r in rec])
            traces[(prof, k)] = (rec, float(g.mean()), float(g.std() / g.mean()))
    _STATE.update(ss=ss, jpeg=jpeg, splits=splits, full=full, traces=traces, hfull=host_full_ms(None, VD),
                  cfgs={c.name: c for c in jpeg + splits + [full]}, duration=duration, seeds=seeds)
    current = {}
    ss.generate_trace = lambda *a, **k: current["rec"]       # the simulator draws its trace through this name
    _STATE["current"] = current


def _cell(job):
    dev, t_full, prof, B = job
    from simulation.stream_sim import SimParams, StreamSimulator
    from simulation.system_model import EdgeHardware
    s = _STATE
    hw = EdgeHardware(name=dev, t_full_ms=t_full, host_full_ms=s["hfull"])
    util = {}
    for k in range(s["seeds"]):
        rec, mean_g, _ = s["traces"][(prof, k)]
        f = B / mean_g
        s["current"]["rec"] = [{**r, "bandwidth_mbps": r["bandwidth_mbps"] * f} for r in rec]
        for c in s["jpeg"] + s["splits"]:
            r = StreamSimulator(SimParams(hw, s["cfgs"], profile=prof, duration_s=s["duration"], seed=0,
                                          mode=c.name)).run()
            acc = r["mean_map50_95_on_time"]
            u = 0.0 if not np.isfinite(acc) else r["on_time_fps_per_uav"] * acc / s["full"].map50_95
            util.setdefault(c.name, []).append(u)
    return job, {n: float(np.mean(v)) for n, v in util.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--duration", type=float, default=60.0)
    ap.add_argument("--analyse-only", action="store_true")
    ap.add_argument("--tuned", default=None, help="a jpeg_tuned_detector.py run: JPEG with the tuned detector")
    ap.add_argument("--entropy", action="store_true", help="add the entropy-coded codes (entropy_bottleneck.py)")
    a = ap.parse_args()
    if a.analyse_only:
        out = json.load(open(OUT / f"sim_check{'_entropy' if a.entropy else ''}{'_tuned' if a.tuned else ''}.json"))
        fading(out)
        return
    from evaluation import break_even_rule as b
    from evaluation.learned_bottleneck_system import GOODPUT
    _setup(a.seeds, a.duration, a.tuned, a.entropy)
    jpeg, splits = _STATE["jpeg"], _STATE["splits"]
    rows, *_ = b.analyse(jpeg, [c for c in splits])
    bbe = {(r["device"], r["t_full_ms"], r["code"]): r for r in rows}
    jobs = [(d, t, p, float(B)) for d, t in b.devices() for p in PROFILES_ for B in GOODPUT]
    t0 = time.time()
    with mp.get_context("fork").Pool(a.workers, initializer=_setup, initargs=(a.seeds, a.duration, a.tuned, a.entropy)) as pool:
        res = dict(pool.map(_cell, jobs, chunksize=4))
    out = {"setting": {"profiles": PROFILES_, "seeds": a.seeds, "duration_s": a.duration, "goodputs": len(GOODPUT),
                       "devices": [{"device": d, "t_full_ms": t} for d, t in b.devices()],
                       "jpeg_tuned_run": a.tuned, "entropy_codes": a.entropy, "jpeg_options": [c.name for c in jpeg],
                       "jpeg_map50_95": [c.map50_95 for c in jpeg], "codes": [c.name for c in splits],
                       "trace_rel_std": {f"{p}_{k}": _STATE["traces"][(p, k)][2] for p in PROFILES_ for k in range(a.seeds)},
                       "minutes": (time.time() - t0) / 60},
           "profiles": {}}
    for p in PROFILES_:
        wins, exc, agree, cells, per = 0, [], 0, 0, []
        for d, t in b.devices():
            for c in splits:
                r = bbe[(d, t, c.name)]
                model_win = set(r["wins_at_mbps"])
                sim_win = []
                for B in GOODPUT:
                    u = res[(d, t, p, float(B))]
                    best_q = max(u[q.name] for q in jpeg)
                    w = u[c.name] > best_q * (1 + 1e-9)
                    cells += 1
                    agree += int(w == (float(B) in model_win))
                    if w:
                        sim_win.append(float(B))
                        wins += 1
                        if r["b_be_mbps"] is not None and not float(B) < r["b_be_mbps"]:
                            exc.append({"device": d, "t_full_ms": t, "code": c.name, "goodput": float(B),
                                        "b_be": r["b_be_mbps"], "u_code": u[c.name], "u_best_jpeg": best_q})
                per.append({"device": d, "t_full_ms": t, "code": c.name, "b_be_mbps": r["b_be_mbps"],
                            "model_wins": sorted(model_win), "sim_wins": sim_win})
        out["profiles"][p] = {"split_win_cells": wins, "exceptions": exc, "cells": cells,
                              "model_sim_agreement": agree / cells, "per_code": per}
        print(f"{p}: {wins} winning cells in simulation, {len(exc)} at or above B_be; model and simulation agree on "
              f"who wins in {100 * agree / cells:.1f} % of {cells} cells", flush=True)
    fading(out)


def fading(out):
    """Exceptions of the constant-goodput rule and of its fading version, per profile; macros for the paper."""
    from evaluation import break_even_rule as b
    from evaluation.learned_bottleneck_system import VD, measured_configs
    from simulation.system_model import host_full_ms
    base = measured_configs()
    tuned = out["setting"].get("jpeg_tuned_run")
    jpeg = jpeg_options(base, tuned)
    ent = out["setting"].get("entropy_codes", False)
    splits = {c.name: c for c in [c for c in base if c.kind == "split"] + b.learned_and_joint()
              + (b.entropy_codes() if ent else [])}
    cfgs, hf = list(splits.values()) + jpeg, host_full_ms(None, VD)
    m = {}
    for p, v in out["profiles"].items():
        s = float(np.mean([x for k, x in out["setting"]["trace_rel_std"].items() if k.startswith(p)]))
        exc, slack, fast_only = 0, [], True
        for r in v["per_code"]:
            bb = b.b_be_fading(r["t_full_ms"], splits[r["code"]], jpeg, s, hf, cfgs)
            r["b_be_fading_mbps"], r["b_be_fading_p"] = (bb if bb else (None, None))
            for B in r["sim_wins"]:
                exc += int(bb is not None and not B < bb[0])
            if r["sim_wins"] and bb:
                slack.append(bb[0] / max(r["sim_wins"]) - 1)
        ex = v["exceptions"]
        v["fading_rule"] = {"rel_std": s, "exceptions": exc, "median_slack": float(np.median(slack)) if slack else None}
        v["constant_rule_exception_devices"] = sorted({f"{e['device']} {e['t_full_ms']:.0f} ms" for e in ex})
        v["constant_rule_exception_ratio_max"] = max((e["goodput"] / e["b_be"] for e in ex), default=None)
        v["constant_rule_exception_margin_median"] = (float(np.median([e["u_code"] / e["u_best_jpeg"] - 1 for e in ex]))
                                                      if ex else None)
        v["constant_rule_exception_tfull_max"] = max((e["t_full_ms"] for e in ex), default=None)
        tag = ("E" if ent else "") + ("T" if tuned else "") + {"moderate": "Mod", "vehicular_fading": "Veh"}[p]
        m.update({f"BeSim{tag}Wins": str(v["split_win_cells"]), f"BeSim{tag}Exc": str(len(ex)),
                  f"BeSim{tag}ExcPct": f"{100 * len(ex) / max(1, v['split_win_cells']):.0f}",
                  f"BeSim{tag}Ratio": f"{v['constant_rule_exception_ratio_max']:.1f}" if ex else "none",
                  f"BeSim{tag}Margin": f"{100 * v['constant_rule_exception_margin_median']:.0f}" if ex else "none",
                  f"BeSim{tag}Agree": f"{100 * v['model_sim_agreement']:.0f}",
                  f"BeSim{tag}Spread": f"{s:.2f}", f"BeSim{tag}FadingExc": str(exc),
                  f"BeSim{tag}FadingSlack": f"{100 * v['fading_rule']['median_slack']:.0f}"})
        print(f"{p}: spread {s:.2f}; constant rule {len(ex)} of {v['split_win_cells']} wins at/above B_be (devices "
              f"{v['constant_rule_exception_devices']}); fading rule {exc} exceptions, median slack "
              f"{v['fading_rule']['median_slack']:.2f}", flush=True)
    t = ("E" if ent else "") + ("T" if tuned else "")
    m.update({f"BeSim{t}Seeds": str(out["setting"]["seeds"]), f"BeSim{t}Duration": f"{out['setting']['duration_s']:.0f}",
              f"BeSim{t}ExcTfullMax": f"{max(v['constant_rule_exception_tfull_max'] or 0 for v in out['profiles'].values()):.0f}"})
    OUT.mkdir(parents=True, exist_ok=True)
    sfx = ("_entropy" if ent else "") + ("_tuned" if tuned else "")
    json.dump(out, open(OUT / f"sim_check{sfx}.json", "w"), indent=1)
    (OUT / f"sim{sfx}_metrics.tex").write_text("% Generated by evaluation/break_even_sim.py -- do not edit.\n"
                                         + "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in m.items()))


if __name__ == "__main__":
    main()
