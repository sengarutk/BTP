#!/usr/bin/env python3
"""Paper 1's break-even goodput on the Pi with MEASURED onboard times (16 Nov 2026, from T11 and T10).

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
T11 = REPO / "experiments" / "results" / "hardware" / "t11" / "t11_video_pi-receiver.jsonl"
T10 = REPO / "experiments" / "results" / "hardware" / "t10" / "t10_bench_camera2.json"
PI_FULL, PI_UNTHROTTLED_FULL = 757.588298499968, 700.0      # rule's throttled Pi; PRIOR_ONBOARD_MS s640 (adaptive2.py)
CODE_MAP = {"learned_k4_c4_w128_d2": "k4_c4_w128_d2", "learned_k4_c8_w128_d2": "k4_c8_w128_d2",
            "learned_k2_c8_w128_d2": "k2_c8_w128_d2"}


def main():
    hfull = b.host_full_ms(None, b.VD)
    scale = PI_FULL / hfull
    raw = json.load(open(VC / "raw.json"))
    rows = {f.stem: json.load(open(f)) for f in VC.glob("*.json")
            if f.stem not in ("raw", "names", "analysis", "analysis_inter", "analysis_pi_measured")}
    base = measured_configs()
    det_jpeg = {c.name: c for c in b.jpeg_grid(base)}
    det_codes = {c.name: c for c in b.learned_and_joint() + b.entropy_codes()}
    onboard = next(c for c in base if c.kind == "onboard")
    A0 = raw["map50_95"]
    t11 = {json.loads(l)["setting"]: json.loads(l) for f_ in (T11, T11.with_name(T11.stem + "_extra.jsonl"))
           for l in open(f_)}                   # CRF 18-33 and 38/43
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

    out = {"scale_rule": scale, "jpeg_pi_over_laptop": ratio_j, "versions": {}}
    for ver, f in (("measured", 1.0), ("measured_throttled", PI_FULL / PI_UNTHROTTLED_FULL)):
        fams = {"jpeg": [], "video": []}
        for n, r in jp.items():
            c = det_jpeg[n]
            ms = meas_j.get(n, r["encode_ms_median"] * ratio_j) * f
            fams["jpeg"].append(opt(c, r, host_edge_proc_ms=at(c, ms),
                                    cloud_ms=c.cloud_ms - q50["decode_ms_median"] + r["decode_ms_median"]))
        proto = det_jpeg["jpeg_q50"]
        for n, r in vids.items():
            ms = t11[n]["ms_per_frame"] * f
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
            ar, viol, checked, wins = b.analyse(opts, others, devs=[("Pi 5 (measured)", PI_FULL)])
            res[fam] = {"rows": [{k: r_[k] for k in ("code", "q_star", "b_be_mbps", "max_win_mbps")} for r_ in ar],
                        "violations": len(viol), "wins_total": wins}
            print(ver, fam, "wins", wins, "exceptions", len(viol), flush=True)
        out["versions"][ver] = res
    # the same codes under the rule's scaled times, for comparison
    sc = json.load(open(VC / "analysis.json"))["cases"]
    out["rule_scaled_pi"] = {fam: [{k: r_[k] for k in ("code", "q_star", "b_be_mbps", "max_win_mbps")}
                                   for r_ in sc[f"{fam}_scaled"]["rows"] if r_["device"].startswith("Pi")]
                             for fam in ("jpeg", "video", "both")}
    json.dump(out, open(VC / "analysis_pi_measured.json", "w"), indent=1)
    print("written", VC / "analysis_pi_measured.json")


if __name__ == "__main__":
    main()
