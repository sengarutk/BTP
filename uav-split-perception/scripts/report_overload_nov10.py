#!/usr/bin/env python3
"""Report update, 10 Nov 2026: 19.13 = overload, when cameras offer the edge computer more frames than it can process
(two or more Pis on one Jetson, or a Pi faster than the Jetson), on the Wi-Fi and on the mesh, direct and relayed.

Every number is read from experiments/results/hardware/overload_model/overload_summary.json
(validation/hardware/overload_model.py), vid_campaign_mesh2_summary.json and swarm_duo_summary.json. Adds 19.13 after
19.12 and a Part 1 bullet. Run after report_part5_oct30.py. Idempotent.
usage: report_overload_nov10.py   (originals archived in experiments/results/hardware/_superseded/report_before_overload_nov10/)
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_parts_oct22 import HTML, MD, html_to_md, table  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
HW = ROOT / "experiments" / "results" / "hardware"
NAMES = {"wifi_jetson": "Wi-Fi (access point), Pi → Jetson", "mesh_jetson": "Mesh, one hop, Pi → Jetson",
         "mesh_relayed": "Mesh, relayed, Pi → Jetson → laptop"}
COL = {"wifi_jetson": "var(--c-heat)", "mesh_jetson": "var(--c-hier)", "mesh_relayed": "var(--c-fixed)"}


def load():
    d = json.load(open(HW / "overload_model" / "overload_summary.json"))
    m2 = json.load(open(HW / "vid_campaign_mesh2_summary.json"))["cells"]
    duo = json.load(open(HW / "swarm_duo_summary.json"))["cells"]
    return d, m2, duo


def g(d, case, n, mode, fps=30):
    return d["grid"][f"{case}|{n}|{fps}|{mode}"]


def sec_s(ms):
    return f"{ms / 1000:.0f} s" if ms >= 1000 else f"{ms:.0f} ms"


def chart(d):
    pis = sorted({int(k.split("|")[1]) for k in d["grid"]})
    ymax = max(v["on_time_fps"] for v in d["grid"].values())
    ytop = 5 * (int(ymax / 5) + 1)
    X = lambda n: 64 + (n - pis[0]) / (pis[-1] - pis[0]) * 520  # noqa: E731
    Y = lambda v: 260 - v / ytop * 236  # noqa: E731
    o = ['<figure class="chart"><svg viewBox="0 0 640 370" width="100%" role="img" aria-label="On-time results per '
         'second against the number of cameras sending 30 frames per second to one Jetson, for three links and two '
         'sending rules" xmlns="http://www.w3.org/2000/svg">']
    for t in range(0, ytop + 1, 5):
        o.append(f'<line class="ax" x1="64" x2="584" y1="{Y(t):.1f}" y2="{Y(t):.1f}"/>'
                 f'<text x="56" y="{Y(t) + 4:.1f}" text-anchor="end">{t}</text>')
    for n in pis:
        o.append(f'<line class="ax" x1="{X(n):.1f}" x2="{X(n):.1f}" y1="260" y2="264"/>'
                 f'<text x="{X(n):.1f}" y="278" text-anchor="middle">{n}</text>')
    o.append('<text x="324" y="298" text-anchor="middle">cameras sending 30 frames/s to one Jetson</text>'
             '<text x="14" y="142" text-anchor="middle" transform="rotate(-90 14 142)">on-time results/s (≤ 300 ms)</text>')
    for case in NAMES:
        for mode, dash in (("stopwait", ""), ("latest", ' stroke-dasharray="5 4"')):
            pts = " ".join(f"{X(n):.1f},{Y(g(d, case, n, mode)['on_time_fps']):.1f}" for n in pis)
            o.append(f'<polyline points="{pts}" fill="none" stroke="{COL[case]}" stroke-width="2"{dash}/>')
            for n in pis:
                o.append(f'<circle cx="{X(n):.1f}" cy="{Y(g(d, case, n, mode)["on_time_fps"]):.1f}" r="2.5" '
                         f'fill="{COL[case]}"/>')
    lg = [(COL[c], "", NAMES[c]) for c in NAMES] + [("var(--muted)", "", "solid: one frame in flight (our system)"),
                                                     ("var(--muted)", ' stroke-dasharray="5 4"', "dashed: latest frame wins")]
    for i, (c, dash, txt) in enumerate(lg):     # below the plot, two columns: links left, sending rules right
        xx, yy = (64, 322 + 15 * i) if i < 3 else (370, 322 + 15 * (i - 3))
        o.append(f'<line x1="{xx}" x2="{xx + 20}" y1="{yy - 4}" y2="{yy - 4}" stroke="{c}" stroke-width="2"{dash}/>'
                 f'<text class="ink" x="{xx + 26}" y="{yy}">{txt}</text>')
    o.append('</svg><figcaption>Model prediction from measured timings. A first-in-first-out queue delivers no on-time '
             'result in any overloaded cell and is left out. Data: '
             '<code>experiments/results/hardware/overload_model/overload_summary.json</code>.</figcaption></figure>\n')
    return "".join(o)


def section():
    d, m2, duo = load()
    inp, cal, cap, srv = d["inputs"], d["inputs"]["calibration_targets"], d["max_cameras_at_30fps_95pct_on_time"], \
        d["bottleneck_capacity_fps"]
    cs = inp["cases"]
    st = {c: dict((s[0], s[1]) for s in cs[c]["stages"]) for c in cs}
    mj, mr = cs["mesh_jetson"]["link"], cs["mesh_relayed"]["link"]
    t_in = table(["Link", "time on air per Q90 frame", "server time per frame", "limit of the path (frames/s)",
                  "bottleneck", "source"],
                 [[NAMES["wifi_jetson"], f"{st['wifi_jetson']['wifi_air']:.1f} ms", f"{st['wifi_jetson']['jetson_server']:.1f} ms",
                   f"{srv['wifi_jetson']:.0f}", "the radio", "placements.csv (measured stages)"],
                  [NAMES["mesh_jetson"], f"{st['mesh_jetson']['mesh_air']:.1f} ms ({mj['goodput_mbps_median']:.0f} Mbit/s, "
                   f"{mj['bytes_median'] / 1e3:.0f} kB)", f"{st['mesh_jetson']['jetson_server']:.1f} ms", f"{srv['mesh_jetson']:.0f}",
                   "the Jetson's GPU", f"mesh campaign 2, {mj['n_goodput_samples']:,} goodput samples"],
                  [NAMES["mesh_relayed"], f"{st['mesh_relayed']['mesh_air_two_hops']:.1f} ms ({mr['goodput_mbps_median']:.1f} Mbit/s, "
                   f"{mr['bytes_median'] / 1e3:.0f} kB)", f"{st['mesh_relayed']['laptop_server']:.1f} ms (laptop)",
                   f"{srv['mesh_relayed']:.0f}", "the shared channel, both hops", f"mesh campaign 2, {mr['n_goodput_samples']:,} samples"]])
    w1, mj1, mr1 = g(d, "wifi_jetson", 1, "stopwait"), g(d, "mesh_jetson", 1, "stopwait"), g(d, "mesh_relayed", 1, "stopwait")
    t_cal = table(["One camera, one frame in flight", "model", "measured on the boards", "verdict"],
                  [[NAMES["wifi_jetson"], f"{w1['fps']:.1f} frames/s, median {w1['lat_p50_ms']:.0f} ms",
                    f"{cal['wifi_jetson_live_fps']:.1f} frames/s, median {cal['wifi_jetson_live_lat_p50_ms']:.0f} ms "
                    "(live placement runs)", "right in direction and size, not exact"],
                   [NAMES["mesh_jetson"], f"median {mj1['lat_p50_ms']:.0f} ms",
                    f"median {cal['mesh_jetson_live_lat_p50_ms']:.0f} ms ({cal['mesh_jetson_live_frames']:,} Jetson-served frames)",
                    "close"],
                   [NAMES["mesh_relayed"], f"{100 * mr1['on_time_share']:.0f} % on time, median {mr1['lat_p50_ms']:.0f} ms",
                    f"<b>{100 * cal['mesh_relayed_fixed_live_on_time_share']:.1f} % on time</b>, median "
                    f"{cal['mesh_relayed_fixed_live_lat_p50_ms']:.0f} ms (fixed offload to the laptop, "
                    f"{cal['mesh_relayed_fixed_runs']} runs)", "<b>model far too optimistic: trust the boards</b>"]])
    rows = []
    for case in NAMES:
        for n in (1, 2, 4, 6, 8, 10):
            a, b, c = (g(d, case, n, m) for m in ("fifo", "stopwait", "latest"))
            rows.append([NAMES[case] if n == 1 else "", n,
                         f"{a['on_time_fps']:.1f} of {a['fps']:.1f} · {sec_s(a['lat_p50_ms'])} · "
                         f"{a['server_work_late_pct']:.0f} % wasted",
                         f"{b['on_time_fps']:.1f} of {b['fps']:.1f} · {sec_s(b['lat_p50_ms'])} / {sec_s(b['lat_p95_ms'])}",
                         f"{c['on_time_fps']:.1f} of {c['fps']:.1f} · {sec_s(c['lat_p50_ms'])}"])
    rows.append(["<i>The relayed rows are the model's; it is far too optimistic there (see the check above).</i>",
                 "", "", "", ""])
    t_grid = table(["Link", "cameras at 30 frames/s", "naive queue: on time of total · median latency · server work "
                    "wasted on late results", "one frame in flight (ours): on time of total · median / 95th-percentile",
                    "latest frame wins: on time of total · median"], rows)
    t_cap = table(["Link", "naive queue", "one frame in flight (ours)", "latest frame wins (needs a coordinator at the radio)"],
                  [[NAMES[c], cap[f"{c}|fifo"],
                    f"{cap[f'{c}|stopwait']}" + (" in the model; <b>fails with 1 on the boards</b>" if c == "mesh_relayed" else ""),
                    f"{cap[f'{c}|latest']} or more" + (" (model only)" if c == "mesh_relayed" else "")] for c in NAMES])
    fx, v41, hier = m2["multihop|fixlap"], m2["multihop|v41"], m2["multihop|hier"]
    dc, dn, dfx, pa = duo["mission|duo_coord"], duo["mission|duo_none"], duo["mission|duo_fixed"], duo["mission|pi_alone"]
    w30, j30 = g(d, "wifi_jetson", 1, "fifo"), g(d, "mesh_jetson", 1, "fifo")
    return f'''<h3>19.13 Overload: more frames than the edge computer can take (10 Nov 2026, laptop only)</h3>
<p>Question: what happens when two or more Pis send to the same Jetson, or one Pi sends faster than the Jetson can
process, on the Wi-Fi and on the mesh (one hop, and relayed)? No new board runs: a queueing model is fed with timings
already measured (<code>validation/hardware/overload_model.py</code>, results
<code>experiments/results/hardware/overload_model/overload_summary.json</code>) and checked against the runs that exist.</p>
<ul>
<li><b>Model.</b> Every frame passes through shared stages in tandem: the radio channel into the edge computer (shared
by all cameras), then the server that runs the detector. Three sending rules: a <i>naive queue</i> (each camera sends
every frame at its camera rate into first-in-first-out queues); <i>one frame in flight</i> per camera (our system: the
camera sends its newest frame only when the previous result is back, and skips the rest); and <i>latest frame wins</i>
(a newer frame replaces a waiting older one, the rule <code>edge_node.py</code> already applies inside the Jetson).
Deadline 300 ms, 30 frames/s cameras, {d['assumptions']['seeds']} seeds of {d['assumptions']['run_ms'] / 1000:.0f} s.</li>
<li><b>Assumptions.</b> Server times vary by ±{100 * d['assumptions']['server_cv']:.0f} % (coefficient of variation);
the radio's spread is taken from the measured goodput samples; the radio is one shared first-come queue (collisions and
rate adaptation are not modelled, so real behaviour is probably somewhat worse); the returned detections (under 1 KB)
are ignored; the Jetson's heating under sustained load is not modelled.</li>
</ul>
{t_in}<p><b>Check against the boards.</b> One hop on Wi-Fi or the mesh: the model agrees with the measurements. Relayed
on the mesh it does not: the real boards are much worse, because the model leaves out contention between the two hops,
the mesh routing overhead and the Jetson's forwarding cost. For the relayed mesh, the measurements are the answer.</p>
{t_cal}<p><b>Results.</b></p>
{t_grid}{chart(d)}<p><b>How many cameras one Jetson can serve</b> (the largest number sending 30 frames/s that keeps at
least 95 % of results on time):</p>
{t_cap}<ul>
<li><b>Which part saturates first depends on the link.</b> Over the access-point Wi-Fi the radio fills first (about
{srv['wifi_jetson']:.0f} frames/s in total), before the Jetson's GPU (about {1000 / st['wifi_jetson']['jetson_server']:.0f}).
On the mesh's direct hop the radio is faster, so the GPU itself is the limit: one Pi sending 30 frames/s already
overloads the Nano. Relayed on the mesh, the shared channel carries both hops and limits everything to about
{srv['mesh_relayed']:.0f} frames/s.</li>
<li><b>A naive queue turns overload into zero useful output.</b> One Pi at 30 frames/s on Wi-Fi: {w30['fps']:.0f}
frames/s processed, <b>{w30['on_time_fps']:.0f} on time</b>, median latency {sec_s(w30['lat_p50_ms'])}, and
{w30['server_work_late_pct']:.1f} % of the Jetson's work spent on results that arrive too late. On the mesh's direct hop:
{j30['fps']:.0f} frames/s processed, {j30['on_time_fps']:.0f} on time, the GPU busy {100 * j30['server_busy_share']:.0f} % of
the time. Latency keeps growing for as long as the overload lasts, so the board runs at full power for nothing.</li>
<li><b>One frame in flight (our system) caps the load but not the waiting.</b> Each camera limits itself, but its frame
still waits behind the other cameras' frames, so from about {cap['wifi_jetson|stopwait'] + 1} cameras on Wi-Fi and
{cap['mesh_jetson|stopwait'] + 1} on the mesh's direct hop that wait alone breaks the deadline. On the relayed mesh the
model puts the limit at {cap['mesh_relayed|stopwait'] + 1} cameras, but the boards already miss most deadlines with one
(below).</li>
<li><b>Latest frame wins removes the problem in the model:</b> the path stays at its full rate, on time, with
{cap['wifi_jetson|latest']} cameras. At the radio this needs a coordinator that tells the cameras when to send (a frame
already handed to the radio cannot be replaced).</li>
</ul>
<p><b>What the boards already show.</b></p>
<ul>
<li><b>Relaying saturates with a single camera.</b> In mesh campaign 2's multihop scenario, fixed offload to the laptop
through the Jetson delivered only {100 * fx['p_aoi300'][0]:.1f} % of results on time ({fx['deadline_met_fps'][0]:.1f} per
second, median latency {fx['lat_median_ms'][0]:.0f} ms, {fx['n']} runs). Adding cameras can only make this worse.</li>
<li><b>Computing at the relay is the fix:</b> in the same scenario the hierarchical mode, where the Jetson runs the
detector instead of forwarding, scored {hier['sAP_fc'][0]:.3f} sAP against {v41['sAP_fc'][0]:.3f} for v4.1 and
{fx['sAP_fc'][0]:.3f} for fixed offload, with {100 * hier['p_aoi300'][0]:.1f} % of results on time.</li>
<li><b>Two cameras sharing a path</b> (the Pi and the Jetson's own camera, mission scenario): with fixed offload the Pi's
detections were available {100 * dfx['pi_availability'][0]:.0f} % of the time (information age
{dfx['pi_aoi_ms'][0] / 1000:.1f} s); with the adaptive controller {100 * dn['pi_availability'][0]:.0f} % without the
coordinator and {100 * dc['pi_availability'][0]:.0f} % with it (alone: {100 * pa['pi_availability'][0]:.0f} %). So with two
cameras the adaptivity avoids the overload, and the coordinator adds little; the model says coordination starts to matter
from about {cap['wifi_jetson|stopwait'] + 1}–{cap['mesh_jetson|stopwait'] + 1} cameras per Jetson.</li>
</ul>
<p><b>What it means.</b> A shared edge drone needs admission control: our one-frame-in-flight rule already prevents
the naive collapse and serves about {cap['wifi_jetson|stopwait']} cameras per Jetson over Wi-Fi and about
{cap['mesh_jetson|stopwait']} over one mesh hop; beyond that, or on a relay path, the edge drone must compute rather than
forward, and a coordinator that grants send slots (latest frame wins) is needed. The naive case, full power for no
on-time output, also supports the second paper's argument that an edge computer's work must be priced.
<b>Limits:</b> model results from measured timings, not overload measurements; the relayed case is reliable only where
measured; heat on the Jetson under sustained full load is not modelled. Two short board runs would confirm it directly
(one Pi at 30 frames/s with a naive queue, and two Pis on one Jetson), about 1 h in the planned board session.</p>
'''


STATE = ("<li><b>Overload (19.13, 10 Nov):</b> when cameras offer a Jetson more frames than it can process, a naive "
         "queue delivers no on-time result at full power; our one-frame-in-flight rule serves about 4 cameras per Jetson "
         "on Wi-Fi and 6 on one mesh hop (queueing model from measured timings), and a relayed mesh path already "
         "saturates with one camera (measured), so the edge drone must compute rather than forward.</li>\n")


def main():
    d, _, _ = load()
    cap = d["max_cameras_at_30fps_95pct_on_time"]
    state = STATE.replace("about 4 cameras", f"about {cap['wifi_jetson|stopwait']} cameras") \
                 .replace("and 6 on one", f"and {cap['mesh_jetson|stopwait']} on one")
    h, m = HTML.read_text(), MD.read_text()
    sec = section()
    j = h.index('<h2 id="argument">')
    i = h.find("<h3>19.13 ")
    assert h.find("<h3>19.12 ") < j
    nx = h.find("<h3>19.14 ")                    # a later section (report_clock_nov10.py) stays where it is
    e = nx if 0 <= i < nx < j else j
    h = h[:i if 0 <= i < j else e] + sec + h[e:]
    j = m.index("## PART 20")
    i = m.find("### 19.13 ")
    nx = m.find("### 19.14 ")
    e = nx if 0 <= i < nx < j else j
    m = m[:i if 0 <= i < j else e] + html_to_md(sec) + m[e:]
    h = re.sub(r"<li><b>Overload \(19\.13.*?</li>\n", "", h, flags=re.S)
    k = h.index('<div class="box state">')
    k = h.index("<ul>\n", k) + len("<ul>\n")
    h = h[:k] + state + h[k:]
    m = re.sub(r"^- \*\*Overload \(19\.13.*\n", "", m, flags=re.M)
    k = m.index("**State on 26 Oct 2026")
    k = m.index("\n- ", k) + 1
    m = m[:k] + html_to_md("<ul>" + state + "</ul>").strip() + "\n" + m[k:]
    HTML.write_text(h)
    MD.write_text(m)
    print("report updated: 19.13 overload, Part 1 bullet")


if __name__ == "__main__":
    main()
