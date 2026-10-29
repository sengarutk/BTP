#!/usr/bin/env python3
"""Report update, 22 Oct 2026 evening: Parts 18 (task B) and 19 (task C) rewritten with everything done since the
first version (relay end-of-run fix, shortened plan, interim B results, VisDrone replay of the earlier campaigns) and
with the expected results and outputs of the work still running; Part 1's state box and "What is left" updated.
Input: B interim scores (one line per run, from the scoring command in the session) in argv[1].
Replaces the HTML between <h2 id="relay"> and <h2 id="argument">, and the Markdown between "## PART 18" and
"## PART 20", so it can be re-run as results arrive.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_parts_oct22 import HTML, MD, P, V, html_to_md, table  # noqa: E402

HW = Path(__file__).resolve().parent.parent / "experiments" / "results" / "hardware"

NAMES = {"jet_s": "fixed Pi → Jetson, YOLOv8s q90", "lap_m": "fixed Pi → laptop, YOLOv8m q90",
         "relay_m": "fixed relay Pi → Jetson → laptop, YOLOv8m q90", "v41": "v4.1 (all paths)"}
SC = {"static_good": "normal", "mission": "mission", "out_of_range": "out of range"}


def b_rows(path):
    rows = []
    for ln in open(path):
        m = re.match(r"(\w+?)__(\w+?)__r(\d) sAP ([\d.]+) fc ([\d.]+) mAP ([\d.]+) fresh ([\d.]+) p95 (\d+) W ([\d.]+) "
                     r"T ([\d.]+) (\{[^}]*\})", ln)
        if not m:
            continue
        sc, pol, rep, s, fc, mp, fr, p95, w, t, srv = m.groups()
        srv = {k.strip(" '"): int(v) for k, v in (x.split(":") for x in srv.strip("{}").split(","))}
        tot = sum(srv.values())
        share = ", ".join(f"{k} {100 * v / tot:.0f} %" for k, v in sorted(srv.items(), key=lambda x: -x[1]))
        rows.append((list(SC).index(sc), list(NAMES).index(pol), int(rep),
                     [SC[sc], NAMES[pol], rep, s, f"<b>{fc}</b>", mp, f"{100 * float(fr):.0f} %", f"{p95} ms",
                      f"{w} W, {float(t):.0f} °C", share]))
    rows.sort(key=lambda r: r[:3])
    return [r[3] for r in rows]


def part18(rows):
    return f'''<h2 id="relay"><span class="num">PART 18</span>Offloading with the VisDrone weights, and the relay path Pi → Jetson → laptop (22 Oct 2026)</h2>
<p>Part 17 shows that the camera drone cannot perceive well alone: the detector is accurate, but a Pi needs 0.7–3.3 s per frame. This Part measures the offloading paths with the VisDrone weights and adds the professor's chain, the camera drone sending through the edge drone to the ground station, as a <b>fallback path</b> of the adaptive controller for a camera beyond the ground station's range. The direct three-tier design stays the main system: the relay is one more option, not a replacement. {V} (36 runs)</p>
<h3>18.1 What was built</h3>
<ul>
<li><b>Relay</b> (<code>validation/hardware/relay.py</code>, on the Jetson): toward the camera it behaves like a worker (connects to the Pi, port 48103); toward the ground like a camera (a normal laptop worker connects to it, port 48104). Frames, probes and the final message pass unchanged both ways, so relayed results are scored exactly like direct ones and the camera's probe round trip covers both hops. The relay keeps its camera link only while a ground worker is connected, so an unreachable ground station appears to the camera as a dead path.</li>
<li><b>Controller</b> (<code>adaptive2.py --paths laptop,jetson,relay</code>): the relay is a third path with the laptop's settings (YOLOv8s at 640/480/320 px, YOLOv8m at 640 px, JPEG q90/q50). Its rate is measured on the Pi → Jetson hop, its round trip includes both hops. v4.1 chooses among onboard, Jetson, laptop and relay with its unchanged objective (Part 16); no new decision logic.</li>
<li><b>Network emulation</b> (<code>adaptive.py</code>): a third netem band for the relay port. The relay's first hop is the Pi → Jetson radio link, so it follows the Jetson path's impairment; the Jetson → laptop hop is not impaired (the edge drone stays in the ground station's range). New scenario <b>out_of_range</b>: the direct Pi → laptop link is cut (100 % loss) for the whole run. Verified on the Pi during the first such run: the laptop band dropped every packet, the Jetson band carried 5.9 MB, the relay band was untouched.</li>
<li><b>VisDrone weights everywhere</b> (<code>--weight-suffix _visdrone</code>): onboard models, the laptop and Jetson workers, and the controller's accuracy table (17.1, all 13 settings). Fault found: a worker picks its model by name and silently fell back to its first model for an unknown name, so a YOLOv8m request would have been served by YOLOv8s with the fine-tuned files; workers now also answer to the plain model name.</li>
<li><b>Kept:</b> v4.1's staleness-decay curve (forecaster v2, measured with the COCO YOLOv8s on the VID train clips). Re-measuring it with the VisDrone weights would be in-sample (those clips are in their training data); the curve is a ratio of accuracy at age t to fresh accuracy and carries over.</li>
<li><b>Scripts:</b> <code>tools/arun_b.sh</code> (one run), <code>tools/campaign_b.sh</code> (the campaign), <code>tools/push_code.sh TARGETS="pi2 nano"</code>.</li>
</ul>
<h3>18.2 The campaign</h3>
{table(["", "Design"],
       [["Policies (4)", "fixed Pi → Jetson YOLOv8s q90; fixed Pi → laptop YOLOv8m q90; fixed relay Pi → Jetson → laptop YOLOv8m q90; v4.1 over onboard + Jetson + laptop + relay (live forecaster, power budget 2.8 W, freshness target 0.95)"],
        ["Scenarios (3)", "normal (all links good); mission (good → ground congested → ground blackout → both degraded → total blackout → recovered); out of range (direct Pi → laptop link cut for the whole run)"],
        ["Repetitions", "3 → 36 runs of 4 minutes (six 40-s phases); camera pi2, edge drone Jetson Orin Nano (15 W), ground station laptop RTX 4050"],
        ["Fairness", "all three paths connected in every run, so the policies differ only in their decisions"],
        ["Scoring", "standard sAP with and without forecaster, sAP50, mAP, AoI, Pi power and temperature, path shares; paired differences with exact permutation tests and Holm correction (Part 19)"]])}
<p><b>Shortened on 22 Oct to free the boards for the mesh work, without losing any of the questions:</b></p>
<ul>
<li><b>Run time halved by a fix, not a cut.</b> Each run took 10.7 min, of which about 5 were spent waiting: the relay passed the camera's end-of-run message on and closed the connection at once, the worker keeps only the newest message, so the end of the connection replaced the unread end message and the worker waited for its 10-minute timeout. The relay now waits for the worker to close first (tested), and the run script stops a lingering relay worker after 20 s. Runs now take about 5.5 min; no measurement was affected (the camera's part of every run was complete).</li>
<li><b>Dropped:</b> the two 24-minute runs (the heat behaviour is covered by Part 17, and an offloading Pi stays at about 50 °C) and the wait for a VisDrone YOLOv8n: v4.1's onboard fallback uses the VisDrone YOLOv8s at 320 and 640 px (it only matters in a total blackout).</li>
<li><b>Kept:</b> 3 repetitions. With 2, a comparison has 6 pairs and the smallest possible exact p-value is 0.031, which cannot pass the Holm correction over 3 comparisons; with 3 repetitions (9 pairs) it is 0.004.</li>
<li>Order: the 9 Pi → Jetson runs were made first (they do not use the laptop GPU, which was training), so they ran at a different time of day than the others.</li>
<li>The laptop restarted twice during the work (17:29 and about 18:40); every run finished before each restart was kept (one was collected from the Pi afterwards), and the campaign resumed.</li>
</ul>
<h3>18.3 Results (all 36 runs)</h3>
<p>Mean over 3 repetitions, standard sAP with the live forecaster ± 95 % CI (<code>experiments/results/hardware/vid_campaign_b_summary.json</code> / <code>.md</code>, <code>validation/hardware/b_summary.py</code>):</p>
{b_table()}
<p>Mission, per phase (sAP with the forecaster, mean of 3):</p>
{b_phases()}
<p>Paired comparisons (reference minus policy; exact permutation p-values, Holm within each reference):</p>
{b_paired()}
<h3>18.4 What the results show</h3>
<ul>
<li><b>Out of range, the relay keeps the drone perceiving.</b> With the direct ground link cut, fixed Pi → laptop delivers nothing (0.000 in 3 of 3 runs) while the relay delivers 0.161 ± 0.032, the best of all policies there, and the Jetson path 0.155. v4.1 moved its laptop-bound frames to the relay and the Jetson by itself (relay 57 %, Jetson 41 %, laptop 0 %) and reached 0.143, slightly below the two fixed paths it switched to (in 3 of 3 pairs, by 0.012–0.018): the cost of trying the dead direct path and of the probes.</li>
<li><b>In the mission, adaptation wins.</b> v4.1 has the highest sAP (0.124 ± 0.007; ahead of the Jetson path by 0.022, the relay by 0.028 and the laptop path by 0.069, in 3 of 3 pairs each), and it is the only policy that still perceives in the total blackout (0.042 against 0.001, onboard YOLOv8s fallback). In the ground blackout the relay (0.172) and the Jetson (0.165) keep working while the laptop path drops to 0.000.</li>
<li><b>On a good link the direct laptop path is best.</b> Fixed laptop YOLOv8m 0.182 ± 0.002, Jetson YOLOv8s 0.159, relay 0.144, v4.1 0.143 ± 0.092 (one weak repetition). The extra hop costs the relay about 0.04 against the direct laptop path (p95 age 444 against 211 ms). v4.1 sent 56 % of its frames to the laptop and the rest to the Jetson and the relay; with all three remote paths sharing one Wi-Fi channel, spreading frames did not pay on a good link here.</li>
<li><b>Overall (9 pairs per comparison):</b> v4.1 0.137, Jetson 0.139, relay 0.134, laptop 0.079 (pulled down by the out-of-range runs); v4.1 keeps P(AoI ≤ 300 ms) at 93 % against 44–84 % for the fixed paths, with a 95th-percentile AoI of 0.33 s against 10–88 s.</li>
<li><b>Cost on the camera drone:</b> every policy keeps the Pi far below its throttling point (2.1–3.4 W, 54–69 °C, against 4.4 W and 85 °C onboard); v4.1 uses about 0.9 W more than the fixed paths because of its onboard fallback.</li>
<li><b>Statistics:</b> with 3 repetitions per scenario no single-scenario comparison can pass a permutation test (smallest possible p = 0.25), and the pooled comparisons mix scenarios in which the ranking reverses, so none is significant after Holm. The out-of-range effect of the relay is nonetheless unambiguous (0.161 against 0.000, 3 of 3, the 95 % interval far from zero). Settling the normal-link ranking of v4.1 needs more repetitions (5 per scenario would allow p = 0.03 per scenario).</li>
<li><b>Phase-to-phase changes are partly the video:</b> the Jetson and relay paths score 0.08–0.09 in the mission's "ground congested" phase, which limits only the direct laptop path, but they score the same in the same phase of the normal-link runs (0.07–0.09), where nothing is impaired: the 7 test clips play in a fixed order and that phase holds the hardest scenes (figure in 18.7). Policies are therefore compared within a phase, never across phases.</li>
</ul>
<h3>18.5 Expected against measured</h3>
{table(["Question", "Expected", "Measured"],
       [["Out of range: does the relay keep perception alive?", "laptop ≈ 0; relay and Jetson ≈ 0.15–0.17; v4.1 moves to them", "<b>Yes</b>: laptop 0.000, relay 0.161, Jetson 0.155, v4.1 0.143 with 57 % relay / 41 % Jetson"],
        ["Mission: does adaptation pay?", "v4.1 best", "<b>Yes</b>: 0.124, 3 of 3 against every fixed policy; only one perceiving in the total blackout"],
        ["Good link: v4.1 at least as good as the best fixed path?", "yes, as in earlier campaigns", "<b>No</b> in this campaign: laptop YOLOv8m 0.182 against v4.1 0.143 (high variance)"],
        ["Cost on the camera drone", "≈ 2–2.5 W, ≈ 50 °C", "2.1–2.5 W fixed, 2.9–3.4 W v4.1; 54–69 °C"]])}
<h3>18.6 The hierarchical chain (the professor's design)</h3>
<p>The design asked for: the Pi processes a frame onboard or sends it to the Jetson; the Jetson processes it on its own GPU or, when it is busy or its result would be worse, forwards it to the laptop; there is <b>no direct Pi → laptop link</b>. This differs from what B ran: the fixed relay only forwarded (the Jetson never decided), and v4.1 made every decision on the Pi with a direct laptop link available. The chain was not run as one system; its results are <b>composed</b> from B's measured runs, because it only ever uses options B measured directly: Pi → Jetson with local detection (the fixed Jetson runs), Pi → Jetson → laptop (the fixed relay runs, same hop and forwarding), and the Pi's onboard fallback when no link works (v4.1 in the total blackout). Lower bound: a Jetson that always detects locally or always forwards, whichever is worse; upper bound: the better of the two in each scenario or mission phase. <span class="tag p">Pending</span> (composed from measured runs; to be run as one system on the mesh)</p>
<div class="tbl"><table>
<tr><th>Scenario (sAP with forecaster)</th><th>Hierarchical chain (from measured runs)</th><th>v4.1 direct three-tier (measured)</th><th>Best fixed path (measured)</th></tr>
<tr><td>Normal link</td><td class="n"><b>0.144–0.159</b></td><td class="n">0.143</td><td class="n">Pi → laptop 0.181</td></tr>
<tr><td>Out of range</td><td class="n"><b>0.155–0.161</b> (unaffected: it has no direct link to lose)</td><td class="n">0.143</td><td class="n">relay 0.161</td></tr>
<tr><td>Mission (mean of the six phases)</td><td class="n"><b>0.121–0.122</b></td><td class="n">0.126</td><td class="n">Pi → Jetson 0.114</td></tr>
<tr><td>Pi power, temperature</td><td class="n"><b>≈ 2.1–2.3 W, ≈ 55 °C</b></td><td class="n">2.9–3.4 W, 62–69 °C</td><td class="n">–</td></tr>
</table></div>

<div class="tbl"><table>
<tr><th>Mission phase</th><th>Hierarchical (from measured runs)</th><th>v4.1 (measured)</th><th>Why</th></tr>
<tr><td>good</td><td class="n">0.208</td><td class="n"><b>0.239</b></td><td class="n">v4.1 also uses the direct laptop link</td></tr>
<tr><td>ground congested</td><td class="n"><b>0.090</b></td><td class="n">0.068</td><td class="n">the chain does not depend on the ground link</td></tr>
<tr><td>ground blackout</td><td class="n"><b>0.165–0.172</b></td><td class="n">0.163</td><td class="n">about equal: both use the Jetson</td></tr>
<tr><td>both degraded</td><td class="n">0.032</td><td class="n"><b>0.058</b></td><td class="n">v4.1 uses two links in parallel</td></tr>
<tr><td>total blackout</td><td class="n">0.042</td><td class="n">0.042</td><td class="n">both fall back to the Pi onboard</td></tr>
<tr><td>recovered</td><td class="n">0.189</td><td class="n">0.186</td><td class="n">about equal</td></tr>
</table></div>

<ul>
<li><b>In this setup the hierarchical chain is about as good as v4.1:</b> slightly better on a normal link and out of range (+0.012 to +0.018), about equal in the mission, with the Pi 0.7–1 W cooler (no onboard work except in a total blackout).</li>
<li><b>v4.1's advantage is two independent links:</b> when both are degraded it uses them in parallel (0.058 against 0.032), and on a perfect link the direct laptop path is the single best option (0.181). Out of range the chain wins by construction.</li>
<li><b>Limits:</b> the results are assembled phase by phase from separate runs, not from a run of the chain itself. The Jetson's own decision was never exercised: with one camera drone its GPU is rarely busy, and in B the Jetson → laptop link was never impaired. All links shared one Wi-Fi channel in the lab.</li>
<li><b>Next (mesh):</b> the Jetson-side decision program (detect locally or forward, by expected accuracy after delay, never forwarding over a bad ground link) is written and the chain is run on the AegisSwarm mesh, where the Pi → Jetson and Jetson → laptop links are separate radio links, with impairments on the Jetson → laptop link as well, and with several camera drones so that the Jetson does get busy.</li>
</ul>
'''


PART19 = f'''<h2 id="rescore"><span class="num">PART 19</span>Every campaign rescored with the standard metrics and replayed with the VisDrone weights (22 Oct 2026; C1–C6 done, VisDrone replay waiting)</h2>
<p>Corrections to how the earlier hardware results (Parts 12–15, 776 runs in 8 campaigns, 6–13 Oct) are scored and reported, from the data already recorded: no new runs. Each run is scored without and with its forecaster (<code>validation/hardware/report_rescore.py</code>; numbers in <code>experiments/results/hardware/report_c_summary*.json</code>, tables in <code>report_c_tables*.md</code>). {P}</p>
<h3>19.1 The fixes</h3>
{table(["#", "Fix", "How"],
       [["C1", "State the holding rule; report the <b>standard</b> sAP (newest result held) everywhere", "The Phase G tables reported the 'quality' rule (the held result with the highest expected accuracy). The verdicts were checked to be the same under the standard rule (G14); the standard values now stand next to every reported one"],
        ["C2", "Score with VisDrone's <b>ignored regions masked</b>, as the official protocol does", "A detection or ground-truth box more than 50 % inside an ignored region (category 0) is removed (VisDrone toolkit rule). The 7 test clips have 3,994 ignored-region boxes on 1,434 frames of 5 clips (2 clips have none)"],
        ["C3", "Add <b>sAP50</b>, <b>sAP by object size</b> and <b>worst-case AoI</b>", "Sizes: COCO area ranges in the 640-px frame; of 108,645 test objects 91.2 % are small, 8.8 % medium and only 7 large, so 'large' is not reported. AoI of the held result: 95th-percentile and peak AoI, the longest stretch with AoI > 300 ms, and P(AoI ≤ 300 ms)"],
        ["C4", "Results <b>per scenario</b>, and per phase inside the missions", "Normal phases separate from congestion and blackouts"],
        ["C5", "State the <b>assumptions</b>", "see 19.4"],
        ["C6", "<b>Holm correction</b> for multiple comparisons", "Paired differences against each campaign's reference controller with 95 % t-intervals, exact sign-flip permutation p-values (all 2<sup>n</sup> sign patterns, no distribution assumed) and Holm-adjusted p-values within each campaign and metric"],
        ["C7", "<b>Replay every campaign with the VisDrone weights</b> (added 22 Oct)", "Each recorded result keeps its frame, server, setting (model, input size, JPEG quality) and arrival time; its detections are replaced by those of the same setting from the VisDrone-trained model, computed exactly as the live system does (letterbox, JPEG encode and decode, FP16 on the GPU for offloaded settings; <code>validation/hardware/vd_variant_dets.py</code>). The architectures are the same, so the timing holds. The controllers made their choices with the COCO accuracy table, so this is 'the same schedules with VisDrone detectors', not what a VisDrone-aware controller would have chosen; that is what Part 18 measures live"]])}
<h3>19.2 Status and expected results</h3>
{table(["Step", "Status", "Expected result", "Output"],
       [["C1–C6 on the recorded (COCO) detections", "<b>done</b> (all 776 runs)", "results in 19.4", "<code>report_c_summary.json</code>, <code>report_c_tables.md</code> (every campaign: pooled table, per scenario, per mission phase, paired tests)"],
        ["C7: VisDrone detections of every setting", "waiting for the go-ahead (checkpoint, 22 Oct 23:00); the VisDrone YOLOv8n fine-tuning is paused at epoch 24 of 80 and resumes from there", "11 settings × 2,846 test frames", "<code>vd_variant_dets/</code>"],
        ["C7: replay of all 776 runs", "after the step above", "Absolute sAP about 2–4× higher (the fine-tuning raised mAP 2–2.7× and onboard sAP 2–4× in Part 17); the rankings of policies expected to hold, because the schedules are the same and the gain applies to every setting", "<code>report_c_summary_visdrone.json</code>, <code>report_c_tables_visdrone.md</code>"],
        ["Final report", "after both", "Parts 12–15 restated with VisDrone-weight numbers next to the original ones", "this report"]])}
<h3>19.3 Results of C1–C6 (all 776 runs, recorded detections)</h3>
<p>Every campaign's headline comparison, now with the standard sAP and the campaign's forecaster (the metric of record), with exact permutation p-values corrected by Holm within each campaign. Differences are reference minus policy, mean ± 95 % CI over scenario × repetition pairs:</p>
{{C_TABLE}}
<ul>
<li><b>The holding rule changes no verdict.</b> The standard and the 'quality' sAP differ by at most a few percent in every campaign, and every comparison that was significant under one rule is significant under the other (C1).</li>
<li><b>Masking the ignored regions changes no verdict.</b> It raises sAP by about 1–2 % uniformly (C2).</li>
<li><b>Survive the Holm correction:</b> energy pricing (v4) over v3 + forecasting (G9: +0.0089, 17 of 20; G11: +0.0083, 19 of 20); v5 over the four literature baselines (+0.011 to +0.027, 20 of 20 each, p &lt; 0.001); the staleness ablations (no staleness −0.0061, p = 0.008; no-forecast curve −0.0058, p = 0.024); v4.1 and v5 over onboard-only (+0.043, 20 of 20).</li>
<li><b>Do not survive it (corrections to earlier wording):</b> v5 over fixed JPEG offloading to the laptop (+0.0065, 16 of 20, Holm p = 0.13; the earlier report called it a win); in the Part 12 campaign, with the forecaster applied, v2 (A_full) is significantly better only than onboard and the fixed Jetson path, and the fixed laptop YOLOv8m has the highest mean (0.046 against 0.043, not significant). The 24-minute missions have 2 runs per policy, so no comparison there can be significant (smallest possible p = 0.5): the long-run ranking of v4.1 remains a trend.</li>
<li><b>Ties confirmed:</b> v4.1, v5 and v5.1 (G13, 20 pairs each, p = 0.69); the generic decay curves and LEAF-style fixed weight against v5 (G12).</li>
<li><b>Object size (C3):</b> medium objects score about 4–5× higher than small ones for every policy (e.g. Part 12 laptop YOLOv8m: small 0.028, medium 0.139); 91 % of the objects are small, so small objects set the overall sAP.</li>
<li><b>Worst-case AoI (C3):</b> the adaptive controllers keep P(AoI ≤ 300 ms) at 86–100 % with a 95th-percentile AoI of 0.2–0.4 s and no stretch with AoI > 300 ms longer than 0.2 s on the Part 12 campaign, while fixed remote paths have 95th-percentile AoI of 11–13 s and stale stretches of 46 s (the blackout phases), a difference the mean sAP does not show.</li>
</ul>
<p><b>First check.</b> Scoring a G12 mission run (freshness-threshold baseline) gives sAP 0.0159 unmasked (identical to the value cached for G12) and 0.0161 masked; small objects 0.010, medium 0.057; P(AoI > 300 ms) was 34 %, with a longest stale stretch of 22 s (the blackout phase).</p>
<h3>19.4 Assumptions, stated explicitly (C5)</h3>
<ul>
<li>VisDrone-VID frames are replayed at 30 fps; the dataset does not publish its frame rate, so every age in milliseconds scales with this choice.</li>
<li>The camera stream is the clips resized to 640 px wide; full resolution would help the small objects but costs transfer and compute.</li>
<li>The controller v1 and v2 results (Parts 9–10) used looped COCO photographs and an accuracy-weighted deadline-met throughput, a proxy without sAP; they cannot be rescored.</li>
<li>Every campaign up to 13 Oct ran the COCO-trained detectors; their absolute sAP is therefore low and not comparable with VisDrone literature, while comparisons between policies within a campaign stand. C7 replays them with the VisDrone weights; from Part 17 on, all live detectors are VisDrone-trained.</li>
<li>Numbers from different campaigns are not comparable (Wi-Fi conditions and board state differ by day): compare within one campaign only.</li>
</ul>
'''

STATE = '''<div class="box state"><b class="h">State on 22 Oct 2026, 23:00 (checkpoint): VisDrone detectors, onboard study, relay campaign and standard-metric rescoring done; VisDrone replay of the earlier campaigns waiting</b>
<ul>
<li><b>Onboard (Part 17, done):</b> YOLOv8s, m and l fine-tuned on VisDrone (mAP50-95 on DET val 0.107 → 0.267, 0.146 → 0.297, 0.164 → 0.313). On two Pi 5s (30 runs): mAP 0.24–0.27 but sAP only 0.006 / 0.005 / 0.001 (0.017 / 0.008 / 0.0015 with the forecaster), because a frame takes 0.7 / 1.6 / 3.3 s; the Pi throttles within about a minute even from a cool start; throttling leaves mAP unchanged and roughly halves sAP.</li>
<li><b>Relay campaign (Part 18, done, 36 runs):</b> offloading gives 0.13–0.18 sAP with the forecaster, about 10× onboard, with the Pi at 2–3.4 W and below 70 °C. Out of the ground station's range the direct path delivers nothing while the relay Pi → Jetson → laptop delivers 0.161 and v4.1 switches to it by itself (0.143); in the mission v4.1 is best (0.124) and the only policy still perceiving in a total blackout; on a good link the direct laptop path is best (0.182).</li>
<li><b>Rescoring (Part 19, C1–C6 done, 776 runs):</b> the standard holding rule and the masking of ignored regions change no verdict; energy pricing, the win over the literature baselines and the staleness ablations survive the Holm correction; v5 over fixed JPEG offloading and v2's lead in Part 12 do not.</li>
<li><b>Hierarchical chain (the professor's design, 18.6):</b> composed from the measured runs at 0.144–0.159 (normal), 0.155–0.161 (out of range) and about 0.12 (mission), about as good as v4.1 and cooler on the Pi; to be built and measured on the mesh.</li>
<li><b>Mesh test (18.8, measured, 12 runs):</b> on the AegisSwarm mesh v4.1 beats the hierarchical chain in all 6 pairs: 0.193 against 0.146 sAP with the forecaster (+32 %, p = 0.031), at the same camera-drone power and no throttling; the chain is limited by the camera → Jetson link, and its Jetson never chose to forward.</li>
<li><b>Waiting for the go-ahead:</b> the VisDrone replay of the 776 earlier runs (YOLOv8n fine-tuning, about 1.5 h, then about 2.5 h on the laptop), then the AegisSwarm mesh work.</li>
</ul></div>
'''

LEFT = '''<tr><td><b>Task C7</b> (Part 19): VisDrone replay of the 776 earlier runs (YOLOv8n fine-tuning resumes from epoch 24 of 80, VisDrone detections of every setting, rescoring), then Parts 12–15 restated</td><td>Laptop GPU and CPU only; waiting for the go-ahead</td><td>about 4 h</td></tr>
<tr><td>Hierarchical chain on the mesh (18.6): Jetson-side decision program (detect locally or forward to the laptop), then the chain against v4.1 with impairments on both links and several camera drones</td><td>Code on the laptop (about 2 h), then the mesh</td><td>about 2 h + runs</td></tr>
<tr><td>Relay campaign follow-up: 5 repetitions per scenario to settle the good-link ranking of v4.1; the ground-congested drop of the Jetson and relay paths</td><td>pi2, Jetson, laptop (or the mesh)</td><td>about 3 h</td></tr>
'''


def _bsum():
    import json
    return json.load(open(HW / "vid_campaign_b_summary.json"))


PN = {"jet_s": "Pi → Jetson (YOLOv8s)", "lap_m": "Pi → laptop (YOLOv8m)", "relay_m": "relay Pi → Jetson → laptop (YOLOv8m)",
      "v41": "v4.1 (all paths)"}


def b_table():
    d = _bsum()["cells"]
    rows = []
    for sc in ("static_good", "mission", "out_of_range", "ALL"):
        for p in ("jet_s", "lap_m", "relay_m", "v41"):
            c = d.get(f"{sc}|{p}")
            if not c:
                continue
            sh = ", ".join(f"{k} {100 * v:.0f} %" for k, v in sorted(c["server_share"].items(), key=lambda x: -x[1]) if v >= 0.005)
            rows.append([{"static_good": "normal", "mission": "mission", "out_of_range": "out of range", "ALL": "all"}[sc], PN[p],
                         f"{c['sAP'][0]:.3f}", f"<b>{c['sAP_fc'][0]:.3f} ± {c['sAP_fc'][1]:.3f}</b>", f"{c['sAP50_fc'][0]:.3f}",
                         f"{c['mAP'][0]:.3f}", f"{100 * c['fresh_share'][0]:.0f} %", f"{c['age_p95_ms'][0] / 1000:.2f} s",
                         f"{c['pi_w'][0]:.2f} W, {c['temp_c'][0]:.0f} °C", sh])
    return table(["Scenario", "Policy", "sAP", "sAP + forecaster", "sAP50 + fc", "mAP", "P(AoI ≤ 300 ms)", "95th-percentile AoI", "Pi", "servers"], rows)


def b_phases():
    d = _bsum()["mission_phases_fc"]
    ph = list(next(iter(d.values())))
    return table(["Policy"] + [x.replace("_", " ") for x in ph], [[PN[p]] + [f"{d[p][k]:.3f}" for k in ph] for p in ("jet_s", "lap_m", "relay_m", "v41")])


def b_paired():
    d = _bsum()
    rows = []
    for name, scope, res in ([("v4.1", "all", d["paired_v41"]), ("relay", "all", d["relay_vs_laptop"])]
                             + [("v4.1", sc, r) for sc, r in d["paired_v41_by_scenario"].items()]
                             + [("relay", sc, r) for sc, r in d["relay_vs_laptop_by_scenario"].items()]):
        for p, r in res.items():
            rows.append([f"{name} vs {PN[p]}", scope.replace("static_good", "normal").replace("_", " "), r["pairs"],
                         f"{r['mean_diff']:+.4f} ± {r['ci95']:.4f}", f"{r['wins']}/{r['pairs']}", f"{r['p_perm']:.3f}", f"{r['p_holm']:.3f}"])
    return table(["Comparison", "Scope", "pairs", "Δ sAP + fc", "wins", "p", "p Holm"], rows)


def c_table():
    import json
    d = json.load(open(HW / "report_c_summary.json"))
    rows = []
    for camp, c in d.items():
        for ref, ms in c["paired"].items():
            for pol, v in sorted(ms["sAP_fc"].items(), key=lambda x: -x[1]["mean_diff"]):
                rows.append([c["section"], f"{ref} vs {pol}", f"{v['mean_diff']:+.4f} ± {v['ci95']:.4f}",
                             f"{v['wins']}/{v['pairs']}", f"{v['p_perm']:.3f}", f"<b>{v['p_holm']:.3f}</b>",
                             f"{ms['sAP_quality_fc'][pol]['p_holm']:.3f}", f"{ms['sAP_masked_fc'][pol]['p_holm']:.3f}"])
    return table(["Campaign", "Comparison", "Δ sAP (standard + fc)", "wins", "p", "p Holm", "p Holm, quality rule",
                  "p Holm, masked"], rows)


def figs():
    f = HW / "figs_hier.html"
    return (f.read_text() if f.exists() else "") + mesh_section()


def mesh_section():
    """18.8: v4.1 against the hierarchical chain, measured on the AegisSwarm mesh (23-24 Oct 2026)."""
    f = HW / "vid_campaign_mesh_summary.json"
    if not f.exists():
        return ""
    import json
    d = json.load(open(f))
    c, pr, ph = d["cells"], d["paired_v41_minus_hier"], d["mission_phases_fc"]
    nm = {"v41": "v4.1 (direct three-tier)", "hier": "hierarchical chain"}
    scn = {"static_good": "normal", "mesh_mission": "mesh mission", "ALL": "both"}
    rows = []
    for sc in ("static_good", "mesh_mission", "ALL"):
        for m in ("v41", "hier"):
            x = c[f"{sc}|{m}"]
            pa = ", ".join(f"{k} {100 * v:.0f} %" for k, v in sorted(x["processed_at"].items(), key=lambda t: -t[1]) if v >= .005)
            rows.append([scn[sc], nm[m], f"{x['sAP'][0]:.3f}", f"<b>{x['sAP_fc'][0]:.3f} ± {x['sAP_fc'][1]:.3f}</b>",
                         f"{x['mAP'][0]:.3f}", f"{x['p_aoi300'][0]:.3f}", f"{x['aoi_p95_ms'][0]:.0f} ms",
                         f"{x['lat_median_ms'][0]:.0f} ms", f"{x['deadline_met_fps'][0]:.1f}",
                         f"{x['pi_w'][0]:.2f} W, {x['pi_temp_c'][0]:.0f} °C, {100 * x['pi_throttled'][0]:.0f} %", pa])
    t1 = table(["Scenario", "Method", "sAP", "sAP + forecaster", "mAP", "P(AoI ≤ 300 ms)", "95th-pct AoI", "median latency",
                "deadline-met throughput (/s)", "Pi: power, temp., throttled", "processed at"], rows)
    prow = [[scn[sc], {"sAP_fc": "sAP + forecaster", "sAP": "sAP", "p_aoi300": "P(AoI ≤ 300 ms)", "pi_w": "Pi power (W)"}[k],
             r["pairs"], f"{r['mean_diff']:+.4f} ± {r['ci95']:.4f}", f"{r['v41_ahead']}/{r['pairs']}", f"{r['p_perm']:.3f}"]
            for sc in ("static_good", "mesh_mission", "ALL") for k, r in pr[sc].items()]
    t2 = table(["Scope", "Metric", "pairs", "v4.1 − chain", "v4.1 ahead", "p (exact)"], prow)
    names = list(ph["v41"])
    t3 = table(["Method"] + [n.replace("_", " ") for n in names], [[nm[m]] + [f"{ph[m][n]:.3f}" for n in names] for m in ("v41", "hier")])
    h = c["ALL|hier"]
    return f'''<h3>18.8 Measured on the mesh: v4.1 against the hierarchical chain (23–24 Oct 2026)</h3>
<p>Both designs run on the real AegisSwarm mesh: an ad-hoc (IBSS) Wi-Fi network "AegisSwarm" on 2.4 GHz channel 6 with batman-adv routing, set up on the boards by hand. <b>Camera drone</b> pi-relayyy (10.1.0.12), <b>edge drone</b> the Jetson (10.1.0.13), <b>ground radio</b> pi-sender (10.1.0.11), cabled to the <b>ground station</b> laptop, which joins through SSH port forwards via pi-sender (no change to the mesh; the traffic still crosses the mesh to pi-sender and then the cable). Measured links (iperf3, 10 s each way; ping ×50): pi-sender ↔ pi-relayyy 43–46 Mbit/s both ways, 7 ms; Pi → Jetson 14–17 Mbit/s, Jetson → Pi 4.0–4.4 Mbit/s (the Jetson's radio transmits at 15 dBm against 31 dBm on the Pis), 5–7 ms, 0–2 % loss. All nodes are one radio hop apart. {V} (12 runs)</p>
<ul>
<li><b>v4.1 (direct three-tier):</b> the camera decides per frame between onboard, the Jetson and the laptop directly (over the mesh to pi-sender), with its usual objective.</li>
<li><b>Hierarchical chain:</b> the camera decides per frame between onboard and the Jetson only (same v4.1 objective: accuracy and staleness, energy price, heat guard, freshness target); the Jetson then decides per frame between detecting itself (YOLOv8s) and forwarding over its own link to the ground station (YOLOv8m on the laptop), by expected accuracy after delay, how busy its GPU is, its power and temperature, and the state of its ground link (<code>validation/hardware/edge_node.py</code>).</li>
<li><b>Scenarios:</b> normal (all links good) and a <b>mesh mission</b> of six 40-s phases: good → ground congested (both ground links 3 Mbit/s) → camera out of range (direct camera → ground link cut) → edge uplink cut (Jetson → ground link cut) → camera → edge link slow (2 Mbit/s) → recovered. 3 repetitions each, order shuffled; 4-minute runs; test-only netem on the experiment ports of <code>bat0</code>, removed after every run. VisDrone weights everywhere; scoring as Part 18 (<code>validation/hardware/mesh_summary.py</code>, <code>experiments/results/hardware/vid_campaign_mesh*</code>).</li>
</ul>
{t1}
<p>Paired by scenario and repetition (exact sign-flip permutation p-values):</p>
{t2}
<p>Mesh mission, per phase (sAP with forecaster, mean of 3):</p>
{t3}
<ul>
<li><b>v4.1 is more accurate than the hierarchical chain in every one of the 6 pairs:</b> +0.047 sAP with the forecaster (0.193 against 0.146, +32 %; p = 0.031 over the 6 pairs; 3 of 3 in each scenario, where 3 pairs cannot give p below 0.25). The reason is the link: v4.1 sends most frames straight to the laptop over the fast camera → ground link (71 % of frames, median latency 52 ms) and uses the Jetson in parallel, while the chain must pass every frame through the slower camera → Jetson link (median latency 106 ms, about half the deadline-met throughput).</li>
<li><b>Both keep the camera drone cool and fresh:</b> the same Pi power (2.8 W) and temperature (64 °C), 0 % throttled, P(AoI ≤ 300 ms) 0.99–1.00. The chain's Jetson ran at {h['jetson_w']:.1f} W and {h['jetson_temp_c']:.0f} °C.</li>
<li><b>Where each design is weak:</b> the chain loses most when the camera → Jetson link slows (0.069 against 0.185 for v4.1), because it has no other path; v4.1 is unaffected there. When the direct ground link is cut ("camera out of range"), v4.1 moves to the Jetson and stays ahead (0.175 against 0.164): with a direct-link fallback to the Jetson it already covers the out-of-range case the chain is designed for.</li>
<li><b>The Jetson's decision:</b> it detected every frame itself and forwarded none (0 of about 18,000). Its forwarding estimate (median about 880 ms) is pessimistic: it learns the ground link from small probes, so their fixed round-trip time inflates the per-KB cost; at the measured 4 Mbit/s an 87 KB frame takes about 210 ms. The decision would still be the same: at that delay YOLOv8m's extra accuracy (0.276 against 0.256 at JPEG q90) does not make up for the staleness, so local detection keeps more accuracy. With a faster edge radio, or several camera drones keeping its GPU busy, forwarding would start to pay.</li>
<li><b>Caveats:</b> 3 repetitions per scenario; one indoor room, all nodes one hop apart, a crowded 2.4 GHz band, built-in radios; v4.1's Jetson power was not logged. Three runs needed a second attempt or a manual copy of their result files after an SSH step over the mesh failed (the measurements themselves always completed); the run script now verifies each start and retries every copy.</li>
</ul>
'''


CHART_CSS = ("  --c-hier:#00806A; --c-onb:#A85F00;\n", "    --c-hier:#2E9C8A; --c-onb:#C2832E;\n")


def main():
    rows = b_rows(sys.argv[1])
    h, m = HTML.read_text(), MD.read_text()
    new = part18(rows) + figs() + "\n" + PART19.replace("{C_TABLE}", c_table()) + "\n"
    if "--c-hier" not in h:      # chart colours (validated: lightness, chroma, colour-blind separation, contrast)
        h = h.replace("--bad:#A8352C; --bad-soft:#F6E2DF;\n", "--bad:#A8352C; --bad-soft:#F6E2DF;\n" + CHART_CSS[0], 1)
        h = h.replace("--bad:#E5847A; --bad-soft:#341C19; color-scheme:dark;\n", "--bad:#E5847A; --bad-soft:#341C19; color-scheme:dark;\n" + CHART_CSS[1])
    i, j = h.index('<h2 id="relay">'), h.index('<h2 id="argument">')
    h = h[:i] + new + h[j:]
    i, j = m.index("## PART 18"), m.index("## PART 20")
    md_figs = ("\n![sAP against throttling](uav-split-perception/docs/figs/hier_sap_vs_throttling.svg)\n\n"
               "![sAP over time](uav-split-perception/docs/figs/hier_sap_vs_time.svg)\n\n"
               "![Clock speed against temperature and throttling](uav-split-perception/docs/figs/hier_clock_vs_throttling.svg)\n\n")
    nm = html_to_md(new)
    k = nm.index("## PART 19")
    m = m[:i] + nm[:k] + md_figs + nm[k:] + m[j:]
    # Part 1 state box: replace the 22 Oct box
    h = re.sub(r'<div class="box state"><b class="h">State on 22 Oct 2026.*?</div>\n', STATE, h, 1, flags=re.S)
    i = m.index("**State on 22 Oct 2026")
    j = m.index("\n\n**", i + 5)
    m = m[:i] + html_to_md(STATE).rstrip("\n") + m[j:]
    # What is left: replace the two task rows
    h = re.sub(r"<tr><td><b>Task (B|C7)</b>.*?</tr>\n(<tr><td>Hierarchical chain on the mesh.*?</tr>\n)?<tr><td>(<b>Task C</b>|Relay campaign follow-up).*?</tr>\n", LEFT, h, 1, flags=re.S)
    m = re.sub(r"^\| \*\*Task (B|C7)\*\*.*\n(\| Hierarchical chain on the mesh.*\n)?\| (\*\*Task C\*\*|Relay campaign follow-up).*\n",
               "\n".join(html_to_md('<div class="tbl"><table><tr><th>x</th></tr>' + LEFT + "</table></div>")
                         .split("\n")[2:5]) + "\n", m, 1, flags=re.M)
    h = re.sub(r'(<div class="meta">Full project report · state on )[^<]*', r"\g<1>22 Oct 2026, 23:00", h, 1)
    m = re.sub(r"^Full project report · state on .*$", "Full project report · state on 22 Oct 2026, 23:00", m, 1,
               flags=re.M)
    HTML.write_text(h)
    MD.write_text(m)
    print("report updated:", len(rows), "B runs")


if __name__ == "__main__":
    main()
