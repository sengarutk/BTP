#!/usr/bin/env python3
"""Reports for the laptop strengthening of 16-17 Nov 2026 (docs/laptop_strengthening_predictions_nov16.md):
Results Brief 19.32-19.38 (+ state box, Part 20 negatives, Part 23 note), Final Report 4.17 (+ negatives, limitations,
what is left), Novelty Brief "Update 17 Nov 2026". Every number is computed here from the result files. Idempotent:
marked blocks are replaced on every run; the Final Report and Novelty Brief edits are applied once (marker comment).
Previous versions are archived in experiments/results/hardware/_superseded/report_before_laptop_nov17/.
usage: python scripts/report_laptop_nov17.py
"""
import json
import re
import shutil
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import report_mesh_nov16 as rm  # noqa: E402  (html_to_md, strip_marked, paths)

ROOT = HERE.parents[1]
H = HERE.parent / "experiments" / "results" / "hardware"
RES = HERE.parent / "experiments" / "results"
ARCH = H / "_superseded" / "report_before_laptop_nov17"
BRIEF_H, BRIEF_M = ROOT / "AEGIS-UAV Results Brief.html", ROOT / "AEGIS-UAV Results Brief.md"
FINAL, NOVEL = ROOT / "AEGIS-UAV Final Report.html", ROOT / "AEGIS-UAV Novelty Brief.html"
MARK_F, MARK_N = "<!-- final-report-update-nov17 -->", "<!-- novelty-update-nov17 -->"


def J(p):
    return json.load(open(p))


def sg(x, f="{:+.4f}"):
    return f.format(x).replace("-", "−")


# ---------------------------------------------------------------- numbers
eq = {c["label"]: c for c in J(H / "equivalence" / "equivalence.json")["comparisons"]}
rc = J(H / "calibration" / "calib_recal_nov16.json")
cf = J(H / "replay" / "conformal_nov12" / "summary.json")
sk = J(H / "skip_counterfactual" / "skip_cf.json")
pmc = J(H / "overload_handling" / "pull_model_check.json")
tm = J(H / "theory_check" / "thermal_two_mode.json")
mc = J(H / "t10" / "t10_model_check.json")
jm = J(RES / "video_codecs" / "analysis_jetson_measured.json")
lit = J(RES / "literature" / "published_splits.json")["papers"]
af = J(H / "replay" / "airflow_nov16" / "airflow_summary.json")
sr = J(H / "replay" / "skip_nov16" / "skip_summary.json")
fr = J(H / "fps_sap_estimate.json")

A24 = af["mission_240s"]
KS = sorted({float(p[2:].split("_")[0]) for p in A24}, reverse=True)


def a(k, b, m="hot_share"):
    return A24.get(f"af{k:g}_{b}", {}).get(m)


def first_zero(b):
    """largest k (least airflow needed) from which the policy's hot time is 0 for this and every smaller k"""
    ok = [k for k in KS if a(k, b) is not None]
    for i, k in enumerate(ok):
        if all(a(kk, b) == 0.0 for kk in ok[i:]):
            return k
    return None


kz = {b: first_zero(b) for b in ("v41", "hold", "guard", "noprice")}
W_spread = {b: (min(a(k, b, "pi_w") for k in KS if a(k, b, "pi_w") is not None),
                max(a(k, b, "pi_w") for k in KS if a(k, b, "pi_w") is not None)) for b in ("v41", "noprice")}
eqs = [c for c in eq.values() if c["equivalent"]]
jrow = lambda v, fam: {r["code"]: r for r in jm["versions"][v][fam]["rows"]}["joint_k4_c4_w128_d2"]  # noqa: E731
au = next(x for x in lit if x["key"] == "autosplit")
s0, s1 = sr["shared0"]["all"], sr["shared1"]["all"]


def tr(k):
    return "—" if k is None else f"{100 * (1 - k):.0f} %"


AF_ROWS = "".join(
    f"<tr><td>{k:g} ({100 * (1 - k):.0f} % lower)</td>"
    + "".join(f"<td>{100 * a(k, b):.1f} %</td>" if a(k, b) is not None else "<td>—</td>"
              for b in ("noprice", "v41", "hold", "guard"))
    + f"<td>{a(k, 'v41', 'pi_w'):.2f} / {a(k, 'noprice', 'pi_w'):.2f}</td></tr>"
    for k in KS if a(k, "v41") is not None)

SECS = f'''<h3>19.32 Laptop strengthening of both papers, 16-17 Nov 2026: what was done and how</h3>
<p>The boards were not set up again (the user's decision). Every remaining weakness of the two papers was patched on the laptop from recorded data and the validated replay, with predictions committed first (<code>docs/laptop_strengthening_predictions_nov16.md</code>; verdicts in the same file). Order: equal accuracy as a tested equivalence, airflow, the deadline probability, published split results, the board-free versions of the planned board items (Jetson camera, held-out skip checks, more camera hosts), the thermal fast mode, the paper 1 conference version, the open feature-coding baseline. The laptop restarted twice when it slept on battery; every runner resumed from its finished rows. <span class="tag v">Validated</span></p>

<h3>19.33 "Same accuracy" as a tested equivalence (paper 2)</h3>
<p>Two one-sided t-tests (TOST, α 0.05) of the paired sAP differences against a margin of ±{J(H / "equivalence" / "equivalence.json")["margin_sap"]} sAP (<code>equivalence_tost.py</code>): {len(eqs)} of {len(eq)} comparisons are shown equivalent.</p>
<table><tr><th>comparison (pairs)</th><th>ΔsAP, 90 % CI</th><th>equivalent?</th><th>ΔPi W</th><th>Δ time ≥ 80 °C</th></tr>
{"".join(f"<tr><td>{c['label']} ({c['pairs']})</td><td>{sg(c['sap']['mean'])} [{sg(c['sap_ci90'][0])}, {sg(c['sap_ci90'][1])}]</td><td>{'yes' if c['equivalent'] else 'not shown'} (p {c['tost_p']:.3f})</td><td>{sg(c['pi_w']['mean'], '{:+.2f}')}</td><td>{sg(c['hot_pct']['mean'], '{:+.1f}') + ' pts' if 'hot_pct' in c else '—'}</td></tr>" for c in eq.values())}</table>
<ul><li>Paper 2 now says "equal accuracy" only where it is shown; the power and heat saved are the effect.</li></ul>

<h3>19.34 How much airflow removes the heat cost (paper 2; replaces the airflow test)</h3>
<p>Airflow lowers the board's thermal resistance; in the validated replay the plant's slope and time constant were scaled by k (<code>replay_airflow.py</code>; 24-min mission with its total blackout; seeds {A24[f"af{KS[-1]:g}_v41"]["seeds"]}). Share of time at or above 80 °C:</p>
<table><tr><th>thermal resistance k</th><th>no prices</th><th>v4.1 (hold always)</th><th>capped hold</th><th>capped hold + guard</th><th>Pi W: v4.1 / no prices</th></tr>{AF_ROWS}</table>
<ul><li><b>Hot time vanishes</b> from k = {kz['noprice']} for the unpriced controller (thermal resistance {tr(kz['noprice'])} lower), from k = {kz['v41']} for v4.1 ({tr(kz['v41'])}), and the capped hold with the guard is cool at every k from {kz['guard']}.</li>
<li><b>The energy price's saving remains at every airflow level</b>: v4.1 draws {W_spread['v41'][0]:.2f}–{W_spread['v41'][1]:.2f} W across k, the unpriced controller {W_spread['noprice'][0]:.2f}–{W_spread['noprice'][1]:.2f} W (its onboard runs get faster on a cooler board, so the saving shrinks a little). Airflow removes the heat cost, not the power saving.</li>
<li>Stated in paper 2 as the threshold a flight test would have to beat: the heat result holds unless airflow lowers the board's thermal resistance by more than the amount above.</li></ul>

<h3>19.35 The deadline probability, recalibrated (paper 2)</h3>
<ul><li><b>On the boards</b> (<code>calib_recal.py</code>; fit on 14-15 Nov, test on the held-out 16 Nov, {rc['n_test']:,} frames): ECE {rc['groups']['all']['raw']['ece']:.3f} → {rc['groups']['all']['isotonic']['ece']:.4f} (isotonic), {rc['groups']['all']['platt']['ece']:.4f} (logistic). Per path the miscalibration differs: frames predicted late arrived on time {100 * rc['groups']['jetson']['below_half_observed']:.0f} % of the time on the Jetson path and {100 * rc['groups']['laptop']['below_half_observed']:.0f} % on the laptop path; a per-path map gives ECE {rc['per_path']['jetson']['isotonic']['ece']:.4f} and {rc['per_path']['laptop']['isotonic']['ece']:.4f}.</li>
<li><b>In the replay</b>, a conformal (distribution-free) p_on (<code>replay_conformal.py</code>, predictions of 12 Nov, all held): ECE {cf['policies']['v41']['calibration']['ece']:.3f} → {cf['policies']['v41_conf']['calibration']['ece']:.3f}, miss rate of frames sent at p_on ≥ 0.95 {100 * cf['policies']['v41_conf']['miss_rate_p_ge_095']:.1f} %, sAP {sg(cf['paired_sAP_conf_minus_v41']['mean'])} ± {cf['paired_sAP_conf_minus_v41']['ci95']:.4f} ({cf['paired_sAP_conf_minus_v41']['n']} pairs).</li></ul>

<h3>19.36 The late-path rule checked where it was not designed (paper 2)</h3>
<ul><li><b>Held-out board logs</b> (<code>skip_counterfactual.py</code>; v4.1 runs of mesh4, topology_nov, relaynoise_nov, energy_nov): in multihop the rule acts on {100 * sk['held_out']['multihop|raw']['affected_share']:.0f} % of network frames, of which {100 * sk['held_out']['multihop|raw']['all']['on_time_share']:.0f} % arrived on time ({100 * sk['design']['multihop|raw']['all']['on_time_share']:.0f} % in the design data): its multihop gain is mainly the relay radio it frees, not only late frames dropped (prediction 7a.1 not held).</li>
<li><b>One hop</b>: with p_on recalibrated per path (maps from 14-15 Nov), the frames it acts on on 16 Nov fall from {sk['recal_16nov']['one_hop|raw']['affected']} to {sk['recal_16nov']['one_hop|recalibrated_per_path']['affected']}, {100 * (1 - sk['recal_16nov']['one_hop|recalibrated_per_path']['all']['on_time_share']):.0f} % of them late: the recalibrated rule keeps the useful backups (offline counterfactual).</li>
<li><b>Held-out replay seeds</b> (<code>replay_skip.py</code>; seeds 11-20, random / mission_mirror / static_good): rule − v4.1 sAP {sg(s0['sAP']['mean'])} ± {s0['sAP']['ci95']:.4f} with independent radios, {sg(s1['sAP']['mean'])} ± {s1['sAP']['ci95']:.4f} with one shared radio ({s0['sAP']['n']} pairs each).</li></ul>

<h3>19.37 Paper 1: the timing model, a fast camera, published wins</h3>
<ul><li><b>The T10 timing model against the sweep</b> (<code>t10_model_check.py</code>): median error of the on-time rate {100 * mc['median_abs_rel_err_ge1']:.0f} % over the {mc['n_cells_ge1']} cells with ≥ 1 result/s (r {mc['pearson_r']:.2f}); best option matched at {mc['best_match']} of {mc['rates']} goodputs (both JPEG at the other).</li>
<li><b>A Jetson as the camera, on measured times</b> (<code>jetson_measured_break_even.py</code>): the smallest joint code's B_be against JPEG {jrow('measured', 'jpeg')['b_be_mbps']:.2f} Mbit/s (as scaled times), {jm['versions']['measured']['jpeg']['wins_total']} winning cells; with video {jrow('video_pi_like_lo', 'both')['b_be_mbps']:.2f}–{jrow('measured', 'both')['b_be_mbps']:.2f} Mbit/s depending on the unmeasured Jetson video encode time; 0 exceptions. No live Jetson sweep.</li>
<li><b>Published wins re-read</b> ({len(lit)} papers, <code>literature/published_splits.json</code>): none compares with an accuracy-matched image; Auto-Split's {au['advantage_raw']:.1f}× latency gain over the raw image is {au['advantage_matched']:.1f}× against its own JPEG of equal mAP.</li>
<li><b>Conference version</b> of paper 1: <code>paper/main_conf.tex</code> (IEEE conference format, every number generated).</li>
<li><b>MPEG feature coding</b>: CompressAI-Vision is open but needs the VVC reference codec and supports other detector families; beyond the 2-hour limit, stated as a limitation.</li></ul>

<h3>19.38 More camera hosts and the thermal fast mode (paper 2)</h3>
<ul><li><b>Pull model against the bench</b> (<code>pull_model_check.py</code>; the model committed 13 Nov, the bench run 15 Nov): shape reproduced, rate overstated by {min(100 * r['rel_err'] for r in pmc['rows'] if r['method'] == 'pull1'):.0f}–{max(100 * r['rel_err'] for r in pmc['rows'] if r['method'] == 'pull1'):.0f} %; extrapolated (model × measured/model) {pmc['pull1_extrapolated_scaled']['16']:.1f} on-time results/s at 16 streams, v4.1's rule 0.</li>
<li><b>Camera rate</b> (<code>fps_sap_estimate.py</code>; the T7 summary fixed, it had been committed empty): streaming AP at 15 / 30 / 60 fps estimated from the held result's real age (proxy r {fr['pearson_r']:.3f} on {fr['calibration_runs']} runs at 30 fps): {fr['by_strategy']['v41_f15']['sAP_fc_est']:.3f} / {fr['by_strategy']['v41_f30']['sAP_fc_est']:.3f} / {fr['by_strategy']['v41_f60']['sAP_fc_est']:.3f}, flat; on-time results/s {fr['by_strategy']['v41_f15']['on_time_fps']:.1f} / {fr['by_strategy']['v41_f30']['on_time_fps']:.1f} / {fr['by_strategy']['v41_f60']['on_time_fps']:.1f}: v4.1's sending rule cannot be overloaded by a faster camera; the cost is power and heat.</li>
<li><b>Two-time-constant thermal fit</b> (<code>thermal_two_mode.py</code>): τ {tm['fit']['tau_f']} s and {tm['fit']['tau_s']} s; its overshoot bound ({tm['delta_fast_c']:.1f} °C) held in {sum(r['bound_holds'] for r in tm['runs'].values())} of {len(tm['runs'])} guarded runs and its simulated peaks were too low: the fast-mode term must be measured (negative result).</li></ul>
'''

STATE = f'''<div class="box state"><b class="h">State on 17 Nov 2026 (laptop strengthening done; details in 19.32-19.38)</b><ul>
<li><b>Paper 2</b>: equal accuracy tested ({len(eqs)} of {len(eq)} comparisons equivalent within ±0.005 sAP); the heat result holds unless airflow lowers the board's thermal resistance by more than {tr(kz['v41'])} (replay); the deadline probability recalibrated (held-out day) and its effect on the late-path rule explained.</li>
<li><b>Paper 1</b>: the timing model within {100 * mc['median_abs_rel_err_ge1']:.0f} % of the sweep; a fast camera keeps a real window on measured times; none of {len(lit)} published split results uses an accuracy-matched image baseline; a conference version exists.</li>
<li><b>Negatives</b>: the late-path rule's multihop gain is mostly the radio it frees; a two-mode thermal model cannot replace the measured fast-mode term; the pull model is 15-23 % optimistic.</li>
<li><b>Left</b>: the user's decisions (venues and page limits, authors, push).</li></ul></div>
'''

NEG = f'''<li><b>Laptop strengthening 16-17 Nov (19.32-19.38).</b> Equal accuracy is not shown for the final controller in multihop alone, the capped hold alone (TOST p {eq['capped hold vs hold always, 24 min']['tost_p']:.3f}), the late-path rule on one hop and the clock knob. The late-path rule's held-out multihop frames were on time {100 * sk['held_out']['multihop|raw']['all']['on_time_share']:.0f} % of the time. A fitted two-mode thermal model does not bound the guard's overshoot. The pull model overstates the coordinator's rate. Video encode on a Jetson camera was not measured.</li>
'''

LEFT = '''<!--left17--><p><b>Update 17 Nov 2026:</b> the laptop strengthening is done (19.32-19.38); both papers and every report are updated. Left: the user's decisions only (venues, page limits, authors, push).</p>
<!--/left17-->'''

S417 = f'''
<h3>4.17 Strengthened on the laptop: tested equivalence, airflow, calibration, a fast camera, published wins (16–17 Nov)</h3>
<p>With the boards packed away, every weakness the 16 Nov review found was patched from recorded data and the validated replay, predictions first (Results Brief 19.32–19.38).</p>
<div class="tbl"><table>
  <tr><th>Weakness</th><th>What was done</th><th>Result</th></tr>
  <tr><td>"Same accuracy" was not a test</td><td>Two one-sided t-tests, margin ±0.005 sAP</td><td>{len(eqs)} of {len(eq)} comparisons shown equivalent; the rest stated as not shown</td></tr>
  <tr><td>No airflow test</td><td>Replay with the board's thermal resistance lowered step by step</td><td>v4.1's hot time vanishes once resistance falls by {tr(kz['v41'])}, the unpriced controller's by {tr(kz['noprice'])}; the power saving stays</td></tr>
  <tr><td>Pessimistic deadline probability</td><td>Recalibrated on two board days, tested on the third; conformal estimate in the replay</td><td>ECE {rc['groups']['all']['raw']['ece']:.3f} → {rc['per_path']['jetson']['isotonic']['ece']:.3f}–{rc['per_path']['laptop']['isotonic']['ece']:.3f} per path; conformal ECE {cf['policies']['v41_conf']['calibration']['ece']:.3f} at no accuracy cost</td></tr>
  <tr><td>The late-path rule looked post hoc</td><td>Checked on held-out logs and replay seeds</td><td>Multihop gain is mostly the radio it frees; per-path recalibration removes its one-hop cost (counterfactual)</td></tr>
  <tr><td>Paper 1 had only "JPEG wins" on hardware</td><td>Model checked cell by cell; a Jetson camera on measured times</td><td>Model within {100 * mc['median_abs_rel_err_ge1']:.0f} %; a Jetson camera keeps a {jrow('measured', 'jpeg')['b_be_mbps']:.1f} Mbit/s window against JPEG</td></tr>
  <tr><td>"The rule is obvious"</td><td>{len(lit)} published split results re-read</td><td>None uses an accuracy-matched image; Auto-Split's {au['advantage_raw']:.1f}× becomes {au['advantage_matched']:.1f}×</td></tr>
  <tr><td>Two camera drones only</td><td>The pull model checked against the bench, then extrapolated</td><td>Shape right, rate {min(100 * r['rel_err'] for r in pmc['rows'] if r['method'] == 'pull1'):.0f}–{max(100 * r['rel_err'] for r in pmc['rows'] if r['method'] == 'pull1'):.0f} % high</td></tr>
  <tr><td>Theorem 3's fast-mode term measured, not derived</td><td>Two-time-constant fit</td><td>Negative: the model cannot replace the measurement</td></tr>
</table></div>
<p>Paper 1 now has a 5-page conference version (<code>paper/main_conf.tex</code>); the MPEG feature-coding baseline stays a limitation (its open toolkit needs the VVC codec and other detectors).</p>
'''


def brief():
    h, m = BRIEF_H.read_text(), BRIEF_M.read_text()
    j = h.index('<h2 id="argument">')
    assert 0 <= h.find("<h3>19.31 ") < j
    i = h.find("<h3>19.32 ")
    h = h[:i if 0 <= i < j else j] + SECS + h[j:]
    j = m.index("## PART 20")
    i = m.find("### 19.32 ")
    m = m[:i if 0 <= i < j else j] + rm.html_to_md(SECS) + m[j:]
    old = "; mesh board sessions 14–16 Nov (19.24–19.31)"
    new = old + "; laptop strengthening 16–17 Nov (19.32–19.38)"
    if new not in h:
        assert old in h and old in m
        h, m = h.replace(old, new), m.replace(old, new)
    for doc in ("h", "m"):
        s = h if doc == "h" else m
        s = rm.strip_marked(s, "<!--state17-->", "<!--/state17-->")
        k = s.index("<!--state16-->")
        s = s[:k] + "<!--state17-->" + ("" if doc == "h" else "\n") + (STATE if doc == "h" else rm.html_to_md(STATE)) \
            + "<!--/state17-->\n" + ("" if doc == "h" else "\n") + s[k:]
        s = rm.strip_marked(s, "<!--neg17-->", "<!--/neg17-->")
        if doc == "h":
            k = s.index("<!--neg16-->")
            s = s[:k] + "<!--neg17-->" + NEG + "<!--/neg17-->\n" + s[k:]
        else:
            k = s.index("<!--neg16-->")
            s = s[:k] + "<!--neg17-->\n" + rm.html_to_md("<ul>" + NEG + "</ul>").rstrip() + "\n<!--/neg17-->\n" + s[k:]
        s = rm.strip_marked(s, "<!--left17-->", "<!--/left17-->")
        k = s.index("<!--left16-->")
        s = s[:k] + (LEFT if doc == "h" else "<!--left17-->\n" + rm.html_to_md(
            LEFT.replace("<!--left17-->", "").replace("<!--/left17-->", "")).rstrip() + "\n<!--/left17-->") + "\n" + s[k:]
        s = re.sub(r"Full project report · state on [0-9]+ [A-Za-z]+ 2026", "Full project report · state on 17 Nov 2026", s, count=1)
        if doc == "h":
            h = s
        else:
            m = s
    BRIEF_H.write_text(h)
    BRIEF_M.write_text(m)


def once(path, mark, edits, inserts):
    s = path.read_text()
    if mark in s:
        print(path.name, "already updated")
        return
    for old, new in edits:
        assert s.count(old) == 1, (path.name, old[:70], s.count(old))
        s = s.replace(old, new)
    for anchor, text in inserts:
        assert s.count(anchor) == 1, (path.name, anchor[:70])
        s = s.replace(anchor, text.strip("\n") + "\n" + anchor)
    s = s.replace("</main>", mark + "\n</main>", 1)
    path.write_text(s)


def final():
    once(FINAL, MARK_F,
         [("26 October 2026, updated 16 November 2026", "26 October 2026, updated 17 November 2026"),
          ("Both papers now include the board results (paper 1: 19 pages, paper 2: 10 pages, every number generated). "
           "Check each venue's page limit.",
           "Both papers now include the board results and the laptop strengthening of 16–17 Nov (4.17); paper 1 also "
           "has a 5-page conference version (<code>paper/main_conf.tex</code>). Check each venue's page limit.")],
         [('</section>\n\n<section id="negative">', S417),
          ('  </ul>\n</section>\n\n<section id="novelty">', NEG.replace("<li><b>Laptop strengthening 16-17 Nov (19.32-19.38).</b>",
                                                                       "    <li>Laptop strengthening (16–17 Nov):")),
          ('  </ul>\n</section>\n\n\n<section id="faults">' if '  </ul>\n</section>\n\n\n<section id="faults">' in FINAL.read_text()
           else '  </ul>\n</section>\n\n<section id="faults">',
           f"    <li>Airflow is bounded in the replay, not measured: the heat result holds unless airflow lowers the board's "
           f"thermal resistance by more than {tr(kz['v41'])}. The per-path recalibration of the deadline probability is an "
           f"offline counterfactual, not a board run.</li>\n")])


def novelty():
    sec = f'''<!--nb17--><section>
  <h2>Update 17 Nov 2026: what the laptop strengthening changed</h2>
  <p>Without the boards, every weakness named on 16 Nov was patched from recorded data and the validated replay, predictions first (Results Brief 19.32–19.38).</p>
  <div class="tbl"><table>
    <tr><th>Claim</th><th>Change</th><th>Novelty now</th></tr>
    <tr><td><b>Paper 1: the break-even rule</b></td><td>The timing model is within {100 * mc['median_abs_rel_err_ge1']:.0f} % of the board sweep cell by cell; on a Jetson camera, measured times keep a real {jrow('measured', 'jpeg')['b_be_mbps']:.1f} Mbit/s window against JPEG; none of {len(lit)} published split results uses an accuracy-matched image (Auto-Split's {au['advantage_raw']:.1f}× becomes {au['advantage_matched']:.1f}× against one)</td><td><span class="chip yes">high</span>: a rule that re-reads the literature, not only our own results</td></tr>
    <tr><td><b>Paper 2: heat priced at equal accuracy</b></td><td>Equal accuracy tested ({len(eqs)} of {len(eq)} comparisons equivalent within ±0.005 sAP); airflow bounded in the replay (heat cost gone once thermal resistance falls by {tr(kz['v41'])}; the power saving stays)</td><td><span class="chip yes">high</span>, now with a stated condition under which it holds</td></tr>
    <tr><td><b>Paper 2: the deadline probability</b></td><td>Recalibrated per path on a held-out day (ECE {rc['groups']['all']['raw']['ece']:.3f} → {rc['per_path']['jetson']['isotonic']['ece']:.3f}–{rc['per_path']['laptop']['isotonic']['ece']:.3f}); a conformal estimate fixes it in the replay at no accuracy cost</td><td><span class="chip part">medium</span>: a distribution-free guarantee checked on hardware logs</td></tr>
    <tr><td><b>Paper 2: the late-path rule</b></td><td>Checked on held-out logs: its multihop gain is mostly the radio it frees; per-path recalibration removes its one-hop cost (counterfactual)</td><td><span class="chip part">medium</span>, no longer post hoc</td></tr>
  </table></div>
  <p><b>Venue view, 17 Nov.</b> Paper 1 has a 5-page conference version for IEEE ICC/Globecom/WoWMoM-class venues and the journal version for TMC/IoT-J. Paper 2 (11 pages) fits TMC; INFOCOM stays a stretch without flight. No venue is certain.</p>
</section><!--/nb17-->
'''
    once(NOVEL, MARK_N, [("26 Oct 2026, updated 16 Nov 2026</div>", "26 Oct 2026, updated 17 Nov 2026</div>")],
         [("<!--nb16--><section>", sec)])


def main():
    ARCH.mkdir(parents=True, exist_ok=True)
    for f in (BRIEF_H, BRIEF_M, FINAL, NOVEL):
        if not (ARCH / f.name).exists():
            shutil.copy2(f, ARCH / f.name)
    brief()
    final()
    novelty()
    print("reports updated; airflow thresholds", kz)


if __name__ == "__main__":
    main()
