#!/usr/bin/env python3
"""Report update, 30 Oct 2026 (laptop-only additions, part 5): 19.12 = a learned feature-compression baseline for the
split result, and the second paper's first draft (docs/laptop_additions_2026-10-30_part5.md).

Every number is read from experiments/results/learned_bottleneck/ (summary.json, system.json, train_*.json) and
paper2/generated/metrics.tex. Adds 19.12 after 19.11, a Part 1 bullet, rewrites the "Limit" of Part 20 section 1 and
updates "What is left". Run after report_part4_oct30.py. Idempotent.
usage: report_part5_oct30.py     (originals archived in experiments/results/hardware/_superseded/report_before_part5_oct30/)
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_parts_oct22 import HTML, MD, html_to_md, table  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LB = ROOT / "experiments" / "results" / "learned_bottleneck"


def fam(rows):
    return [r for r in rows if r.get("width") == 128 and r.get("dec_layers") == 2]


def label(r):
    return f"k{r['cut']}, {r['channels']} channels" + (", full resolution" if r.get("stride") == 1 else "")


def tables():
    s = json.load(open(LB / "summary.json"))
    rows = []
    for r in sorted(fam(s["learned"]), key=lambda r: (r["cut"], r["payload_bytes_mean"])):
        jm, jb, sv = r["jpeg_map_at_same_bytes"], r["jpeg_bytes_for_same_map"], r["bytes_saving_vs_jpeg_pct"]
        rows.append([f"learned, {label(r)}", f"{r['payload_bytes_mean'] / 1e3:.1f}", f"{r['map50_95']:.3f}",
                     "—" if jm is None else f"{jm:.3f}", "—" if jb is None else f"{jb / 1e3:.1f}",
                     "—" if sv is None else (f"<b>{sv:.0f} %</b>" if sv > 0 else f"{sv:.0f} %".replace("-", "−"))])
    for r in s["jpeg"]:
        rows.append([f"JPEG q{r['q']}", f"{r['payload_bytes_mean'] / 1e3:.1f}", f"{r['map50_95']:.3f}", "", "", ""])
    for r in s["posthoc_splits"]:
        rows.append([f"post-hoc {r['config'].replace('_', ' ')}", f"{r['payload_bytes_mean'] / 1e3:.1f}",
                     f"{r['map50_95_unchanged_check']:.3f}", "", "", ""])
    t1 = table(["Payload", "kB per frame", "mAP@[.5:.95]", "JPEG mAP at the same size", "JPEG kB for the same mAP",
                "bytes saved against JPEG"], rows)
    sy = json.load(open(LB / "system.json"))
    by = sy["learned_beats_image"]["by_t_full"]
    rows2 = []
    for t in sorted(by, key=float):
        v = by[t]
        g = v["max_gain_pct_where_image_usable"]
        rows2.append([f"{float(t):.0f} ms" + (" (the Pi 5, measured)" if t == max(by, key=float) else ""),
                      f"{len(v['goodput_mbps'])} of {len(sy['goodput_mbps'])}",
                      "—" if v["max_goodput_mbps"] is None else f"{v['max_goodput_mbps']:.1f} Mbit/s",
                      "—" if g is None else f"+{g:.0f} %",
                      ", ".join(b.replace("learned_", "") for b in v["best_learned"]) or "—"])
    t2 = table(["Onboard speed (YOLOv8s per frame)", "goodputs where a learned code beats the best image option",
                "up to", f"largest gain where the image delivers at least {sy['learned_beats_image']['usable_threshold']:g} "
                "accuracy-weighted on-time results/s", "learned codes that win"], rows2)
    return s, sy, t1, t2


def chart():
    """The rate-accuracy figure as inline SVG in the brief's style (theme colours through its CSS variables)."""
    import math
    s = json.load(open(LB / "summary.json"))
    jp, lb, ph = s["jpeg"], fam(s["learned"]), s["posthoc_splits"]
    base = jp[0]["base_map50_95"]
    xs = [r["payload_bytes_mean"] / 1e3 for r in jp + lb + ph]
    x0, x1 = math.log10(min(xs) / 1.5), math.log10(max(xs) * 1.5)
    y0 = min(r["map50_95"] for r in jp + lb) - 0.01
    y1 = base + 0.01
    X = lambda kb: 64 + (math.log10(kb) - x0) / (x1 - x0) * 556  # noqa: E731
    Y = lambda m: 270 - (m - y0) / (y1 - y0) * 252  # noqa: E731
    o = ['<figure class="chart"><svg viewBox="0 0 640 320" width="100%" role="img" aria-label="Accuracy against payload '
         'on VisDrone DET val: JPEG, learned bottlenecks and post-hoc splits" xmlns="http://www.w3.org/2000/svg">']
    t = math.floor(y0 * 20) / 20
    while t <= y1:
        if t >= y0:
            o.append(f'<line class="ax" x1="64" x2="620" y1="{Y(t):.1f}" y2="{Y(t):.1f}"/>'
                     f'<text x="56" y="{Y(t) + 4:.1f}" text-anchor="end">{t:.2f}</text>')
        t = round(t + 0.05, 2)
    for kb in (1, 2, 5, 10, 20, 50, 100, 200, 500):
        if x0 <= math.log10(kb) <= x1:
            o.append(f'<line class="ax" x1="{X(kb):.1f}" x2="{X(kb):.1f}" y1="270" y2="274"/>'
                     f'<text x="{X(kb):.1f}" y="288" text-anchor="middle">{kb}</text>')
    o.append('<text x="342" y="308" text-anchor="middle">payload per frame (kB, log scale)</text>'
             '<text x="14" y="144" text-anchor="middle" transform="rotate(-90 14 144)">mAP@[.5:.95]</text>')
    o.append(f'<line x1="64" x2="620" y1="{Y(base):.1f}" y2="{Y(base):.1f}" stroke="var(--muted)" stroke-dasharray="4 3"/>'
             f'<text x="618" y="{Y(base) - 5:.1f}" text-anchor="end">unsplit model {base:.3f}</text>')
    pts = " ".join(f"{X(r['payload_bytes_mean'] / 1e3):.1f},{Y(r['map50_95']):.1f}" for r in jp)
    o.append(f'<polyline points="{pts}" fill="none" stroke="var(--c-heat)" stroke-width="2"/>')
    for r in jp:
        x, y = X(r["payload_bytes_mean"] / 1e3), Y(r["map50_95"])
        o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="var(--c-heat)"/>'
                 f'<text x="{x + 6:.1f}" y="{y + 12:.1f}">q{r["q"]}</text>')
    for r in lb:
        x, y = X(r["payload_bytes_mean"] / 1e3), Y(r["map50_95"])
        lab = f"{r['channels']}{'f' if r.get('stride') == 1 else ''}"
        if r["cut"] == 2:
            o.append(f'<polygon points="{x:.1f},{y - 5:.1f} {x - 5:.1f},{y + 4:.1f} {x + 5:.1f},{y + 4:.1f}" '
                     f'fill="var(--c-hier)"/><text x="{x - 8:.1f}" y="{y - 4:.1f}" text-anchor="end">{lab}</text>')
        else:
            dx = 7 if r.get("stride") == 1 else -8
            o.append(f'<rect x="{x - 4:.1f}" y="{y - 4:.1f}" width="8" height="8" fill="var(--c-fixed)"/>'
                     f'<text x="{x + dx:.1f}" y="{y + (12 if r.get("stride") == 1 else -6):.1f}" '
                     f'text-anchor="{"start" if dx > 0 else "end"}">{lab}</text>')
    for r in ph:
        x, y = X(r["payload_bytes_mean"] / 1e3), Y(r["map50_95_unchanged_check"])
        o.append(f'<polygon points="{x:.1f},{y - 5:.1f} {x + 5:.1f},{y:.1f} {x:.1f},{y + 5:.1f} {x - 5:.1f},{y:.1f}" '
                 f'fill="var(--c-noprice)"/>')
    lg = [("var(--c-heat)", "JPEG q10-q95"), ("var(--c-fixed)", "learned, k4 (f = full resolution)"),
          ("var(--c-hier)", "learned, k2"), ("var(--c-noprice)", "post-hoc INT8 + zstd, k2 and k4")]
    for i, (c, txt) in enumerate(lg):
        yy = 200 + 16 * i
        o.append(f'<rect x="420" y="{yy - 8}" width="10" height="10" fill="{c}"/><text class="ink" x="436" y="{yy + 1}">{txt}</text>')
    o.append('</svg><figcaption>Accuracy against payload on VisDrone2019-DET val (548 images), every payload measured on '
             'the same frames; labels on the learned codes give their channels. Data: '
             '<code>experiments/results/learned_bottleneck/summary.json</code>.</figcaption></figure>\n')
    return "".join(o)


def numbers():
    s = json.load(open(LB / "summary.json"))
    f = fam(s["learned"])
    tr = json.load(open(LB / f"train_{f[0]['config']}.json"))
    p2 = dict(re.findall(r"\\newcommand\{\\(\w+)\}\{(.*)\}", (ROOT / "paper2" / "generated" / "metrics.tex").read_text()))
    return f, tr, p2


def section():
    s, sy, t1, t2 = tables()
    f, tr, p2 = numbers()
    win = [r for r in f if r["bytes_saving_vs_jpeg_pct"] is not None and r["bytes_saving_vs_jpeg_pct"] > 0]
    lose = [r for r in f if r["jpeg_map_at_same_bytes"] is not None and r["map50_95"] < r["jpeg_map_at_same_bytes"]]
    best = max(f, key=lambda r: r["map50_95"])
    q90 = next(r for r in s["jpeg"] if r["q"] == 90)
    ph4 = next(r for r in s["posthoc_splits"] if r["cut"] == 4)
    by = sy["learned_beats_image"]["by_t_full"]
    ts = sorted(by, key=float)
    import math
    full = [r for r in f if r.get("stride") == 1 and r["cut"] == 4]
    half = [r for r in f if r.get("stride") == 2 and r["cut"] == 4]
    res_sentence = ""
    if full and half:                            # the closest-sized pair of full- and half-resolution k4 codes
        fb, hb = min(((a, b) for a in full for b in half),
                     key=lambda p: abs(math.log(p[0]["payload_bytes_mean"] / p[1]["payload_bytes_mean"])))
        res_sentence = (f" Resolution matters more than channels: at about the same size, the k4 code at full resolution "
                        f"with {fb['channels']} channels reached {fb['map50_95']:.3f} ({fb['payload_bytes_mean'] / 1e3:.1f} kB), "
                        f"the half-resolution one with {hb['channels']} channels {hb['map50_95']:.3f} "
                        f"({hb['payload_bytes_mean'] / 1e3:.1f} kB).")
    sat_sentence = ""
    if lose:
        big = max(f, key=lambda r: r["map50_95"])
        sat_sentence = (" Not every code wins: " + " and ".join(
            f"{label(r)} ({r['payload_bytes_mean'] / 1e3:.1f} kB, {r['map50_95']:.3f} against JPEG's "
            f"{r['jpeg_map_at_same_bytes']:.3f} at that size)" for r in sorted(lose, key=lambda r: r["payload_bytes_mean"]))
            + f" lose to JPEG; accuracy saturates near {big['map50_95']:.2f}.")
    pw = [g for g in sy["grid"] if str(g["t_full_ms"]) == ts[-1] and g["goodput_mbps"] in by[ts[-1]]["goodput_mbps"]]
    pi_text = ("at no goodput" if not pw else
               f"only up to {by[ts[-1]]['max_goodput_mbps']:.1f} Mbit/s, where no option delivers more than "
               f"{max(max(g['learned']['utility'], g['image']['utility']) for g in pw):.1f} accuracy-weighted on-time "
               f"results per second; above that the image wins")
    return f'''<h3>19.12 Laptop-only additions, part 5: a learned feature-compression baseline, and the second paper (30 Oct 2026)</h3>
<p>Write-up <code>docs/laptop_additions_2026-10-30_part5.md</code>. Part 20 (section 1) left one test open: a learned,
trained compressor for the features. Code <code>evaluation/learned_bottleneck.py</code> (training, evaluation, the JPEG and
post-hoc measurements, figure) and <code>evaluation/learned_bottleneck_system.py</code> (the system model); results
<code>experiments/results/learned_bottleneck/</code>; weights <code>weights/learned_bottleneck/</code>.</p>
<ul>
<li><b>Design</b> (BottleFit / supervised compression, here with the detector frozen): a small encoder (two
convolutions) after layer 2 or 4 of the VisDrone YOLOv8s outputs a few channels at half or full resolution, quantised per
image to 8 bits and coded with zstd-1 (the toolkit's coder); a decoder restores the layer's output and the rest of the
detector is unchanged. Only the encoder and decoder are trained, by distilling the detector's own neck outputs (layers
15, 18, 21) and the cut tensor: {tr['n_train']:,} VisDrone2019-DET training images, {tr['n_holdout']} held out for
monitoring, no labels, {tr['epochs']} epochs. DET val ({f[0]['n']} images) is the test set.</li>
<li><b>Like for like.</b> Every payload is measured on the same DET val frames: the learned codes, JPEG at q10–q95 and
the post-hoc INT8 + zstd splits (through the toolkit's quantiser and wire format). The VisDrone tables of R3
(<code>visdrone_ft_split/</code>) keep the COCO-measured payloads by design, so they were not used for sizes; on VisDrone
frames JPEG q50 is 30.4 kB, not 37.4. The validator's warm-up pass on a dummy frame is excluded from every average.</li>
</ul>
{t1}
{chart()}
<ul>
<li><b>A learned code beats the image on bits.</b> It needs {min(r['bytes_saving_vs_jpeg_pct'] for r in win):.0f}–{max(r['bytes_saving_vs_jpeg_pct'] for r in win):.0f} % fewer
bytes than JPEG for the same accuracy, which no post-hoc split does (k4 INT8 + zstd is {ph4['payload_bytes_mean'] / 1e3:.0f} kB on these
frames).{res_sentence}{sat_sentence}</li>
<li><b>It does not reach the unsplit accuracy.</b> The best code reached {best['map50_95']:.3f} at
{best['payload_bytes_mean'] / 1e3:.1f} kB; JPEG q90 reaches {q90['map50_95']:.3f} at {q90['payload_bytes_mean'] / 1e3:.1f} kB and the unsplit
model {f[0]['base_map50_95']:.3f}. A likely limit is the small decoder with the detector frozen; training the detector with
the bottleneck (as supervised compression does) may go further.</li>
</ul>
<p><b>Does it change the system result?</b> Each option scored with the paper's own model, exactly as its adaptive policy
scores it (expected accuracy-weighted on-time results per second; <code>learned_bottleneck_system.py</code>), over
{len(sy['goodput_mbps'])} goodputs from 0.25 to 50 Mbit/s and the paper's onboard speeds plus the measured Pi:</p>
{t2}
<ul>
<li><b>Only with fast onboard compute and a slow link.</b> The image needs more bits now, so Proposition 1 no longer
applies, but it still needs far less onboard work. With YOLOv8s at {float(ts[0]):.0f} ms per frame a learned code wins up to
{by[ts[0]]['max_goodput_mbps']:.1f} Mbit/s; on the measured Pi ({float(ts[-1]):.0f} ms) {pi_text}, because layers 0..k and the
encoder cost more onboard time than the smaller payload saves.</li>
<li><b>Verdict for the paper.</b> "Send the image" stays the answer for the drone computers measured here, except at the
lowest goodputs; it is no longer a statement about bits alone. The paper now says so (<code>paper/main.tex</code>, section "A Learned Bottleneck", every
number generated by <code>evaluation/make_learned.py</code>).</li>
</ul>
<p><b>The second paper, first draft.</b> <code>paper2/</code> (<code>bash build.sh</code>): the priced controller — energy
pricing on Wi-Fi and the mesh, the objective matched to the forecaster, decision placement by topology, the literature
schedulers and the AccuMO-style planner, the hindsight oracle and calibration (replay), the two-camera swarm, the
whole-system energy view and the negative results; 5 pages, a testbed figure, the decay figure and a results table, every
number generated from the result files (<code>paper2/make_metrics.py</code>, sources in
<code>paper2/generated/metrics_sources.md</code>), every new citation verified via doi.org. What it still needs is listed in
<code>paper2/README.md</code>; chiefly the planner's board campaign.</p>
'''


STATE = ("<li><b>Laptop-only additions, part 5 (19.12, 30 Oct):</b> a learned feature-compression baseline: a small "
         "bottleneck trained at layer 2 or 4 with the detector frozen beats JPEG on bits (fewer bytes for the same "
         "accuracy), but on the Pi it wins end to end only at the lowest goodputs, so \"send the image\" stands for the drone "
         "computers measured; the "
         "second paper's first draft is in <code>paper2/</code>.</li>\n")
LIMIT_OLD = "<b>Limit.</b> A learned, trained compressor for the features could change this; that test is still to do."
LIMIT_NEW = ("<b>Limit.</b> A learned compressor changes the bits but not, on these drone computers, the verdict (19.12): "
             "trained with the detector frozen, it needs fewer bytes than JPEG for the same accuracy, but it does not "
             "reach the unsplit accuracy, and on the Pi it wins end to end only at the lowest goodputs because it needs far "
             "more onboard work. A "
             "compressor trained together with the detector, or faster onboard hardware, may change this.")
LEFT = [("<tr><td>Learned feature-compression baseline for the split result (e.g. Yuan et al. 2022/2024, BottleFit)</td>"
         "<td>The laptop GPU</td><td>1–2 weeks</td></tr>",
         "<tr><td><s>Learned feature-compression baseline for the split result</s> <b>Done 30 Oct</b> (19.12): fewer bytes "
         "than JPEG; on the Pi better end to end only at the lowest goodputs. Open: a bottleneck trained together "
         "with the detector</td>"
         "<td>The laptop GPU</td><td>days</td></tr>"),
        ("<tr><td>Paper: hardware section, claims and citations checked (19.11). Still to do: the controller paper (the "
         "argument of Part 20) and the professor's report</td><td>—</td><td>1–2 weeks</td></tr>",
         "<tr><td>Paper 1: hardware section and the learned bottleneck (19.11–19.12). Paper 2: first draft in "
         "<code>paper2/</code> (19.12); to finish after the planner's board campaign. Final Report updated</td>"
         "<td>The board campaign for paper 2</td><td>a few days</td></tr>")]


def md_row(html_row):
    cells = re.findall(r"<td>(.*?)</td>", html_row)
    return "| " + " | ".join(html_to_md(f"<p>{c}</p>").strip() for c in cells) + " |"


def main():
    h, m = HTML.read_text(), MD.read_text()
    sec = section()
    j = h.index('<h2 id="argument">')
    i = h.find("<h3>19.12 ")
    h = h[:i if 0 <= i < j else j] + sec + h[j:]
    j = m.index("## PART 20")
    i = m.find("### 19.12 ")
    m = m[:i if 0 <= i < j else j] + html_to_md(sec) + m[j:]
    h = re.sub(r"<li><b>Laptop-only additions, part 5 \(19\.12.*?</li>\n", "", h, flags=re.S)
    k = h.index('<div class="box state">')
    k = h.index("<ul>\n", k) + len("<ul>\n")
    h = h[:k] + STATE + h[k:]
    m = re.sub(r"^- \*\*Laptop-only additions, part 5 \(19\.12.*\n", "", m, flags=re.M)
    k = m.index("**State on 26 Oct 2026")
    k = m.index("\n- ", k) + 1
    m = m[:k] + html_to_md("<ul>" + STATE + "</ul>").strip() + "\n" + m[k:]
    if LIMIT_NEW not in h:
        assert h.count(LIMIT_OLD) == 1
        h = h.replace(LIMIT_OLD, LIMIT_NEW)
    lo, ln = html_to_md(f"<p>{LIMIT_OLD}</p>").strip(), html_to_md(f"<p>{LIMIT_NEW}</p>").strip()
    if ln not in m:
        assert m.count(lo) == 1, lo[:60]
        m = m.replace(lo, ln)
    for old, new in LEFT:
        if new not in h:
            assert h.count(old) == 1, old[:60]
            h = h.replace(old, new)
        mo, mn = md_row(old), md_row(new)
        if mn not in m:
            assert m.count(mo) == 1, mo[:80]
            m = m.replace(mo, mn)
    HTML.write_text(h)
    MD.write_text(m)
    print("report updated: 19.12, Part 1 bullet, Part 20 section 1 limit, what is left (2 rows)")


if __name__ == "__main__":
    main()
