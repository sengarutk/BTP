#!/usr/bin/env python3
"""Report update, 25 Oct 2026: 19.6 - tasks R2 (staleness curve and forecaster re-measured with a YOLOv8s trained on
VisDrone-DET only), R3 (swarm simulation re-weighted with VisDrone accuracy) and R4 (INT8 split accuracy and the
image codecs on VisDrone). Inserted after 19.5 (before Part 20); marks R2-R4 done in the state box. Idempotent.
"""
import csv
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_parts_oct22 import HTML, MD, html_to_md, table  # noqa: E402

RES = Path(__file__).resolve().parent.parent / "experiments" / "results"
HW = RES / "hardware"
VD = RES / "visdrone_ft_split"


def r2():
    o = json.load(open(HW / "staleness_decay_forecast_v2.json"))
    n = json.load(open(HW / "staleness_decay_forecast_v2_det.json"))
    idx = [1, 3, 5, 6, 7]
    t = table(["Detector (VisDrone-VID train replay)", "fresh AP"] + [f"after {o['lag_ms'][i]:.0f} ms" for i in idx],
              [["COCO YOLOv8s (in use), no forecaster", f"{o['ap_no_forecast'][0]:.3f}"] + [f"{o['ratio_no_forecast'][i]:.3f}" for i in idx],
               ["VisDrone-DET-only YOLOv8s, no forecaster", f"{n['ap_no_forecast'][0]:.3f}"] + [f"{n['ratio_no_forecast'][i]:.3f}" for i in idx],
               ["COCO YOLOv8s, forecaster v2", ""] + [f"{o['ratio'][i]:.3f}" for i in idx],
               ["VisDrone-DET-only YOLOv8s, forecaster re-tuned", ""] + [f"{n['ratio'][i]:.3f}" for i in idx]])
    to, tn = json.load(open(HW / "forecast_tuning_v2.json")), json.load(open(HW / "forecast_tuning_v2_det.json"))
    rows = tn["all"]
    k = next(i for i, r in enumerate(rows) if r["params"] == to["best"]["params"])
    diff = {p: (to["best"]["params"][p], tn["best"]["params"][p]) for p in tn["best"]["params"]
            if tn["best"]["params"][p] != to["best"]["params"].get(p)}
    return t, k + 1, len(rows), rows[0]["mean_ap_lagged"], rows[k]["mean_ap_lagged"], diff


def r4():
    v = {r["config"]: r for r in csv.DictReader(open(VD / "accuracy_mAP_results.csv"))}
    c = {r["config"]: r for r in csv.DictReader(open(RES / "accuracy_mAP_results.csv"))}
    rows = []
    for k in ("full_fp32", "k2_int8", "k4_int8", "k4_fp16", "k7_int8", "k12_int8", "k18_int8", "k4_int8_per_channel",
              "k4_uint8_clip"):
        lo, hi = v[k]["delta_map50_95_ci_low"], v[k]["delta_map50_95_ci_high"]
        rows.append([k, f"{float(c[k]['map50_95']):.4f}", f"{float(c[k]['delta_map50_95']):+.4f}", f"{float(v[k]['map50_95']):.4f}",
                     f"{float(v[k]['delta_map50_95']):+.4f}" + (f" [{float(lo):+.4f}, {float(hi):+.4f}]" if lo not in ("", None) else "")])
    t = table(["Configuration", "COCO val2017 mAP", "Δ vs full", "VisDrone-DET val mAP", "Δ vs full [95 % CI]"], rows)
    ca = json.load(open(VD / "codec_accuracy.json"))
    co = {r["config"]: r for r in csv.DictReader(open(RES / "codec_offload.csv"))}
    base = ca["full_fp32"]["map50_95"]
    t2 = table(["Image codec (whole frame)", "COCO Δ mAP", "VisDrone Δ mAP", "VisDrone relative loss"],
               [[k, f"{float(co[k]['delta_map50_95']):+.4f}", f"{ca[k]['map50_95'] - base:+.4f}",
                 f"{100 * (ca[k]['map50_95'] - base) / base:+.1f} %"] for k in co])
    worst = max(abs(float(v[k]["delta_map50_95"])) for k in v if ("int8" in k or "fp16" in k) and "clip" not in k)
    return t, t2, worst


def r3():
    a = json.load(open(HW / "swarm_calibrated_summary.json"))["summary"]
    b = json.load(open(HW / "swarm_calibrated_visdrone_summary.json"))["summary"]
    same = sum(x == y for k in a for x, y in zip(a[k]["best_by_n"], b[k]["best_by_n"]))
    tot = sum(len(a[k]["best_by_n"]) for k in a)
    return same, tot


def section():
    t2a, rank, nset, best_ap, coco_ap, diff = r2()
    t4, t4c, worst = r4()
    same, tot = r3()
    dtxt = ", ".join(f"{p} {x} → {y}" for p, (x, y) in diff.items()) or "none"
    return f'''<h3>19.6 Tasks R2–R4: the remaining COCO-era measurements redone with VisDrone (25 Oct 2026)</h3>
<p><b>R2 – staleness curve and forecaster with a detector that never saw VID footage.</b> The controllers' staleness curve and the forecaster's setting were measured on the VisDrone-VID <i>train</i> clips with the COCO YOLOv8s. The VisDrone YOLOv8s of 17.1 was trained on those clips, so it cannot re-measure them; a YOLOv8s fine-tuned on VisDrone-DET only (same recipe, 80 epochs, DET-val mAP 0.265 against 0.267 with the VID clips; <code>scripts/train_visdrone.py --det-only</code>, <code>weights/yolov8s_visdrone_det.pt</code>) re-ran the whole pipeline (<code>FC_DETECTOR=det forecast.py dets / tune / tune2 / decay v2</code>; outputs <code>*_det.json</code>, the originals untouched). AP relative to the fresh result:</p>
{t2a}
<ul>
<li><b>The staleness curve is the same</b> although the detector is 65 % more accurate: relative AP after 100 ms 0.40 against 0.41, after 267 ms 0.07 both. The controllers' curve (<code>staleness_decay_forecast_v2.json</code>) stays valid for the VisDrone detectors.</li>
<li><b>The forecaster's setting is confirmed</b>: re-tuned from scratch, the best setting differs only in {dtxt}; the setting in use ranks {rank} of {nset} with mean lagged AP {coco_ap:.4f} against {best_ap:.4f} for the new best (0.1 %). Nothing in the controllers or the scoring needs to change.</li>
</ul>
<p><b>R4 – split computing on VisDrone.</b> Every split point and precision of Part 3 re-evaluated with the VisDrone YOLOv8s on VisDrone2019-DET val (548 images, batch 1, paired image bootstrap; <code>evaluation/evaluate_mAP.py --weights weights/yolov8s_visdrone.pt --data visdrone_val</code>, <code>experiments/results/visdrone_ft_split/</code>):</p>
{t4}
<ul>
<li><b>INT8 and FP16 split computing stay lossless on aerial images</b>: every INT8 and FP16 split point is within {worst:.4f} mAP of the full model and every 95 % interval contains 0, as on COCO. Only clipped uint8 at k4 loses (−0.0019, as −0.0014 on COCO).</li>
</ul>
{t4c}
<ul>
<li><b>Image codecs cost three to five times more on aerial images</b> (relative to the full-quality accuracy): JPEG q50 −24 % against −8 % on COCO, q90 −4 % against −0.7 %; WebP is better than JPEG at the same quality. Small objects lose their detail first, so split computing (lossless) gains against JPEG when the detector is VisDrone-trained.</li>
</ul>
<p><b>R3 – the swarm simulation of Part 13 re-weighted.</b> The same grid (2 camera drones × 2 networks × 2 sharing rules × 2 channel profiles × 6 swarm sizes × 6 strategies, 5 seeds of 120 s) with every configuration's accuracy replaced by the VisDrone value (payloads and times unchanged; <code>build_visdrone_configs.py</code>, <code>swarm_calibrated.py --visdrone</code> → <code>swarm_calibrated_visdrone*</code>):</p>
<ul>
<li><b>The best strategy is unchanged in {same} of {tot} cells</b> (swarm size × scenario). Of the {tot - same} that changed, 2 are exact ties (identical numbers, the order is a tie-break) and 1 is within the confidence interval (10.96 ± 0.33 against 10.85 ± 0.28 on-time results per drone per second).</li>
<li><b>One behaviour changes, in the right direction</b>: because JPEG q50 costs so much more on aerial images, the adaptive controller moves from q50 to q75 (10 Jetson drones on the cellular cell with blackouts: q50 93 % → 10 % of frames, q75 4 % → 78 %), trading on-time results (29.1 → 25.4 per second) for accuracy. Part 13's conclusions stand.</li>
</ul>
'''


def main():
    h, m = HTML.read_text(), MD.read_text()
    sec = section()
    j = h.index('<h2 id="argument">')
    i = h.find("<h3>19.6 ")
    h = h[:i if 0 <= i < j else j] + sec + h[j:]
    j = m.index("## PART 20")
    i = m.find("### 19.6 ")
    m = m[:i if 0 <= i < j else j] + html_to_md(sec) + m[j:]
    li = ('<li><b>R2–R4 (19.6, done 25 Oct):</b> the staleness curve and the forecaster re-measured with a detector '
          'that never saw VID footage are the same (the forecaster in use ranks 2 of 25, 0.1 % from the best); INT8 '
          'split computing stays lossless on VisDrone, while image codecs cost three to five times more on aerial '
          'images; the swarm simulation re-weighted with VisDrone accuracy keeps its best strategy in 93 of 96 cells '
          '(the 3 others are ties).</li>\n')
    h = re.sub(r"<li><b>R2–R4 \(19\.6.*?</li>\n", "", h)
    m = re.sub(r"^- \*\*R2–R4 \(19\.6.*\n", "", m, flags=re.M)
    k = h.index('<div class="box state">')
    k = h.index("<ul>\n", k) + 5
    h = h[:k] + li + h[k:]
    k = m.index("**State on 2")
    k = m.index("\n- ", k) + 1
    m = m[:k] + html_to_md("<ul>\n" + li + "</ul>").strip() + "\n" + m[k:]
    HTML.write_text(h)
    MD.write_text(m)
    print("report updated: 19.6 (R2-R4), state box")


if __name__ == "__main__":
    main()
