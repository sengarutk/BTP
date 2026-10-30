#!/usr/bin/env python3
"""Report update, 30 Oct 2026 (laptop-only additions, part 4): 19.11 = v4.1's settings sweep, the replay's onboard power
model corrected and re-validated, a held-out check on fresh seeds, the AccuMO-style planner ported to the board, the
next board session prepared, the paper's hardware section (docs/laptop_additions_2026-10-30_part4.md).

Every number is read from the result files:
  replay/sweep_oct29/sweep_summary.json                 the settings sweep (replay_sweep.py)
  replay/validate_main_oct29_plant/replay_check.json    the replay against the 240 hardware runs, old power model
  replay/validate_main_oct30_power_t85/replay_check.json  the same with the corrected model (power + 85 C hold)
  replay/heldout_power_oct30/accumo_summary.json        seeds 11-20, corrected model (20 s phases; peak <= 75 C, so
                                                        the 85 C hold cannot act there)
  replay/heldout_power_oct30_t85/accumo_summary.json    seeds 11-13, 24-min mission, corrected model with the hold
  planner_bench_laptop_oct30.json, planner_smoke_oct30.json, paper/generated_tables/hw_metrics.tex
Adds 19.11 after 19.10, a Part 1 bullet, and updates "What is left". Run after report_accumo_oct29.py. Idempotent.
usage: report_part4_oct30.py     (the originals are archived in
       experiments/results/hardware/_superseded/report_before_part4_oct30/)
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_parts_oct22 import HTML, MD, html_to_md, table  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
HW = ROOT / "experiments" / "results" / "hardware"
RP = HW / "replay"
SETTING = {"energy": ("energy target", "2.8 W", "--power-budget", "{:g} W"),
           "fresh": ("freshness target", "0.95", "--fresh-target", "{:g}"),
           "mu_step": ("energy price step", "0.1", "--eta", "{:g}"),
           "fresh_step": ("freshness price step", "2.0", "--eta-f", "{:g}"),
           "fresh_cap": ("freshness price cap", "2.0", "--lam-f-max", "{:g}")}
SC = [("mission_20s", "mission"), ("random_20s", "random links"), ("mission_240s", "24-min mission")]


def pm(x, ci=None, bold=True):
    s = f"{x + 0.0:+.4f}".replace("-", "−")
    if ci is None:
        return s
    s = f"{s} ± {ci:.4f}"
    return f"<b>{s}</b>" if bold and abs(x) > ci else s


def sweep_table():
    sw = json.load(open(RP / "sweep_oct29" / "sweep_summary.json"))["scenarios"]
    rows = []
    for key, (lab, dflt, flag, f) in SETTING.items():
        vals = sorted({v["value"] for e in sw.values() for v in e["variants"].values() if v["setting"] == key})
        for val in vals:
            r = [f"{lab} (<code>{flag}</code>, v4.1: {dflt})", f.format(val)]
            for sc, _ in SC:
                v = next((x for x in sw.get(sc, {}).get("variants", {}).values()
                          if x["setting"] == key and x["value"] == val), None)
                r.append("—" if v is None else
                         f"{pm(v['minus_v41']['mean'], v['minus_v41']['ci95'])} "
                         f"({v['pi_w_minus_v41'] + 0.0:+.2f} W)".replace("(-", "(−"))
            rows.append(r)
    n = {sc: len(sw[sc]["seeds"]) for sc, _ in SC if sc in sw}
    head = ["Setting", "Value"] + [f"{lab}, n {n.get(sc, 0)}: sAP − v4.1 (Pi W)" for sc, lab in SC]
    return table(head, rows), sw


def check_rows():
    old = json.load(open(RP / "validate_main_oct29_plant" / "replay_check.json"))
    new = json.load(open(RP / "validate_main_oct30_power_t85" / "replay_check.json"))
    rows = []
    for k, lab in (("sAP", "sAP"), ("pi_w", "Pi power (W)"), ("hot_share", "time ≥ 80 °C"),
                   ("availability", "share of time with a fresh result")):
        a, b = old["agreement"][k], new["agreement"][k]
        rows.append([lab, f"{a['pearson']:.3f} / {a['mean_abs_diff']:.3f}", f"{b['pearson']:.3f} / {b['mean_abs_diff']:.3f}"])
    rows.append(["paired verdicts against v5 that agree with hardware", f"{old['verdicts_agree']} of 11",
                 f"{new['verdicts_agree']} of 11"])
    lo, ln = old["paired_vs_v5"]["leaf"], new["paired_vs_v5"]["leaf"]
    rows.append(["LEAF − v5 sAP (hardware " + pm(lo["hardware_diff"]) + ")", pm(lo["replay_diff"]), pm(ln["replay_diff"])])
    heavy = ("jsq", "conf_trigger", "reward_offload")
    for k, lab in (("pi_w", "Pi power of the 3 onboard-heavy baselines (replay / hardware)"),
                   ("hot_share", "their time ≥ 80 °C (replay / hardware)")):
        f = (lambda x: f"{x:.2f} W") if k == "pi_w" else (lambda x: f"{100 * x:.0f} %")
        cell = lambda d: ", ".join(f"{f(d['policies'][p][k][0])} / {f(d['policies'][p][k][1])}" for p in heavy)  # noqa
        rows.append([lab, cell(old), cell(new)])
    return table(["Replay against the 240 hardware runs", "old model: r / mean abs. diff.",
                  "corrected model: r / mean abs. diff."], rows), old, new


def heldout_table():
    s20 = json.load(open(RP / "heldout_power_oct30" / "accumo_summary.json"))
    s240 = json.load(open(RP / "heldout_power_oct30_t85" / "accumo_summary.json"))
    src = {"mission_20s": s20["mission_20s"], "random_20s": s20["random_20s"], "mission_240s": s240["mission_240s"]}
    cols = [("accumo", "AccuMO-style planner"), ("leaf", "LEAF-style weight"), ("sw_e2.4", "v4.1 at 2.4 W"),
            ("sw_e2.6", "v4.1 at 2.6 W")]
    rows = []
    for sc, lab in SC:
        P = src[sc]["policies"]
        r = [f"{lab} (seeds {min(src[sc]['seeds'])}–{max(src[sc]['seeds'])})", f"{P['v41']['sAP']:.4f}"]
        for c, _ in cols:
            d = P.get(c, {}).get("v41_minus")
            r.append("—" if d is None else pm(-d["mean"], d["ci95"]))
        rows.append(r)
    return table(["Scenario", "v4.1 sAP + fc"] + [f"{lab} − v4.1" for _, lab in cols], rows), src


def numbers():
    hw = dict(re.findall(r"\\newcommand\{\\(\w+)\}\{(.*)\}", (ROOT / "paper" / "generated_tables" / "hw_metrics.tex").read_text()))
    return (json.load(open(HW / "planner_bench_laptop_oct30.json")), json.load(open(HW / "planner_smoke_oct30.json")),
            {k: v.replace("$-$", "−").replace("{,}", ",") for k, v in hw.items()})


def section():
    st, sw = sweep_table()
    ct, old, new = check_rows()
    ht, ho = heldout_table()
    bench, smoke, hw = numbers()
    e = lambda sc, v: next(x for x in sw[sc]["variants"].values() if x["setting"] == "energy" and x["value"] == v)  # noqa
    gains = [x for sc in ("mission_20s", "random_20s") for x in sw[sc]["variants"].values()
             if x["setting"] in ("mu_step", "fresh_step", "fresh_cap")]
    gmax = max(abs(x["minus_v41"]["mean"]) for x in gains)
    fr = [x for sc in ("mission_20s", "random_20s") for x in sw[sc]["variants"].values() if x["setting"] == "fresh"]
    lo_e = [e(sc, v)["minus_v41"]["mean"] for sc in ("mission_20s", "random_20s") for v in (2.4, 2.6)]
    hi_e = [e(sc, v)["minus_v41"]["mean"] for sc in ("mission_20s", "random_20s") for v in (3.0, 3.2)]
    long32 = e("mission_240s", 3.2)["minus_v41"]
    long24 = e("mission_240s", 2.4)["minus_v41"]
    m20, r20, l240 = ho["mission_20s"]["policies"], ho["random_20s"]["policies"], ho["mission_240s"]["policies"]
    d = lambda P, p: P[p]["v41_minus"]  # noqa
    # without the 85 C hold (heldout_power_oct30, the same 12 runs): how far the linear thermal fit lets the board run
    rows = [json.load(open(f)) for f in (RP / "heldout_power_oct30" / "rows").glob("*.json")]
    tmax = max(r["temp_max_c"] for r in rows if r["phase_s"] == 240.0)
    t20 = max(r["temp_max_c"] for r in rows if r["phase_s"] == 20.0)
    assert t20 < 85.0
    return f'''<h3>19.11 Laptop-only additions, part 4: v4.1's settings, the replay's power model, a held-out check, the planner on the board (29–30 Oct 2026)</h3>
<p>Write-up <code>docs/laptop_additions_2026-10-30_part4.md</code>; nothing earlier was changed or re-scored (every new
setting of the replay is a switch whose default reproduces the stored results exactly; checked on stored runs of v5,
v4.1 and the planner, identical to the last digit).</p>
<p><b>1. How sensitive is v4.1 to its own settings?</b> One setting at a time moved away from what the board runs,
the others held, on the same seeds and link draws as v4.1 (<code>validation/hardware/replay_sweep.py</code>,
<code>replay/sweep_oct29/</code>, 295 runs; seeds 1–10, the 24-min mission seeds 1–3; old power model, as 19.8–19.10).
Bold: the 95 % interval excludes zero; positive = better than v4.1.</p>
{st}
<ul>
<li><b>v4.1 is flat in its update speeds and freshness cap</b> (at most {gmax:.4f} sAP from v4.1), and nearly flat in
its freshness target ({pm(min(x['minus_v41']['mean'] for x in fr))} to {pm(max(x['minus_v41']['mean'] for x in fr))}).
Nothing in the result depends on hand-tuning these.</li>
<li><b>The energy target is the one that matters.</b> A tighter target (2.4–2.6 W) scores {pm(min(lo_e))} to
{pm(max(lo_e))} on the short scenarios, a looser one (3.0–3.2 W) {pm(min(hi_e))} to {pm(max(hi_e))}; over the
24-min mission 3.2 W costs {pm(long32['mean'], long32['ci95'], False)} and 2.4 W ties ({pm(long24['mean'], long24['ci95'], False)}).
The direction is the replay's known bias (it favours less onboard work), so this is a hint, not a reason to change
2.8 W; it was checked on fresh seeds below.</li>
</ul>
<p><b>2. The replay's onboard power, corrected.</b> The replay spread the bench energy of one onboard inference over
the inference time, so a slower inference (CPU contention, throttling) drew <i>less</i> power; on the Pi the power
during inference stays the same when it slows (4.8 W cool, 4.7 W throttled, Part 6), so the energy grows. Corrected as
a switch (<code>replay.py --onboard-power power</code>: the bench power held for the whole inference), with the board
held at its 85 °C throttle limit (the firmware does that; with full power kept, the linear thermal fit would let the
simulated board reach {tmax:.0f} °C in the 24-min mission, which the real board never does). Re-validated against the same 240 hardware runs
(<code>replay/validate_main_oct30_power_t85/</code>, same scenarios, seeds and netem setting as
<code>validate_main_oct29_plant</code>):</p>
{ct}
<ul>
<li><b>The power and heat errors shrink</b>, but the replay still under-states the onboard-heavy baselines' heat, and
<b>its LEAF bias is unchanged</b> ({pm(new['paired_vs_v5']['leaf']['replay_diff'])} against a hardware tie). So the
bias is not in the power model; the likely cause is CPU contention on the Pi (onboard inference slowing the camera
loop, encoding and forecasting), which the replay does not model. Comparisons of policies that differ in onboard use
by a few per cent remain beyond the replay.</li>
</ul>
<p><b>3. Held-out check on fresh seeds, corrected model.</b> Seeds 11–20 (never used before), v4.1 against the
AccuMO-style planner, the LEAF-style weight and v4.1 with a 2.4 or 2.6 W target
(<code>replay/heldout_power_oct30/</code>, 100 runs, peak {t20:.0f} °C, so the 85 °C hold never acts there; the
24-min mission seeds 11–13 in
<code>replay/heldout_power_oct30_t85/</code>, 12 runs).</p>
{ht}
<ul>
<li><b>The ranking of 19.10 holds on fresh seeds and with the corrected power model:</b> the planner and LEAF tie or
lead v4.1 (random links {pm(-d(r20, 'accumo')['mean'], d(r20, 'accumo')['ci95'])} and
{pm(-d(r20, 'leaf')['mean'], d(r20, 'leaf')['ci95'])}; mission {pm(-d(m20, 'accumo')['mean'], d(m20, 'accumo')['ci95'])}
and {pm(-d(m20, 'leaf')['mean'], d(m20, 'leaf')['ci95'])}), by less than the replay's LEAF bias. The board campaign
below decides it.</li>
<li><b>The tighter energy target gains little</b> ({pm(-d(m20, 'sw_e2.4')['mean'], d(m20, 'sw_e2.4')['ci95'])} and
{pm(-d(r20, 'sw_e2.4')['mean'], d(r20, 'sw_e2.4')['ci95'])} at 2.4 W; 24-min mission
{pm(-d(l240, 'sw_e2.4')['mean'], d(l240, 'sw_e2.4')['ci95'])}): well inside the replay's error and in the direction of
its bias. <b>2.8 W stays.</b></li>
</ul>
<p><b>4. The AccuMO-style planner on the board.</b> <code>adaptive2.py --policy accumo</code> (with
<code>--mpc-horizon</code>, and <code>--mpc-context</code> for the camera-motion-conditioned decay from the live
forecaster). The search is one shared module, <code>validation/hardware/mpc_planner.py</code>.</p>
<ul>
<li><b>Same decisions as the replay's planner:</b> <code>tests/test_mpc_planner.py</code> runs both on the same replay
state every frame of two replayed missions (with and without the energy price) and requires identical choices.</li>
<li><b>Runs end to end:</b> a loopback run on the laptop (camera and GPU worker on 127.0.0.1, the network shaping
replaced by a no-op, the laptop's network untouched) completed all {smoke['n_frames']} frames; the planner took
{smoke['mpc']['plan_ms_median']:.2f} ms per frame (95th percentile {smoke['mpc']['plan_ms_p95']:.2f} ms) and used the
camera-motion curve in {sum(smoke['mpc']['tertile_counts'])} of {smoke['mpc']['n']} frames
(<code>planner_smoke_oct30.json</code>; a functional check, not a measurement).</li>
<li><b>Planner time:</b> {bench['ms_median']:.2f} ms median, {bench['ms_p95']:.2f} ms 95th percentile per frame on the
laptop, single-threaded, over {bench['n']} sampled states (<code>bench_planner.py</code>,
<code>planner_bench_laptop_oct30.json</code>), against a 33 ms frame budget. The same script runs on the Pi without
workers.</li>
</ul>
<p><b>5. The next board session, ready to run.</b></p>
<ul>
<li><code>tools/push_code_mesh.sh</code>: the code and configuration to the camera and the Jetson over the mesh
(with an import check on the camera); <code>tools/push_code.sh</code> updated for Wi-Fi.</li>
<li><code>tools/campaign_mesh4.sh</code>: v4.1, the planner (<code>accumo</code>) and the LEAF-style weight
(<code>leaf</code>, as in the 240-run campaign) × good links, mesh mission, multihop × 5 repetitions = 45 runs,
shuffled, resumable; it first times the planner on the camera Pi. About 6 h.</li>
<li><code>tools/campaign_ego160.sh</code>: the 160 px camera-motion step (19.9) timed on the Pi
(<code>egomotion_bench.py</code>), then v4.1 at 320 and 160 px × 2 scenarios × 3 repetitions = 12 runs
(<code>EGO_W=160</code>; the default stays 320). About 1.5 h.</li>
<li><code>validation/hardware/calib_hw.py</code>: the calibration check of 19.8 on real runs (the controller's logged
deadline probabilities against measured latencies, the same bins as the replay); tested on the loopback run and on
campaign 3 (runs from before the logging are skipped).</li>
</ul>
<p><b>6. The paper.</b> <code>paper/main.tex</code> has a new section "Hardware Check" (all
{hw['HwNPlacements']} placements; live runs: a Q90 JPEG to the laptop {hw['HwJpegOnTime']} on-time results/s against
{hw['HwKOneOnTime']} for the best split; INT8/FP16 splits within {hw['HwVdSplitMaxAbsDelta']} mAP with the VisDrone
YOLOv8s while Q90 JPEG loses {hw['HwVdJpegNinetyPct']} %, so a split can beat it by at most {hw['HwVdBoundPct']} %;
the simulator against {hw['HwSimRuns']} real runs, r = {hw['HwSimR']}), plus updates to the abstract, contributions and
limitations. Every number is generated from the result files (<code>evaluation/make_hardware.py</code>, traced in
<code>docs/claims_to_evidence.md</code>). Checked: the simulator code against the paper's policy equations (they
match); every cited DOI against CrossRef/DataCite (one fix: the YOLOv5 v7.0 entry is from 2022, not 2020).</p>
'''


STATE = ('<li><b>Laptop-only additions, part 4 (19.11, 30 Oct):</b> v4.1 is flat in its own settings except the energy '
         'target, and a tighter target gains nothing beyond the replay\'s error on fresh seeds (2.8 W stays); the '
         'replay\'s onboard power model was corrected (power error halved) but its pro-LEAF bias is not in the power '
         'model; the AccuMO-style planner runs on the board code (<code>--policy accumo</code>, same decisions as the '
         'replay\'s); the next mesh campaign and the 160 px test are scripted; the paper has a hardware section.</li>\n')
LEFT_ROWS = [
    ("5 repetitions of the 24-minute missions; the AccuMO-style planner of 19.10 against v4.1 and the LEAF-style "
     "weight on the board (replay done: within its error)", "Mesh; port the planner into <code>adaptive2.py</code>",
     "about 1 day; 1–2 days",
     "5 repetitions of the 24-minute missions; the AccuMO-style planner against v4.1 and the LEAF-style weight on the "
     "board (planner ported and tested, 19.11; <code>tools/campaign_mesh4.sh</code>, 45 runs)",
     "Mesh (<code>push_code_mesh.sh</code> first)", "about 1 day; about 6 h"),
    ("Cheaper camera-motion step on the Pi: <code>W_SMALL = 160</code>, measure the step time and the onboard speed-up "
     "(19.9)", "The camera Pi", "1–2 h",
     "Cheaper camera-motion step on the Pi: 160 px, the step time and the onboard speed-up (19.9; scripted, 19.11: "
     "<code>tools/campaign_ego160.sh</code>, 12 runs)", "The camera Pi on the mesh", "about 1.5 h"),
    ("Calibration of the deadline probabilities on hardware (the per-frame logging of 19.8; push adaptive2.py to the "
     "camera Pi first)", "The next board campaign", "no extra runs",
     "Calibration of the deadline probabilities on hardware (the per-frame logging of 19.8; analysis ready: "
     "<code>calib_hw.py</code>, 19.11)", "The next board campaign", "no extra runs"),
    ("Commit and push the work since <code>08bc5a28</code> (branch <code>main</code>)", "Your go-ahead", "minutes",
     "Commit the work since <code>b34f3738</code> (29 Oct, the 19.9–19.11 work); push <code>main</code>, which is "
     "1 local commit ahead of GitHub (<code>08bc5a28</code>)", "Your go-ahead", "minutes"),
    ("Paper and professor report update", "—", "1–2 weeks",
     "Paper: hardware section, claims and citations checked (19.11). Still to do: the controller paper (the argument of "
     "Part 20) and the professor's report", "—", "1–2 weeks"),
]


def html_row(a, b, c):
    return f"<tr><td>{a}</td><td>{b}</td><td>{c}</td></tr>"


def md_cell(s):
    return html_to_md(f"<p>{s}</p>").strip()


def main():
    h, m = HTML.read_text(), MD.read_text()
    sec = section()
    j = h.index('<h2 id="argument">')
    i = h.find("<h3>19.11 ")
    h = h[:i if 0 <= i < j else j] + sec + h[j:]
    j = m.index("## PART 20")
    i = m.find("### 19.11 ")
    m = m[:i if 0 <= i < j else j] + html_to_md(sec) + m[j:]
    h = re.sub(r"<li><b>Laptop-only additions, part 4 \(19\.11.*?</li>\n", "", h, flags=re.S)
    k = h.index('<div class="box state">')
    k = h.index("<ul>\n", k) + len("<ul>\n")
    h = h[:k] + STATE + h[k:]
    m = re.sub(r"^- \*\*Laptop-only additions, part 4 \(19\.11.*\n", "", m, flags=re.M)
    k = m.index("**State on 26 Oct 2026")
    k = m.index("\n- ", k) + 1
    m = m[:k] + html_to_md("<ul>" + STATE + "</ul>").strip() + "\n" + m[k:]
    for a, b, c, a2, b2, c2 in LEFT_ROWS:
        old_h, new_h = html_row(a, b, c), html_row(a2, b2, c2)
        if new_h not in h:
            assert h.count(old_h) == 1, a[:60]
            h = h.replace(old_h, new_h)
        old_m = f"| {md_cell(a)} | {md_cell(b)} | {md_cell(c)} |"
        new_m = f"| {md_cell(a2)} | {md_cell(b2)} | {md_cell(c2)} |"
        if new_m not in m:
            assert m.count(old_m) == 1, old_m[:80]
            m = m.replace(old_m, new_m)
    HTML.write_text(h)
    MD.write_text(m)
    print(f"report updated: 19.11, Part 1 bullet, what is left ({len(LEFT_ROWS)} rows)")


if __name__ == "__main__":
    main()
