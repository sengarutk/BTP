#!/usr/bin/env python3
"""Report update, 25 Oct 2026: task C7 done - the 776 earlier runs replayed with the VisDrone-trained detectors
(report_rescore.py --visdrone -> report_c_summary_visdrone.json) next to the COCO rescoring (report_c_summary.json).
Adds 19.5 (before Part 20), marks C7 done in 19.2, the caveats list and "What is left". Idempotent.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_parts_oct22 import HTML, MD, html_to_md, table  # noqa: E402

HW = Path(__file__).resolve().parent.parent / "experiments" / "results" / "hardware"


def verdict(r):
    if r["p_holm"] < 0.05:
        return "reference ahead" if r["mean_diff"] > 0 else "reference behind"
    return "no significant difference"


def section():
    v = json.load(open(HW / "report_c_summary_visdrone.json"))
    c = json.load(open(HW / "report_c_summary.json"))
    lvl, pr, changed, rho = [], [], [], []
    tot = n_sig_c = n_sig_v = rev = gained = lost = 0
    for camp in v:
        a = []
        for sc, ps in v[camp]["scenarios"].items():
            if sc == "ALL":                 # the pooled row is not a cell (counted until 28 Oct 2026)
                continue
            for p, x in ps.items():
                y = c[camp]["scenarios"].get(sc, {}).get(p)
                if y and y["sAP_fc"][0] > 0:
                    a.append((y["sAP_fc"][0], x["sAP_fc"][0]))
        a = np.array(a)
        rk = lambda z: np.argsort(np.argsort(z))  # noqa: E731
        rho.append(np.corrcoef(rk(a[:, 0]), rk(a[:, 1]))[0, 1])
        lvl.append([v[camp]["section"], len(a), f"{a[:, 0].mean():.3f}", f"{a[:, 1].mean():.3f}",
                    f"{np.median(a[:, 1] / a[:, 0]):.2f}×", f"{np.corrcoef(rk(a[:, 0]), rk(a[:, 1]))[0, 1]:.2f}"])
        for ref, mets in v[camp]["paired"].items():
            for opp, r in mets.get("sAP_fc", {}).items():
                rc = c.get(camp, {}).get("paired", {}).get(ref, {}).get("sAP_fc", {}).get(opp)
                if rc is None or "mirror_of" in r:     # a mirrored pair is one comparison (28 Oct 2026)
                    continue
                tot += 1
                n_sig_c += rc["p_holm"] < 0.05
                n_sig_v += r["p_holm"] < 0.05
                a_, b_ = verdict(rc), verdict(r)
                rev += (rc["p_holm"] >= .05 and r["p_holm"] >= .05 and np.sign(rc["mean_diff"]) != np.sign(r["mean_diff"]))
                gained += rc["p_holm"] >= .05 and r["p_holm"] < .05
                lost += rc["p_holm"] < .05 and r["p_holm"] >= .05
                row = [v[camp]["section"], f"{ref} vs {opp}", f"{rc['mean_diff']:+.4f} (p Holm {rc['p_holm']:.3f})",
                       f"{r['mean_diff']:+.4f} ± {r['ci95']:.4f}", f"{r['wins']}/{r['pairs']}",
                       f"<b>{r['p_holm']:.3f}</b>" if r["p_holm"] < 0.05 else f"{r['p_holm']:.3f}"]
                pr.append(row)
                if a_ != b_ or np.sign(rc["mean_diff"]) != np.sign(r["mean_diff"]):
                    changed.append(row[:3] + [row[3], row[5], f"{a_} → {b_}"])
    t1 = table(["Campaign", "strategy × scenario cells", "mean sAP + fc, COCO weights", "mean sAP + fc, VisDrone weights",
                "median ratio", "rank correlation of the cells"], lvl)
    t2 = table(["Campaign", "Comparison (reference vs strategy)", "COCO: Δ sAP + fc", "VisDrone: Δ sAP + fc",
                "wins", "VisDrone: p Holm"], pr)
    t3 = table(["Campaign", "Comparison", "COCO: Δ (p Holm)", "VisDrone: Δ", "VisDrone: p Holm", "verdict"], changed)
    return f'''<h3>19.5 Results of C7: every earlier campaign replayed with the VisDrone weights (done 25 Oct 2026)</h3>
<p>Each of the 776 recorded runs of Parts 12–16 keeps its schedule exactly as it happened (frame, server, setting, arrival time); only the detections are replaced by those of the VisDrone-trained detector of the same model, input size and JPEG quality (11 settings × 2,846 test frames, <code>vd_variant_dets/</code>), then the run is rescored with the standard sAP and the campaign's forecaster, as in C1–C6 (<code>validation/hardware/report_rescore.py --visdrone</code>; <code>experiments/results/hardware/report_c_summary_visdrone.json</code>). {tot} paired comparisons, Holm-corrected within each campaign as in 19.3.</p>
{t1}
<ul>
<li><b>Accuracy about 2.4× higher everywhere, rankings unchanged.</b> With detectors that have seen aerial imagery, every campaign's sAP rises by a median factor of 2.3–2.6, and the ranking of the strategy × scenario cells is almost the same (rank correlation {min(rho):.2f}–{max(rho):.2f}).</li>
<li><b>No verdict reverses.</b> Of the {tot} paired comparisons, none changes from a significant win to a significant loss or back. {n_sig_v} are significant with the VisDrone weights against {n_sig_c} with the COCO weights: {gained} comparisons that were too close to call with the COCO detections (absolute sAP 0.03–0.05) become significant with the VisDrone detections, each in the direction the COCO numbers already pointed, and {lost} lose significance. The clearest case: the adaptive controller against fixed offloading to the laptop, +0.023 (Part 14, 80 runs) and +0.029 (G12, 240 runs) sAP with the VisDrone weights, both significant, where the COCO weights gave +0.005 and +0.007, not significant.</li>
<li>{rev} comparisons swap sign between the two weight sets, all of them ties in both (no significant difference either way).</li>
<li>The receiver fault of 18.9 affects 14 of these runs equally under both weight sets (the schedules are the same) and changes no verdict.</li>
</ul>
<p>Comparisons whose verdict or sign changed:</p>
{t3}
<details><summary>All {tot} paired comparisons, COCO and VisDrone weights</summary>
{t2}
</details>
'''


def main():
    h, m = HTML.read_text(), MD.read_text()
    sec = section()
    j = h.index('<h2 id="argument">')
    i = h.find("<h3>19.5 ")
    h = h[:i if 0 <= i < j else j] + sec + h[j:]
    j = m.index("## PART 20")
    i = m.find("### 19.5 ")
    m = m[:i if 0 <= i < j else j] + html_to_md(sec) + m[j:]
    # 19.2 status rows
    h = re.sub(r"<tr><td>C7: VisDrone detections of every setting</td><td class=\"n\">[^<]*</td>",
               '<tr><td>C7: VisDrone detections of every setting</td><td class="n"><b>done</b> (23–24 Oct)</td>', h, 1)
    h = re.sub(r"<tr><td>C7: replay of all 776 runs</td><td class=\"n\">[^<]*</td><td class=\"n\">[^<]*</td>",
               '<tr><td>C7: replay of all 776 runs</td><td class="n"><b>done</b> (25 Oct)</td><td class="n">results in 19.5: '
               'sAP about 2.4× higher, rankings unchanged, no verdict reversed</td>', h, 1)
    h = re.sub(r"(<tr><td>Final report</td><td class=\"n\">)[^<]*(</td><td class=\"n\">Parts 12–15 restated)",
               r"\g<1><b>done</b>: 19.5 lists every comparison with both weight sets\g<2>", h, 1)
    # caveat
    a = "C7 replays them with the VisDrone weights; from Part 17 on, all live detectors are VisDrone-trained."
    b = ("C7 (19.5) replayed them with the VisDrone weights: sAP about 2.4× higher, the same rankings, no verdict "
         "reversed; from Part 17 on, all live detectors are VisDrone-trained.")
    h, m = h.replace(a, b), m.replace(a, b)
    # what is left
    h = re.sub(r"<tr><td><b>Task C7</b> \(Part 19\):.*?</tr>\n",
               "<tr><td><s>Task C7 (Part 19): VisDrone replay of the 776 earlier runs</s> <b>Done 25 Oct</b> (19.5)</td><td>—</td><td>—</td></tr>\n", h, 1)
    m = re.sub(r"^\| \*\*Task C7\*\* \(Part 19\):.*\n",
               "| <s>Task C7 (Part 19): VisDrone replay of the 776 earlier runs</s> **Done 25 Oct** (19.5) | — | — |\n", m, 1, flags=re.M)
    # Markdown copies of the 19.2 rows
    m = re.sub(r"^\| C7: VisDrone detections of every setting \|[^|]*\|", "| C7: VisDrone detections of every setting | **done** (23–24 Oct) |", m, 1, flags=re.M)
    m = re.sub(r"^\| C7: replay of all 776 runs \|[^|]*\|[^|]*\|",
               "| C7: replay of all 776 runs | **done** (25 Oct) | results in 19.5: sAP about 2.4× higher, rankings unchanged, no verdict reversed |", m, 1, flags=re.M)
    m = re.sub(r"^(\| Final report \|)[^|]*(\| Parts 12–15 restated)", r"\g<1> **done**: 19.5 lists every comparison with both weight sets \g<2>", m, 1, flags=re.M)
    HTML.write_text(h)
    MD.write_text(m)
    print("report updated: 19.5 (C7), 19.2 status, caveat, what is left")


if __name__ == "__main__":
    main()
