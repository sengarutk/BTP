#!/usr/bin/env python3
"""Independent audit of the laptop-strengthening numbers (17 Nov 2026), in both papers' generated macros.

Written separately from the analysis scripts, from the raw result files where possible:
  - equivalence: paired differences from the score caches, 90 % t-intervals with a printed t table (one-sided 0.95)
  - recalibration: the held-out day's ECE recomputed from the raw frame logs with the training days' isotonic fit
    (scikit-free pool-adjacent-violators written here), and the per-path on-time shares of frames predicted late
  - the late-path rule's counterfactual: frames acted on, recounted from the logs
  - paper 1: T10 model check recomputed from the sweep files; the Jetson bench times; the literature numbers against
    the papers' tables as quoted in published_splits.json
  - camera rate: the measured 30-fps sAP against the cache
Exit code 1 on any mismatch beyond a macro's printed precision. Output: docs/audit_nov17.md
usage: python scripts/audit_nov17.py
"""
import datetime as dt
import glob
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
H = ROOT / "experiments" / "results" / "hardware"
T95_ONE = {2: 2.920, 3: 2.353, 4: 2.132, 5: 2.015, 8: 1.860, 9: 1.833}      # Student t, one-sided 0.95


def macros(p):
    out = {}
    for m in re.finditer(r"\\newcommand\{\\(\w+)\}\{(.*)\}\s*$", Path(p).read_text(), re.M):
        out[m.group(1)] = m.group(2).replace("\\textminus{}", "-").replace("{,}", ",")
    return out


M2 = macros(ROOT / "paper2" / "generated" / "metrics.tex")
M1 = macros(ROOT / "paper" / "generated_tables" / "board_metrics.tex")
rows, bad = [], [0]


def check(name, got, mac):
    if mac is None:
        rows.append((name, f"{got:.6g}", "—", "MISSING MACRO"))
        bad[0] += 1
        return
    mv = float(mac.replace(",", "").lstrip("+"))
    dec = len(mac.split(".")[1]) if "." in mac else 0
    ok = abs(got - mv) <= 0.5 * 10 ** -dec + 1e-9
    bad[0] += not ok
    rows.append((name, f"{got:.6g}", mac, "ok" if ok else "MISMATCH"))


def paired(camp, scs, a, b, key="sAP_fc"):
    c = json.load(open(H / f"vid_campaign_{camp}" / "_eval_cache_mesh.json"))
    d = [c[f"{sc}__{a}__r{r}"][key] - c[f"{sc}__{b}__r{r}"][key] for sc in scs for r in range(1, 10)
         if f"{sc}__{a}__r{r}" in c and f"{sc}__{b}__r{r}" in c]
    d = np.array(d)
    se = d.std(ddof=1) / math.sqrt(len(d))
    t = T95_ONE[len(d) - 1]
    return d.mean() - t * se, d.mean() + t * se, len(d)


def main():
    # equivalence (paper 2)
    for lab, camp, scs, a, b, nm in (("no prices", "mesh2", ("static_good", "mesh_mission", "multihop"), "noprice", "v41", "NoPrice"),
                                     ("heat price", "mesh2", ("static_good", "mesh_mission", "multihop"), "heat", "v41", "Heat"),
                                     ("final vs v4.1", "final_nov", ("mesh_mission", "multihop"), "v41final", "v41", "Fin"),
                                     ("final vs v4.1, multihop", "final_nov", ("multihop",), "v41final", "v41", "FinMulti"),
                                     ("capped hold", "heat_nov", ("mission",), "v41cap", "v41", "Cap"),
                                     ("capped hold + guard", "heat_nov", ("mission",), "v41guard", "v41", "CapGuard"),
                                     ("budget 2.4 vs 2.8", "budget_nov", ("mesh_mission", "multihop"), "v41final24", "v41final", "Budget")):
        lo, hi, n = paired(camp, scs, a, b)
        check(f"equivalence {lab}: 90 % CI low", lo, M2.get(f"Eq{nm}Lo"))
        check(f"equivalence {lab}: 90 % CI high", hi, M2.get(f"Eq{nm}Hi"))
        check(f"equivalence {lab}: pairs", n, M2.get(f"Eq{nm}Pairs"))
        eqv = (-0.005 < lo) and (hi < 0.005)
        rows.append((f"equivalence {lab}: shown", str(eqv), M2.get(f"Eq{nm}Equiv"),
                     "ok" if (eqv and M2.get(f"Eq{nm}Equiv") == "yes") or (not eqv and M2.get(f"Eq{nm}Equiv") == "no") else "MISMATCH"))
        bad[0] += rows[-1][3] != "ok"
    # recalibration (paper 2): raw frame logs, split by run file date
    camps = ("mesh4 energy_nov relaynoise_nov topology_nov fps_nov heat_nov heat_nov2 plus_nov2 two_nov two_cap "
             "final_nov heat_final dvfs_heat dvfs_short budget_nov fix_nov").split()
    P, Y, S, TR = [], [], [], []
    for c in camps:
        for f in sorted((H / f"vid_campaign_{c}").glob("a2_*.json")):
            day = dt.date.fromtimestamp(f.stat().st_mtime)
            run = json.load(open(f))
            for fr in run.get("frames", []):
                if fr.get("pred"):
                    P.append(fr["pred"]["p_on"])
                    Y.append(1.0 if fr.get("lat_ms") is not None and fr["lat_ms"] <= run.get("deadline_ms", 300.0) else 0.0)
                    S.append(fr.get("server"))
                    TR.append(day < dt.date(2026, 11, 16))
    P, Y, S, TR = map(np.array, (P, Y, S, TR))

    def ece(p, y):
        e = np.linspace(0, 1, 11)
        b = np.clip(np.digitize(p, e) - 1, 0, 9)
        return sum((b == k).sum() / len(p) * abs(p[b == k].mean() - y[b == k].mean()) for k in range(10) if (b == k).any())

    def iso(x, y):            # pool adjacent violators, blocks as (start x, mean, weight)
        o = np.argsort(x, kind="stable")
        blocks = []
        for xv, yv in zip(x[o], y[o]):
            if blocks and blocks[-1][0] == xv:
                bx, bm, bw = blocks[-1]
                blocks[-1] = (bx, (bm * bw + yv) / (bw + 1), bw + 1)
            else:
                blocks.append((xv, yv, 1.0))
            while len(blocks) > 1 and blocks[-2][1] > blocks[-1][1]:
                (x1, m1, w1), (_, m2, w2) = blocks[-2], blocks[-1]
                blocks[-2:] = [(x1, (m1 * w1 + m2 * w2) / (w1 + w2), w1 + w2)]
        xs = np.array([b[0] for b in blocks])
        ms = np.array([b[1] for b in blocks])
        return lambda q: ms[np.clip(np.searchsorted(xs, q, side="right") - 1, 0, len(ms) - 1)]

    te = ~TR
    check("held-out frames", te.sum(), M2.get("RcTestFrames"))
    check("held-out ECE, logged p_on", ece(P[te], Y[te]), M2.get("RcEceRaw"))
    check("held-out ECE, isotonic (one map)", ece(iso(P[TR], Y[TR])(P[te]), Y[te]), M2.get("RcEceIso"))
    for s_, nm in (("jetson", "Jet"), ("laptop", "Lap")):
        m = te & (S == s_)
        check(f"held-out ECE, per-path isotonic, {s_}", ece(iso(P[TR & (S == s_)], Y[TR & (S == s_)])(P[m]), Y[m]),
              M2.get(f"RcPathEce{nm}"))
        check(f"{s_}: frames predicted late, on time %", 100 * Y[m & (P < 0.5)].mean(), M2.get(f"Rc{nm}LowOn"))
    # T10 model check (paper 1)
    pr = json.load(open(H / "t10" / "t10_prediction.json"))
    cells = []
    for f in glob.glob(str(H / "t10" / "sweep" / "*.json")):
        if f.endswith("__htb.json"):
            continue
        d = json.load(open(f))
        q = pr["by_rate"][str(float(d["rate_mbit"]))][d["option"]]
        cells.append((d["rate_mbit"], d["option"], q["fps"] * q["p_on"], d["on_time_fps"]))
    agg = {}
    for r_, o, pp, mm in cells:
        agg.setdefault((r_, o), [pp, []])[1].append(mm)
    big = [(p_, np.mean(m_)) for p_, m_ in agg.values() if max(p_, np.mean(m_)) >= 1.0]
    check("T10 model: median |error| % (cells >= 1/s)", 100 * np.median([abs(p_ - m_) / m_ for p_, m_ in big]), M1.get("BpModelErrPct"))
    check("T10 model: cells", len(agg), M1.get("BpModelCells"))
    jt = json.load(open(H / "t10" / "t10_bench_jetson2.json"))["options"]
    check("Jetson camera: codes' onboard ms, min", min(jt[c]["onboard_ms_median"] for c in ("k4_c4_w128_d2", "k4_c8_w128_d2", "k2_c8_w128_d2")), M1.get("BpJetCodeMsMin"))
    check("Jetson camera: codes' onboard ms, max", max(jt[c]["onboard_ms_median"] for c in ("k4_c4_w128_d2", "k4_c8_w128_d2", "k2_c8_w128_d2")), M1.get("BpJetCodeMsMax"))
    # literature: Auto-Split's own numbers (Table 7 and 8 normalized latencies as quoted)
    check("Auto-Split advantage vs raw image (1.0 / 0.08)", 1.0 / 0.08, M1.get("BpLitAutoRaw"))
    check("Auto-Split advantage vs JPEG q60 (0.15 / 0.08)", 0.15 / 0.08, M1.get("BpLitAutoMatched"))
    # camera rate: the measured 30-fps value
    c = json.load(open(H / "vid_campaign_fps_nov" / "_eval_cache_mesh.json"))
    check("30 fps measured sAP_fc (3 runs)", np.mean([c[f"static_good__v41_f30__r{r}"]["sAP_fc"] for r in (1, 2, 3)]), M2.get("FrThirtyMeas"))
    # airflow (paper 2): hot time and power from the replay's own rows, not the summary
    rws = [json.load(open(f)) for f in glob.glob(str(H / "replay" / "airflow_nov16" / "rows" / "mission_240s__*.json"))]
    def mean_of(pol, key):
        v = [x[key] for x in rws if x["policy"] == pol and x["seed"] in (1, 2, 3)]
        return float(np.mean(v)), len(v)
    check("airflow: v4.1 still air, time >= 80 C %", 100 * mean_of("af1_v41", "hot_share")[0], M2.get("AfVHot"))
    check("airflow: unpriced still air, time >= 80 C %", 100 * mean_of("af1_noprice", "hot_share")[0], M2.get("AfNoHot"))
    zero = [k for k in (1.0, 0.9, 0.8, 0.7, 0.6) if mean_of(f"af{k:g}_v41", "hot_share")[0] == 0]
    check("airflow: v4.1 hot time 0 from % lower resistance", 100 * (1 - max(zero)), M2.get("AfVZero"))
    sav = [mean_of(f"af{k:g}_noprice", "pi_w")[0] - mean_of(f"af{k:g}_v41", "pi_w")[0] for k in (1.0, 0.9, 0.8, 0.7, 0.6)]
    check("airflow: energy price saving, min W", min(sav), M2.get("AfSaveMin"))
    check("airflow: energy price saving, max W", max(sav), M2.get("AfSaveMax"))
    out = ["# Independent audit of the laptop-strengthening numbers, 17 Nov 2026", "",
           "`scripts/audit_nov17.py`: own code from the raw result files (score caches, frame logs, sweep files); "
           "compared with paper 2's `generated/metrics.tex` and paper 1's `generated_tables/board_metrics.tex`.", "",
           "| quantity | recomputed | macro | |", "| --- | --- | --- | --- |"]
    out += [f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} |" for r in rows]
    out += ["", f"**{bad[0]} mismatches** in {len(rows)} checks."]
    (ROOT / "docs" / "audit_nov17.md").write_text("\n".join(out) + "\n")
    print("\n".join(out[4:]))
    sys.exit(1 if bad[0] else 0)


if __name__ == "__main__":
    main()
