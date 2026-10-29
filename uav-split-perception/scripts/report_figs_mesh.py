#!/usr/bin/env python3
"""Three report figures for the mesh campaigns (Part 18.8-18.10), the counterparts of report_figs_hier.py's 18.7
figures (inline SVG, report theme tokens), from measured runs only.
  1. sAP vs time throttled - one dot per run: every mesh run (campaigns 1-3, short and 24-min) against the Pi alone
     (Part 17: VisDrone YOLOv8s/m/l and YOLO11n/s/m onboard, both Pis); the strategy without prices drawn apart
  2. sAP over time - per phase of the 4-minute mesh mission (campaign 2, mean of 3 runs): v4.1, v4.1 + Jetson energy
     price, fixed Pi -> laptop, freshness threshold
  3. Pi clock vs temperature, 20-s windows, filled = throttled (firmware flag): v4.1, heat price, no prices
     (campaign 2, 4-minute runs, all three scenarios)
Output: experiments/results/hardware/figs_mesh.html (figure markup), docs/figs/mesh_*.svg (standalone copies),
figs_mesh_data.json (the plotted numbers).
"""
import glob
import json
from pathlib import Path

import numpy as np

from report_figs_hier import HW, MB, ML, MR, MT, ROOT, H, W, axes, dot, legend, svg, windows

CAMPS = {"vid_campaign_mesh": "mesh campaign 1", "vid_campaign_mesh2": "mesh campaign 2",
         "vid_campaign_mesh2_long": "mesh campaign 2, 24 min", "vid_campaign_mesh3": "mesh campaign 3"}
NAMES = {"v41": "v4.1", "v41e": "v4.1 + Jetson energy (0.5 W)", "v41e12": "v4.1 + Jetson energy (1.2 W)",
         "heat": "heat + freshness", "heate": "heat + Jetson energy", "noprice": "no prices", "fixlap": "fixed Pi → laptop",
         "aoithr": "freshness threshold", "hier": "hierarchical chain"}
HEX = {"--c-hier": "#00806A", "--c-onb": "#A85F00", "--c-noprice": "#6250d6", "--c-heat": "#eb6834",
       "--c-fixed": "#2a78d6", "--c-thr": "#eda100", "--surface": "#FFFFFF"}


def mesh_runs():
    """(campaign, scenario, strategy, rep, throttled share, sAP with forecaster) for every scored mesh run."""
    out = []
    for camp in CAMPS:
        cache = json.load(open(HW / camp / "_eval_cache_mesh.json"))
        for stem, v in sorted(cache.items()):
            sc, st, rep = stem.split("__")
            out.append((camp, sc, st, rep, v["pi_throttled"], v["sAP_fc"]))
    return out


def main():
    data = {}
    # ---- figure 1: sAP vs time throttled, one dot per run
    runs = mesh_runs()
    onb = []
    for fn in ("throttle_analysis_visdrone.json", "throttle_analysis_yolo11.json"):
        onb += [(r["model"], r["cond"], r["throttled_share"], r["sAP_fc"])
                for r in json.load(open(HW / "onboard_sap" / fn))["rows"] if r.get("throttled_share") is not None]
    data["fig1"] = {"mesh": runs, "onboard": onb}
    sx, sy, g = axes(0, 1, 0, 0.25, [0, .25, .5, .75, 1], [0, .05, .1, .15, .2, .25],
                     "throttled-time ratio of the run (firmware flag)", "sAP with forecaster",
                     xfmt="{:.0%}", yfmt="{:.2f}")
    b = [g]
    for camp, sc, st, rep, thr, s in runs:
        cls = "--c-noprice" if st == "noprice" else "--c-hier"
        b.append(dot(sx(thr), sy(s), cls, f"{NAMES[st]}, {CAMPS[camp]}, {sc.replace('_', ' ')} {rep}: "
                                          f"throttled {thr:.0%}, sAP {s:.3f}"))
    for model, cond, thr, s in onb:
        b.append(dot(sx(thr), sy(s), "--c-onb", f"Pi alone, {model.replace('vd', '').replace('640', '-640')} "
                                                f"({cond.replace('_', ' ')}): throttled {thr:.0%}, sAP {s:.4f}"))
    other = [r for r in runs if r[2] != "noprice"]
    nop = [r for r in runs if r[2] == "noprice"]
    b.append(f'<text x="{sx(0) + 10:.1f}" y="{sy(0.232):.1f}" class="ink">every priced, fixed and literature strategy: at most 0.5 % throttled</text>')
    b.append(f'<text x="{sx(1):.1f}" y="{sy(0.062):.1f}" text-anchor="end" class="ink">Pi alone: at most {max(x[3] for x in onb):.3f}</text>')
    b.append(legend([("--c-hier", True, f"mesh strategies with a price, fixed or literature ({len(other)} runs)"),
                     ("--c-noprice", True, f"mesh, no prices ({len(nop)} runs)"),
                     ("--c-onb", True, f"Pi alone, onboard ({len(onb)} runs, Part 17)")], ML + 190, sy(0.118)))
    f1 = svg("".join(b), "sAP against the share of time the Pi was throttled, mesh campaigns and the Pi alone")

    # ---- figure 2: sAP per phase of the 4-minute mesh mission (campaign 2)
    cache = json.load(open(HW / "vid_campaign_mesh2" / "_eval_cache_mesh.json"))

    def phases(st):
        ms = [v["phase_fc"] for k, v in cache.items() if k.startswith(f"mesh_mission__{st}__")]
        return np.mean([list(m.values()) for m in ms], 0), list(ms[0]), len(ms)
    series = [("v41", "--c-hier", False), ("v41e", "--c-hier", True), ("aoithr", "--c-thr", False),
              ("fixlap", "--c-fixed", False)]
    vals = {st: phases(st) for st, _, _ in series}
    names = vals["v41"][1]
    data["fig2"] = {"phases": names, **{st: v[0].tolist() for st, v in vals.items()},
                    "runs": {st: v[2] for st, v in vals.items()}}
    sx, sy, g = axes(0, 240, 0, 0.36, [0, 40, 80, 120, 160, 200, 240], [0, .05, .1, .15, .2, .25, .3],
                     "time in the 4-minute mesh mission (s); six 40-s phases", "sAP with forecaster", yfmt="{:.2f}")
    b = [g]
    short = ["good", "ground congested", "camera out of range", "edge uplink cut", "edge link slow", "recovered"]
    for i, n in enumerate(short):
        for j, w in enumerate(n.split(" ", 1) if " " in n and len(n) > 12 else [n]):
            b.append(f'<text x="{sx(40 * i + 20):.1f}" y="{sy(0.318) + 12 * j:.1f}" text-anchor="middle">{w}</text>')
        if i:
            b.append(f'<line class="ax" x1="{sx(40 * i):.1f}" x2="{sx(40 * i):.1f}" y1="{MT}" y2="{H - MB}"/>')

    def step_line(v, cls, dash, tip):
        pts = " ".join(f"{sx(40 * i + d):.1f},{sy(x):.1f}" for i, x in enumerate(v) for d in (0, 40))
        da = 'stroke-dasharray="6 4"' if dash else ""
        return (f'<polyline points="{pts}" style="fill:none;stroke:var({cls});stroke-width:2;stroke-linejoin:round" {da}>'
                f'<title>{tip}</title></polyline>')
    for st, cls, dash in series:
        v = vals[st][0]
        b.append(step_line(v, cls, dash, f"{NAMES[st]}: " + ", ".join(f"{n} {x:.3f}" for n, x in zip(short, v))))
        for i, x in enumerate(v):       # invisible wide hit targets per phase
            b.append(f'<rect x="{sx(40 * i):.1f}" y="{sy(x) - 5:.1f}" width="{sx(40) - sx(0):.1f}" height="10" '
                     f'style="fill:transparent"><title>{NAMES[st]}, {short[i]}: {x:.3f}</title></rect>')
    leg = [("--c-hier", "", "v4.1"), ("--c-hier", 'stroke-dasharray="6 4"', "v4.1 + Jetson energy (0.5 W)"),
           ("--c-thr", "", "freshness threshold"), ("--c-fixed", "", "fixed Pi → laptop")]
    xs = [ML + 4, ML + 74, ML + 290, ML + 440]
    lyt = sy(0.343)
    b.append(f'<rect x="{ML + 2}" y="{lyt - 11:.1f}" width="{W - ML - MR - 4}" height="22" rx="3" style="fill:var(--surface)"/>')
    for x0, (cls, da, txt) in zip(xs, leg):
        b.append(f'<line x1="{x0}" x2="{x0 + 22}" y1="{lyt:.1f}" y2="{lyt:.1f}" style="stroke:var({cls});stroke-width:2" {da}/>'
                 f'<text x="{x0 + 27}" y="{lyt + 4:.1f}" class="ink">{txt}</text>')
    f2 = svg("".join(b), "sAP over the phases of the 4-minute mesh mission")

    # ---- figure 3: clock vs temperature, 20-s windows (campaign 2, 4-minute runs)
    win = {st: [w for f in sorted(glob.glob(str(HW / "vid_campaign_mesh2" / f"a2_*__{st}__r?.json"))) for w in windows(f)]
           for st in ("v41", "heat", "noprice")}
    data["fig3"] = win
    sx, sy, g = axes(50, 95, 1000, 2500, [50, 60, 70, 80, 90], [1000, 1200, 1500, 1800, 2100, 2400],
                     "Pi temperature (°C), 20-s windows", "Pi ARM clock (MHz)")
    b = [g, f'<line class="ax" x1="{sx(80):.1f}" x2="{sx(80):.1f}" y1="{MT}" y2="{H - MB}" style="stroke-dasharray:4 4"/>'
            f'<text x="{sx(80) + 4:.1f}" y="{MT + 12}">80 °C: firmware throttles</text>']
    cls3 = {"v41": "--c-hier", "heat": "--c-heat", "noprice": "--c-noprice"}
    for st in ("v41", "heat", "noprice"):
        for (t, c, th) in win[st]:
            b.append(dot(sx(t), sy(c), cls3[st], f"{NAMES[st]}: {t:.1f} °C, {c:.0f} MHz, throttled {th:.0%}",
                         filled=th >= 0.5, r=3.5))
    b.append(legend([("--c-hier", False, "v4.1 (Pi energy price)"), ("--c-heat", False, "heat + freshness"),
                     ("--c-noprice", False, "no prices, not throttled"), ("--c-noprice", True, "no prices, throttled")],
                    ML + 16, sy(1450)))
    f3 = svg("".join(b), "Pi clock against temperature on the mesh, throttled windows filled")

    def summ(w):
        a = np.array(w)
        thr = a[:, 2] >= .5
        return {"windows": len(a), "temp_mean": float(a[:, 0].mean()), "temp_range": [float(a[:, 0].min()), float(a[:, 0].max())],
                "throttled_share": float(thr.mean()),
                "clock_throttled": float(a[thr, 1].mean()) if thr.any() else None,
                "clock_unthrottled_median": float(np.median(a[~thr, 1]))}
    data["fig3_summary"] = {st: summ(w) for st, w in win.items()}
    data["fig1_summary"] = {"mesh_runs": len(runs), "other_max_throttled": max(r[4] for r in other),
                            "noprice_throttled": [min(r[4] for r in nop), max(r[4] for r in nop)],
                            "noprice_sap": [min(r[5] for r in nop), max(r[5] for r in nop)],
                            "onboard_runs": len(onb), "onboard_throttled": [min(x[2] for x in onb), max(x[2] for x in onb)],
                            "onboard_sap_max": max(x[3] for x in onb),
                            "mesh_sap_range": [min(r[5] for r in runs), max(r[5] for r in runs)]}
    json.dump(data, open(HW / "figs_mesh_data.json", "w"), indent=1)
    (ROOT / "docs" / "figs").mkdir(parents=True, exist_ok=True)
    style = ("<style>text{fill:#56635F;font:11px monospace} .ink{fill:#16211F} .ax{stroke:#D3DBD8}</style>")
    for name, fig in (("sap_vs_throttling", f1), ("sap_vs_time", f2), ("clock_vs_throttling", f3)):
        flat = fig
        for k, v in HEX.items():
            flat = flat.replace(f"var({k})", v)
        (ROOT / "docs" / "figs" / f"mesh_{name}.svg").write_text(flat.replace(">", ">" + style, 1))
    s1, s3 = data["fig1_summary"], data["fig3_summary"]
    p = dict(zip(short, zip(*[vals[st][0] for st, _, _ in series])))
    html = f'''<h3>18.11 Graphs: throttling, time and clock speed on the mesh</h3>
<p>The counterparts of 18.7 for the mesh campaigns (18.8–18.10), all from measured runs. Hover a mark for its values. Data: <code>experiments/results/hardware/figs_mesh_data.json</code>; figures also in <code>docs/figs/mesh_*.svg</code> (<code>scripts/report_figs_mesh.py</code>).</p>
<figure class="chart">{f1}<figcaption><b>sAP against throttling.</b> One dot per run: all {s1["mesh_runs"]} mesh runs (campaigns 1–3, 4-minute and 24-minute) and the {s1["onboard_runs"]} onboard runs of Part 17 (YOLOv8s/m/l and YOLO11n/s/m on the Pi alone). Every mesh strategy with a price, fixed offloading, the freshness threshold and the hierarchical chain keeps the camera drone almost never throttled (at most {100 * s1["other_max_throttled"]:.1f} % of a run) and reaches {s1["mesh_sap_range"][0]:.2f}–{s1["mesh_sap_range"][1]:.2f} sAP (the lower dots are multihop and mission runs). Without prices the Pi is throttled {100 * s1["noprice_throttled"][0]:.0f}–{100 * s1["noprice_throttled"][1]:.0f} % of the run at the same accuracy ({s1["noprice_sap"][0]:.2f}–{s1["noprice_sap"][1]:.2f}): the extra onboard work buys nothing. The Pi alone is throttled {100 * s1["onboard_throttled"][0]:.0f}–{100 * s1["onboard_throttled"][1]:.0f} % of every run and reaches at most {s1["onboard_sap_max"]:.3f}.</figcaption></figure>
<figure class="chart">{f2}<figcaption><b>sAP over the 4-minute mesh mission</b> (campaign 2, mean of 3 runs per strategy; the per-phase table in 18.9 gives the numbers). As in 18.7, the level changes from phase to phase are mostly the video: every run plays the same clips in the same order, so compare the lines within one phase. Fixed laptop offloading is level with v4.1 on good links, but collapses when the ground link is congested ({p["ground congested"][3]:.3f} against {p["ground congested"][0]:.3f}) or out of range ({p["camera out of range"][3]:.4f} against {p["camera out of range"][0]:.3f}, where v4.1 moves to the Jetson), and recovers only partly in the next phase ({p["edge uplink cut"][3]:.3f}). The Jetson energy price (0.5 W budget) costs most when the camera is out of range ({p["camera out of range"][1]:.3f}): the Jetson then carries the stream and the price shrinks its input; elsewhere it is within about 0.01 of v4.1. The freshness threshold offloads too rarely and stays below v4.1 in every phase. The hierarchical chain's mission runs are in 18.8 (another campaign, so not drawn here).</figcaption></figure>
<figure class="chart">{f3}<figcaption><b>Clock speed against temperature on the mesh</b> (campaign 2, 4-minute runs, all three scenarios; 20-s windows; filled = throttled in most of the window). v4.1 keeps the Pi at {s3["v41"]["temp_mean"]:.0f} °C on average ({s3["v41"]["temp_range"][0]:.0f}–{s3["v41"]["temp_range"][1]:.0f} °C), heat + freshness at {s3["heat"]["temp_mean"]:.0f} °C, both never throttled ({100 * s3["v41"]["throttled_share"]:.0f} % and {100 * s3["heat"]["throttled_share"]:.0f} % of windows). Without prices the Pi averages {s3["noprice"]["temp_mean"]:.0f} °C, crosses 80 °C and is throttled in {100 * s3["noprice"]["throttled_share"]:.0f} % of the windows, at {s3["noprice"]["clock_throttled"]:.0f} MHz when throttled (2,400 MHz is the full clock). Below 80 °C the clock varies only because the frequency governor slows an idle CPU.</figcaption></figure>
'''
    (HW / "figs_mesh.html").write_text(html)
    print(json.dumps({"fig1": s1, "fig3": s3, "fig2": data["fig2"]}, indent=1))


if __name__ == "__main__":
    main()
