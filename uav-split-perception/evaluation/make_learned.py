"""Numbers of the paper's learned-bottleneck subsection, from experiments/results/learned_bottleneck/ (30 Oct 2026).

Sources: summary.json (learned_bottleneck.py summary: every payload measured on the same VisDrone2019-DET val frames,
the JPEG size of each learned code's accuracy interpolated on the measured JPEG curve), system.json
(learned_bottleneck_system.py: the paper's policy model over goodput and onboard speed), train_*.json (data sizes).
The pilot configuration (width 64, 12 epochs) is excluded; the family is width 128, 2 decoder layers, 20 epochs.
mAP values are written in points (x 100), payloads in KiB (1 KiB = 1024 bytes).
Writes paper/generated_tables/lb_metrics.tex and its section of docs/claims_to_evidence.md.
"""
import json
from pathlib import Path

from evaluation.ledger import write_section

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "experiments" / "results" / "learned_bottleneck"
OUT = ROOT / "paper" / "generated_tables"
WORDS = {2: "Two", 4: "Four"}
ORD = {0: "One", 1: "Two", 2: "Three"}


def kib(b: float) -> str:
    return f"{b / 1024:.1f}"


def mp(x: float) -> str:
    """mAP in points."""
    return f"{100 * x:.1f}"


def main():
    s = json.load(open(D / "summary.json"))
    sysm = json.load(open(D / "system.json"))
    fam = [r for r in s["learned"] if r.get("width") == 128 and r.get("dec_layers") == 2]
    assert fam, "no learned configuration of the main family"
    tr = json.load(open(D / f"train_{fam[0]['config']}.json"))
    m, how = {}, {}

    def add(name, value, source, note):
        m[name] = value
        how[name] = (source, note)

    S, Y, T = "learned_bottleneck/summary.json", "learned_bottleneck/system.json", f"learned_bottleneck/train_{fam[0]['config']}.json"
    add("LbTrainImages", f"{tr['n_train']:,}".replace(",", "{,}"), T, "VisDrone2019-DET training images used")
    add("LbHoldImages", str(tr["n_holdout"]), T, "training images held out for monitoring")
    add("LbValImages", str(fam[0]["n"]), S, "VisDrone2019-DET val images every payload and mAP is measured on")
    add("LbEpochs", str(tr["epochs"]), T, "training epochs")
    add("LbBaseMap", mp(fam[0]["base_map50_95"]), S, "mAP of the unsplit VisDrone YOLOv8s, points")
    add("LbConfigs", str(len(fam)), S, "learned configurations of the family (width 128, 2 decoder layers)")
    best = max(fam, key=lambda r: r["map50_95"])
    add("LbMaxMap", mp(best["map50_95"]), S, "highest mAP of any learned code, points")
    add("LbMaxBytes", kib(best["payload_bytes_mean"]), S, "its mean payload, KiB")
    add("LbMaxCut", str(best["cut"]), S, "its cut")
    add("LbMaxJpegMap", "" if best["jpeg_map_at_same_bytes"] is None else mp(best["jpeg_map_at_same_bytes"]), S,
        "JPEG mAP at the same payload (interpolated on the measured JPEG curve), points")
    jq90 = next(r for r in s["jpeg"] if r["q"] == 90)
    add("LbJpegNinetyMap", mp(jq90["map50_95"]), S, "mAP of JPEG Q90 on the same frames, points")
    add("LbJpegNinetyBytes", kib(jq90["payload_bytes_mean"]), S, "mean JPEG Q90 payload, KiB")
    for cut in sorted({r["cut"] for r in fam}):
        rows = sorted((r for r in fam if r["cut"] == cut), key=lambda r: r["payload_bytes_mean"])
        w = WORDS[cut]
        win = [r for r in rows if r["bytes_saving_vs_jpeg_pct"] is not None and r["bytes_saving_vs_jpeg_pct"] > 0]
        lose = [r for r in rows if r["bytes_saving_vs_jpeg_pct"] is not None and r["bytes_saving_vs_jpeg_pct"] <= 0]
        assert len(win) + len(lose) == len(rows), "a learned code lies outside the measured JPEG accuracy range"
        add(f"LbK{w}N", str(len(rows)), S, f"learned codes at k{cut}")
        add(f"LbK{w}WinN", str(len(win)), S, f"k{cut} codes that need fewer bytes than JPEG for the same mAP")
        if win:
            add(f"LbK{w}SavingMin", f"{min(r['bytes_saving_vs_jpeg_pct'] for r in win):.0f}", S,
                f"smallest byte saving against JPEG at equal mAP among the winning k{cut} codes, %")
            add(f"LbK{w}SavingMax", f"{max(r['bytes_saving_vs_jpeg_pct'] for r in win):.0f}", S, "largest saving, %")
            add(f"LbK{w}WinMaxBytes", kib(max(r["payload_bytes_mean"] for r in win)), S,
                f"largest payload of a winning k{cut} code, KiB")
            ex = max(win, key=lambda r: r["bytes_saving_vs_jpeg_pct"])
            add(f"LbK{w}ExBytes", kib(ex["payload_bytes_mean"]), S, f"payload of the k{cut} code with the largest saving, KiB")
            add(f"LbK{w}ExMap", mp(ex["map50_95"]), S, "its mAP, points")
            add(f"LbK{w}ExJpegBytes", kib(ex["jpeg_bytes_for_same_map"]), S, "JPEG payload for the same mAP, KiB")
        for i, lo in enumerate(lose):            # every losing code, smallest payload first
            tag = f"LbK{w}Lose{ORD[i]}"
            add(f"{tag}Ch", str(lo["channels"]), S, "channels of this losing code")
            add(f"{tag}Res", "full" if lo["stride"] == 1 else "half", S, "its resolution relative to the cut tensor")
            add(f"{tag}Bytes", kib(lo["payload_bytes_mean"]), S, "its mean payload, KiB")
            add(f"{tag}Map", mp(lo["map50_95"]), S, "its mAP, points")
            add(f"{tag}JpegMap", mp(lo["jpeg_map_at_same_bytes"]), S, "JPEG mAP at the same payload, points")
            add(f"{tag}ExtraPct", f"{-lo['bytes_saving_vs_jpeg_pct']:.0f}", S,
                "extra bytes it needs against JPEG for the same mAP, %")
        add(f"LbK{w}LoseN", str(len(lose)), S, f"k{cut} codes that need more bytes than JPEG for the same mAP")
    by = sysm["learned_beats_image"]["by_t_full"]
    ts = sorted(by, key=float)
    fast, slow_, pi = ts[0], ts[-2], ts[-1]
    num = lambda x: "0" if x is None else f"{x:.1f}"  # noqa: E731   (the grid is log-spaced: 1 decimal)
    add("LbFastMs", f"{float(fast):g}", Y, "fastest onboard speed of the system grid (t_full, ms)")
    add("LbFastGoodput", num(by[fast]["max_goodput_mbps"]), Y, "largest goodput where a learned code beats the image there")
    add("LbSlowMs", f"{float(slow_):g}", Y, "slowest swept onboard speed (t_full, ms)")
    add("LbSlowGoodput", num(by[slow_]["max_goodput_mbps"]), Y, "the same at that speed (Mbit/s)")
    add("LbPiMs", f"{float(pi):.0f}", Y, "the measured Raspberry Pi 5 (t_full, ms)")
    add("LbPiWins", str(len(by[pi]["goodput_mbps"])), Y, "goodputs of the grid where a learned code wins on the Pi")
    add("LbPiGoodput", num(by[pi]["max_goodput_mbps"]), Y, "largest of them (Mbit/s)")
    add("LbGridGoodputs", str(len(sysm["goodput_mbps"])), Y, "goodputs in the grid")
    pw = [g for g in sysm["grid"] if str(g["t_full_ms"]) == pi and g["goodput_mbps"] in by[pi]["goodput_mbps"]]
    add("LbPiUtilMax", f"{max([max(g['learned']['utility'], g['image']['utility']) for g in pw], default=0.0):.1f}", Y,
        "most accuracy-weighted on-time results/s any option delivers where a learned code wins on the Pi")
    g = [v["max_gain_pct_where_image_usable"] for v in by.values() if v["max_gain_pct_where_image_usable"] is not None]
    add("LbMaxGainPct", f"{max(g):.0f}" if g else "0", Y, "largest relative gain where the image is usable, %")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "lb_metrics.tex").write_text("% Generated by evaluation/make_learned.py from experiments/results/learned_bottleneck"
                                        " -- do not edit.\n" + "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in m.items()))
    write_section('Learned bottleneck (Section "A Learned Bottleneck")',
                  "Generated by `evaluation/make_learned.py` (`make tables`) into `paper/generated_tables/lb_metrics.tex` "
                  "from `experiments/results/learned_bottleneck/`. mAP in points (x 100), payloads in KiB.",
                  [(k, v.replace("{,}", ","), *how[k]) for k, v in m.items()])
    for k, v in m.items():
        print(f"{k:22s} {v}")


if __name__ == "__main__":
    main()
