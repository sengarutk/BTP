#!/usr/bin/env python3
"""Results Brief 19.24-19.31 (16 Nov 2026): the mesh board sessions of 14-16 Nov 2026 on five boards, every verdict
with its numbers. EVERY number is computed here from the result files (campaign summaries, eval caches, run JSONs,
bench files, check outputs); none is typed by hand. Predictions and their wording: docs/mesh_predictions_nov14.md,
docs/board_session_predictions_nov.md; one-line verdicts: docs/mesh_results_nov15.md.
Also: Part 19's title, a state box in Part 1 (before the 12 Nov box), Part 20's honest negatives, Part 23 (what is
left). Idempotent (marked blocks / sections replaced); originals archived in
experiments/results/hardware/_superseded/report_before_mesh_nov16/.
"""
import glob
import json
import math
import re
import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_parts_oct22 import HTML, MD, html_to_md, table  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "experiments" / "results" / "hardware"
ARCH = R / "_superseded" / "report_before_mesh_nov16"


# ---------- helpers ----------
def summ(camp):
    return json.load(open(R / f"vid_campaign_{camp}_summary.json"))


def cell(camp, key, metric="sAP_fc"):
    return summ(camp)["cells"][key][metric]           # [mean, ci95]


def cache(camp):
    return json.load(open(R / f"vid_campaign_{camp}" / "_eval_cache_mesh.json"))


def t_p(t, df):
    x = np.linspace(abs(t), abs(t) + 200, 400001)
    f = math.gamma((df + 1) / 2) / (math.sqrt(df * math.pi) * math.gamma(df / 2)) * (1 + x ** 2 / df) ** (-(df + 1) / 2)
    return float(2 * np.trapz(f, x))


T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262}


def paired(camp, sc, a, b, metric="sAP_fc", reps=5, cams=("",)):
    c = cache(camp)
    d = np.array([c[f"{sc}__{a}__r{r}{cm}"][metric] - c[f"{sc}__{b}__r{r}{cm}"][metric]
                  for r in range(1, reps + 1) for cm in cams])
    n = len(d)
    se = d.std(ddof=1) / math.sqrt(n)
    return {"mean": float(d.mean()), "ci": T975[n - 1] * se, "ahead": int((d > 0).sum()), "n": n,
            "p": t_p(d.mean() / se, n - 1) if se > 0 else 1.0}


def heat(f):
    d = json.load(open(f))
    me = d["measured_energy"]
    L = np.array(me["log_t_w_c"])
    t, T = L[:, 0], L[:, 2]
    dt = np.diff(t, append=t[-1])
    C = np.array(me["clock_log_t_mhz_flags"])
    return {"peak": float(T.max()), "h80": 100 * dt[T >= 80].sum() / t[-1], "h78": 100 * dt[T >= 78].sum() / t[-1],
            "thr": int(((C[:, 2].astype(int) & 4) > 0).sum()), "w": me["mean_w"],
            "t2": float(T[t >= t[-1] / 2].mean())}


def heats(camp, st):
    return [heat(f) for f in sorted(glob.glob(str(R / f"vid_campaign_{camp}" / f"a2_mission__{st}__r?.json")))]


def f3(x):
    return f"{x:+.4f}"


def pm(p):
    pv = "p < 0.001" if p["p"] < 0.001 else f"p {p['p']:.3f}"
    return f"{p['mean']:+.4f} ± {p['ci']:.4f} ({p['ahead']}/{p['n']}, {pv})"


def rng(v, fmt="{:.1f}"):
    return fmt.format(min(v)) + ("" if abs(max(v) - min(v)) < 1e-9 else "–" + fmt.format(max(v)))


# ---------- 19.25 heat ----------
t4 = {s: heats("heat_nov", s) for s in ("v41", "v41cap", "v41guard")}
g = heats("heat_nov2", "v41guard765")
fh = heats("heat_final", "v41final")
over = [h["peak"] - 76.5 for h in g] + [h["peak"] - 78.0 for h in t4["v41guard"]]
th = json.load(open(R / "theory_check" / "theory_check.json"))["theorem1"]
H25 = table(["strategy (24-min mission, 4-min total blackout)", "runs", "peak °C", "time ≥ 80 °C", "throttled samples",
             "sAP+fc"],
            [["v4.1 (hold always)", len(t4["v41"]), rng([h["peak"] for h in t4["v41"]]), rng([h["h80"] for h in t4["v41"]]) + " %",
              rng([h["thr"] for h in t4["v41"]], "{:d}"), f"{cell('heat_nov', 'mission|v41')[0]:.4f}"],
             ["capped hold (78 °C)", len(t4["v41cap"]), rng([h["peak"] for h in t4["v41cap"]]),
              rng([h["h80"] for h in t4["v41cap"]]) + " %", rng([h["thr"] for h in t4["v41cap"]], "{:d}"),
              f"{cell('heat_nov', 'mission|v41cap')[0]:.4f}"],
             ["capped hold + guard 78 °C", len(t4["v41guard"]), rng([h["peak"] for h in t4["v41guard"]]),
              rng([h["h80"] for h in t4["v41guard"]], "{:.2f}") + " %", rng([h["thr"] for h in t4["v41guard"]], "{:d}"),
              f"{cell('heat_nov', 'mission|v41guard')[0]:.4f}"],
             ["hold + guard 76.5 °C", len(g), rng([h["peak"] for h in g]), rng([h["h80"] for h in g], "{:.2f}") + " %",
              rng([h["thr"] for h in g], "{:d}"), f"{cell('heat_nov2', 'mission|v41guard765')[0]:.4f}"],
             ["final controller (guard 76.5 °C + YOLO11n-480)", len(fh), rng([h["peak"] for h in fh]),
              rng([h["h80"] for h in fh], "{:.2f}") + " %", rng([h["thr"] for h in fh], "{:d}"),
              f"{cell('heat_final', 'mission|v41final')[0]:.4f}"]])

# ---------- 19.26 final controller ----------
fin = {(sc, s): cell("final_nov", f"{sc}|{s}") for sc in ("mesh_mission", "multihop") for s in ("v41final", "v41", "accumo", "leaf")}
finw = {(sc, s): cell("final_nov", f"{sc}|{s}", "pi_w") for sc in ("mesh_mission", "multihop") for s in ("v41final", "v41", "accumo", "leaf")}
pF = {(sc, b): paired("final_nov", sc, "v41final", b) for sc in ("mesh_mission", "multihop") for b in ("v41", "accumo", "leaf")}
pB = {sc: (paired("budget_nov", sc, "v41final24", "v41final", reps=3), paired("budget_nov", sc, "v41final24", "v41final", "pi_w", reps=3))
      for sc in ("mesh_mission", "multihop")}
pX = {sc: paired("fix_nov", sc, "v41fix24", "v41final24") for sc in ("mesh_mission", "multihop")}


def shares(camp, sc, st):
    cnt, lat = {}, {}
    for f in glob.glob(str(R / f"vid_campaign_{camp}" / f"a2_{sc}__{st}__r?.json")):
        for fr in json.load(open(f))["frames"]:
            s = fr.get("server")
            if s:
                cnt[s] = cnt.get(s, 0) + 1
                if fr.get("lat_ms"):
                    lat.setdefault(s, []).append(fr["lat_ms"])
    tot = sum(cnt.values())
    return {s: (100 * cnt[s] / tot, float(np.median(lat[s])) if s in lat else None) for s in cnt}


shF, shX = shares("final_nov", "multihop", "v41final"), shares("fix_nov", "multihop", "v41fix24")
shX0 = shares("fix_nov", "multihop", "v41final24")
H26a = table(["scenario", "final controller", "v4.1", "AccuMO-style planner", "LEAF-style weight"],
             [[sc] + [f"{fin[(sc, s)][0]:.4f} ({finw[(sc, s)][0]:.2f} W)" for s in ("v41final", "v41", "accumo", "leaf")]
              for sc in ("mesh_mission", "multihop")])
H26b = table(["comparison (paired)", "mesh_mission", "multihop"],
             [["final − v4.1, sAP+fc", pm(pF[("mesh_mission", "v41")]), pm(pF[("multihop", "v41")])],
              ["final − AccuMO, sAP+fc", pm(pF[("mesh_mission", "accumo")]), pm(pF[("multihop", "accumo")])],
              ["final − LEAF, sAP+fc", pm(pF[("mesh_mission", "leaf")]), pm(pF[("multihop", "leaf")])],
              ["budget 2.4 − 2.8 W, sAP+fc", pm(pB["mesh_mission"][0]), pm(pB["multihop"][0])],
              ["budget 2.4 − 2.8 W, Pi W", pm(pB["mesh_mission"][1]), pm(pB["multihop"][1])],
              ["late-path skip − none (2.4 W), sAP+fc", pm(pX["mesh_mission"]), pm(pX["multihop"])]])

# ---------- 19.27 v4.1+ and DVFS ----------
dvh = {s: heats("dvfs_heat", s) for s in ("v41final", "v41dvfs")}
pDh = paired("dvfs_heat", "mission", "v41dvfs", "v41final", reps=3)
pDs = paired("dvfs_short", "mission", "v41dvfs", "v41final", reps=5)
pDhw = paired("dvfs_heat", "mission", "v41dvfs", "v41final", "pi_w", reps=3)
prof = json.load(open(R / "energy" / "dvfs_profile_pi-receiver_20261116.json"))["summary"]
H27 = table(["clock", "YOLOv8s-320: ms / W / J", "YOLO11n-480: ms / W / J"],
            [[f"{int(f) / 1000:.1f} GHz"] + [f"{prof[f][v]['ms']:.0f} / {prof[f][v]['power_w']:.2f} / {prof[f][v]['j_per_inference']:.3f}"
                                              for v in ("s320", "n480y11")] for f in ("1500", "1800", "2100", "2400")])


def share18(camp):
    out = []
    for f in sorted(glob.glob(str(R / f"vid_campaign_{camp}" / "a2_mission__v41dvfs__r?.json"))):
        ob = [fr.get("variant") for fr in json.load(open(f))["frames"] if fr.get("server") == "onboard"]
        out.append(100 * sum(1 for v in ob if "@" in v) / max(1, len(ob)))
    return out


s18 = share18("dvfs_heat") + share18("dvfs_short")

# ---------- 19.28 swarm ----------
two = {(sc, s): cell("two_nov", f"{sc}|{s}") for sc in ("static_good", "mesh_mission") for s in ("v41j1", "v41j2")}
cap = {(sc, s): cell("two_cap", f"{sc}|{s}") for sc in ("static_good", "mesh_mission") for s in ("v41j2", "v41j2cap")}
pC = {sc: paired("two_cap", sc, "v41j2cap", "v41j2", reps=2, cams=("_c1", "_c2")) for sc in ("static_good", "mesh_mission")}
pull = {}
for f in glob.glob(str(R / "pull_nov_fair" / "*.jsonl")):
    m = re.match(r"(pull1|v41)_s(\d)_r(\d)_(camera2?)\.jsonl", Path(f).name)
    lines = [json.loads(l) for l in open(f)]
    tot = [l for l in lines if "on_time_total" in l][-1]
    lat = [l["lat_p50_ms"] for l in lines if "stream" in l and l.get("lat_p50_ms")]
    k = (m.group(1), int(m.group(2)), int(m.group(3)))
    a = pull.setdefault(k, {"on": 0.0, "lat": []})
    a["on"] += tot["on_time_total"]
    a["lat"] += lat
H28 = table(["streams (2 camera Pis)", "v4.1 rule: on-time/s (median ms)", "pull one ahead: on-time/s (median ms)"],
            [[str(n)] + [" / ".join(f"{pull[(mo, n, r)]['on']:.1f}" for r in (1, 2) if (mo, n, r) in pull)
                         + f" ({rng([float(np.median(pull[(mo, n, r)]['lat'])) for r in (1, 2) if (mo, n, r) in pull], '{:.0f}')})"
                         for mo in ("v41", "pull1")] for n in (1, 2, 4, 6, 8)])

# ---------- 19.29 the other mesh tests ----------
top = summ("topology_nov")["paired"]
fps = {k: [float(np.mean([json.load(open(f))["total"]["on_time_fps"]          # T7: on-time results/s (run totals,
                           for f in glob.glob(str(R / "vid_campaign_fps_nov" / f"a2_static_good__{k}__r?.json"))]))]  # as scored)
       for k in ("v41_f15", "v41_f30", "v41_f60", "v41ea_f30")}
en = {k: cell("energy_nov", f"static_good|{k}", m) for k in ("v41", "v41b36", "freshonly") for m in ("pi_w",)}
rn = {(sc, s): cell("relaynoise_nov", f"{sc}|{s}") for sc in ("multihop_loss2", "multihop_loss5") for s in ("hier", "v41", "fixlap")}

# ---------- 19.30 paper 1 on the boards ----------
pr = json.load(open(R / "t10" / "t10_prediction.json"))
sweep = {}
for f in glob.glob(str(R / "t10" / "sweep" / "*.json")):
    d = json.load(open(f))
    if f.endswith("__htb.json"):
        continue
    sweep.setdefault((float(d["rate_mbit"]), d["option"]), []).append(d)
O = pr["options"]
best = {}
for (rate, o), L in sweep.items():
    v = np.mean([x["on_time_fps"] for x in L]) * O[o]["map50_95"] / O[o]["base_map50_95"]
    if rate not in best or v > best[rate][1]:
        best[rate] = (o, v)
t11 = {json.loads(l)["setting"]: json.loads(l) for fn in ("t11_video_pi-receiver.jsonl", "t11_video_pi-receiver_extra.jsonl")
       for l in open(R / "t11" / fn)}
vc = ROOT / "experiments" / "results" / "video_codecs"
lap = {k: json.load(open(vc / f"{k}.json"))["encode_ms_per_frame"] for k in t11 if "ms_per_frame" in t11[k]}
ratios = [t11[k]["ms_per_frame"] / lap[k] for k in lap]
pim = json.load(open(vc / "analysis_pi_measured.json"))
rule = {(fam, r["code"]): r for fam, v in pim["rule_scaled_pi"].items() for r in v}
meas = {(fam, r["code"]): r for fam, v in pim["versions"]["measured"].items() for r in v["rows"]}
y11 = json.load(open(ROOT / "experiments" / "results" / "second_detector" / "yolo11s" / "break_even_pi_measured.json"))
H30 = table(["Pi break-even goodput (Mbit/s)", "image family", "rule (scaled host times)", "measured Pi times"],
            [["YOLOv8s joint_k4_c4 (paper 1's headline code)", "JPEG", f"{rule[('jpeg', 'joint_k4_c4_w128_d2')]['b_be_mbps']:.2f}",
              f"{meas[('jpeg', 'joint_k4_c4_w128_d2')]['b_be_mbps']:.2f}"],
             ["", "JPEG + low-delay video", f"{rule[('both', 'joint_k4_c4_w128_d2')]['b_be_mbps']:.2f}",
              f"{meas[('both', 'joint_k4_c4_w128_d2')]['b_be_mbps']:.2f}"],
             ["YOLOv8s learned_k4_c4", "JPEG + video", f"{rule[('both', 'learned_k4_c4_w128_d2')]['b_be_mbps']:.2f}",
              f"{meas[('both', 'learned_k4_c4_w128_d2')]['b_be_mbps']:.2f}"]]
            + [[f"YOLO11s {r['code'].replace('learned_', '')}", "JPEG", f"{r['b_be_mbps_rule']:.2f}", f"{r['b_be_mbps_measured']:.2f}"]
               for r in sorted(y11["rows"], key=lambda r: r["code"]) if r["b_be_mbps_rule"]])
wins_video = pim["versions"]["measured"]["both"]["wins_total"]

# ---------- 19.31 calibration and checks ----------
cal = json.load(open(R / "calibration" / "calib_hw_nov16.json"))
ca = cal["groups"]["all/all"]["p_on_vs_deadline"]
H31 = table(["predicted chance of meeting 300 ms", "frames", "mean predicted", "observed on time"],
            [[b["bin"], f"{b['n']:,}", f"{b['pred']:.3f}", f"{b['observed']:.3f}"] for b in ca["bins"]])
prc = json.load(open(R / "theory_check" / "price_rules_check.json"))
tb = [json.loads(l) for l in open(R / "tunnel_bench" / "tunnel_bench.jsonl")]
tun = {k: [x["sizes"][s][m] for x in tb if x["label"].startswith(k)] for k, s, m in
       (("laptop", "1024", "rtt_ms_median"), ("pi-sender", "1024", "rtt_ms_median"))}
tung = {k: [x["sizes"]["83000"]["goodput_mbps_median"] for x in tb if x["label"].startswith(k)] for k in ("laptop", "pi-sender")}
tunr = {k: [x["sizes"]["83000"]["rtt_ms_median"] for x in tb if x["label"].startswith(k)] for k in ("laptop", "pi-sender")}


V = '<span class="tag v">Validated</span>'
P = '<span class="tag p">Pending</span>'
SECS = f'''<h3>19.24 The mesh board sessions of 14-16 November 2026: what ran and how</h3>
<p>Five boards on the batman-adv mesh (IBSS channel 6): pi-sender as the ground radio (cabled to the laptop), the camera Pis pi-relayyy and pi-receiver, the edge drones Nano1 (Orin Nano, 15 W) and Nano2 (Orin Nano Super, 25 W). Every campaign and bench had its predictions committed before its first run (<code>docs/mesh_predictions_nov14.md</code>, <code>docs/board_session_predictions_nov.md</code>); every verdict in one table: <code>docs/mesh_results_nov15.md</code>; session log: <code>docs/mesh_session_nov14.md</code>. Rules kept throughout: no change to the mesh configuration, temporary nft/tc rules removed after every run, every run started below a fixed camera temperature where heat was measured, runs made on laptop battery (weaker ground GPU) archived and re-run, results never deleted (archived in <code>_superseded/</code> with the reason). Faults met and fixed during the sessions: a charger that dropped three times (two sessions paused and resumed, one laptop shutdown; no result lost), three restart faults in the automation (PATH and environment of Windows-launched sessions, a leftover link logger), and four tool faults found by smoke tests before the T10 sweep. Removed by the user's decision (no equipment): airflow (T5) and flight (G1), stated as limitations; cut as redundant after the results below: joint fades, governor comparison, a cheaper camera-motion step, YOLO11m on the ground, the remaining board profiles, the BATMAN-adv overhead test and the bridge re-run (the tunnel's cost was measured instead, 19.31). {V}</p>
<h3>19.25 Heat: the capped hold, the guard, and Theorem 3 on the boards</h3>
<p>The 24-minute mission with its 4-minute total blackout, every run started below 55 °C:</p>
{H25}
<ul>
<li><b>The always-on blackout hold heats the board</b> ({rng([h['h80'] for h in t4['v41']])} % of the time at ≥ 80 °C, throttled); capping it at 78 °C removes almost all of it at no accuracy cost (T4.1-T4.4).</li>
<li><b>Theorem 3 (b), the guard's peak bound, needs a fast-mode term.</b> After the guard acts the Pi's die keeps heating: measured overshoot above the guard {rng(over)} °C over the {len(over)} guarded runs. With the guard at 76.5 °C the peak stayed ≤ 80.4 °C (one sample at 80.4 in one run, G.1 narrowly not held), no run throttled, and accuracy was unchanged (G.2). The theorem is stated as peak ≤ guard + δ_fast with δ_fast measured on the board (3.9 °C here).</li>
<li><b>Theorem 1 holds update by update on every recorded run</b> ({th['runs']} runs, {th['updates']:,} price updates, 0 unexplained steps; T4.5), and the freshness price follows its rule on every update (price_rules_check, 0 unexplained).</li>
</ul>
<h3>19.26 The final controller against v4.1 and the published-style schedulers</h3>
<p>Final controller: v4.1 + capped hold and guard at 76.5 °C + YOLO11n-480 onboard (timed at start-up, priced at its measured energy) + 10 ms contention term, then (below) a 2.4 W budget and the late-path skip. Five paired repetitions, every run below 60 °C at start:</p>
{H26a}
{H26b}
<ul>
<li><b>The final configuration costs nothing against v4.1</b> (F.1) and never throttles; Theorem 1 holds on all its runs (F.4); on the 24-min mission it keeps the peak at {rng([h['peak'] for h in fh])} °C, never throttled, at sAP {cell('heat_final', 'mission|v41final')[0]:.4f} (FH.1-FH.2).</li>
<li><b>The AccuMO-style planner beat it in multihop</b> (F.2 not held): v4.1 kept sending ~{shF['laptop'][0]:.0f} % of its frames to the two-hop laptop, whose results arrived in a median {shF['laptop'][1]:.0f} ms (past the deadline; the controller's own p_on for them was ~0), and that traffic shared the relay's radio with the Jetson path. The earlier "a greedy priced controller ties the planner" (2 repetitions, P1.1) was under-powered.</li>
<li><b>AccuMO and LEAF drew 0.36-0.60 W less at the same accuracy</b> (F.3): v4.1 fills its 2.8 W budget with onboard work worth almost nothing in these scenarios. With a 2.4 W budget instead, the final controller's power changes by {pB['mesh_mission'][1]['mean']:+.2f} W (mesh_mission) and {pB['multihop'][1]['mean']:+.2f} W (multihop), the camera runs about 3 °C cooler, and sAP changes by {pB['mesh_mission'][0]['mean']:+.4f} / {pB['multihop'][0]['mean']:+.4f} (B.1-B.2): the power gap was the budget setting. The final controller's budget is 2.4 W.</li>
<li><b>The fix for multihop:</b> while a timely path exists, a path predicted late (p_on < 0.5) gets only its own on-time options or no frame. Multihop {pX['multihop']['mean']:+.4f} (5/5 pairs; the planner's lead was {-pF[('multihop', 'accumo')]['mean']:+.4f}); the laptop's share fell from {shX0['laptop'][0]:.1f} % to {shX['laptop'][0]:.1f} % (median {shX['laptop'][1]:.0f} ms) and the Jetson path's median latency from {shX0['jetson'][1]:.0f} to {shX['jetson'][1]:.0f} ms. On the one-hop mission {pX['mesh_mission']['mean']:+.4f}, not significant (FX.2 narrowly not held: in 2 of 5 pairs the skipped late path was missed as a backup). Adopted in the final controller with that caveat.</li>
</ul>
<h3>19.27 v4.1+ re-tested, and the CPU clock as a third knob</h3>
<ul>
<li><b>v4.1+ (15 Nov re-test, 3 repetitions):</b> YOLO11n-480 (192 ms on the Pi) replaced YOLOv8s-320 for most onboard frames and almost all blackout frames (T8R.4), and v4.1+ never throttled on the mission while v4.1 spent 20-22 % of it at ≥ 80 °C; but the room-following budget held its power (3.29-3.36 W) without reaching its temperature target under bursty load (T8R.1-T8R.2 partly). The room-following budget is dropped; the fixed budget stays.</li>
<li><b>DVFS profile</b> (<code>dvfs_profile.py</code>, pi-receiver, two passes, the clock pinned):</li>
</ul>
{H27}
<ul>
<li><b>1.8 GHz is the energy minimum</b> (−27 % J per inference against 2.4 GHz for both models, 1.4-1.7 W less while inferring, +22-28 ms); the curve is U-shaped (1.5 GHz costs more).</li>
<li><b>As a priced knob it is used but neutral:</b> the controller ran {rng(s18, '{:.0f}')} % of its onboard inferences at 1.8 GHz (D.1), yet power changed by {pDhw['mean']:+.3f} W on the 24-min mission (D.2 not held) and sAP by {pDh['mean']:+.4f} (heat) / {pDs['mean']:+.4f} (short) (D.3): under a power budget the price spends the saving on more onboard inferences (+16 %), not on lower power. At the 2.4 W budget the same (B.3). Reported as implemented, measured and neutral.</li>
</ul>
<h3>19.28 Two camera drones on one channel</h3>
<ul>
<li><b>A second edge drone costs accuracy on one shared channel</b> (T6.2 not held): per camera, static_good {two[('static_good', 'v41j1')][0]:.4f} with one Jetson against {two[('static_good', 'v41j2')][0]:.4f} with two; mesh_mission {two[('mesh_mission', 'v41j1')][0]:.4f} against {two[('mesh_mission', 'v41j2')][0]:.4f}. More paths in flight make every result later.</li>
<li><b>A per-camera cap on paths in flight does not fix it</b> (C.1-C.3 not held): {pm(pC['static_good'])} (static_good), {pm(pC['mesh_mission'])} (mesh_mission); a camera cannot see the other camera's traffic.</li>
<li><b>A swarm-wide pull-one-ahead coordinator holds the channel at capacity</b> (S6, two camera Pis, 8 streams; receiver-driven scheduling as in datacentre transport, measured here on a drone mesh):</li>
</ul>
{H28}
<ul><li>Fairness across the two hosts with several streams each did not hold (S6.5; one host's streams starved, cause not found): no fairness claim.</li></ul>
<h3>19.29 Topology, frame rate, noisy relay, energy price</h3>
<ul>
<li><b>Topology decides where the decision belongs</b> (T9, 5 repetitions, one campaign): hier − v4.1 (sAP+fc, paired): multihop {top['hier-v41|multihop']['sAP_fc']['mean_diff']:+.4f} ± {top['hier-v41|multihop']['sAP_fc']['ci95']:.4f} (hier ahead in {top['hier-v41|multihop']['sAP_fc']['first_ahead']}/5), static_good {top['hier-v41|static_good']['sAP_fc']['mean_diff']:+.4f} ± {top['hier-v41|static_good']['sAP_fc']['ci95']:.4f} (v4.1 ahead in {5 - top['hier-v41|static_good']['sAP_fc']['first_ahead']}/5): deciding at the relay pays only when the camera is two hops from the ground.</li>
<li><b>Frame rate</b> (T7): on-time results per second (3 runs each) 15 fps {fps['v41_f15'][0]:.1f}, 30 fps {fps['v41_f30'][0]:.1f}, 60 fps {fps['v41_f60'][0]:.1f}, 30 fps with encode-ahead {fps['v41ea_f30'][0]:.1f}: v4.1 leaves the radio idle between 30-fps ticks, and encoding the next frame while the radio is busy recovers part of it.</li>
<li><b>Noisy relay</b> (T3, 2 % / 5 % loss): sAP+fc hier {rn[('multihop_loss2', 'hier')][0]:.4f} / {rn[('multihop_loss5', 'hier')][0]:.4f}, v4.1 {rn[('multihop_loss2', 'v41')][0]:.4f} / {rn[('multihop_loss5', 'v41')][0]:.4f}, fixed laptop {rn[('multihop_loss2', 'fixlap')][0]:.4f} / {rn[('multihop_loss5', 'fixlap')][0]:.4f}.</li>
<li><b>Energy price</b> (T2): Pi power v4.1 at 2.8 W {en['v41'][0]:.2f} W, at 3.6 W {en['v41b36'][0]:.2f} W, freshness price only {en['freshonly'][0]:.2f} W; Theorem 1 confirmed; the one-fit budget-to-temperature rule needs a per-board intercept (pi-relayyy 29.72 + 11.66 °C/W).</li>
</ul>
<h3>19.30 Paper 1 on the boards: the break-even goodput predicted, then measured</h3>
<ul>
<li><b>T10</b> (pi-receiver → Nano2, the link serialised at each goodput by netem, codes started below 60 °C): the best measured option at every goodput from 0.5 to 8 Mbit/s was a JPEG ({', '.join(f"{r:g}: {best[r][0]}" for r in sorted(best))}); no learned code wins on a Pi 5 camera, as paper 1's model predicted from the board benches (T10.1-T10.2, T10.4 held; T10.3 3 of 4). With a token-bucket link (low average goodput from a shared fast radio) the 4 KB code wins at 0.5 Mbit/s: the result depends on how the link is slow.</li>
<li><b>T11: CPU encoding on the Pi</b> (same frames and encoder arguments as paper 1): x264 ultrafast CRF 23 {t11['x264_ultrafast_crf23']['ms_per_frame']:.1f} ms, x265 medium CRF 23 {t11['x265_medium_crf23']['ms_per_frame']:.1f} ms per frame; Pi/laptop {min(ratios):.2f}-{max(ratios):.2f}. The rule scales host processing by the full-model ratio ({pim['scale_rule']:.1f} on the throttled Pi): right for network inference (the YOLO11s codes measured within 2 % of it, Y.1), 20-30x too slow for CPU encoding; the YOLOv8s codes' Pi times were 19-51 % above the rule's.</li>
<li><b>Re-analysis with measured Pi times</b> (<code>evaluation/pi_measured_break_even.py</code>, <code>pi_measured_second_detector.py</code>):</li>
</ul>
{H30}
<ul><li>With low-delay video in the image family and measured Pi times, no split code has a winning cell on the Pi ({wins_video} cells, 0 exceptions): the model and the live sweep agree. Paper 1's Pi numbers are replaced by these.</li></ul>
<h3>19.31 The deadline model on the hardware, and the checks</h3>
<p>Every offloaded frame of the {cal['runs']} runs of 14-16 Nov, the controller's logged p_on against arrival within 300 ms (<code>calib_hw.py</code>; ECE {ca['ece']:.3f}, Brier {ca['brier']:.3f}):</p>
{H31}
<ul>
<li><b>Never over-confident, strongly pessimistic at the low end</b>: observed ≥ predicted in every bin; frames predicted at ~0 % arrived on time {ca['bins'][0]['observed'] * 100:.0f} % of the time. The late-path skip acts on this estimate, which fits its small mission-side cost; a recalibrated p_on is a direction for paper 2, not tested.</li>
<li><b>The SSH tunnel on the laptop path</b> (<code>tunnel_bench.py</code>): 1 KB round trip {rng(tun['laptop'])} ms through it against {rng(tun['pi-sender'])} ms over the direct mesh hop; an 83 KB frame {rng(tunr['laptop'])} against {rng(tunr['pi-sender'])} ms, goodput {rng(tung['laptop'])} against {rng(tung['pi-sender'])} Mbit/s: a small measured artefact (+2-4 ms per frame).</li>
<li>Theorem 1 holds update by update on all {th['runs']} recorded runs; the freshness price follows its rule on every update.</li>
</ul>
'''

STATE = f'''<div class="box state"><b class="h">State on 16 Nov 2026 (mesh board sessions done; details in 19.24-19.31)</b><ul>
<li><b>Paper 2's final controller</b>: v4.1 + capped hold and guard at 76.5 °C + YOLO11n-480 onboard + a 2.4 W budget + the late-path skip. On five boards it ties v4.1, never throttles on a 24-min blackout mission (peak {rng([h['peak'] for h in fh])} °C), matches the AccuMO-style planner in multihop after the fix ({pX['multihop']['mean']:+.4f} for the fix, 5/5 pairs) and beats it on the one-hop mission ({pF[('mesh_mission', 'accumo')]['mean']:+.4f}); Theorem 1 holds on all {th['runs']} recorded runs.</li>
<li><b>Paper 1 on the boards</b>: predicted from board benches and then measured, no learned split beats JPEG on a Pi 5 camera at any goodput; with measured Pi times the model agrees (0 winning cells with video).</li>
<li><b>Honest negatives</b>: the guard's peak bound needs a measured fast-mode term (δ_fast 3.9 °C); DVFS is neutral under a power budget; a second edge drone on one channel costs accuracy and a per-camera cap does not fix it; pull-one-ahead fairness not shown.</li>
<li><b>Left</b>: laptop only — reproducibility package, the papers rewritten with every verdict, the Novelty Brief and Final Report, an independent audit.</li>
</ul></div>
'''

NEG = f'''<li><b>Mesh sessions 14-16 Nov (19.24-19.31).</b> The guard's peak bound held only with a measured fast-mode term (δ_fast 3.9 °C; G.1 narrowly not held at 76.5 °C). The room-following budget missed its temperature target under bursty load. DVFS was used but neutral under a power budget. A second edge drone on one shared channel cost accuracy, and a per-camera cap did not fix it. The AccuMO-style planner beat the greedy controller in multihop until the late-path skip; the skip costs a little where the late path was a useful backup. Pull-one-ahead fairness across hosts was not shown. The deadline probabilities are pessimistic at the low end.</li>
'''

LEFT = '''<!--left16--><p><b>Update 16 Nov 2026:</b> every board test is done (19.24-19.31); nothing more is planned on the mesh. Left, laptop only: the reproducibility package, both papers rewritten with every verdict (failures included), the Novelty Brief and Final Report, and an independent audit of every number.</p>
<!--/left16-->'''


def strip_marked(s, a, b):
    return re.sub(re.escape(a) + r".*?" + re.escape(b) + r"\n*", "", s, flags=re.S)


def main():
    h, m = HTML.read_text(), MD.read_text()
    if not (ARCH / HTML.name).exists():
        ARCH.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HTML, ARCH / HTML.name)
        shutil.copy2(MD, ARCH / MD.name)
    # sections 19.24-19.31: before Part 20, replacing any earlier version
    j = h.index('<h2 id="argument">')
    assert 0 <= h.find("<h3>19.23 ") < j, "19.23 missing"
    i = h.find("<h3>19.24 ")
    h = h[:i if 0 <= i < j else j] + SECS + h[j:]
    j = m.index("## PART 20")
    i = m.find("### 19.24 ")
    m = m[:i if 0 <= i < j else j] + html_to_md(SECS) + m[j:]
    old19 = "laptop additions to 12 Nov, including the hardening of both papers (19.15–19.23)"
    new19 = old19 + "; mesh board sessions 14–16 Nov (19.24–19.31)"
    if new19 not in h:
        assert old19 in h and old19 in m
        h, m = h.replace(old19, new19), m.replace(old19, new19)
    # state box before the 12 Nov one
    h = strip_marked(h, "<!--state16-->", "<!--/state16-->")
    k = h.index("<!--state12-->")
    h = h[:k] + "<!--state16-->" + STATE + "<!--/state16-->\n" + h[k:]
    m = strip_marked(m, "<!--state16-->", "<!--/state16-->")
    k = m.index("<!--state12-->")
    m = m[:k] + "<!--state16-->\n" + html_to_md(STATE) + "<!--/state16-->\n\n" + m[k:]
    # Part 20 honest negatives: one more item
    h = strip_marked(h, "<!--neg16-->", "<!--/neg16-->")
    k = h.index("</ul>", h.index("<h3>Honest negatives, also part of the paper</h3>"))
    h = h[:k] + "<!--neg16-->" + NEG + "<!--/neg16-->\n" + h[k:]
    m = strip_marked(m, "<!--neg16-->", "<!--/neg16-->")
    k = m.index("\n", m.index("### Honest negatives, also part of the paper")) + 1      # fixed anchor: under the heading
    m = m[:k] + "\n<!--neg16-->\n" + html_to_md("<ul>" + NEG + "</ul>").rstrip() + "\n<!--/neg16-->\n" + m[k:]
    # Part 23: a note at the top
    h = strip_marked(h, "<!--left16-->", "<!--/left16-->")
    k = h.index("</h2>", h.index('<h2 id="next">')) + 5
    h = h[:k] + "\n" + LEFT + "\n" + h[k:]
    m = strip_marked(m, "<!--left16-->", "<!--/left16-->")
    k = m.index("\n", m.index("## PART 23")) + 1
    m = m[:k] + "\n<!--left16-->\n" + html_to_md(LEFT.replace("<!--left16-->", "").replace("<!--/left16-->", "")).rstrip() + "\n<!--/left16-->\n" + m[k:]
    # date line
    h = re.sub(r"Full project report · state on [0-9]+ [A-Za-z]+ 2026", "Full project report · state on 16 Nov 2026", h, count=1)
    m = re.sub(r"Full project report · state on [0-9]+ [A-Za-z]+ 2026", "Full project report · state on 16 Nov 2026", m, count=1)
    HTML.write_text(h)
    MD.write_text(m)
    print("written; 19.24-19.31", len(SECS), "chars")


if __name__ == "__main__":
    main()
