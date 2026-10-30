#!/usr/bin/env python3
"""Report update, 29 Oct 2026 (part 3): a published scheduler (AccuMO-style model-predictive offloading) against v4.1
in the replay, as 19.10 (docs/laptop_additions_2026-10-29_part3.md).

Every number is read from replay/accumo_oct29/accumo_summary.json and its rows (replay_accumo.py) and from the replay
validation (replay/validate_main_oct29_plant/replay_check.json). Adds 19.10 after 19.9, a Part 1 bullet, a pointer in
16.1 and changes the published-scheduler row of "What is left". Run after report_laptop2_oct29.py. Idempotent.
usage: report_accumo_oct29.py     (the originals are archived in
       experiments/results/hardware/_superseded/report_before_accumo_oct29/)
"""
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_parts_oct22 import HTML, MD, html_to_md, table  # noqa: E402

HW = Path(__file__).resolve().parent.parent / "experiments" / "results" / "hardware"
D = HW / "replay" / "accumo_oct29"
SC = [("mission_20s", "mission (6 × 20 s)"), ("mission_mirror_20s", "mirror mission (6 × 20 s)"),
      ("random_20s", "random links (30 × 4 s)"), ("static_good_20s", "good links (6 × 20 s)"),
      ("mission_240s", "24-min mission (6 × 4 min)")]
COLS = [("accumo", "AccuMO-style"), ("accumo_global", "AccuMO-style, one global curve"),
        ("accumo_energy", "AccuMO-style + v4.1's energy price"), ("leaf", "LEAF-style fixed weight"),
        ("v4", "v4 (v4.1 without the freshness price)")]


def fmt(d):
    """paired v41 - this -> this - v41, bold where the interval excludes 0."""
    s = f"{round(-d['mean'], 4) + 0.0:+.4f} ± {d['ci95']:.4f} (n {d['n']})".replace("-", "−")
    return f"<b>{s}</b>" if abs(d["mean"]) > d["ci95"] else s


def numbers():
    s = json.load(open(D / "accumo_summary.json"))
    rows = [json.load(open(f)) for f in D.glob("rows/*.json")]
    plan = [r["plan_ms_median"] for r in rows if r["policy"].startswith("accumo") and "plan_ms_median" in r]
    p95 = [r["plan_ms_p95"] for r in rows if r["policy"].startswith("accumo") and "plan_ms_p95" in r]
    chk = json.load(open(HW / "replay" / "validate_main_oct29_plant" / "replay_check.json"))["paired_vs_v5"]["leaf"]
    # the stored v4.1 rows of the oracle replay (19.8) must be reproduced exactly
    rep = []
    for r in rows:
        if r["policy"] == "v41" and r["phase_s"] == 20.0:
            f = HW / "replay" / "oracle_oct29_plant" / "rows" / f"{r['scenario']}__v41__r{r['seed']}.json"
            if f.exists():
                rep.append(abs(json.load(open(f))["sAP"] - r["sAP"]))
    return s, float(np.median(plan)), float(np.median(p95)), chk, rep


def section():
    s, pm, p95, chk, rep = numbers()
    rows = []
    for k, lab in SC:
        P = s[k]["policies"]
        rows.append([lab, f"{P['v41']['sAP']:.4f}"] + [fmt(P[c]["v41_minus"]) if c in P else "—" for c, _ in COLS]
                    + [f"{100 * P['accumo']['send_share']['onboard']:.1f} % / {100 * P['v41']['send_share']['onboard']:.1f} %",
                       f"{100 * P['accumo']['fresh_share']:.0f} % / {100 * P['v41']['fresh_share']:.0f} %"])
    t = table(["Scenario", "v4.1 sAP + fc"] + [f"{lab} − v4.1" for _, lab in COLS] +
              ["frames onboard, AccuMO-style / v4.1", "time fresh (< 300 ms), AccuMO-style / v4.1"], rows)
    P = {k: s[k]["policies"] for k, _ in SC}
    lit = [P["mission_20s"][b]["v41_minus"]["mean"] for b in ("jsq", "aoi_thr", "conf_trigger", "reward_offload")]
    acc_lit = [P["mission_20s"][b]["sAP"] for b in ("jsq", "aoi_thr", "conf_trigger", "reward_offload")]
    long = P["mission_240s"]
    hw = f"{chk['hardware_diff']:+.4f}".replace("-", "−")
    return f'''<h3>19.10 A published scheduler in the replay: AccuMO-style model-predictive offloading (29 Oct 2026)</h3>
<p>The closest published scheduler, AccuMO (MobiCom 2023), predicts how the accuracy of the last result falls with its
age, depending on content (camera motion), and plans offloading over a 30-frame horizon (model-predictive control) to
maximise the predicted accuracy; it prices neither energy nor heat. Part 16.1 argues that a greedy per-frame choice
with slow prices is enough. This section tests that argument in the replay. Script
<code>validation/hardware/replay_accumo.py</code>, output <code>replay/accumo_oct29/</code>, write-up
<code>docs/laptop_additions_2026-10-29_part3.md</code>; nothing earlier was changed or re-scored.</p>
<ul>
<li><b>The planner.</b> The accuracy model is our measured decay with forecaster v2 for the camera-motion tertile of the
current frame (AccuMO's content dependence; tertiles fixed on train). A plan fixes one setting, or none, per server for
the next 30 frames (9 × 7 × 4 = 252 plans). Each server repeats its setting whenever it is free, and its results arrive
after the expected latency at the live goodput estimate. Results already in flight are included, re-predicted with the
live estimator. The objective is the mean over the horizon of the accuracy of the result on screen (the newest capture
that has arrived) times its decay. Each frame the best plan is recomputed and one of its idle servers is started. The
search takes {pm:.1f} ms per frame on the laptop, beside other jobs (95th percentile {p95:.1f} ms).</li>
<li><b>Ablations.</b> One global decay curve instead of the content-conditioned one, and the planner with v4.1's energy
price (same 2.8 W target and dual update), which separates planning from pricing.</li>
<li><b>Same conditions as 19.8.</b> The same seeds and link draws for every policy; the stored v4.1 runs of 19.8 are
reproduced exactly ({len(rep)} runs, {'identical sAP' if max(rep) == 0 else f'largest difference {max(rep):.1e} sAP'}). 15 seeds for the mission and random
scenarios, 5 for the others, 7 for the 24-minute mission.</li>
</ul>
{t}
<p>(Bold: the 95 % interval excludes zero. Positive means better than v4.1.)</p>
<ul>
<li><b>In the replay, v4.1 does not beat the AccuMO-style planner.</b> They tie on the mission, mirror mission and good
links. The planner is ahead on random links ({fmt(P['random_20s']['accumo']['v41_minus'])}) and over the 24-minute mission
({fmt(long['accumo']['v41_minus'])}, {long['accumo']['hot_share'] * 100:.0f} % of the time ≥ 80 °C against
{long['v41']['hot_share'] * 100:.0f} %). It sends fewer frames onboard and keeps results fresh less of the time, yet
scores higher. A likely reason: an onboard result is newer, so on screen it replaces a better offloaded one that is
still on its way; the planner sees that cost, while v4.1's freshness price pushes towards onboard results (v4, without
that price, recovers part of the gap on random links).</li>
<li><b>The gain is not from planning.</b> The LEAF-style fixed-weight greedy controller is ahead of v4.1 by as much or
more in every scenario, and v4 (v4.1 without the freshness price) is ahead on random links. Content conditioning adds
nothing (the global curve gives the same result), and adding v4.1's energy price to the planner changes nothing (without it,
its power is already at or below the 2.8 W target).</li>
<li><b>These differences are within the replay's known error for this kind of comparison.</b> The validation against
the 240-run main campaign (19.8) has the replay putting LEAF {chk['replay_diff']:+.4f} sAP ahead of v5 where the
hardware measured a tie ({hw}): the replay favours policies that run less onboard. On hardware
v4.1 − v4 was +0.0025 ± 0.0041 (G11) and LEAF tied v5 (G12). So the replay cannot rank the AccuMO-style planner
against v4.1; only a board campaign can.</li>
<li><b>Against the other literature baselines the planner behaves like v4.1.</b> On the mission, v4.1 is ahead of
shortest-queue, freshness-threshold, confidence-trigger and offloading-reward scheduling by
{min(lit):+.4f} to {max(lit):+.4f} sAP (sAP {min(acc_lit):.4f}–{max(acc_lit):.4f}), and the planner by similar
margins.</li>
<li><b>What this changes.</b> The paper cannot claim that v4.1 beats AccuMO-style planning. The supported claim is
narrower: on this system a greedy priced choice does as well as a 30-frame model-predictive planner, at a fraction of
the computation. The hardware test is the planner against v4.1 and LEAF on the board (the planner needs porting into
<code>adaptive2.py</code>, and its time on the Pi measuring).</li>
</ul>
'''


STATE = ('<li><b>A published scheduler (19.10, 29 Oct):</b> in the replay an AccuMO-style 30-frame planner ties v4.1 or '
         'is slightly ahead (random links, 24-min mission), but so is a LEAF-style fixed weight, and these differences '
         'are within the replay\'s known error; the claim narrows to "a greedy priced choice does as well as planning". '
         'The board test is listed under "What is left".</li>\n')
OLD_ROW = ("5 repetitions of the 24-minute missions; a published scheduler (AoPI- or AccuMO-style) re-implemented on "
           "the testbed")
NEW_ROW = ("5 repetitions of the 24-minute missions; the AccuMO-style planner of 19.10 against v4.1 and the LEAF-style "
           "weight on the board (replay done: within its error)")
OLD_NEEDS = "<td>Mesh; code</td><td>about 1 day; 1 week</td>"
NEW_NEEDS = "<td>Mesh; port the planner into <code>adaptive2.py</code></td><td>about 1 day; 1–2 days</td>"
PTR = (" Whether planning would do better is tested in the replay in 19.10: an AccuMO-style 30-frame planner does no "
       "better than a greedy priced choice, within the replay's error.")
GREEDY_END = "maximising an average reward under average constraints."


def main():
    h, m = HTML.read_text(), MD.read_text()
    sec = section()
    j = h.index('<h2 id="argument">')
    i = h.find("<h3>19.10 ")
    h = h[:i if 0 <= i < j else j] + sec + h[j:]
    j = m.index("## PART 20")
    i = m.find("### 19.10 ")
    m = m[:i if 0 <= i < j else j] + html_to_md(sec) + m[j:]
    h = re.sub(r"<li><b>A published scheduler \(19\.10.*?</li>\n", "", h, flags=re.S)
    k = h.index('<div class="box state">')
    k = h.index("<ul>\n", k) + len("<ul>\n")
    h = h[:k] + STATE + h[k:]
    m = re.sub(r"^- \*\*A published scheduler \(19\.10.*\n", "", m, flags=re.M)
    k = m.index("**State on 26 Oct 2026")
    k = m.index("\n- ", k) + 1
    m = m[:k] + html_to_md("<ul>" + STATE + "</ul>").strip() + "\n" + m[k:]
    if PTR not in h:
        assert h.count(GREEDY_END) == 1 and m.count(GREEDY_END) == 1
        h, m = h.replace(GREEDY_END, GREEDY_END + PTR), m.replace(GREEDY_END, GREEDY_END + PTR)
    h = h.replace(f"<tr><td>{OLD_ROW}</td>{OLD_NEEDS}", f"<tr><td>{NEW_ROW}</td>{NEW_NEEDS}")
    m = m.replace(f"| {OLD_ROW} | Mesh; code | about 1 day; 1 week |",
                  f"| {NEW_ROW} | Mesh; port the planner into `adaptive2.py` | about 1 day; 1–2 days |")
    assert NEW_ROW in h and NEW_ROW in m
    HTML.write_text(h)
    MD.write_text(m)
    print("report updated: 19.10, Part 1 bullet, 16.1 pointer, what is left")


if __name__ == "__main__":
    main()
