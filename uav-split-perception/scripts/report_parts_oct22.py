#!/usr/bin/env python3
"""Adds the 20-22 Oct 2026 work to the report (repo root: "AEGIS-UAV Results Brief.html" and ".md"):
new Parts 17 (VisDrone fine-tuning, onboard sAP and throttling = task A), 18 (relay path and offloading with the
VisDrone weights = task B) and 19 (standard-metric rescoring = task C); later Parts renumbered 20-25; Part 1, the
fault table, "What is left" and "Where everything is" extended. Every number is copied from the result files named
in the text. The HTML is the source; the Markdown blocks are rendered from the same HTML by html_to_md().
Idempotent: refuses to run twice (looks for id="visdrone").
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
HTML = ROOT / "AEGIS-UAV Results Brief.html"
MD = ROOT / "AEGIS-UAV Results Brief.md"
V, P = '<span class="tag v">Validated</span>', '<span class="tag p">Pending</span>'


def table(head, rows):
    h = "<tr>" + "".join(f"<th>{c}</th>" for c in head) + "</tr>"
    body = "".join("<tr>" + "".join(f'<td class="n">{c}</td>' if i else f"<td>{c}</td>" for i, c in enumerate(r))
                   + "</tr>\n" for r in rows)
    return f'<div class="tbl"><table>\n{h}\n{body}</table></div>\n'


PART17 = f'''<h2 id="visdrone"><span class="num">PART 17</span>VisDrone-trained detectors on the Pi: streaming accuracy and thermal throttling (20–21 Oct 2026)</h2>
<p>Question from the professor: what streaming AP do YOLOv8s, YOLOv8m and YOLOv8l reach when they run ONBOARD the camera drone (Raspberry Pi 5) on the VisDrone video test clips, and how does thermal throttling change it, in short and in long runs? Until now every detector was the COCO-trained model, which has never seen aerial imagery; all results in this Part use detectors fine-tuned on VisDrone. {V}</p>
<h3>17.1 Fine-tuning on VisDrone</h3>
<ul>
<li><b>Data</b> (<code>scripts/prepare_visdrone_finetune.py</code>): VisDrone2019-DET train (6,471 aerial images) plus the VisDrone2019-VID <i>train</i> clips (every 5th frame, resized to 640 px wide exactly like the camera stream). VisDrone classes mapped to the COCO ids the whole project uses (pedestrian, people → person; car, van → car; truck; bus; motor → motorcycle; bicycle), 8 output classes, ignored regions and tricycles dropped. Model selection on VisDrone2019-DET val. The 7 VID <i>val</i> clips, the test stream of every live run, were never used for training or selection.</li>
<li><b>Training</b> (<code>scripts/train_visdrone.py</code>, laptop RTX 4050 6 GB): from the COCO weights, 640 px, seed 0; YOLOv8s 80 epochs (batch 8, 2.8 h), YOLOv8m 60 epochs (batch 4, 4.1 h), YOLOv8l 50 epochs (batch 4, 5.1 h); best epoch by DET-val mAP. Weights: <code>weights/yolov8{{s,m,l}}_visdrone.pt</code>.</li>
</ul>
{table(["Model", "COCO weights: mAP50-95 on VisDrone-DET val", "VisDrone weights (training)", "VisDrone weights (re-measured, project pipeline)", "Gain"],
       [["YOLOv8s", "0.107", "0.266", "0.2671", "×2.5"], ["YOLOv8m", "0.146", "0.296", "0.2972", "×2.0"],
        ["YOLOv8l", "0.164", "0.313", "0.3131", "×1.9"]])}
<p>The re-measurement with the project's own validation code (batch 1, <code>validation/hardware/variant_accuracy.py</code>) matches the training numbers, which also confirms that the class mapping is consistent end to end. The same code measured every setting the controller can choose (input size × JPEG quality) with the VisDrone weights, for the offloading tests of Part 18 (<code>experiments/results/hardware/variant_accuracy_visdrone_ft.json</code>; the COCO entries in it are unchanged):</p>
{table(["VisDrone-trained model, input", "raw frame", "JPEG q90", "JPEG q50", "JPEG q35"],
       [["YOLOv8s 640 px", "0.2671", "0.2563", "0.2030", "0.1883"], ["YOLOv8s 480 px", "–", "0.2022", "0.1570", "–"],
        ["YOLOv8s 320 px", "0.1367", "0.1296", "0.0957", "–"], ["YOLOv8m 640 px", "0.2972", "0.2759", "0.2097", "–"],
        ["YOLOv8l 640 px", "0.3131", "–", "–", "–"]])}
<h3>17.2 The onboard test</h3>
<ul>
<li><b>Boards:</b> two new Raspberry Pi 5 (8 GB, fanless, Debian 13, PyTorch 2.14 CPU): pi2 <code>sengar@192.168.0.129</code> ("pi-relayyy") and pi3 <code>dubey@192.168.0.247</code> ("pi-sender"), run in parallel, one model alone on each Pi (policy <code>fixed:onboard:&lt;model&gt;</code>, 3 CPU threads, conf 0.01), streaming the 7 test clips at 30 fps.</li>
<li><b>Runs per model and Pi:</b> 2 <b>hot-start short</b> runs (4 min, started straight after the previous run, board 63–74 °C), 2 <b>cool-start short</b> runs (the Pi first cooled below 55 °C on pi2 and 61 °C on pi3, its idle floor), 1 <b>long</b> run (24 min = six 4-minute windows, cool start). 10 runs per model, 30 in all (all files checked: 7,196 frames per short run, results = detections, clock log present, model as intended).</li>
<li><b>Logged at 1 Hz:</b> Pi power (PMIC), temperature, ARM clock (<code>vcgencmd measure_clock arm</code>) and the firmware throttle flag (<code>get_throttled</code>, bit 2 = throttled now).</li>
<li><b>Scored</b> (<code>validation/hardware/onboard_throttle_analysis.py</code>): sAP with the standard newest-result rule, with and without forecaster v2; sAP50; mAP (each result against its own frame, i.e. accuracy without delay). Folders <code>vid_campaign_onboard{{,_cool,_long}}_vd_{{pi2,pi3}}</code> (s, m) and <code>*_vd_l_{{pi2,pi3}}</code> (l); summary <code>onboard_sap/throttle_analysis_visdrone.json</code>.</li>
</ul>
<h3>17.3 Results</h3>
{table(["Model, runs", "mAP", "sAP", "sAP + forecaster", "sAP50", "time per frame", "Pi power", "temp start → mean (max)", "clock", "throttled-time ratio"],
       [["YOLOv8s, hot short (4)", "0.242", "0.0062", "0.0162", "0.0183", "728 ms", "4.43 W", "70 → 85 °C (87)", "1668 MHz", "73 %"],
        ["YOLOv8s, cool short (4)", "0.243", "0.0061", "0.0172", "0.0168", "718 ms", "4.71 W", "60 → 84 °C (87)", "1759 MHz", "64 %"],
        ["YOLOv8s, long (2)", "0.232", "0.0051", "0.0139", "0.0147", "752 ms", "4.29 W", "60 → 85 °C (88)", "1570 MHz", "89 %"],
        ["YOLOv8m, hot short (4)", "0.256", "0.0053", "0.0082", "0.0114", "1615 ms", "4.80 W", "63 → 85 °C (88)", "1675 MHz", "77 %"],
        ["YOLOv8m, cool short (4)", "0.254", "0.0046", "0.0080", "0.0104", "1635 ms", "4.75 W", "62 → 85 °C (88)", "1651 MHz", "78 %"],
        ["YOLOv8m, long (2)", "0.245", "0.0035", "0.0057", "0.0082", "1726 ms", "4.38 W", "62 → 87 °C (89)", "1487 MHz", "95 %"],
        ["YOLOv8l, hot short (4)", "0.274", "0.0011", "0.0014", "0.0035", "3257 ms", "4.57 W", "74 → 86 °C (89)", "1542 MHz", "94 %"],
        ["YOLOv8l, cool short (4)", "0.268", "0.0008", "0.0015", "0.0025", "3238 ms", "4.71 W", "63 → 86 °C (89)", "1598 MHz", "84 %"],
        ["YOLOv8l, long (2)", "0.253", "0.0008", "0.0011", "0.0021", "3474 ms", "4.42 W", "64 → 88 °C (91)", "1426 MHz", "97 %"]])}
<p>Long runs window by window (mean of the two 24-minute runs; mAP in each window is the accuracy of the results delivered in it):</p>
{table(["Model", "minutes", "sAP + forecaster", "mAP", "time per frame", "temperature", "clock", "throttled-time ratio"],
       [["YOLOv8s", "0–4", "0.0168", "0.245", "725 ms", "84.1 °C", "1714 MHz", "69 %"], ["YOLOv8s", "4–8", "0.0127", "0.223", "752 ms", "85.5 °C", "1544 MHz", "93 %"],
        ["YOLOv8s", "12–16", "0.0123", "0.229", "755 ms", "85.6 °C", "1526 MHz", "94 %"], ["YOLOv8s", "20–24", "0.0125", "0.228", "755 ms", "85.7 °C", "1560 MHz", "92 %"],
        ["YOLOv8m", "0–4", "0.0090", "0.247", "1650 ms", "84.9 °C", "1651 MHz", "81 %"], ["YOLOv8m", "4–8", "0.0055", "0.239", "1686 ms", "86.9 °C", "1503 MHz", "97 %"],
        ["YOLOv8m", "12–16", "0.0061", "0.242", "1747 ms", "87.3 °C", "1442 MHz", "99 %"], ["YOLOv8m", "20–24", "0.0052", "0.239", "1761 ms", "87.3 °C", "1435 MHz", "98 %"],
        ["YOLOv8l", "0–4", "0.0015", "0.265", "3225 ms", "85.3 °C", "1622 MHz", "84 %"], ["YOLOv8l", "4–8", "0.0016", "0.244", "3400 ms", "87.6 °C", "1438 MHz", "100 %"],
        ["YOLOv8l", "12–16", "0.0015", "0.240", "3492 ms", "88.6 °C", "1379 MHz", "100 %"], ["YOLOv8l", "20–24", "0.0015", "0.266", "3559 ms", "89.0 °C", "1349 MHz", "100 %"]])}
<h3>17.4 What throttling costs</h3>
<p>The firmware lowers the ARM clock from 2.4 GHz once the Pi reaches about 80 °C. Each run's sAP at the inference time the full clock would give (measured time × mean clock / 2,400 MHz) was read off the emulation curve of 17.5 (the same detections and the same scorer, only the delay changed):</p>
{table(["Model (all 10 runs)", "time per frame: measured → at 2.4 GHz", "sAP: measured → at 2.4 GHz", "sAP + forecaster: measured → at 2.4 GHz"],
       [["YOLOv8s", "≈ 730 → 490–525 ms", "0.005 → 0.008", "0.018 → 0.030–0.033"], ["YOLOv8m", "≈ 1620–1730 → 1070–1120 ms", "0.005 → 0.0065", "0.0067 → 0.012"],
        ["YOLOv8l", "≈ 3240–3470 → 2060–2160 ms", "0.0017 → 0.0018", "0.0019 → 0.0044–0.0048"]])}
<ul>
<li><b>Throttling roughly halves streaming accuracy</b> (with the forecaster: s −42 %, m −43 %, l −58 %). It does <b>not</b> change mAP: the detector is as accurate as before, its results simply arrive later and are held longer.</li>
<li><b>Cooling the board first barely helps.</b> A cool start throttles within about a minute (64–84 % of the short run throttled), and its sAP is the same as a hot start within the run-to-run spread. Over 24 minutes the clock keeps sinking (s 1714 → 1560 MHz, l 1622 → 1349 MHz) and inference slows by 4–10 %.</li>
</ul>
<h3>17.5 Why onboard sAP is so low, and what would raise it</h3>
<p>Emulation (<code>validation/hardware/onboard_sap.py</code>): the laptop computes each model's detections on every test frame exactly as the Pi does; a single engine then takes the newest frame every L ms and the drone holds each result until the next one arrives. Same scorer as the live runs:</p>
{table(["Delay per result L", "YOLOv8s-VisDrone sAP / + forecaster", "YOLOv8m-VisDrone", "YOLOv8l-VisDrone"],
       [["33 ms (keeps up with 30 fps)", "0.165 / 0.217", "0.175 / 0.230", "0.184 / 0.241"],
        ["100 ms", "0.060 / 0.152", "0.063 / 0.159", "0.068 / 0.171"], ["300 ms", "0.013 / 0.056", "0.016 / 0.058", "0.014 / 0.068"],
        ["600 ms", "0.007 / 0.023", "0.009 / 0.025", "0.007 / 0.026"], ["1000 ms", "0.003 / 0.010", "0.007 / 0.013", "0.005 / 0.013"],
        ["3000 ms", "0.002 / 0.002", "0.002 / 0.002", "0.002 / 0.002"]])}
<ul>
<li><b>The detectors work; the delay is what destroys sAP.</b> mAP is 0.24–0.27 on the test clips (at the level published for these models on VisDrone, a hard dataset: 91 % of the test objects are smaller than 32 × 32 px). sAP charges for the delay: after 0.7–3.3 s a small object seen from a moving drone has moved further than its own size, so the old box no longer overlaps it (IoU &lt; 0.5) and counts as a miss.</li>
<li><b>The most accurate model is the worst onboard.</b> YOLOv8l has the best mAP but, at 3.3 s per frame, the lowest sAP; on the Pi alone YOLOv8s is the right choice.</li>
<li><b>A Pi alone cannot deliver usable streaming perception on drone video.</b> 15–20 % sAP needs results within about 100 ms plus forecasting; only offloading provides that (Part 18). This is the motivation for the three-tier system, measured now with the right weights.</li>
</ul>
<h3>17.6 What the VisDrone weights changed</h3>
<p>The same onboard test was first run with the COCO weights (hot short, cool short and long runs on both Pis, 20–21 Oct; folders <code>vid_campaign_onboard{{,_cool,_long}}_{{pi2,pi3}}</code>; superseded by this Part and kept only for this comparison):</p>
{table(["Hot-start short runs", "mAP COCO → VisDrone", "sAP COCO → VisDrone", "sAP + forecaster COCO → VisDrone"],
       [["YOLOv8s", "0.088 → 0.242 (×2.7)", "0.0014 → 0.0062 (×4.4)", "0.0045 → 0.0162 (×3.6)"],
        ["YOLOv8m", "0.117 → 0.256 (×2.2)", "0.0025 → 0.0053 (×2.1)", "0.0042 → 0.0082 (×2.0)"],
        ["YOLOv8l", "0.134 → 0.274 (×2.0)", "0.0004 → 0.0011 (×2.8)", "0.0005 → 0.0014 (×2.8)"]])}
<p>Timing, power and throttling were the same with both weight sets (identical architectures). Caveats: at 2–3.5 s per frame a 4-minute run holds only about 75 YOLOv8l results, so its sAP values are small and noisy; the full-clock figures are computed from the emulation, not measured; one camera at a time, lab temperature, fanless boards.</p>
'''

PART18 = f'''<h2 id="relay"><span class="num">PART 18</span>Offloading with the VisDrone weights, and the relay path Pi → Jetson → laptop (22 Oct 2026, running)</h2>
<p>Part 17 shows the camera drone cannot perceive well alone. This Part measures the offloading paths with the VisDrone weights and adds the professor's chain, the camera drone sending through the edge drone to the ground station, as a <b>fallback path</b> of the adaptive controller (for a camera beyond the ground station's range), not as a replacement for the direct three-tier design. {P}</p>
<h3>18.1 What was built</h3>
<ul>
<li><b>Relay</b> (<code>validation/hardware/relay.py</code>, on the Jetson): toward the camera it behaves like a worker (connects to the Pi on port 48103); toward the ground like a camera (a normal laptop worker connects to it on port 48104). Frames, probes and the final message pass unchanged both ways, so relayed results are scored exactly like direct ones and the camera's probe round trip covers both hops. The relay holds its camera link only while a ground worker is connected, so an unreachable ground station shows up at the camera as a dead path instead of frames that never return.</li>
<li><b>Controller</b> (<code>adaptive2.py --paths laptop,jetson,relay</code>): the relay is one more path with the laptop's settings (YOLOv8s at 640/480/320 px and YOLOv8m at 640 px, JPEG q90/q50); its rate is measured on the Pi → Jetson hop, its round trip includes both hops. v4.1 chooses among onboard, Jetson, laptop and relay with its unchanged objective; no new decision logic.</li>
<li><b>Network emulation</b> (<code>adaptive.py</code>): a third netem band for the relay port. The relay's first hop is the Pi → Jetson radio link, so it follows the Jetson path's impairment; the Jetson → laptop hop is not impaired (the edge drone stays within the ground station's range). New scenario <b>out_of_range</b>: the direct Pi → laptop link is cut (100 % loss) for the whole run.</li>
<li><b>VisDrone weights everywhere</b> (<code>--weight-suffix _visdrone</code>): onboard models, the laptop and Jetson workers, and the controller's accuracy table (17.1). A fault found on the way: a worker picks its model by name and silently fell back to its first model for an unknown name, so a YOLOv8m request would have been served by YOLOv8s with the fine-tuned files; workers now also answer to the plain model name (Part 21).</li>
<li><b>Fine-tuning YOLOv8n on VisDrone</b> (running), so that v4.1's fastest onboard fallback (YOLOv8n at 320 px) is also VisDrone-trained.</li>
<li><b>Kept:</b> v4.1's staleness-decay curve (forecaster v2, measured with the COCO YOLOv8s on the VID train clips). Re-measuring it with the VisDrone weights would be in-sample, because those clips were part of their training data; the curve is a ratio of accuracy at age t to fresh accuracy and carries over.</li>
<li><b>Scripts:</b> <code>tools/arun_b.sh</code> (one run: VisDrone workers, relay), <code>tools/campaign_b.sh</code> (the campaign), <code>tools/push_code.sh</code> now also takes <code>TARGETS="pi2 nano"</code>.</li>
</ul>
<h3>18.2 First measurements (pi2 camera, Jetson, laptop; 22 Oct)</h3>
{table(["Run", "sAP", "sAP + forecaster", "mAP of results", "results on time (≤ 300 ms)", "age p95", "Pi power, temperature"],
       [["Relay, YOLOv8m q90, normal link (1-min smoke test)", "0.048", "0.157", "0.249", "11.8 /s, fresh 89 % of the time", "400 ms", "2.06 W, 49 °C"],
        ["Pi → Jetson, YOLOv8s q90, normal (4 min)", "0.070", "0.169", "0.231", "16.7 /s, fresh 99.6 %", "200 ms", "2.26 W, 52 °C"],
        ["Pi → Jetson, YOLOv8s q90, mission (4 min)", "0.036", "0.095", "0.241", "fresh 60 % (blackout phases)", "30 s", "2.06 W, 52 °C"],
        ["for comparison: YOLOv8s onboard (Part 17)", "0.006", "0.017", "0.242", "–", "–", "4.4 W, 85 °C"]])}
<ul>
<li><b>Offloading reaches the 15–20 % range.</b> With the forecaster, the Jetson path gives 0.169 and the relay 0.157 sAP: about 10× onboard, with the Pi at half the power and 30 °C cooler (no throttling).</li>
<li>In the mission, per phase (with forecaster): good link 0.189, ground link congested 0.093, ground blackout 0.138, both links degraded 0.031, total blackout 0.001, recovered 0.185. A fixed Jetson policy loses everything in a total blackout; the adaptive controller's onboard fallback exists for that phase. Why the Jetson path drops in the ground-congested phase, which impairs only the laptop path, is being checked.</li>
<li>These are the first single runs, not campaign results; the paired comparison follows in 18.3.</li>
</ul>
<h3>18.3 The campaign (running)</h3>
{table(["", "Design"],
       [["Policies (4)", "fixed Pi → Jetson YOLOv8s q90; fixed Pi → laptop YOLOv8m q90; fixed relay Pi → Jetson → laptop YOLOv8m q90; v4.1 over onboard + Jetson + laptop + relay (live forecaster, power budget 2.8 W, freshness target 0.95)"],
        ["Scenarios (3)", "normal (all links good), mission (congestion and blackouts), out of range (direct Pi → laptop link cut for the whole run)"],
        ["Repetitions", "3 → 36 runs of 4 minutes (six 40-s phases), plus two 24-minute missions (v4.1 and the relay)"],
        ["Fairness", "all three paths connected in every run, so the policies differ only in their decisions; one camera drone (pi2)"],
        ["Order", "the 9 Pi → Jetson runs first, while the laptop GPU trains YOLOv8n (they do not use it), then the 27 runs that need the laptop GPU; so the Pi → Jetson runs were made at a different time of day"],
        ["Scoring", "standard sAP with and without forecaster, sAP50, mAP, freshness (Part 19 metrics), power, temperature; paired differences with Holm correction"]])}
<p>Questions it answers: does v4.1 match the best fixed path on a good link; does it move to the relay when the camera is out of the ground station's range (where fixed Pi → laptop delivers nothing); and how much the extra hop costs against the direct paths. Results folders <code>vid_campaign_b/</code> and <code>vid_campaign_b_long/</code>.</p>
'''

PART19 = f'''<h2 id="rescore"><span class="num">PART 19</span>Every campaign rescored with the standard metrics (22 Oct 2026, running)</h2>
<p>Corrections to how the earlier results (Parts 12–15) are scored and reported, from data already recorded, no new runs (<code>validation/hardware/report_rescore.py</code>; tables in <code>experiments/results/hardware/report_c_tables.md</code>, numbers in <code>report_c_summary.json</code>). 776 runs in 8 campaigns, each scored without and with its forecaster. {P}</p>
{table(["#", "Fix", "How"],
       [["C1", "State the holding rule; report the <b>standard</b> sAP (newest result held) everywhere", "The Phase G tables reported the 'quality' rule (the held result with the highest expected accuracy). The verdicts were already checked to be the same under the standard rule (G14); the standard values now stand next to every reported one"],
        ["C2", "Score with VisDrone's <b>ignored regions masked</b>, as the official protocol does", "A detection or ground-truth box more than 50 % inside an ignored region (category 0) is removed (VisDrone toolkit rule). The 7 test clips have 3,994 ignored-region boxes on 1,434 frames of 5 clips (2 clips have none)"],
        ["C3", "Add <b>sAP50</b>, <b>sAP by object size</b> and <b>worst-case AoI</b>", "Sizes: COCO area ranges in the 640-px frame; of 108,645 test objects 91.2 % are small, 8.8 % medium and only 7 large, so 'large' is not reported. Freshness: 95th-percentile and maximum age of the held result, the longest stretch older than 300 ms, and the fresh share"],
        ["C4", "Results <b>per scenario</b>, and per phase inside the missions", "Normal phases separate from congestion and blackouts"],
        ["C5", "State the <b>assumptions</b>", "see below"],
        ["C6", "<b>Holm correction</b> for multiple comparisons", "Paired differences against each campaign's reference controller with 95 % t-intervals, exact sign-flip permutation p-values (all 2<sup>n</sup> sign patterns, no distribution assumed) and Holm-adjusted p-values within each campaign and metric"]])}
<p><b>Assumptions, stated explicitly (C5).</b> (1) VisDrone-VID frames are replayed at 30 fps; the dataset does not publish its frame rate, so every age in milliseconds scales with this choice. (2) The camera stream is the clips resized to 640 px wide; full resolution would help the small objects but costs transfer and compute. (3) The controller v1 and v2 results (Parts 9–10) used looped COCO photographs and an accuracy-weighted deadline-met throughput, a proxy without sAP. (4) Every campaign up to 13 Oct used the COCO-trained detectors; their absolute sAP is therefore low and not comparable with VisDrone literature, while comparisons between policies within a campaign stand. From Part 17 on, all detectors are VisDrone-trained. (5) Numbers from different campaigns are not comparable (Wi-Fi conditions and board state differ by day): compare within one campaign only.</p>
<p><b>First check.</b> Scoring a G12 mission run (freshness-threshold baseline) gives sAP 0.0159 unmasked (identical to the value cached for G12) and 0.0161 masked; small objects 0.010, medium 0.057; P(AoI > 300 ms) was 34 %, with a longest stale stretch of 22 s (the blackout phase). The full tables are added here when the rescoring completes.</p>
'''

STATE = '''<div class="box state"><b class="h">State on 22 Oct 2026: detectors fine-tuned on VisDrone; onboard study finished; relay path built and its campaign running; every campaign being rescored</b>
<ul>
<li>YOLOv8s, m and l fine-tuned on VisDrone: mAP50-95 on DET val 0.107 → 0.267, 0.146 → 0.297, 0.164 → 0.313 (Part 17).</li>
<li>Onboard on two new Pi 5s (30 runs): mAP 0.24–0.27 but sAP only 0.006 / 0.005 / 0.001 (0.017 / 0.008 / 0.0015 with the forecaster), because a frame takes 0.7 / 1.6 / 3.3 s. The Pi throttles within about a minute even from a cool start; throttling leaves mAP unchanged and roughly halves sAP (Part 17).</li>
<li>Relay path Pi → Jetson → laptop built as a fallback path of v4.1; first measurements with the VisDrone weights: 0.169 sAP (Pi → Jetson) and 0.157 (relay) with the forecaster, about 10× onboard. The 36-run campaign and two 24-minute missions are running (Part 18).</li>
<li>All 776 earlier runs being rescored with the standard sAP, ignored regions masked, sAP50, sizes, worst-case freshness and Holm correction (Part 19).</li>
</ul></div>
'''

FAULTS = '''<tr><td>Worker served an unknown model name with its first model</td><td>With fine-tuned files a YOLOv8m request would have run YOLOv8s</td><td>Workers also answer to the plain model name (22 Oct)</td></tr>
<tr><td>Two copies of the YOLOv8l onboard tests started on the same Pis (a watcher left from an earlier session)</td><td>Runs killed each other (21 Oct)</td><td>All stopped, partial folders archived (<code>_superseded/l_duplicate_launch/</code>), rerun once; one campaign per board, checked before every launch</td></tr>
<tr><td>Campaign recovery pulled same-named runs of another campaign on the same Pi</td><td>Short and long runs mixed (21 Oct)</td><td>Duplicates set aside after checksum comparison; distinct labels and empty folders per campaign</td></tr>
<tr><td>Throttle analysis read the VisDrone model names and folders wrongly</td><td>Empty / NaN summary</td><td>Fixed before any number was reported</td></tr>
'''

LEFT = '''<tr><td><b>Task B</b> (Part 18): the 36-run relay campaign and two 24-minute missions, analysis and report</td><td>pi2, the Jetson and the laptop GPU; unattended</td><td>running, about 7 h</td></tr>
<tr><td><b>Task C</b> (Part 19): rescoring of 776 runs, tables, report</td><td>Laptop CPU</td><td>running, about 4 h</td></tr>
'''

FILES = '''<tr><td><code>weights/yolov8{s,m,l}_visdrone.pt</code>, <code>experiments/finetune/</code>, <code>scripts/prepare_visdrone_finetune.py</code>, <code>scripts/train_visdrone.py</code></td><td>VisDrone fine-tuning: weights, training runs, data preparation</td></tr>
<tr><td><code>experiments/results/hardware/onboard_sap/</code>, <code>vid_campaign_onboard*_vd*</code></td><td>Part 17: onboard runs, emulation, throttling analysis (<code>throttle_analysis_visdrone.json</code>)</td></tr>
<tr><td><code>validation/hardware/relay.py</code>, <code>tools/campaign_b.sh</code>, <code>tools/arun_b.sh</code>, <code>experiments/results/hardware/vid_campaign_b*/</code></td><td>Part 18: relay path and its campaign</td></tr>
<tr><td><code>validation/hardware/report_rescore.py</code>, <code>experiments/results/hardware/report_c_*</code></td><td>Part 19: standard-metric rescoring</td></tr>
'''


def html_to_md(h):
    """Markdown for the blocks this script adds (the report's own markup subset)."""
    out = []
    for blk in re.findall(r"<h2.*?</h2>|<h3>.*?</h3>|<p>.*?</p>|<ul>.*?</ul>|<div class=\"tbl\">.*?</div>|<div class=\"box state\">.*?</div>", h, re.S):
        if blk.startswith("<h2"):
            m = re.search(r'<span class="num">(.*?)</span>(.*?)</h2>', blk)
            out.append(f"## {m.group(1)}{m.group(2)}")
        elif blk.startswith("<h3"):
            out.append("### " + inline(blk[4:-5]))
        elif blk.startswith("<p>"):
            out.append(inline(blk[3:-4]))
        elif blk.startswith("<ul>"):
            out.append("\n".join("- " + inline(li) for li in re.findall(r"<li>(.*?)</li>", blk, re.S)))
        elif 'class="tbl"' in blk:
            rows = re.findall(r"<tr>(.*?)</tr>", blk, re.S)
            cells = [[inline(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", r, re.S)] for r in rows]
            md = ["| " + " | ".join(cells[0]) + " |", "| " + " | ".join("---" for _ in cells[0]) + " |"]
            md += ["| " + " | ".join(r) + " |" for r in cells[1:]]
            out.append("\n".join(md))
        else:
            t = re.search(r'<b class="h">(.*?)</b>', blk, re.S).group(1)
            out.append(f"**{inline(t)}**\n\n" + "\n".join("- " + inline(li) for li in re.findall(r"<li>(.*?)</li>", blk, re.S)))
    return "\n\n".join(out) + "\n\n"


def inline(s):
    s = re.sub(r'<span class="tag [a-z]">(.*?)</span>', r"\1", s)
    s = re.sub(r"</?b>", "**", s)
    s = re.sub(r"</?i>", "*", s)
    s = re.sub(r"</?code>", "`", s)
    s = s.replace("<sup>n</sup>", "^n").replace("&lt;", "<").replace("&gt;", ">").replace("&#60;", "<").replace("&#62;", ">")
    return re.sub(r"\s+", " ", s).strip()


def main():
    h = HTML.read_text()
    m = MD.read_text()
    if 'id="visdrone"' in h:
        sys.exit("already applied")
    # renumber Parts 17-22 -> 20-25 (headings, both files) and the cross-references in the text
    for n in range(22, 16, -1):
        h = h.replace(f'<span class="num">PART {n}</span>', f'<span class="num">PART {n + 3}</span>')
        m = re.sub(rf"^## PART {n}(?=\D)", f"## PART {n + 3}", m, flags=re.M)
        h = re.sub(rf"\bPart {n}\b", f"Part {n + 3}", h)
        m = re.sub(rf"\bPart {n}\b", f"Part {n + 3}", m)
    new = PART17 + "\n" + PART18 + "\n" + PART19 + "\n"
    h = h.replace('<h2 id="argument">', new + '<h2 id="argument">', 1)
    mi = m.index("## PART 20What it all means")
    m = m[:mi] + html_to_md(new) + m[mi:]
    # contents
    toc_new = ('<li><a href="#visdrone">VisDrone-trained detectors on the Pi: streaming accuracy and throttling</a></li>\n'
               '<li><a href="#relay">Offloading with the VisDrone weights, and the relay path</a></li>\n'
               '<li><a href="#rescore">Every campaign rescored with the standard metrics</a></li>\n')
    h = h.replace('<li><a href="#argument">', toc_new + '<li><a href="#argument">', 1)
    # the Markdown contents list is regenerated from the HTML one (it lacked Part 16, so its numbers were off by one)
    nav = h[h.index('<nav class="toc"'):h.index("</nav>")]
    toc_md = "\n".join(f"{i}. [{t}](#{a})" for i, (a, t) in
                       enumerate(re.findall(r'<li><a href="#([^"]+)">(.*?)</a></li>', nav), 1))
    ti = m.index("**Contents**\n\n") + len("**Contents**\n\n")
    m = m[:ti] + toc_md + m[m.index("\n\n", ti):]
    # state box, meta line
    h = h.replace('<h2 id="now"><span class="num">PART 1</span>Where things stand right now</h2>\n',
                  '<h2 id="now"><span class="num">PART 1</span>Where things stand right now</h2>\n' + STATE, 1)
    mi = m.index("## PART 1Where things stand right now\n") + len("## PART 1Where things stand right now\n")
    m = m[:mi] + "\n" + html_to_md(STATE) + m[mi:]
    h = re.sub(r'<div class="meta">Full project report · state on [^<]*</div>',
               '<div class="meta">Full project report · state on 22 Oct 2026, 18:30</div>', h, 1)
    m = re.sub(r"^Full project report · state on .*$", "Full project report · state on 22 Oct 2026, 18:30", m, 1, flags=re.M)
    # faults, what is left, files: rows appended to the existing tables
    for sec, rows in (('id="bugs"', FAULTS), ('id="next"', LEFT), ('id="files"', FILES)):
        i = h.index(sec)
        j = h.index("</table></div>", i)
        h = h[:j] + rows + h[j:]
        title = {'id="bugs"': "## PART 21Faults found and fixed", 'id="next"': "## PART 23What is left",
                 'id="files"': "## PART 24Where everything is"}[sec]
        k = m.index(title)
        k = m.index("\n\n", m.index("| ---", k))
        md_rows = html_to_md('<div class="tbl"><table><tr><th>x</th></tr>' + rows + "</table></div>").split("\n")[2:]
        m = m[:k] + "\n" + "\n".join(r for r in md_rows if r.strip()) + m[k:]
    HTML.write_text(h)
    MD.write_text(m)
    print("report updated")


if __name__ == "__main__":
    main()
