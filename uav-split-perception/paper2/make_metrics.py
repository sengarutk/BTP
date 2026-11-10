#!/usr/bin/env python3
"""Every number of paper2/main.tex, generated from the result files (30 Oct 2026). Writes generated/metrics.tex (LaTeX
macros) and generated/metrics_sources.md (each macro, its value and the exact file and field it comes from).

Conventions of the source files: the campaign summaries (summarize_vid.py, summarize_mesh*.py) give paired differences
as reference minus policy (paired_vs_ref) or first minus second (the mesh "a-b|scenario" keys); signs are turned here so
that every macro reads "the priced controller minus the alternative" unless its name says otherwise. Streaming AP is the
original scoring with the live forecaster v2 ("sAP_quality_fcv2live") for the Wi-Fi campaigns and sAP with forecaster
("sAP_fc") on the mesh, as in the Results Brief; the standard-metric re-scoring (report_c_summary_visdrone.json) gives
the Holm-corrected p-values.
usage: python paper2/make_metrics.py
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HW = ROOT / "experiments" / "results" / "hardware"
OUT = Path(__file__).resolve().parent / "generated"
M, SRC = {}, []


def j(rel):
    return json.load(open(HW / rel))


def put(name, value, src, fmt="{:.4f}"):
    assert re.fullmatch(r"[A-Za-z]+", name), name
    s = fmt.format(value) if not isinstance(value, str) else value
    s = s.replace("-", "\\textminus{}") if s.startswith("-") else s
    M[name] = s
    SRC.append((name, s.replace("\\textminus{}", "−"), src))


def signed(x):
    return ("+" if x >= 0 else "-") + f"{abs(x):.4f}"


def main():
    # ---- testbed
    pl = j("placements_summary.json")
    put("PiFullMs", pl["devices"]["pi"]["full_ms"], "placements_summary.json devices.pi.full_ms", "{:.0f}")
    put("JetsonFullMs", pl["devices"]["jetson"]["full_ms"], "placements_summary.json devices.jetson.full_ms", "{:.1f}")

    # ---- heat as an accuracy cost: onboard-only runs on the Pi with clock and throttle logging (Part 17), and the same
    # runs re-scored with each result's latency at the full 2.4 GHz clock (counterfactual_full_clock, an emulation)
    th = j("onboard_sap/throttle_analysis_visdrone.json")
    cf = th["counterfactual_full_clock"]
    loss = [100 * (1 - v["sAP_fc_measured"] / v["sAP_fc_full_clock"]) for c in cf for v in cf[c].values()]
    put("ThrottleLossMin", min(loss), "onboard_sap/throttle_analysis_visdrone.json counterfactual_full_clock.*.*: "
        "1 - sAP_fc_measured / sAP_fc_full_clock, minimum over every condition and detector x 100", "{:.0f}")
    put("ThrottleLossMax", max(loss), "... maximum x 100", "{:.0f}")
    put("ThrottleCells", str(len(loss)), "... number of condition x detector cells")
    sc = th["summary"]["short_cool"]["s640vd"]
    put("ThrottleStartCool", sc["temp_start"], "onboard_sap/throttle_analysis_visdrone.json summary.short_cool.s640vd"
        ".temp_start (YOLOv8s onboard, runs started cool)", "{:.0f}")
    put("ThrottleShareCool", 100 * sc["throttled_share"], "... .throttled_share x 100", "{:.0f}")
    put("ThrottleTempCool", sc["temp_mean"], "... .temp_mean", "{:.0f}")
    put("ThrottleShareLong", 100 * th["summary"]["long_cool"]["s640vd"]["throttled_share"],
        "... summary.long_cool.s640vd.throttled_share x 100 (24-min runs)", "{:.0f}")

    # ---- C1 energy pricing, Wi-Fi: G9 energy campaign (ref v3+fc2 = A_stream_fc2; v4 = A_eco_tight, 2.8 W)
    e = j("vid_campaign_energy_summary_v2_live.json")["paired_vs_ref"]["sAP_quality_fcv2live"]["A_eco_tight"]
    put("EnGain", signed(-e["mean_diff"]), "vid_campaign_energy_summary_v2_live.json paired_vs_ref.sAP_quality_fcv2live"
        ".A_eco_tight.mean_diff (ref v3+fc2 minus v4, sign turned)")
    put("EnGainCi", e["ci95"], "... .A_eco_tight.ci95")
    put("EnPairs", str(e["n"] if "n" in e else e["pairs"]), "... .A_eco_tight.n")
    put("EnWins", str((e["n"] if "n" in e else e["pairs"]) - e["wins"]), "... pairs minus .wins (wins = ref ahead)")
    sce = j("vid_campaign_energy_summary_v2_live.json")["scenarios"]
    ref = sum(v["A_stream_fc2"]["sAP_quality_fcv2live"] for v in sce.values()) / len(sce)
    put("EnGainPct", 100 * -e["mean_diff"] / ref, "EnGain / mean over the 4 scenarios of scenarios.*.A_stream_fc2"
        ".sAP_quality_fcv2live (the unpriced controller's sAP) x 100", "{:.0f}")
    # replication, G11 (11 Oct; ref v4, v3+fc2 = A_stream_fc2)
    r = j("vid_campaign_v42_summary_v2_live.json")["paired_vs_ref"]["sAP_quality_fcv2live"]["A_stream_fc2"]
    put("EnRepGain", signed(r["mean_diff"]), "vid_campaign_v42_summary_v2_live.json paired_vs_ref.sAP_quality_fcv2live"
        ".A_stream_fc2.mean_diff (ref v4 minus v3+fc2)")
    put("EnRepCi", r["ci95"], "... .A_stream_fc2.ci95")
    put("EnRepWins", str(r["wins"]), "... .A_stream_fc2.wins")
    put("EnRepPairs", str(r["pairs"]), "... .A_stream_fc2.pairs")
    scr = j("vid_campaign_v42_summary_v2_live.json")["scenarios"]
    ref2 = sum(v["A_stream_fc2"]["sAP_quality_fcv2live"] for v in scr.values()) / len(scr)
    put("EnRepGainPct", 100 * r["mean_diff"] / ref2, "EnRepGain / mean over scenarios of scenarios.*.A_stream_fc2"
        ".sAP_quality_fcv2live x 100", "{:.0f}")
    # standard metric, VisDrone detections, Holm (report_c_summary_visdrone.json)
    rc = j("report_c_summary_visdrone.json")
    a = rc["vid_campaign_energy"]["paired"]["A_stream_fc2"]["sAP_fc"]["A_eco_tight"]
    put("EnVdGain", signed(-a["mean_diff"]), "report_c_summary_visdrone.json vid_campaign_energy.paired.A_stream_fc2"
        ".sAP_fc.A_eco_tight.mean_diff (sign turned)")
    put("EnVdHolm", a["p_holm"], "... .p_holm", "{:.3f}")
    b = rc["vid_campaign_v42"]["paired"]
    k = next(k for k in b if "A_stream_fc2" in b[k].get("sAP_fc", {}))
    bb = b[k]["sAP_fc"]["A_stream_fc2"]
    put("EnRepVdGain", signed(bb["mean_diff"]), f"report_c_summary_visdrone.json vid_campaign_v42.paired.{k}.sAP_fc"
        ".A_stream_fc2.mean_diff")
    put("EnRepVdHolm", bb["p_holm"], "... .p_holm", "{:.3f}")

    # ---- C1 on the mesh: no prices against v4.1 (mesh campaign 2, 3 scenarios x 3 reps)
    m2 = j("vid_campaign_mesh2_summary.json")
    np_ = m2["paired"]["noprice-v41|ALL"]
    put("MeshNoPriceSap", signed(-np_["sAP_fc"]["mean_diff"]), "vid_campaign_mesh2_summary.json paired['noprice-v41|ALL']"
        ".sAP_fc.mean_diff (sign turned: v4.1 minus no prices)")
    put("MeshNoPriceP", np_["sAP_fc"]["p_perm"], "... .sAP_fc.p_perm", "{:.3f}")
    put("MeshNoPriceW", np_["pi_w"]["mean_diff"], "... .pi_w.mean_diff (no prices minus v4.1)", "{:.2f}")
    put("MeshNoPriceC", np_["pi_temp_c"]["mean_diff"], "... .pi_temp_c.mean_diff", "{:.1f}")
    put("MeshNoPriceWp", np_["pi_w"]["p_perm"], "... .pi_w.p_perm", "{:.3f}")
    put("MeshPairs", str(np_["pi_w"]["pairs"]), "... .pi_w.pairs")
    put("MeshNoPriceThrottle", 100 * m2["cells"]["ALL|noprice"]["pi_throttled"][0], "vid_campaign_mesh2_summary.json "
        "cells['ALL|noprice'].pi_throttled[0] x 100", "{:.0f}")
    put("MeshVThrottle", 100 * m2["cells"]["ALL|v41"]["pi_throttled"][0], "cells['ALL|v41'].pi_throttled[0] x 100", "{:.0f}")
    lg = j("vid_campaign_mesh2_long_summary.json")["cells"]["ALL|v41"]
    put("MeshLongSap", lg["sAP_fc"][0], "vid_campaign_mesh2_long_summary.json cells['ALL|v41'].sAP_fc[0]", "{:.3f}")
    put("MeshLongN", str(lg["n"]), "... .n")
    put("MeshLongThrottle", 100 * lg["pi_throttled"][0], "... .pi_throttled[0] x 100", "{:.0f}")

    # ---- whole-system view (G11, 11 Oct): accuracy per watt of every board (camera Pi + Jetson edge drone)
    po = j("vid_campaign_v42_measured_summary.json")["pooled"]
    fx = po["fixed_laptop_m640q90"]
    v4x = {k: v for k, v in po.items() if k.startswith("A_eco")}
    put("SysEffFixed", fx["sAP_per_w_board"], "vid_campaign_v42_measured_summary.json pooled.fixed_laptop_m640q90"
        ".sAP_per_w_board (sAP per W of all boards)")
    put("SysEffMin", min(v["sAP_per_w_board"] for v in v4x.values()), "... pooled.A_eco*.sAP_per_w_board, minimum")
    put("SysEffMax", max(v["sAP_per_w_board"] for v in v4x.values()), "... maximum")
    put("SysEffRatioMin", fx["sAP_per_w_board"] / max(v["sAP_per_w_board"] for v in v4x.values()),
        "fixed / best v4.x", "{:.1f}")
    put("SysEffRatioMax", fx["sAP_per_w_board"] / min(v["sAP_per_w_board"] for v in v4x.values()),
        "fixed / worst v4.x", "{:.1f}")
    put("SysFixedAvail", 100 * fx["availability"], "... pooled.fixed_laptop_m640q90.availability x 100 (share of time "
        "with a result younger than 300 ms)", "{:.0f}")
    put("SysVAvailMin", 100 * min(v["availability"] for v in v4x.values()), "... pooled.A_eco*.availability, min x 100",
        "{:.0f}")

    # ---- negative results on heat pricing (corrected 10 Nov 2026): two different experiments.
    # (a) Wi-Fi main campaign: v5 = v4.2 + the predictive heat price ON TOP of the energy price, against v4.2 (same
    #     energy price, no heat price): does a heat price add anything beyond the energy price?
    v42 = j("vid_campaign_main_summary_v2_live.json")["paired_vs_ref"]["sAP_quality_fcv2live"]["v42"]
    put("HeatTopSap", signed(v42["mean_diff"]), "vid_campaign_main_summary_v2_live.json paired_vs_ref"
        ".sAP_quality_fcv2live.v42.mean_diff (ref v5 minus v42 = heat price on top minus energy price alone)")
    put("HeatTopSapCi", v42["ci95"], "... .v42.ci95")
    put("HeatTopPairs", str(v42["pairs"]), "... .v42.pairs")
    ms = j("vid_campaign_main_measured_summary.json")
    cw = ms["paired_vs_ref"]["v42"]["camera_w"]
    assert (ms["pooled"]["v42"]["camera_w"] - ms["pooled"]["v5"]["camera_w"]) * cw["diff"] >= 0   # diff = v42 - v5
    put("HeatTopW", f"{-cw['diff']:+.2f}", "vid_campaign_main_measured_summary.json paired_vs_ref.v42"
        ".camera_w.diff (v42 minus v5; sign turned: v5 minus v42)")
    put("HeatTopWCi", cw["ci"], "... .camera_w.ci", "{:.2f}")
    put("MainPairs", str(v42["pairs"]), "vid_campaign_main_summary_v2_live.json paired_vs_ref.sAP_quality_fcv2live"
        ".v42.pairs (every main-campaign comparison has the same 20 pairs)")
    import glob
    import statistics
    hz = []
    for f in sorted(glob.glob(str(HW / "vid_campaign_mesh2" / "a2_*__r?.json"))):
        lg = json.load(open(f))["measured_energy"]["log_t_w_c"]
        hz.append(len(lg) / (lg[-1][0] - lg[0][0]))
    put("PowerHz", statistics.median(hz), f"vid_campaign_mesh2/a2_*.json measured_energy.log_t_w_c: median samples "
        f"per second over {len(hz)} runs", "{:.1f}")
    # (b) mesh campaign 2: "heat" = the heat price INSTEAD of the energy price (arun_mesh.sh HEAT has no
    #     --energy-aware; its runs log no energy price), against v4.1 (energy price): which signal should be priced?
    h = m2["paired"]["heat-v41|ALL"]
    put("HeatSap", signed(h["sAP_fc"]["mean_diff"]), "vid_campaign_mesh2_summary.json paired['heat-v41|ALL'].sAP_fc"
        ".mean_diff (heat price minus v4.1)")
    put("HeatW", h["pi_w"]["mean_diff"], "... .pi_w.mean_diff", "{:.2f}")
    put("HeatC", h["pi_temp_c"]["mean_diff"], "... .pi_temp_c.mean_diff", "{:.1f}")
    put("HeatP", h["pi_w"]["p_perm"], "... .pi_w.p_perm", "{:.3f}")
    # negative: pricing the edge drone (Jetson) energy: 0.5 W budget (mesh 2), 1.2 W (mesh 3)
    je = m2["paired"]["v41e-v41|ALL"]["sAP_fc"]
    put("JetHalfSap", signed(je["mean_diff"]), "vid_campaign_mesh2_summary.json paired['v41e-v41|ALL'].sAP_fc.mean_diff")
    m3 = j("vid_campaign_mesh3_summary.json")["paired"]
    k3 = next(k for k in m3 if k.endswith("|ALL"))
    put("JetTwelveSap", signed(m3[k3]["sAP_fc"]["mean_diff"]), f"vid_campaign_mesh3_summary.json paired['{k3}']"
        ".sAP_fc.mean_diff")
    put("JetTwelveP", m3[k3]["sAP_fc"]["p_perm"], "... .sAP_fc.p_perm", "{:.3f}")

    # ---- C2 the objective must match the forecaster: v3+fc2 against v2 (wifi_fc2), and the 240-run ablations
    f2 = j("vid_campaign_wifi_fc2_summary_v2_live.json")["paired_vs_ref"]["sAP_quality_fcv2live"]["A_stream_fc2"]
    put("FcGain", signed(-f2["mean_diff"]), "vid_campaign_wifi_fc2_summary_v2_live.json paired_vs_ref"
        ".sAP_quality_fcv2live.A_stream_fc2.mean_diff (ref v2 minus v3+fc2, sign turned)")
    put("FcGainCi", f2["ci95"], "... .ci95")
    put("FcPairs", str(f2["n"] if "n" in f2 else f2["pairs"]), "... .n")
    mn = j("vid_campaign_main_summary_v2_live.json")["paired_vs_ref"]["sAP_quality_fcv2live"]
    for key, name in (("v5_nofc", "NoFc"), ("v5_flat", "Flat"), ("v5_lin", "Lin"), ("v5_exp", "Exp"), ("leaf", "Leaf")):
        put(f"Main{name}", signed(-mn[key]["mean_diff"]), f"vid_campaign_main_summary_v2_live.json paired_vs_ref"
            f".sAP_quality_fcv2live.{key}.mean_diff (ref v5 minus {key}; sign turned: {key} minus v5)")
        put(f"Main{name}Ci", mn[key]["ci95"], f"... .{key}.ci95")
        put(f"Main{name}Loss", mn[key]["mean_diff"], f"... .{key}.mean_diff (v5 minus {key}: positive = what {key} loses)")
    lit = {k: -mn[k]["mean_diff"] for k in ("aoi_thr", "conf_trigger", "jsq", "reward_offload")}
    put("MainLitMin", signed(max(lit.values())), "the same, aoi_thr/conf_trigger/jsq/reward_offload: the least negative")
    put("MainLitMax", signed(min(lit.values())), "the same: the most negative")
    put("LitBehindMin", -max(lit.values()), "v5 minus the literature schedulers (positive = v5 ahead): smallest margin")
    put("LitBehindMax", -min(lit.values()), "v5 minus the literature schedulers: largest margin")

    # ---- C3 where the decision belongs: v4.1 against the hierarchical chain (mesh 1: direct link; mesh 2: multihop)
    m1 = j("vid_campaign_mesh_summary.json")
    put("TopoDirectV", m1["cells"]["ALL|v41"]["sAP_fc"][0], "vid_campaign_mesh_summary.json cells['ALL|v41'].sAP_fc[0]",
        "{:.3f}")
    put("TopoDirectH", m1["cells"]["ALL|hier"]["sAP_fc"][0], "... cells['ALL|hier'].sAP_fc[0]", "{:.3f}")
    pa = m1["paired_v41_minus_hier"]["ALL"]["sAP_fc"]
    put("TopoDirectP", pa["p_perm"], "vid_campaign_mesh_summary.json paired_v41_minus_hier.ALL.sAP_fc.p_perm", "{:.3f}")
    put("TopoDirectPairs", str(pa["pairs"]), "... .pairs")
    put("TopoMultiV", m2["cells"]["multihop|v41"]["sAP_fc"][0], "vid_campaign_mesh2_summary.json cells['multihop|v41']"
        ".sAP_fc[0]", "{:.3f}")
    put("TopoMultiH", m2["cells"]["multihop|hier"]["sAP_fc"][0], "... cells['multihop|hier'].sAP_fc[0]", "{:.3f}")
    put("TopoDirectDiff", signed(pa["mean_diff"]), "vid_campaign_mesh_summary.json paired_v41_minus_hier.ALL.sAP_fc.mean_diff")
    put("TopoDirectDiffCi", pa["ci95"], "... .ci95")
    hm = m2["paired"]["hier-v41|multihop"]["sAP_fc"]
    put("TopoMultiDiff", signed(-hm["mean_diff"]), "vid_campaign_mesh2_summary.json paired['hier-v41|multihop'].sAP_fc"
        ".mean_diff (sign turned: v4.1 minus chain)")
    put("TopoMultiDiffCi", hm["ci95"], "... .ci95")
    put("TopoMultiPairs", str(hm["pairs"]), "... .pairs")
    put("MeshNoPriceSapCi", np_["sAP_fc"]["ci95"], "vid_campaign_mesh2_summary.json paired['noprice-v41|ALL'].sAP_fc.ci95")
    put("HeatSapCi", h["sAP_fc"]["ci95"], "vid_campaign_mesh2_summary.json paired['heat-v41|ALL'].sAP_fc.ci95")

    # ---- C4 against a published planner (replay): AccuMO-style, 19.10 (accumo_oct29) and 19.11 (held-out, power model)
    ac = j("replay/accumo_oct29/accumo_summary.json")
    for sc, name in (("mission_20s", "Mission"), ("random_20s", "Random"), ("mission_240s", "Long")):
        d = ac[sc]["policies"]["accumo"]["v41_minus"]
        put(f"Mpc{name}", signed(-d["mean"]), f"replay/accumo_oct29/accumo_summary.json {sc}.policies.accumo.v41_minus"
            ".mean (v4.1 minus planner; sign turned)")
        put(f"Mpc{name}Ci", d["ci95"], "... .ci95")
        put(f"Mpc{name}N", str(d["n"]), "... .n")
        dl = ac[sc]["policies"]["leaf"]["v41_minus"]
        put(f"Leaf{name}", signed(-dl["mean"]), f"... {sc}.policies.leaf.v41_minus.mean (sign turned)")
    ho = j("replay/heldout_power_oct30/accumo_summary.json")["random_20s"]["policies"]
    put("MpcHeldRandom", signed(-ho["accumo"]["v41_minus"]["mean"]), "replay/heldout_power_oct30/accumo_summary.json "
        "random_20s.policies.accumo.v41_minus.mean (sign turned)")
    put("MpcHeldRandomCi", ho["accumo"]["v41_minus"]["ci95"], "... .ci95")
    ck = j("replay/validate_main_oct30_power_t85/replay_check.json")
    put("ReplayLeafBias", signed(ck["paired_vs_v5"]["leaf"]["replay_diff"] - ck["paired_vs_v5"]["leaf"]["hardware_diff"]),
        "replay/validate_main_oct30_power_t85/replay_check.json paired_vs_v5.leaf.replay_diff - .hardware_diff")
    put("ReplaySapR", ck["agreement"]["sAP"]["pearson"], "... agreement.sAP.pearson", "{:.3f}")
    orc = j("replay/oracle_oct29_plant/oracle_summary.json")["scenarios"]
    sh = {k: v["v41_share_of_oracle_schedule"] for k, v in orc.items()}
    put("OracleShareMin", 100 * min(v for k, v in sh.items() if k != "random"), "replay/oracle_oct29_plant/oracle_summary"
        ".json scenarios.{mission,mission_mirror,static_good}.v41_share_of_oracle_schedule, minimum x 100", "{:.0f}")
    put("OracleShareMax", 100 * max(v for k, v in sh.items() if k != "random"), "... maximum x 100", "{:.0f}")
    put("OracleShareRandom", 100 * sh["random"], "... scenarios.random.v41_share_of_oracle_schedule x 100", "{:.0f}")
    cl = max(abs(v["clair_minus_v41"]["mean"]) for v in orc.values())
    inside = all(abs(v["clair_minus_v41"]["mean"]) <= v["clair_minus_v41"]["ci95"] for v in orc.values())
    assert inside, "a clairvoyant gain outside its interval: rewrite the sentence"
    put("ClairMax", cl, "... scenarios.*.clair_minus_v41.mean, largest absolute value (each inside its 95 % interval)")
    cal = j("replay/oracle_oct29_plant/oracle_summary.json")["calibration"]["p_on_vs_300ms"]
    assert not [b for b in cal["bins"] if b["n"] >= 100 and b["pred"] > b["observed"] + 0.02], "an over-confident bin"
    put("CalPred", 100 * cal["mean_pred"], "replay/oracle_oct29_plant/oracle_summary.json calibration.p_on_vs_300ms"
        ".mean_pred x 100 (v4.1's predicted chance of meeting 300 ms, every offloaded frame of the replay)", "{:.1f}")
    put("CalObs", 100 * cal["observed"], "... .observed x 100", "{:.1f}")
    put("CalEce", cal["ece"], "... .ece", "{:.3f}")
    put("CalFrames", f"{cal['n']:,}".replace(",", "{,}"), "... .n")
    # ---- several camera drones: calibrated swarm simulation and the two-camera hardware swarm
    sw = j("swarm_calibrated_mp_summary.json")
    k20 = sw["sizes"].index(20)
    cell = sw["summary"]["pi5|wifi_ap|waterfill|moderate"]
    put("SwarmTwentyAlone", cell["adaptive_all"][k20], "swarm_calibrated_mp_summary.json summary"
        "['pi5|wifi_ap|waterfill|moderate'].adaptive_all[20 drones] (detections/s per drone)", "{:.2f}")
    put("SwarmTwentyCoord", cell["adaptive_coord"][k20], "... .adaptive_coord[20 drones]", "{:.2f}")
    du = j("swarm_duo_summary.json")
    dd = du["paired"]["duo_none - duo_fixed (mean_sAP_fc)"]
    put("DuoAdaptGain", signed(dd["mean_diff"]), "swarm_duo_summary.json paired['duo_none - duo_fixed (mean_sAP_fc)']"
        ".mean_diff (both cameras adaptive minus both fixed, mean of the two cameras)")
    put("DuoAdaptCi", dd["ci95"], "... .ci95")
    put("DuoAdaptWins", str(dd["wins"]), "... .wins")
    put("DuoPairs", str(dd["n"]), "... .n")
    dc = du["paired"]["duo_coord - duo_none (mean_sAP_fc)"]
    put("DuoCoordGain", signed(dc["mean_diff"]), "swarm_duo_summary.json paired['duo_coord - duo_none (mean_sAP_fc)']"
        ".mean_diff")
    put("DuoCoordCi", dc["ci95"], "... .ci95")
    loss = [100 * (1 - du["cells"][f"{sc}|duo_none"]["pi_sAP_fc"][0] / du["cells"][f"{sc}|pi_alone"]["pi_sAP_fc"][0])
            for sc in ("mission", "static_good")]
    put("DuoShareLossMin", min(loss), "swarm_duo_summary.json cells: 1 - pi_sAP_fc(duo_none) / pi_sAP_fc(pi_alone), "
        "mission and static_good, minimum x 100", "{:.0f}")
    put("DuoShareLossMax", max(loss), "... maximum x 100", "{:.0f}")
    bench = j("planner_bench_laptop_oct30.json")
    lw = [ac[sc]["policies"]["v41"]["pi_w"] - ac[sc]["policies"]["accumo"]["pi_w"]
          for sc in ("mission_20s", "random_20s", "mission_240s")]
    put("MpcLessWMin", min(lw), "replay/accumo_oct29/accumo_summary.json {mission_20s, random_20s, mission_240s}"
        ".policies: v41.pi_w - accumo.pi_w, min (the planner runs less onboard)", "{:.2f}")
    put("MpcLessWMax", max(lw), "... max", "{:.2f}")
    put("MpcMs", bench["ms_median"], "planner_bench_laptop_oct30.json ms_median", "{:.2f}")
    put("MpcPlanMsReplay", ac["mission_20s"]["policies"]["accumo"]["plan_ms_median"],
        "replay/accumo_oct29/accumo_summary.json mission_20s.policies.accumo.plan_ms_median (replay, beside other jobs)",
        "{:.1f}")

    # ---- guarantees (Phase 1, 10 Nov 2026): paper2/theory_check.py -> theory_check/theory_check.json
    tc = j("theory_check/theory_check.json")
    t1, t2, tf = tc["theorem1"], tc["theorem2"], tc["temperature"]["fits"]
    src = "theory_check/theory_check.json"
    assert t1["all_hold"]
    put("ThmRuns", str(t1["runs"]), f"{src} theorem1.runs (priced runs with a logged price, every campaign)")
    put("ThmCamps", str(len(t1["by_campaign"])), f"{src} theorem1.by_campaign (number of campaigns)")
    put("ThmEta", tc["eta"], f"{src} eta (adaptive2.py default)", "{:g}")
    put("ThmMuMax", tc["mu_max"], f"{src} mu_max (adaptive2.py default)", "{:g}")
    put("ThmMarginFour", tc["mu_max"] / (tc["eta"] * 240), "mu_max / (eta x 240 updates): the price term's ceiling "
        "for a 4-minute run", "{:.2f}")
    put("ThmMarginLong", tc["mu_max"] / (tc["eta"] * 1440), "mu_max / (eta x 1440 updates): 24-minute run", "{:.3f}")
    bc = t1["by_campaign"]
    mesh = [bc[c] for c in ("vid_campaign_mesh", "vid_campaign_mesh2", "vid_campaign_mesh3")]
    put("ThmMeshExcess", max(x["max_avg_minus_budget_w"] for x in mesh), f"{src} by_campaign[mesh, mesh2, mesh3]"
        ".max_avg_minus_budget_w, max", "{:.2f}")
    put("ThmMeshRuns", str(sum(x["runs"] for x in mesh)), "... .runs, sum")
    lg = bc["vid_campaign_mesh2_long"]
    put("ThmLongExcess", lg["max_avg_minus_budget_w"], f"{src} by_campaign.vid_campaign_mesh2_long"
        ".max_avg_minus_budget_w", "{:.2f}")
    put("ThmLongCapPct", 100 * lg["mean_capped_share"], "... .mean_capped_share x 100 (updates with the price at its "
        "cap)", "{:.0f}")
    put("ThmLongCapW", lg["max_term_cap_only_w"], "... .max_term_cap_only_w", "{:.2f}")
    put("ThmLongHoldW", lg["max_term_hold_only_w"], "... .max_term_hold_only_w", "{:.2f}")
    put("ThmLongRuns", str(lg["runs"]), "... .runs")
    # audit of 11 Nov 2026: every update classified from the logged values (theory_check.py), per-campaign table
    put("ThmUpdates", f"{t1['updates']:,}".replace(",", "{,}"), f"{src} theorem1.updates")
    put("ThmUnexplained", str(t1["unexplained_neg_steps"] + t1["unexplained_pos_steps"]),
        f"{src} theorem1.unexplained_neg_steps + unexplained_pos_steps (updates the controller as written cannot make)")
    put("ThmOverRuns", str(t1["runs_over_budget"]), f"{src} theorem1.runs_over_budget")
    put("ThmCapRuns", str(t1["runs_capped"]), f"{src} theorem1.runs_capped")
    wifi_h = [bc[c] for c in ("vid_campaign_table", "vid_campaign_b", "vid_campaign_long")]
    put("ThmWifiHoldExcess", max(x["max_avg_minus_budget_w"] for x in wifi_h), f"{src} by_campaign[table, b, long]"
        ".max_avg_minus_budget_w, max (Wi-Fi campaigns with the cap and the hold)", "{:.2f}")
    put("ThmWifiHoldW", max(x["max_term_hold_only_w"] for x in wifi_h), "... .max_term_hold_only_w, max", "{:.2f}")
    alt = [r for r in t1["per_run"] if abs(r["budget_w"] - 2.8) > 1e-6]
    put("ThmAltBudgetRuns", str(len(alt)), f"{src} theorem1.per_run with budget_w != 2.8")
    put("ThmAltBudget", min(r["budget_w"] for r in alt), "... min budget_w of those runs", "{:.1f}")
    names = {"vid_campaign_main": "Wi-Fi, main$^\\dagger$", "vid_campaign_v42": "Wi-Fi, edge price$^\\dagger$",
             "vid_campaign_energy": "Wi-Fi, energy$^\\dagger$", "vid_campaign_b": "Wi-Fi, B",
             "vid_campaign_table": "Wi-Fi, table", "vid_campaign_long": "Wi-Fi, 24 min",
             "vid_campaign_mesh": "mesh 1", "vid_campaign_mesh2": "mesh 2", "vid_campaign_mesh3": "mesh 3",
             "vid_campaign_mesh2_long": "mesh, 24 min"}
    rows = []
    for c in names:
        x = bc[c]
        f2 = lambda v: f"{v:.2f}"  # noqa: E731
        rows.append(f"{names[c]} & {x['runs']} & {f2(x['max_avg_minus_budget_w'])} & {100 * x['mean_hold_only_share']:.1f}"
                    f" & {100 * x['mean_capped_share']:.1f} & {f2(x['max_term_hold_only_w'])} & {f2(x['max_term_cap_only_w'])}"
                    f" & {x['max_mu']:.1f} \\\\")
    put("ThmCampaignRows", "\n".join(rows), f"{src} theorem1.by_campaign (rows of Table tab:thm)")
    old = [bc[c] for c in ("vid_campaign_energy", "vid_campaign_v42", "vid_campaign_main")]
    put("ThmOldExcess", max(x["max_avg_minus_budget_w"] for x in old), f"{src} by_campaign[energy, v42, main]"
        ".max_avg_minus_budget_w, max (campaigns before the price cap and the blackout hold)", "{:.1f}")
    put("ThmOldMu", max(x["max_mu"] for x in old), "... .max_mu, max", "{:.0f}")
    put("ThmMsqMed", t2["msq_median_w2"], f"{src} theorem2.msq_median_w2 (v4.1 mesh runs: mean (P-B)^2)", "{:.2f}")
    put("ThmMsqMax", t2["msq_max_w2"], "... .msq_max_w2", "{:.1f}")
    put("ThmMsqRuns", str(t2["v41_mesh_runs"]), "... .v41_mesh_runs")
    put("ThmGapMed", t2["gap_bound_msq_median_value_per_s"], "... eta x msq_median / 2", "{:.3f}")
    put("ThmGapMax", t2["gap_bound_msq_max_value_per_s"], "... eta x msq_max / 2", "{:.2f}")
    put("ThmGapPct", 100 * t2["gap_bound_msq_max_value_per_s"] / 30.0, "ThmGapMax / 30 frames/s (the largest value "
        "rate: one full-accuracy result per frame) x 100", "{:.1f}")
    pl, ct = tf["plant"], tf["controller"]
    put("ThPlantA", pl["intercept_c"], f"{src} temperature.fits.plant.intercept_c (6 levels below 84 C)", "{:.1f}")
    put("ThPlantB", pl["c_per_w"], "... .c_per_w", "{:.1f}")
    put("ThRuns", str(pl["runs"]), "... .runs (runs of at least 20 minutes, second half)")
    put("ThMae", pl["mean_abs_error_c"], "... .mean_abs_error_c", "{:.1f}")
    put("ThMax", pl["max_abs_error_c"], "... .max_abs_error_c", "{:.1f}")
    put("ThBudgetEighty", pl["budget_for_80c_w"], "... .budget_for_80c_w", "{:.1f}")
    put("ThBudgetEightyCtl", ct["budget_for_80c_w"], f"{src} temperature.fits.controller.budget_for_80c_w", "{:.1f}")
    put("ThPredBudget", pl["intercept_c"] + pl["c_per_w"] * 2.8, "plant fit at the 2.8 W budget", "{:.0f}")
    put("ThTau", j("energy/energy_constants.json")["pi"]["thermal"]["tau_s"], "energy/energy_constants.json "
        "pi.thermal.tau_s (measured cool-down time constant)", "{:.0f}")
    sg1 = lambda v: ("+" if v >= 0 else "-") + f"{abs(v):.1f}"  # noqa: E731
    put("ThMeanErr", sg1(pl["mean_error_c"]), f"{src} temperature.fits.plant.mean_error_c (predicted minus measured)")
    be = pl["signed_error_by_campaign_c"]
    sg2 = lambda v: ("+" if v >= 0 else "-") + f"{abs(v):.2f}"  # noqa: E731
    put("ThBiasWifi", sg2(be["vid_campaign_long"]),
        "... .signed_error_by_campaign_c.vid_campaign_long")
    put("ThBiasMesh", sg2(be["vid_campaign_mesh2_long"]),
        "... .signed_error_by_campaign_c.vid_campaign_mesh2_long")
    lvl = j("energy/thermal_steady_pi.json")["levels"]
    used = [v for v in lvl.values() if v.get("arm_clock_mhz_last60", 0) >= 1450 and v["temp_steady_c"] < 84.0]
    put("ThLevels", str(len(used)), "energy/thermal_steady_pi.json levels with clock >= 1450 MHz and < 84 C (as replay.py)")
    hot = max(used, key=lambda v: v["temp_steady_c"])
    put("ThHotLevelC", hot["temp_steady_c"], "... hottest of them: temp_steady_c", "{:.1f}")
    put("ThHotLevelMhz", hot["arm_clock_mhz_last60"], "... its arm_clock_mhz_last60 (2400 MHz unthrottled)", "{:.0f}")

    # ---- relay noise (Phase 4, 10-11 Nov 2026): evaluation/relay_noise_sweep.py --calib pi5 (paper 2's calibrated
    #      swarm: Pi 5 758 ms, measured powers, 25 Mbit/s access point) -> relay_noise_pi5/summary.json
    rn, src = (j("../relay_noise_pi5/summary.json") if (HW.parent / "relay_noise_pi5" / "summary.json").exists()
               else None), "relay_noise_pi5/summary.json"
    hops = rn["setting"]["hops"] if rn else []
    if rn:
        shares = [v["share"] for h in hops for v in rn[f"hops{h}"]["relayed_on_time_adaptive_all"].values()
                  if v["share"] is not None]
        put("RnCells", str(sum(rn[f"hops{h}"]["cells"] for h in hops)), f"{src} hops*.cells (relay-on cells)")
        put("RnSeeds", str(rn["setting"]["seeds"]), f"{src} setting.seeds")
        put("RnRankChanges", str(sum(len(rn[f"hops{h}"]["ranking_changes"]) for h in hops)),
            f"{src} hops*.ranking_changes (cells whose strategy order differs from 3 dB, no loss)")
        put("RnShareClean", 100 * rn["hops1"]["relayed_on_time_adaptive_all"]["3dB_0pct"]["share"],
            f"{src} hops1.relayed_on_time_adaptive_all.3dB_0pct.share x 100", "{:.0f}")
        put("RnShareMin", 100 * min(shares), f"{src} min over hops, shadowing, loss of relayed_on_time share x 100", "{:.0f}")
        put("RnShareMax", 100 * max(shares), f"{src} max over hops, shadowing, loss of relayed_on_time share x 100", "{:.0f}")
        put("RnShareTwoHopTen", 100 * min(v["share"] for k, v in rn[f"hops{hops[-1]}"]["relayed_on_time_adaptive_all"].items()
                                          if k.endswith("_10pct")),
            f"{src} hops{hops[-1]}, 10 % loss, worst shadowing: relayed on-time share x 100", "{:.0f}")
        H = [rn[f"hops{h}"] for h in hops]
        pcs = [v for x in H for v in x["per_condition_adaptive_all"].values() if v["share_min"] is not None]
        put("RnSettings", str(sum(x["settings"] for x in H)), f"{src} hops*.settings (relay settings; x3 policies = RnCells)")
        put("RnCondShareMin", 100 * min(v["share_min"] for v in pcs), f"{src} min over hops*.per_condition_adaptive_all.share_min x 100", "{:.0f}")
        put("RnCondShareMax", 100 * max(v["share_max"] for v in pcs), f"{src} max over hops*.per_condition_adaptive_all.share_max x 100", "{:.0f}")
        put("RnNoiseSpreadPts", 100 * max(v["share_max"] - v["share_min"] for v in pcs),
            f"{src} max over conditions of (share_max - share_min) x 100: what shadowing x loss move the share", "{:.0f}")
        put("RnRelayedPct", 100 * max(x["relayed_per_camera_frame_max"] for x in H),
            f"{src} max hops*.relayed_per_camera_frame_max x 100", "{:.1f}")
        lead = [rn[f"hops{h}"]["adaptive_lead_fps"] for h in hops]
        put("RnLeadMin", min(x["min"] for x in lead), f"{src} hops*.adaptive_lead_fps.min", "{:.1f}")
        put("RnLeadMax", max(x["max"] for x in lead), f"{src} hops*.adaptive_lead_fps.max", "{:.1f}")
        gain = [rn[f"hops{h}"]["relay_gain_fps"] for h in hops]
        put("RnGainMin", min(x["adaptive_all_min"] for x in gain), f"{src} hops*.relay_gain_fps.adaptive_all_min", "{:.2f}")
        put("RnGainMax", max(x["adaptive_all_max"] for x in gain), f"{src} hops*.relay_gain_fps.adaptive_all_max", "{:.2f}")
        put("RnGainRelPct", 100 * max(x["adaptive_all_rel_abs_max"] for x in gain),
            f"{src} max over hops of relay_gain_fps.adaptive_all_rel_abs_max x 100 (|relay - no relay| / no relay, "
            "cells with >= 1 on-time frame/s per drone without relaying)", "{:.0f}")
        if "second_hop_cost_adaptive_all_fps" in rn:
            sh = rn["second_hop_cost_adaptive_all_fps"]
            put("RnSecondHopMin", sh["min"], f"{src} second_hop_cost_adaptive_all_fps.min", "{:.2f}")
            put("RnSecondHopMedian", sh["median"], f"{src} second_hop_cost_adaptive_all_fps.median", "{:.2f}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "metrics.tex").write_text("% Generated by paper2/make_metrics.py from experiments/results -- do not edit.\n" +
                                     "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in M.items()))
    (OUT / "metrics_sources.md").write_text(
        "# paper2 numbers and their sources (generated by paper2/make_metrics.py; paths under "
        "experiments/results/hardware/)\n\n| Macro | Value | Source |\n| --- | --- | --- |\n" +
        "".join(f"| `\\{k}` | {v} | {s} |\n" for k, v, s in SRC))
    for k, v, _ in SRC:
        print(f"{k:22s} {v}")


if __name__ == "__main__":
    main()
