#!/usr/bin/env python3
"""Final Report update, 16 Nov 2026: the mesh board sessions of 14-16 Nov (Results Brief 19.24-19.31). Run after
scripts/report_final_nov12.py. Idempotent (a marker comment); the previous version is archived to
experiments/results/hardware/_superseded/report_before_final_nov16/.
Every number is computed by scripts/report_mesh_nov16.py from the result files (the same source as the Results Brief,
paper 1's board_metrics.tex and paper 2's metrics.tex); run counts are counted from the campaign folders."""
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import report_mesh_nov16 as rm  # noqa: E402

ROOT = HERE.parents[1]
F = ROOT / "AEGIS-UAV Final Report.html"
ARCH = rm.R / "_superseded" / "report_before_final_nov16"
MARK = "<!-- final-report-update-nov16 -->"


def pm(p):
    t = rm.pm(p).replace("<", "&lt;")
    return "−" + t[1:] if t.startswith("-") else t


def sg(x, fmt="{:+.4f}"):
    return fmt.format(x).replace("-", "−")


def runs(camp):
    """distinct (scenario, strategy, repetition) of a campaign folder; two-camera runs count once"""
    d = rm.R / f"vid_campaign_{camp}"
    return len({re.sub(r"_c\d+$", "", f.stem) for f in d.glob("a2_*__r*.json")})


CAMPS = [("heat_nov", "Capped hold and guard at 78 °C, 24-min mission with blackout"),
         ("heat_nov2", "Guard at 76.5 °C"), ("heat_final", "Final controller, 24-min mission"),
         ("mesh4", "AccuMO-style planner and LEAF-style weight, first pass"),
         ("final_nov", "Final controller against v4.1, AccuMO, LEAF (5 paired repetitions)"),
         ("budget_nov", "2.4 W against 2.8 W budget"), ("fix_nov", "The late-path skip"),
         ("plus_nov", "v4.1+ re-test"), ("plus_nov2", "v4.1+ re-test, second part"),
         ("dvfs_heat", "CPU clock as a priced knob, 24-min mission"), ("dvfs_short", "CPU clock, short missions"),
         ("two_nov", "Two camera drones, one or two Jetsons"), ("two_cap", "Per-camera cap on paths in flight"),
         ("topology_nov", "Direct against multihop, 5 repetitions"), ("fps_nov", "Frame rate and encode-ahead"),
         ("relaynoise_nov", "Lossy relay (2 %, 5 %)"), ("energy_nov", "Energy price and budget")]
NRUNS = {c: runs(c) for c, _ in CAMPS}
TOTAL = sum(NRUNS.values())

t4, g, fh = rm.t4, rm.g, rm.fh
pk = lambda L: rm.rng([x["peak"] for x in L])            # noqa: E731
hot = lambda L: rm.rng([x["h80"] for x in L])            # noqa: E731
fin, finw, pF, pB, pX = rm.fin, rm.finw, rm.pF, rm.pB, rm.pX
dW = [finw[(sc, "v41")][0] - finw[(sc, s)][0] for sc in ("mesh_mission", "multihop") for s in ("accumo", "leaf")]
pim, rule, meas = rm.pim, rm.rule, rm.meas
HJ = "joint_k4_c4_w128_d2"
ys = [r["b_be_mbps_measured"] for r in rm.y11["rows"] if r["b_be_mbps_measured"]]
pull = rm.pull
pv = lambda mo, n: rm.rng([pull[(mo, n, r)]["on"] for r in (1, 2) if (mo, n, r) in pull])   # noqa: E731
top = rm.top
tsm, tst = top["hier-v41|multihop"]["sAP_fc"], top["hier-v41|static_good"]["sAP_fc"]
ca = rm.ca
low = ca["bins"][0]["observed"] * 100
save = [round(100 * (1 - rm.prof["1800"][m]["j_per_inference"] / rm.prof["2400"][m]["j_per_inference"])) for m in ("s320", "n480y11")]
tdel = [a - b for k in ("tun", "tunr") for a, b in zip(getattr(rm, k)["laptop"], getattr(rm, k)["pi-sender"])]

S416 = f"""
<h3>4.16 On the mesh boards: heat, the final controller, two cameras and paper 1's rule (14–16 Nov)</h3>
<p>Five boards on the batman-adv mesh, {TOTAL} controller runs in {len(CAMPS)} campaigns plus the break-even sweep, the encoder bench, the pull bench and a clock profile; predictions committed before every first run (<code>docs/mesh_predictions_nov14.md</code>), every verdict in one table (<code>docs/mesh_results_nov15.md</code>). Details: Results Brief 19.24–19.31.</p>
<div class="tbl"><table>
  <tr><th>Question</th><th>Measured on the boards</th><th>Verdict</th></tr>
  <tr><td>Does the blackout hold heat the board, and does the cap fix it? (24-min mission, 4-min total blackout)</td><td>v4.1: peak {pk(t4['v41'])} °C, ≥ 80 °C for {hot(t4['v41'])} % of the time, throttled. Capped hold (78 °C): peak {pk(t4['v41cap'])} °C, {hot(t4['v41cap'])} %, never throttled, at the same accuracy. Final controller: peak {pk(fh)} °C, {hot(fh)} %</td><td>Replay result confirmed</td></tr>
  <tr><td>Theorem 3 (the guard's peak bound)</td><td>After the guard acts the die keeps heating: overshoot {min(rm.over):.1f}–{max(rm.over):.1f} °C over {len(rm.over)} guarded runs. With the guard at 76.5 °C the peak was {pk(g)} °C (one sample at 80.4), no run throttled</td><td>Holds as peak ≤ guard + δ<sub>fast</sub>, δ<sub>fast</sub> = {max(rm.over):.1f} °C measured</td></tr>
  <tr><td>Theorem 1 (power, update by update)</td><td>{rm.th['runs']} runs, {rm.th['updates']:,} price updates, {rm.th['unexplained_neg_steps'] + rm.th['unexplained_pos_steps']} unexplained</td><td>Holds on every run</td></tr>
  <tr><td>Final controller against v4.1 (5 paired repetitions)</td><td>mesh mission {pm(pF[('mesh_mission', 'v41')])}; multihop {pm(pF[('multihop', 'v41')])}</td><td>Costs nothing on one hop</td></tr>
  <tr><td>Against the AccuMO-style planner</td><td>mesh mission {pm(pF[('mesh_mission', 'accumo')])}; multihop {pm(pF[('multihop', 'accumo')])}: v4.1 sent {rm.shX0['laptop'][0]:.0f} % of its frames to the two-hop laptop, whose results arrived late (median {rm.shX0['laptop'][1]:.0f} ms) and shared the relay's radio. The planner and the LEAF-style weight drew {min(dW):.2f}–{max(dW):.2f} W less</td><td>The planner won multihop: <b>not held</b> before the fix</td></tr>
  <tr><td>The fixes: a 2.4 W budget and the late-path skip</td><td>Budget 2.4 − 2.8 W: Pi power {sg(pB['mesh_mission'][1]['mean'], '{:+.2f}')} / {sg(pB['multihop'][1]['mean'], '{:+.2f}')} W, sAP {sg(pB['mesh_mission'][0]['mean'])} / {sg(pB['multihop'][0]['mean'])} (n.s.). Skip of paths predicted late: multihop {pm(pX['multihop'])} (the planner's lead was {abs(pF[('multihop', 'accumo')]['mean']):.4f}); laptop share {rm.shX0['laptop'][0]:.1f} → {rm.shX['laptop'][0]:.1f} %; one-hop mission {pm(pX['mesh_mission'])}</td><td>Power gap closed by the budget; multihop gap closed by the skip, with a small one-hop cost (narrowly not held)</td></tr>
  <tr><td>v4.1+ (YOLO11n-480 onboard, room-following budget)</td><td>Never throttled; the room-following budget held its power but missed its temperature target under bursty load</td><td>Room-following budget dropped</td></tr>
  <tr><td>The CPU clock as a third knob</td><td>1.8 GHz is the energy minimum ({rm.rng(save, "{:.0f}")} % less energy per inference than 2.4 GHz). The controller chose it for {min(rm.s18):.0f}–{max(rm.s18):.0f} % of its onboard inferences, yet power changed by {sg(rm.pDhw['mean'], '{:+.3f}')} W and sAP by {sg(rm.pDh['mean'])} / {sg(rm.pDs['mean'])}: the price spends the saving on more inferences</td><td>Implemented, measured, neutral</td></tr>
  <tr><td>Two camera drones on one channel</td><td>A second Jetson costs accuracy (static {rm.two[('static_good', 'v41j1')][0]:.4f} → {rm.two[('static_good', 'v41j2')][0]:.4f}; mission {rm.two[('mesh_mission', 'v41j1')][0]:.4f} → {rm.two[('mesh_mission', 'v41j2')][0]:.4f} per camera); a per-camera cap does not fix it. A swarm-wide pull-one-ahead coordinator holds {pv('pull1', 8)} on-time results/s at 8 streams where the v4.1 rule collapses to {pv('v41', 8)}</td><td>Receiver-driven scheduling works on the mesh; fairness across hosts not shown</td></tr>
  <tr><td>Topology (5 repetitions, one campaign)</td><td>hier − v4.1: multihop {sg(tsm['mean_diff'])} (5/5), one hop {sg(tst['mean_diff'])} (0/5)</td><td>Topology reversal confirmed</td></tr>
  <tr><td>Frame rate</td><td>On-time results/s at 15 / 30 / 60 fps: {rm.fps['v41_f15'][0]:.1f} / {rm.fps['v41_f30'][0]:.1f} / {rm.fps['v41_f60'][0]:.1f}; 30 fps with encode-ahead {rm.fps['v41ea_f30'][0]:.1f}</td><td>The radio idles between 30-fps ticks</td></tr>
  <tr><td>Paper 1: the break-even goodput, live (T10)</td><td>The best measured option at every goodput from {min(rm.best):g} to {max(rm.best):g} Mbit/s was a JPEG; with a token-bucket link the 4 KB code wins at 0.5 Mbit/s</td><td>The rule's prediction held</td></tr>
  <tr><td>Paper 1: encode times measured on the Pi (T11)</td><td>Pi/laptop {min(rm.ratios):.2f}–{max(rm.ratios):.2f} for video, {pim['jpeg_pi_over_laptop']:.1f} for JPEG, against the rule's scale of {pim['scale_rule']:.1f}. With measured times the headline code's Pi B<sub>be</sub> is {meas[('jpeg', HJ)]['b_be_mbps']:.2f} Mbit/s against JPEG (rule {rule[('jpeg', HJ)]['b_be_mbps']:.2f}) and {meas[('both', HJ)]['b_be_mbps']:.2f} against JPEG + video (rule {rule[('both', HJ)]['b_be_mbps']:.2f}); {rm.wins_video} winning cells with video. YOLO11s codes: {min(ys):.2f}–{max(ys):.2f} Mbit/s, {rm.y11['wins_total']} wins</td><td>Paper 1's Pi numbers replaced by measured ones; verdict unchanged and sharper</td></tr>
  <tr><td>The deadline model on the hardware</td><td>{ca['n']:,} offloaded frames of {rm.cal['runs']} runs: ECE {ca['ece']:.3f}; observed ≥ predicted in every bin; frames predicted near 0 arrived on time {low:.0f} % of the time</td><td>Never over-confident; pessimistic at the low end</td></tr>
  <tr><td>The SSH tunnel on the laptop path</td><td>83 KB frame {rm.rng(rm.tunr['laptop'])} ms through it against {rm.rng(rm.tunr['pi-sender'])} ms over the direct hop</td><td>A small measured artefact (+{min(tdel):.0f}–{max(tdel):.0f} ms)</td></tr>
</table></div>
<p><b>The final controller</b> (paper 2): v4.1 + the capped hold and guard at 76.5 °C + YOLO11n-480 onboard (timed at start-up, priced at its measured energy) + a 10 ms contention term + a 2.4 W budget + the late-path skip. Removed by decision (no equipment): airflow over the Pi and flight. Cut as redundant after these results: joint fades, a governor comparison, YOLO11m on the ground, the remaining board profiles, the batman-adv overhead test and the bridge re-run (the tunnel's cost was measured instead). Paper 2 builds at 10 pages and paper 1 at 19, every number generated.</p>
"""

NEG = f"""    <li>On the mesh boards (14–16 Nov): the guard's peak bound needs a measured fast-mode term ({max(rm.over):.1f} °C); the room-following budget missed its temperature target under bursty load; the CPU clock is neutral under a power budget; a second edge drone on one shared channel costs accuracy and a per-camera cap does not fix it; the AccuMO-style planner beat the greedy controller in multihop until the late-path skip, which costs a little on one hop; pull-one-ahead fairness across hosts was not shown; the deadline probabilities are pessimistic at the low end.</li>
"""

FAULTS = """    <tr><td>Windows-launched board sessions lost PATH and environment; a leftover link logger; a charger that dropped three times (14–16 Nov)</td><td>One session stopped at its health check; two paused; no result lost</td><td>Full paths, environment exported, exact-PID clean-up; sessions resumed on mains; battery runs archived and re-run</td></tr>
    <tr><td>Four tool faults in the break-even sweep (slow NMS, token-bucket credit, sender order, warm-up)</td><td>Found by smoke tests before the sweep</td><td>Fixed before the first counted run</td></tr>
"""

LIMITS_REPL = [
    ("<li>One camera drone on the mesh; results for larger swarms come from the calibrated simulator.</li>",
     "<li>At most two camera drones and two edge drones on the mesh, on one shared channel; results for larger swarms "
     "come from the calibrated simulator.</li>"),
    ("<li>The laptop joins the mesh through SSH port forwards on the ground radio, which acknowledges data before it "
     "reaches the laptop.</li>",
     "<li>The laptop joins the mesh through SSH port forwards on the ground radio, which acknowledges data before it "
     "reaches the laptop; measured cost +" + f"{min(tdel):.0f}–{max(tdel):.0f}" + " ms per frame.</li>"),
    ("<li>The video options assume an error-free stream, and their encode times on the boards are scaled from the "
     "laptop, not measured.</li>",
     "<li>The video options assume an error-free stream; their Pi encode times are now measured (4.16), their Jetson "
     "times are still scaled from the laptop.</li>"),
    ("<li>The capped hold, the hard guard and the room-following budget are trace-replay results; the replay ranks hot "
     "time correctly but misses its level by 16 points.</li>",
     "<li>The capped hold and the hard guard are measured on the boards (4.16); the guard's bound needs a measured "
     f"fast-mode term ({max(rm.over):.1f} °C). No airflow or flight test (no equipment). The deadline probabilities are pessimistic at the low "
     "end; a recalibrated estimate is untested.</li>"),
    ("and the YOLO11s device times are scaled from YOLOv8s measurements.</li>",
     "and the YOLO11s Jetson times are scaled from YOLOv8s measurements (on the Pi they are measured within 2 % of the "
     "rule).</li>"),
]

LIMITS_REPL += [
    ("<p>Paper 2 builds at 9 pages. The hard guard, the capped hold and the room-following budget are replay results "
     "until the board session confirms them.</p>",
     "<p>Paper 2 builds at 9 pages. The hard guard, the capped hold and the room-following budget are replay results "
     "until the board session confirms them. <b>16 Nov:</b> the boards confirmed the capped hold and the guard (with a "
     "measured overshoot term) but not the room-following budget, which was dropped (4.16).</p>"),
    ("5 in the Wi-Fi energy campaigns); some controller variants differ only slightly.</li>",
     "5 in the Wi-Fi energy campaigns, and 5 paired repetitions in the 14–16 Nov final, late-path and topology "
     "campaigns); some controller variants differ only slightly.</li>"),
]

BOARDS_OLD_START = '    <div class="card"><h3>Needs the boards</h3><ul>'
BOARDS_NEW = f"""    <div class="card"><h3>Boards: done (14–16 Nov)</h3><ul>
      <li>Every board test is done (4.16, Results Brief 19.24–19.31): two camera drones, the planner and the LEAF-style weight on the mesh with 5 repetitions, both topologies in one campaign, the capped hold and the guard, the energy test, the noisy relay, video encode times on the Pi and the live break-even sweep. Nothing more is planned on the mesh.</li>
      <li>Not done, by decision: a flight or tethered test and airflow over the Pi (no equipment); stated as limitations.</li>
    </ul></div>"""

TEAM_REPL = [
    ("<li>Both papers: a rewrite around the new results and a fresh audit (about 1–2 days). Paper 2 is now 9 pages: "
     "check the venue's limit.</li>",
     "<li>Both papers now include the board results (paper 1: 19 pages, paper 2: 10 pages, every number generated). "
     "Check each venue's page limit.</li>\n"
     "      <li><s>Verify the full title of one new paper 2 reference (Sun 2026) against the publisher's record.</s> "
     "Done 16 Nov with Crossref; the title is corrected in the paper.</li>"),
    ("<li>Pick the board day and check the venue deadlines.</li>", "<li>Check the venue deadlines.</li>"),
]

NOVELTY_REPL = [
    ("Paper 2 is more realistic for TMC; INFOCOM only if the board session confirms the capped hold.",
     "Paper 2 is more realistic for TMC; INFOCOM only if the board session confirms the capped hold. <b>Update 16 "
     "Nov:</b> the board sessions confirmed the capped hold and the guard (with a measured overshoot term), measured "
     "two camera drones on the mesh and the published-style planner on the testbed (it won multihop until the "
     "late-path skip), and replaced paper 1's Pi numbers with measured ones (4.16). The swarm coordinator is now a "
     "measured receiver-driven scheduler (as in datacentre transport, NDP and Homa), not a simulation; the CPU-clock "
     "knob is neutral."),
    ("<td>JCAB (bandwidth and configuration); DroneCOCoNet</td><td><span class=\"chip mid\">medium</span>, simulation "
     "only</td>",
     "<td>JCAB (bandwidth and configuration); DroneCOCoNet; receiver-driven transport (NDP, Homa)</td><td><span "
     "class=\"chip mid\">medium</span>: the pull-one-ahead coordinator measured on the mesh (4.16)</td>"),
]

HEAD_REPL = [
    ("26 October 2026, updated 12 November 2026", "26 October 2026, updated 16 November 2026"),
    ("<div><b>≈ 1,150</b><span>live hardware runs in 19 campaigns</span></div>",
     f"<div><b>≈ 1,150</b><span>live hardware runs in 19 campaigns, plus {TOTAL} on the mesh boards on 14–16 Nov</span></div>"),
    ("below about 2 Mbit/s on the Pi, and 1.5 Mbit/s even on the Jetson once the camera can use low-delay video (4.14).",
     "below about 2 Mbit/s on the Pi, and 1.5 Mbit/s even on the Jetson once the camera can use low-delay video (4.14). "
     f"On the boards a JPEG was the best option at every goodput tested, and with measured Pi encode times no code wins "
     f"once video is allowed (4.16)."),
    ("pricing the edge drone's energy saves only 0–10 % of its power (about 4 % at a budget that costs almost no accuracy).",
     "pricing the edge drone's energy saves only 0–10 % of its power (about 4 % at a budget that costs almost no accuracy). "
     f"On the boards, capping the blackout hold takes the time at ≥ 80 °C from {hot(t4['v41'])} % to "
     f"{hot(t4['v41cap'])} % at the same accuracy (4.16)."),
]

INV_ROWS = "".join(f'    <tr><td>{d} (<code>{c}</code>)</td><td>Mesh</td><td class="num">{NRUNS[c]}</td><td>14–16 Nov</td></tr>\n'
                   for c, d in CAMPS)
INV_REPL = [
    ('    <tr><td><b>Total</b></td><td></td><td class="num"><b>≈ 1,150</b></td>',
     INV_ROWS + f'    <tr><td><b>Total</b></td><td></td><td class="num"><b>≈ {1150 + TOTAL:,}</b></td>'),
]

FILES = """    <tr><td>Mesh board sessions (14–16 Nov)</td><td>predictions and verdicts <code>docs/mesh_predictions_nov14.md</code>, <code>docs/mesh_results_nov15.md</code>; session log <code>docs/mesh_session_nov14.md</code>; every number <code>scripts/report_mesh_nov16.py</code>; campaigns <code>tools/campaign_final_nov.sh</code>, <code>campaign_dvfs_nov.sh</code>, <code>campaign_t10_nov.sh</code>; paper 1 board numbers <code>evaluation/board_metrics_paper1.py</code>, <code>pi_measured_break_even.py</code></td></tr>
"""


def main():
    s = F.read_text()
    if MARK in s:
        print("already applied")
        return
    ARCH.mkdir(parents=True, exist_ok=True)
    shutil.copy2(F, ARCH / F.name)
    for old, new in HEAD_REPL + LIMITS_REPL + TEAM_REPL + NOVELTY_REPL + INV_REPL:
        assert s.count(old) == 1, ("replace anchor", old[:80], s.count(old))
        s = s.replace(old, new)
    # the "Needs the boards" card, replaced whole
    i = s.index(BOARDS_OLD_START)
    j = s.index("    </ul></div>", i) + len("    </ul></div>")
    s = s[:i] + BOARDS_NEW + s[j:]
    for anchor, text in (('</section>\n\n<section id="negative">', S416),
                         ('  </ul>\n</section>\n\n<section id="novelty">', NEG),
                         ('  </table></div>\n</section>\n\n<section id="next">', FAULTS),
                         ('    <tr><td>Fine-tuned weights</td>', FILES)):
        assert s.count(anchor) == 1, ("insert anchor", anchor[:80], s.count(anchor))
        s = s.replace(anchor, text.strip("\n") + "\n" + anchor)
    s = s.replace("</main>", MARK + "\n</main>", 1)
    F.write_text(s)
    print("updated", F, "runs", TOTAL, NRUNS)


# ---------------------------------------------------------------- the Novelty Brief (same numbers, own marker)
NB = ROOT / "AEGIS-UAV Novelty Brief.html"
NB_ARCH = rm.R / "_superseded" / "report_before_novelty_nov16"
NB_MARK = "<!-- novelty-update-nov16 -->"

NB_SEC = f"""<!--nb16--><section>
  <h2>Update 16 Nov 2026: what the mesh board sessions changed</h2>
  <p>On 14–16 November every board test was run on five boards of the mesh ({TOTAL} controller runs in {len(CAMPS)} campaigns, plus a live break-even sweep, an encoder bench and a pull bench), each with its prediction committed first (Results Brief 19.24–19.31; verdicts in <code>docs/mesh_results_nov15.md</code>). Claim by claim:</p>
  <div class="tbl"><table>
    <tr><th>Claim</th><th>Before</th><th>Measured on the boards</th><th>Novelty now</th></tr>
    <tr><td><b>Paper 2: the controller's blackout hold drives the heat; capping it and a hard guard remove it</b></td><td>Replay only</td><td>v4.1 at ≥ 80 °C for {hot(t4['v41'])} % of a 24-min mission, throttled; the capped hold {hot(t4['v41cap'])} %, never throttled, same accuracy. Theorem 3 holds only with a measured fast-mode term: the die overshoots the guard by {min(rm.over):.1f}–{max(rm.over):.1f} °C. The closest new work, thermal partitioning of real-time tasks on fanless boards (Sun et al., RTAS 2026), is single-device scheduling, with no offloading and no streaming accuracy</td><td><span class="chip yes">high</span> for the heat diagnosis, now measured</td></tr>
    <tr><td><b>Paper 2: a greedy priced choice does as well as a planner</b></td><td>Replay: tie</td><td>On the boards (5 paired repetitions) the AccuMO-style planner <b>won multihop</b> by {abs(pF[('multihop', 'accumo')]['mean']):.4f}: v4.1 kept sending late frames to the two-hop laptop. The late-path skip recovers it, by {pm(pX['multihop'])}, at a small, non-significant one-hop cost; on one hop the final controller leads the planner by {pm(pF[('mesh_mission', 'accumo')])}</td><td><span class="chip part">medium</span>: a measured head-to-head with a published-style planner, including where greedy lost</td></tr>
    <tr><td><b>Paper 2: the power guarantee</b></td><td>376 runs</td><td>{rm.th['runs']} runs, {rm.th['updates']:,} updates, {rm.th['unexplained_neg_steps'] + rm.th['unexplained_pos_steps']} unexplained. The budget was the cause of the planner's power advantage: at 2.4 W the final controller draws {abs(pB['multihop'][1]['mean']):.2f} W less at the same accuracy</td><td><span class="chip part">medium</span>, unchanged</td></tr>
    <tr><td><b>Swarm: sharing one channel</b></td><td>Simulation only</td><td>A second edge drone on the same channel costs every camera accuracy, and a per-camera cap does not fix it. A swarm-wide pull-one-ahead coordinator keeps {pv('pull1', 8)} on-time results/s at 8 streams, where the v4.1 rule falls to {pv('v41', 8)}. Fairness across hosts was not shown</td><td><span class="chip part">medium</span>: receiver-driven scheduling (NDP, SIGCOMM 2017; Homa, SIGCOMM 2018) applied and measured on a drone mesh; the idea is not ours. Simulated multi-UAV offloading (Du et al., arXiv 2605.03898) is latency-only</td></tr>
    <tr><td><b>Topology decides the architecture</b></td><td>3 repetitions, two campaigns</td><td>One campaign, 5 repetitions: hier − v4.1 {sg(tsm['mean_diff'])} in multihop (5/5), {sg(tst['mean_diff'])} with a direct link (0/5)</td><td><span class="chip part">medium</span>, now isolated</td></tr>
    <tr><td><b>Paper 1: the break-even rule</b></td><td>Model and simulator only</td><td>Predict-then-measure on the real link: a JPEG was best at every goodput from {min(rm.best):g} to {max(rm.best):g} Mbit/s, as predicted; on a token-bucket link a 4 KB code wins at 0.5 Mbit/s, so how the link is slow matters. Pi encode times measured (Pi/laptop {min(rm.ratios):.2f}–{max(rm.ratios):.2f}, not the rule's {pim['scale_rule']:.1f}): the headline code's Pi B<sub>be</sub> is {meas[('jpeg', HJ)]['b_be_mbps']:.2f} Mbit/s against JPEG and {meas[('both', HJ)]['b_be_mbps']:.2f} against video; {rm.wins_video} winning cells with video</td><td><span class="chip yes">high</span> as a tested rule, now with a hardware check</td></tr>
    <tr><td><b>The CPU clock as a priced knob</b></td><td>Not tried</td><td>1.8 GHz is the energy minimum, and the controller chose it for {min(rm.s18):.0f}–{max(rm.s18):.0f} % of its onboard inferences, but under a power budget the saving buys more inferences, not less power</td><td><span class="chip no">low</span>: a neutral, reported result</td></tr>
    <tr><td><b>The deadline model</b></td><td>44,524 frames</td><td>{ca['n']:,} frames: never over-confident (ECE {ca['ece']:.3f}), pessimistic at the low end ({low:.0f} % of frames predicted near 0 arrived on time)</td><td>Supporting</td></tr>
  </table></div>
  <p><b>What reviewers will still attack.</b> No flight and no airflow test: removed by decision (no equipment), and stated as limitations. The fanless motivation of the closest heat work (RTAS 2026) supports testing without a fan. At most two camera drones share one channel. The guard's bound needs a measured overshoot term, and the late-path skip costs a little where the late path was a useful backup.</p>
  <p><b>Venue view, 16 Nov.</b> Two of the three top-venue gaps named above are closed on the hardware: two camera drones on the mesh, and a published-style scheduler measured on the testbed. The third, flight, is out of scope. Paper 1 (19 pages) is realistic for IEEE TMC and a strong fit for IoT-J. Paper 2 (10 pages) is realistic for TMC; INFOCOM is now arguable, since the capped hold is confirmed on the boards. Check each venue's page limit.</p>
</section><!--/nb16-->
"""

NB_REPL = [
    ("26 Oct 2026, updated 12 Nov 2026</div>", "26 Oct 2026, updated 16 Nov 2026</div>"),
    ("see the section after the verdict.</p>",
     f"see the section after the verdict. Updated 16 Nov 2026: the mesh board sessions ({TOTAL} runs; Results Brief "
     "19.24–19.31), in the first section after the verdict.</p>"),
    ("For a top venue paper 2 now most needs an airflow test (does the heat cost survive propeller wash?) and the "
     "capped hold on the board.</p>",
     "For a top venue paper 2 now most needs an airflow test (does the heat cost survive propeller wash?) and the "
     "capped hold on the board. <b>16 Nov:</b> the capped hold, two camera drones and the planner are now measured on "
     "the boards; airflow and flight are out of scope (no equipment).</p>"),
    ("<li>One camera drone on the mesh; multi-drone results are simulated.</li>",
     "<li>At most two camera drones and two edge drones, on one shared channel; larger swarms are simulated.</li>"),
    ("<li>3 repetitions per mesh cell; some controller variants differ only slightly.</li>",
     "<li>3 repetitions per mesh cell in most campaigns (5 in the final comparisons); some controller variants differ "
     "only slightly.</li>"),
    ("<li>A published scheduler (AccuMO-style) is re-implemented, but compared only in the trace replay so far; the "
     "board campaign is scripted, not run.</li>",
     "<li>A published scheduler (AccuMO-style) is re-implemented and measured on the boards; it beat the greedy "
     "controller in multihop until the late-path skip.</li>"),
    ("<li>In flight, propeller wash may cool the board: does the heat cost survive? Not tested.</li>",
     "<li>In flight, propeller wash may cool the board: does the heat cost survive? Not tested (no equipment).</li>"),
    ("<li>The break-even rule is checked in the authors' own model and simulator, not yet on the real link; the capped "
     "hold and the hard guard are replay results.</li>",
     "<li>The break-even rule is checked on one real link (a Pi 5 to a Jetson, shaped by netem and a token bucket); "
     "the guard's bound needs a measured overshoot term.</li>"),
    ("<li>The laptop joins the mesh through an SSH tunnel on the ground radio.</li>",
     "<li>The laptop joins the mesh through an SSH tunnel on the ground radio (measured cost "
     f"+{min(tdel):.0f}–{max(tdel):.0f} ms per frame).</li>"),
    ("<li>Two camera drones on the mesh (third Pi): measured contention for the Jetson.</li>",
     "<li><s>Two camera drones on the mesh (third Pi): measured contention for the Jetson.</s> Done 15–16 Nov.</li>"),
    ("<li>The AccuMO-style planner on the mesh against v4.1 and LEAF (ported and tested; <code>campaign_mesh4.sh</code>, "
     "45 runs, about 6 h).</li>",
     "<li><s>The AccuMO-style planner on the mesh against v4.1 and LEAF.</s> Done 14–16 Nov, 5 repetitions.</li>"),
    ("<li>5 repetitions in the headline mesh comparisons.</li>",
     "<li><s>5 repetitions in the headline mesh comparisons.</s> Done for the final comparisons and the topology.</li>"),
    ("<li>An airflow test over the Pi, and the capped hold and the guard over 24-minute missions on the board "
     "(prepared: Results Brief 19.23).</li>",
     "<li><s>The capped hold and the guard over 24-minute missions on the board.</s> Done 14–15 Nov. An airflow test: "
     "out of scope (no equipment).</li>"),
    ("<li>A predict-then-measure test of the break-even rule on the real link (shape the Pi's link on the boards, "
     "predict the crossover first).</li>",
     "<li><s>A predict-then-measure test of the break-even rule on the real link.</s> Done 16 Nov (T10, T11).</li>"),
    ("<td>Admission rule with link health, calibrated simulator (r = 0.947); no admission-control paper found</td>"
     "<td><span class=\"chip part\">medium</span>, simulation only</td>",
     "<td>Admission rule with link health, calibrated simulator (r = 0.947); on the boards, a measured pull-one-ahead "
     "coordinator (receiver-driven, as NDP and Homa) holds a shared channel at capacity (16 Nov)</td>"
     "<td><span class=\"chip part\">medium</span>, measured on two cameras</td>"),
    ("<td>The comparison on the same link draws, with the planner ported to the board code; a hardware campaign is "
     "still needed</td><td><span class=\"chip no\">low until measured on the board</span></td>",
     "<td>The comparison on the same link draws, with the planner ported to the board code. On the boards (16 Nov) the "
     "planner won multihop until the late-path skip; on one hop the priced controller leads</td>"
     "<td><span class=\"chip part\">medium</span>, measured</td>"),
    ("<td>A measured head-to-head of the two designs on one batman-adv mesh, with forced multi-hop</td><td><span "
     "class=\"chip part\">medium</span>, 3 reps</td>",
     "<td>A measured head-to-head of the two designs on one batman-adv mesh, with forced multi-hop</td><td><span "
     "class=\"chip part\">medium</span>, 5 reps in one campaign (16 Nov)</td>"),
]

NB_REPL += [
    ("and a 45-run mesh campaign against v4.1 and LEAF is scripted; until it runs, this comparison is replay-only.</p>",
     "and a 45-run mesh campaign against v4.1 and LEAF is scripted; until it runs, this comparison is replay-only. "
     "<b>16 Nov:</b> it ran on the boards with 5 repetitions: the planner won multihop until the late-path skip, and on "
     "one hop the priced controller leads (first section after the verdict).</p>"),
    ("in the replay it ties v4.1 or is slightly ahead, by less than the replay's known error</td>",
     "in the replay it ties v4.1 or is slightly ahead, by less than the replay's known error; on the boards it won "
     "multihop until the late-path skip (16 Nov)</td>"),
]

NB_SRC = """<!--nbsrc16-->    <li>Added 16 Nov (<code>docs/related_work_check_nov16.md</code>): Sun et al., AI Inference in the Heat: Thermal-Aware Strict Partitioning for Configurable Real-Time Gang Tasks, RTAS 2026, doi 10.1109/RTAS68450.2026.00031 (checked with Crossref); Du, Xu &amp; Yu, multi-UAV sensing offload and edge inference <a href="https://arxiv.org/abs/2605.03898">arxiv 2605.03898</a>; NDP (SIGCOMM 2017) doi 10.1145/3098822.3098825; Homa (SIGCOMM 2018) doi 10.1145/3230543.3230564; BiSwift <a href="https://arxiv.org/abs/2312.15740">arxiv 2312.15740</a>; HECS-B <a href="https://arxiv.org/abs/2504.15295">arxiv 2504.15295</a>.</li>
<!--/nbsrc16-->
"""


def novelty():
    s = NB.read_text()
    if NB_MARK in s:
        print("novelty: already applied")
        return
    NB_ARCH.mkdir(parents=True, exist_ok=True)
    shutil.copy2(NB, NB_ARCH / NB.name)
    for old, new in NB_REPL:
        assert s.count(old) == 1, ("novelty replace anchor", old[:80], s.count(old))
        s = s.replace(old, new)
    for anchor, text in (("<!--nb12--><section>", NB_SEC), ("<!--/nbsrc12-->\n", None)):
        assert s.count(anchor) == 1, ("novelty insert anchor", anchor, s.count(anchor))
        s = s.replace(anchor, text + anchor) if text else s.replace(anchor, anchor + NB_SRC)
    s = s.replace("</main>", NB_MARK + "\n</main>", 1) if "</main>" in s else s + NB_MARK
    NB.write_text(s)
    print("updated", NB)


if __name__ == "__main__":
    main()
    novelty()
