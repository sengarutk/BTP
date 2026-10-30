#!/usr/bin/env python3
"""Final Report update, 30 Oct 2026: the learned-bottleneck baseline (4.1), the published planner and the oracle bound in
the trace replay (new 4.12), the verdict's top-venue list and "What is left". Every number is read from the result
files: learned_bottleneck/summary.json and system.json, replay/accumo_oct29/accumo_summary.json,
replay/heldout_power_oct30/accumo_summary.json, replay/validate_main_oct30_power_t85/replay_check.json,
replay/oracle_oct29_plant/oracle_summary.json. Idempotent (each insertion is keyed by its own text).
usage: report_final_oct30.py     (the original is archived in experiments/results/hardware/_superseded/report_before_part5_oct30/)
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FR = ROOT.parent / "AEGIS-UAV Final Report.html"
R = ROOT / "experiments" / "results"
RP = R / "hardware" / "replay"


def pm(x):
    return f"{x + 0.0:+.4f}".replace("-", "−")


def texts():
    s = json.load(open(R / "learned_bottleneck" / "summary.json"))
    fam = [r for r in s["learned"] if r.get("width") == 128 and r.get("dec_layers") == 2]
    win = [r for r in fam if r["bytes_saving_vs_jpeg_pct"] is not None and r["bytes_saving_vs_jpeg_pct"] > 0]
    best = max(fam, key=lambda r: r["map50_95"])
    q90 = next(r for r in s["jpeg"] if r["q"] == 90)
    sy = json.load(open(R / "learned_bottleneck" / "system.json"))
    by = sy["learned_beats_image"]["by_t_full"]
    ts = sorted(by, key=float)
    pw = [g for g in sy["grid"] if str(g["t_full_ms"]) == ts[-1] and g["goodput_mbps"] in by[ts[-1]]["goodput_mbps"]]
    umax = max(max(g["learned"]["utility"], g["image"]["utility"]) for g in pw) if pw else 0.0
    lb = (f"<p><b>A learned bottleneck changes the bits, not the verdict (30 Oct).</b> A small encoder and decoder trained "
          f"at layer 2 or 4 of the VisDrone YOLOv8s, with the detector frozen (distillation of its own neck outputs, no "
          f"labels), needs {min(r['bytes_saving_vs_jpeg_pct'] for r in win):.0f}–"
          f"{max(r['bytes_saving_vs_jpeg_pct'] for r in win):.0f} % fewer bytes than JPEG for the same accuracy, measured on "
          f"the same VisDrone frames, which no post-hoc split does. It tops out at {best['map50_95']:.3f} mAP "
          f"({best['payload_bytes_mean'] / 1e3:.0f} kB) against {q90['map50_95']:.3f} for a JPEG q90 of "
          f"{q90['payload_bytes_mean'] / 1e3:.0f} kB. In the system model it beats the image only with fast onboard "
          f"compute and a slow link (YOLOv8s at {float(ts[0]):.0f} ms per frame: up to "
          f"{by[ts[0]]['max_goodput_mbps']:.1f} Mbit/s), and on the measured Pi ({float(ts[-1]):.0f} ms) only up to "
          f"{by[ts[-1]]['max_goodput_mbps']:.1f} Mbit/s, where no option delivers more than {umax:.1f} accuracy-weighted "
          f"on-time results per second; above that, running the first layers and the encoder onboard costs more time than the "
          f"smaller payload saves. "
          f"(Results Brief 19.12.)</p>\n")
    ac = json.load(open(RP / "accumo_oct29" / "accumo_summary.json"))
    ho = json.load(open(RP / "heldout_power_oct30" / "accumo_summary.json"))
    ck = json.load(open(RP / "validate_main_oct30_power_t85" / "replay_check.json"))
    orc = json.load(open(RP / "oracle_oct29_plant" / "oracle_summary.json"))["scenarios"]
    sh = {k: 100 * v["v41_share_of_oracle_schedule"] for k, v in orc.items()}
    d = lambda S, sc, p: -S[sc]["policies"][p]["v41_minus"]["mean"]  # noqa: E731
    bias = ck["paired_vs_v5"]["leaf"]["replay_diff"] - ck["paired_vs_v5"]["leaf"]["hardware_diff"]
    pl = (f"<h3>4.12 Against a published planner, and the distance from the best schedule (trace replay)</h3>\n"
          f"<p>An AccuMO-style planner (MobiCom 2023: one setting per server for the next 30 frames, 252 plans, the "
          f"content-conditioned decay) was re-implemented in the trace replay. Against v4.1 it tied on the mission "
          f"({pm(d(ac, 'mission_20s', 'accumo'))}) and was slightly ahead on random link faults "
          f"({pm(d(ac, 'random_20s', 'accumo'))}; {pm(d(ho, 'random_20s', 'accumo'))} on fresh seeds) and over 24-minute "
          f"missions ({pm(d(ac, 'mission_240s', 'accumo'))}), but a LEAF-style fixed weight was ahead by as much, and the "
          f"replay is known to favour such low-onboard policies by about {bias:.3f} sAP. So the claim narrows to: a greedy "
          f"priced choice does as well as a 30-frame planner. The planner now runs in the board code "
          f"(<code>adaptive2.py --policy accumo</code>); its mesh campaign is scripted. In the same replay v4.1 reaches "
          f"{min(v for k, v in sh.items() if k != 'random'):.0f}–{max(v for k, v in sh.items() if k != 'random'):.0f} % of "
          f"a hindsight per-phase oracle ({sh['random']:.0f} % when the faults change every 4 s), gains nothing from a "
          f"clairvoyant link, and its own settings are not hand-tuned: only the energy target moves accuracy, and 2.8 W "
          f"holds on fresh seeds. (Results Brief 19.8–19.11.)</p>\n")
    return lb, pl


VERDICT_OLD = ("A top venue would additionally need a learned feature-compression baseline for the split result, two or "
               "more camera drones on the mesh, a published scheduler (AoPI- or AccuMO-style) re-implemented on the "
               "testbed, and ideally a flight or outdoor test.")
VERDICT_NEW = ("A top venue would additionally need two or more camera drones on the mesh, the published scheduler measured "
               "on the testbed, and ideally a flight or outdoor test. Since 30 October a learned feature-compression "
               "baseline is measured (it beats JPEG on bits, and on the Pi end to end only at the lowest goodputs) and an "
               "AccuMO-style planner is "
               "re-implemented (in the trace replay, where it ties v4.1, and in the board code, where its campaign is "
               "scripted).")
LEFT = [("<li>One published baseline (A²-UAV-style or AccuMO-style) re-implemented on the testbed.</li>",
         "<li>The AccuMO-style planner against v4.1 and the LEAF-style weight on the mesh (ported and tested; "
         "<code>tools/campaign_mesh4.sh</code>, 45 runs, about 6 h).</li>"),
        ("<li>Commit and push the work since <code>08bc5a28</code>.</li>",
         "<li>Commit the work since <code>b34f3738</code> and push <code>main</code> (1 commit ahead of GitHub).</li>"),
        ("<li>Write the paper from Parts 17–20 of the Results Brief and this report; update the professor's report.</li>",
         "<li>Paper 1 has a hardware section and the learned bottleneck; paper 2 (the priced controller) has a first draft "
         "in <code>paper2/</code>; finish it after the planner campaign.</li>")]


def main():
    h = FR.read_text()
    lb, pl = texts()
    a = "because small objects lose their detail first.</p>\n"
    assert h.count(a) == 1
    i = h.index(a) + len(a)
    j = h.index("<h3>4.2 ", i)
    h = h[:i] + lb + h[j:]                          # replaces an earlier version of the paragraph (idempotent)
    if "<h3>4.12 " in h:
        i = h.index("<h3>4.12 ")
        h = h[:i] + h[h.index("<h2", i):]
    k = h.index("<h2", h.index("<h3>4.11 "))
    k = h.rfind("</section>", 0, k) if h.rfind("</section>", 0, k) > h.index("<h3>4.11 ") else k
    h = h[:k] + pl + h[k:]
    if VERDICT_NEW not in h:
        assert h.count(VERDICT_OLD) == 1
        h = h.replace(VERDICT_OLD, VERDICT_NEW)
    for old, new in LEFT:
        if new not in h:
            assert h.count(old) == 1, old
            h = h.replace(old, new)
    FR.write_text(h)
    print("Final Report updated: 4.1 learned bottleneck, 4.12 planner and oracle, verdict, what is left")


if __name__ == "__main__":
    main()
