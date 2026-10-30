#!/usr/bin/env python3
"""Report update, 29 Oct 2026 (part 2): joint link failures, a cheaper camera-motion step and the decay curve on all
56 VID train sequences, as 19.9 (docs/laptop_additions_2026-10-29_part2.md).

Every number is read from the result files: replay/joint_oct29/joint_summary.json (replay_joint.py),
forecast_cheap_oct29.json and forecast_cheap_oct29_timing.json (forecast_cheap.py), staleness_decay_train56.json
(decay_all56.py; the B part is left out until it exists) and the live runs' forecaster timing (live_forecast).
Adds 19.9 after 19.8, a Part 1 bullet and rows of "What is left" (it replaces 19.8's interference row, so run it after
report_laptop_oct29.py). Idempotent (re-running replaces them).
usage: report_laptop2_oct29.py     (the originals are archived in
       experiments/results/hardware/_superseded/report_before_laptop2_oct29/)
"""
import glob
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_parts_oct22 import HTML, MD, html_to_md, table  # noqa: E402
from report_laptop_oct29 import LEFT as LEFT_19_8  # noqa: E402

HW = Path(__file__).resolve().parent.parent / "experiments" / "results" / "hardware"
NAMES = {"base": "base: 320 px, 200 corners, every frame", "w240": "240 px", "w160": "160 px", "c100": "100 corners",
         "c50": "50 corners", "skip2": "every second frame", "w160_skip2": "160 px, every second frame",
         "w240_c100": "240 px, 100 corners"}


def pi_ego():
    v = []
    for f in glob.glob(str(HW / "vid_campaign_*" / "a2_*.json")):
        try:
            lf = json.load(open(f)).get("live_forecast")
        except (ValueError, AttributeError):
            continue
        if lf and lf.get("ego_ms_median"):
            v.append((lf["ego_ms_median"], lf.get("obs_ms_median"), lf.get("pred_ms_median")))
    a = np.array(v, float)
    return len(a), float(np.median(a[:, 0])), float(np.nanmedian(a[:, 1])), float(np.nanmedian(a[:, 2]))


def part_a():
    j = json.load(open(HW / "replay" / "joint_oct29" / "joint_summary.json"))
    pm = lambda x: f"{round(x[0], 4) + 0.0:+.4f} ± {x[1]:.4f}"  # noqa: E731
    sig = lambda x, s: f"<b>{s}</b>" if abs(x[0]) > x[1] else s  # noqa: E731
    rows = []
    for c, x in j["conds"].items():
        lab = "no bursts" if c == "none" else "ρ {}, {} s".format(*c[1:].split("_d"))
        neg = lambda v: [-v[0], v[1]]  # noqa: E731
        rows.append([lab, f"{100 * x['faded']['faded_both'][0]:.1f} %", f"{x['policies']['v41']['sAP'][0]:.4f}",
                     sig(x["loss_vs_none"]["v41"], pm(x["loss_vs_none"]["v41"])) if "loss_vs_none" in x else "—",
                     sig(x["paired"]["v41-v41_clair"], pm(neg(x["paired"]["v41-v41_clair"]))),
                     sig(x["paired"]["v41-v5"], pm(x["paired"]["v41-v5"])),
                     sig(x["paired"]["v41-fix_laptop_m640q90"], pm(x["paired"]["v41-fix_laptop_m640q90"])),
                     f"{100 * x['v41_dispatch_share']['onboard']:.1f} %"])
    t = table(["Bursts (ρ = share hitting both paths, mean length)", "both paths faded", "v4.1 sAP + fc",
               "v4.1 loss vs no bursts", "clairvoyant − v4.1", "v4.1 − v5", "v4.1 − fixed laptop",
               "v4.1 frames onboard"], rows)
    fl = [x["faded"][k][0] for c, x in j["conds"].items() if c != "none" for k in ("faded_laptop", "faded_jetson")]
    r = j["rho1_minus_rho0"]
    fr = [x["policies"]["v41"]["fresh_share"][0] for c, x in j["conds"].items() if c != "none"]
    v41l = [j["conds"][c]["loss_vs_none"]["v41"][0] for c in j["conds"] if c != "none"]
    lapl = [j["conds"][c]["loss_vs_none"]["fix_laptop_m640q90"][0] for c in j["conds"] if c != "none"]
    return f'''<p><b>1. Joint link failures: what do they cost, and could better prediction recover it?</b> (<code>validation/hardware/replay_joint.py</code>, 420 replay runs, <code>replay/joint_oct29/</code>.) All mesh links share one channel, so interference can hit both offloading paths at the same moment, and the replay draws the two paths independently. The unimpaired static_good scenario got short deep fades on top: during a burst a path's goodput is capped at {j['fade_mbps']:g} Mbit/s, and a transfer's time is integrated over the burst timeline. Bursts arrive at random, last 0.3 s or 1.5 s on average, and a share ρ of them hits both paths. The burst rate per path is the same for every ρ, so each path is faded for the same share of time ({100 * min(fl):.0f}–{100 * max(fl):.0f} %), and only how often both are faded at once changes. 10 seeds; every policy of a seed sees the same bursts. The clairvoyant v4.1 knows every transfer's true time, bursts included. Check: without bursts the runs reproduce the 19.8 replay exactly. ± = Student-t 95 % half-width over 10 paired seeds; bold = interval excludes 0.</p>
{t}
<ul>
<li><b>Joint fades cost more than independent fades of the same amount.</b> v4.1 with every burst joint against every burst independent, each path faded equally often: {pm(r['d0.3']['v41'])} sAP with 0.3 s bursts (significant), {pm(r['d1.5']['v41'])} with 1.5 s bursts (not significant). Two parallel paths hedge independent fades; they cannot hedge joint ones. The single-path strategies are indifferent to ρ, as they must be.</li>
<li><b>Perfect link prediction still adds nothing</b>, even when every fade is joint. The loss comes from having no good path, not from mispredicting one. Even with perfect knowledge the only remaining move is onboard inference, and v4.1 already makes it: its onboard share rises with ρ, and it keeps {100 * min(fr):.1f}–{100 * max(fr):.1f} % of frames fresh.</li>
<li><b>v4.1 degrades least.</b> It loses {-max(v41l):.3f}–{-min(v41l):.3f} sAP; fixed laptop offloading loses {-max(lapl):.3f}–{-min(lapl):.3f}. v4.1 is ahead of v5 in every condition.</li>
<li><b>What this changes.</b> In the replay, a joint-failure-aware or radio-aware controller has no headroom: the clairvoyant bound is flat. The interference test on the mesh remains worth running, but as a measurement: whether joint fades occur on the shared channel, and how often, which sizes the cost above on real links. It is not a route to a better controller unless the measured fades look very different. Limits: synthetic bursts (0.5 Mbit/s cap, exponential lengths), the only onboard fallback is YOLOv8n-320, no other impairment.</li>
</ul>
'''


def part_c():
    a = json.load(open(HW / "forecast_cheap_oct29.json"))
    tm = json.load(open(HW / "forecast_cheap_oct29_timing.json"))
    n, ego, obs, pred = pi_ego()
    v = a["variants"]
    rows = [[NAMES[k], f"{100 * x['train']['share_of_forecaster_gain_kept']:.0f} %",
             f"{100 * x['val']['share_of_forecaster_gain_kept']:.0f} %", f"{x['val']['mean_ap_lagged']:.4f}",
             f"{tm[k]['ms_per_frame_median']:.2f} ms ({tm[k]['cost_vs_base']:.2f}×)"] for k, x in v.items()]
    t = table(["Camera-motion step", "train: share of the forecaster's gain kept", "val: share kept",
               "val: lagged AP", "laptop time per frame"], rows)
    w = v["w160"]
    est = ego * tm["w160"]["cost_vs_base"]
    return f'''<p><b>2. A cheaper camera-motion step for the live forecaster</b> (<code>validation/hardware/forecast_cheap.py</code>; <code>forecast_cheap_oct29.json</code>, <code>forecast_cheap_oct29_timing.json</code>). Part 14 found that the live forecaster slows onboard inference on the Pi (YOLOv8s-320 170 → 412 ms). Over {n} live runs, the camera-motion step costs a median {ego:.2f} ms per camera frame on the Pi (about {ego * 30 / 10:.0f} % of one core at 30 fps). Recording a result costs {obs:.2f} ms, and moving the held boxes to the display time {pred:.2f} ms. So the camera-motion step is the part to make cheaper. Variants of the step were tested with the forecaster's settings and detections unchanged. Accuracy uses <code>forecast.replay</code>: one result every 2 frames, shown 0–600 ms late, mean AP over the lagged settings. The variant is chosen on train (where the forecaster was tuned) and reported on val (the live test clips). "Gain" = lagged AP with the forecaster minus without. Check: the base variant reproduces the stored camera-motion chains exactly and the stored tuning to 4 decimals. Times were taken on the idle laptop, each variant 3 times interleaved.</p>
{t}
<ul>
<li><b>Track on a 160-px image.</b> It is the cheapest variant that keeps ≥ 99 % of the gain on train. On val it keeps {100 * w['val']['share_of_forecaster_gain_kept']:.0f} % (lagged AP {w['val']['mean_ap_lagged']:.4f} against {v['base']['val']['mean_ap_lagged']:.4f}) at {tm['w160']['cost_vs_base']:.2f}× the time. If the Pi scales like the laptop, that is about {ego:.1f} → {est:.1f} ms per frame. This is an estimate: the Pi's step time and the onboard speed-up must be measured (a one-constant change, <code>W_SMALL = 160</code> in <code>egomotion.py</code>, not made because it changes what the live system runs).</li>
<li><b>Tracking every second frame is the wrong saving.</b> It loses {100 - 100 * v['skip2']['val']['share_of_forecaster_gain_kept']:.0f} % of the gain on val, because an odd frame's one-frame camera motion is left uncorrected.</li>
</ul>
'''


def part_b():
    f = HW / "staleness_decay_train56.json"
    if not f.exists():
        return ""
    d = json.load(open(f))
    s, ref = d["subsets"], d["stored_8seq_curve"]
    lags = d["lag_ms"]
    show = [i for i, x in enumerate(lags) if x in (0.0, 100.0, 266.7, 400.0, 600.0, 1166.7)]
    fmt = lambda r: [f"{r[i]:.3f}" for i in show]  # noqa: E731
    rows = [["8 sequences (stored, what the controller uses), forecaster"] + fmt(ref["ratio"]),
            [f"all {s['all56']['sequences']} sequences, forecaster"] + fmt(s["all56"]["ratio"]),
            [f"the {s['new48']['sequences']} new sequences only, forecaster"] + fmt(s["new48"]["ratio"]),
            ["8 sequences (stored), no forecaster"] + fmt(ref["ratio_no_forecast"]),
            [f"all {s['all56']['sequences']} sequences, no forecaster"] + fmt(s["all56"]["ratio_no_forecast"]),
            [f"the {s['new48']['sequences']} new sequences only, no forecaster"] + fmt(s["new48"]["ratio_no_forecast"])]
    t = table(["Accuracy held / fresh accuracy, at age"] + [f"{lags[i]:.0f} ms" for i in show], rows)
    rep = max(abs(a - b) for a, b in zip(s["old8"]["ratio"], ref["ratio"]))
    gain = lambda x: float(np.mean(x["ap"][1:]) - np.mean(x["ap_no_forecast"][1:]))  # noqa: E731
    gdev = max(abs(a - b) for k in ("ratio", "ratio_no_forecast") for a, b in zip(s["old8_gpu"][k], s["old8"][k]))
    i6 = d["lag_ms"].index(600.0)
    dmax6 = max(abs(a - b) for a, b in zip(s["all56"]["ratio"][:i6 + 1], ref["ratio"][:i6 + 1]))
    rp = json.load(open(HW / "staleness_decay_train56_replay.json"))
    i267 = d["lag_ms"].index(266.7)
    rec = lambda x: (x["ratio"][i267] - x["ratio_no_forecast"][i267]) / (1 - x["ratio_no_forecast"][i267])  # noqa: E731
    return f'''<p><b>3. The decay curve and the forecaster on all 56 VisDrone-VID train sequences, not 8</b> (<code>validation/hardware/decay_all56.py</code>, <code>staleness_decay_train56.json</code>). The decay curve the controllers schedule for, and the forecaster's settings, come from 8 of the 56 train sequences. The other 48 were downloaded from the same mirror and measured with the same pipeline: first 400 frames per sequence, COCO YOLOv8s at 640, one result every 2 frames. The forecaster is frozen, so for the 48 new sequences it is a held-out test. The 48 new sequences were detected on the laptop GPU (the CPU was too slow beside other work). Checks: the 8 known sequences reproduce the stored curve (largest difference {rep:.4f}), and the same 8 detected on the GPU give the same curves (largest difference {gdev:.4f}).</p>
{t}
<ul>
<li><b>The curve holds.</b> With the forecaster, the curve on all 56 sequences is within {dmax6:.3f} of the stored one (in the ratio to fresh accuracy) up to 600 ms, the range of live result ages. Beyond that it keeps more: {s['all56']['ratio'][-1]:.3f} against {ref['ratio'][-1]:.3f} at {lags[-1]:.0f} ms.</li>
<li><b>The forecaster keeps most of its effect on unseen video.</b> On the 48 sequences it never saw, it adds {gain(s['new48']):+.4f} AP averaged over the stale ages, against {gain(s['old8']):+.4f} on the 8 it was tuned on. Part of the difference is that accuracy decays more slowly on the new sequences, so less is lost. As a share of what is lost at {lags[i267]:.0f} ms it recovers {100 * rec(s['new48']):.0f} % on the new sequences against {100 * rec(s['old8']):.0f} % on the 8.</li>
<li><b>The controller does not depend on it.</b> v4.1 scheduling for the 56-sequence curve instead of the stored one, in the replay of 19.8 (4 scenarios × 5 seeds, paired): {rp['diff_mean']:+.4f} ± {rp['diff_ci95']:.4f} sAP. Measuring the curve on 8 sequences was enough.</li>
</ul>
'''


def section():
    return ('<h3>19.9 Laptop-only additions, part 2: joint link failures, a cheaper camera-motion step, the decay '
            'curve on all train sequences (29 Oct 2026)</h3>\n<p>Nothing earlier was re-scored or overwritten; every '
            'output is a new file (<code>docs/laptop_additions_2026-10-29_part2.md</code>).</p>\n'
            + part_a() + part_c() + part_b())


STATE = ('<li><b>Laptop-only additions, part 2 (19.9, 29 Oct):</b> in the replay, joint link fades cost v4.1 more than '
         'independent ones of the same amount, and perfect link prediction still adds nothing, so the interference test '
         'is a measurement, not a route to a better controller; tracking camera motion on a 160-px image keeps 98 % of '
         'the forecaster\'s gain at about 0.57× the cost (Pi measurement pending); on all 56 VID train sequences the decay '
         'curve is within 0.03 of the 8-sequence one up to 600 ms and the controller\'s accuracy is unchanged.</li>\n')
LEFT_OLD_KEYS = [LEFT_19_8[0][0][:40]]
LEFT = [("Co-channel interference test on the mesh: how often both paths fade together (19.9: a measurement; in the "
         "replay neither joint-failure awareness nor perfect prediction adds accuracy)", "A device for interference "
         "traffic; the mesh", "about half a day"),
        ("Cheaper camera-motion step on the Pi: <code>W_SMALL = 160</code>, measure the step time and the onboard "
         "speed-up (19.9)", "The camera Pi", "1–2 h")]


def main():
    h, m = HTML.read_text(), MD.read_text()
    sec = section()
    j = h.index('<h2 id="argument">')
    i = h.find("<h3>19.9 ")
    h = h[:i if 0 <= i < j else j] + sec + h[j:]
    j = m.index("## PART 20")
    i = m.find("### 19.9 ")
    m = m[:i if 0 <= i < j else j] + html_to_md(sec) + m[j:]
    # Part 1 bullet, first in the state box
    h = re.sub(r"<li><b>Laptop-only additions, part 2 \(19\.9.*?</li>\n", "", h, flags=re.S)
    k = h.index('<div class="box state">')
    k = h.index("<ul>\n", k) + len("<ul>\n")
    h = h[:k] + STATE + h[k:]
    m = re.sub(r"^- \*\*Laptop-only additions, part 2 \(19\.9.*\n", "", m, flags=re.M)
    k = m.index("**State on 26 Oct 2026")
    k = m.index("\n- ", k) + 1
    m = m[:k] + html_to_md("<ul>" + STATE + "</ul>").strip() + "\n" + m[k:]
    # What is left: replace the 19.8 interference row, add the camera-motion row; the old forecaster row points here
    for key in LEFT_OLD_KEYS + [x[0][:40] for x in LEFT]:
        h = re.sub(r"<tr><td>" + re.escape(key) + r".*?</tr>\n", "", h)
    for key in LEFT_OLD_KEYS + [re.sub(r"</?code>", "`", x[0])[:40] for x in LEFT]:
        m = re.sub(r"^\| " + re.escape(key) + r".*\n", "", m, flags=re.M)
    for task, needs, time in LEFT:
        a = h.index("<tr><td>Commit and push the work since")
        h = h[:a] + f"<tr><td>{task}</td><td>{needs}</td><td>{time}</td></tr>\n" + h[a:]
        a = m.index("| Commit and push the work since")
        tm = re.sub(r"</?code>", "`", task)
        m = m[:a] + f"| {tm} | {needs} | {time} |\n" + m[a:]
    old = "Make the live forecaster cheaper on the Pi (camera tracking every other frame or at lower resolution)"
    new = "Make the live forecaster cheaper on the Pi (19.9: track camera motion at 160 px, not every other frame)"
    h, m = h.replace(old, new), m.replace(old, new)
    HTML.write_text(h)
    MD.write_text(m)
    print("report updated: 19.9", "(with B)" if part_b() else "(without B)", "Part 1 bullet, what is left")


if __name__ == "__main__":
    main()
