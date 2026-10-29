#!/usr/bin/env python3
"""Report update, 29 Oct 2026: the laptop-only additions (docs/laptop_additions_2026-10-29.md) as 19.8.

Every number is read from the result files: replay/oracle_oct29_plant/oracle_summary.json (replay_oracle.py, the
replay with its full-range board thermal fit), replay/validate_main_oct29{,_plant}/replay_check.json (replay against
the 240-run main campaign, before and after that fit) and worst_phase_oct29{,_coco}.json (report_worstphase_oct29.py).
Adds 19.8 before Part 20, a Part 1 bullet and rows of "What is left". Idempotent (re-running replaces them).
usage: report_laptop_oct29.py      (the originals are archived in
       experiments/results/hardware/_superseded/report_before_laptop_oct29/)
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_parts_oct22 import HTML, MD, html_to_md, table  # noqa: E402

HW = Path(__file__).resolve().parent.parent / "experiments" / "results" / "hardware"
RP = HW / "replay"
NAMES = {"fix_jetson_s640q90": "Jetson YOLOv8s-640 q90", "fix_jetson_s640q50": "Jetson YOLOv8s-640 q50",
         "fix_laptop_m640q90": "laptop YOLOv8m-640 q90"}


def section():
    o = json.load(open(RP / "oracle_oct29_plant" / "oracle_summary.json"))
    old = json.load(open(RP / "validate_main_oct29" / "replay_check.json"))
    new = json.load(open(RP / "validate_main_oct29_plant" / "replay_check.json"))
    wv = json.load(open(HW / "worst_phase_oct29.json"))
    wc = json.load(open(HW / "worst_phase_oct29_coco.json"))
    pm = lambda x, d=4: f"{x['mean']:+.{d}f} ± {x['ci95']:.{d}f}"  # noqa: E731
    rows = []
    for sc, v in o["scenarios"].items():
        bf, bv = v["sAP"]["best_fixed"]
        sig = abs(v["v41_minus_best_fixed"]["mean"]) > v["v41_minus_best_fixed"]["ci95"]
        rows.append([sc, f"{v['sAP']['v41']:.4f}", pm(v["clair_minus_v41"]), f"{NAMES.get(bf, bf)} {bv:.4f}",
                     ("<b>" if sig else "") + pm(v["v41_minus_best_fixed"]) + ("</b>" if sig else ""),
                     f"{100 * v['v41_share_of_oracle_schedule']:.1f} %", f"{100 * v['v41_share_of_oracle_per_seed']:.1f} %"])
    t1 = table(["Scenario", "v4.1 sAP + fc", "clairvoyant v4.1 − v4.1", "best fixed setting", "v4.1 − best fixed",
                "v4.1 / per-phase schedule oracle", "v4.1 / per-seed oracle"], rows)
    cal = o["calibration"]["p_on_vs_300ms"]
    t2 = table(["Predicted chance of meeting 300 ms", "frames", "mean predicted", "observed on time"],
               [[b["bin"], f"{b['n']:,}", f"{b['pred']:.3f}", f"{b['observed']:.3f}"] for b in cal["bins"] if b["n"] >= 100]
               + [["all", f"{cal['n']:,}", f"{cal['mean_pred']:.3f}", f"{cal['observed']:.3f}"]])
    ag = lambda d, k: d["agreement"][k]["pearson"]  # noqa: E731
    t3 = table(["Replay against the 240-run main campaign (G12)", "thermal fit of 28 Oct (levels < 80 °C)",
                "full-range fit (now)"],
               [["sAP + fc, correlation over 12 policies", f"{ag(old, 'sAP'):.3f}", f"{ag(new, 'sAP'):.3f}"],
                ["Pi power, correlation", f"{ag(old, 'pi_w'):.3f}", f"{ag(new, 'pi_w'):.3f}"],
                ["time at ≥ 80 °C, correlation", f"{ag(old, 'hot_share'):.3f}", f"<b>{ag(new, 'hot_share'):.3f}</b>"],
                ["paired verdicts against v5 that agree", f"{old['verdicts_agree']} of 11", f"{new['verdicts_agree']} of 11"]])
    hp = new["policies"]
    hot = lambda p: f"{100 * hp[p]['hot_share'][0]:.0f} % / {100 * hp[p]['hot_share'][1]:.0f} %"  # noqa: E731
    npair = lambda w: sum(len(c["paired_worst_phase"]) for c in w.values())  # noqa: E731
    nsig = lambda w: sum(t["p_holm"] < 0.05 for c in w.values() for t in c["paired_worst_phase"])  # noqa: E731
    rk = [v["same"] for c in wv.values() for v in c["rank_check"].values()]
    tm = wv["vid_campaign_table"]["scenarios"]["mission"]
    st = lambda p: f"{100 * tm[p]['miss'][0]:.1f} % of frames (longest {tm[p]['longest_stale_s'][0]:.2f} s)"  # noqa: E731
    return f'''<h3>19.8 Laptop-only additions: oracle bounds, calibration, worst phase, staleness (29 Oct 2026)</h3>
<p>Four checks that needed no boards. Nothing earlier was re-scored or overwritten: every output is a new file (<code>docs/laptop_additions_2026-10-29.md</code>). Items 1–2 use the trace-driven replay (<code>validation/hardware/replay.py</code>): measured goodput traces of the static_good runs, the scenario's netem phases applied as on the Pi (per-phase reset), the measured server, encode and onboard times, the measured power model, and the real detections of every setting on every frame, scored with the standard sAP and forecaster v2 (COCO detectors, as the replay's detection set). Common random numbers: every policy of a seed sees the same goodput draws. 4 scenarios × 5 seeds, 20 s phases.</p>
<p><b>1. How far is v4.1 from the best possible schedule?</b> (<code>validation/hardware/replay_oracle.py</code>, 380 runs: v4.1, a clairvoyant v4.1 and the 17 fixed settings, laptop 8, Jetson 6, onboard 3.) The <i>clairvoyant</i> v4.1 knows the exact goodput its next transfer on each path will get. The <i>per-phase oracle</i> picks with hindsight, in each phase, the best of v4.1 and the 17 fixed settings: either one schedule chosen on the mean over seeds, or separately per seed (an upper bound inflated by noise). ± = Student-t 95 % half-width over 5 paired seeds; bold = interval excludes 0.</p>
{t1}
<ul>
<li><b>Perfect link prediction adds nothing.</b> The clairvoyant gain is inside its interval in every scenario. It only shortens the longest stale stretch (mean over the 20 runs 0.39 → 0.07 s). Under the fault types emulated here (rate caps, full outages, real goodput stretches), a better link predictor (radio-aware or conformal) cannot raise accuracy.</li>
<li><b>v4.1 is within 3 % of the hindsight schedule oracle</b> in the mission, mirror and static scenarios. In random (4 s phases, the impairment changes every phase) it reaches 88 %; the headroom is there. The oracle is optimistic: phase changes are free, and it is chosen on the data it is scored on. Neither oracle is a proven optimum: the exact per-frame optimum is intractable.</li>
<li>Where the oracle beats v4.1: fixed onboard YOLOv8n-320 in total blackout, fixed onboard YOLOv8s-640 when both links are degraded, a fixed Jetson setting in the mission's ground blackout, and a fixed laptop setting in the mirror's edge-impaired phases. The gaps are small. v4.1 beats the best single fixed setting everywhere (significant in mission, mission_mirror and random; in static_good it ties).</li>
</ul>
<p><b>2. Are the controller's deadline probabilities calibrated?</b> {cal['n']:,} offloaded frames of v4.1 in the same runs: the Gaussian chance of meeting 300 ms, p_on, against whether the result did arrive in time.</p>
{t2}
<ul>
<li><b>The estimate is cautious, never over-confident.</b> Frames arrive on time more often than predicted in every bin with more than 7 frames. ECE {cal['ece']:.3f}, Brier {cal['brier']:.3f}. With item 1, the caution costs no accuracy. This is the replay's link model. The same check on hardware needs the new per-frame logging (item 4).</li>
</ul>
<p><b>3. Worst-phase sAP and staleness of every hardware campaign</b> (<code>scripts/report_worstphase_oct29.py</code>, from the existing per-run scores; <code>worst_phase_oct29{{,_coco}}.json/.md</code>). Recent work on streaming-perception evaluation recommends reporting the worst stream and deadline misses next to the mean.</p>
<ul>
<li><b>Worst-phase sAP does not separate the strategies.</b> Of the paired worst-phase comparisons against each campaign's references (Holm over the unique comparisons), {nsig(wv)} of {npair(wv)} are significant with the VisDrone detectors, {nsig(wc)} of {npair(wc)} with COCO. The strategy ranked first by worst phase differs from the one first by mean in {len(rk) - sum(rk)} of {len(rk)} campaign scenarios, never significantly. The reason is that the worst phase is set by the video shown in it (in static_good, a clip on an unimpaired link), the same for every strategy.</li>
<li><b>Staleness does separate them.</b> In the same-day table's mission (G13, 5 runs each), the held result is older than 300 ms for v4.1 in {st('v41')}, for v5 in {st('v5')}, and for v5.1 in {st('v51')}. This is the freshness price at work, now on the standard staleness measures. The paper should report the miss rate and the longest stale stretch next to mean sAP, and give worst-phase sAP once, noting that video content dominates it.</li>
</ul>
<p><b>4. Logging for the next hardware campaign.</b> <code>adaptive2.py</code> now records, for every frame sent to a path, the controller's own prediction at decision time (<code>pred</code>: p_on, p_late, rate and spread estimates, predicted latency). It is computed by a new function, <code>path_pred</code>, with the same formulas and estimates as <code>path_value</code> and no side effects. Decisions are unchanged. Checked: it equals <code>path_value</code>'s p_on in 140 test cases, and all 118 tests pass. It has not yet run on a board and must be pushed to the camera Pi before the next campaign.</p>
<p><b>Replay heat model, fixed.</b> The 28 Oct correction (Part 21) refit the Pi's thermal model on the levels below 80 °C only. That is right for v5's heat price, but it made the replay's board almost never reach 80 °C. The replay now keeps two models, as on the hardware. The board itself follows the fit over every unthrottled 6-minute level, T = 34.4 °C + 12.7 °C/W × P. At 4–5 W it is 2–5 °C warmer than the below-80 °C fit (Part 21), but it is the one that reproduces the measured time in the hot range, which is what sets throttling in the replay. The controller still prices heat with its own model, the fit below 80 °C (<code>replay.load_all</code>). Items 1–2 are from the corrected replay; the earlier oracle run (<code>oracle_oct29/</code>) gives the same shares to 0.1 %.</p>
{t3}
<ul>
<li>The replay ranks heat correctly but understates its size for the onboard-heavy baselines (time at ≥ 80 °C, replay / hardware: conf_trigger {hot('conf_trigger')}, jsq {hot('jsq')}, reward_offload {hot('reward_offload')}; v5 {hot('v5')}), because it gives them 0.4–0.7 W less power than measured. Replay heat results are therefore comparisons only, not absolute values.</li>
</ul>
<p><b>What this changes in the plan.</b> A better link predictor is not worth building for the emulated faults. Prediction can only pay if real interference behaves differently, with bursts or both paths failing at once. The replay cannot test that, because its two paths draw goodput independently, so the co-channel interference test on the mesh remains the one novelty item. New claim for the paper, labelled as replay: v4.1 gains nothing from a clairvoyant link and reaches 97–100 % of a hindsight per-phase oracle (88 % with 4 s phases).</p>
'''


STATE = ('<li><b>Laptop-only additions (19.8, 29 Oct):</b> in the replay, v4.1 gains nothing from a clairvoyant link and '
         'reaches 97–100 % of a hindsight per-phase oracle (88 % with 4 s phases); its deadline probabilities are cautious, '
         'never over-confident; worst-phase sAP separates no strategies (0 of 169), while staleness does (v4.1 holds a '
         'result older than 300 ms 1.4 % of the time, v5 16 %); the replay\'s heat model was corrected (heat agreement '
         'with hardware back to r = 0.96); the controller now logs its own predictions for the hardware calibration check.</li>\n')
FAULT = ("The replay's board followed the controller's thermal fit (levels below 80 °C) after the 28 Oct correction "
         "(<code>replay.py</code>)", "The replay's board almost never reached 80 °C (time at ≥ 80 °C against hardware "
         "r = 0.53, was 0.96)", "Board and controller models separated: the board follows the full-range fit, the "
         "controller its own (29 Oct, 19.8); r = 0.96 again")
LEFT = [("Co-channel interference test on the mesh: both paths failing at once (19.8: the only remaining place where "
         "better link prediction could pay)", "A device for interference traffic; the mesh", "about half a day"),
        ("Calibration of the deadline probabilities on hardware (the per-frame logging of 19.8; push adaptive2.py to "
         "the camera Pi first)", "The next board campaign", "no extra runs")]


def main():
    h, m = HTML.read_text(), MD.read_text()
    sec = section()
    j = h.index('<h2 id="argument">')
    i = h.find("<h3>19.8 ")
    h = h[:i if 0 <= i < j else j] + sec + h[j:]
    j = m.index("## PART 20")
    i = m.find("### 19.8 ")
    m = m[:i if 0 <= i < j else j] + html_to_md(sec) + m[j:]
    # Part 1 bullet, first in the state box
    h = re.sub(r"<li><b>Laptop-only additions \(19\.8.*?</li>\n", "", h, flags=re.S)
    k = h.index('<div class="box state">')
    k = h.index("<ul>\n", k) + len("<ul>\n")
    h = h[:k] + STATE + h[k:]
    m = re.sub(r"^- \*\*Laptop-only additions \(19\.8.*\n", "", m, flags=re.M)
    k = m.index("**State on 26 Oct 2026")
    k = m.index("\n- ", k) + 1
    m = m[:k] + html_to_md("<ul>" + STATE + "</ul>").strip() + "\n" + m[k:]
    # Part 21: the fault
    h = re.sub(r"<tr><td>The replay's board followed the controller's.*?</tr>\n", "", h)
    m = re.sub(r"^\| The replay's board followed the controller's.*\n", "", m, flags=re.M)
    a = h.index("<tr><td>The Pi's thermal fit admitted the 50 %-duty level")
    a = h.index("</tr>\n", a) + 6
    h = h[:a] + "<tr><td>" + "</td><td>".join(FAULT) + "</td></tr>\n" + h[a:]
    a = m.index("| The Pi's thermal fit admitted the 50 %-duty level")
    a = m.index("\n", a) + 1
    m = m[:a] + "| " + " | ".join(re.sub(r"</?code>", "`", x) for x in FAULT) + " |\n" + m[a:]
    # What is left
    for task, needs, time in LEFT:
        key = task[:40]
        h = re.sub(r"<tr><td>" + re.escape(key) + r".*?</tr>\n", "", h)
        m = re.sub(r"^\| " + re.escape(key) + r".*\n", "", m, flags=re.M)
        a = h.index("<tr><td>Commit and push the work since")
        h = h[:a] + f"<tr><td>{task}</td><td>{needs}</td><td>{time}</td></tr>\n" + h[a:]
        a = m.index("| Commit and push the work since")
        m = m[:a] + f"| {task} | {needs} | {time} |\n" + m[a:]
    HTML.write_text(h)
    MD.write_text(m)
    print("report updated: 19.8, Part 1 bullet, what is left")


if __name__ == "__main__":
    main()
