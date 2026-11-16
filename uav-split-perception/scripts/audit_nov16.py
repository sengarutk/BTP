#!/usr/bin/env python3
"""Independent audit of the board numbers in both papers (16 Nov 2026).

Written separately from scripts/report_mesh_nov16.py (the generator), reading only the raw result files:
  A. re-scores a sample of runs from their frame logs (validation/hardware/mesh_summary.score, no cache) and checks
     the cached scores every summary is built from;
  B. recomputes the headline board macros of paper 2 (paper2/generated/metrics.tex) and paper 1
     (paper/generated_tables/board_metrics.tex) with its own code: heat from the Pi's temperature log, paired
     differences with a Student-t interval and p-value of its own (regularised incomplete beta), cell means, frame
     shares, the T10 sweep, the pull bench;
  C. prints every comparison, and exits non-zero on any mismatch beyond the macro's printed precision.
usage: python scripts/audit_nov16.py [--no-rescore]   -> docs/audit_nov16.md
"""
import argparse
import glob
import json
import math
import random
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
H = ROOT / "experiments" / "results" / "hardware"
T975 = {2: 4.303, 3: 3.182, 4: 2.776}          # Student t, two-sided 95 %, by degrees of freedom


def macros(path):
    out = {}
    for m in re.finditer(r"\\newcommand\{\\(\w+)\}\{(.*)\}\s*$", Path(path).read_text(), re.M):
        out[m.group(1)] = m.group(2).replace("\\textminus{}", "-").replace("{,}", ",").replace("$", "")
    return out


def betacf(a, b, x):                      # Lentz continued fraction for the incomplete beta (Numerical Recipes 6.4)
    qab, qap, qam, c, d = a + b, a + 1, a - 1, 1.0, 1 - (a + b) * x / (a + 1)
    d = 1 / (d if abs(d) > 1e-300 else 1e-300)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        for aa in (m * (b - m) * x / ((qam + m2) * (a + m2)), -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))):
            d = 1 + aa * d
            d = 1 / (d if abs(d) > 1e-300 else 1e-300)
            c = 1 + aa / c if abs(1 + aa / c) > 1e-300 else 1e-300
            h *= d * c
        if abs(d * c - 1) < 1e-14:
            break
    return h


def t_two_sided_p(t, df):
    x = df / (df + t * t)
    lnb = math.lgamma(df / 2 + 0.5) - math.lgamma(df / 2) - math.lgamma(0.5)
    bt = math.exp(lnb + (df / 2) * math.log(x) + 0.5 * math.log(1 - x))
    ib = bt * betacf(df / 2, 0.5, x) / (df / 2) if x < (df / 2 + 1) / (df / 2 + 0.5 + 1) else \
        1 - bt * betacf(0.5, df / 2, 1 - x) / 0.5
    return ib                               # I_x(df/2, 1/2) is the two-sided p-value


def runs_of(camp, sc, st):
    return sorted(glob.glob(str(H / f"vid_campaign_{camp}" / f"a2_{sc}__{st}__r[0-9].json")))


def cache(camp):
    return json.load(open(H / f"vid_campaign_{camp}" / "_eval_cache_mesh.json"))


def pair(camp, sc, a, b, metric="sAP_fc", cams=("",)):
    c = cache(camp)
    reps = sorted({int(re.search(r"__r(\d+)", k).group(1)) for k in c if k.startswith(f"{sc}__{a}__")})
    d = np.array([c[f"{sc}__{a}__r{r}{cm}"][metric] - c[f"{sc}__{b}__r{r}{cm}"][metric] for r in reps for cm in cams
                  if f"{sc}__{a}__r{r}{cm}" in c and f"{sc}__{b}__r{r}{cm}" in c])
    n = len(d)
    se = float(np.std(d, ddof=1)) / math.sqrt(n)
    return {"mean": float(d.mean()), "ci": T975[n - 1] * se, "wins": int((d > 0).sum()), "n": n,
            "p": t_two_sided_p(abs(d.mean()) / se, n - 1)}


def cellmean(camp, sc, st, metric="sAP_fc"):
    c = cache(camp)
    return float(np.mean([v[metric] for k, v in c.items() if re.fullmatch(rf"{sc}__{st}__r\d+", k)]))


def temp_log(f):
    me = json.load(open(f))["measured_energy"]
    L = np.array(me["log_t_w_c"], float)
    C = np.array(me["clock_log_t_mhz_flags"], float)
    return L[:, 0], L[:, 2], C


def peak_hot(f, thr=80.0):
    t, T, C = temp_log(f)
    w = np.r_[t[1:] - t[:-1], 0.0]          # each sample holds until the next one
    return float(T.max()), 100 * float(w[T >= thr].sum()) / float(t[-1]), int(((C[:, 2].astype(int) >> 2) & 1).sum())


def share(camp, sc, st, server):
    n = tot = 0
    lat = []
    for f in runs_of(camp, sc, st):
        for fr in json.load(open(f))["frames"]:
            if fr.get("server"):
                tot += 1
                if fr["server"] == server:
                    n += 1
                    if fr.get("lat_ms"):
                        lat.append(fr["lat_ms"])
    return 100 * n / tot, float(np.median(lat))


class Audit:
    def __init__(self):
        self.rows, self.bad = [], 0

    def check(self, name, got, macro, tol=None):
        if macro is None:
            self.rows.append((name, got, "—", "no macro"))
            return
        try:
            mv = float(str(macro).replace(",", "").lstrip("+"))
        except ValueError:
            self.rows.append((name, got, macro, "not numeric"))
            return
        dec = len(str(macro).split(".")[1]) if "." in str(macro) else 0
        tol = tol if tol is not None else 0.5 * 10 ** -dec + 1e-9
        ok = abs(got - mv) <= tol
        self.bad += not ok
        self.rows.append((name, f"{got:.6g}", macro, "ok" if ok else "MISMATCH"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-rescore", action="store_true")
    a = ap.parse_args()
    M2 = macros(ROOT / "paper2" / "generated" / "metrics.tex")
    M1 = macros(ROOT / "paper" / "generated_tables" / "board_metrics.tex")
    A = Audit()

    # A. re-score a sample of runs from their frame logs, against the cached scores
    resc = []
    if not a.no_rescore:
        sys.path.insert(0, str(ROOT / "validation" / "hardware"))
        from mesh_summary import score
        rnd = random.Random(16)
        pool = [f for c in ("final_nov", "fix_nov", "heat_nov", "two_cap", "topology_nov", "budget_nov")
                for f in [rnd.choice(sorted(glob.glob(str(H / f"vid_campaign_{c}" / "a2_*.json"))))]]
        for f in pool:
            key, s = score(f)
            c = cache(Path(f).parent.name.replace("vid_campaign_", ""))[key]
            for m in ("sAP", "sAP_fc", "pi_w", "deadline_met_fps"):
                ok = abs(s[m] - c[m]) < 1e-9
                A.bad += not ok
                resc.append((Path(f).parent.name + "/" + key, m, f"{s[m]:.6f}", f"{c[m]:.6f}", "ok" if ok else "MISMATCH"))

    # B. paper 2: heat on the 24-min mission
    hv = [peak_hot(f) for f in runs_of("heat_nov", "mission", "v41")]
    hc = [peak_hot(f) for f in runs_of("heat_nov", "mission", "v41cap")]
    hg = [peak_hot(f) for f in runs_of("heat_nov2", "mission", "v41guard765")]
    hf = [peak_hot(f) for f in runs_of("heat_final", "mission", "v41final")]
    hg78 = [peak_hot(f) for f in runs_of("heat_nov", "mission", "v41guard")]
    A.check("v4.1 hot time min %", min(h[1] for h in hv), M2.get("BdHoldHotMin"))
    A.check("v4.1 hot time max %", max(h[1] for h in hv), M2.get("BdHoldHotMax"))
    A.check("v4.1 throttled samples min", min(h[2] for h in hv), M2.get("BdHoldThrMin"))
    A.check("capped hold hot max %", max(h[1] for h in hc), M2.get("BdCapHotMax"))
    A.check("capped hold peak max", max(h[0] for h in hc), M2.get("BdCapPeakMax"))
    A.check("guard 76.5 peak min", min(h[0] for h in hg), M2.get("BdGuardPeakMin"))
    A.check("guard 76.5 peak max", max(h[0] for h in hg), M2.get("BdGuardPeakMax"))
    A.check("guard 76.5 hot max %", max(h[1] for h in hg), M2.get("BdGuardHotMax"))
    A.check("final peak", max(h[0] for h in hf), M2.get("BdFinPeak"))
    over = [h[0] - 76.5 for h in hg] + [h[0] - 78.0 for h in hg78]
    A.check("overshoot min", min(over), M2.get("BdDeltaFastMin"))
    A.check("overshoot max (delta_fast)", max(over), M2.get("BdDeltaFast"))
    A.check("guarded runs", len(over), M2.get("BdGuardedRuns"))
    for st, camp, mc in (("v41", "heat_nov", "BdHoldSap"), ("v41cap", "heat_nov", "BdCapSap"),
                         ("v41guard765", "heat_nov2", "BdGuardSap"), ("v41final", "heat_final", "BdFinSap")):
        A.check(f"24-min sAP {st}", cellmean(camp, "mission", st), M2.get(mc))
    # the final comparison, 5 pairs per scenario
    for sc, s in (("mesh_mission", "Mis"), ("multihop", "Multi")):
        for b, nm in (("v41", "V"), ("accumo", "Acc"), ("leaf", "Leaf")):
            p = pair("final_nov", sc, "v41final", b)
            A.check(f"final - {b}, {sc}", p["mean"], M2.get(f"BdFinVs{nm}{s}"))
            A.check(f"  CI", p["ci"], M2.get(f"BdFinVs{nm}{s}Ci"))
            A.check(f"  ahead of 5", p["wins"], M2.get(f"BdFinVs{nm}{s}Wins"))
        A.check(f"final sAP {sc}", cellmean("final_nov", sc, "v41final"), M2.get(f"BdFinSap{s}"))
        A.check(f"final W {sc}", cellmean("final_nov", sc, "v41final", "pi_w"), M2.get(f"BdFinW{s}"))
        for st, nm in (("accumo", "Acc"), ("leaf", "Leaf")):
            A.check(f"{st} sAP {sc}", cellmean("final_nov", sc, st), M2.get(f"Bd{nm}Sap{s}"))
            A.check(f"{st} W {sc}", cellmean("final_nov", sc, st, "pi_w"), M2.get(f"Bd{nm}W{s}"))
        pb = pair("budget_nov", sc, "v41final24", "v41final", "pi_w")
        A.check(f"budget 2.4-2.8 W, {sc}", pb["mean"], M2.get(f"BdBudgetW{s}"))
        A.check(f"budget 2.4-2.8 sAP, {sc}", pair("budget_nov", sc, "v41final24", "v41final")["mean"], M2.get(f"BdBudgetSap{s}"))
        px = pair("fix_nov", sc, "v41fix24", "v41final24")
        A.check(f"late-path skip, {sc}", px["mean"], M2.get(f"BdFix{s}"))
        A.check(f"  CI", px["ci"], M2.get(f"BdFix{s}Ci"))
        A.check(f"  ahead of 5", px["wins"], M2.get(f"BdFix{s}Wins"))
        A.check(f"  p (own t)", px["p"], None)
    A.check("laptop share, final multihop %", share("final_nov", "multihop", "v41final", "laptop")[0], M2.get("BdLapShare"))
    A.check("laptop median ms, final multihop", share("final_nov", "multihop", "v41final", "laptop")[1], M2.get("BdLapLat"))
    A.check("laptop share before skip %", share("fix_nov", "multihop", "v41final24", "laptop")[0], M2.get("BdFixLapBefore"))
    A.check("laptop share after skip %", share("fix_nov", "multihop", "v41fix24", "laptop")[0], M2.get("BdFixLapAfter"))
    A.check("laptop ms after skip", share("fix_nov", "multihop", "v41fix24", "laptop")[1], M2.get("BdFixLapAfterMs"))
    A.check("jetson ms before skip", share("fix_nov", "multihop", "v41final24", "jetson")[1], M2.get("BdFixJetBefore"))
    A.check("jetson ms after skip", share("fix_nov", "multihop", "v41fix24", "jetson")[1], M2.get("BdFixJetAfter"))
    # two cameras (per camera, both cameras' runs)
    for sc, s in (("static_good", "Stat"), ("mesh_mission", "Mis")):
        c = cache("two_nov")
        for st, nm in (("v41j1", "One"), ("v41j2", "Two")):
            A.check(f"two cameras {st} {sc}", float(np.mean([v["sAP_fc"] for k, v in c.items()
                                                                if re.fullmatch(rf"{sc}__{st}__r\d+_c\d", k)])),
                    M2.get(f"BdTwo{nm}{s}"))
        A.check(f"per-camera cap {sc}", pair("two_cap", sc, "v41j2cap", "v41j2", cams=("_c1", "_c2"))["mean"],
                M2.get(f"BdCap{s}"))
    # pull bench, 8 streams on two camera Pis
    tot = {}
    for f in glob.glob(str(H / "pull_nov_fair" / "*_s8_*.jsonl")):
        mo, r = re.match(r"(pull1|v41)_s8_r(\d)_", Path(f).name).groups()
        last = [json.loads(l) for l in open(f) if "on_time_total" in l][-1]
        tot[(mo, r)] = tot.get((mo, r), 0.0) + last["on_time_total"]
    A.check("v4.1 rule, 8 streams, min /s", min(v for k, v in tot.items() if k[0] == "v41"), M2.get("BdRuleEightMin"))
    A.check("v4.1 rule, 8 streams, max /s", max(v for k, v in tot.items() if k[0] == "v41"), M2.get("BdRuleEightMax"))
    A.check("pull, 8 streams, min /s", min(v for k, v in tot.items() if k[0] == "pull1"), M2.get("BdPullEightMin"))
    A.check("pull, 8 streams, max /s", max(v for k, v in tot.items() if k[0] == "pull1"), M2.get("BdPullEightMax"))
    # calibration and Theorem 1 (from their own result files: their generators are re-run by repro_check.sh)
    cal = json.load(open(H / "calibration" / "calib_hw_nov16.json"))["groups"]["all/all"]["p_on_vs_deadline"]
    A.check("calibration ECE", cal["ece"], M2.get("BdCalEce"))
    A.check("calibration frames", cal["n"], M2.get("BdCalFrames"))
    A.check("calibration low bin observed %", 100 * cal["bins"][0]["observed"], M2.get("BdCalLowObs"))
    assert all(b["observed"] >= b["pred"] for b in cal["bins"]), "a calibration bin is over-confident"

    # paper 1: T10 sweep (best option per goodput, accuracy-weighted) and the measured-Pi analysis
    pr = json.load(open(H / "t10" / "t10_prediction.json"))["options"]
    sw = {}
    for f in glob.glob(str(H / "t10" / "sweep" / "*.json")):
        if f.endswith("__htb.json"):
            continue
        d = json.load(open(f))
        sw.setdefault(float(d["rate_mbit"]), {}).setdefault(d["option"], []).append(d["on_time_fps"])
    best = {r: max(o, key=lambda k: np.mean(o[k]) * pr[k]["map50_95"] / pr[k]["base_map50_95"]) for r, o in sw.items()}
    allj = all(v.startswith("jpeg") for v in best.values())
    A.rows.append(("T10: best option at every goodput is a JPEG", str(allj), M1.get("BpBestAllJpeg"),
                   "ok" if (allj and M1.get("BpBestAllJpeg") == "yes") else "MISMATCH"))
    A.bad += not (allj and M1.get("BpBestAllJpeg") == "yes")
    A.check("T10 largest code on-time /s", max(np.mean(v) for o in sw.values() for k, v in o.items() if not k.startswith("jpeg")),
            M1.get("BpCodeFpsMax"))
    pim = json.load(open(ROOT / "experiments" / "results" / "video_codecs" / "analysis_pi_measured.json"))
    mj = {r["code"]: r for r in pim["versions"]["measured"]["jpeg"]["rows"]}
    mb = {r["code"]: r for r in pim["versions"]["measured"]["both"]["rows"]}
    A.check("headline code B_be, JPEG, measured", mj["joint_k4_c4_w128_d2"]["b_be_mbps"], M1.get("BpHeadJpegMeas"))
    A.check("headline code B_be, JPEG+video, measured", mb["joint_k4_c4_w128_d2"]["b_be_mbps"], M1.get("BpHeadVideoMeas"))
    A.check("winning cells with video, measured", pim["versions"]["measured"]["both"]["wins_total"], M1.get("BpWinsVideoMeas"))
    A.check("exceptions, all families", sum(v["violations"] for v in pim["versions"]["measured"].values()), M1.get("BpExc"))
    A.check("rule's Pi host scale", pim["scale_rule"], M1.get("BpScale"))
    t11 = [json.loads(l) for fn in ("t11_video_pi-receiver.jsonl", "t11_video_pi-receiver_extra.jsonl")
           for l in open(H / "t11" / fn)]
    t11 = {x["setting"]: x for x in t11}
    A.check("x264 ultrafast CRF 23 ms", t11["x264_ultrafast_crf23"]["ms_per_frame"], M1.get("BpXuf"))
    A.check("x265 medium CRF 23 ms", t11["x265_medium_crf23"]["ms_per_frame"], M1.get("BpXmed"))

    out = ["# Independent audit of the board numbers, 16 Nov 2026", "",
           "`scripts/audit_nov16.py`: own code, raw result files only (not `scripts/report_mesh_nov16.py`).", ""]
    if resc:
        out += ["## A. Runs re-scored from their frame logs (no cache) against the cached scores", "",
                "| run | metric | re-scored | cached | |", "| --- | --- | --- | --- | --- |"]
        out += [f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} |" for r in resc] + [""]
    out += ["## B. Macros recomputed", "", "| quantity | recomputed | macro | |", "| --- | --- | --- | --- |"]
    out += [f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} |" for r in A.rows]
    out += ["", f"**{A.bad} mismatches.**"]
    (ROOT / "docs" / "audit_nov16.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))
    sys.exit(1 if A.bad else 0)


if __name__ == "__main__":
    main()
