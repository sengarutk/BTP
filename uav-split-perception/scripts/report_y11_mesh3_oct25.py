#!/usr/bin/env python3
"""Report update, 25 Oct 2026: 17.7 (YOLO11 n/s/m fine-tuned on VisDrone, and onboard on the two Pis of the mesh,
the professor's request) and 18.10 (mesh campaign 3: the Jetson energy price with a 1.2 W budget, Jetson power
measured in both strategies). Numbers from onboard_sap/throttle_analysis_yolo11.json (+ _visdrone for YOLOv8),
onboard_sap/onboard_sap_emulated.json, variant_accuracy_visdrone_ft11.json, vid_campaign_mesh3_summary.json.
Run after report_mesh2_oct24.py and report_c7_oct25.py. Idempotent.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_parts_oct22 import HTML, MD, html_to_md, table  # noqa: E402

HW = Path(__file__).resolve().parent.parent / "experiments" / "results" / "hardware"
OS = HW / "onboard_sap"
NAME = {"n640y11": "YOLO11n", "s640y11": "YOLO11s", "m640y11": "YOLO11m",
        "s640vd": "YOLOv8s", "m640vd": "YOLOv8m", "l640vd": "YOLOv8l"}
CN = {"short_hot": "hot short", "short_cool": "cool short", "long_cool": "long"}


def onboard_rows(summ, models):
    rows = []
    for m in models:
        for c in ("short_hot", "short_cool", "long_cool"):
            x = summ[c].get(m)
            if x is None:
                continue
            rows.append([f"{NAME[m]}, {CN[c]} ({x['n']})", f"{x['fresh_AP']:.3f}", f"{x['sAP']:.4f}",
                         f"<b>{x['sAP_fc']:.4f}</b>", f"{x['sAP50']:.4f}", f"{x['lat_ms']:.0f} ms", f"{x['pi_w']:.2f} W",
                         f"{x['temp_start']:.0f} → {x['temp_mean']:.0f} °C", f"{x['clock_mhz']:.0f} MHz",
                         f"{100 * x['throttled_share']:.0f} %"])
    return rows


def section_17_7():
    y = json.load(open(OS / "throttle_analysis_yolo11.json"))
    v = json.load(open(OS / "throttle_analysis_visdrone.json"))
    acc = json.load(open(HW / "variant_accuracy_visdrone_ft11.json"))
    emu = json.load(open(OS / "onboard_sap_emulated.json"))
    t_train = table(["Model", "YOLOv8 (Part 17.1)", "YOLO11", "difference"],
                    [[s, f"{acc[f'yolov8{s}_visdrone_640_raw']:.3f}", f"<b>{acc[f'yolo11{s}_visdrone_640_raw']:.3f}</b>",
                      f"{acc[f'yolo11{s}_visdrone_640_raw'] - acc[f'yolov8{s}_visdrone_640_raw']:+.3f}"] for s in "nsm"])
    head = ["Model, runs", "mAP of delivered results", "sAP", "sAP + forecaster", "sAP50", "time per frame", "Pi power",
            "temp start → mean", "clock", "throttled-time ratio"]
    t_on = table(head, onboard_rows(y["summary"], ("n640y11", "s640y11", "m640y11"))
                 + onboard_rows(v["summary"], ("s640vd", "m640vd")))
    fc = y["counterfactual_full_clock"]
    t_cf = table(["Model (all runs)", "time per frame: measured → at 2.4 GHz", "sAP + forecaster: measured → at 2.4 GHz"],
                 [[NAME[m], f"{min(fc[c][m]['lat_ms'] for c in fc):.0f}–{max(fc[c][m]['lat_ms'] for c in fc):.0f} → "
                   f"{min(fc[c][m]['lat_full_clock_ms'] for c in fc):.0f}–{max(fc[c][m]['lat_full_clock_ms'] for c in fc):.0f} ms",
                   f"{min(fc[c][m]['sAP_fc_measured'] for c in fc):.4f}–{max(fc[c][m]['sAP_fc_measured'] for c in fc):.4f} → "
                   f"{min(fc[c][m]['sAP_fc_full_clock'] for c in fc):.4f}–{max(fc[c][m]['sAP_fc_full_clock'] for c in fc):.4f}"]
                  for m in ("n640y11", "s640y11", "m640y11")])
    t_emu = table(["Delay", "YOLOv8s", "YOLO11s", "YOLOv8m", "YOLO11m", "YOLO11n"],
                  [[f"{L} ms"] + [f"{emu[k]['by_latency_ms'][L]['sAP_fc2']:.4f}" for k in
                                  ("yolov8s_vd", "yolo11s_vd", "yolov8m_vd", "yolo11m_vd", "yolo11n_vd")]
                   for L in ("100", "300", "600", "1000", "2000")]
                  + [["fresh AP (no delay)"] + [f"{emu[k]['fresh_AP']:.3f}" for k in
                                               ("yolov8s_vd", "yolo11s_vd", "yolov8m_vd", "yolo11m_vd", "yolo11n_vd")]])
    S = y["summary"]
    n_, s_, m_ = S["short_cool"]["n640y11"], S["short_cool"]["s640y11"], S["short_cool"]["m640y11"]
    v8s = v["summary"]["short_cool"]["s640vd"]
    return f'''<h3>17.7 YOLO11 n, s and m: fine-tuned on VisDrone and onboard on the Pi (25 Oct 2026)</h3>
<p>The professor asked for YOLO11, specifically n, s and m. They were fine-tuned exactly as YOLOv8 in 17.1 (the same data, 640 px, seed 0, COCO weights as the start; <code>scripts/train_visdrone.py</code>; n and s 80 epochs, m 60; training stops early after 20 epochs without improvement on DET val, which ended YOLO11s at epoch 76 with its best at 56), then run onboard exactly as 17.2 (static_good, one model alone on the Pi, 2 runs started hot, 2 started cool, 1 of 24 minutes, on each of the two Pi 5s; the camera drone pi-relayyy and pi-sender, both on the mesh, no network traffic involved: <code>validation/hardware/tools/campaign_onboard_y11.sh</code>, 30 runs; scored by <code>onboard_throttle_analysis.py --weights yolo11</code>). Weights <code>weights/yolo11{{n,s,m}}_visdrone.pt</code>.</p>
<p>Detection accuracy (mAP50-95 on VisDrone2019-DET val, the same evaluator for both families):</p>
{t_train}
<p>Onboard on the Pi 5 (YOLOv8s and m from 17.3 for comparison; mean over both Pis):</p>
{t_on}
<p>The same detections scored at a fixed delay (the emulation of 17.5: sAP with the forecaster, as if every result arrived that long after its frame):</p>
{t_emu}
<p>What the full clock would give (as 17.4):</p>
{t_cf}
<ul>
<li><b>YOLO11 matches or beats YOLOv8 at the same size</b>: n equal, s +0.002, m +0.016 mAP50-95 on VisDrone DET val; YOLO11m (0.314) reaches YOLOv8l (0.313) with fewer than half the parameters.</li>
<li><b>YOLO11n is the best detector to run on the Pi.</b> It needs about {n_['lat_ms']:.0f} ms per frame, so its results are far fresher than any other model's: sAP with the forecaster {n_['sAP_fc']:.3f}, about {n_['sAP_fc'] / v8s['sAP_fc']:.1f}× YOLOv8s ({v8s['sAP_fc']:.3f}) and {n_['sAP_fc'] / s_['sAP_fc']:.1f}× YOLO11s ({s_['sAP_fc']:.3f}), although its mAP is lower ({n_['fresh_AP']:.3f} against {s_['fresh_AP']:.3f}). For an onboard detector, speed buys more streaming accuracy than a larger model does. It also heats the Pi less: throttled {100 * n_['throttled_share']:.0f} % of a cool short run, against {100 * s_['throttled_share']:.0f} % for YOLO11s and {100 * m_['throttled_share']:.0f} % for YOLO11m.</li>
<li><b>At the same size, YOLO11 and YOLOv8 behave alike onboard.</b> YOLO11s and YOLOv8s take the same time per frame on the Pi (720–750 ms) and reach the same sAP. YOLO11m is about 15 % slower than YOLOv8m on the Pi's CPU (1.88–2.02 s against 1.62–1.73 s in 17.3), so its higher accuracy is lost to the delay: sAP with the forecaster 0.005–0.007, against 0.006–0.008 for YOLOv8m.</li>
<li><b>Throttling costs the same as for YOLOv8</b>: at the full 2.4 GHz clock sAP with the forecaster would be 30–50 % higher for n, 45–75 % for s and 85–125 % for m; over 24 minutes the clock sinks (n 1988 → 1663 MHz, m 1677 → 1404 MHz) and inference slows by 7–9 %.</li>
<li>The conclusion of 17.5 stands with YOLO11: onboard detection alone stays far below offloading (0.17–0.21 sAP with the forecaster on the mesh, 18.9), and the best onboard choice is the smallest, fastest model.</li>
</ul>
'''


def section_18_10():
    s = json.load(open(HW / "vid_campaign_mesh3_summary.json"))
    c, p = s["cells"], s["paired"]
    SC = {"static_good": "normal", "mesh_mission": "mesh mission", "multihop": "multihop", "ALL": "all three"}
    rows = []
    for sc in ("static_good", "mesh_mission", "multihop", "ALL"):
        for m, nm in (("v41", "v4.1"), ("v41e12", "v4.1 + Jetson energy (1.2 W)")):
            x = c[f"{sc}|{m}"]
            rows.append([SC[sc], nm, x["n"], f"<b>{x['sAP_fc'][0]:.3f} ± {x['sAP_fc'][1]:.3f}</b>", f"{x['mAP'][0]:.3f}",
                         f"{x['p_aoi300'][0]:.3f}", f"{x['deadline_met_fps'][0]:.1f}", f"{x['pi_w'][0]:.2f} W",
                         f"{x['jetson_w'][0]:.2f} W"])
    t1 = table(["Scenario", "Strategy", "runs", "sAP + forecaster", "mAP", "P(AoI ≤ 300 ms)", "deadline-met /s",
                "Pi power", "Jetson power (measured)"], rows)
    pr = []
    for sc in ("static_good", "mesh_mission", "multihop", "ALL"):
        r = p[f"v41e12-v41|{sc}"]
        f = lambda k: f"{r[k]['mean_diff']:+.4f} ({r[k]['first_ahead']}/{r[k]['pairs']}, p {r[k]['p_perm']:.3f})"  # noqa: E731
        pr.append([SC[sc], f("sAP_fc"), f("deadline_met_fps"), f("jetson_w"), f("pi_w")])
    t2 = table(["Scope", "Δ sAP + fc", "Δ deadline-met /s", "Δ Jetson power (W)", "Δ Pi power (W)"], pr)
    A, M = p["v41e12-v41|ALL"], p["v41e12-v41|multihop"]
    return f'''<h3>18.10 Mesh campaign 3: the Jetson energy price with a realistic budget (25 Oct 2026)</h3>
<p>18.9 found the Jetson energy price costly at a 0.5 W budget that the Jetson could never meet. Here it runs with a budget of 1.2 W of extra Jetson power, between the Jetson's unpriced draw in the normal (about 1.0 W) and mission (about 1.4 W) scenarios, against v4.1 in the same campaign: 2 strategies × 3 scenarios × 3 repetitions = 18 runs, same mesh, same day, same camera code. The camera now logs the Jetson's measured board power in every strategy (<code>edge_w_log</code>), so the energy saved is measured. Every run was checked against the laptop ping log (no run lost a ping); <code>tools/campaign_mesh3.sh</code>, <code>experiments/results/hardware/vid_campaign_mesh3*</code>.</p>
{t1}
<p>Paired (same scenario and repetition; first number v4.1 + Jetson energy minus v4.1):</p>
{t2}
<ul>
<li><b>With a realistic budget the price acts only where the Jetson carries the stream.</b> In the normal scenario it never rises (identical results); in multihop it lowers the Jetson's power by {-M['jetson_w']['mean_diff']:.2f} W (about 4 % of its {c['multihop|v41']['jetson_w'][0]:.2f} W, 3/3 pairs) for {M['sAP_fc']['mean_diff']:+.4f} sAP.</li>
<li><b>It now costs almost nothing</b>: {A['sAP_fc']['mean_diff']:+.4f} sAP with the forecaster over all 9 pairs (p = {A['sAP_fc']['p_perm']:.3f}), against −0.016 at the 0.5 W budget, and it returns slightly more results per second ({A['deadline_met_fps']['mean_diff']:+.2f}/s, p = {A['deadline_met_fps']['p_perm']:.3f}).</li>
<li><b>But it can save little on this hardware</b>: the Jetson draws about 4.1 W idle and 5.0–5.7 W while detecting, so pricing its inference can change at most the 1–1.5 W on top of idle. The Jetson energy price is worth having only when the edge drone's battery is the binding limit; on these boards the camera drone's energy and heat (18.9) matter more.</li>
</ul>
'''


def main():
    h, m = HTML.read_text(), MD.read_text()
    s7, s10 = section_17_7(), section_18_10()
    j = h.index('<h2 id="relay">')
    i = h.find("<h3>17.7 ")
    h = h[:i if 0 <= i < j else j] + s7 + h[j:]
    j = m.index("## PART 18")
    i = m.find("### 17.7 ")
    m = m[:i if 0 <= i < j else j] + html_to_md(s7) + m[j:]
    j = h.index('<h2 id="rescore">')
    i = h.find("<h3>18.10 ")
    h = h[:i if 0 <= i < j else j] + s10 + h[j:]
    j = m.index("## PART 19")
    i = m.find("### 18.10 ")
    m = m[:i if 0 <= i < j else j] + html_to_md(s10) + m[j:]
    # what is left: the Jetson re-test is done
    done = ('<tr><td><s>Jetson energy price with a realistic budget</s> <b>Done 25 Oct</b> (18.10): costs almost nothing, '
            'saves about 4 % of the Jetson\'s power where it carries the stream</td><td>—</td><td>—</td></tr>\n')
    h = re.sub(r"<tr><td>Jetson energy price with a budget.*?</tr>\n", done, h, 1)
    m = re.sub(r"^\| Jetson energy price with a budget.*\n",
               "| <s>Jetson energy price with a realistic budget</s> **Done 25 Oct** (18.10): costs almost nothing, saves "
               "about 4 % of the Jetson's power where it carries the stream | — | — |\n", m, 1, flags=re.M)
    # state box
    li = ('<li><b>YOLO11 and mesh campaign 3 (17.7, 18.10, done 25 Oct):</b> YOLO11 n/s/m fine-tuned on VisDrone '
          '(mAP 0.211 / 0.269 / 0.314, equal to or above YOLOv8); onboard on the Pi YOLO11n is the best detector '
          '(sAP with forecaster about 0.047, ~2.7× YOLOv8s) because it is fastest; the Jetson energy price at a '
          '1.2 W budget costs almost nothing and saves about 4 % of the Jetson\'s power in multihop.</li>\n')
    h = re.sub(r"<li><b>YOLO11 and mesh campaign 3 \(17\.7.*?</li>\n", "", h)
    m = re.sub(r"^- \*\*YOLO11 and mesh campaign 3 \(17\.7.*\n", "", m, flags=re.M)
    k = h.index('<div class="box state">')
    k = h.index("<ul>\n", k) + 5
    h = h[:k] + li + h[k:]
    k = m.index("**State on 2")
    k = m.index("\n- ", k) + 1
    m = m[:k] + html_to_md("<ul>\n" + li + "</ul>").strip() + "\n" + m[k:]
    HTML.write_text(h)
    MD.write_text(m)
    print("report updated: 17.7 (YOLO11), 18.10 (mesh campaign 3), what is left, state box")


if __name__ == "__main__":
    main()
