#!/usr/bin/env python3
"""Report update, 26 Oct 2026: 19.7 - streaming accuracy against camera-drone power (Pareto analysis,
validation/hardware/pareto_analysis.py -> pareto_analysis.json), two inline SVG figures (report theme tokens, as
report_figs_hier.py) for the 240-run main campaign and the second mesh campaign, plus a table for every campaign.
Inserted after 19.6 (before Part 20); standalone copies in docs/figs/pareto_*.svg. Idempotent.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_figs_hier import H, MB, ML, MR, MT, W, axes, dot, legend, svg  # noqa: E402
from report_parts_oct22 import HTML, MD, html_to_md, table  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
HW = ROOT / "experiments" / "results" / "hardware"
NAME = {"v5": "v5", "v5_lin": "v5 linear decay", "v5_exp": "v5 exp. decay", "v42": "v4.2", "v41": "v4.1",
        "v41e": "v4.1 + Jetson price", "heat": "heat price", "heate": "heat + Jetson price", "v51": "v5.1",
        "leaf": "LEAF-style fixed weight", "v5_nofc": "v5 without forecaster", "v5_flat": "v5 flat decay",
        "noprice": "no prices", "aoi_thr": "freshness threshold", "aoithr": "freshness threshold",
        "jsq": "shortest queue", "conf_trigger": "confidence trigger (OffloaD-style)",
        "reward_offload": "offloading reward (Qiu-style)", "fixed_laptop_m640q90": "fixed laptop",
        "fixlap": "fixed laptop", "A_eco_tight": "v4 (tight budget)", "A_eco": "v4", "A_full": "v2", "A_eco41": "v4.1",
        "A_eco42": "v4.2", "A_eco42d": "v4.2 (decayed)", "A_stream_fc2": "v3 + forecaster (no energy price)",
        "onboard_n320": "onboard YOLOv8n", "stream_fc2": "v3 + forecaster (stream objective, no prices)", "v41e12": "v4.1 + Jetson price (1.2 W)"}
OURS = {"v5", "v5_lin", "v5_exp", "v42", "v41", "v41e", "heat", "heate", "v51", "A_eco_tight", "A_eco", "A_eco41",
        "A_eco42", "A_eco42d", "v41e12"}
ABL = {"v5_nofc", "v5_flat", "noprice", "A_full", "A_stream_fc2", "stream_fc2"}


def cls(p):
    return "--accent" if p in OURS else ("--warn" if p in ABL else "--bad")


def fig(camp, d, xr, yr, xt, yt, title, leg_xy):
    cells, fr = d["cells"], d["front"]
    sx, sy, g = axes(xr[0], xr[1], yr[0], yr[1], xt, yt, "camera-drone (Pi 5) power, W", "sAP with forecaster",
                     yfmt="{:.2f}")
    b = [g]
    pts = sorted(((cells[p]["pi_w"][0], cells[p]["sAP_fc"][0]) for p in fr))
    b.append('<polyline points="' + " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in pts)
             + '" style="fill:none;stroke:var(--ink);stroke-width:1.2;stroke-dasharray:4 3"/>')
    # strategies closer than 0.12 W and 0.004 sAP share one label
    groups = []
    for p, c in sorted(cells.items(), key=lambda kv: -kv[1]["sAP_fc"][0]):
        for gr in groups:
            q = gr[0]
            if abs(cells[q]["pi_w"][0] - c["pi_w"][0]) < 0.12 and abs(cells[q]["sAP_fc"][0] - c["sAP_fc"][0]) < 0.004:
                gr.append(p)
                break
        else:
            groups.append([p])
    dots = [(sx(c["pi_w"][0]), sy(c["sAP_fc"][0])) for c in cells.values()]
    lx, ly = leg_xy
    taken = [(lx - 8, ly - 10, lx + 215, ly + 46)]           # legend box
    taken += [(x - 6, y - 6, x + 6, y + 6) for x, y in dots]
    lab = []
    for gr in groups:
        for p in gr:
            c = cells[p]
            b.append(dot(sx(c["pi_w"][0]), sy(c["sAP_fc"][0]), cls(p),
                         f"{NAME.get(p, p)}: sAP {c['sAP_fc'][0]:.3f}, {c['pi_w'][0]:.2f} W, {c['temp_c'][0]:.0f} °C, "
                         f"{c['n']} runs" + (" (Pareto front)" if p in fr else ""), filled=p not in ABL))
        c = cells[gr[0]]
        x, y = sx(c["pi_w"][0]), sy(c["sAP_fc"][0])
        txt = " / ".join(NAME.get(p, p) for p in gr) if len(gr) < 3 else f"{NAME.get(gr[0], gr[0])} (+{len(gr) - 1} alike)"
        w = 6.1 * len(txt)
        for anchor, tx, ty, box in (("start", x + 9, y + 4, (x + 8, y - 7, x + 10 + w, y + 7)),
                                    ("end", x - 9, y + 4, (x - 10 - w, y - 7, x - 8, y + 7)),
                                    ("middle", x, y - 11, (x - w / 2, y - 21, x + w / 2, y - 7)),
                                    ("middle", x, y + 19, (x - w / 2, y + 9, x + w / 2, y + 23))):
            inside = box[0] >= ML and box[2] <= W - 4 and box[1] >= 2 and box[3] <= H - MB
            if inside and not any(box[0] < t[2] and t[0] < box[2] and box[1] < t[3] and t[1] < box[3] for t in taken):
                break
        taken.append(box)
        lab.append(f'<text x="{tx:.1f}" y="{ty:.1f}" text-anchor="{anchor}" class="ink" style="font-size:10px">{txt}</text>')
    b += lab
    b.append(legend([("--accent", True, "our controller (prices)"), ("--warn", False, "ablation of it"),
                     ("--bad", True, "fixed / literature baseline")], lx, ly))
    return svg("".join(b), title)


def section():
    d = json.load(open(HW / "pareto_analysis.json"))
    f1 = fig("vid_campaign_main", d["vid_campaign_main"], (2.2, 5.0), (0.06, 0.135), [2.5, 3, 3.5, 4, 4.5, 5],
             [0.07, 0.09, 0.11, 0.13], "Main campaign: sAP against Pi power", (ML + 14, H - MB - 50))
    f2 = fig("vid_campaign_mesh2", d["vid_campaign_mesh2"], (2.0, 4.5), (0.12, 0.185), [2, 2.5, 3, 3.5, 4, 4.5],
             [0.12, 0.14, 0.16, 0.18], "Mesh campaign 2: sAP against Pi power", (W - MR - 225, H - MB - 50))
    rows = []
    for camp, label in (("vid_campaign_energy", "G9 energy (100 runs)"), ("vid_campaign_v42", "G11 v4.2 (120)"),
                        ("vid_campaign_main", "G12 main (240)"), ("vid_campaign_table", "G13 same-day (80)"),
                        ("vid_campaign_long", "G13 24-min (12)"), ("vid_campaign_mesh2", "18.9 mesh 2 (63)"),
                        ("vid_campaign_mesh3", "18.10 mesh 3 (18)")):
        x = d[camp]
        best = max(x["cells"], key=lambda p: x["cells"][p]["sAP_fc"][0])
        dom = [p for p in x["cells"] if p not in x["front"]]
        rows.append([label, NAME.get(x["reference"], x["reference"]), NAME.get(best, best),
                     ", ".join(NAME.get(p, p) for p in x["front"]), ", ".join(NAME.get(p, p) for p in dom) or "—"])
    t = table(["Campaign", "reference controller", "most accurate", "on the Pareto front (not beaten on both)",
               "dominated (another strategy is more accurate AND uses less power)"], rows)
    m, me = d["vid_campaign_main"]["paired_vs_reference"], d["vid_campaign_mesh2"]["paired_vs_reference"]
    lit = ("jsq", "conf_trigger", "reward_offload")
    return f'''<h3>19.7 Accuracy against power: where every strategy sits (Pareto analysis, 26 Oct 2026)</h3>
<p>Every campaign that logged the camera drone's power (7 campaigns, 633 runs), each strategy's mean streaming accuracy (standard sAP with the campaign's forecaster, VisDrone detections) against its mean Pi power, compared only within its own campaign. A strategy is on the <b>Pareto front</b> if no other strategy of the same campaign is both more accurate and less power-hungry (<code>validation/hardware/pareto_analysis.py</code>, <code>experiments/results/hardware/pareto_analysis.json/.md</code>; the hierarchical chain, run in multihop only, is left out of the pooled mesh-2 comparison). Hover a dot for its numbers.</p>
<figure class="chart">{f1}<figcaption><b>Main campaign (G12, 240 runs, Wi-Fi, 12 strategies).</b> Our controller family sits at the accurate end of the front; the literature schedulers that offload or retry aggressively (shortest queue, confidence trigger, offloading reward) are <b>both less accurate and 1.5–1.7 W more power-hungry</b> ({min(m[p]['dsAP_ref_minus'][0] for p in lit):.3f}–{max(m[p]['dsAP_ref_minus'][0] for p in lit):.3f} sAP behind and {min(-m[p]['dW_ref_minus'][0] for p in lit):.2f}–{max(-m[p]['dW_ref_minus'][0] for p in lit):.2f} W, all p &lt; 0.001). The only cheaper strategies are fixed laptop offloading and the freshness threshold, which save 0.5–0.7 W by giving up 0.02–0.03 sAP. The cluster at the top holds v5, its linear and exponential decay variants and the LEAF-style fixed weight (hover for each); the LEAF-style weight ties v5 only because it was set to the price v4's dual ascent itself settles at (Part 16).</figcaption></figure>
<figure class="chart">{f2}<figcaption><b>Mesh campaign 2 (18.9, real AegisSwarm mesh, 63 runs).</b> v4.1 is the most accurate strategy and dominates every other priced variant: the heat price and no prices reach the same accuracy at +{-me['heat']['dW_ref_minus'][0]:.2f} W and +{-me['noprice']['dW_ref_minus'][0]:.2f} W (the latter throttled 39 % of the time), the Jetson price at its 0.5 W budget costs {me['v41e']['dsAP_ref_minus'][0]:.3f} sAP for no Pi saving. The freshness threshold is the only other point on the front, {me['aoithr']['dW_ref_minus'][0]:.2f} W cheaper but {me['aoithr']['dsAP_ref_minus'][0]:.3f} sAP behind.</figcaption></figure>
{t}
<ul>
<li><b>A priced controller is on the front in every campaign</b> and is the most accurate strategy in every campaign (in the main campaign it is v5's linear-decay variant, which v5 trails by 0.0003 sAP). No baseline is both more accurate and cheaper.</li>
<li><b>Removing a price moves the controller off the front, never along it</b>: without the energy price (v2, v3 + forecaster, "no prices") it is less accurate or equally accurate and always 0.9–1.5 W more power-hungry and hotter (up to 84 °C, throttling).</li>
<li><b>The cheap end of the front belongs to strategies that rarely use the Pi</b> (fixed offloading, freshness threshold): they save 0.55–0.75 W by giving up 17–28 % of streaming accuracy and fail when the link fails (18.9). A user who values Pi energy more than our budget does can move along the front by lowering the controller's power budget, the knob the energy price exists for.</li>
</ul>
'''


def main():
    h, m = HTML.read_text(), MD.read_text()
    sec = section()
    j = h.index('<h2 id="argument">')
    i = h.find("<h3>19.7 ")
    h = h[:i if 0 <= i < j else j] + sec + h[j:]
    j = m.index("## PART 20")
    i = m.find("### 19.7 ")
    md_sec = html_to_md(re.sub(r"<figure class=\"chart\">.*?<figcaption>(.*?)</figcaption></figure>",
                               r"<p>\1</p>", sec, flags=re.S))
    m = m[:i if 0 <= i < j else j] + md_sec + m[j:]
    HTML.write_text(h)
    MD.write_text(m)
    style = "<style>text{fill:#56635F;font:11px monospace} .ink{fill:#16211F} .ax{stroke:#D3DBD8}</style>"
    hexes = {"--surface": "#FFFFFF", "--accent": "#0D6B5E", "--warn": "#9A5A00", "--bad": "#A8352C", "--ink": "#16211F",
             "--rule": "#D3DBD8", "--muted": "#56635F"}
    figs = re.findall(r"<svg .*?</svg>", sec, flags=re.S)
    (ROOT / "docs" / "figs").mkdir(parents=True, exist_ok=True)
    for name, f in zip(("pareto_main", "pareto_mesh2"), figs):
        for k, v in hexes.items():          # standalone copies: plain colours (no CSS variables)
            f = f.replace(f"var({k})", v)
        (ROOT / "docs" / "figs" / f"{name}.svg").write_text(f.replace(">", ">" + style, 1))
    print("report updated: 19.7 (Pareto), docs/figs/pareto_*.svg")


if __name__ == "__main__":
    main()
