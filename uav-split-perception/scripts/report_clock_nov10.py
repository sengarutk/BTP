#!/usr/bin/env python3
"""Report update, 10 Nov 2026: 19.14 = does the camera Pi's clock speed matter, and would pinning it at the full
2.4 GHz (instead of letting the governor slow an idle CPU) help v4.1? Includes the "warm up with one onboard frame" idea.

Every number is read from experiments/results/hardware/clock_effect/clock_effect.json
(validation/hardware/clock_effect_analysis.py). Adds 19.14 after 19.13 and a Part 1 bullet. Run after
report_overload_nov10.py. Idempotent.
usage: report_clock_nov10.py   (originals archived in experiments/results/hardware/_superseded/report_before_clock_nov10/)
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_parts_oct22 import HTML, MD, html_to_md, table  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
J = ROOT / "experiments" / "results" / "hardware" / "clock_effect" / "clock_effect.json"
ORDER = [("v41", "v4.1"), ("v41e", "v4.1 + Jetson energy price"), ("v41e12", "v4.1 + Jetson price, 1.2 W"),
         ("heat", "heat price"), ("heate", "heat + Jetson price"), ("hier", "hierarchical chain"),
         ("fixlap", "fixed laptop offload"), ("aoithr", "freshness threshold"), ("noprice", "no prices")]
CLS = [("full", "2.4 GHz (full)", "var(--c-hier)"), ("governor", "slowed by the governor (idle)", "var(--c-fixed)"),
       ("throttled", "throttled (too hot)", "var(--c-heat)")]


def pct(x):
    return f"{100 * x:.0f} %"


def chart(d):
    sh = d["clock_share_by_strategy"]
    rows = [(k, n) for k, n in ORDER if k in sh]
    o = [f'<figure class="chart"><svg viewBox="0 0 640 {60 + 24 * len(rows)}" width="100%" role="img" '
         'aria-label="Share of clock samples at full clock, slowed by the governor and throttled, per strategy" '
         'xmlns="http://www.w3.org/2000/svg">']
    x0, w = 200, 420
    for i, (k, n) in enumerate(rows):
        y = 14 + 24 * i
        o.append(f'<text class="ink" x="{x0 - 8}" y="{y + 13}" text-anchor="end">{n}</text>')
        x = x0
        for c, _, col in CLS:
            v = sh[k].get(c, 0.0)
            if v > 0:
                o.append(f'<rect x="{x:.1f}" y="{y}" width="{v * w:.1f}" height="17" fill="{col}">'
                         f'<title>{n}: {pct(v)} {c}</title></rect>')
                if v >= 0.08:
                    o.append(f'<text x="{x + v * w / 2:.1f}" y="{y + 13}" text-anchor="middle" fill="#fff">{pct(v)}</text>')
            x += v * w
    yl = 26 + 24 * len(rows)
    for i, (_, lab, col) in enumerate(CLS):
        xx = x0 + 140 * i
        o.append(f'<rect x="{xx}" y="{yl}" width="10" height="10" fill="{col}"/><text class="ink" x="{xx + 15}" '
                 f'y="{yl + 9}">{lab}</text>')
    o.append('</svg><figcaption>Share of the camera Pi\'s clock samples (about one per second) in each state, all 96 mesh '
             'runs of campaigns 1–3. Data: <code>experiments/results/hardware/clock_effect/clock_effect.json</code>.'
             '</figcaption></figure>\n')
    return "".join(o)


def section():
    d = json.load(open(J))
    sh, L, P, T = d["clock_share_by_strategy"], d["latency_ms_by_scenario_server_class"], d["power_w_by_strategy_class"], \
        d["temp_c_by_class"]
    b, ae = d["bench"], d["accuracy_estimate"]
    v, npz = sh["v41"], sh["noprice"]
    rows = []
    for sc, scn in (("static_good", "good links"), ("mesh_mission", "mission"), ("multihop", "relayed (multihop)")):
        for srv, sn in (("laptop", "laptop"), ("jetson", "Jetson"), ("onboard", "onboard")):
            c = [L.get(f"{sc}|{srv}|{k}") for k, _, _ in CLS]
            if not any(c):
                continue
            rows.append([sc and f"{scn}" if srv == "laptop" else "", sn] +
                        [f"{x['median']:.0f} ms ({x['n']:,})" if x else "—" for x in c])
    t_lat = table(["Scenario", "frames processed by", "median latency at full clock (frames)", "slowed by the governor",
                   "throttled"], rows)
    t_pw = table(["Strategy", "Pi power at full clock", "slowed by the governor", "throttled"],
                 [[n] + [f"{P[f'{k}|{c}']['mean']:.2f} W" if f"{k}|{c}" in P else "—" for c, _, _ in CLS]
                  for k, n in ORDER if f"{k}|full" in P])
    bf, bt = b["full_clock"], b["throttled"]
    t_b = table(["Pi 5 benchmark (4 threads)", "YOLOv8s per frame", "JPEG q90 encode", "inference energy per frame",
                 "clock at the end"],
                [["cool start", f"{bf['yolov8s_ms']:.0f} ms", f"{bf['jpeg_q90_enc_ms']:.1f} ms", f"{bf['energy_per_frame_j']:.1f} J",
                  "not recorded"],
                 ["sustained, throttled", f"{bt['yolov8s_ms']:.0f} ms (+{100 * (bt['yolov8s_ms'] / bf['yolov8s_ms'] - 1):.0f} %)",
                  f"{bt['jpeg_q90_enc_ms']:.1f} ms", f"{bt['energy_per_frame_j']:.1f} J "
                  f"(+{100 * (bt['energy_per_frame_j'] / bf['energy_per_frame_j'] - 1):.0f} %)",
                  f"{bt['end_state']['arm_clock_hz'] / 1e9:.1f} GHz, flags {bt['end_state']['throttled']}"]])
    lg = L["static_good|laptop|governor"]["median"] - L["static_good|laptop|full"]["median"]
    ot = d["v41_on_time_share"]
    scs = ("static_good", "mesh_mission", "multihop")
    on = [100 * (L[f"{s}|onboard|throttled"]["median"] / L[f"{s}|onboard|full"]["median"] - 1) for s in scs]
    jg = [L[f"{s}|jetson|governor"]["median"] - L[f"{s}|jetson|full"]["median"] for s in scs]
    onr, jgr = f"{min(on):.0f}–{max(on):.0f} %", f"{min(jg):.0f}–{max(jg):.0f} ms"
    return f'''<h3>19.14 Clock speed: does the camera Pi need to run at its full 2.4 GHz? (10 Nov 2026, laptop only)</h3>
<p>Question: the clock-against-temperature graph of 18.11 shows many samples below the Pi's full clock. Does that cost
latency, accuracy, speed or energy, and should every board on the mesh be kept at full capability, for example by
letting the Pi process one frame onboard first so that it reaches its full clock before v4.1 takes over? No new runs:
every mesh run (campaigns 1–3, {d['runs']} runs) logs the Pi's clock and throttle flags about once a second, its power
and temperature four times a second, and every frame's latency
(<code>validation/hardware/clock_effect_analysis.py</code>, results
<code>experiments/results/hardware/clock_effect/clock_effect.json</code>). Each sample and frame is put in one of three
classes by the nearest clock sample: full clock; below full but not throttled (the frequency governor slowing an idle
CPU); and throttled (a current throttle flag, above about 80 °C).</p>
{chart(d)}<ul>
<li><b>Two different kinds of low clock.</b> With v4.1 the Pi is at full clock {pct(v.get('full', 0))} of the time and
slowed by the governor {pct(v.get('governor', 0))}, never throttled ({pct(v.get('throttled', 0))}): it mostly offloads, so
its CPU is often idle and the governor lowers the clock. That is harmless. Throttling is the harmful kind: without prices
the Pi is throttled {pct(npz.get('throttled', 0))} of the time. Mean temperature: {T['full']['mean']:.0f} °C at full clock,
{T['governor']['mean']:.0f} °C when slowed by the governor, {T['throttled']['mean']:.0f} °C when throttled.</li>
</ul>
{t_lat}<ul>
<li><b>Slowed by the governor:</b> frames sent to the laptop take {lg:.0f} ms longer in the median (good links), frames
sent to the Jetson {jgr}, and <b>onboard inference takes no longer at all</b>, because the governor raises the clock to full
within milliseconds once inference starts.</li>
<li><b>Throttled:</b> onboard inference takes {onr} longer on the mesh, as in the benchmark below (+{100 * (bt['yolov8s_ms'] / bf['yolov8s_ms'] - 1):.0f} %
per frame and +{100 * (bt['energy_per_frame_j'] / bf['energy_per_frame_j'] - 1):.0f} % energy per frame). This is the clock effect that
matters, and v4.1's energy price prevents it.</li>
<li><b>Accuracy does not depend on the clock:</b> the same model gives the same detections at any speed; only timing,
and so staleness, changes.</li>
<li><b>The {lg:.0f} ms is an upper bound on the clock's own effect.</b> The CPU idles exactly when there is less to do,
which is also when links are slow, so latency differences between classes are partly coincidence (for example the
relayed path's large gap is mostly the link). And the benchmark shows JPEG encoding itself taking about the same time
when throttled to {bt['end_state']['arm_clock_hz'] / 1e9:.1f} GHz ({bt['jpeg_q90_enc_ms']:.1f} ms) as at a cool start
({bf['jpeg_q90_enc_ms']:.1f} ms).</li>
</ul>
{t_b}<p><b>Power.</b> Power is lower when the governor slows the clock, but mostly because the Pi is doing less in those
moments (same caveat). What a fixed full clock costs while idle was not measured.</p>
{t_pw}<p><b>Would pinning the clock at 2.4 GHz help v4.1?</b> A little, and not measurably.</p>
<ul>
<li><b>Latency:</b> at most about {lg:.0f} ms less on laptop-served frames ({pct(ae['v41_laptop_share'])} of v4.1's frames),
{jgr} on Jetson-served frames, nothing onboard.</li>
<li><b>On-time results:</b> no change. v4.1 already delivers {pct(ot['static_good'])} of its results within the 300 ms
deadline on good links, {pct(ot['mesh_mission'])} in the mission and {pct(ot['multihop'])} relayed.</li>
<li><b>Accuracy:</b> with the forecaster each frame of staleness costs {100 * ae['decay_loss_per_ms'] * 1000 / 30:.1f} % of
accuracy (measured decay curve), so the gain is at most {100 * ae['relative_sap_gain_upper']:.1f} % relative, about
+{ae['absolute_sap_gain_upper']:.4f} sAP, assuming the whole gap is the clock's doing. The paired campaigns resolve
differences of about ±0.005, so no campaign could detect it.</li>
<li><b>Cost:</b> a CPU that never slows down idles at higher power and runs warmer, closer to the 80 °C point where
throttling starts, which is the effect that does cost speed and energy; v4.1's power budget would then allow less
onboard work.</li>
<li><b>The warm-up idea</b> (process one frame onboard first, then hand over to v4.1) would not hold: the governor
re-decides the clock every few tens of milliseconds from the current load, so the clock falls back as soon as the CPU
idles, which with v4.1 happens between most frames. Pinning the clock needs the governor set to "performance".</li>
<li><b>The other boards are already at full capability:</b> the Jetson's clocks are locked at its highest (15 W) mode
by <code>jetson_clocks</code> before every run (<code>tools/arun_mesh.sh</code>), the laptop's GPU is far from busy, and
the relay Pi only forwards packets.</li>
</ul>
<p><b>Verdict.</b> Keep the default governor. The clock problem worth solving is overheating, and v4.1 already solves it
(never throttled, against {pct(npz.get('throttled', 0))} without prices). Optional board test if the session has time:
v4.1 with the governor set to "performance" against the default, 2 scenarios × 3 runs (about 1 h), measuring latency,
sAP, power and temperature; expected: a few ms less latency, the same accuracy, more power and heat.</p>
'''


def state(d):
    v, npz, ae = d["clock_share_by_strategy"]["v41"], d["clock_share_by_strategy"]["noprice"], d["accuracy_estimate"]
    L = d["latency_ms_by_scenario_server_class"]
    on = [100 * (L[f"{s}|onboard|throttled"]["median"] / L[f"{s}|onboard|full"]["median"] - 1)
          for s in ("static_good", "mesh_mission", "multihop")]
    return (f"<li><b>Clock speed (19.14, 10 Nov):</b> the Pi's clock is often below 2.4 GHz with v4.1 "
            f"({pct(v.get('governor', 0))} of the time) only because the governor slows an idle CPU, which is harmless; "
            f"pinning it at full clock would save at most about {ae['laptop_latency_gap_ms']:.0f} ms on offloaded frames, "
            f"about +{ae['absolute_sap_gain_upper']:.4f} sAP at most, while throttling ({min(on):.0f}–{max(on):.0f} % slower onboard inference) "
            f"is the effect that matters, and v4.1 prevents it (0 % against {pct(npz.get('throttled', 0))} without prices)."
            "</li>\n")


def main():
    d = json.load(open(J))
    h, m = HTML.read_text(), MD.read_text()
    sec = section()
    j = h.index('<h2 id="argument">')
    assert 0 <= h.find("<h3>19.13 ") < j, "run report_overload_nov10.py first"
    i = h.find("<h3>19.14 ")
    h = h[:i if 0 <= i < j else j] + sec + h[j:]
    j = m.index("## PART 20")
    i = m.find("### 19.14 ")
    m = m[:i if 0 <= i < j else j] + html_to_md(sec) + m[j:]
    st_ = state(d)
    h = re.sub(r"<li><b>Clock speed \(19\.14.*?</li>\n", "", h, flags=re.S)
    k = h.index('<div class="box state">')
    k = h.index("<ul>\n", k) + len("<ul>\n")
    h = h[:k] + st_ + h[k:]
    m = re.sub(r"^- \*\*Clock speed \(19\.14.*\n", "", m, flags=re.M)
    k = m.index("**State on 26 Oct 2026")
    k = m.index("\n- ", k) + 1
    m = m[:k] + html_to_md("<ul>" + st_ + "</ul>").strip() + "\n" + m[k:]
    HTML.write_text(h)
    MD.write_text(m)
    print("report updated: 19.14 clock speed, Part 1 bullet")


if __name__ == "__main__":
    main()
