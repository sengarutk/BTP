#!/usr/bin/env python3
"""Item 1b of the laptop strengthening (16 Nov 2026; predictions: docs/laptop_strengthening_predictions_nov16.md):
paper 1's break-even goodput for a FAST camera, a Jetson Orin Nano, with its MEASURED onboard times. The structure is
evaluation/pi_measured_break_even.py's (the Pi version), with the device changed:
  codes, JPEG   T10 bench on Nano2 as the camera (t10_bench_jetson2.json: k4_c4 9.52, k4_c8 9.54, k2_c8 6.57 ms
                onboard incl. uint8 + zstd; JPEG q20 3.74, q35 3.84, q90 4.37 ms); other JPEG qualities: laptop x the
                median measured Jetson/laptop ratio
  video         not measured on the Jetson: laptop encode time x the same JPEG ratio (on the Pi the JPEG ratio, 4.5,
                was larger than every video ratio, 1.55-3.08, so this overstates video's cost and favours the codes)
  device        the rule's "Jetson Orin Nano" (raw/jetson_gpu_fp16.json full_ms) for every unmeasured option
No live sweep with the Jetson as the camera was run (the boards were not set up again); this is the rule on measured
times only. Families: JPEG, video, both.
usage: python evaluation/jetson_measured_break_even.py -> experiments/results/video_codecs/analysis_jetson_measured.json

The Pi version's notes follow.
Paper 1's break-even goodput on the Pi with MEASURED onboard times (16 Nov 2026, from T11 and T10).

The rule (break_even_rule.py, simulation/system_model.EdgeHardware.onboard_ms) scales every option's host processing by
t_full / t_host (757.6 / 11.93 = 63.5 on the throttled Pi 5): right for neural-network work, wrong for CPU encoding,
which the Pi does only 1.6-5x slower than the laptop. Measured on the Pi (pi-receiver, unthrottled):
  video encode  experiments/results/hardware/t11/t11_video_pi-receiver.jsonl (ffmpeg, video_codecs.py's exact arguments)
  JPEG encode   T10 bench (jpeg_q20 2.26, q35 2.33, q90 2.71 ms; other qualities: laptop x the median Pi/laptop ratio)
  codes         T10 bench (split_live.py: k4_c4 226.5, k4_c8 227.8, k2_c8 174.4 ms onboard incl. uint8 + zstd)
This analysis re-runs break_even_rule.analyse for the Pi only, with every measured option's onboard time set to its
measured time (its host processing set so the rule's formula returns exactly that time); codes without a Pi
measurement keep the rule's time. Two versions: as measured (unthrottled) and x 1.082 (the throttled/unthrottled
full-model time ratio, 757.6 / 700, the rule's throttled Pi). Families: JPEG, video, both (as video_codecs.py).
usage: python evaluation/pi_measured_break_even.py -> experiments/results/video_codecs/analysis_pi_measured.json
"""
import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from evaluation import break_even_rule as b                       # noqa: E402
from evaluation.learned_bottleneck_system import measured_configs  # noqa: E402

VC = REPO / "experiments" / "results" / "video_codecs"
T10 = REPO / "experiments" / "results" / "hardware" / "t10" / "t10_bench_jetson2.json"
PI_FULL = json.load(open(REPO / "experiments" / "results" / "hardware" / "raw" / "jetson_gpu_fp16.json"))["full_ms"]  # the rule's Jetson
CODE_MAP = {"learned_k4_c4_w128_d2": "k4_c4_w128_d2", "learned_k4_c8_w128_d2": "k4_c8_w128_d2",
            "learned_k2_c8_w128_d2": "k2_c8_w128_d2"}


def main():
    hfull = b.host_full_ms(None, b.VD)
    scale = PI_FULL / hfull
    raw = json.load(open(VC / "raw.json"))
    rows = {f.stem: json.load(open(f)) for f in VC.glob("*.json")
            if f.stem not in ("raw", "names", "analysis", "analysis_inter", "analysis_pi_measured", "analysis_jetson_measured")}
    base = measured_configs()
    det_jpeg = {c.name: c for c in b.jpeg_grid(base)}
    det_codes = {c.name: c for c in b.learned_and_joint() + b.entropy_codes()}
    onboard = next(c for c in base if c.kind == "onboard")
    A0 = raw["map50_95"]
    t10 = json.load(open(T10))["options"]
    jp = {r["option"]: r for k, r in rows.items() if k.startswith("jpeg_q")}
    vids = {k: r for k, r in rows.items() if "_crf" in k and r["codec"] != "h264_nvenc"}
    codes = {r["option"]: r for k, r in rows.items() if k.startswith("code_")}
    q50 = jp["jpeg_q50"]
    meas_j = {q: t10[q]["onboard_ms_median"] for q in ("jpeg_q20", "jpeg_q35", "jpeg_q90")}
    ratio_j = float(np.median([meas_j[q] / jp[q]["encode_ms_median"] for q in meas_j]))

    def opt(c, r, **kw):
        return replace(c, payload_bytes=r["payload_bytes_mean"], map50_95=r["map50_95"], map50=r["map50"],
                       delta_map50_95=r["map50_95"] - A0, **kw)

    def at(c, target_ms):        # host processing such that onboard_ms = t_full * phi + host * scale = target_ms
        return max(0.0, (target_ms - PI_FULL * c.edge_flop_frac) / scale)

    out = {"device_full_ms": PI_FULL, "scale_rule": scale, "jpeg_jetson_over_laptop": ratio_j, "versions": {}}
    # video's Jetson/laptop encode ratio is not measured: the JPEG ratio (upper end), and the Pi's measured video/JPEG
    # ratio range applied to it (T11: video 1.55-3.08 vs JPEG 4.5 on the Pi, i.e. x 0.344-0.684)
    pim = json.load(open(VC / "analysis_pi_measured.json"))
    t11 = [json.loads(l) for fn in ("t11_video_pi-receiver.jsonl", "t11_video_pi-receiver_extra.jsonl")
           for l in open(REPO / "experiments" / "results" / "hardware" / "t11" / fn)]
    pv = [x["ms_per_frame"] / rows[x["setting"]]["encode_ms_per_frame"] for x in t11 if x["setting"] in rows]
    vs = {"measured": 1.0, "video_pi_like_hi": max(pv) / pim["jpeg_pi_over_laptop"],
          "video_pi_like_lo": min(pv) / pim["jpeg_pi_over_laptop"]}
    out["video_scale"] = vs
    for ver, f in (("measured", 1.0), ("video_pi_like_hi", 1.0), ("video_pi_like_lo", 1.0)):
        fams = {"jpeg": [], "video": []}
        for n, r in jp.items():
            c = det_jpeg[n]
            ms = meas_j.get(n, r["encode_ms_median"] * ratio_j) * f
            fams["jpeg"].append(opt(c, r, host_edge_proc_ms=at(c, ms),
                                    cloud_ms=c.cloud_ms - q50["decode_ms_median"] + r["decode_ms_median"]))
        proto = det_jpeg["jpeg_q50"]
        for n, r in vids.items():
            ms = r["encode_ms_per_frame"] * ratio_j * vs[ver] * f   # not measured on the Jetson (see the header)
            fams["video"].append(opt(proto, r, name=n, dtype=n, host_edge_proc_ms=at(proto, ms),
                                     cloud_ms=proto.cloud_ms - q50["decode_ms_median"] + r["decode_ms_per_frame"]))
        fams["both"] = fams["jpeg"] + fams["video"]
        splits = []
        for n, r in codes.items():
            if n not in det_codes:
                continue
            c = det_codes[n]
            kw = {"host_edge_proc_ms": at(c, t10[CODE_MAP[n]]["onboard_ms_median"] * f)} if n in CODE_MAP else {}
            splits.append(opt(c, r, **kw))
        others = [opt(onboard, raw | {"payload_bytes_mean": 0.0})] + splits
        res = {}
        for fam, opts in fams.items():
            ar, viol, checked, wins = b.analyse(opts, others, devs=[("Jetson Orin Nano (measured)", PI_FULL)])
            res[fam] = {"rows": [{k: r_[k] for k in ("code", "q_star", "b_be_mbps", "max_win_mbps")} for r_ in ar],
                        "violations": len(viol), "wins_total": wins}
            print(ver, fam, "wins", wins, "exceptions", len(viol), flush=True)
        out["versions"][ver] = res
    # the same codes under the rule's scaled times, for comparison
    sc = json.load(open(VC / "analysis.json"))["cases"]
    out["rule_scaled_jetson"] = {fam: [{k: r_[k] for k in ("code", "q_star", "b_be_mbps", "max_win_mbps")}
                                       for r_ in sc[f"{fam}_scaled"]["rows"] if r_["device"] == "Jetson Orin Nano"]
                                 for fam in ("jpeg", "video", "both")}
    json.dump(out, open(VC / "analysis_jetson_measured.json", "w"), indent=1)
    print("written", VC / "analysis_jetson_measured.json")


if __name__ == "__main__":
    main()
