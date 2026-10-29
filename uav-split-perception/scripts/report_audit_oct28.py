#!/usr/bin/env python3
"""Report update, 28 Oct 2026: apply the corrections of docs/audit_2026-10-28.md to the Results Brief (.md and .html).

Part 1 (tables, regenerated from data): 19.3 and the two 19.5 comparison tables from report_c_summary(_visdrone).json
(Holm over the unique comparisons of a campaign, mirrored pairs listed once), and the 19.5 campaign table without the
pooled ALL cells.
Part 2 (text): every other correction, each an exact replacement that must match once in each file (or the stated
number of times), so a stale or ambiguous edit stops the script instead of silently doing nothing.
usage: report_audit_oct28.py [--dry] [--text=report_audit_oct28_text2]      (the originals are archived in
       experiments/results/hardware/_superseded/report_before_audit_oct28/docs/)
"""
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
HW = ROOT / "experiments" / "results" / "hardware"
DOCS = ROOT.parent
MD, HTML = DOCS / "AEGIS-UAV Results Brief.md", DOCS / "AEGIS-UAV Results Brief.html"
C = json.load(open(HW / "report_c_summary.json"))
V = json.load(open(HW / "report_c_summary_visdrone.json"))


def unique_rows(S):
    """(campaign, ref, policy, record) for every comparison of S once (mirrored pairs skipped), in table order."""
    out = []
    for camp, cs in S.items():
        for ref, mets in cs["paired"].items():
            for p, r in sorted(mets["sAP_fc"].items(), key=lambda x: -x[1]["mean_diff"]):
                if "mirror_of" not in r:
                    out.append((camp, ref, p, r))
    return out


def verdict(r):
    if r["p_holm"] >= 0.05:
        return "no significant difference"
    return "reference ahead" if r["mean_diff"] > 0 else "reference behind"


def table(fmt, header, rows):
    if fmt == "md":
        return "\n".join(["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"] +
                         ["| " + " | ".join(r) + " |" for r in rows])
    b = lambda s: re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)  # noqa: E731
    return "\n".join(["<div class=\"tbl\"><table>", "<tr>" + "".join(f"<th>{h}</th>" for h in header) + "</tr>"] +
                     ["<tr><td>" + b(r[0]) + "</td>" + "".join(f"<td class=\"n\">{b(x)}</td>" for x in r[1:]) + "</tr>"
                      for r in rows] + ["</table></div>"])


def t193():
    rows = []
    for camp, ref, p, r in unique_rows(C):
        q = C[camp]["paired"][ref]["sAP_quality_fc"][p]["p_holm"]
        m = C[camp]["paired"][ref]["sAP_masked_fc"][p]["p_holm"]
        rows.append([C[camp]["section"], f"{ref} vs {p}", f"{r['mean_diff']:+.4f} ± {r['ci95']:.4f}",
                     f"{r['wins']}/{r['pairs']}", f"{r['p_perm']:.3f}", f"**{r['p_holm']:.3f}**", f"{q:.3f}", f"{m:.3f}"])
    return ["Campaign", "Comparison", "Δ sAP (standard + fc)", "wins", "p", "p Holm", "p Holm, quality rule",
            "p Holm, masked"], rows


def t195():
    changed, full = [], []
    for camp, ref, p, v in unique_rows(V):
        c = C[camp]["paired"][ref]["sAP_fc"][p]
        hv = f"**{v['p_holm']:.3f}**" if v["p_holm"] < 0.05 else f"{v['p_holm']:.3f}"
        coco = f"{c['mean_diff']:+.4f} (p Holm {c['p_holm']:.3f})"
        vd = f"{v['mean_diff']:+.4f} ± {v['ci95']:.4f}"
        full.append([V[camp]["section"], f"{ref} vs {p}", coco, vd, f"{v['wins']}/{v['pairs']}", hv])
        if verdict(c) != verdict(v) or np.sign(c["mean_diff"]) != np.sign(v["mean_diff"]):
            changed.append([V[camp]["section"], f"{ref} vs {p}", coco, vd, hv, f"{verdict(c)} → {verdict(v)}"])
    return (["Campaign", "Comparison", "COCO: Δ (p Holm)", "VisDrone: Δ", "VisDrone: p Holm", "verdict"], changed,
            ["Campaign", "Comparison (reference vs strategy)", "COCO: Δ sAP + fc", "VisDrone: Δ sAP + fc", "wins",
             "VisDrone: p Holm"], full)


def t195_cells():
    rk = lambda x: np.argsort(np.argsort(x))  # noqa: E731
    rows, stats = [], {"rho": [], "ratio": []}
    for camp in C:
        cells = [(sc, p) for sc in C[camp]["scenarios"] if sc != "ALL" for p in C[camp]["scenarios"][sc]]
        a = np.array([C[camp]["scenarios"][sc][p]["sAP_fc"][0] for sc, p in cells])
        b = np.array([V[camp]["scenarios"][sc][p]["sAP_fc"][0] for sc, p in cells])
        rho, ratio = float(np.corrcoef(rk(a), rk(b))[0, 1]), float(np.median(b / a))
        stats["rho"].append(rho), stats["ratio"].append(ratio)
        rows.append([C[camp]["section"], str(len(cells)), f"{a.mean():.3f}", f"{b.mean():.3f}", f"{ratio:.2f}×",
                     f"{rho:.2f}"])
    return (["Campaign", "strategy × scenario cells", "mean sAP + fc, COCO weights", "mean sAP + fc, VisDrone weights",
             "median ratio", "rank correlation of the cells"], rows, stats)


def replace_table(text, fmt, header_start, new):
    """Replace the table whose header row starts with header_start (md: '| A | B'; html: '<tr><th>A</th><th>B')."""
    if fmt == "md":
        i = text.index(header_start)
        j = text.find("\n\n", i)
        assert text.count(header_start) == 1, header_start
        return text[:i] + new + text[j:]
    i = text.index(header_start)
    assert text.count(header_start) == 1, header_start
    s = text.rfind("<div class=\"tbl\"><table>", 0, i)
    assert i - s < 40, "table wrapper not found"
    e = text.index("</table></div>", i) + len("</table></div>")
    return text[:s] + new + text[e:]


def tables(md, html):
    h, rows = t193()
    hc, changed, hf, full = t195()
    hcell, cells, st = t195_cells()
    for fmt in ("md", "html"):
        t = md if fmt == "md" else html
        hdr = (lambda cols: "| " + " | ".join(cols) + " |") if fmt == "md" else \
              (lambda cols: "<tr>" + "".join(f"<th>{c}</th>" for c in cols[:3]))
        t = replace_table(t, fmt, hdr(h), table(fmt, h, rows))
        t = replace_table(t, fmt, hdr(hc), table(fmt, hc, changed))
        t = replace_table(t, fmt, hdr(hf), table(fmt, hf, full))
        t = replace_table(t, fmt, hdr(hcell), table(fmt, hcell, cells))
        if fmt == "md":
            md = t
        else:
            html = t
    uv, uc = unique_rows(V), unique_rows(C)
    n_sig = sum(r["p_holm"] < 0.05 for *_, r in uv)
    n_sig_c = sum(r["p_holm"] < 0.05 for *_, r in uc)
    pair = [(C[c]["paired"][f]["sAP_fc"][p], r) for c, f, p, r in uv]
    hold = [(c, f, p) for c, f, p, r in uc       # standard vs quality holding rule disagree on significance (COCO)
            if (r["p_holm"] < 0.05) != (C[c]["paired"][f]["sAP_quality_fc"][p]["p_holm"] < 0.05)]
    info = {"unique": len(uv), "sig_vd": n_sig, "sig_coco": n_sig_c, "changed": len(changed),
            "gained": sum(a["p_holm"] >= .05 and b["p_holm"] < .05 for a, b in pair),
            "lost": sum(a["p_holm"] < .05 and b["p_holm"] >= .05 for a, b in pair),
            "swap": sum(np.sign(a["mean_diff"]) != np.sign(b["mean_diff"]) for a, b in pair),
            "hold_disagree": hold,
            "rho": (min(st["rho"]), max(st["rho"])), "ratio": (min(st["ratio"]), max(st["ratio"]))}
    return md, html, info


def wrap_tables(html):
    """Every <table> inside a <div class="tbl"> (horizontal scroll on phones); 5 tables lacked it."""
    out, i, n = [], 0, 0
    while True:
        j = html.find("<table", i)
        if j < 0:
            out.append(html[i:])
            return "".join(out), n
        k = html.index("</table>", j) + len("</table>")
        if 'class="tbl"' in html[max(0, j - 30):j]:
            out.append(html[i:k])
        else:
            out.append(html[i:j] + '<div class="tbl">' + html[j:k] + "</div>")
            n += 1
        i = k


def md2html(s):
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", s)


EDITS = []          # (old, new, count, which): which = "both" (md form, html derived), "md", "html"


def E(old, new, count=1, which="both", html_old=None, html_new=None):
    EDITS.append((old, new, count, which, html_old, html_new))


def apply_edits(md, html, dry):
    bad = 0
    for old, new, count, which, hold, hnew in EDITS:
        for fmt in ("md", "html"):
            if which not in ("both", fmt):
                continue
            o, n = (old, new) if fmt == "md" else (hold or md2html(old), hnew or md2html(new))
            t = md if fmt == "md" else html
            k = t.count(o)
            if k != count:
                bad += 1
                print(f"[{fmt}] expected {count}, found {k}: {o[:110]!r}")
                continue
            t = t.replace(o, n)
            if fmt == "md":
                md = t
            else:
                html = t
    if bad:
        raise SystemExit(f"{bad} edits did not match; nothing written")
    return md, html


def main():
    dry = "--dry" in sys.argv
    md, html = MD.read_text(encoding="utf8"), HTML.read_text(encoding="utf8")
    md, html, info = tables(md, html)
    print("tables:", info)
    import importlib                                # the text corrections, kept in their own file(s);
    mod = next((x.split("=", 1)[1] for x in sys.argv if x.startswith("--text=")), "report_audit_oct28_text")
    txt = importlib.import_module(mod)              # --text=report_audit_oct28_text2 for the second pass
    txt.register(E, info)
    md, html = apply_edits(md, html, dry)
    html, nw = wrap_tables(html)
    print("tables given the scroll wrapper:", nw)
    if dry:
        print("dry run: nothing written")
        return
    MD.write_text(md, encoding="utf8")
    HTML.write_text(html, encoding="utf8")
    print("written", MD.name, HTML.name)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
