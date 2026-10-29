#!/usr/bin/env python3
"""Three report figures (inline SVG, report theme tokens): the hierarchical chain Pi -> Jetson -> laptop (each tier
deciding) against the Pi alone, from measured runs only.
  1. sAP vs time throttled - one dot per run: Part A onboard runs (VisDrone YOLOv8s/m/l, both Pis) and the runs
     the chain is composed of (B: fixed Pi -> Jetson, relay; normal, out of range, mission)
  2. sAP over time - per 40-s phase of a 4-minute run: the chain's estimate (normal link, mission; band = Jetson
     detects locally vs forwards, total blackout = Pi onboard fallback) and YOLOv8s onboard (Part A short runs)
  3. Pi clock vs temperature, 20-s windows, filled = throttled (firmware flag) in that window
Output: experiments/results/hardware/figs_hier.html (figure markup), docs/figs/hier_*.svg (standalone copies),
figs_hier_data.json (the plotted numbers).
"""
import glob
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
HW = ROOT / "experiments" / "results" / "hardware"
sys.path.insert(0, str(ROOT / "validation" / "hardware"))
W, H = 640, 340
ML, MR, MT, MB = 64, 20, 18, 52


def axes(xmin, xmax, ymin, ymax, xt, yt, xl, yl, xfmt="{:g}", yfmt="{:g}"):
    sx = lambda x: ML + (x - xmin) / (xmax - xmin) * (W - ML - MR)  # noqa: E731
    sy = lambda y: H - MB - (y - ymin) / (ymax - ymin) * (H - MT - MB)  # noqa: E731
    g = []
    for t in yt:
        g.append(f'<line class="ax" x1="{ML}" x2="{W - MR}" y1="{sy(t):.1f}" y2="{sy(t):.1f}"/>'
                 f'<text x="{ML - 8}" y="{sy(t) + 4:.1f}" text-anchor="end">{yfmt.format(t)}</text>')
    for t in xt:
        g.append(f'<text x="{sx(t):.1f}" y="{H - MB + 18}" text-anchor="middle">{xfmt.format(t)}</text>')
    g.append(f'<line class="ax" x1="{ML}" x2="{ML}" y1="{MT}" y2="{H - MB}"/>')
    g.append(f'<text x="{(ML + W - MR) / 2:.0f}" y="{H - 10}" text-anchor="middle">{xl}</text>')
    g.append(f'<text transform="translate(16 {(MT + H - MB) / 2:.0f}) rotate(-90)" text-anchor="middle">{yl}</text>')
    return sx, sy, "".join(g)


def svg(body, label):
    return (f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="{label}" '
            f'xmlns="http://www.w3.org/2000/svg">{body}</svg>')


def legend(items, x0, y0):
    out = []
    for i, (cls, filled, txt) in enumerate(items):
        y = y0 + 18 * i
        fill = f'style="fill:var({cls})"' if filled else f'style="fill:var(--surface);stroke:var({cls});stroke-width:2"'
        out.append(f'<circle cx="{x0}" cy="{y}" r="5" {fill}/><text x="{x0 + 12}" y="{y + 4}" class="ink">{txt}</text>')
    return "".join(out)


def dot(x, y, cls, tip, filled=True, r=4.5):
    st = (f"fill:var({cls});stroke:var(--surface);stroke-width:2" if filled
          else f"fill:var(--surface);stroke:var({cls});stroke-width:2")
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" style="{st}"><title>{tip}</title></circle>'


def load_partA():
    rows = json.load(open(HW / "onboard_sap" / "throttle_analysis_visdrone.json"))["rows"]
    return [r for r in rows if r.get("throttled_share") is not None]


def runs_partA():
    pats = ["vid_campaign_onboard_vd_pi?", "vid_campaign_onboard_cool_vd_pi?", "vid_campaign_onboard_long_vd_pi?",
            "vid_campaign_onboard_vd_l_pi?", "vid_campaign_onboard_cool_vd_l_pi?", "vid_campaign_onboard_long_vd_l_pi?"]
    return sorted(f for p in pats for f in glob.glob(str(HW / p / "a2_*__r?.json")))


def runs_chain():
    return sorted(f for p in ("jet_s", "relay_m") for f in glob.glob(str(HW / "vid_campaign_b" / f"a2_*__{p}__r?.json")))


def windows(f, step=20.0):
    """(temperature, clock MHz, throttled share) per step-second window of one run."""
    me = json.load(open(f))["measured_energy"]
    ck = np.array(me.get("clock_log_t_mhz_flags", []), float)
    lg = np.array([x for x in me["log_t_w_c"] if x[2] == x[2]], float)
    if not len(ck) or not len(lg):
        return []
    ck = ck[ck[:, 2] >= 0]
    out = []
    for lo in np.arange(0, ck[-1, 0], step):
        m = (ck[:, 0] >= lo) & (ck[:, 0] < lo + step)
        mt = (lg[:, 0] >= lo) & (lg[:, 0] < lo + step)
        if m.sum() >= 5 and mt.any():
            out.append((float(lg[mt, 2].mean()), float(ck[m, 1].mean()),
                        float(np.mean((ck[m, 2].astype(int) & 4) > 0))))
    return out


def main():
    data = {}
    # ---- figure 1: sAP vs time throttled, one dot per run
    A = load_partA()
    bc = json.load(open(HW / "vid_campaign_b" / "_eval_cache_b.json"))
    chain_runs = {}
    for f in runs_chain():
        stem = Path(f).stem[3:]
        ck = np.array(json.load(open(f))["measured_energy"]["clock_log_t_mhz_flags"], float)
        ck = ck[ck[:, 2] >= 0]
        chain_runs[stem] = (float(np.mean((ck[:, 2].astype(int) & 4) > 0)), bc[stem]["sAP_fc"])
    data["fig1"] = {"onboard": [(r["model"], r["cond"], r["throttled_share"], r["sAP_fc"]) for r in A],
                    "chain_parts": chain_runs}
    sx, sy, g = axes(0, 1, 0, 0.2, [0, .25, .5, .75, 1], [0, .05, .1, .15, .2],
                     "throttled-time ratio of the run (firmware flag)", "sAP with forecaster",
                     xfmt="{:.0%}", yfmt="{:.2f}")
    b = [g]
    for stem, (thr, s) in chain_runs.items():
        sc, pol, rep = stem.split("__")
        name = {"jet_s": "Pi → Jetson (Jetson detects)", "relay_m": "Pi → Jetson → laptop (forwarded)"}[pol]
        b.append(dot(sx(thr), sy(s), "--c-hier", f"{name}, {sc.replace('_', ' ')} {rep}: throttled {thr:.0%}, sAP {s:.3f}"))
    for model, cond, thr, s in data["fig1"]["onboard"]:
        b.append(dot(sx(thr), sy(s), "--c-onb", f"onboard {model.replace('vd', '')} ({cond.replace('_', ' ')}): "
                                               f"throttled {thr:.0%}, sAP {s:.4f}"))
    b.append(f'<text x="{sx(1):.1f}" y="{sy(0.032):.1f}" text-anchor="end" class="ink">Pi alone: YOLOv8s ≈ 0.017, m ≈ 0.007, l ≈ 0.0015</text>')
    b.append(f'<text x="{sx(0) + 10:.1f}" y="{sy(0.172):.1f}" class="ink">hierarchical chain: 0 % throttled</text>')
    b.append(legend([("--c-hier", True, "hierarchical chain (18 runs of its parts)"),
                     ("--c-onb", True, "Pi alone, onboard (30 runs)")], ML + 270, MT + 150))
    f1 = svg("".join(b), "sAP against the share of time the Pi was throttled")

    # ---- figure 2: sAP over time (per 40-s phase)
    from stream_ap import VID, evaluate
    labels = json.load(open(VID / "labels.json"))
    fp = json.load(open(HW / "forecast_tuning_v2.json"))["best"]["params"]
    onb = []
    for f in sorted(glob.glob(str(HW / "vid_campaign_onboard_vd_pi?" / "a2_*s640_vd__r?.json"))
                    + glob.glob(str(HW / "vid_campaign_onboard_cool_vd_pi?" / "a2_*s640_vd__r?.json"))):
        onb.append(list(evaluate(Path(f), labels, "newest", forecast=fp)["per_phase_sAP"].values()))
    onb = np.mean(onb, 0)

    def phase_mean(sc, pol):
        ms = [v["phase_fc"] for k, v in bc.items() if k.startswith(f"{sc}__{pol}__")]
        return np.mean([list(m.values()) for m in ms], 0), list(ms[0])
    nj, _ = phase_mean("static_good", "jet_s")
    nr, _ = phase_mean("static_good", "relay_m")
    mj, names = phase_mean("mission", "jet_s")
    mr, _ = phase_mean("mission", "relay_m")
    mv, _ = phase_mean("mission", "v41")
    tb = names.index("total_blackout")
    n_lo, n_hi = np.minimum(nj, nr), np.maximum(nj, nr)
    m_lo, m_hi = np.minimum(mj, mr), np.maximum(mj, mr)
    m_lo[tb] = m_hi[tb] = mv[tb]
    data["fig2"] = {"phases_mission": names, "normal_low": n_lo.tolist(), "normal_high": n_hi.tolist(),
                    "mission_low": m_lo.tolist(), "mission_high": m_hi.tolist(), "onboard_s640": onb.tolist()}
    sx, sy, g = axes(0, 240, 0, 0.25, [0, 40, 80, 120, 160, 200, 240], [0, .05, .1, .15, .2, .25],
                     "time in the 4-minute run (s); six 40-s phases", "sAP with forecaster", yfmt="{:.2f}")
    b = [g]
    short = ["good", "congested", "ground cut", "both slow", "all cut", "recovered"]
    for i, n in enumerate(short):
        b.append(f'<text x="{sx(40 * i + 20):.1f}" y="{MT + 12}" text-anchor="middle">{n}</text>')
        if i:
            b.append(f'<line class="ax" x1="{sx(40 * i):.1f}" x2="{sx(40 * i):.1f}" y1="{MT}" y2="{H - MB}"/>')

    def step_band(lo, hi, cls, op):
        pts_hi = " ".join(f"{sx(40 * i + d):.1f},{sy(v):.1f}" for i, v in enumerate(hi) for d in (0, 40))
        pts_lo = " ".join(f"{sx(40 * i + d):.1f},{sy(v):.1f}" for i, v in reversed(list(enumerate(lo))) for d in (40, 0))
        return f'<polygon points="{pts_hi} {pts_lo}" style="fill:var({cls});opacity:{op}"/>'

    def step_line(v, cls, dash=False, tip=""):
        pts = " ".join(f"{sx(40 * i + d):.1f},{sy(x):.1f}" for i, x in enumerate(v) for d in (0, 40))
        da = 'stroke-dasharray="6 4"' if dash else ""
        return (f'<polyline points="{pts}" style="fill:none;stroke:var({cls});stroke-width:2;stroke-linejoin:round" {da}>'
                f'<title>{tip}</title></polyline>')
    b.append(step_band(n_lo, n_hi, "--c-hier", 0.16))
    b.append(step_line((n_lo + n_hi) / 2, "--c-hier", tip="chain, normal link: " + ", ".join(f"{a:.3f}–{c:.3f}" for a, c in zip(n_lo, n_hi))))
    b.append(step_band(m_lo, m_hi, "--c-hier", 0.16))
    b.append(step_line((m_lo + m_hi) / 2, "--c-hier", dash=True, tip="chain, mission: " + ", ".join(f"{a:.3f}–{c:.3f}" for a, c in zip(m_lo, m_hi))))
    b.append(step_line(onb, "--c-onb", tip="YOLOv8s onboard: " + ", ".join(f"{x:.4f}" for x in onb)))
    ly = sy(0.228)
    b.append(f'<rect x="{ML + 4}" y="{ly - 11:.1f}" width="478" height="22" rx="3" style="fill:var(--surface)"/>')
    for x0, cls, dash, txt in ((ML + 10, "--c-hier", "", "chain, normal link"), (ML + 190, "--c-hier", 'stroke-dasharray="6 4"', "chain, mission"),
                               (ML + 340, "--c-onb", "", "Pi alone, YOLOv8s")):
        b.append(f'<line x1="{x0}" x2="{x0 + 24}" y1="{ly:.1f}" y2="{ly:.1f}" style="stroke:var({cls});stroke-width:2" {dash}/>'
                 f'<text x="{x0 + 30}" y="{ly + 4:.1f}" class="ink">{txt}</text>')
    f2 = svg("".join(b), "sAP over the phases of a 4-minute run")

    # ---- figure 3: clock vs temperature, 20-s windows
    wa = [w for f in runs_partA() for w in windows(f)]
    wb = [w for f in runs_chain() for w in windows(f)]
    data["fig3"] = {"onboard_windows": wa, "chain_windows": wb}
    sx, sy, g = axes(40, 95, 1000, 2500, [40, 50, 60, 70, 80, 90], [1000, 1200, 1500, 1800, 2100, 2400],
                     "Pi temperature (°C), 20-s windows", "Pi ARM clock (MHz)")
    b = [g, f'<line class="ax" x1="{sx(80):.1f}" x2="{sx(80):.1f}" y1="{MT}" y2="{H - MB}" style="stroke-dasharray:4 4"/>'
            f'<text x="{sx(80) + 4:.1f}" y="{MT + 12}">80 °C: firmware throttles</text>']
    for (t, c, th) in wb:
        b.append(dot(sx(t), sy(c), "--c-hier", f"chain: {t:.1f} °C, {c:.0f} MHz, throttled {th:.0%}", filled=th >= 0.5, r=3.5))
    for (t, c, th) in wa:
        b.append(dot(sx(t), sy(c), "--c-onb", f"onboard: {t:.1f} °C, {c:.0f} MHz, throttled {th:.0%}", filled=th >= 0.5, r=3.5))
    b.append(legend([("--c-hier", False, "hierarchical chain, not throttled"),
                     ("--c-onb", False, "Pi alone, not throttled"),
                     ("--c-onb", True, "Pi alone, throttled")], ML + 16, sy(1490)))
    f3 = svg("".join(b), "Pi clock against temperature, throttled windows filled")

    fa = np.array(wa)
    fb = np.array(wb)
    data["fig3_summary"] = {"onboard_throttled_share": float((fa[:, 2] >= .5).mean()),
                            "onboard_clock_throttled": float(fa[fa[:, 2] >= .5, 1].mean()),
                            "onboard_temp_mean": float(fa[:, 0].mean()),
                            "chain_throttled_share": float((fb[:, 2] >= .5).mean()),
                            "chain_temp_range": [float(fb[:, 0].min()), float(fb[:, 0].max())],
                            "chain_clock_range": [float(fb[:, 1].min()), float(fb[:, 1].max())]}
    json.dump(data, open(HW / "figs_hier_data.json", "w"), indent=1)
    (ROOT / "docs" / "figs").mkdir(parents=True, exist_ok=True)
    style = ("<style>svg{--surface:#fff;--c-hier:#00806A;--c-onb:#A85F00;--rule:#D3DBD8;--muted:#56635F;--ink:#16211F}"
             "text{fill:var(--muted);font:11px monospace} .ink{fill:var(--ink)} .ax{stroke:var(--rule)}</style>")
    for name, fig in (("sap_vs_throttling", f1), ("sap_vs_time", f2), ("clock_vs_throttling", f3)):
        flat = (fig.replace("var(--c-hier)", "#00806A").replace("var(--c-onb)", "#A85F00").replace("var(--surface)", "#FFFFFF"))
        (ROOT / "docs" / "figs" / f"hier_{name}.svg").write_text(flat.replace(">", ">" + style, 1))
    s3 = data["fig3_summary"]
    html = f'''<h3>18.7 Graphs: throttling, time and clock speed (hierarchical chain against the Pi alone)</h3>
<p>All three from measured runs: the chain's parts (B, 18 runs of fixed Pi → Jetson and relay) and Part 17's onboard runs (30). Hover a mark for its values. Data: <code>experiments/results/hardware/figs_hier_data.json</code>; figures also in <code>docs/figs/hier_*.svg</code> (<code>scripts/report_figs_hier.py</code>).</p>
<figure class="chart">{f1}<figcaption><b>sAP against throttling.</b> One dot per run. The chain never throttles the camera drone (all 18 runs at 0 %) and reaches 0.08–0.18 sAP (the lower dots are the mission runs, with their blackout phases); the Pi alone is throttled 59–98 % of every run and reaches at most 0.019. Throttling is a symptom of doing the work on the camera drone: offloading removes it.</figcaption></figure>
<figure class="chart">{f2}<figcaption><b>sAP over time within a 4-minute run</b> (six 40-s phases; phase names are the mission's, the normal link is good throughout). Band: the Jetson detecting locally or forwarding to the laptop (lower and upper bound); line: its middle. <b>The step-to-step changes on the normal link (0.07–0.20) are the video, not the network:</b> the 7 test clips play in a fixed order, so every run shows the same scenes in the same phase (phase 2 holds the hardest ones; the Pi alone drops there too). Compare the lines within one phase. In the mission (dashed) the chain matches the normal link while the link to the Jetson is good (good, ground cut, recovered): it never uses the direct ground link, so cutting it costs nothing. It falls only when the Pi → Jetson link is slowed (both slow: 0.03 against 0.16) and in the total blackout keeps the Pi's onboard fallback (0.04). The Pi alone stays at 0.01–0.03 after its first phase.</figcaption></figure>
<figure class="chart">{f3}<figcaption><b>Clock speed against temperature and throttling</b> (20-s windows; filled = throttled in most of the window). The Pi alone sits at {s3["onboard_temp_mean"]:.0f} °C on average, throttled in {100 * s3["onboard_throttled_share"]:.0f} % of the windows, at {s3["onboard_clock_throttled"]:.0f} MHz when throttled (2,400 MHz is the full clock). In the chain the Pi stays at {s3["chain_temp_range"][0]:.0f}–{s3["chain_temp_range"][1]:.0f} °C and is never throttled ({100 * s3["chain_throttled_share"]:.0f} % of windows); its clock varies from {s3["chain_clock_range"][0]:.0f} to {s3["chain_clock_range"][1]:.0f} MHz only because the frequency governor slows an idle CPU, not because of heat.</figcaption></figure>
'''
    (HW / "figs_hier.html").write_text(html)
    print(json.dumps(data["fig3_summary"]), "normal", n_lo.round(3), n_hi.round(3), "mission", m_lo.round(3), m_hi.round(3), "onboard", onb.round(4))


if __name__ == "__main__":
    main()
