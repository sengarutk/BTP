#!/usr/bin/env python3
"""Report update, 24 Oct 2026: section 18.9 (second mesh campaign, every pricing strategy on the AegisSwarm mesh, 66
short + 16 long runs), two faults found during it (Part 21), the state box and "What is left".
Numbers come from experiments/results/hardware/vid_campaign_mesh2{,_long}_summary.json (validation/hardware/
mesh2_summary.py) and the run files (Jetson variant mix, the Jetson energy log). Idempotent: re-running replaces
the section and the rows it added.
"""
import collections
import glob
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_parts_oct22 import HTML, MD, html_to_md, table  # noqa: E402

HW = Path(__file__).resolve().parent.parent / "experiments" / "results" / "hardware"
NM = {"v41": "v4.1: Pi energy + freshness", "v41e": "v4.1 + Jetson energy", "heat": "heat + freshness",
      "heate": "heat + Jetson energy + freshness", "noprice": "no prices (stream objective)",
      "fixlap": "fixed Pi → laptop, YOLOv8m q90", "aoithr": "freshness threshold (literature)",
      "hier": "hierarchical chain"}
SC = {"static_good": "normal", "mesh_mission": "mesh mission", "multihop": "multihop", "ALL": "all three"}
ORDER = ["v41", "v41e", "heat", "heate", "noprice", "fixlap", "aoithr", "hier"]


def load(name):
    return json.load(open(HW / f"{name}_summary.json"))


def cell_rows(c, scen):
    rows = []
    for sc in scen:
        for m in ORDER:
            x = c.get(f"{sc}|{m}")
            if x is None:
                continue
            pa = ", ".join(f"{k} {100 * v:.0f} %" for k, v in sorted(x["processed_at"].items(), key=lambda t: -t[1])
                           if v >= .005)
            th = x["pi_throttled"][0]
            rows.append([SC[sc], NM[m], x["n"], f"{x['sAP'][0]:.3f}", f"<b>{x['sAP_fc'][0]:.3f} ± {x['sAP_fc'][1]:.3f}</b>",
                         f"{x['mAP'][0]:.3f}", f"{x['p_aoi300'][0]:.3f}", f"{x['aoi_p95_ms'][0]:.0f} ms",
                         f"{x['deadline_met_fps'][0]:.1f}", f"{x['lat_median_ms'][0]:.0f} ms",
                         f"{x['pi_w'][0]:.2f} W, {x['pi_temp_c'][0]:.0f} °C, {100 * th:.0f} %", pa])
    return rows


HEAD = ["Scenario", "Strategy", "runs", "sAP", "sAP + forecaster", "mAP", "P(AoI ≤ 300 ms)", "95th-pct AoI",
        "deadline-met throughput (/s)", "median latency", "Pi: power, temp., throttled", "processed at"]


def pr(p, cmp_, sc, k):
    r = p.get(f"{cmp_}|{sc}", {}).get(k)
    if r is None:
        return "–"
    return f"{r['mean_diff']:+.3f} ({r['first_ahead']}/{r['pairs']}, p {r['p_perm']:.3f})"


def paired_table(p, scen, cmps):
    rows = []
    for x, y in cmps:
        cmp_ = f"{x}-{y}"
        rows.append([f"{NM[x]} − {NM[y]}"] + [pr(p, cmp_, sc, "sAP_fc") for sc in scen]
                    + [pr(p, cmp_, "ALL", "pi_w").replace("+", "+").split(" (")[0] + " W",
                       pr(p, cmp_, "ALL", "pi_temp_c").split(" (")[0] + " °C"])
    return table(["Comparison (same scenario and repetition)"] + [f"Δ sAP + fc, {SC[s]}" for s in scen]
                 + ["Δ Pi power (all)", "Δ Pi temp. (all)"], rows)


def jetson_mix():
    rows = []
    for camp, lab in (("vid_campaign_mesh2", "4-min"), ("vid_campaign_mesh2_long", "24-min")):
        for sc in ("static_good", "mesh_mission", "multihop"):
            for st in ("v41", "v41e", "heat", "heate"):
                fs = glob.glob(str(HW / camp / f"a2_{sc}__{st}__r*.json"))
                if not fs:
                    continue
                var, pe, mod = collections.Counter(), [], []
                for f in fs:
                    d = json.load(open(f))
                    var.update(x["variant"].split("q")[0] for x in d["frames"] if x.get("server") == "jetson")
                    pe += [e[2] for e in d["measured_energy"].get("mu_edge_log", []) if e[3] == "measured"]
                    mod.append(jetson_model_w(d))
                tot = sum(var.values())
                mix = ", ".join(f"{k[1:]} px {100 * v / tot:.0f} %" for k, v in var.most_common(3) if v / tot >= .005)
                rows.append([f"{SC[sc]} ({lab})", NM[st], mix, f"{np.mean(mod):.2f} W",
                             f"{np.mean(pe):.2f} W" if pe else "not logged"])
    return table(["Scenario", "Strategy", "Jetson input size (share of its frames)",
                  "Jetson extra power, from its profile", "Jetson extra power, measured live"], rows)


EC_J = json.load(open(HW / "energy" / "energy_constants.json"))["jetson"]


def jetson_model_w(d):
    """Extra Jetson power of a run from its measured profile: energy per inference of each frame it detected
    (by input size) over the run, plus the radio's receive power (energy/energy_constants.json)."""
    fr = d["frames"]
    e = sum(EC_J["infer_j"].get(x["variant"].split("q")[0], 0.0) for x in fr if x.get("server") == "jetson")
    return e / (len(fr) / 30.0) + EC_J["radio_rx_w"]


def section():
    s, lo = load("vid_campaign_mesh2"), load("vid_campaign_mesh2_long")
    c, p, ph = s["cells"], s["paired"], s["mission_phases_fc"]
    t1 = table(HEAD, cell_rows(c, ["static_good", "mesh_mission", "multihop"]))
    t1b = table(HEAD, cell_rows(c, ["ALL"]))
    scen = ["static_good", "mesh_mission", "multihop", "ALL"]
    t2 = paired_table(p, scen, [("noprice", "v41"), ("heat", "v41"), ("v41e", "v41"), ("heate", "heat"),
                                ("heate", "v41"), ("fixlap", "v41"), ("aoithr", "v41"), ("hier", "v41")])
    names = list(ph["v41"])
    t3 = table(["Strategy"] + [n.replace("_", " ") for n in names],
               [[NM[m]] + [f"{ph[m][n]:.3f}" for n in names] for m in ORDER if m in ph])
    t4 = table(HEAD, cell_rows(lo["cells"], ["mesh_mission"]))
    lp = lo["paired"]
    t5 = table(["Comparison (24-min missions)", "pairs", "Δ sAP + fc", "first ahead", "p", "Δ Pi power", "Δ Pi temp."],
               [[f"{NM[x]} − {NM[y]}", r["sAP_fc"]["pairs"], f"{r['sAP_fc']['mean_diff']:+.4f} ± {r['sAP_fc']['ci95']:.4f}",
                 f"{r['sAP_fc']['first_ahead']}/{r['sAP_fc']['pairs']}", f"{r['sAP_fc']['p_perm']:.3f}",
                 f"{r['pi_w']['mean_diff']:+.2f} W", f"{r['pi_temp_c']['mean_diff']:+.1f} °C"]
                for (x, y) in (("heat", "v41"), ("v41e", "v41"), ("heate", "heat"), ("heate", "v41"))
                for r in [lp[f"{x}-{y}|mesh_mission"]]])
    lph = lo["mission_phases_fc"]
    lnames = list(lph["v41"])
    t6 = table(["Strategy (24-min)"] + [n.replace("_", " ") for n in lnames],
               [[NM[m]] + [f"{lph[m][n]:.3f}" for n in lnames] for m in ORDER if m in lph])
    t7 = jetson_mix()
    A = lambda m, sc="ALL": c[f"{sc}|{m}"]  # noqa: E731
    P = lambda x, y, k="sAP_fc", sc="ALL": p[f"{x}-{y}|{sc}"][k]  # noqa: E731
    np_, he, ve, hh, fx, ao, hi = (P("noprice", "v41"), P("heat", "v41"), P("v41e", "v41"), P("heate", "heat"),
                                   P("fixlap", "v41"), P("aoithr", "v41"), P("hier", "v41", sc="multihop"))
    return f'''<h3>18.9 Second mesh campaign: every pricing strategy on the mesh (24 Oct 2026)</h3>
<p>The question: on the real mesh, which prices are worth having? Each strategy adds or removes one price of controller v4.1, with the same VisDrone weights and the live motion forecaster in all of them, and they are compared only with each other (one campaign, same code, same day). Network as in 18.8 (AegisSwarm IBSS mesh, batman-adv; camera drone pi-relayyy, edge drone the Jetson, ground radio pi-sender cabled to the laptop).</p>
<ul>
<li><b>Strategies:</b> <b>v4.1</b> (Pi energy price + freshness price); <b>v4.1 + Jetson energy price</b> (budget 0.5 W of extra Jetson power, measured live by the Jetson worker); <b>heat + freshness</b> (heat price on the Pi's temperature, target 75 °C, guard 84 °C, instead of the Pi energy price); <b>heat + Jetson energy + freshness</b>; <b>no prices</b> (the stream objective alone); <b>fixed Pi → laptop</b> (YOLOv8m, JPEG q90); <b>freshness threshold</b> (literature baseline: offload when the held result gets older than a threshold); and the <b>hierarchical chain</b> of 18.8 in the multihop scenario (its normal and mission runs are in 18.8).</li>
<li><b>Scenarios:</b> normal; the <b>mesh mission</b> of 18.8 (six phases: good → ground congested → camera out of range → edge uplink cut → camera → edge link slow → recovered); and <b>multihop</b>, new: the direct camera ↔ ground-radio link is blocked by a temporary nftables rule on both boards, so batman-adv relays every packet to the ground through the Jetson (camera → Jetson about 15 Mbit/s, Jetson → ground radio about 4 Mbit/s). Each multihop run starts only after the camera's route to the ground radio goes via the Jetson; every other run starts only after the direct route is back. The rule is removed after every run.</li>
<li><b>Runs:</b> 7 strategies × 3 scenarios × 3 repetitions + the chain × multihop × 3 = <b>66 four-minute runs</b>, order shuffled; then <b>16 twenty-four-minute mesh missions</b> (4-min phases): v4.1 and heat × 5, the two Jetson-priced strategies × 3. Scoring as 18.8 (<code>validation/hardware/mesh2_summary.py</code>; <code>experiments/results/hardware/vid_campaign_mesh2*</code>).</li>
</ul>
<div class="box"><b class="h">Two faults found during the campaign, both fixed before the runs reported here</b>
<ul>
<li><b>The camera lost results on a live link</b> (in the code since at least the first commit, 8 Oct, so in the campaigns since): the sender thread set a send timeout on the socket that the receiver thread was reading (<code>settimeout</code> switches the shared socket to non-blocking), so the receiver's next read could fail with "resource temporarily unavailable" and the thread ended; results were then lost until the next reconnect, while the sender kept sending. In the first runs, the no-price strategy got back 1,692 of 6,418 laptop results. Fixed with a kernel send timeout (<code>SO_SNDTIMEO</code>) that leaves the receiver alone (<code>adaptive.py</code>); the same run then got back 4,848 of 4,852. The campaign was restarted from scratch; the 5 runs made before the fix are archived. Strategies with the freshness price moved away from a path that stopped answering, so they were hit least; fixed policies and strategies without the freshness price kept feeding it. <b>Effect on the earlier campaigns</b> (<code>validation/hardware/receiver_fault_audit.py</code>, the 824 runs of Parts 12–18 made before the fix): the fault's signature, 1 s or more of results lost on a path whose link was not impaired, appears in 16 runs (2 %), mostly strategies without the freshness price (worst: 1,031 of 1,465 laptop results lost); results lost on unimpaired paths overall 0.03–1.7 % per campaign. Removing the 16 runs changes no verdict: in 9 of the 13 affected cells (strategy × scenario) the ranking is unchanged, in the other 4 two neighbours within their confidence intervals swap places (differences 0.0005–0.009 sAP against intervals of ±0.006–0.02). No re-run is needed.</li>
<li><b>The laptop's Ethernet dropped sparse packets:</b> its Realtek adapter has Energy-Efficient Ethernet, Green Ethernet and power saving on, and lost 100 % of pings at 1 per second, 23 % at 5 per second and none at 20 per second or more (bulk TCP was unaffected, 270 Mbit/s). Probes and SSH keep-alives on a quiet laptop path were lost, the tunnel dropped twice, and the laptop path stalled in some runs. From 07:42 IST a tiny keep-awake ping (20 per second, on the cable only, never on the mesh) held the adapter awake and the loss stopped. Every run was checked against a 1-s ping log and the laptop path's result loss: a run with more than 5 % of pings or laptop results lost, or a ping outage of 5 s or more, was archived and re-run (5 runs, all repetition 1; each re-run agrees with repetitions 2 and 3). Repetition-1 runs made before the keep-awake lost slightly more laptop results (1–3 % against under 1 %) but agree with their later repetitions within the spread shown.</li>
</ul></div>
<p><b>Results, 4-minute runs (3 per cell):</b></p>
{t1}
<p>Pooled over the three scenarios (9 runs per strategy):</p>
{t1b}
<p><b>Paired differences</b> (same scenario and repetition; mean difference, pairs where the first strategy is ahead, exact sign-flip permutation p; 3 pairs cannot give p below 0.25, 9 pairs give p down to 0.004):</p>
{t2}
<p>Mesh mission, per phase (sAP with forecaster, mean of 3):</p>
{t3}
<p><b>24-minute mesh missions</b> (5 runs for v4.1 and heat, 3 for the Jetson-priced strategies):</p>
{t4}
{t5}
{t6}
<p><b>What the Jetson energy price does</b> (all runs; the unpriced strategies do not log the Jetson's power):</p>
{t7}
<ul>
<li><b>The prices buy the same accuracy for far less heat.</b> Without prices the controller is as accurate as v4.1 ({np_['mean_diff']:+.3f} sAP with the forecaster, {np_['first_ahead']}/9 pairs ahead, p = {np_['p_perm']:.3f}) but runs the camera drone at {A('noprice')['pi_w'][0]:.1f} W and {A('noprice')['pi_temp_c'][0]:.0f} °C, throttled {100 * A('noprice')['pi_throttled'][0]:.0f} % of the time, against {A('v41')['pi_w'][0]:.1f} W, {A('v41')['pi_temp_c'][0]:.0f} °C and never throttled for v4.1 (+{P('noprice', 'v41', 'pi_w')['mean_diff']:.2f} W, +{P('noprice', 'v41', 'pi_temp_c')['mean_diff']:.1f} °C, 9/9 pairs, p = 0.004). The extra onboard work (12 % of frames against 2 %) adds almost nothing because the onboard detector is late.</li>
<li><b>The Pi energy price is the better guard; the heat price adds nothing measurable here.</b> Heat + freshness is as accurate as v4.1 ({he['mean_diff']:+.4f}, {he['first_ahead']}/9, p = {he['p_perm']:.2f}; 24-min: {lp['heat-v41|mesh_mission']['sAP_fc']['mean_diff']:+.4f}, 5 pairs) but runs {P('heat', 'v41', 'pi_w')['mean_diff']:.2f} W and {P('heat', 'v41', 'pi_temp_c')['mean_diff']:.1f} °C warmer (9/9, p = 0.004; 24-min +{lp['heat-v41|mesh_mission']['pi_w']['mean_diff']:.2f} W, +{lp['heat-v41|mesh_mission']['pi_temp_c']['mean_diff']:.1f} °C, 5/5). A heat price only acts near its target (75 °C), so below it the controller does slightly more onboard work; the energy price acts all the time and keeps the Pi near 70 °C. Neither throttled, even over 24 minutes: offloading keeps the camera drone cool, so on this mesh the heat price never had to act.</li>
<li><b>The Jetson energy price costs accuracy.</b> v4.1 + Jetson energy is {-ve['mean_diff']:.3f} behind v4.1 (0/9 pairs ahead, p = {ve['p_perm']:.3f}), heat + Jetson energy {-hh['mean_diff']:.3f} behind heat (0/9, p = {hh['p_perm']:.3f}); the loss is largest in multihop ({P('v41e', 'v41', sc='multihop')['mean_diff']:+.3f}), where two thirds to three quarters of the frames go to the Jetson, and holds over 24 minutes ({lp['v41e-v41|mesh_mission']['sAP_fc']['mean_diff']:+.3f}, 3/3). The reason is the budget: even with the smaller inputs the Jetson drew 0.9–1.3 W of extra power, so the 0.5 W budget was never met: the price reached its anti-windup cap (5) within about a minute and stayed there, and the camera shrank the Jetson's input from 640 to 480 or 320 px. That returns more results per second ({A('v41e')['deadline_met_fps'][0]:.1f} against {A('v41')['deadline_met_fps'][0]:.1f}) but less accurate ones (mAP {A('v41e')['mAP'][0]:.3f} against {A('v41')['mAP'][0]:.3f}), and streaming AP gains more from accuracy than it loses from the fewer results. What it saves: the unpriced runs did not log the Jetson's power, so it is computed from the Jetson's measured profile (energy per inference by input size, plus radio receive); where both exist, profile and live measurement agree within 0.1 W (table below). The price saves about 0 W in the normal scenario, 0.2 W in the mission and 0.6 W in multihop, out of the Jetson's 5–6 W total, i.e. 0–10 %, for 0.005–0.037 sAP. At this budget the Jetson energy price is not worth its accuracy cost; a budget near the Jetson's unpriced draw (about 1.0–1.4 W) would leave the normal and mission cases alone and act only when the Jetson carries the stream (multihop). From now on the camera logs the Jetson's power in every strategy (<code>edge_w_log</code>), so the next mesh session can test that budget directly.</li>
<li><b>Fixed offloading is best only while its link holds.</b> Fixed Pi → laptop is the most accurate strategy on a good link ({c['static_good|fixlap']['sAP_fc'][0]:.3f} against {c['static_good|v41']['sAP_fc'][0]:.3f}, 3/3) but falls to {c['mesh_mission|fixlap']['sAP_fc'][0]:.3f} in the mission (0 while the camera is out of range; P(AoI ≤ 300 ms) {c['mesh_mission|fixlap']['p_aoi300'][0]:.2f}) and {c['multihop|fixlap']['sAP_fc'][0]:.3f} in multihop (median latency {c['multihop|fixlap']['lat_median_ms'][0]:.0f} ms through the relay). The freshness threshold keeps results fresh (P(AoI ≤ 300 ms) about 1) but returns only 7–10 per second and is {-ao['mean_diff']:.3f} behind v4.1 (0/9).</li>
<li><b>When the ground can be reached only through the edge drone, the hierarchical chain is ahead.</b> In multihop the chain reaches {c['multihop|hier']['sAP_fc'][0]:.3f} against {c['multihop|v41']['sAP_fc'][0]:.3f} for v4.1 ({hi['mean_diff']:+.3f}, 3/3 pairs, p = {hi['p_perm']:.2f}, the smallest possible with 3): the Jetson detects {100 * c['multihop|hier']['processed_at'].get('jetson', 0):.0f} % of the frames itself, while v4.1 still sends about a fifth through the slow relayed hop to the laptop. With a direct camera → ground link (18.8) v4.1 was ahead by 0.047. The better design therefore depends on the topology: a direct link to the ground favours deciding everything on the camera, a relay-only route favours letting the relay decide. (18.8 ran before the receiver fix, but the audit above finds no affected run in it; its runs are a separate campaign, so the two are compared by verdict, not number for number.)</li>
<li><b>Long missions keep the ranking.</b> Over 24 minutes v4.1 and heat stay level ({lo['cells']['mesh_mission|v41']['sAP_fc'][0]:.3f} and {lo['cells']['mesh_mission|heat']['sAP_fc'][0]:.3f}, 5 runs each, spread ±0.002), the Jetson-priced strategies 0.008–0.011 behind (3/3), no throttling, mean Pi temperature 71–75 °C. Their per-phase values are not comparable with the 4-minute runs phase by phase: a 4-minute phase covers different footage of the test clips than a 40-s one.</li>
<li><b>Caveats:</b> 3 repetitions per scenario (pooled 9 pairs for the main comparisons), one indoor room, nodes one radio hop apart, a crowded 2.4 GHz band; the laptop joins the mesh through SSH port forwards via pi-sender, whose TCP proxy acknowledges data before it reaches the laptop (a real ground station on the mesh would see its own back-pressure); Jetson power only logged when it is priced.</li>
</ul>
'''


FAULTS = ('<tr><td>Sender thread toggled the socket timeout (<code>settimeout</code>) while the receiver thread read the same socket</td>'
          '<td>Receiver ended with EAGAIN; results lost until the next reconnect (no-price run: 1,692 of 6,418 laptop results); '
          'in the code since at least 8 Oct</td><td>Kernel send timeout (<code>SO_SNDTIMEO</code>) set once per connection; '
          'mesh campaign 2 restarted from scratch</td></tr>\n'
          '<tr><td>Laptop Ethernet (Realtek) dropped sparse packets: Energy-Efficient Ethernet / power saving</td>'
          '<td>100 % ping loss at 1/s; SSH tunnel dropped, laptop path stalled (5 mesh runs re-run)</td>'
          '<td>Keep-awake ping on the cable (20/s); runs checked against a 1-s ping log and discarded on loss; '
          'disabling EEE in Windows is the proper fix</td></tr>\n')
STATE_LI = ('<li><b>Mesh campaign 2 (18.9, done 24 Oct, 66 + 16 runs):</b> on the real mesh the prices buy the same accuracy '
            'for far less heat (no prices: same sAP, +1.5 W, +14 °C, throttled 39 %); the Pi energy price beats the heat '
            'price (same sAP, 0.46 W and 4.8 °C cooler); the Jetson energy price as set (0.5 W) costs 0.016 sAP '
            'and saves only 0–10 % of the Jetson\'s power; '
            'fixed offloading collapses when its link fails; with a relay-only route the hierarchical chain is ahead '
            '(0.151 against 0.137). A camera-side fault that lost results on live links was found and fixed (Part 21); '
            'it hit 16 of the 824 runs made before the fix (2 %) and changes no earlier verdict.</li>\n')
LEFT_ROWS = ('<tr><td><s>Size of the receiver fault in the earlier campaigns</s> <b>Done 24 Oct</b>: 20 of 906 runs (2 %), no '
             'verdict changes, no re-run needed (18.9)</td><td>—</td><td>—</td></tr>\n'
             '<tr><td>Jetson energy price with a budget near its unpriced draw (about 1.0–1.4 W), Jetson power now logged in every '
             'strategy; push the new <code>adaptive2.py</code> to the camera first</td><td>Mesh</td><td>about 3 h</td></tr>\n')


def main():
    h, m = HTML.read_text(), MD.read_text()
    sec = section()
    # 18.9 before PART 19 (replace an earlier 18.9)
    j = h.index('<h2 id="rescore">')
    i = h.find("<h3>18.9 ")
    h = h[:i if 0 <= i < j else j] + sec + h[j:]
    j = m.index("## PART 19")
    i = m.find("### 18.9 ")
    m = m[:i if 0 <= i < j else j] + html_to_md(sec) + m[j:]
    # Part 21 faults
    if "SO_SNDTIMEO" not in h.split('<h2 id="bugs">')[1].split("</table>")[0]:
        b = h.index('<h2 id="bugs">')
        e = h.index("</table></div>", b)
        h = h[:e] + FAULTS + h[e:]
        k = m.index("| netem 'change' kept")
        k = m.index("\n", k) + 1
        m = m[:k] + "\n".join(html_to_md('<div class="tbl"><table><tr><th>a</th><th>b</th><th>c</th></tr>' + FAULTS
                                         + "</table></div>").strip().split("\n")[2:4]) + "\n" + m[k:]
    # state box: mesh campaign 2 bullet first
    h = re.sub(r"<li><b>Mesh campaign 2 \(18\.9.*?</li>\n", "", h)
    m = re.sub(r"^- \*\*Mesh campaign 2 \(18\.9.*\n", "", m, flags=re.M)
    if "Mesh campaign 2 (18.9" not in h:
        k = h.index('<div class="box state">')
        k = h.index("<ul>\n", k) + 5
        h = h[:k] + STATE_LI + h[k:]
        k = m.index("**State on 2")
        k = m.index("\n- ", k) + 1
        m = m[:k] + html_to_md("<ul>\n" + STATE_LI + "</ul>").strip() + "\n" + m[k:]
    h = h.replace("<b class=\"h\">State on 22 Oct 2026, 23:00 (checkpoint): VisDrone detectors, onboard study, relay campaign and standard-metric rescoring done; VisDrone replay of the earlier campaigns waiting</b>",
                  "<b class=\"h\">State on 24 Oct 2026, 21:00: VisDrone detectors, onboard study, relay campaign, standard-metric rescoring and both mesh campaigns done; VisDrone replay of the earlier campaigns waiting</b>")
    m = m.replace("**State on 22 Oct 2026, 23:00 (checkpoint): VisDrone detectors, onboard study, relay campaign and standard-metric rescoring done; VisDrone replay of the earlier campaigns waiting**",
                  "**State on 24 Oct 2026, 21:00: VisDrone detectors, onboard study, relay campaign, standard-metric rescoring and both mesh campaigns done; VisDrone replay of the earlier campaigns waiting**")
    # What is left: the chain row is done; two new rows
    old = re.search(r"<tr><td>Hierarchical chain on the mesh \(18\.6\):.*?</tr>\n", h)
    if old:
        h = h.replace(old.group(0), '<tr><td><s>Hierarchical chain on the mesh (18.6)</s> <b>Done 23–24 Oct</b> (18.8, 18.9)</td><td>—</td><td>—</td></tr>\n')
        mo = re.search(r"^\| Hierarchical chain on the mesh \(18\.6\):.*\n", m, flags=re.M)
        m = m.replace(mo.group(0), "\n".join(html_to_md('<div class="tbl"><table><tr><th>a</th><th>b</th><th>c</th></tr>'
                                                         + '<tr><td><s>Hierarchical chain on the mesh (18.6)</s> <b>Done 23–24 Oct</b> (18.8, 18.9)</td><td>—</td><td>—</td></tr>\n'
                                                         + "</table></div>").strip().split("\n")[2:3]) + "\n")
    # rows this script added on an earlier run: replace with the current LEFT_ROWS
    done_row = '<tr><td><s>Hierarchical chain on the mesh (18.6)</s> <b>Done 23–24 Oct</b> (18.8, 18.9)</td><td>—</td><td>—</td></tr>\n'
    h = re.sub(r"<tr><td>(<s>)?Size of the receiver fault.*?</tr>\n|<tr><td>Jetson energy price[^\n]*?</tr>\n", "", h)
    h = h.replace(done_row, done_row + LEFT_ROWS, 1)
    m = re.sub(r"^\| (<s>)?Size of the receiver fault.*\n|^\| Jetson energy price.*\n", "", m, flags=re.M)
    md_done = "| <s>Hierarchical chain on the mesh (18.6)</s> **Done 23–24 Oct** (18.8, 18.9) | — | — |\n"
    md_rows = "\n".join(html_to_md('<div class="tbl"><table><tr><th>a</th><th>b</th><th>c</th></tr>' + LEFT_ROWS
                                   + "</table></div>").strip().split("\n")[2:4]) + "\n"
    m = m.replace(md_done, md_done + md_rows, 1)
    h = re.sub(r'(<div class="meta">Full project report · state on )[^<]*', r"\g<1>24 Oct 2026, 21:00", h, 1)
    m = re.sub(r"^Full project report · state on .*$", "Full project report · state on 24 Oct 2026, 21:00", m, 1, flags=re.M)
    HTML.write_text(h)
    MD.write_text(m)
    print("report updated: 18.9, Part 21 (+2), state box, what is left")


if __name__ == "__main__":
    main()
