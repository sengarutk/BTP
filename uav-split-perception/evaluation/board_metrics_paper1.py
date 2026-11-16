#!/usr/bin/env python3
"""Paper 1's numbers from the mesh board sessions (16 Nov 2026): the live break-even sweep (T10), the Pi encode times
(T11), and the break-even goodput re-computed with measured Pi times (evaluation/pi_measured_break_even.py,
pi_measured_second_detector.py). Every number is computed by scripts/report_mesh_nov16.py from the result files (the
same source as Results Brief 19.30 and paper 2). Output: paper/generated_tables/board_metrics.tex (macros \\Bp...) and
board_metrics_sources.md.
usage: python evaluation/board_metrics_paper1.py
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import report_mesh_nov16 as rm  # noqa: E402

OUT = ROOT / "paper" / "generated_tables"
M, SRC = {}, []


def put(name, value, src, fmt="{:.2f}"):
    assert name.isalpha(), name
    s = value if isinstance(value, str) else fmt.format(value)
    M[name] = s.replace("-", "\\textminus{}", 1) if s.startswith("-") else s
    SRC.append((name, s, src))


def main():
    R = rm.R
    pr = json.load(open(R / "t10" / "t10_prediction.json"))
    O = pr["options"]
    src = "experiments/results/hardware/t10 (scripts/report_mesh_nov16.py)"
    # T10: the best measured option per goodput, and the codes' and JPEG's measured rates
    rates = sorted(rm.best)
    put("BpRates", ", ".join(f"{r:g}" for r in rates), f"{src}: goodputs swept (Mbit/s)")
    put("BpBestAllJpeg", "yes" if all(rm.best[r][0].startswith("jpeg") for r in rates) else "no",
        f"{src}: a JPEG option is best at every goodput")
    code_fps = [np.mean([x["on_time_fps"] for x in L]) for (r, o), L in rm.sweep.items() if not o.startswith("jpeg")]
    put("BpCodeFpsMax", max(code_fps), f"{src}: largest on-time rate of any code (results/s)", "{:.1f}")
    for r, nm in ((4.0, "Four"), (8.0, "Eight")):
        put(f"BpJpegFps{nm}", np.mean([x["on_time_fps"] for x in rm.sweep[(r, "jpeg_q20")]]),
            f"{src}: jpeg_q20 on-time results/s at {r:g} Mbit/s", "{:.1f}")
    for o, nm in (("k4_c4_w128_d2", "KfourCfour"), ("k2_c8_w128_d2", "KtwoCeight")):
        put(f"BpOnb{nm}", O[o]["onboard_ms"], f"{src}: t10_prediction.json options.{o}.onboard_ms (cold bench)", "{:.0f}")
    put("BpJpegOnb", O["jpeg_q20"]["onboard_ms"], f"{src}: jpeg_q20 onboard ms", "{:.1f}")
    # the token-bucket (shared radio) arm at 0.5 Mbit/s
    htb = {}
    for f in (R / "t10" / "sweep").glob("*__htb.json"):
        d = json.load(open(f))
        htb[(float(d["rate_mbit"]), d["option"])] = d["on_time_fps"]
    put("BpHtbCode", htb[(0.5, "k4_c4_w128_d2")], f"{src}: token bucket, 0.5 Mbit/s, k4_c4 on-time/s", "{:.1f}")
    put("BpHtbJpeg", htb[(0.5, "jpeg_q20")], f"{src}: token bucket, 0.5 Mbit/s, jpeg_q20 on-time/s", "{:.1f}")
    # T11 and the measured-Pi re-analysis
    put("BpXuf", rm.t11["x264_ultrafast_crf23"]["ms_per_frame"], "t11: x264 ultrafast CRF 23 ms/frame on the Pi", "{:.1f}")
    put("BpXmed", rm.t11["x265_medium_crf23"]["ms_per_frame"], "t11: x265 medium CRF 23 ms/frame on the Pi", "{:.0f}")
    put("BpRatioMin", min(rm.ratios), "t11: Pi/laptop encode time, min over settings")
    put("BpRatioMax", max(rm.ratios), "t11: ... max")
    put("BpScale", rm.pim["scale_rule"], "analysis_pi_measured.json: the rule's host-time scale on the Pi", "{:.1f}")
    put("BpJpegRatio", rm.pim["jpeg_pi_over_laptop"], "analysis_pi_measured.json: JPEG encode, Pi/laptop, median of the measured qualities", "{:.1f}")
    for fam, nm in (("jpeg", "Jpeg"), ("both", "Video")):
        put(f"BpHead{nm}Rule", rm.rule[(fam, "joint_k4_c4_w128_d2")]["b_be_mbps"], f"analysis_pi_measured.json: joint_k4_c4, {fam}, rule")
        put(f"BpHead{nm}Meas", rm.meas[(fam, "joint_k4_c4_w128_d2")]["b_be_mbps"], f"... measured Pi times")
    put("BpWinsVideoMeas", str(rm.wins_video), "analysis_pi_measured.json: winning cells, measured, JPEG + video")
    put("BpWinsJpegMeas", str(rm.pim["versions"]["measured"]["jpeg"]["wins_total"]), "... JPEG only")
    put("BpExc", str(sum(v["violations"] for v in rm.pim["versions"]["measured"].values())), "... exceptions, all families")
    t10b = json.load(open(R / "t10" / "t10_bench_camera2.json"))["options"]
    put("BpCodeMsMin", min(t10b[c]["onboard_ms_median"] for c in ("k4_c4_w128_d2", "k4_c8_w128_d2", "k2_c8_w128_d2")),
        "t10_bench_camera2.json: measured Pi onboard ms of the codes, min", "{:.0f}")
    put("BpCodeMsMax", max(t10b[c]["onboard_ms_median"] for c in ("k4_c4_w128_d2", "k4_c8_w128_d2", "k2_c8_w128_d2")),
        "... max", "{:.0f}")
    y = rm.y11
    dev = [abs(r["onboard_ms_measured"] / r["onboard_ms_rule"] - 1) * 100 for r in y["rows"] if r["code"].startswith("learned_")]
    put("BpYelevenDev", max(dev), "break_even_pi_measured.json: YOLO11s codes, |measured/rule - 1| max (%)", "{:.0f}")
    bes = [r["b_be_mbps_measured"] for r in y["rows"] if r["b_be_mbps_measured"]]
    put("BpYelevenBeMin", min(bes), "break_even_pi_measured.json: YOLO11s B_be measured, min")
    put("BpYelevenBeMax", max(bes), "... max")
    put("BpYelevenWins", str(y["wins_total"]), "... winning cells")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "board_metrics.tex").write_text("% Generated by evaluation/board_metrics_paper1.py -- do not edit.\n" +
                                           "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in M.items()))
    (OUT / "board_metrics_sources.md").write_text("# paper 1 board numbers and their sources\n\n| Macro | Value | Source |\n"
                                                  "| --- | --- | --- |\n" + "".join(f"| `\\{k}` | {v} | {s} |\n" for k, v, s in SRC))
    for k, v, _ in SRC:
        print(f"{k:20s} {v}")


if __name__ == "__main__":
    main()
