"""Numbers and the table of the hardware section (Section "Hardware check") from the testbed result files.

Sources (experiments/results/):
  hardware/placements_summary.json            all placements over Pi 5, Jetson Orin Nano and the laptop GPU
  hardware/placement_model_check.json         placement model vs live runs (evaluation/placement_model_check.py)
  hardware/live_summary.csv                   live pipeline runs (30 fps camera, 60 s, detections returned)
  hardware/raw/pi5_cpu_4t_sustained.json      per-segment and encoding times on the throttled Pi 5 (4 threads)
  hardware/raw/laptop_gpu_fp16.json           the same on the laptop GPU (FP16)
  hardware/sim_vs_real_stopwait_persist.json  the simulator rebuilt from 44 real runs of fixed single-path offloading
  visdrone_ft_split/accuracy_mAP_results.json every split point and precision with the VisDrone-trained YOLOv8s
  visdrone_ft_split/codec_accuracy.json       whole-frame image codecs on the same images
  learned_bottleneck/posthoc_k4_int8_zstd.json, jpeg_q90.json   payloads measured on the same VisDrone DET val frames
mAP values are written in points (x 100), payloads in KiB (1 KiB = 1024 bytes).
Writes paper/generated_tables/hw_metrics.tex, table_hardware.tex and its section of docs/claims_to_evidence.md.
"""
import csv
import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from evaluation.ledger import write_section

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "experiments" / "results"
OUT = ROOT / "paper" / "generated_tables"

LIVE_ROWS = [("pi_laptop_jpeg", "Pi JPEG Q90 $\\to$ laptop"), ("pi_jetson_jpeg", "Pi JPEG Q90 $\\to$ Jetson"),
             ("pi_laptop_k1", "Pi $k_1$ INT8 $\\to$ laptop (best split)"),
             ("pi_laptop_k4", "Pi $k_4$ INT8 $\\to$ laptop"), ("pi_jetson_k4", "Pi $k_4$ INT8 $\\to$ Jetson"),
             ("pi_solo", "Pi alone")]
SIM_POLICY = {"fixed:laptop:m640q90": "Laptop", "fixed:jetson:s640q90": "Jetson"}


def r1(x, nd=1):
    """Round half up, as the results brief does (10.85 -> 10.9; float formatting gives 10.8)."""
    return str(Decimal(str(x)).quantize(Decimal(1).scaleb(-nd), ROUND_HALF_UP))


def pts(x: float, nd: int = 2) -> str:
    """mAP or mAP difference in points (x 100), signed with a LaTeX minus."""
    return f"{100 * x:+.{nd}f}".replace("-", "$-$") if round(100 * x, nd) != 0 else f"{0:.{nd}f}"


def main():
    m, how = {}, {}

    def add(name, value, source, note):
        m[name] = value
        how[name] = (source, note)

    pl = json.load(open(RES / "hardware" / "placements_summary.json"))
    src = "hardware/placements_summary.json"
    add("HwNPlacements", f"{pl['n_placements']:,}".replace(",", "{,}"), src, "number of placements evaluated by the model")
    add("HwPiFullMs", f"{pl['devices']['pi']['full_ms']:.0f}", src, "YOLOv8s on the throttled Pi 5 (4 threads), ms")
    add("HwJetsonFullMs", f"{pl['devices']['jetson']['full_ms']:.1f}", src, "YOLOv8s on the Jetson GPU (FP16), ms")

    live = {r["placement"]: r for r in csv.DictReader(open(RES / "hardware" / "live_summary.csv"))}
    src = "hardware/live_summary.csv"
    j, k1, k4 = live["pi_laptop_jpeg"], live["pi_laptop_k1"], live["pi_laptop_k4"]
    add("HwJpegFps", r1(j["fps_median"]), src, "Pi JPEG Q90 -> laptop: median delivered frames/s over runs")
    add("HwJpegOnTime", r1(j["on_time_fps_median"]), src, "the same, results within 300 ms per s")
    add("HwJpegLatMs", r1(j["lat_p50_ms_median"], 0), src, "the same, median capture-to-result latency (ms)")
    add("HwKOneFps", r1(k1["fps_median"]), src, "Pi k1 INT8+zstd -> laptop: median frames/s")
    add("HwKOneOnTime", r1(k1["on_time_fps_median"]), src, "the same, on time per s")
    add("HwKOneLatMs", r1(k1["lat_p50_ms_median"], 0), src, "the same, median latency (ms)")
    add("HwKFourOnTime", r1(k4["on_time_fps_median"]), src, "Pi k4 INT8+zstd -> laptop: median on-time results/s")
    add("HwPiSoloFps", r1(live["pi_solo"]["fps_median"]), src, "YOLOv8s on the Pi alone: median frames/s")
    add("HwLiveRuns", str(sum(int(r["runs"]) for r in live.values())), src, "sum of runs over every live placement")

    # Placement model against the live runs (evaluation/placement_model_check.py -> placement_model_check.json)
    pc = json.load(open(RES / "hardware" / "placement_model_check.json"))
    src = "hardware/placement_model_check.json"
    s2, s3, iv = pc["one_or_two_devices"], pc["three_devices"], pc["pi_image_vs_split"]
    add("HwModelNShort", str(s2["n"]), src, "live placements on one or two devices matched to a model row")
    add("HwModelRatioMin", f"{s2['min_ratio']:.1f}", src,
        "min over one- and two-device live placements of model fps / median live fps")
    add("HwModelRatioMax", f"{s2['max_ratio']:.1f}", src, "max of the same ratio")
    add("HwModelNThree", str(s3["n"]), src, "live three-device placements matched to a model row")
    add("HwModelRatioThreeMax", f"{s3['max_ratio']:.1f}", src,
        "max over three-device live placements of model fps / median live fps")
    both = iv["model_ranks_every_image_above_every_split"] and iv["live_ranks_every_image_above_every_split"]
    add("HwModelImageAboveSplit", "every" if both else "not every", src,
        "whether model and live runs both rank every Pi image-offload placement above every Pi split placement")

    sim = json.load(open(RES / "hardware" / "sim_vs_real_stopwait_persist.json"))
    s, rows_ = sim["summary"]["all"], sim["rows"]
    src = "hardware/sim_vs_real_stopwait_persist.json"
    add("HwSimR", f"{s['corr']:.3f}", src, "Pearson r of predicted vs measured on-time results/s over all phases")
    add("HwSimMae", f"{s['mae_fps']:.1f}", src, "mean absolute error over all phases (results/s)")
    add("HwSimPhases", str(s["n"]), src, "number of phases compared")
    add("HwSimRuns", str(len({x["run"] for x in rows_})), src, "number of distinct live runs")
    assert {x["policy"] for x in rows_} == set(SIM_POLICY), "the simulator check now covers other strategies"
    for pol, word in SIM_POLICY.items():
        rr = [x for x in rows_ if x["policy"] == pol]
        add(f"HwSimRuns{word}", str(len({x["run"] for x in rr})), src, f"distinct runs of {pol}")
        add(f"HwSimPhases{word}", str(len(rr)), src, f"phases of {pol}")

    # VisDrone-trained YOLOv8s: accuracy in points
    acc = json.load(open(RES / "visdrone_ft_split" / "accuracy_mAP_results.json"))["results"]
    full = next(r for r in acc if r["config"] == "full_fp32")["map50_95"]
    q = [r for r in acc if r["dtype"] in ("int8", "fp16") and r["config"] != "full_fp32"]
    src = "visdrone_ft_split/accuracy_mAP_results.json"
    add("HwVdFullMap", f"{100 * full:.1f}", src, "mAP@[.5:.95] of the unsplit VisDrone YOLOv8s, points")
    add("HwVdSplitMaxAbsDelta", f"{100 * max(abs(r['delta_map50_95']) for r in q):.2f}", src,
        "largest |delta mAP| over the INT8 and FP16 splits, points")
    add("HwVdSplitN", str(len(q)), src, "number of INT8 and FP16 split configurations")
    add("HwVdSplitAllCiZero", "all" if all(r["delta_map50_95_ci_low"] <= 0 <= r["delta_map50_95_ci_high"] for r in q)
        else "not all", src, "whether every 95% paired-bootstrap interval contains zero")
    cod = json.load(open(RES / "visdrone_ft_split" / "codec_accuracy.json"))
    src = "visdrone_ft_split/codec_accuracy.json"
    for qq, name in ((90, "Ninety"), (50, "Fifty")):
        d = cod[f"jpeg_q{qq}"]["map50_95"] - cod["full_fp32"]["map50_95"]
        add(f"HwVdJpeg{name}Delta", pts(d), src, f"mAP of JPEG Q{qq} minus unsplit, points (signed, for tables)")
        add(f"HwVdJpeg{name}Loss", f"{-100 * d:.2f}", src, f"the same as a positive loss in points, for prose")
        add(f"HwVdJpeg{name}Pct", f"{100 * -d / cod['full_fp32']['map50_95']:.1f}", src,
            f"relative loss of JPEG Q{qq}, % of the unsplit mAP")
    # Proposition prop:dominance (offload dominance): a split can beat an image that needs no more bits, onboard time
    # and onboard + server time by at most the accuracy ratio A_split / A_image; best INT8/FP16 split vs Q90 JPEG.
    best = max(r["map50_95"] for r in q)
    add("HwVdBoundPct", f"{100 * (best / cod['jpeg_q90']['map50_95'] - 1):.1f}",
        "visdrone_ft_split/accuracy_mAP_results.json, codec_accuracy.json",
        "100 x (mAP of the best INT8/FP16 split / mAP of JPEG Q90 - 1): the accuracy-ratio bound of prop:dominance")

    # The three conditions of prop:dominance on these frames and devices
    lb = RES / "learned_bottleneck"
    split_b = json.load(open(lb / "posthoc_k4_int8_zstd.json"))["payload_bytes_mean"]
    jpeg_b = json.load(open(lb / "jpeg_q90.json"))["payload_bytes_mean"]
    src = "learned_bottleneck/posthoc_k4_int8_zstd.json, jpeg_q90.json"
    add("HwVdSplitKiB", f"{split_b / 1024:.1f}", src, "mean k4 INT8+zstd payload on VisDrone DET val, KiB")
    add("HwVdJpegNinetyKiB", f"{jpeg_b / 1024:.1f}", src, "mean JPEG Q90 payload on the same frames, KiB")
    add("HwVdSplitOverJpeg", f"{split_b / jpeg_b:.1f}", src, "k4 INT8+zstd payload / JPEG Q90 payload, same frames")
    pi = json.load(open(RES / "hardware" / "raw" / "pi5_cpu_4t_sustained.json"))
    lap = json.load(open(RES / "hardware" / "raw" / "laptop_gpu_fp16.json"))
    cuts = sorted(int(k) for k in pi["codec"])
    on = {k: pi["segment_ms"][f"-1,{k}"] + pi["codec"][str(k)]["int8_zstd"]["enc_ms"] for k in cuts}
    tot = {k: on[k] + lap["codec"][str(k)]["int8_zstd"]["dec_ms"] + lap["segment_ms"][f"{k},22"] + lap["post_ms"]
           for k in cuts}
    img_on = pi["jpeg"]["enc_ms"]
    img_tot = img_on + lap["jpeg"]["dec_ms"] + lap["full_ms"] + lap["post_ms"]
    kmin = min(on, key=on.get)
    src = "hardware/raw/pi5_cpu_4t_sustained.json, hardware/raw/laptop_gpu_fp16.json"
    add("HwPiJpegEncMs", f"{img_on:.1f}", src, "JPEG Q90 encoding on the Pi (the image's onboard work), ms")
    add("HwPiSplitOnboardMinMs", f"{on[kmin]:.0f}", src,
        "min over cuts k of Pi time for layers 0..k + INT8+zstd encoding (a split's onboard work), ms")
    add("HwPiSplitOnboardMinCut", str(kmin), src, "the cut attaining HwPiSplitOnboardMinMs")
    add("HwPiImgTotalMs", f"{img_tot:.1f}", src,
        "Pi JPEG encode + laptop decode + laptop YOLOv8s + NMS, ms (onboard plus server time of the image)")
    add("HwPiSplitTotalMinMs", f"{min(tot.values()):.0f}", src,
        "min over k of Pi layers 0..k + encode + laptop decode + laptop layers k+1..22 + NMS, ms")
    assert split_b > jpeg_b and img_on < on[kmin] and img_tot < min(tot.values()), "a dominance condition fails"

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "hw_metrics.tex").write_text("% Generated by evaluation/make_hardware.py from experiments/results -- do not edit.\n" +
                                        "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in m.items()))
    rows = []
    for key, lab in LIVE_ROWS:
        r = live[key]
        rows.append(f"{lab} & {r['runs']} & {r1(r['fps_median'])} & {r1(r['on_time_fps_median'])} & "
                    f"{r1(r['lat_p50_ms_median'], 0)} \\\\")
    (OUT / "table_hardware.tex").write_text(
        "% Generated by evaluation/make_hardware.py -- do not edit.\n\\begin{tabular}{@{}lrrrr@{}}\n\\toprule\n"
        "Placement & Runs & Frames/s & On time/s & $p_{50}$ (ms) \\\\ \\midrule\n" + "\n".join(rows) +
        "\n\\bottomrule\n\\end{tabular}\n")
    write_section('Hardware check (Section "Hardware Check")',
                  "Generated by `evaluation/make_hardware.py` (`make tables`) into `paper/generated_tables/hw_metrics.tex` "
                  "and `table_hardware.tex`; paths under `experiments/results/`. mAP in points (x 100), payloads in KiB.",
                  [(k, v.replace("$-$", "-").replace("{,}", ","), *how[k]) for k, v in m.items()])
    for k, v in m.items():
        print(f"{k:24s} {v}")


if __name__ == "__main__":
    main()
