#!/usr/bin/env python3
"""Novelty Brief update, 12 Nov 2026: what the hardening of both papers (Results Brief 19.15-19.23) adds to the novelty,
against the closest work found in the 11 Nov survey (docs/novelty_roadmap_nov11.md, sources there). Idempotent (marker
comments); previous version archived to experiments/results/hardware/_superseded/novelty_before_nov12/."""
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
F = ROOT / "AEGIS-UAV Novelty Brief.html"
ARCH = ROOT / "uav-split-perception" / "experiments" / "results" / "hardware" / "_superseded" / "novelty_before_nov12"

SEC = """<!--nb12--><section>
  <h2>Update 12 Nov 2026: what hardening the two papers adds</h2>
  <p>Since 10 November the work has been written as two papers and hardened on the laptop. Every test had its prediction committed before it ran (Results Brief 19.15–19.23). Neither paper has a new <i>algorithm</i>. Their novelty is results that are proved, measured and stress-tested, and design rules, which is the normal currency of a measurement-and-systems paper.</p>
  <div class="tbl"><table>
    <tr><th>Claim</th><th>Closest prior work</th><th>What is ours</th><th>Novelty</th></tr>
    <tr><td><b>Paper 1: a break-even goodput for any split</b>, in which the code's own payload does not enter, so no coder (even at the rate–distortion limit) raises it; a split that switches codes is bounded by its best code</td><td>Neurosurgeon (per-layer latency choice); Matsubara &amp; Levorato 2020 (a crossover near 8 Mbit/s for one setup); Bayes-Split-Edge and ENACHI (per-setup optimisation); task-oriented coding limits (Shao, Mao &amp; Zhang, JSAC 2022; indirect rate–distortion, arXiv 2602.12866)</td><td>A proved bound for every code of a given accuracy and onboard time against a whole image-codec family, not a per-setup optimum. It is the system-level complement to the rate limits: closing the rate gap leaves the bound where it is</td><td><span class="chip yes">high</span> as a stated, tested rule; the proof is short</td></tr>
    <tr><td><b>Paper 1: the bound stress-tested against ever-stronger splits and image codecs</b>: jointly trained codes, an 18-quality JPEG grid, a JPEG-tuned detector, entropy-coded codes 52–73 % smaller (same bound), video, inter-frame coded codes, learned and ROI image codecs, a second detector, an energy version</td><td>SC2 benchmark; Entropic Student; FrankenSplit; BottleFit; Yuan et al. 2022/2024 (all rate–accuracy); MPEG FCM (75–85 % savings over remote inference, reported); AccMPEG, DDS (ROI coding); IFMDC (inter-frame feature coding); learned image codecs (Ballé 2018, Minnen 2018)</td><td>Prior work wins on rate–accuracy; this shows the end-to-end win stays bounded however good the rate is. With low-delay video the window shrinks to about 1.5 Mbit/s even on a Jetson, and a split never saves energy on a Pi. 0 exceptions in every model check</td><td><span class="chip part">medium</span> to <span class="chip yes">high</span> for breadth</td></tr>
    <tr><td><b>Paper 1: under fading the constant bound fails on fast devices; a spread-discounted version holds</b></td><td>Dynamic split computing (arXiv 2205.11269)</td><td>Measured in a simulator on fading traces (14–24 % of wins above the constant bound; 0 above the fading version). Empirical, not proved</td><td><span class="chip part">medium</span></td></tr>
    <tr><td><b>Paper 2: heat measured as a streaming-accuracy cost</b> (throttling alone costs 37–59 % of onboard sAP) inside a real three-tier offloading system</td><td>Pi 4 thermal throttling (throughput, arXiv 2010.06291); Heat &amp; Memory constraints (FPS halves above 80 °C, 2024); Tan &amp; Cao, TMC 2024; Phoenix (TECS 2026)</td><td>Accuracy in a distributed scheduler, not frames per second on one device</td><td><span class="chip yes">high</span></td></tr>
    <tr><td><b>Paper 2: a sample-path power bound checked on every logged update</b> (66,655 updates, 376 runs, 0 unexplained), a budget rule for the board's mean temperature (within 1.6 °C), and a peak bound under a hard guard with its converse</td><td>Drift-plus-penalty (Neely 2010, the standard); thermal virtual queues (data-centre and mmWave work, arXiv 1709.00715, 2412.20032, 2601.19587); OCO with long-term constraints</td><td>The theory is a standard application. What is uncommon is checking it on real logs, with the hold and cap terms named, and a peak bound with a converse that says when no controller can help</td><td><span class="chip part">medium</span></td></tr>
    <tr><td><b>Paper 2: the controller's own blackout hold drives the heat on long missions</b>; capping it, a room-following budget and a hard guard remove it</td><td>AccuMO; LEAF-style weights; thermal-aware DVFS + offloading (threshold-based)</td><td>A diagnosis by sweep (285 replay runs) with predictions committed first. The fix is replay-only until the board session runs</td><td><span class="chip part">medium</span>, replay only</td></tr>
    <tr><td><b>Paper 2: a constrained deep-RL baseline</b> (PPO-Lagrangian) does not beat the greedy priced controller</td><td>Safe-DQN and CMDP offloading for UAVs (IoT-J 2024); constrained RL with zero duality gap</td><td>The baseline in the same replay, on the same seeds; it keeps the budget and trails by 0.004–0.012 sAP</td><td><span class="chip no">low</span>: a baseline, not a claim</td></tr>
    <tr><td><b>Method: predictions committed before every run; an open benchmark with a bit-exact check</b></td><td>—</td><td>Rare in systems papers; failed predictions are reported as failed</td><td><span class="chip part">medium</span>, as a selling point</td></tr>
  </table></div>
  <p><b>What reviewers will still attack.</b> For paper 1, the rule is checked in the authors' own model and simulator. A predict-then-measure test on the real link would turn it into a hardware result. The MPEG FCM baseline was not run: its reference software is hosted for MPEG members. For paper 2, the most dangerous question is whether, in flight, propeller wash cools the board so that the heat cost disappears. That needs an airflow test. The capped hold and the guard need board runs, and there is one camera drone on the mesh.</p>
  <p><b>Venue view, 12 Nov.</b> Paper 1 is realistic for IEEE TMC and a strong fit for IEEE IoT-J; SenSys has a Benchmarks/Experiences category. Paper 2 is more realistic for TMC. INFOCOM is possible only if the board session confirms the capped hold. MobiSys 2027 (abstract 27 Nov, paper 4 Dec 2026, 12 pages) needs the airflow test, the capped-hold board runs and a rewrite within about three weeks, so it is feasible only with a board day within about ten days. The MobiCom winter cycle (typically Feb–Mar 2027) is the realistic top-venue target.</p>
</section><!--/nb12-->
"""

SRC = """<!--nbsrc12-->    <li>Added 12 Nov (survey of 11 Nov): SC2 benchmark <a href="https://arxiv.org/abs/2203.08875">arxiv 2203.08875</a>; FrankenSplit <a href="https://arxiv.org/abs/2302.10681">2302.10681</a>; BottleFit <a href="https://arxiv.org/abs/2201.02693">2201.02693</a>; Matsubara &amp; Levorato <a href="https://arxiv.org/abs/2007.15818">2007.15818</a>; MPEG FCM <a href="https://arxiv.org/abs/2512.10209">2512.10209</a>, CompressAI-Vision <a href="https://arxiv.org/abs/2509.20777">2509.20777</a>; indirect rate–distortion <a href="https://arxiv.org/abs/2602.12866">2602.12866</a>; dynamic split computing <a href="https://arxiv.org/abs/2205.11269">2205.11269</a>; AccMPEG <a href="https://arxiv.org/abs/2204.12534">2204.12534</a>; Ballé et al. ICLR 2018 and Minnen et al. NeurIPS 2018 (learned image codecs, checked on arXiv); Pi 4 thermal throttling <a href="https://arxiv.org/abs/2010.06291">2010.06291</a>; Heat &amp; Memory constraints doi 10.1145/3662004.3663555; thermal virtual queues <a href="https://arxiv.org/abs/1709.00715">1709.00715</a>, <a href="https://arxiv.org/abs/2412.20032">2412.20032</a>, <a href="https://arxiv.org/abs/2601.19587">2601.19587</a>; constrained RL <a href="https://arxiv.org/abs/1910.13393">1910.13393</a>; MAVBench <a href="https://arxiv.org/abs/1905.06388">1905.06388</a>. Full list: <code>docs/novelty_roadmap_nov11.md</code>.</li>
<!--/nbsrc12-->"""

REPL = [
    ('<div class="eyebrow">AEGIS-UAV · contribution and novelty, 26 Oct 2026</div>',
     '<div class="eyebrow">AEGIS-UAV · contribution and novelty, 26 Oct 2026, updated 12 Nov 2026</div>'),
    ("Updated 30 Oct 2026: a published scheduler re-implemented (AccuMO-style, Results Brief 19.10–19.11).</p>",
     "Updated 30 Oct 2026: a published scheduler re-implemented (AccuMO-style, Results Brief 19.10–19.11). Updated 12 Nov "
     "2026: both papers hardened (Results Brief 19.15–19.23); see the section after the verdict.</p>"),
    ("A learned feature-compression baseline is now measured (30 Oct; Results Brief 19.12).</p>",
     "A learned feature-compression baseline is now measured (30 Oct; Results Brief 19.12). Since 12 Nov, the split "
     "result is a tested break-even rule, and the priced controller has guarantees checked on its logs (below). For "
     "a top venue paper 2 now most needs an airflow test (does the heat cost survive propeller wash?) and the capped "
     "hold on the board.</p>"),
    ("<li>A published scheduler (AccuMO-style) is re-implemented, but compared only in the trace replay so far; the board campaign is scripted, not run.</li>",
     "<li>A published scheduler (AccuMO-style) is re-implemented, but compared only in the trace replay so far; the board campaign is scripted, not run.</li>\n"
     "      <li>In flight, propeller wash may cool the board: does the heat cost survive? Not tested.</li>\n"
     "      <li>The break-even rule is checked in the authors' own model and simulator, not yet on the real link; the capped hold and the hard guard are replay results.</li>"),
    ("<li>5 repetitions in the headline mesh comparisons.</li>",
     "<li>5 repetitions in the headline mesh comparisons.</li>\n"
     "      <li>An airflow test over the Pi, and the capped hold and the guard over 24-minute missions on the board (prepared: Results Brief 19.23).</li>\n"
     "      <li>A predict-then-measure test of the break-even rule on the real link (shape the Pi's link on the boards, predict the crossover first).</li>"),
]


def main():
    s = F.read_text()
    if not (ARCH / F.name).exists():
        ARCH.mkdir(parents=True, exist_ok=True)
        shutil.copy2(F, ARCH / F.name)
    s = re.sub(r"<!--nb12-->.*?<!--/nb12-->\n", "", s, flags=re.S)
    s = re.sub(r"<!--nbsrc12-->.*?<!--/nbsrc12-->\n", "", s, flags=re.S)
    for old, new in REPL:
        if new in s:
            continue
        assert s.count(old) == 1, old[:70]
        s = s.replace(old, new)
    k = s.index("</div>", s.index('<div class="verdict">')) + len("</div>\n")
    s = s[:k] + SEC + s[k:]
    k = s.index("  </ul>", s.index("<h2>Sources checked</h2>"))
    s = s[:k] + SRC + "\n" + s[k:]
    F.write_text(s)
    print("Novelty Brief updated")


if __name__ == "__main__":
    main()
