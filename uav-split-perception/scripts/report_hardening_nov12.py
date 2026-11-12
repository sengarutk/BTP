#!/usr/bin/env python3
"""Results Brief update, 12 Nov 2026: the hardening of both papers (10-12 Nov), sections 19.15-19.23, a Part 1 state
box, Part 20 sections 8-9 and negatives, Part 21 faults, Part 23 tasks, Part 24 paths. Run after report_clock_nov10.py.
Idempotent: every block is removed (by its marker) and re-inserted. Originals archived in
experiments/results/hardware/_superseded/report_before_hardening_nov12/.

Sources of every number (all generated): paper2/generated/metrics.tex; the paper 1 metric files listed in the header
of paper/drafts/design_rule.tex (be_metrics, b_be_ci_metrics, energy_be_metrics, sim*_metrics, video_metrics,
video_inter_metrics, lic_metrics, sd_metrics); docs/*predictions*.md (results sections); docs/board_session_predictions_nov.md.
"""
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_parts_oct22 import HTML, MD, html_to_md, table  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ARCH = ROOT / "experiments" / "results" / "hardware" / "_superseded" / "report_before_hardening_nov12"

S15 = '''<h3>19.15 Hardening both papers: the plan and how it was run (10–12 Nov 2026, laptop only)</h3>
<p>Both results are now written as papers. Paper 1: a split of the detector rarely beats sending the image, and when it can is predictable. Paper 2: heat on a fanless drone computer is a hidden accuracy cost, and a priced controller removes most of it, with guarantees. The plan was to remove the weaknesses a top reviewer would attack first, using only the laptop, and to leave the boards for one prepared session. The work was done in a fixed order: theory first, then stronger baselines, then the tests a reviewer would ask for.</p>
<ul>
<li><b>Rule for every test:</b> the prediction was written and committed to git <i>before</i> the run (<code>docs/*predictions*.md</code>). The result was then added below it, held or failed, and nothing above that line was edited. 19.22 lists every verdict.</li>
<li><b>Paper 1</b> (19.16–19.19): a break-even rule for when any split can beat the image, tested against jointly trained codes, fading links, a detector tuned on JPEG, an entropy coder, video, learned and region-of-interest image codecs, inter-frame coding and a second detector. Journal-version draft: <code>paper/drafts/design_rule.tex</code>. The arXiv version (without these) is merged into <code>main</code>.</li>
<li><b>Paper 2</b> (19.20–19.21): three theorems and a proposition, each checked on the logged hardware runs, plus 285 trace-replay runs sweeping the controller's settings, a hard thermal guard, a budget that follows the room temperature, and a constrained deep-RL baseline. Paper: <code>paper2/main.tex</code> (builds, 9 pages).</li>
<li><b>Nothing new was run on the boards.</b> What needs them is prepared, with predictions committed (19.23).</li>
</ul>
'''

S16 = '''<h3>19.16 Paper 1: a jointly trained bottleneck</h3>
<p>The bottleneck of 19.12 was trained with the detector frozen. Here it is trained together with the detector's server-side layers, on the detection loss, at the same cuts and code sizes, and selected on held-out frames (<code>evaluation/joint_bottleneck.py</code>, run 2). This is the strongest version of a split a reviewer could ask for: both sides of the cut learn.</p>
''' + table(["Code (cut, channels)", "Size", "Frozen detector, mAP", "Jointly trained, mAP", "Gain (paired bootstrap, 1,000 resamples)"],
            [["k4, 4 channels", "3.3 KiB", "0.142", "0.183", "+0.041, significant"],
             ["k4, 16 channels", "13.1 KiB", "0.206", "0.219", "+0.013, significant"],
             ["k2, 8 channels", "25.9 KiB", "0.233", "0.238", "+0.005, significant (interval from +0.001)"],
             ["k4, 32 channels, stride 1", "102 KiB", "0.253", "0.256", "+0.002 paired, not significant (−0.002 to +0.006)"]]) + '''<ul>
<li><b>The gain is largest for the smallest code</b>, where the frozen detector struggles most with the coarse code.</li>
<li><b>Gains of 0.005 or less are not claimed</b> in the paper, after an independent audit of the drafts.</li>
<li><b>What it changes</b> is in 19.17: a more accurate code needs a better JPEG setting to match it, which raises its break-even goodput.</li>
</ul>
'''

S17 = '''<h3>19.17 Paper 1: when can a split pay off? The break-even rule</h3>
<p><b>The rule.</b> In the paper's system model, an option has an onboard time, a payload, a server time and an accuracy. Its frame rate is limited by the larger of its onboard time and its sending time, and it is on time with a probability set by the goodput's spread. Proposition (break-even goodput): take a split code k, with frame time m_k (its onboard time, at least one camera frame). Any image setting q that is at least as accurate (P·A_q ≥ A_k) and no slower onboard does at least as well as the code once the goodput B is at least max(b_q/m_k, R_q/(1 − z_P·s)). Here b_q is the image's size, R_q its deadline rate and s the goodput's relative spread. So k can beat every image setting only below B_be(k), the smallest such value over the qualifying settings. The proof is five lines (the image's frame rate is at least the code's, and its on-time probability at least P).</p>
<ul>
<li><b>Corollary 1 (no coder raises the bound).</b> B_be depends on the code only through its accuracy and onboard time, <i>not its payload</i>. A better coder, even one at the rate–distortion limit, adds wins only below B_be.</li>
<li><b>Corollary 2 (switching codes does not help).</b> A split that changes code slot by slot, say with the channel, can beat the image only below the largest B_be of its codes.</li>
<li><b>What sets B_be:</b> the size of the cheapest image that matches the code's accuracy, and the device's speed. A faster device shortens m_k, so a code can win at higher goodputs, until the camera rate binds.</li>
</ul>
''' + table(["Check", "Setting", "Result"],
            [["Consistency check (same model as the proposition)", "14 codes (4 jointly trained) and post-hoc INT8 splits; 18 JPEG qualities (Q10–Q95 in steps of 5); 3 measured devices and 4 sweep speeds; a goodput grid with 19 % steps", "Codes win in 548 cells, all below their B_be: <b>0 exceptions</b>. It confirms the derivation and the code, not the model"],
             ["Grid resolution", "the paper's old 7 JPEG qualities", "657 winning cells instead of 548: a coarse JPEG grid overstates the split. The jointly trained 25.9 KiB code's apparent win on the Pi (1.74 Mbit/s) was an artefact of it"],
             ["How tight the bound is", "laptop and Jetson: 22 code–device pairs win somewhere", "Their largest winning goodput is a median 15 % (at most 23 %) below B_be; one grid step is 19 %"],
             ["The Pi", "frozen codes", "Only the 3.5 KiB code wins: B_be 0.81 Mbit/s (matched by JPEG Q20), wins up to 0.60"],
             ["Jointly trained codes", "smallest code, now matched by Q35 instead of Q20", "B_be on the Jetson 4.06 → 5.83 Mbit/s (wins up to 5.03 instead of 3.54); on the Pi 0.81 → 1.17 (wins up to 0.72 instead of 0.60): +44 %"],
             ["Post-hoc splits", "43 rows of the 19-detector survey", "All need more bits and more onboard work than a Q95 JPEG; on any processor slower than about 13 ms per full inference a post-hoc split cannot beat the image beyond its accuracy ratio"]]) + '''<p><b>Fading links (stream simulator).</b> The proposition assumes a goodput within ±sB of its mean. Every code and JPEG setting was run in the stream simulator on fading traces (moderate and vehicular profiles, 3 realisations of 60 s, rescaled to each mean goodput; the same realisation for every option). Their spread is 0.38 and 0.54 of the mean, far above the model's 0.1.</p>
<ul>
<li><b>Model and simulator agree</b> on whether a split beats JPEG in 94 % and 90 % of the cells.</li>
<li><b>The constant-goodput bound fails</b>: 99 of 719 simulated split wins (14 %) on the moderate profile and 207 of 858 (24 %) on the vehicular one lie at or above B_be, at up to 1.6× and 2.7× it. All are on devices that need at most 180 ms per inference, where the camera rate binds; on the Pi and at 360 ms the bound holds. The margins are small (a median 4–5 % over the best JPEG). The cause: under fading, JPEG often falls below the goodput it needs to keep up with the camera, while a small code keeps pace.</li>
<li><b>A fading version</b> discounts both terms by the same low quantile of the goodput, using the link's measured spread: B_be,f = min over P and q of max(b_q/m_k, R_q)/(1 − z_P·s). With the traces' own spread and nothing fitted, <b>no simulated win lies above it</b> (0 and 0 exceptions). It is conservative: a median 122 % and 158 % above the largest win. It is an empirical rule, not a theorem: the model has no closed form for the frame rate under a varying goodput.</li>
</ul>
'''

S18 = '''<h3>19.18 Paper 1: stronger baselines on both sides of the comparison</h3>
<ul>
<li><b>A detector tuned on JPEG.</b> The jointly trained codes get a trained server side, so for a like-for-like comparison the image path gets one too: the whole detector fine-tuned on JPEG-decoded images, each at a quality drawn from the 18 grid qualities (30 epochs, epoch 16 chosen on the same held-out frames; <code>evaluation/jpeg_tuned_detector.py</code>). It gains +0.070 mAP at Q10 and +0.028 at Q35, significant up to Q70, but it is significantly worse from Q85 up (−0.021 at Q95). A detector trained at Q35 alone is not better (0.220 against 0.217, not significant). The server knows the quality it receives, so the fair baseline runs the better detector at each quality.</li>
<li><b>Against that baseline:</b> split wins fall from 548 to 409 cells (−25 %), still 0 exceptions. The smallest joint code is now matched by Q15. Its B_be on the Pi falls from 1.17 to 0.68 Mbit/s (wins up to 0.51), and on the Jetson from 5.83 to 3.38 (wins up to 2.96). Joint training still raises B_be by 28 % over the frozen code (0.53 Mbit/s), not 44 %: part of its advantage came from training only one side. In the simulator the fading version again has 0 exceptions, while 103 of 519 and 217 of 628 wins lie above the constant bound.</li>
<li><b>A stronger coder for the split.</b> Five codes with a learned entropy model (a learned per-channel gain, integer rounding, a factorised prior, a range coder; <code>evaluation/entropy_bottleneck.py</code>). The bitstreams are real: all 2,740 test decodes reproduce the encoder's symbols, within 0.8 % of the model's ideal size. They span 1.4–12.6 KiB and 0.121–0.230 mAP, 52–73 % smaller than the zstd codes and 72–88 % smaller than JPEG at the same accuracy.</li>
<li><b>And they do not move the bound</b>, exactly as Corollary 1 says. At 0.206 mAP the entropy code of 5.2 KiB and the zstd code of 13.4 KiB are matched by the same JPEG setting (Q55). Both have B_be 7.78 Mbit/s on the Jetson, and both win up to 7.17; the smaller code only adds wins lower down (from 0.25 instead of 0.42 Mbit/s). On the Pi they win up to 0.60 Mbit/s, as the zstd codes do. 0 exceptions against either detector, and 0 for the fading version in the simulator.</li>
<li><b>How precise B_be is</b> (<code>evaluation/break_even_ci.py</code>; 200 bootstrap resamples of the test frames, every option rescored on the same frames). Smallest joint code: 1.06–1.26 Mbit/s on the Pi, 5.27–6.31 on the Jetson, matched by Q35 in 73 % of resamples. The frozen code of the same size: 0.68–0.81 on the Pi, so the joint shift is larger than the noise. Across all codes the interval is a median 22 % of B_be wide (at most 53 %). B_be moves in steps, because it changes only when the matching quality does.</li>
<li><b>Energy</b> (<code>evaluation/energy_break_even.py</code>, the Pi's measured constants). A frame costs e_enc + (a + bB)·b_q/B for an image and e_c(k) + (a + bB)·b_k/B for a split (radio power a + bB fitted; encode 0.0069 J; a full inference 2.23 J, the split's share by MACs). The split uses less energy exactly when B < B_E = aS/(e_c − e_enc − bS), with S the bits saved. For the 19 codes on the Pi, B_E is at most 183 kbit/s (median 61), and 64 kbit/s for the smallest joint code. At 1 Mbit/s that code costs 0.57 J per frame against 0.051 J for its JPEG setting, 11×. <b>On a Pi a split is never the energy-saving choice.</b></li>
</ul>
'''

S19 = '''<h3>19.19 Paper 1: stronger image codecs, inter-frame codes and a second detector</h3>
<p>JPEG is the weakest codec the camera could use. The proposition holds for any image family, so it was repeated with stronger ones: video, learned image codecs and region-of-interest JPEG. In each case the image side and the codes were run on the same frames. For video against video, the split codes were also coded against the previous frame. Finally a second detector was tested. Video, inter-frame and ROI use the 2,558 scored frames of the 7 VisDrone-VID validation sequences; the learned image codecs use the DET frames.</p>
''' + table(["Image family or change", "Bytes at equal accuracy", "Smallest joint code's B_be (Jetson / Pi)", "Winning cells", "Exceptions"],
            [["JPEG on the VID frames (reference)", "—", "9.84 / 1.88 Mbit/s", "1,118", "0"],
             ["Low-delay video: x264, x265 (ultrafast, medium), no B-frames, intra refresh, keyint 60", "46 % (x264 ultrafast) to 87 % (x264 medium) fewer than JPEG; NVENC 91 %", "1.51 / 1.06 (video + JPEG)", "204; 168 with the JPEG-tuned detector; 64 if encoding were free onboard", "0"],
             ["+ the split codes inter-frame coded (lossless, residual or previous code as a zstd dictionary, intra every 60)", "the codes 26–32 % smaller (median 29 %); the joint c4 code 3,292 → 2,242 B", "unchanged: 1.51 / 1.06", "260", "0"],
             ["Learned image codecs (bmshj2018-hyperprior, mbt2018-mean, cheng2020-anchor q1)", "52 % fewer than JPEG (median)", "unchanged on both boards: their encoders cost 108–458 % of the detector's MACs", "1,030 → 860 (DET frames, JPEG alone 1,030)", "0"],
             ["Region-of-interest JPEG with server feedback", "median 0 % (−13 to +12 %)", "8.99 / 1.88 (JPEG + ROI)", "1,106 (JPEG + ROI); 204 with video too", "0"]]) + '''<ul>
<li><b>Video</b> (<code>evaluation/video_codecs.py</code>): encode times were measured single-threaded from raw frames on the laptop and scaled to each device like every host time. Neither board has a hardware encoder that was used. The video options assume an error-free stream, which favours video (a lost frame would corrupt the frames that reference it).</li>
<li><b>Inter-frame codes</b> (<code>evaluation/interframe_codes.py</code>): the uint8 code of every frame is recorded in the validator's own run and put in sequence order. It is then coded as the smallest of intra, the residual from the previous code, or zstd with the previous code as a dictionary, with a 1-byte flag. Every frame decodes bit-exact. The recorded intra sizes and accuracies reproduce the video run exactly for all 12 codes. Residuals win on 96–98 % of frames. The added CPU time is 0.04–0.55 ms per frame and is charged to the code. B_be does not change because it does not depend on the code's bytes (Corollary 1); the only cell that moves, 0.16 → 0.15 Mbit/s with free video encoding, moves because of the added coding time. The entropy-coded codes were not inter-coded.</li>
<li><b>Learned image codecs</b> (<code>evaluation/learned_image_codecs.py</code>, CompressAI 1.2.8 in its own venv <code>venv_lic</code>): real bitstreams, the same hook as the JPEG rows. cheng2020-anchor needs 3.0 s to encode and 4.6 s to decode a frame on the laptop, so only quality 1 was run (deviation recorded).</li>
<li><b>Region-of-interest JPEG</b> (<code>evaluation/roi_jpeg.py</code>): a closed loop. The server's detections of frame t − 2, grown by 16 px and snapped to the 16-px JPEG blocks, form the mask. The camera sends the whole frame at q_b ∈ {10, 20, 30} plus the masked frame at q_r ∈ {50, 70, 90}, grey outside the mask. The server rebuilds the mask from its own boxes, so no side information is sent. The regions cover 30 % of the frame. The low-quality layer is about half the bytes, and the objects the 2-frame-old feedback misses fall in it, so ROI saves nothing. The camera side takes 6.2× one JPEG encode (2.9–3.1 ms), mostly the unoptimised mask code. A learned per-macroblock quality model (AccMPEG) was not tried.</li>
<li><b>A second detector, YOLO11s</b> (<code>evaluation/second_detector.py</code>; 0.269 mAP): the same cut after the stride-8 block, the same bottleneck and training, codes of 4–32 channels. Its device times are scaled from YOLOv8s measurements: 1.01× on the Pi (matched onboard runs), 1.42× elsewhere (host GPU profile). Post-hoc INT8 needs 425 KiB per frame (4.0× a Q95 JPEG). The codes are 3.3–25.9 KiB with 0.139–0.204 mAP, close to the YOLOv8s codes of the same widths. Its onboard part is heavier (31 % of the MACs against 21 %). B_be is 0.78–1.77 Mbit/s on the Pi and 4.06–9.12 on the Jetson (wins up to 7.17). <b>On the Pi no code wins at any goodput</b>: the onboard layers take 250 ms of the 300 ms deadline, so a code is on time only above about 2.3 Mbit/s, where JPEG is better. 220 winning cells, 0 exceptions.</li>
<li><b>MPEG feature coding (FCM, test model FCTM)</b> was not run. Its reference software is hosted for MPEG members (git.mpeg.expert) and builds on the slow VTM codec. It is covered by discussion and citation (arXiv 2512.10209; CompressAI-Vision, arXiv 2509.20777).</li>
</ul>
<p><b>What paper 1 now says.</b> Before building a split, compute B_be from four things: the code's accuracy, the image codec's rate–accuracy curve (with the best detector the server can run for it), the device's full-model time and, on a fading link, the goodput's spread. If the link is mostly above B_be, send the image. On the Pi that window is below about 2 Mbit/s (0.7–1.9 depending on the code and the baseline). Once the camera can use low-delay video, it is 1.5 Mbit/s even on the Jetson. A split never saves energy on a Pi.</p>
'''

S20 = '''<h3>19.20 Paper 2: guarantees for the priced controller, checked on the hardware</h3>
<ul>
<li><b>Theorem 1 (power budget, every run).</b> After N price updates, mean power ≤ budget + μ_N/(ηN) + (1/ηN)·(the downward steps the rule skipped while the price was held in a blackout or at its cap). It follows from the update rule alone, so what can fail is the rule. All 66,655 logged updates of the 376 priced runs (10 campaigns) were classified from the logged values as a plain step, clipped at zero, raised by the thermal guard, held, or at the cap: 0 fall outside these cases, so the bound holds on every run. The price term is at most 0.21 W over a 4-minute run and 0.035 W over 24 minutes.</li>
<li><b>It is a decomposition, not a cap.</b> 364 of the 376 runs averaged above their budget. On the mesh (51 runs) the excess was at most 0.07 W. On the 24-minute mesh missions it reached 0.15 W: the price sat at its cap 18 % of the time, and the cap term explains up to 0.11 W. Wi-Fi scenarios with total blackouts reached 1.06 W, up to 0.74 W of it from the hold. Campaigns run before the cap and hold existed exceeded by up to 1.3 W, with the price wound up to 14.</li>
<li><b>Theorem 2 (accuracy gap, idealised).</b> With i.i.d. states, a greedy choice on the true power and plain steps, the controller is within (η/2)·mean (P − B)² of the best policy that knows the statistics and meets the budget: the standard drift-plus-penalty trade, a gap of order η against Theorem 1's 1/η. The hardware breaks its assumptions in six stated ways: non-plain steps, a state that depends on past actions (busy servers, heat), time correlation, per-frame choices, the freshness bonus, and a different metric. So it is a guide, not a measurement. With the measured (P − B)² of the 42 v4.1 mesh runs (median 0.70 W², at most 1.6), the bound is 0.035–0.08 value units per second, at most 0.3 % of the largest value rate. Empirically, v4.1 reaches 97–100 % of a hindsight per-phase oracle (88 % when faults change every 4 s).</li>
<li><b>Proposition (budget and temperature).</b> With a first-order thermal model, the mean temperature over a window is a + b·(mean power) minus a transient, so Theorem 1 bounds it. The 6 measured steady levels give a = 34.4 °C, b = 12.7 °C/W, τ = 149 s. On the second half of all 16 runs of 20 minutes or more it predicts the mean temperature within 1.6 °C on average (at most 2.8). The error is a campaign offset (+1.63 °C on the 24-minute Wi-Fi runs, −0.04 °C on the mesh), not scatter. Rule: 2.8 W means about 70 °C; keeping the mean below 80 °C, where throttling starts, needs B ≤ 3.6 W. It bounds the mean, not the peak.</li>
<li><b>Theorem 3 (peak temperature under a hard guard).</b> Write the power as the load without onboard inference plus the extra of inference. (a) The temperature is never below what the load without inference alone gives (the floor). (b) If inferences run one at a time and none starts at or above the guard temperature θ_g, the peak is at most θ_g + the rise during one inference + a term from the floor's range. Measured constants: 62 offload-only runs give the floor (mean power 2.52 W, peak 4.05 W; 24-minute floor 67.2 °C after 2τ). With θ_g = 78 °C, the bound is 79.9 °C in the lab. It stays below the 85 °C throttling limit for a room up to 14.5 °C warmer. By (a), no controller can hold 78 °C in a room more than 10.8 °C warmer (16.2 on the floor's mean).</li>
<li><b>The other three price updates, checked the same way</b> (<code>paper2/price_rules_check.py</code>, 12 Nov). Every logged update of the freshness price λ_F (53,758 updates, 158 runs), the heat price λ_T (34,929, 170 runs) and the Jetson energy price μ_e (43,355, 239 runs) follows the rule the paper states, with 0 exceptions. The caps on λ_F (2) and μ_e (5) were added on 13 Oct. In 8 and 28 runs of the two Wi-Fi campaigns of 11–12 Oct, the same rules ran without them, and the prices reached 4.1 and 6.4. Paper 2 now says so.</li>
<li><b>The value equation</b> V(s, v) = (A_v/A_ref)·H(L, T)·p_late − μ·E_cam + λ_F·p_on·[AoI + L ≥ D] was compared term by term with the board code (<code>adaptive2.py</code>, <code>path_value</code> and <code>onboard_value</code>) and matches. That includes the holding window (5 samples from L to L + T), the 1 s late window, the skip when no value is positive, and the hold rule (every link's best setting at most 20 % likely on time, board below 85 °C). Its predictions are checked against outcomes only in the replay (calibration, below); the per-frame logging for the same check on hardware runs from the next board session.</li>
<li><b>Calibration</b> (replay, 44,524 offloaded frames): v4.1 predicted on average a 94.4 % chance of meeting the deadline and 98.5 % did (expected calibration error 0.042), with no over-confident bin: cautious, not optimistic.</li>
</ul>
'''

S21 = '''<h3>19.21 Paper 2: the controller's settings swept in the replay, the hard guard and a learned baseline</h3>
<p>Each change is to one setting of v4.1, on the same seeds and link draws, in the trace replay validated against the hardware (<code>validation/hardware/replay_theory_sweep.py</code>): 6 step sizes from 0.02 to 1, budgets from 2.4 to 4.5 W, room temperature, the hold, the price cap, a room-following budget and the hard guard; 10 seeds of the 2-minute scenarios and 5 of the 24-minute mission. Theorem 1 holds in every run. What the replay can and cannot show: it reproduces mean power (r = 0.99) and how hot time varies between policies (r = 0.98), but its hot-time <i>level</i> is off by 16 points, so the shares below are comparisons, not predictions of the board. Its sAP is reliable only to about ±0.005, and every accuracy difference below is smaller, so none is a conclusion. Its thermal plant is the proposition's own model, so its mean temperatures are no evidence for it. The room temperature was never logged, so the warmer rooms shift the plant's intercept: an extrapolation.</p>
''' + table(["Setting (24-minute missions unless noted)", "Time at or above 80 °C", "Mean / peak temperature", "Power", "Freshness", "sAP against v4.1"],
            [["v4.1 (lab, 2.8 W)", "18 %", "—", "—", "—", "—"],
             ["Budget 2.4 → 4.5 W", "18–21 % at every budget", "73.2 → 78.8 °C", "—", "—", "+0.0007 (2.4 W) / −0.0029 (3.6 W)"],
             ["Hold switched off (diagnostic only)", "0 %", "72.4 / 76.5 °C", "3.07 W", "98.9 %", "−0.0002 ± 0.0004"],
             ["Hold capped at 78 °C", "0 %", "72.8 / 78.0 °C", "3.11 W", "99.4 %", "+0.0000 ± 0.0001"],
             ["Room +5 °C, budget 3.6 W kept / corrected to 3.2 W", "38 % / 37 %", "80.3 / 80.0 °C", "3.73 / 3.67 W", "99.4 %", "−0.0013 / −0.0012"],
             ["Room +10 °C, 3.6 W kept / corrected to 2.8 W", "60 % / 57 %", "81.7 / 81.5 °C", "3.67 / 3.61 W", "99.2 / 99.1 %", "+0.0001 / +0.0004"],
             ["Room +10 °C, capped hold", "57 % (price at its cap 29 % of updates)", "81.5 / 85.0 °C", "3.59 W", "98.7 %", "+0.0003"],
             ["Room +10 °C, cap raised to 10, 20 or 50 (identical runs: the price never passes 7.0)", "42 %", "79.7 / 83.0 °C", "2.85 W", "89.4 %", "−0.0008 ± 0.0003"],
             ["Room-following budget (cap 5): lab / +5 / +10 °C", "0 % / 23 % / 52 % (price at the cap 74 %)", "72.1 / 77.1 / 81.2 °C", "3.05 / 3.23 / 3.54 W (budget 2.65 / 2.39 / 2.56)", "99.3 / 98.2 / 97.9 %", "+0.0008 / +0.0006 / +0.0003"],
             ["<b>Room-following budget + cap 50</b>: +5 / +10 °C", "<b>0 % / 0 %</b>", "73.5 / 77.1 °C", "2.76 / 2.63 W", "94.3 / 88.8 %", "+0.0004 / −0.0016 ± 0.0015"],
             ["<b>Hard guard</b> (78 °C) + capped hold: lab / +5 / +10 / +15 °C", "<b>0 / 0 / 0 %</b> / 84 %", "peak 78.0 / 78.0 / 80.0* / 85.0* °C", "3.11 / 2.99 / 2.73 / 2.61 W", "99.4 / 94.2 / 86.1 / 78.9 %", "+0.0000 / −0.0005 / +0.0001 / −0.0035 ± 0.0003"],
             ["Offload-only floor: lab / +15 °C", "—", "mean 64.9 / 79.9 °C", "—", "—", "—"]]) + '''<ul>
<li><b>Step size (2-minute runs).</b> As η grows from 0.02 to 1, the price term falls from 0.41 to 0.017 W on the mission (0.48 to 0.024 W with random faults), and the excess over the budget falls with it, from 0.79 to 0.52 W (0.52 to 0.16). Theorem 2's gap term grows to 0.55 (0.20) value units per second, but sAP does not fall: at η = 1 it differs from v4.1 by +0.0009 ± 0.0010 (+0.0014 ± 0.0008). We predicted a loss; the idealised O(η) gap is not visible in this system. Over 24 minutes the step size hardly matters: the price term all but vanishes (0.13 to 0.001 W), and the excess stays at 0.54–0.57 W, almost all of it the hold (up to 0.44 W).</li>
<li><b>Where the heat comes from.</b> Hot time is 18–21 % at every budget, though the mean temperature stays below 80 °C as the proposition says (we predicted almost none below 3.2 W). Switching the blackout hold off removes it (18 % → 0 %), so on a long mission with blackouts it is the hold, not the budget, that heats the board. The hardware agrees: the two 24-minute Wi-Fi missions of v4.1 spent 19–27 % of the time at or above 80 °C. Capping the hold at the guard's 78 °C gives 0 % at the same sAP.</li>
<li><b>A warmer room</b> needs two changes together. Correcting the budget by 1/b per degree, as the proposition suggests, barely helps (38 % → 37 %, 60 % → 57 %). Raising the cap alone leaves 42 % at +10 °C, because 2.8 W is too much there (the plant crosses 80 °C at 2.81 W). A budget from an online estimate of the room's offset (the controller's fit inverted) falls as it should, but under the cap of 5 it cannot be enforced. Together, the room-following budget and a cap of 50 give 0 % hot time at +5 and +10 °C, at a cost in freshness (94.3 % and 88.8 %).</li>
<li><b>The hard guard</b> (no onboard inference starts at or above 78 °C) keeps the peak at 78.0 °C in the lab and at +5 °C, with no hot time up to +10 °C. At +15 °C the floor alone averages 79.9 °C, above the guard, so the board is hot 84 % of the time, which by Theorem 3 (a) no controller can avoid. *The replay starts the board at 70 °C plus the room's offset, so at +10 and +15 °C every run starts above the guard, and those peaks are the start temperature. Theorem 3 (b) holds on all 20 guard runs; the replay's radio model makes the bound loose (84.0–85.9 °C). The cost is freshness: 86.1 % at +10 °C against 98.7 % without the guard.</li>
<li><b>A constrained deep-RL baseline</b> (<code>validation/hardware/rl_baseline.py</code>). PPO-Lagrangian: a Lagrange multiplier on the 2.8 W budget, v4.1's actions, a reward for fresh, accurate results, trained on 2-minute episodes from seeds not used for evaluation. Results: 0.036 sAP over 24-minute missions against v4.1's 0.046 (−0.0100 ± 0.0014); −0.0124 ± 0.0039 on 2-minute missions; −0.0038 ± 0.0034 with random faults. It drew 2.43 W against 3.41 W. It keeps the budget, which v4.1 exceeds through its hold and cap, so the comparison is at the same budget, not the same power. Two earlier attempts failed and are reported. In the first, the cost under-charged the radio (it stays on until the acknowledgement). In the second, the multiplier wound up to 88 and the policy only skipped. The fix was to cap the multiplier at 20 and to evaluate the stochastic policy as trained.</li>
<li><b>Noisy relays</b> (the calibrated swarm simulator, both calibrations; 144 settings, 5–20 drones, 5 seeds; one or two air-to-air hops with 3, 6 or 8 dB of shadowing and 0–10 % loss per packet with retransmission). The adaptive policy relayed at most 1.9 % of the camera frames. Whether a relayed frame was on time depended on the swarm (0–100 % across channel profiles and sizes), not on the relay link: within each, noise moved it by at most 8 points. Relaying changed the policy's rate by −0.36 to +0.37 detections/s per drone, at most 4 %. The shared access point, not the relay link, limits the swarm.</li>
</ul>
'''

S22 = '''<h3>19.22 Every prediction against its result</h3>
<p>Each row was committed before its run. "Failed" predictions are kept as written; they are part of the record.</p>
''' + table(["Test (prediction file)", "Prediction", "Verdict"],
            [["Step size (theory_sweep 1–4)", "Theorem 1 holds; price term and excess fall with η; sAP lower at η = 1", "1–3 held; 4 <b>failed</b>: sAP does not fall"],
             ["Budget (5)", "no hot time below 3.2 W; best budget near 3.6 W", "<b>Failed</b>: 18–21 % hot at every budget (the hold)"],
             ["Warmer room, corrected budget (6)", "brings hot time back to the lab's level", "<b>Failed</b>: 37 % and 57 %"],
             ["No hold (7)", "hot time falls well below 18 %; sAP falls", "Held for heat (0 %) and excess; not for sAP (no change)"],
             ["Hold capped at 78 °C (8)", "hot time far below 18 % in the lab and below 58 % at +10 °C", "Held in the lab (0 %); <b>failed</b> at +10 °C (57 %)"],
             ["Higher cap (9)", "lowers hot time at +10 °C, more at higher caps", "Partly: 57 % → 42 %, but every cap above 7 is the same"],
             ["Room-following budget (10)", "near 2.8 W in the lab; lower budget and hot time when warmer", "Lab right; budget falls as predicted but hot time barely moves (price at its cap)"],
             ["Hard guard (11)", "peak ≤ 78.5 °C and 0 % hot to +10 °C; > 50 % hot at +15 °C", "Mostly right; the +10/+15 °C peaks are the replay's start temperature; sAP at +15 °C narrowly outside the predicted 0.003"],
             ["Room-following budget + cap 50 (12)", "0 % hot at +5 °C within 0.15 W of budget; < 15 % hot at +10 °C", "Mostly right: 0 % and 0 %, but power 0.48 W above the budget at +5 °C"],
             ["Floor (13)", "62–67 °C in the lab; above 78 °C at +15 °C", "Right (64.9 and 79.9 °C)"],
             ["RL baseline (14–15)", "power within 0.3 W of 2.8 W; does not beat v4.1, below it somewhere", "14 narrowly missed (2.43 W); 15 right (below in all three)"],
             ["Video codecs (codec_family V1–V4)", "fewer bytes than JPEG; B_be falls; 0 exceptions", "Held in direction; savings larger than predicted"],
             ["Learned image codecs (L1–L3)", "about half the bytes; encoders too slow for the boards", "Held; cheng2020 run at quality 1 only"],
             ["Second detector (1–4)", "post-hoc > Q95; codes 3–15 KiB; 0 exceptions; Pi B_be within 2× of YOLOv8s", "Held; the size range was misstated (26 KiB at 32 channels, as for YOLOv8s); new: no Pi win at all"],
             ["Inter-frame codes (1–4)", "exact reproduction; 5–30 % saving; B_be unchanged; ≤ 260 wins", "Held; saving 26–32 % (2 points above the range); wins exactly 260"],
             ["ROI JPEG (1–4)", "regions 20–50 %; 10–40 % saving; encode 1.5–2×; B_be falls less than with video", "1 and 4 held; 2 <b>failed</b> (0 %); 3 <b>failed</b> in size (6.2×)"]]) + '''
'''

S23 = '''<h3>19.23 What the board session must test (prepared, predictions committed)</h3>
<p>Everything above that touches heat or the controller's settings is a replay or model result until the boards confirm it. The session is scripted and dry-run (<code>tools/dryrun_board_session.sh</code>), with its predictions in <code>docs/board_session_predictions_nov.md</code>, committed before any run. About 5 h on the mesh.</p>
<ul>
<li><b>Planner campaign</b> (<code>REPS=2 tools/campaign_mesh4.sh</code>, 18 runs): v4.1 against the AccuMO-style planner and the LEAF-style fixed weight. Replay prediction: planner ahead by +0.0018 to +0.0045, within the replay's known bias.</li>
<li><b>Energy test</b> (<code>tools/campaign_energy_nov.sh</code>): pricing on and off with the paths fixed, to isolate the energy mechanism.</li>
<li><b>Noisy relay</b> (<code>tools/campaign_relaynoise_nov.sh</code>): multihop with 2 % and 5 % loss and jitter.</li>
<li><b>To add from 19.21:</b> the hold capped at 78 °C and the hard guard over 24-minute missions with blackouts (the heat claim of paper 2 depends on it); the room-following budget; a run with airflow over the Pi (in flight, propeller wash cools the board); and x264 encode times measured on the Pi, to replace the scaled ones of 19.19.</li>
</ul>
'''

STATE = '''<div class="box state"><b class="h">State on 12 Nov 2026: both papers hardened on the laptop (19.15–19.23); the board session is prepared, not yet run</b>
<ul>
<li><b>Paper 1 (19.16–19.19):</b> a split beats the image only below a break-even goodput B_be that a short proposition gives, with 0 exceptions in every model check, across: the jointly trained codes; the 18-quality JPEG grid; a detector tuned on JPEG; an entropy coder (52–73 % smaller codes, same B_be); bootstrap intervals; energy (a split never saves energy on a Pi); video (B_be 9.84 → 1.51 Mbit/s on the Jetson); inter-frame codes; learned image codecs; ROI JPEG; a second detector. Under fading the constant bound fails on fast devices; a spread-discounted version holds.</li>
<li><b>Paper 2 (19.20–19.21):</b> Theorem 1 (power) is checked on all 66,655 logged updates; the budget rule predicts the board's mean temperature within 1.6 °C. The remaining heat on long missions comes from the blackout hold, and capping it at 78 °C removes it in the replay. A room-following budget with a higher price cap handles a 10 °C warmer room. Theorem 3 bounds the peak under a hard guard and says where no controller can help. A PPO-Lagrangian baseline trails v4.1.</li>
<li><b>Every prediction was committed before its run</b> (19.22): several failed, and they are reported as failed.</li>
</ul>
</div>
'''

ARG = '''<h3>8. When a split can pay off is predictable</h3>
<p>A split of the detector can beat sending the image only below a break-even goodput, set by the cheapest image that matches the code's accuracy and by the device's speed, not by the code's own size (19.17). No better coder raises it. It held in every check: jointly trained codes, a detector tuned on JPEG, an entropy coder, video, inter-frame codes, learned and ROI image codecs, a second detector. On fading links only its spread-discounted version holds. On a Pi the window is below about 2 Mbit/s and a split never saves energy; with low-delay video it is 1.5 Mbit/s even on a Jetson.</p>
<h3>9. The priced controller's guarantees, and where its heat came from</h3>
<p>Mean power stays below the budget plus named terms on every logged run (Theorem 1), and the budget sets the board's mean temperature (within 1.6 °C). On long missions with blackouts the board was still hot 19–27 % of the time, and the replay traces this to the controller's own blackout hold. A hold capped at 78 °C, a room-following budget and a hard guard with a proved peak bound remove it in the replay; the board session must confirm it (19.20–19.23).</p>
'''

NEG = '''<li>The constant-goodput break-even bound fails under fading on fast devices (14–24 % of simulated wins above it); only the spread-discounted version holds, and it is empirical (19.17).</li>
<li>A coarse JPEG grid overstated where splits pay off (657 against 548 cells), and the one apparent Pi win of a jointly trained code was an artefact of it (19.17).</li>
<li>Region-of-interest JPEG with feedback saved nothing; learned image codecs are too expensive for either board; the YOLO11s codes never win on the Pi (19.19).</li>
<li>The priced controller left the board hot 19–27 % of the time on 24-minute missions with blackouts, through its hold; at +10 °C the 2.8 W budget is too high, and a higher cap alone does not fix it (19.21).</li>
<li>The constrained deep-RL baseline trails v4.1, and its first two training attempts failed (19.21).</li>
'''

FAULTS = [["Windows memory watchdog stopped all jobs at once (11 Nov, 23:29 IST)", "About two hours lost; no results lost (all jobs resumable)", "One GPU job at a time, at most 2–3 replay shards, a watcher on every chain"],
          ["RL baseline: the cost charged the radio only for the transfer (<code>rl_baseline.py</code>)", "First training attempt under-charged energy", "Radio charged until the acknowledgement, within 3 % of the billed power; attempt archived"],
          ["RL baseline: the Lagrange multiplier wound up to 88", "The trained policy only skipped (availability 0)", "Multiplier capped at 20, step 0.1; stochastic policy evaluated; attempt archived"],
          ["YOLO11s analysis re-timed its codes on every run (<code>second_detector.py</code>)", "Win count moved between runs (223 against 220)", "Timings measured once and kept in <code>code_timings.json</code>; re-runs identical"],
          ["Paper 2 build checks read a stale LaTeX log (no latexmk)", "Clean builds reported that had not been checked", "Built with pdflatex + bibtex; 9 pages, no undefined references"],
          ["Checkpoints saved by scripts run as <code>__main__</code> (joint, JPEG-tuned)", "Loading them elsewhere failed", "Set <code>__main__.&lt;Class&gt;</code> before loading"],
          ["IST times written in two prediction notes ran ahead of the clock", "Notes up to 45 min later than their commits", "Corrected from the git commit times"],
          ["RL baseline intervals used 1.96 instead of Student's t (<code>paper2/make_metrics.py</code>)", "Intervals of 5–10 pairs 13–30 % too narrow", "t quantiles; all three differences still exclude zero"],
          ["Paper 2 stated the caps on λ_F and μ_e without saying they were added on 13 Oct", "36 runs of 11–12 Oct read as if capped", "Found by <code>price_rules_check.py</code>; stated in paper 2"]]

TASKS = [["The board session of 19.23 (planner, energy test, noisy relay; plus the capped hold, the hard guard, the room-following budget, airflow, Pi encode times)", "The mesh (<code>push_code_mesh.sh</code> first)", "about 5 h + additions"],
         ["Rewrite both papers around the new results and audit each with a fresh reader; paper 2 is 9 pages, check the venue's limit", "The laptop", "1–2 days"],
         ["Paper 1's arXiv version: authors, repository URL and your approval (<code>make_arxiv.py</code> refuses to build while placeholders remain)", "You", "—"],
         ["<s>Bottleneck trained together with the detector</s> <b>Done</b> (19.16)", "—", "—"]]

FILES = [["<code>paper/drafts/design_rule.tex</code>", "Paper 1 journal-version section: the break-even rule and every test (19.16–19.19)"],
         ["<code>evaluation/break_even_rule.py</code>, <code>break_even_sim.py</code>, <code>break_even_ci.py</code>, <code>energy_break_even.py</code>", "The rule, its simulator test, bootstrap intervals, energy version"],
         ["<code>evaluation/joint_bottleneck.py</code>, <code>jpeg_tuned_detector.py</code>, <code>entropy_bottleneck.py</code>", "Jointly trained codes, the JPEG-tuned detector, the entropy-coded codes"],
         ["<code>evaluation/video_codecs.py</code>, <code>interframe_codes.py</code>, <code>learned_image_codecs.py</code>, <code>roi_jpeg.py</code>, <code>second_detector.py</code>", "Stronger image codecs, inter-frame codes, YOLO11s; results under <code>experiments/results/</code> (video_codecs, interframe_codes, learned_image_codecs, roi_jpeg, second_detector)"],
         ["<code>paper2/</code>: <code>main.tex</code>, <code>make_metrics.py</code>, <code>theory_check.py</code>, <code>guard_theorem.py</code>", "Paper 2, its generated numbers, the Theorem 1 check, the Theorem 3 constants and replay check"],
         ["<code>validation/hardware/replay_theory_sweep.py</code>, <code>rl_baseline.py</code>", "The replay sweeps of 19.21 and the PPO-Lagrangian baseline"],
         ["<code>docs/*predictions*.md</code>, <code>docs/novelty_roadmap_nov11.md</code>, <code>docs/laptop_tasks_nov11.md</code>", "Predictions with their results, the roadmap, the task list"]]


def rows_html(rows):
    return "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>\n" for r in rows)


def rows_md(rows):
    from report_parts_oct22 import inline
    return "".join("| " + " | ".join(inline(c) for c in r) + " |\n" for r in rows)


SECS = S15 + S16 + S17 + S18 + S19 + S20 + S21 + S22 + S23
TAG_H = "<!-- hardening-nov12 -->"


def strip_marked(s, a, b):
    """Remove every block between the start marker a and end marker b (inclusive)."""
    return re.sub(re.escape(a) + r".*?" + re.escape(b) + r"\n*", "", s, flags=re.S)


def main():
    h, m = HTML.read_text(), MD.read_text()
    if not (ARCH / HTML.name).exists():
        ARCH.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HTML, ARCH / HTML.name)
        shutil.copy2(MD, ARCH / MD.name)
    # sections 19.15-19.23: before Part 20, after 19.14
    j = h.index('<h2 id="argument">')
    assert 0 <= h.find("<h3>19.14 ") < j, "run report_clock_nov10.py first"
    i = h.find("<h3>19.15 ")
    h = h[:i if 0 <= i < j else j] + SECS + h[j:]
    j = m.index("## PART 20")
    i = m.find("### 19.15 ")
    m = m[:i if 0 <= i < j else j] + html_to_md(SECS) + m[j:]
    # Part 19's title
    old19 = "(22–26 Oct 2026; C1–C7 done; corrected 28 Oct)"
    new19 = "(22–26 Oct 2026; C1–C7 done; corrected 28 Oct); laptop additions to 12 Nov, including the hardening of both papers (19.15–19.23)"
    if new19 not in h:
        assert h.count(old19) >= 1 and m.count(old19) >= 1
        h, m = h.replace(old19, new19), m.replace(old19, new19)
    # state box (Part 1), before the 26 Oct box
    h = strip_marked(h, "<!--state12-->", "<!--/state12-->")
    k = h.index('<div class="box state"><b class="h">State on 26 Oct 2026')
    h = h[:k] + "<!--state12-->" + STATE + "<!--/state12-->\n" + h[k:]
    m = strip_marked(m, "<!--state12-->", "<!--/state12-->")
    k = m.index("**State on 26 Oct 2026")
    m = m[:k] + "<!--state12-->\n" + html_to_md(STATE) + "<!--/state12-->\n\n" + m[k:]
    # Part 20: sections 8-9 before the negatives, and new negatives
    h = strip_marked(h, "<!--arg12-->", "<!--/arg12-->")
    k = h.index("<h3>Honest negatives, also part of the paper</h3>")
    h = h[:k] + "<!--arg12-->" + ARG + "<!--/arg12-->\n" + h[k:]
    m = strip_marked(m, "<!--arg12-->", "<!--/arg12-->")
    k = m.index("### Honest negatives, also part of the paper")
    m = m[:k] + "<!--arg12-->\n" + html_to_md(ARG) + "<!--/arg12-->\n\n" + m[k:]
    h = strip_marked(h, "<!--neg12-->", "<!--/neg12-->")
    k = h.index("</ul>", h.index("<h3>Honest negatives, also part of the paper</h3>"))
    h = h[:k] + "<!--neg12-->" + NEG + "<!--/neg12-->\n" + h[k:]
    m = re.sub(r"(?m)^- .*\(19\.(17|19|21)\)\.\n", "", m)
    k = m.index("\n\n## PART 21", m.index("### Honest negatives"))
    m = m[:k] + "\n" + html_to_md("<ul>" + NEG + "</ul>").rstrip("\n") + m[k:]
    # Part 21 faults, Part 23 tasks, Part 24 files (rows appended to each table; md rows likewise)
    for part, nxt, rows, first in (("PART 21", "PART 22", FAULTS, False), ("PART 23", "PART 24", TASKS, True),
                                   ("PART 24", "PART 25", FILES, False)):
        idh = {"PART 21": "bugs", "PART 23": "next", "PART 24": "files"}[part]
        a = h.index(f'<h2 id="{idh}">')
        seg_end = h.index("</table>", a)
        seg = h[a:seg_end]
        for r in rows:
            seg = seg.replace("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>\n", "")
        if first:
            hr = seg.index("</tr>", seg.index("<tr><th")) + len("</tr>\n")
            seg = seg[:hr] + rows_html(rows) + seg[hr:]
        else:
            seg = seg + rows_html(rows)
        h = h[:a] + seg + h[seg_end:]
        a = m.index(f"## {part}")
        b = m.index(f"## {nxt}", a)
        seg = m[a:b]
        for line in rows_md(rows).splitlines(keepends=True):
            seg = seg.replace(line, "")
        lines = seg.split("\n")
        tbl = [n for n, line in enumerate(lines) if line.startswith("| ")]
        ins = (tbl[1] + 1) if first else (tbl[-1] + 1)
        lines[ins:ins] = rows_md(rows).rstrip("\n").split("\n")
        m = m[:a] + "\n".join(lines) + m[b:]
    HTML.write_text(h)
    MD.write_text(m)
    print("Results Brief updated: 19.15-19.23, state box, Part 20 sections 8-9 and negatives, Parts 21, 23, 24")


if __name__ == "__main__":
    main()
