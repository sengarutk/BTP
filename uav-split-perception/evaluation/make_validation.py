#!/usr/bin/env python3
"""Macros and the summary table for the simulator validation (validation/): ns-3, OMNeT++
(INET, Simu5G), the real network stack, and the channel generator's statistics.

Reads experiments/results/validation/: a2a_compare, lte_compare, omnet_rate_vs_sinr,
omnet_cell_sharing, omnet_cell_sharing_mixed, emulation (.csv); stream_summary,
calibrated_conclusions, channel_statistics, omnet_a2a_summary, relay_summary,
relay_forwarding_conclusions, sharing_conclusions (.json). Writes paper/generated_tables/val_metrics.tex and
table_validation.tex, and docs/claims_validation.md.
"""

import csv
import json
from pathlib import Path

import numpy as np

from evaluation.make_tables import Macros, num

REPO = Path(__file__).resolve().parent.parent
VAL = REPO / "experiments" / "results" / "validation"
TABLES = REPO / "paper" / "generated_tables"
LEDGER = REPO / "docs" / "claims_validation.md"


def read(name):
    with open(VAL / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> None:
    m = Macros()
    # V1 air-to-air
    src = "experiments/results/validation/a2a_compare.csv"
    a2a = [{k: float(v) for k, v in r.items()} for r in read("a2a_compare.csv")]
    both = [r for r in a2a if r["model_mbps"] > 0 and r["ns3_snr_limited_best_mbps"] > 0]
    ratio = [r["ns3_snr_limited_best_mbps"] / r["model_mbps"] for r in both]
    m.add("ValAtwoARatioMin", f"{min(ratio):.1f}", src)
    m.add("ValAtwoARatioMax", f"{max(ratio):.1f}", src)
    at50 = next(r for r in a2a if r["distance_m"] == 50.0)
    m.add("ValAtwoAModelFifty", num(at50["model_mbps"]), src)
    m.add("ValAtwoANsFifty", num(at50["ns3_snr_limited_best_mbps"]), src)
    last_std = max(r["distance_m"] for r in a2a if r["ns3_std_min_best_mbps"] > 0)
    first_std0 = min(r["distance_m"] for r in a2a if r["distance_m"] > last_std)
    last_snr = max(r["distance_m"] for r in a2a if r["ns3_snr_limited_best_mbps"] > 0)
    first_snr0 = min(r["distance_m"] for r in a2a if r["distance_m"] > last_snr)
    m.add("ValAtwoAStdRange", f"{last_std:.0f}--{first_std0:.0f}", src)
    m.add("ValAtwoASnrRange", f"{last_snr:.0f}--{first_snr0:.0f}", src)
    # V2 cellular
    src = "experiments/results/validation/lte_compare.csv"
    lte = sorted(({k: float(v) for k, v in r.items()} for r in read("lte_compare.csv")), key=lambda r: r["sinr_db"])
    top = lte[-1]
    m.add("ValLteNsPeak", num(top["ns3_mbps"]), src)
    m.add("ValLteModelPeak", num(top["tr36942_mbps"]), src)
    mid = [r for r in lte if r["ns3_mbps"] > 0 and r["tr36942_mbps"] > r["ns3_mbps"]]
    m.add("ValLteOptimisticMin", f"{min(r['tr36942_mbps'] / r['ns3_mbps'] for r in mid):.1f}", src)
    m.add("ValLteOptimisticMax", f"{max(r['tr36942_mbps'] / r['ns3_mbps'] for r in mid):.1f}", src)
    m.add("ValLteOptimisticSinrMax", f"{max(r['sinr_db'] for r in mid):.0f}", src)
    cross = [r for r in lte if r["ns3_mbps"] >= r["tr36942_mbps"] and r["ns3_mbps"] > 0]
    m.add("ValLtePessimisticSinrMin", f"{min(r['sinr_db'] for r in cross):.0f}", src)
    zero = max(r["sinr_db"] for r in lte if r["ns3_mbps"] == 0)
    m.add("ValLteCutoffDb", f"{zero:.1f}".replace("-", "$-$"), src)
    # V3/V4 packet-level streaming
    src = "experiments/results/validation/stream_summary.json"
    st = json.loads((VAL / "stream_summary.json").read_text())
    m.add("ValStreamSettings", str(st["n_settings"]), src)
    m.add("ValStreamR", f"{st['pearson_r']:.2f}", src)
    m.add("ValStreamMeanAbsDiff", f"{st['mean_abs_diff_fps']:.1f}", src)
    m.add("ValStreamBestAgrees", st["best_strategy_agrees"].replace("/", " of "), src)
    rows = st["rows"]
    optimistic = sum(r["py"] >= r["ns3"] - 0.05 for r in rows)
    m.add("ValStreamPyAtLeastNs", f"{optimistic} of {len(rows)}", src)
    split_gap = [r["py"] - r["ns3"] for r in rows if r["config"].startswith("k4")]
    jpeg_gap = [r["py"] - r["ns3"] for r in rows if r["config"].startswith("jpeg")]
    m.add("ValStreamSplitGap", f"{np.mean(split_gap):.1f}", src)
    m.add("ValStreamJpegGap", f"{np.mean(jpeg_gap):.1f}", src)
    # Calibrated system study
    src = "experiments/results/validation/calibrated_conclusions.json"
    c = json.loads((VAL / "calibrated_conclusions.json").read_text())
    names = {"default": "Default", "ns3_lte": "Lte", "ns3_a2a": "Atwoa", "ns3_both": "Both"}
    for v, tag in names.items():
        m.add(f"ValCal{tag}JpegBest", c[v]["jpeg_best_fixed_cells"].replace("/", " of "), src)
        m.add(f"ValCal{tag}SplitBeatsOnboard", c[v]["split_beats_onboard_cells"].replace("/", " of "), src)
    m.add("ValCalAdaptiveAllMax", f"{max(c[v]['adaptive_all_over_jpeg'][1] for v in c):.2f}", src)
    m.add("ValCalRelayGainMax", f"{max(c[v]['relay_gain_fps_max'] for v in c):.1f}", src)
    rel = [tuple(map(int, c[v]["relayed_split_on_time"].split("/"))) for v in c]
    m.add("ValCalRelaySplitPctMax", f"{100 * max(a / b for a, b in rel):.1f}", src)

    # C1 channel generator statistics
    src = "experiments/results/validation/channel_statistics.json"
    ch = json.loads((VAL / "channel_statistics.json").read_text())
    m.add("ValChanKHat", "/".join(f"{ch[k]['K_hat_dB']:.2f}" for k in ("K9dB", "K3dB", "K0dB")), src)
    m.add("ValChanClarkeErr", f"{ch['clarke_acf_max_abs_error']:.3f}", src)
    m.add("ValChanShadowStd", f"{ch['shadow_std_dB(target 4)']:.2f}", src)
    # O1 Simu5G NR uplink
    src = "experiments/results/validation/omnet_rate_vs_sinr.csv"
    nr = sorted(({k: float(v) for k, v in r.items()} for r in read("omnet_rate_vs_sinr.csv")), key=lambda r: r["sinr_db"])
    m.add("ValNrPeak", f"{max(r['simu5g_nr_mbps'] for r in nr):.0f}", src)
    near = lambda x: min(nr, key=lambda r: abs(r["sinr_db"] - x))  # noqa: E731
    for tag, x in (("Seventeen", 17), ("Ten", 10), ("Five", 5)):
        m.add(f"ValNr{tag}", f"{near(x)['simu5g_nr_mbps']:.1f}", src)
        m.add(f"ValNr{tag}Model", f"{near(x)['tr36942_mbps']:.1f}", src)
    m.add("ValNrCutoffDb", f"{max(r['sinr_db'] for r in nr if r['simu5g_nr_mbps'] == 0):.0f}".replace("-", "$-$"), src)
    # O2/O2b Simu5G cell sharing
    src = "experiments/results/validation/omnet_cell_sharing.csv"
    cs = {int(float(r["n_uavs"])): {k: float(v) for k, v in r.items()} for r in read("omnet_cell_sharing.csv")}
    m.add("ValShareCell", f"{cs[5]['cell_goodput_mbps']:.1f}", src)
    m.add("ValSharePfServed", f"{cs[10]['cell_goodput_mbps'] / cs[10]['per_uav_max_mbps']:.0f}", src)
    m.add("ValSharePfRate", f"{cs[10]['per_uav_max_mbps']:.1f}", src)
    m.add("ValShareJainTen", f"{cs[10]['jain_fairness']:.2f}", src)
    m.add("ValShareJainTwenty", f"{cs[20]['jain_fairness']:.2f}", src)
    src = "experiments/results/validation/omnet_cell_sharing_mixed.csv"
    mx = [{k: float(v) for k, v in r.items()} for r in read("omnet_cell_sharing_mixed.csv")]
    m.add("ValMixedMaxErr", f"{max(abs(r['saturated_got_mbps'] - r['waterfill_saturated_mbps']) for r in mx):.2f}", src)
    # O4 INET 802.11ac
    src = "experiments/results/validation/omnet_a2a_summary.json"
    o4 = json.loads((VAL / "omnet_a2a_summary.json").read_text())
    rg = o4["range_m_by_mcs"]
    m.add("ValInetRangeSame", f"{sum(v['inet'] == v['python'] for v in rg.values())} of {len(rg)}", src)
    m.add("ValInetNsLonger", f"{sum(v['ns3'] > v['python'] for v in rg.values())} of {len(rg)}", src)
    m.add("ValInetNormDiff", f"{o4['mean_abs_norm_diff']['inet_python']:.3f}", src)
    m.add("ValInetNsNormDiff", f"{o4['mean_abs_norm_diff']['ns3_python']:.3f}", src)
    m.add("ValInetMaxRange", f"{o4['max_range_m']['python']:.0f}", src)
    # O5 relay path in ns-3
    src = "experiments/results/validation/relay_summary.json"
    o5 = json.loads((VAL / "relay_summary.json").read_text())
    m.add("ValRelayHopMin", f"{o5['hop1_python_over_ns3_range'][0]:.1f}", src)
    m.add("ValRelayHopMax", f"{o5['hop1_python_over_ns3_range'][1]:.1f}", src)
    m.add("ValRelayPathMin", f"{o5['path_python_over_ns3_range'][0]:.1f}", src)
    m.add("ValRelayPathMax", f"{o5['path_python_over_ns3_range'][1]:.1f}", src)
    m.add("ValRelayVerdictAgree", f"{o5['deadline_verdict_agree']} of {o5['deadline_cases']}", src)
    m.add("ValRelaySplitOwnMs", f"{max(o5['split_relayed_with_b_own_ns3_ms'].values()):.0f}", src)
    src = "experiments/results/validation/relay_forwarding_conclusions.json"
    rf = json.loads((VAL / "relay_forwarding_conclusions.json").read_text())
    m.add("ValRelayFwdGainMax", f"{max(v['relay_gain_fps_max'] for v in rf.values()):.1f}", src)
    m.add("ValRelayFwdSplitPct", f"{100 * max(v['relayed_on_time_fraction']['split_k4_int8_zstd'] or 0 for v in rf.values()):.1f}", src)
    # V5 real network stack (loopback + netem)
    src = "experiments/results/validation/emulation.csv"
    em = [{k: (float(v) if k != "config" else v) for k, v in r.items()} for r in read("emulation.csv")]
    m.add("ValEmuMaxDiff", f"{max(abs(r['sim_on_time_fps'] - r['emu_on_time_fps']) for r in em):.1f}", src)
    j40 = next(r for r in em if r["config"] == "jpeg_q90" and r["rate_mbps"] == 40.0)
    m.add("ValEmuJpegFortySim", f"{j40['sim_on_time_fps']:.1f}", src)
    m.add("ValEmuJpegFortyEmu", f"{j40['emu_on_time_fps']:.1f}", src)
    m.add("ValEmuJpegFortyNoAck", f"{j40['sim_no_ack_wait_on_time_fps']:.1f}", src)
    # Cell-sharing sensitivity of the swarm conclusions
    src = "experiments/results/validation/sharing_conclusions.json"
    sh = json.loads((VAL / "sharing_conclusions.json").read_text())
    unfair = [sh[mdl][p]["adaptive_all"][-1] for mdl in ("capped", "weighted") for p in ("moderate", "blackout")]
    m.add("ValShareAdTwentyMin", f"{min(unfair):.1f}", src)
    m.add("ValShareAdTwentyMax", f"{max(unfair):.1f}", src)
    m.add("ValShareAdTwentyFair", f"{min(sh['waterfill'][p]['adaptive_all'][-1] for p in ('moderate', 'blackout')):.1f}", src)
    assert all(sh[mdl][p]["jpeg_beats_split_all_n"] and sh[mdl][p]["adaptive_all_best_all_n"] for mdl in sh for p in sh[mdl])
    m.add("ValShareRelayGainMax", f"{max(sh[mdl][p]['relay_gain_max'] for mdl in sh for p in sh[mdl]):.2f}", src)

    lines = [r"\begin{tabular}{@{}lllll@{}}", r"\toprule",
             r"Conclusion & Paper models & ns-3 cellular & ns-3 A2A & Both \\ \midrule"]
    rows_ = [("JPEG Q90 best fixed strategy (of 16)", lambda v: c[v]["jpeg_best_fixed_cells"].split("/")[0]),
             ("Split beats onboard (of 16)", lambda v: c[v]["split_beats_onboard_cells"].split("/")[0]),
             ("Adaptive (all) / JPEG Q90", lambda v: "{:.2f}--{:.2f}".format(*c[v]["adaptive_all_over_jpeg"])),
             ("Relayed split frames on time", lambda v: "{:,} / {:,}".format(*map(int, c[v]["relayed_split_on_time"].split("/")))),
             ("Largest relay gain (frames/s)", lambda v: f"{c[v]['relay_gain_fps_max']:.2f}")]
    for label, f in rows_:
        lines.append(label + " & " + " & ".join(f(v) for v in names) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    TABLES.mkdir(parents=True, exist_ok=True)
    (TABLES / "table_validation.tex").write_text("% Generated by evaluation/make_validation.py -- do not edit.\n"
                                                 + "\n".join(lines) + "\n", encoding="utf-8")
    (TABLES / "val_metrics.tex").write_text(m.tex().replace("make_tables.py", "make_validation.py"), encoding="utf-8")
    LEDGER.write_text(m.ledger().replace("make_tables.py", "make_validation.py")
                      .replace("; the sections below are written by the generators named in them (`evaluation/ledger.py`)", "")
                      .replace("# Claims-to-evidence ledger", "# Claims-to-evidence ledger: simulator validation"),
                      encoding="utf-8")
    print(f"{len(m.items)} macros")
    for n, v, _ in m.items:
        print(f"  {n} = {v}")


if __name__ == "__main__":
    main()
