#!/usr/bin/env python3
"""Final Report update, 12 Nov 2026: everything since 30 Oct (Results Brief 19.13 overload, 19.14 clock speed, and the
hardening of both papers, 10-12 Nov). Run after scripts/report_final_oct30.py. Idempotent (a marker comment); the
previous version is archived to experiments/results/hardware/_superseded/report_before_final_nov12/.
Every number is from a generated result file: paper2/generated/metrics.tex, the paper 1 metric files listed in
paper/drafts/design_rule.tex's header, overload_model/overload_summary.json, clock_effect/clock_effect.json, and the
docs/*predictions*.md result sections."""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
F = ROOT / "AEGIS-UAV Final Report.html"
ARCH = ROOT / "uav-split-perception" / "experiments" / "results" / "hardware" / "_superseded" / "report_before_final_nov12"
MARK = "<!-- final-report-update-nov12 -->"

S413 = """
<h3>4.13 Many cameras on one edge drone, and the camera Pi's clock (10 Nov, from logged data)</h3>
<p><b>Overload.</b> A queueing model fed only with measured stage times (<code>overload_model.py</code>; Results Brief 19.13) asks what happens when cameras offer the Jetson more frames than it can take. The path limit is about 17 frames/s over the Wi-Fi access point (the radio fills first), 26 over one mesh hop (the Jetson's GPU) and 12 relayed over the mesh (the shared channel). A naive queue turns overload into nothing: one Pi at 30 frames/s gets 0 results on time, with a median latency of 28 s and all of the Jetson's work wasted. Our one-frame-in-flight rule caps the load and serves 4 cameras per Jetson on Wi-Fi and 6 over one mesh hop. A coordinator that lets the newest frame replace a waiting one (latest frame wins) would serve 10 or more in the model. The model matches the boards for one hop. It is far too optimistic for the relayed mesh: there the boards already fail with one camera (12.5 % of results on time for fixed offloading through the Jetson), and computing at the relay is the fix (the hierarchical mode, 100 % on time). With two cameras, the adaptivity, not the coordinator, avoids the overload: the Pi's detections were available 68 % of the time without the coordinator and 70 % with it, against 19 % for fixed offloading.</p>
<p><b>Clock speed.</b> Every mesh run logged the Pi's clock (<code>clock_effect_analysis.py</code>; 19.14). With v4.1 the Pi is at its full 2.4 GHz 60 % of the time and slowed by the governor because it is idle 40 %, never throttled; without prices it is throttled 86 % of the time. Pinning the full clock would save at most about 6 ms on laptop-served frames and at most +0.0009 sAP, and part of that is confounding. Throttling is the harmful kind: it makes onboard frames 12–27 % slower. Verdict: keep the default governor; prevent throttling, not idle down-clocking.</p>
"""

S414 = """
<h3>4.14 When can a split pay off? A tested rule (paper 1, 10–12 Nov)</h3>
<p>The learned bottleneck of 4.1 beats JPEG on bits but rarely end to end. Paper 1 now says exactly where. <b>Proposition (break-even goodput):</b> a code <i>k</i> can beat every image setting only below B<sub>be</sub>(<i>k</i>), the payload rate of the cheapest image setting that matches its accuracy, at the code's own frame time, or that setting's deadline rate. Two corollaries follow. B<sub>be</sub> does not depend on the code's own size, so no better coder (even one at the rate–distortion limit) raises it; it only adds wins below it. A split that switches codes slot by slot is bounded by the largest of their B<sub>be</sub>. The rule was then put through every test a reviewer is likely to ask for. Predictions were committed before each run, and the results were written against them (<code>docs/*predictions*.md</code>).</p>
<div class="tbl"><table>
  <tr><th>Test</th><th>What it showed</th><th>Rule</th></tr>
  <tr><td>Model check: 14 codes (incl. 4 jointly trained) against 18 JPEG qualities, 3 devices and 4 speeds</td><td>A code wins in 548 cells. With the old 7 qualities the count was 657: a coarse JPEG grid overstates the split</td><td>0 exceptions (a consistency check of the derivation)</td></tr>
  <tr><td>Jointly trained codes (bottleneck plus the detector's server side)</td><td>+0.002 to +0.041 mAP; 3 of 4 gains significant. The smallest code's B<sub>be</sub> on the Pi rises from 0.81 to 1.17 Mbit/s; it wins up to 0.72</td><td>0 exceptions</td></tr>
  <tr><td>Fading links (stream simulator, two trace profiles)</td><td>The constant-goodput bound <b>fails</b> on fast devices (≤ 180 ms per inference): 14 % and 24 % of simulated wins lie above it, by small margins. A fading version, discounted by the link's measured spread, has none</td><td>Fading version: 0 exceptions (empirical, not a theorem)</td></tr>
  <tr><td>A detector fine-tuned on JPEG (the fair image baseline)</td><td>+0.070 mAP at Q10, worse from Q85 up, so the server uses the better detector per quality. Split wins fall from 548 to 409; the smallest joint code's Pi B<sub>be</sub> falls from 1.17 to 0.68</td><td>0 exceptions</td></tr>
  <tr><td>A learned entropy coder for the split (5 codes, real range-coded bitstreams)</td><td>52–73 % smaller than the zstd codes at the same accuracy, but the same B<sub>be</sub>, as the corollary says</td><td>0 exceptions</td></tr>
  <tr><td>Bootstrap intervals (200 resamples)</td><td>Smallest joint code: 1.06–1.26 Mbit/s on the Pi; the frozen code 0.68–0.81. The joint shift is larger than the noise</td><td>—</td></tr>
  <tr><td>Energy (measured Pi constants)</td><td>On the Pi a split uses less energy than its JPEG setting only below 183 kbit/s for any code (median 61). At 1 Mbit/s the smallest joint code costs 0.57 J per frame against 0.051 J, 11×</td><td>Energy version B<sub>E</sub></td></tr>
  <tr><td>Low-delay video as the image family (x264, x265 on 2,558 VisDrone-VID frames)</td><td>46–87 % fewer bytes than JPEG at equal accuracy (software encoders; NVENC 91 %). The smallest joint code's B<sub>be</sub> falls from 9.84 to 1.51 Mbit/s on the Jetson and from 1.88 to 1.06 on the Pi; winning cells fall from 1,118 to 204 (64 if encoding were free)</td><td>0 exceptions</td></tr>
  <tr><td>Inter-frame coding of the split codes (video against video)</td><td>Lossless, against the previous frame's code: 26–32 % fewer bytes, accuracy identical. B<sub>be</sub> unchanged; wins 204 → 260, all below it</td><td>0 exceptions</td></tr>
  <tr><td>Learned image codecs (pretrained hyperprior models)</td><td>52 % fewer bytes than JPEG, but their encoders cost 1.1–4.6× the whole detector, so on the Pi and the Jetson nothing changes</td><td>0 exceptions</td></tr>
  <tr><td>Region-of-interest JPEG with server feedback</td><td>Regions cover 30 % of the frame; <b>no saving</b> at equal accuracy (median 0 %, −13 to +12 %). Adds nothing once video is available</td><td>0 exceptions</td></tr>
  <tr><td>A second detector (YOLO11s)</td><td>Codes of 3.3–25.9 KiB; B<sub>be</sub> 0.78–1.77 Mbit/s on the Pi, 4.06–9.12 on the Jetson. On the Pi no code wins at any goodput: the onboard layers take 250 ms of the 300 ms deadline</td><td>0 exceptions in 220 wins</td></tr>
  <tr><td>MPEG feature coding (FCM/FCTM) as a baseline</td><td>Not run: the reference software is hosted for MPEG members and builds on the slow VTM codec; covered by discussion and citation</td><td>—</td></tr>
</table></div>
<p><b>What it means.</b> The paper's verdict holds and is now sharper. A split pays off only below a goodput the rule predicts from the code's accuracy, the image codec's rate curve and the device's speed. That window is below about 2 Mbit/s on a Pi (0.7–1.9 Mbit/s, depending on the code and the image baseline), and once the camera can use low-delay video it shrinks to 1.5 Mbit/s even on the Jetson. On a board like the Pi a split never saves energy. Details: <code>paper/drafts/design_rule.tex</code> (8 pages in a test build, every number generated).</p>
"""

S415 = """
<h3>4.15 Guarantees for the priced controller, and where heat still comes from (paper 2, 10–12 Nov)</h3>
<ul>
  <li><b>Theorem 1 (power, every run).</b> Mean power stays below the budget plus a price term (at most 0.21 W over a 4-minute run, 0.035 W over 24 minutes) plus the updates where the price was held or capped. It follows from the update rule, so what had to be checked was the rule. All 66,655 logged updates of the 376 priced runs (10 campaigns) follow it (0 unexplained), so the bound holds on every run. The freshness, heat and Jetson prices follow their stated rules on all 132,042 of their logged updates too; their caps were added on 13 Oct, and 36 earlier runs ran without them. It is a decomposition, not a cap: 364 of the 376 runs averaged above budget, by at most 0.07 W on the mesh and 0.15 W over 24 minutes.</li>
  <li><b>Theorem 2 (accuracy gap, idealised).</b> The standard drift-plus-penalty trade: a gap of order η against a price term of order 1/η. The hardware breaks its assumptions in six stated ways, so it is a guide, not a measurement.</li>
  <li><b>Budget and temperature.</b> The measured thermal model, 34.4 + 12.7·P °C (τ = 149 s), predicts the mean temperature of all 16 runs of 20 minutes or more within 1.6 °C. A budget of 2.8 W means about 70 °C; staying below the 80 °C throttle point needs B ≤ 3.6 W.</li>
  <li><b>Where heat still comes from.</b> On 24-minute Wi-Fi missions with total blackouts, the board was still at or above 80 °C 19–27 % of the time. The validated trace replay traces this to the controller's blackout hold (onboard work while every link is down), at every budget from 2.4 to 4.5 W. Capping the hold at 78 °C gives 0 % hot time at the same sAP (replay; board test pending). The paper's heat claim is scoped to this.</li>
  <li><b>A warmer room.</b> At +10 °C the 2.8 W budget is too high, and raising the price cap alone leaves 42 % hot time. A budget that estimates the room's offset online, together with a higher cap, gives 0 % hot time at +5 and +10 °C, at 94 % and 89 % freshness.</li>
  <li><b>Theorem 3 (hard guard, peak temperature).</b> If no onboard inference starts at or above a guard temperature, the peak is bounded: 79.9 °C with the lab constants, and it stays below the 85 °C throttling limit for a room up to 14.5 °C warmer. Its converse: no controller can keep the board cooler than its offload-only floor. In the replay the bound held on all 20 guard runs, with no hot time up to +10 °C. At +15 °C the floor alone averages 79.9 °C and the board is hot 84 % of the time, as the converse predicts.</li>
  <li><b>Settings swept</b> (285 replay runs, predictions committed first): the step size trades the price term against the gap as the theorems say, with no measurable sAP effect. The replay reproduces mean power (r = 0.99) and the ranking of hot time (r = 0.98), but not its level (off by 16 points), so its hot-time numbers are comparisons, not predictions.</li>
  <li><b>A learned baseline.</b> A constrained deep-RL policy (PPO-Lagrangian, budget 2.8 W) keeps the budget (2.43 W) but trails v4.1 on all three scenarios: −0.0100 ± 0.0014 sAP over 24 minutes, −0.0124 ± 0.0039 on 2-minute missions, −0.0038 ± 0.0034 with random faults. Two earlier training attempts failed and are reported.</li>
  <li><b>Noisy relays</b> (calibrated swarm simulator; 144 settings with 3–8 dB shadowing and 0–10 % loss per hop): the adaptive policy relays at most 1.9 % of frames, and relaying changes its rate by at most 4 %. The shared access point, not the relay link, limits the swarm.</li>
  <li><b>Calibration.</b> Over 44,524 offloaded frames, v4.1 predicted a 94.4 % chance of meeting the deadline and 98.5 % did: cautious, not optimistic.</li>
</ul>
<p>Paper 2 builds at 9 pages. The hard guard, the capped hold and the room-following budget are replay results until the board session confirms them.</p>
"""

NEG = """
    <li>The constant-goodput break-even bound of paper 1 fails under fading on fast devices (14–24 % of simulated wins above it); only the spread-discounted version holds, and it is empirical, not proved.</li>
    <li>A coarse JPEG grid overstated where splits pay off (657 against 548 winning cells), and one apparent win of a jointly trained code on the Pi was an artefact of it.</li>
    <li>Region-of-interest JPEG with server feedback saved nothing at equal accuracy; learned image codecs are too expensive to run on either board.</li>
    <li>The YOLO11s codes never win on the Pi: their onboard layers leave 12 ms of the deadline.</li>
    <li>The priced controller still left the board hot 19–27 % of the time on 24-minute missions with blackouts, through its blackout hold; at +10 °C the 2.8 W budget is too high and a higher price cap alone does not fix it.</li>
    <li>The constrained deep-RL baseline trails v4.1, and its first two training attempts failed (an under-charged radio; a multiplier that wound up until the policy only skipped).</li>
"""

FAULTS = """
    <tr><td>Windows memory watchdog stopped every job at once (11 Nov, 23:29 IST)</td><td>About two hours lost; no results lost (all jobs resumable)</td><td>One GPU job at a time, at most 2–3 replay shards</td></tr>
    <tr><td>The RL baseline's cost under-charged the radio, which stays on until the acknowledgement</td><td>First training attempt invalid</td><td>Energy model matched to the billed power within 3 %; attempts archived and reported</td></tr>
    <tr><td>The YOLO11s analysis re-timed its codes on every run</td><td>Win count moved between runs (223 against 220)</td><td>Timings measured once and kept; re-runs identical</td></tr>
    <tr><td>Paper 2 build checks read a stale LaTeX log</td><td>Clean builds reported that were not checked</td><td>Built with pdflatex + bibtex; now builds clean at 9 pages</td></tr>
"""

BOARDS = """
      <li>The board session prepared on 10–12 Nov (predictions committed in <code>docs/board_session_predictions_nov.md</code>): the planner campaign (<code>REPS=2 tools/campaign_mesh4.sh</code>, 18 runs), the energy test (<code>campaign_energy_nov.sh</code>) and the noisy relay (<code>campaign_relaynoise_nov.sh</code>), about 5 h. Add the capped hold and the hard guard, the room-following budget, a run with airflow over the Pi, and video encode times measured on the Pi.</li>
"""

FILES = """
    <tr><td>Paper 1, break-even rule and its tests</td><td><code>paper/drafts/design_rule.tex</code>; <code>evaluation/</code>: <code>break_even_rule.py</code>, <code>break_even_sim.py</code>, <code>break_even_ci.py</code>, <code>energy_break_even.py</code>, <code>joint_bottleneck.py</code>, <code>jpeg_tuned_detector.py</code>, <code>entropy_bottleneck.py</code>, <code>video_codecs.py</code>, <code>interframe_codes.py</code>, <code>learned_image_codecs.py</code> (venv <code>venv_lic</code>), <code>roi_jpeg.py</code>, <code>second_detector.py</code></td></tr>
    <tr><td>Paper 2 (priced controller)</td><td><code>paper2/main.tex</code>, <code>paper2/make_metrics.py</code>, <code>paper2/theory_check.py</code>, <code>paper2/guard_theorem.py</code>; replay sweeps <code>validation/hardware/replay_theory_sweep.py</code>; RL baseline <code>validation/hardware/rl_baseline.py</code></td></tr>
    <tr><td>Predictions and their results</td><td><code>docs/*predictions*.md</code>; roadmap <code>docs/novelty_roadmap_nov11.md</code>, task list <code>docs/laptop_tasks_nov11.md</code></td></tr>
    <tr><td>Overload and clock (10 Nov)</td><td><code>validation/hardware/overload_model.py</code>, <code>clock_effect_analysis.py</code></td></tr>
"""

REPL = [
    ('<div class="eyebrow">AEGIS-UAV · final report · 26 October 2026</div>',
     '<div class="eyebrow">AEGIS-UAV · final report · 26 October 2026, updated 12 November 2026</div>'),
    ("(exact splits with lightweight encoding; learned feature compressors were not tested); INT8 split computing is "
     "lossless, but its payload is 2–12× a JPEG.</li>",
     "; INT8 split computing is lossless, but its payload is 2–12× a JPEG. Learned and jointly trained codes beat JPEG "
     "only below a break-even goodput that a tested rule predicts (0 exceptions in every check): below about 2 Mbit/s on "
     "the Pi, and 1.5 Mbit/s even on the Jetson once the camera can use low-delay video (4.14).</li>"),
    ("Full analysis and sources: the AEGIS-UAV Novelty Brief.</p>",
     "Since 10 November both papers have been hardened on the laptop. Paper 1 has a tested break-even rule; paper 2 "
     "has a power guarantee checked on every logged update, a thermal budget rule, a hard-guard peak bound and a "
     "deep-RL baseline (4.14, 4.15). Honest venue view: paper 1 is realistic for IEEE TMC and a strong fit for IoT-J. "
     "Paper 2 is more realistic for TMC; INFOCOM only if the board session confirms the capped hold. "
     "Full analysis and sources: the AEGIS-UAV Novelty Brief.</p>"),
    ("<tr><td>Sending the image beats splitting the network, for the exact splits and encodings tested</td>"
     "<td>Auto-Split; learned feature compression can beat image coding (Yuan 2022, 2024; BottleFit)</td>"
     "<td><span class=\"chip lo\">low</span>, bounded</td></tr>",
     "<tr><td>A tested break-even rule for when any split (post-hoc, learned, jointly trained, entropy-coded, "
     "inter-frame coded) can beat the image, against JPEG, a JPEG-tuned detector, video, learned and ROI image codecs, "
     "with an energy version</td><td>Auto-Split; SC2 benchmark; BottleFit; Matsubara and Levorato; learned feature "
     "compression (Yuan 2022, 2024); information limits of task-oriented coding</td><td><span class=\"chip mid\">"
     "medium</span>: the rule is simple; testing it this widely is new</td></tr>\n"
     "    <tr><td>A sample-path power guarantee checked on every logged update, a budget rule for the board's "
     "temperature, and a peak bound under a hard guard</td><td>Drift-plus-penalty (Neely); thermal virtual queues; "
     "heat-and-memory-constrained offloading</td><td><span class=\"chip mid\">medium</span>: standard theory, new "
     "check on hardware</td></tr>"),
    ("<li>A learned feature compressor could change the split-versus-JPEG result; not tested.</li>",
     "<li>Learned feature compression is now tested (4.14), but the MPEG feature-coding standard was not run, a "
     "learned per-region quality model (AccMPEG) was not tried, and the YOLO11s device times are scaled from YOLOv8s "
     "measurements.</li>\n"
     "    <li>The video options assume an error-free stream, and their encode times on the boards are scaled from the "
     "laptop, not measured.</li>\n"
     "    <li>The capped hold, the hard guard and the room-following budget are trace-replay results; the replay "
     "ranks hot time correctly but misses its level by 16 points.</li>"),
    ("<li>Paper 1 has a hardware section and the learned bottleneck; paper 2 (the priced controller) has a first "
     "draft in <code>paper2/</code>; finish it after the planner campaign.</li>",
     "<li>Paper 1's arXiv version is merged into <code>main</code>; it still needs the authors, the repository URL "
     "and your approval. Its journal version (the break-even rule) is drafted in <code>paper/drafts/design_rule.tex</code>.</li>\n"
     "      <li>Both papers: a rewrite around the new results and a fresh audit (about 1–2 days). Paper 2 is now 9 "
     "pages: check the venue's limit.</li>\n"
     "      <li>Pick the board day and check the venue deadlines.</li>"),
]

INSERTS = [   # (anchor, text, position) - inserted before the anchor
    ('</section>\n\n<section id="negative">', S413 + S414 + S415),
    ('  </ul>\n</section>\n\n<section id="novelty">', NEG),
    ('  </table></div>\n</section>\n\n<section id="next">', FAULTS),
    ('    </ul></div>\n    <div class="card"><h3>Needs the team</h3>', BOARDS),
    ('    <tr><td>Fine-tuned weights</td>', FILES),
]


def main():
    s = F.read_text()
    if MARK in s:
        print("already applied")
        return
    ARCH.mkdir(parents=True, exist_ok=True)
    shutil.copy2(F, ARCH / F.name)
    for old, new in REPL:
        assert s.count(old) == 1, ("replace anchor", old[:80], s.count(old))
        s = s.replace(old, new)
    for anchor, text in INSERTS:
        assert s.count(anchor) == 1, ("insert anchor", anchor[:80], s.count(anchor))
        s = s.replace(anchor, text.rstrip("\n").lstrip("\n") + "\n" + anchor if not anchor.startswith("</section>")
                      else text.rstrip("\n") + "\n" + anchor)
    s = s.replace("</main>", MARK + "\n</main>", 1) if "</main>" in s else s + MARK
    F.write_text(s)
    print("updated", F)


if __name__ == "__main__":
    main()
