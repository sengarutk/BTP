#!/usr/bin/env python3
"""Macros, tables and figures of the generalization study (Section "Generalization" of the paper).

Reads only experiments/results/generalization/*.csv (plus the main codec table for reference
curves). Outputs:
  paper/generated_tables/gen_metrics.tex      \\newcommand per number used in the text
  paper/generated_tables/table_gen_models.tex detectors x (payload, ratio to JPEG, exactness, accuracy)
  paper/generated_tables/table_gen_space.tex  scenario parameter space and rank correlations
  paper/figures/gen_bits.pdf, gen_models.pdf, gen_regimes.pdf
  docs/claims_generalization.md                macro -> value -> source ledger
"""

import csv
import math
from pathlib import Path
from typing import Dict, List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import NullFormatter

from evaluation.make_figures import C, save
from evaluation.make_tables import Macros, num

REPO_ROOT = Path(__file__).resolve().parent.parent
GEN = REPO_ROOT / "experiments" / "results" / "generalization"
RESULTS = REPO_ROOT / "experiments" / "results"
TABLES = REPO_ROOT / "paper" / "generated_tables"
LEDGER = REPO_ROOT / "docs" / "claims_generalization.md"

WORDS = {2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight"}
MODEL_LABEL = {"yolov5nu": "YOLOv5n", "yolov5su": "YOLOv5s", "yolov5mu": "YOLOv5m", "yolov8n": "YOLOv8n",
               "yolov8s": "YOLOv8s", "yolov8m": "YOLOv8m", "yolov8l": "YOLOv8l", "yolov8x": "YOLOv8x",
               "yolov9t": "YOLOv9t", "yolov9s": "YOLOv9s", "yolov9m": "YOLOv9m", "yolov10n": "YOLOv10n",
               "yolov10s": "YOLOv10s", "yolov10m": "YOLOv10m", "yolo11n": "YOLO11n", "yolo11s": "YOLO11s",
               "yolo11m": "YOLO11m", "yolo11l": "YOLO11l", "yolo11x": "YOLO11x"}
TFULL_RANGE_MS = (10, 1000)  # as sampled in evaluation/gen_scenarios.py (_logu(rng, 10, 1000)); checked in scenarios_part
SPACE = [  # (column, label, range text) -- ranges as sampled in evaluation/gen_scenarios.py
    ("t_full_ms", "Onboard full-model latency $t_{full}$", "10--1000 ms (log)"),
    ("deadline_ms", "Deadline $D$", "100--1000 ms (log)"),
    ("camera_fps", "Camera rate $F$", "10, 15, 24, 30, 60 FPS"),
    ("mean_sinr_db", "Mean SINR", "$-$5--20 dB"),
    ("bandwidth_mhz", "Uplink bandwidth", "5--100 MHz (log)"),
    ("shadow_sigma_db", "Shadowing $\\sigma_{sh}$", "2--8 dB"),
    ("d_corr_m", "Decorrelation distance", "10--100 m"),
    ("speed_mps", "UAV speed", "0--30 m/s"),
    ("rician_k_db", "Rician $K$", "$-$5--15 dB"),
    ("base_delay_ms", "One-way delay", "5--100 ms (log)"),
    ("n_blackouts", "Blackouts per minute", "0--3"),
    ("blackout_s", "Blackout length", "1--5 s"),
    ("server_scale", "Server time factor", "0.5--4$\\times$ (log)"),
    ("p_compute_w", "Compute power (busy)", "5--30 W"),
    ("p_idle_w", "Compute power (idle)", "1--4 W"),
    ("p_tx_w", "Modem transmit power", "1.5--6 W"),
    ("p_rx_w", "Modem idle power", "0.5--1.5 W"),
    ("mass_kg", "Take-off mass", "0.25--5 kg (log)"),
    ("avionics_w", "Avionics power", "3--20 W"),
    ("hysteresis", "Policy hysteresis", "0--0.2"),
    ("min_rel_std", "Policy uncertainty floor", "0.05--0.3"),
    ("est_tau_ms", "Estimator time constant", "50--1000 ms (log)"),
]
MAJOR = ("t_full_ms", "deadline_ms", "camera_fps", "mean_sinr_db", "bandwidth_mhz")


def read(path: Path) -> List[Dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def pct(x: float, digits: int = 1) -> str:
    return f"{100 * x:.{digits}f}"


def pts(x: float, digits: int = 2) -> str:
    v = 100 * x
    return f"{v:+.{digits}f}".replace("-", "$-$") if abs(v) >= 0.5 * 10 ** -digits else f"{0:.{digits}f}"


def ci_pts(r: Dict[str, str]) -> str:
    return (f"{pts(float(r['delta_map50_95']))} [{pts(float(r['delta_map50_95_ci_low']))}, "
            f"{pts(float(r['delta_map50_95_ci_high']))}]")


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    rx, ry = np.argsort(np.argsort(x)), np.argsort(np.argsort(y))
    return float(np.corrcoef(rx, ry)[0, 1])


def rho_tex(r: float) -> str:
    return f"{r:+.2f}".replace("-", "$-$")


# ---------------------------------------------------------------- bit width
def bits_part(m: Macros, acc: List[Dict[str, str]]) -> None:
    src = "experiments/results/generalization/accuracy.csv"
    rows = {int(r["setting"]): r for r in acc if r["model"] == "yolov8s" and int(r["imgsz"]) == 640
            and r["data"] == "coco_val2017" and r["kind"] == "split" and int(r["cut"]) == 4}
    jpeg = {int(r["setting"]): r for r in acc if r["model"] == "yolov8s" and int(r["imgsz"]) == 640
            and r["data"] == "coco_val2017" and r["kind"] == "jpeg"}
    for b, r in rows.items():
        m.add(f"GenBits{WORDS[b]}KiB", num(float(r["wire_kib"])), src)
        m.add(f"GenBits{WORDS[b]}Delta", ci_pts(r), src)
    for q, r in jpeg.items():
        word = {75: "SeventyFive", 90: "Ninety", 95: "NinetyFive"}[q]
        m.add(f"GenJpeg{word}KiB", num(float(r["wire_kib"])), src)
        m.add(f"GenJpeg{word}Delta", ci_pts(r), src)

    # 6 bits reaches about the accuracy of JPEG Q95; how much larger is it?
    m.add("GenBitsSixRatioJpegNinetyFive", f"{float(rows[6]['wire_kib']) / float(jpeg[95]['wire_kib']):.1f}", src)
    # At equal size: INT4 vs JPEG Q75
    m.add("GenFourBitVsJpegSeventyFiveGap",
          f"{100 * (float(jpeg[75]['delta_map50_95']) - float(rows[4]['delta_map50_95'])):.1f}", src)

    fig, ax = plt.subplots(figsize=(3.45, 2.3))
    codec = read(RESULTS / "codec_baselines.csv")
    for name, col in (("JPEG", C["jpeg"]), ("WebP", C["webp"]), ("H.264", C["h264"])):
        pts_ = sorted((float(r["wire_kib"]), 100 * float(r["delta_map50_95"])) for r in codec if r["codec_name"] == name)
        ax.plot(*zip(*pts_), marker="o", color=col, label=f"{name} (image)")
    sb = sorted((float(r["wire_kib"]), 100 * float(r["delta_map50_95"]), b) for b, r in rows.items() if b >= 3)
    ax.plot([s[0] for s in sb], [s[1] for s in sb], marker="s", color=C["split"], label="Split $k_4$, $n$-bit + zstd")
    for x, y, b in sb:
        ax.annotate(f"{b}b", (x, y), textcoords="offset points", xytext=(4, -8), fontsize=6, color=C["split"])
    ax.set_xscale("log")
    ax.set_xticks([10, 30, 100, 300])
    ax.set_xticklabels(["10", "30", "100", "300"])
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_xlabel("Wire size per frame (KiB, log)")
    ax.set_ylabel(r"$\Delta$mAP@[.5:.95] (points)")
    ax.set_ylim(-25, 1)
    ax.legend(loc="lower right", frameon=False)
    save(fig, "gen_bits")


# ---------------------------------------------------------------- detectors / resolution / imagery
def models_part(m: Macros, acc: List[Dict[str, str]]) -> None:
    src = "experiments/results/generalization/model_summary.csv"
    summ = read(GEN / "model_summary.csv")
    coco640 = {r["model"]: r for r in summ if r["images"] == "coco" and int(r["imgsz"]) == 640}
    models = [k for k in MODEL_LABEL if k in coco640]
    ratios = {k: float(coco640[k]["ratio_jpeg_q90"]) for k in models}
    exact = [k for k in models if coco640[k]["cuts_exact"] == coco640[k]["cuts_total"]]
    m.add("GenNModels", str(len(models)), src)
    m.add("GenNExactModels", str(len(exact)), src)
    m.add("GenNFamilies", str(len({MODEL_LABEL[k][:6] for k in models})), src)
    m.add("GenTotalCutsChecked", num(sum(int(coco640[k]["cuts_total"]) for k in models), 0), src)
    kstar = {k: int(coco640[k]["bottleneck_cut"]) for k in models}
    odd = [k for k in models if kstar[k] not in (3, 4)]
    m.add("GenNStrideEightBottleneck", str(len(models) - len(odd)), src)
    m.add("GenOddBottleneck", ", ".join(f"{MODEL_LABEL[k]} ($k^\\ast={kstar[k]}$)" for k in odd) or "none", src)
    m.add("GenRatioMin", f"{min(ratios.values()):.1f}", src)
    m.add("GenRatioMax", f"{max(ratios.values()):.1f}", src)
    m.add("GenRatioMinModel", MODEL_LABEL[min(ratios, key=ratios.get)], src)
    m.add("GenRatioMaxModel", MODEL_LABEL[max(ratios, key=ratios.get)], src)
    r95 = {k: float(coco640[k]["ratio_jpeg_q95"]) for k in models}
    m.add("GenRatioNinetyFiveMin", f"{min(r95.values()):.1f}", src)
    m.add("GenNModelsBelowJpeg", str(sum(v < 1 for v in ratios.values())), src)
    m.add("GenSurveyJpegNinetyKiB", num(float(coco640[models[0]]["jpeg_q90_kib"])), src)
    m.add("GenZstdNineteenGainMax", pct(max(1 - float(coco640[k]["int8_zstd19_kib"]) / float(coco640[k]["int8_zstd_kib"])
                                            for k in models)), src)

    # Accuracy of the models study (bottleneck cut at 8/6/4 bits, JPEG Q90) on COCO val2017.
    acc_m = [r for r in acc if int(r["imgsz"]) == 640 and r["data"] == "coco_val2017"]
    def get(model, kind, setting):
        for r in acc_m:
            if r["model"] == model and r["kind"] == kind and int(r["setting"]) == setting:
                return r
        return None
    acc_models = [k for k in models if get(k, "split", 8) and get(k, "jpeg", 90)]
    d8 = [float(get(k, "split", 8)["delta_map50_95"]) for k in acc_models]
    d6 = [float(get(k, "split", 6)["delta_map50_95"]) for k in acc_models if get(k, "split", 6)]
    d4 = [float(get(k, "split", 4)["delta_map50_95"]) for k in acc_models if get(k, "split", 4)]
    dj = [float(get(k, "jpeg", 90)["delta_map50_95"]) for k in acc_models]
    sig8 = sum(float(get(k, "split", 8)["delta_map50_95_ci_high"]) < 0 for k in acc_models)
    a_src = "experiments/results/generalization/accuracy.csv"
    m.add("GenNAccModels", str(len(acc_models)), a_src)
    m.add("GenIntEightWorst", pts(min(d8)), a_src)
    m.add("GenIntEightSignificant", str(sig8), a_src)
    m.add("GenIntSixRange", f"{pts(max(d6))} to {pts(min(d6))}", a_src)
    m.add("GenIntFourRange", f"{pts(max(d4))} to {pts(min(d4))}", a_src)
    m.add("GenJpegNinetyRange", f"{pts(max(dj))} to {pts(min(dj))}", a_src)
    wr = [float(get(k, "split", 8)["wire_kib"]) / float(get(k, "jpeg", 90)["wire_kib"]) for k in acc_models]
    m.add("GenAccWireRatioRange", f"{min(wr):.0f}--{max(wr):.0f}", a_src)

    lines = ["\\begin{tabular}{@{}lrrrrrrrr@{}}", "\\toprule",
             "Model & GFLOPs & $k^*$ & Onboard & INT8+zstd & $\\times$JPEG & Exact & "
             "\\multicolumn{2}{c}{$\\Delta$mAP (points)} \\\\",
             " & & & FLOPs (\\%) & (KiB) & Q90 & cuts & INT8 at $k^*$ & JPEG Q90 \\\\ \\midrule"]
    for k in models:
        r = coco640[k]
        a8, aj = get(k, "split", 8), get(k, "jpeg", 90)
        lines.append(f"{MODEL_LABEL[k]} & {float(r['gflops']):.1f} & {r['bottleneck_cut']} & "
                     f"{100 * float(r['edge_flop_frac']):.1f} & {num(float(r['int8_zstd_kib']))} & "
                     f"{float(r['ratio_jpeg_q90']):.1f} & {r['cuts_exact']}/{r['cuts_total']} & "
                     f"{pts(float(a8['delta_map50_95'])) if a8 else '--'} & "
                     f"{pts(float(aj['delta_map50_95'])) if aj else '--'} \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    (TABLES / "table_gen_models.tex").write_text("% Generated by evaluation/make_generalization.py -- do not edit.\n"
                                                 + "\n".join(lines) + "\n", encoding="utf-8")

    # Resolution and imagery (YOLOv8s): payload ratio to JPEG Q90 per input size and image set.
    res = [(int(r["imgsz"]), r) for r in summ if r["model"] == "yolov8s"]
    by = {(r["images"], s): float(r["ratio_jpeg_q90"]) for s, r in res}
    jk = {(r["images"], s): float(r["jpeg_q90_kib"]) for s, r in res}
    coco_sizes = sorted(s for (i, s) in by if i == "coco")
    lo, hi = coco_sizes[0], coco_sizes[-1]
    m.add("GenResSizes", ", ".join(str(s) for s in coco_sizes), src)
    m.add("GenResSizeSmall", str(lo), src)
    m.add("GenResSizeLarge", str(hi), src)
    m.add("GenResRatioSmall", f"{by[('coco', lo)]:.1f}", src)
    m.add("GenResRatioLarge", f"{by[('coco', hi)]:.1f}", src)
    m.add("GenResRatioSixForty", f"{by[('coco', 640)]:.1f}", src)
    m.add("GenResMinRatioAllModels", f"{min(float(r['ratio_jpeg_q90']) for r in summ):.1f}", src)
    m.add("GenNSurveyRows", str(len(summ)), src)
    # Onboard work at the bottleneck cut (FLOP fraction + quantize/serialize time, both relative to the full model)
    # against the image's encoding time: the onboard-time condition of prop:dominance, per survey row.
    onb = [r for r in summ if float(r["edge_flop_frac"]) + float(r["rho_split"]) > float(r["rho_jpeg"])]
    m.add("GenOnboardFavoursImageRows", str(len(onb)), src,
          "survey rows (model x input size x imagery) where edge_flop_frac + rho_split > rho_jpeg at the bottleneck cut")
    for size, word in ((640, "Low"), (1280, "High")):
        if ("visdrone", size) in by:
            m.add(f"GenAerialRatio{word}", f"{by[('visdrone', size)]:.1f}", src)
            m.add(f"GenAerialJpegKiB{word}", num(jk[("visdrone", size)]), src)
            m.add(f"GenCocoJpegKiB{word}", num(jk[("coco", size)]), src)
            m.add(f"GenCocoRatio{word}", f"{by[('coco', size)]:.1f}", src)

    # Aerial accuracy (VisDrone, COCO-mapped): INT8 split vs JPEG at equal settings.
    aer = [r for r in acc if r["data"] == "visdrone_val"]
    if aer:
        def ag(model, s, kind, setting):
            return next((r for r in aer if r["model"] == model and int(r["imgsz"]) == s and r["kind"] == kind
                         and int(r["setting"]) == setting), None)
        n_aer = {int(r["num_images"]) for r in aer}
        assert len(n_aer) == 1, "every aerial accuracy row must use the same VisDrone images"
        m.add("GenAerialValImages", f"{n_aer.pop():,}", a_src,
              "num_images of the visdrone_val rows of accuracy.csv (VisDrone2019-DET val)")
        for model, tag in (("yolov8s", "VEightS"), ("yolo11s", "ElevenS")):
            for s, stag in ((640, "Low"), (1280, "High")):
                base = ag(model, s, "full", 32)
                if base is None:
                    continue
                m.add(f"GenAerialBase{tag}{stag}", f"{100 * float(base['map50_95']):.1f}", a_src)
                for kind, setting, name in (("split", 8, "IntEight"), ("split", 6, "IntSix"), ("split", 4, "IntFour"),
                                            ("jpeg", 90, "JpegNinety"), ("jpeg", 75, "JpegSeventyFive"),
                                            ("jpeg", 95, "JpegNinetyFive")):
                    r = ag(model, s, kind, setting)
                    if r:
                        m.add(f"GenAerial{name}{tag}{stag}", ci_pts(r), a_src)
                        m.add(f"GenAerial{name}{tag}{stag}KiB", num(float(r["wire_kib"])), a_src)

    # Resolution accuracy (YOLOv8s on COCO)
    for s in (320, 480, 960):
        rr = {(r["kind"], int(r["setting"])): r for r in acc if r["model"] == "yolov8s" and int(r["imgsz"]) == s
              and r["data"] == "coco_val2017"}
        word = {320: "ThreeTwenty", 480: "FourEighty", 960: "NineSixty"}[s]
        for (kind, setting), name in ((("split", 8), "IntEight"), (("split", 6), "IntSix"), (("jpeg", 90), "JpegNinety")):
            if (kind, setting) in rr:
                m.add(f"GenRes{word}{name}", ci_pts(rr[(kind, setting)]), a_src)
                m.add(f"GenRes{word}{name}KiB", num(float(rr[(kind, setting)]["wire_kib"])), a_src)

    # Figure: payload ratio to JPEG Q90 per model (bars) and per resolution/imagery (inset panel).
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.1, 2.1), gridspec_kw={"width_ratios": [2.3, 1]})
    xs = np.arange(len(models))
    a1.bar(xs, [ratios[k] for k in models], color=C["split"], label="vs JPEG Q90")
    a1.scatter(xs, [r95[k] for k in models], color=C["jpeg"], zorder=3, s=10, label="vs JPEG Q95")
    a1.axhline(1.0, color="k", lw=0.8, ls="--")
    a1.set_xticks(xs)
    a1.set_xticklabels([MODEL_LABEL[k] for k in models], rotation=60, ha="right")
    a1.set_ylabel("Smallest split payload /\nJPEG size")
    a1.legend(frameon=False, loc="upper left")
    for images, col, lab in (("coco", C["split"], "COCO"), ("visdrone", C["webp"], "VisDrone (aerial)")):
        pts_ = sorted((s, by[(i, s)]) for (i, s) in by if i == images)
        if pts_:
            a2.plot(*zip(*pts_), marker="o", color=col, label=lab)
    a2.axhline(1.0, color="k", lw=0.8, ls="--")
    a2.set_xlabel("Input size (px)")
    a2.set_ylabel("YOLOv8s ratio to JPEG Q90")
    a2.set_ylim(0, max(by.values()) * 1.15)
    a2.legend(frameon=False, loc="upper left")
    save(fig, "gen_models")


# ---------------------------------------------------------------- Monte Carlo
def scenarios_part(m: Macros) -> None:
    src = "experiments/results/generalization/scenarios.csv"
    rows = read(GEN / "scenarios.csv")
    f = lambda r, k: float(r[k])  # noqa: E731
    single = [r for r in rows if r["swarm"] == "False"]
    swarm = [r for r in rows if r["swarm"] == "True"]
    tf = [f(r, "t_full_ms") for r in rows]
    assert TFULL_RANGE_MS[0] <= min(tf) and max(tf) <= TFULL_RANGE_MS[1], "t_full outside the documented range"
    assert SPACE[0][2] == f"{TFULL_RANGE_MS[0]}--{TFULL_RANGE_MS[1]} ms (log)", "Table V and TFULL_RANGE_MS disagree"
    m.add("GenTfullMinMs", f"{TFULL_RANGE_MS[0]:g}", "evaluation/gen_scenarios.py",
          "design constant: lower end of the log-uniform t_full range of the Monte Carlo (sampled values checked)")
    m.add("GenTfullMaxMs", f"{TFULL_RANGE_MS[1]:g}", "evaluation/gen_scenarios.py",
          "design constant: upper end of the log-uniform t_full range of the Monte Carlo (sampled values checked)")
    m.add("GenNScenarios", num(len(single), 0), src)
    m.add("GenNSwarmScenarios", num(len(swarm), 0), src)
    from evaluation.gen_scenarios import sample
    m.add("GenNVariables", str(len(sample(np.random.default_rng(0), swarm=True))), "evaluation/gen_scenarios.py")
    single_vars = [k for k, v in sample(np.random.default_rng(0), swarm=False).items() if k != "n_uavs" and v is not None]
    m_single_vars = m.add("GenNVariablesSingle", str(len(single_vars)), "evaluation/gen_scenarios.py")

    def stats(S, tag):
        feas = [r for r in S if f(r, "u_oracle") > 0]
        us = np.array([f(r, "u_best_split") for r in feas]); uc = np.array([f(r, "u_best_codec") for r in feas])
        uo = np.array([f(r, "u_onboard") for r in feas]); ur = np.array([f(r, "u_oracle") for r in feas])
        m.add(f"Gen{tag}Feasible", num(len(feas), 0), src)
        m.add(f"Gen{tag}CodecBeatsSplitPct", pct(np.mean(uc >= us - 1e-9)), src)
        wins = us > uc + 1e-9
        m.add(f"Gen{tag}SplitWinsN", str(int(wins.sum())), src)
        gain = (us[wins] - uc[wins]) / uc[wins] if wins.any() else np.array([0.0])
        m.add(f"Gen{tag}MaxSplitGainPct", f"{100 * gain.max():.2f}", src)
        kinds = [("onboard" if r["oracle"].startswith("full") else "split" if r["oracle"].startswith("k") else "codec")
                 for r in feas]
        for k, name in (("onboard", "Onboard"), ("split", "Split"), ("codec", "Codec")):
            m.add(f"Gen{tag}Oracle{name}Pct", pct(kinds.count(k) / len(kinds)), src)
        m.add(f"Gen{tag}SplitBeatsOnboardPct", pct(np.mean(us > uo + 1e-9)), src)
        for a, name in (("u_adaptive_all", "AdaptiveAll"), ("u_adaptive_split", "AdaptiveSplit")):
            x = np.array([f(r, a) for r in feas]) / ur
            m.add(f"Gen{tag}{name}Median", f"{np.median(x):.2f}", src)
            m.add(f"Gen{tag}{name}PFive", f"{np.percentile(x, 5):.2f}", src)
            m.add(f"Gen{tag}{name}NinetyPct", pct(np.mean(x >= 0.9)), src)
        best_so = np.maximum(us, uo)
        x = np.array([f(r, "u_adaptive_split") for r in feas]) / np.maximum(best_so, 1e-9)
        m.add(f"Gen{tag}AdaptiveSplitVsOwnMedian", f"{np.median(x):.2f}", src)
        m.add(f"Gen{tag}DominanceHoldsPct", pct(np.mean([r["prop1_codec_dominates_all_splits"] == "True" for r in feas])), src)
        be = np.array([f(r, "mean_goodput_mbps") > f(r, "break_even_mbps") for r in feas])
        m.add(f"Gen{tag}BreakEvenAccPct", pct(np.mean(be == (us > uo + 1e-9))), src)
        kind = lambda n: "onboard" if n.startswith("full") else "split" if n.startswith("k") else "none" if n == "none" else "codec"  # noqa: E731
        m.add(f"Gen{tag}AnalyticAgreePct", pct(np.mean([kind(r["analytic_winner"]) == kind(r["oracle"]) for r in feas])), src)
        es = np.array([f(r, "endurance_spread") for r in S]); eb = np.array([f(r, "endurance_bound") for r in S])
        m.add(f"Gen{tag}EnduranceBoundPct", pct(np.mean(es <= eb + 1e-9)), src)
        m.add(f"Gen{tag}EnduranceSpreadMedianPct", pct(np.median(es)), src)
        m.add(f"Gen{tag}EnduranceSpreadMaxPct", pct(es.max(), 0), src)
        mass = np.array([f(r, "mass_kg") for r in S])
        m.add(f"Gen{tag}EnduranceLightMedianPct", pct(np.median(es[mass < 0.5])), src)
        m.add(f"Gen{tag}EnduranceHeavyMedianPct", pct(np.median(es[mass > 2.0])), src)
        return feas, us, uc, uo

    feas, us, uc, uo = stats(single, "")
    # Bound check: split's utility ratio over the best codec never exceeds their accuracy ratio.
    wins = [r for r, a, b in zip(feas, us, uc) if a > b + 1e-9]
    if wins:
        ratio = max(f(r, "u_best_split") / f(r, "u_best_codec") / f(r, "acc_ratio_split_codec") for r in wins)
        m.add("GenBoundRatioMax", f"{ratio:.3f}", src)
        m.add("GenSplitWinMinGoodput", f"{min(f(r, 'mean_goodput_mbps') for r in wins):.0f}", src)
        m.add("GenSplitWinMaxTfull", f"{max(f(r, 't_full_ms') for r in wins):.0f}", src)
    stats(swarm, "Swarm")

    # Adaptive policy (all options) against fixed JPEG Q90 in the same random systems.
    per: Dict[str, Dict[str, float]] = {}
    for r in read(GEN / "scenario_strategies.csv"):
        per.setdefault(r["scenario"], {})[r["strategy"]] = float(r["utility"])
    pairs = [(v["adaptive_all"], v["jpeg_q90"]) for v in per.values() if "jpeg_q90" in v and "adaptive_all" in v]
    below = [(a, j) for a, j in pairs if a < j - 1e-9]
    m.add("GenAdaptiveBelowJpegN", num(len(below), 0), "experiments/results/generalization/scenario_strategies.csv")
    m.add("GenAdaptiveScenariosN", num(len(pairs), 0), "experiments/results/generalization/scenario_strategies.csv")
    worst = min((a / j for a, j in below if j > 0), default=1.0)
    m.add("GenAdaptiveVsJpegWorstPct", f"{100 * (1 - worst):.0f}", "experiments/results/generalization/scenario_strategies.csv")

    # Rank correlations (single-UAV feasible scenarios)
    eps = 0.05
    y_so = np.log((us + eps) / (uo + eps))
    y_cs = np.log((uc + eps) / (us + eps))
    lines = ["\\begin{tabular}{@{}llrr@{}}", "\\toprule",
             "Variable & Range sampled & $r_s$(split/onboard) & $r_s$(codec/split) \\\\ \\midrule"]
    rhos = {}
    for col, label, rng in SPACE:
        x = np.array([f(r, col) for r in feas])
        a, b = spearman(x, y_so), spearman(x, y_cs)
        rhos[col] = (a, b)
        lines.append(f"{label} & {rng} & {rho_tex(a)} & {rho_tex(b)} \\\\")
    x = np.array([f(r, "mean_goodput_mbps") for r in feas])
    a, b = spearman(x, y_so), spearman(x, y_cs)
    lines.append(f"\\midrule Resulting mean goodput & -- & {rho_tex(a)} & {rho_tex(b)} \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    (TABLES / "table_gen_space.tex").write_text("% Generated by evaluation/make_generalization.py -- do not edit.\n"
                                                + "\n".join(lines) + "\n", encoding="utf-8")
    m.add("GenRhoTfull", rho_tex(rhos["t_full_ms"][0]), src)
    m.add("GenRhoGoodput", rho_tex(a), src)
    m.add("GenRhoBandwidth", rho_tex(rhos["bandwidth_mhz"][0]), src)
    m.add("GenRhoSinr", rho_tex(rhos["mean_sinr_db"][0]), src)
    m.add("GenRhoDeadlineCodec", rho_tex(rhos["deadline_ms"][1]), src)
    m.add("GenRhoCameraCodec", rho_tex(rhos["camera_fps"][1]), src)
    minor = [c for c, _, _ in SPACE if c not in MAJOR]
    assert len(SPACE) == int(m_single_vars), "table must list every single-UAV variable"
    m.add("GenRhoMinorMax", f"{max(max(abs(rhos[c][0]), abs(rhos[c][1])) for c in minor):.2f}", src)

    # Figure: regime map -- which kind of option is best in each scenario, over (T, mean goodput)
    fig, ax = plt.subplots(figsize=(3.45, 2.5))
    style = {"onboard": (C["onboard"], "o", "Onboard best"), "codec": (C["jpeg"], "^", "Image offload best"),
             "split": (C["split"], "s", "Split best")}
    kinds = ["onboard" if r["oracle"].startswith("full") else "split" if r["oracle"].startswith("k") else "codec"
             for r in feas]
    for k, (col, mk, lab) in style.items():
        sel = [r for r, kk in zip(feas, kinds) if kk == k]
        ax.scatter([f(r, "t_full_ms") for r in sel], [max(f(r, "mean_goodput_mbps"), 0.1) for r in sel],
                   s=6 if k != "split" else 14, marker=mk, color=col, alpha=0.6 if k != "split" else 1.0,
                   label=f"{lab} ({len(sel)})", edgecolors="none")
    # Proposition 3 lines: goodput at which one payload takes as long as the full onboard model (beta = 1)
    t = np.logspace(1, 3, 50)
    ref = {r["config"]: r for r in read(RESULTS / "split_pareto_analysis.csv")}
    cod = {r["config"]: r for r in read(RESULTS / "codec_offload.csv")}
    for bytes_, col, lab in ((float(cod["jpeg_q90"]["payload_bytes_mean"]), C["jpeg"], r"$\beta=1$, JPEG Q90"),
                             (float(ref["k4_int8_zstd"]["payload_bytes_mean"]), C["split"], r"$\beta=1$, $k_4$+zstd")):
        ax.plot(t, bytes_ * 8 / 1e3 / t, color=col, ls="--", lw=0.9, label=lab)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_ylim(0.1, 300)
    ax.set_xlabel("Onboard full-model latency $t_{full}$ (ms)")
    ax.set_ylabel("Mean goodput (Mbit/s)")
    # Legend above the axes, off the data (the scatter fills every corner of the plot).
    ax.legend(frameon=False, fontsize=6, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2,
              columnspacing=1.0, handletextpad=0.4, markerscale=1.5)
    save(fig, "gen_regimes")


def theory_part(m: Macros) -> None:
    """Constants of Proposition 2 (offload dominance) for the measured YOLOv8s options."""
    from simulation.analytic import Option
    from simulation.system_model import host_full_ms, load_offload_configs

    src = "experiments/results/split_pareto_analysis.csv, codec_offload.csv"
    cfg = load_offload_configs()
    h = host_full_ms(cfg)
    o = {n: Option.from_config(c, h) for n, c in cfg.items()}
    splits = [n for n in o if o[n].kind == "split"]
    jpegs = [n for n in o if n.startswith("jpeg")]
    q = o["jpeg_q90"]
    # Proposition 2 holds for JPEG Q90 against every split once t_full (phi_k + rho_k - rho_q) >= s_q - s_k.
    t_min = max(max(0.0, (q.server_ms - o[k].server_ms)) / (o[k].phi + o[k].rho - q.rho) for k in splits)
    assert all(q.bits <= o[k].bits for k in splits)
    m.add("GenDominanceTmin", f"{t_min:.0f}", src)
    m.add("GenPhiRhoKFour", f"{o['k4_int8_zstd'].phi + o['k4_int8_zstd'].rho:.2f}", src)
    m.add("GenRhoJpegMax", f"{max(o[n].rho for n in jpegs):.2f}", src)
    k = o["k4_int8_zstd"]
    for qq, word in (("jpeg_q90", "Ninety"), ("jpeg_q95", "NinetyFive")):
        m.add(f"GenAccBound{word}Pct", f"{100 * (k.acc / o[qq].acc - 1):.1f}", src)


def main() -> None:
    m = Macros()
    theory_part(m)
    acc = read(GEN / "accuracy.csv")
    bits_part(m, acc)
    models_part(m, acc)
    scenarios_part(m)
    TABLES.mkdir(parents=True, exist_ok=True)
    (TABLES / "gen_metrics.tex").write_text(m.tex().replace("make_tables.py", "make_generalization.py"), encoding="utf-8")
    LEDGER.write_text(m.ledger().replace("make_tables.py", "make_generalization.py")
                      .replace("; the sections below are written by the generators named in them (`evaluation/ledger.py`)", "")
                      .replace("# Claims-to-evidence ledger", "# Claims-to-evidence ledger: generalization study"),
                      encoding="utf-8")
    print(f"{len(m.items)} macros")


if __name__ == "__main__":
    main()
