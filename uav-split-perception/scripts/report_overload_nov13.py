#!/usr/bin/env python3
"""Results Brief 19.13 rewritten (13 Nov 2026): the simple question, the simple answer, then the results that support
it. Corrects the 10 Nov version, which called stop-and-wait ("one frame in flight") "our system": v4.1 sends its
newest frame once the previous one has LEFT THE RADIO (adaptive2.py), and the Jetson keeps only the newest waiting
frame (edge_node.py). Adds the ways to handle many Pis per Jetson and the many-Jetson case.
Every number is read from:
  experiments/results/hardware/overload_model_nov13/overload_summary.json   (overload_model.py, with v4.1's rule)
  experiments/results/hardware/overload_handling/summary.json               (overload_handling.py)
  experiments/results/hardware/overload_multi/summary.json                  (overload_multi.py)
Also replaces the Part 1 bullet on 19.13 and the Final Report's 4.13 overload paragraph. Idempotent; originals
archived in experiments/results/hardware/_superseded/report_before_overload_nov13/.
"""
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_parts_oct22 import HTML, MD, html_to_md, table  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "experiments" / "results" / "hardware"
FINAL = ROOT.parent / "AEGIS-UAV Final Report.html"
ARCH = R / "_superseded" / "report_before_overload_nov13"

om = json.load(open(R / "overload_model_nov13" / "overload_summary.json"))
oh = json.load(open(R / "overload_handling" / "summary.json"))["grid"]
mu = json.load(open(R / "overload_multi" / "summary.json"))["grid"]
g, cap, cal = om["grid"], om["max_cameras_at_30fps_95pct_on_time"], om["inputs"]["calibration_targets"]
caps = om["bottleneck_capacity_fps"]
CASES = (("wifi_jetson", "Wi-Fi (access point), Pi → Jetson"), ("mesh_jetson", "Mesh, one hop, Pi → Jetson"),
         ("mesh_relayed", "Mesh, relayed, Pi → Jetson → laptop"))


def c(case, n, fps, mode):
    return g[f"{case}|{n}|{fps}|{mode}"]


def ot(x):
    return f"{x['on_time_fps']:.1f} of {x['fps']:.1f}"


def h(case, n, m):
    x = oh[f"{case}|{n}|{m}"]
    return f"{x['on_time_fps_total']:.1f} / {x['on_time_fps_worst_cam']:.1f} / {x['aoi_mean_ms']:.0f}" \
        if x["aoi_mean_ms"] != float("inf") else f"{x['on_time_fps_total']:.1f} / {x['on_time_fps_worst_cam']:.1f} / –"


def mm(radio, m, n, s):
    x = mu[f"{radio}|{m}|{n}|{s}"]
    return f"{x['on_time_total']:.1f} / {x['on_time_worst']:.1f} / {x['aoi_mean_ms']:.0f}"


w1, m1 = c("wifi_jetson", 1, 30, "ackwait"), c("mesh_jetson", 1, 30, "ackwait")
w1s, m1s = c("wifi_jetson", 1, 30, "stopwait"), c("mesh_jetson", 1, 30, "stopwait")
wf = c("wifi_jetson", 1, 30, "fifo")

SEC = f'''<h3>19.13 Overload: more frames than the edge computer can take (10 Nov 2026; rewritten 13 Nov 2026, laptop only)</h3>
<p><b>The question.</b> What happens if a camera Pi sends frames faster, or if more Pis share one Jetson, and how should the system handle it?</p>
<p><b>The answer.</b> The Jetson can only serve so many frames per second: about {caps["wifi_jetson"]:.0f} over the Wi-Fi access point (the radio is the limit), {caps["mesh_jetson"]:.0f} over one mesh hop (the Jetson's GPU is the limit) and {caps["mesh_relayed"]:.0f} relayed through the Jetson (the shared channel is the limit). A faster camera or more Pis cannot raise that; they only decide how it is shared.</p>
<ul>
<li><b>A faster camera is safe with v4.1.</b> It never sends more than the path can carry, so latency stays flat; above the path's limit the extra frames are simply skipped.</li>
<li><b>More Pis are fine up to {cap["wifi_jetson|ackwait"]} per Jetson on Wi-Fi and {cap["mesh_jetson|ackwait"]} over a mesh hop.</b> Beyond that, v4.1 alone collapses: frames wait behind the other Pis' frames at the shared radio and arrive too late.</li>
<li><b>The fix is a coordinator on the Jetson that pulls the next frame ("pull one ahead").</b> It stays at full capacity with any number of Pis. With several Jetsons, give each its own radio channel. On one shared channel, more than two Jetsons add nothing.</li>
<li><b>Why it matters for the main topic (paper 2).</b> v4.1 keeps a Pi cool by offloading whenever a server can answer on time. An overloaded Jetson stops answering on time, so every Pi falls back to onboard detection and heats up. The coordinator protects the condition the heat solution relies on. This last step is reasoned, not yet measured.</li>
</ul>
<p><b>How it was answered.</b> No new board runs. A queueing model (<code>validation/hardware/overload_model.py</code>) is fed with measured timings: radio time per frame and server time, with their measured spreads (placements.csv; mesh campaign 2, {om["inputs"]["cases"]["mesh_jetson"]["link"]["n_goodput_samples"]:,} goodput samples). Settings: cameras at 30 frames/s, deadline 300 ms, 5 seeds of 120 s. The model assumes one shared radio with no collisions, so real behaviour is probably somewhat worse; it ignores the small returned results and the Jetson's heating. Four sending rules:</p>
''' + table(["Rule", "What the camera does"], [
    ["Naive queue", "Sends every frame, 30 per second, into first-come queues"],
    ["Stop-and-wait", "Sends its newest frame only when its previous <i>result</i> is back"],
    ["<b>v4.1's rule</b>", "Sends its newest frame once its previous frame has <i>left the radio</i>; at the Jetson a newer frame of the same Pi replaces its waiting one (<code>adaptive2.py</code>, <code>edge_node.py</code>)"],
    ["Latest frame wins", "Each Pi has only its newest frame waiting anywhere, also at the radio; at the radio this needs a coordinator"]]) + f'''<p><b>Correction (13 Nov).</b> The 10 Nov version called stop-and-wait "our system". It is not: v4.1 sends once the bytes have left the radio. With one Pi, v4.1 is better than stated then. With many Pis it reaches one fewer Pi per Jetson. Every number below uses v4.1's actual rule (<code>overload_model_nov13/</code>; the three original rules reproduce the 10 Nov numbers exactly, all 216 cells).</p>
<p><b>Check against the boards.</b> One hop: v4.1's rule gives a median of {m1["lat_p50_ms"]:.0f} ms on the mesh. The boards measured {cal["mesh_jetson_live_lat_p50_ms"]:.0f} ms over {cal["mesh_jetson_live_frames"]:,} Jetson-served frames; stop-and-wait gives {m1s["lat_p50_ms"]:.0f} ms, so v4.1's rule is the better fit. Relayed: the model gives 100 % on time with one Pi, but the boards measured {100 * cal["mesh_relayed_fixed_live_on_time_share"]:.1f} % (median {cal["mesh_relayed_fixed_live_lat_p50_ms"]:.0f} ms, {cal["mesh_relayed_fixed_runs"]} runs of fixed offloading through the Jetson). The model omits contention between the two hops, routing overhead and the Jetson's forwarding cost, so for relays the board measurements are the answer.</p>
<p><b>Result 1: one Pi, faster camera.</b> On-time results per second of results delivered, and the median latency:</p>
''' + table(["Camera rate", "Wi-Fi, v4.1", "Mesh hop, v4.1", "Wi-Fi, naive queue"],
            [[f"{fps} frames/s", f"{ot(c('wifi_jetson', 1, fps, 'ackwait'))}, {c('wifi_jetson', 1, fps, 'ackwait')['lat_p50_ms']:.0f} ms",
              f"{ot(c('mesh_jetson', 1, fps, 'ackwait'))}, {c('mesh_jetson', 1, fps, 'ackwait')['lat_p50_ms']:.0f} ms",
              f"{ot(c('wifi_jetson', 1, fps, 'fifo'))}, {c('wifi_jetson', 1, fps, 'fifo')['lat_p50_ms']:.0f} ms"] for fps in (10, 15, 30)]) + f'''<ul>
<li><b>v4.1 never overloads the Jetson, at any camera rate:</b> latency stays flat and every result is on time. The gain stops at the path's limit: going from 15 to 30 frames/s adds {c("wifi_jetson", 1, 30, "ackwait")["on_time_fps"] - c("wifi_jetson", 1, 15, "ackwait")["on_time_fps"]:.1f} results/s on Wi-Fi.</li>
<li><b>On Wi-Fi v4.1 reaches {w1["on_time_fps"]:.1f} of the radio's {caps["wifi_jetson"]:.0f}/s.</b> The radio idles while v4.1 waits for the next camera tick and encodes. Keeping the newest frame encoded and ready ("encode ahead") would close most of the gap: latest frame wins reaches {c("wifi_jetson", 1, 30, "latest")["on_time_fps"]:.1f}.</li>
<li><b>A naive queue at 30 frames/s collapses:</b> {wf["on_time_fps"]:.0f} on time, a median latency of {wf["lat_p50_ms"] / 1000:.0f} s, and {wf["server_work_late_pct"]:.0f} % of the Jetson's work spent on results that are already late.</li>
</ul>
<p><b>Result 2: more Pis per Jetson</b> (each at 30 frames/s). On-time results of results delivered, per second, in total:</p>
''' + table(["Path", "Pis", "v4.1", "Stop-and-wait", "Latest frame wins (coordinator)"],
            [[name if n == 1 else "", str(n), ot(c(case, n, 30, "ackwait")), ot(c(case, n, 30, "stopwait")),
              ot(c(case, n, 30, "latest"))] for case, name in CASES for n in (1, 2, 4, 6, 10)]) + \
    '<p>Largest number of Pis a Jetson can serve with at least 95 % of results on time:</p>\n' + \
    table(["Path", "v4.1", "Stop-and-wait", "Latest frame wins", "Naive"],
          [[name, str(cap[f"{case}|ackwait"]), str(cap[f"{case}|stopwait"]), f'{cap[f"{case}|latest"]} or more',
            str(cap[f"{case}|fifo"])] for case, name in CASES]) + f'''<ul>
<li><b>The Pis share a fixed capacity.</b> Two Pis on Wi-Fi get about {c("wifi_jetson", 2, 30, "ackwait")["on_time_fps"] / 2:.1f} on-time results/s each instead of {w1["on_time_fps"]:.1f}.</li>
<li><b>v4.1 collapses past about {cap["wifi_jetson|ackwait"] + 1} Pis on Wi-Fi and {cap["mesh_jetson|ackwait"] + 1} on a mesh hop.</b> Each Pi keeps one frame at the radio, so a frame waits behind all the other Pis' frames, and once that wait passes 300 ms almost nothing is on time.</li>
<li><b>A lower camera rate barely helps,</b> because the limit is the shared capacity. At 10 frames/s, {100 * c("wifi_jetson", 6, 10, "ackwait")["on_time_share"]:.0f} % of results are on time with 6 Pis on Wi-Fi and {100 * c("mesh_jetson", 8, 10, "ackwait")["on_time_share"]:.0f} % with 8 on the mesh.</li>
</ul>
<p><b>Result 3: ways to handle many Pis on one Jetson</b> (<code>validation/hardware/overload_handling.py</code>, same inputs). Each cell: total on-time results per second / the worst-served Pi / the mean age of each Pi's newest detection in ms (its age of information).</p>
''' + table(["Method", "Wi-Fi, 4 Pis", "Wi-Fi, 10 Pis", "Mesh hop, 6 Pis", "Mesh hop, 10 Pis"],
            [[nm, h("wifi_jetson", 4, m), h("wifi_jetson", 10, m), h("mesh_jetson", 6, m), h("mesh_jetson", 10, m)]
             for m, nm in (("v41", "v4.1 today"), ("coord", "Coordinator: send turns, first come"),
                           ("pull1", "<b>Pull one ahead</b>: the Jetson asks for the next frame while one may be on its way"),
                           ("ratecap", "Fair-share rate limit (capacity / number of Pis)"),
                           ("dropold", "Jetson drops frames that can no longer be on time"),
                           ("twojet", "Two Jetsons, v4.1"), ("pull1x2", "Two Jetsons + pull one ahead"))]) + f'''<ul>
<li><b>Pull one ahead is the best single-Jetson method.</b> It stays near capacity for every number of Pis and gives the freshest detections on the mesh. A frame is granted only when the Jetson can take it, and one more may be on its way, so the radio and the GPU work in parallel and no queue builds.</li>
<li><b>Send turns at radio speed</b> fix Wi-Fi, where the radio is the limit, but not the mesh at 8-10 Pis: the turns outpace the GPU, so the queue moves to the Jetson.</li>
<li><b>A rate limit helps only a little.</b> Dropping late frames is useless where the radio is the limit (on Wi-Fi it makes things worse) and helps a little where the GPU is.</li>
<li><b>A second Jetson does nothing on Wi-Fi,</b> because the radio is the limit. It nearly doubles capacity on the mesh.</li>
<li>Giving the turn to the Pi with the oldest detection was the same as first come here, because all Pis are alike. It would matter if their links differed.</li>
<li>Three faults in the first version of this code were found and fixed before these results: the oldest-first rule kept choosing a Pi whose frame was already on its way; the first pull version let the radio and the GPU work only in turn; and "pull one ahead" was running as v4.1. The v4.1 and coordinator rows reproduce the overload model.</li>
</ul>
<p><b>Result 4: many Pis and several Jetsons</b> (<code>validation/hardware/overload_multi.py</code>, mesh-hop timings). Two radio settings: all drones on one shared channel (the testbed's mesh today), or each Jetson's group on its own channel. Same cells as Result 3.</p>
''' + table(["Radio", "Jetsons", "Pis", "v4.1, Pis fixed to Jetsons", "v4.1, each frame to the least-loaded Jetson", "Global pull one ahead"],
            [[r_ if (m, n) == (1, 8) else "", str(m), str(n), mm(r, m, n, "static"), mm(r, m, n, "jsq"), mm(r, m, n, "gpull")]
             for r, r_ in (("shared", "One shared channel"), ("clustered", "A channel per Jetson"))
             for m, n in ((1, 8), (2, 8), (2, 16), (4, 16))]) + f'''<ul>
<li><b>On one shared channel, Jetsons stop helping after two:</b> about {mu["shared|2|8|gpull"]["on_time_total"]:.0f} results/s with two, and the same with four (the channel's airtime).</li>
<li><b>With a channel per Jetson, capacity grows with each one:</b> about {mu["clustered|1|8|gpull"]["on_time_total"]:.0f}, {mu["clustered|2|8|gpull"]["on_time_total"]:.0f}, {mu["clustered|3|16|gpull"]["on_time_total"]:.0f} and {mu["clustered|4|16|gpull"]["on_time_total"]:.0f}/s for one to four Jetsons.</li>
<li><b>Sending each frame to the least-loaded Jetson, decided by the Pis, backfires under load</b>: with three Jetsons and 16 Pis it gives {mu["clustered|3|16|jsq"]["on_time_total"]:.1f}/s against {mu["clustered|3|16|static"]["on_time_total"]:.1f} with fixed assignment. All Pis rush to the same free Jetson. The Jetsons should pull; the Pis should not push.</li>
<li><b>Global pull one ahead never collapses</b> and keeps detections fresh. With four Jetsons on their own channels and 16 Pis: {mu["clustered|4|16|gpull"]["on_time_total"]:.0f} on-time results/s in total, about {mu["clustered|4|16|gpull"]["on_time_per_pi"]:.1f} per Pi.</li>
</ul>
<p><b>What the boards already show.</b></p>
<ul>
<li><b>Relaying saturates with one Pi.</b> In mesh campaign 2's multihop scenario, fixed offloading to the laptop through the Jetson delivered {100 * cal["mesh_relayed_fixed_live_on_time_share"]:.1f} % of results on time ({cal["mesh_relayed_fixed_live_on_time_fps"]:.1f}/s).</li>
<li><b>Computing at the relay is the fix.</b> The hierarchical mode, where the Jetson runs the detector instead of forwarding, scored 0.151 sAP against 0.137 for v4.1 and 0.067 for fixed offloading, with 100 % of results on time.</li>
<li><b>Two cameras sharing a path</b> (the Pi and the Jetson's own camera, mission scenario). The Pi's detections were available 19 % of the time with fixed offloading, 68 % with v4.1 alone and 70 % with the coordinator (76 % for the Pi alone). With two cameras, adaptivity avoids the overload; coordination starts to matter from about {cap["wifi_jetson|ackwait"] + 1}-{cap["mesh_jetson|ackwait"] + 1} Pis per Jetson.</li>
</ul>
<p><b>Inferences.</b></p>
<ul>
<li><b>Fix the bottleneck that exists.</b> Wi-Fi is limited by the radio: use a coordinator; a second Jetson does not help. A mesh hop is limited by the GPU: pull according to the GPU, or add a Jetson on its own channel. Relays are limited by the shared channel: compute at the relay.</li>
<li><b>Coordination does not create capacity; it decides how capacity is shared and prevents the collapse.</b> With 10 Pis on one Jetson, each gets about {oh["wifi_jetson|10|pull1"]["on_time_fps_total"] / 10:.1f} (Wi-Fi) or {oh["mesh_jetson|10|pull1"]["on_time_fps_total"] / 10:.1f} (mesh) on-time results per second.</li>
<li><b>The recommended design for a large swarm.</b> v4.1 on every Pi; a "pull one ahead" coordinator shared by the Jetsons; a radio channel per Jetson group; about {cap["mesh_jetson|ackwait"]} Pis per Jetson; compute at the relay. With our one camera Pi, v4.1 is not overloaded, and all of this matters only from about {cap["wifi_jetson|ackwait"] + 1} (Wi-Fi) or {cap["mesh_jetson|ackwait"] + 1} (mesh) Pis per Jetson.</li>
<li><b>How it ties to paper 2.</b> v4.1 keeps each Pi cool by offloading when a server can answer on time. Overload makes offloads late, so the Pis fall back onboard and heat up. Keeping the edge on time is what lets the per-Pi heat solution scale to a swarm. In paper 2 this is a supporting section and future work, not the main claim.</li>
</ul>
<p><b>Limits.</b> These are model results from measured timings, not overload measurements. The model assumes ideal turn-taking, no radio collisions and no interference between channels; real numbers will be lower, and relays much lower. It counts on-time results and their age, not streaming AP, and it does not model v4.1's own choice between servers, its prices, or the Jetsons' heating. The step "overload pushes the Pis onboard and heats them" is reasoned, not measured.</p>
<p><b>Board tests that would confirm it.</b></p>
<ul>
<li>One Pi at 30 frames/s with a naive queue against v4.1.</li>
<li>Two Pis on one Jetson, v4.1 against pull one ahead, logging each Pi's temperature and onboard share (about 1 h; needs the second Pi on the mesh).</li>
<li>For several Jetsons: two Jetsons on separate channels.</li>
</ul>
'''

STATE = (f"<li><b>Overload (19.13, rewritten 13 Nov):</b> one Jetson serves about {caps['wifi_jetson']:.0f} frames/s over Wi-Fi and "
         f"{caps['mesh_jetson']:.0f} over a mesh hop, however fast the cameras send. v4.1 never overloads it from one Pi. It handles up to "
         f"{cap['wifi_jetson|ackwait']} Pis per Jetson on Wi-Fi and {cap['mesh_jetson|ackwait']} on a mesh hop, then collapses; a "
         "\"pull one ahead\" coordinator on the Jetson keeps it at full capacity with any number of Pis. With several Jetsons, "
         "give each its own channel (on one shared channel more than two add nothing). Relays need computing at the relay. "
         "Model results; the 10 Nov version had mislabelled stop-and-wait as v4.1's rule.</li>\n")

FINAL_OLD_RE = re.compile(r"<p><b>Overload\.</b>.*?</p>\n", re.S)
FINAL_NEW = (f"<p><b>Overload.</b> A queueing model fed with measured stage times (<code>overload_model.py</code>; Results Brief 19.13, "
             f"rewritten 13 Nov) asks what happens when cameras offer the Jetson more frames than it can take. The Jetson's path "
             f"carries about {caps['wifi_jetson']:.0f} frames/s over the Wi-Fi access point (the radio is the limit), "
             f"{caps['mesh_jetson']:.0f} over one mesh hop (its GPU) and {caps['mesh_relayed']:.0f} relayed. A naive queue turns overload "
             f"into nothing: one Pi at 30 frames/s gets {wf['on_time_fps']:.0f} results on time, with a median latency of "
             f"{wf['lat_p50_ms'] / 1000:.0f} s. v4.1 sends its newest frame once the previous one has left the radio, so one Pi "
             f"never overloads the path: {w1['on_time_fps']:.1f} on-time results/s on Wi-Fi, {m1['on_time_fps']:.1f} on the mesh. Its "
             f"modelled {m1['lat_p50_ms']:.0f} ms median matches the boards' {cal['mesh_jetson_live_lat_p50_ms']:.0f} ms. It serves up to "
             f"{cap['wifi_jetson|ackwait']} Pis per Jetson on Wi-Fi and {cap['mesh_jetson|ackwait']} on a mesh hop, then collapses. A "
             "coordinator on the Jetson that pulls one frame ahead keeps it at full capacity with any number of Pis. With several "
             "Jetsons, capacity grows only if each has its own channel. The model is far too optimistic for relays: the boards "
             f"already fail with one Pi ({100 * cal['mesh_relayed_fixed_live_on_time_share']:.1f} % on time), and computing at the relay is "
             "the fix (the hierarchical mode, 100 % on time). (The 10 Nov version had called stop-and-wait v4.1's rule; corrected.)</p>\n")


def main():
    h_, m_ = HTML.read_text(), MD.read_text()
    if not (ARCH / HTML.name).exists():
        ARCH.mkdir(parents=True, exist_ok=True)
        for f in (HTML, MD, FINAL):
            shutil.copy2(f, ARCH / f.name)
    i, j = h_.index("<h3>19.13 "), h_.index("<h3>19.14 ")
    h_ = h_[:i] + SEC + h_[j:]
    i, j = m_.index("### 19.13 "), m_.index("### 19.14 ")
    m_ = m_[:i] + html_to_md(SEC) + m_[j:]
    h_ = re.sub(r"<li><b>Overload \(19\.13.*?</li>\n", STATE, h_, count=1, flags=re.S)
    m_ = re.sub(r"(?m)^- \*\*Overload \(19\.13.*\n", html_to_md("<ul>" + STATE + "</ul>").strip() + "\n", m_, count=1)
    HTML.write_text(h_)
    MD.write_text(m_)
    f = FINAL.read_text()
    assert len(FINAL_OLD_RE.findall(f)) == 1
    FINAL.write_text(FINAL_OLD_RE.sub(lambda _: FINAL_NEW, f, count=1))
    print("19.13 rewritten; Part 1 bullet and Final Report 4.13 updated")


if __name__ == "__main__":
    main()
