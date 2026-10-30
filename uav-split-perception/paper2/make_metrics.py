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

    # ---- negative: a heat price adds nothing beyond the energy price (heat-v41)
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
    put("MpcMs", bench["ms_median"], "planner_bench_laptop_oct30.json ms_median", "{:.2f}")
    put("MpcPlanMsReplay", ac["mission_20s"]["policies"]["accumo"]["plan_ms_median"],
        "replay/accumo_oct29/accumo_summary.json mission_20s.policies.accumo.plan_ms_median (replay, beside other jobs)",
        "{:.1f}")

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
