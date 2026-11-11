#!/usr/bin/env python3
"""The break-even rule with a second detector, the VisDrone YOLO11s (paper 1, roadmap P1-4, 11 Nov 2026).

Accuracy and payload: evaluation/learned_bottleneck.py --detector yolo11s (JPEG at the 18 qualities of the rule,
post-hoc INT8 + zstd at k2 and k4, learned codes at k4) on the 548 VisDrone-DET val frames, the frames of the YOLOv8s
rows. Results: experiments/results/second_detector/yolo11s/.

Timings. The YOLOv8s rows take their host times from the measured table (visdrone_ft_split/split_pareto_analysis.csv)
and their device times from the boards. For the YOLO11s the same quantities are obtained as ratios to the YOLOv8s,
each measured the same way for both detectors:
  host            `profile`: this laptop's GPU, FP32, batch 1, 640 x 640, median of 100 timed passes after 20 warm-up
                  passes, CUDA-synchronised: the full network, layers 0..k (onboard) and layers k+1.. (server).
                  host full time = the table's YOLOv8s value x (YOLO11s / YOLOv8s full time); the server part of a
                  split at k = the table's YOLOv8s k-split server time - YOLOv8s suffix + YOLO11s suffix
  laptop, Jetson  the YOLOv8s device time x the host ratio (the Jetson was not run with the YOLO11s)
  Pi 5            measured: median per-phase latency of onboard inference at 640 in the matched onboard campaigns of
                  both detectors on both Pis (hardware/vid_campaign_onboard_vd{,_y11}_pi{2,3}), as a ratio
  edge fraction   MACs of layers 0..k (+ the bottleneck encoder) / MACs of the network (thop, 640 x 640), as for the
                  YOLOv8s rows; checked against the YOLOv8s topology file (yolov8s_graph_topology.json)
  learned codes   quantise + zstd on the host CPU and the decoder on the host GPU, median of 50 (as
                  learned_bottleneck_system.learned_rows)
usage: second_detector.py profile | analyse     -> experiments/results/second_detector/yolo11s/
"""
import argparse
import copy
import glob
import json
import statistics
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from evaluation import break_even_rule as b  # noqa: E402
from evaluation import learned_bottleneck as L  # noqa: E402
from evaluation.learned_bottleneck_system import VD, macs, measured_configs  # noqa: E402
from simulation.system_model import OffloadConfig, host_full_ms, load_offload_configs  # noqa: E402

RES = REPO / "experiments" / "results"
NAME = "yolo11s"
OUT = RES / "second_detector" / NAME
HW = RES / "hardware"
CUT = 4


def timed(fn, n=100, warm=20):
    for _ in range(warm):
        fn()
    torch.cuda.synchronize()
    ts = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        torch.cuda.synchronize()
        ts.append((time.perf_counter() - t0) * 1e3)
    return float(np.median(ts))


def forward_parts(det, x, cut):
    """Layers 0..cut, then the rest (the Ultralytics forward, split at cut; cut's output is the only tensor that
    crosses, which load-time asserts check through det.save)."""
    assert min(det.save) >= cut, det.save

    def prefix():
        h = x
        for m in det.model[:cut + 1]:
            h = m(h)
        return h
    feat = prefix()

    def suffix():
        y = [None] * (cut + 1)
        y[cut] = feat
        h = feat
        for m in det.model[cut + 1:]:
            if m.f != -1:
                h = y[m.f] if isinstance(m.f, int) else [h if j == -1 else y[j] for j in m.f]
            h = m(h)
            y.append(h if m.i in det.save else None)
        return h
    return prefix, suffix, feat


class Prefix(torch.nn.Module):
    def __init__(self, det, cut):
        super().__init__()
        self.layers = torch.nn.Sequential(*det.model[:cut + 1])

    def forward(self, x):
        return self.layers(x)


def cmd_profile(a):
    from ultralytics import YOLO
    dev = torch.device("cuda")
    out = {}
    x = torch.zeros(1, 3, 640, 640, device=dev)
    for name in ("yolov8s", NAME):
        det = YOLO(str(REPO / "weights" / f"{name}_visdrone.pt")).model.to(dev).float().eval()
        with torch.no_grad():
            pre, suf, feat = forward_parts(det, x, CUT)
            full = timed(lambda: det(x))
            t_pre, t_suf = timed(pre), timed(suf)
            ref = det(x)
            ref = ref[0] if isinstance(ref, (list, tuple)) else ref
            split = suf()
            split = split[0] if isinstance(split, (list, tuple)) else split
            assert torch.allclose(ref, split, atol=1e-4), name      # the split forward is the network's
        cpu = copy.deepcopy(det).cpu()
        m_total = macs(cpu, torch.zeros(1, 3, 640, 640))
        m_pre = macs(Prefix(copy.deepcopy(det).cpu(), CUT), torch.zeros(1, 3, 640, 640))
        out[name] = {"full_ms": full, "prefix_ms": t_pre, "suffix_ms": t_suf, "macs_total": m_total,
                     "macs_prefix": m_pre, "cut_channels": int(feat.shape[1]), "cut_hw": list(feat.shape[2:])}
        print(name, {k: (round(v, 4) if isinstance(v, float) else v) for k, v in out[name].items()}, flush=True)
    topo = json.load(open(RES / "yolov8s_graph_topology.json"))
    frac_topo = topo["splits"][f"k{CUT}"]["edge_gmacs"] / topo["summary"]["total_gmacs"]
    frac_here = out["yolov8s"]["macs_prefix"] / out["yolov8s"]["macs_total"]
    out["check_yolov8s_edge_fraction"] = {"topology_file": frac_topo, "thop_here": frac_here}
    assert abs(frac_topo - frac_here) < 0.01, (frac_topo, frac_here)
    pi = {}
    for tag, nm in (("vd", "yolov8s"), ("vd_y11", NAME)):
        v = []
        for f in glob.glob(str(HW / f"vid_campaign_onboard_{tag}_pi[23]" / "a2_*s640*.json")):
            v += [ph["lat_p50_ms"] for ph in json.load(open(f))["per_phase"].values() if "lat_p50_ms" in ph]
        pi[nm] = {"phases": len(v), "median_ms": statistics.median(v)}
    out["pi_onboard_640"] = pi
    out["ratio_host"] = out[NAME]["full_ms"] / out["yolov8s"]["full_ms"]
    out["ratio_pi"] = pi[NAME]["median_ms"] / pi["yolov8s"]["median_ms"]
    out["method"] = __doc__.split("\n\n")[2]
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(OUT / "profile.json", "w"), indent=1)
    print("host ratio", round(out["ratio_host"], 3), " Pi ratio", round(out["ratio_pi"], 3))


def code_timings(ev, det, prof, dev):
    """Encoder MACs, quantise + zstd (CPU) and decoder (GPU) times of one learned code (learned_rows' method)."""
    import zstandard
    bn, ck = L.load_bottleneck(L.CKPT / f"{ev['config']}.pt", dev)
    x = torch.zeros(1, 3, 640, 640, device=dev)
    feat = L.run_detector(det, x, ev["cut"])["cut"]
    enc = macs(copy.deepcopy(bn.enc).cpu(), feat.cpu())
    cz = zstandard.ZstdCompressor(level=1)
    tq, td = [], []
    with torch.no_grad():
        z = bn.enc(feat)
        for _ in range(50):
            t0 = time.perf_counter()
            _, q, _, _ = bn.quantize(z)
            cz.compress(q.cpu().numpy().tobytes())
            tq.append((time.perf_counter() - t0) * 1e3)
            zq = q.float()
            torch.cuda.synchronize()
            t0 = time.perf_counter()
            bn.dec(zq)
            torch.cuda.synchronize()
            td.append((time.perf_counter() - t0) * 1e3)
    return enc, float(np.median(tq)), float(np.median(td))


def configs():
    """The YOLO11s options (OffloadConfig rows on the YOLOv8s rows' basis) and its devices."""
    prof = json.load(open(OUT / "profile.json"))
    rh, rp = prof["ratio_host"], prof["ratio_pi"]
    p8, p11 = prof["yolov8s"], prof[NAME]
    lb = OUT / "learned_bottleneck"
    base8 = measured_configs()
    jp8 = {c.name: c for c in b.jpeg_grid(base8)}
    tab = load_offload_configs(VD)
    hf8 = host_full_ms(None, VD)
    hf11 = hf8 * rh
    jrows = {json.load(open(f))["config"]: json.load(open(f)) for f in lb.glob("jpeg_q*.json")}
    base11 = next(iter(jrows.values()))["base_map50_95"]
    onboard = next(c for c in base8 if c.kind == "onboard")
    onb = replace(onboard, map50_95=base11, map50=onboard.map50, delta_map50_95=0.0)
    jpeg = []
    for n, r in sorted(jrows.items(), key=lambda kv: kv[1]["q"]):
        c = jp8[n]
        # the same frames and the same encoder: the payload must be the YOLOv8s row's
        assert abs(r["payload_bytes_mean"] - c.payload_bytes) < 1e-6 * c.payload_bytes, (n, r["payload_bytes_mean"])
        jpeg.append(replace(c, map50_95=r["map50_95"], map50=r["map50"], delta_map50_95=r["map50_95"] - base11,
                            cloud_ms=c.cloud_ms - hf8 + hf11))
    others = [onb]
    srv = lambda cut_cfg: cut_cfg.cloud_ms - p8["suffix_ms"] + p11["suffix_ms"]       # noqa: E731
    for k in (2, 4):
        f = lb / f"posthoc_k{k}_int8_zstd.json"
        if f.exists() and k == CUT:          # the suffix was profiled at the k4 cut only
            r = json.load(open(f))
            ph = tab[f"k{k}_int8_zstd"]
            others.append(replace(ph, payload_bytes=r["payload_bytes_mean"],
                                  edge_flop_frac=p11["macs_prefix"] / p11["macs_total"], cloud_ms=srv(ph)))
    L.use_detector(NAME)
    det = L.load_detector("cuda")
    ref = tab[f"k{CUT}_int8_zstd"]
    extra = {}
    # the code timings are measured once and kept (code_timings.json), so that analyse is deterministic: re-timing on
    # every run moved the win count by a few cells (223 vs 220, 12 Nov 2026)
    tf = OUT / "code_timings.json"
    cached = json.load(open(tf)) if tf.exists() else {}
    for f in sorted(lb.glob("eval_k4_*.json")):
        ev = json.load(open(f))
        if ev["config"] in cached:
            enc, tq, td = (cached[ev["config"]][k] for k in ("encoder_macs", "host_quant_zstd_ms", "host_decoder_ms"))
        else:
            enc, tq, td = code_timings(ev, det, prof, "cuda")
        others.append(OffloadConfig(name=f"learned_{ev['config']}", kind="split", cut=ev["cut"],
                                    dtype=f"learned_{ev['config']}", payload_bytes=ev["payload_bytes_mean"],
                                    edge_flop_frac=(p11["macs_prefix"] + enc) / p11["macs_total"],
                                    host_edge_proc_ms=tq, cloud_ms=srv(ref) + td, map50_95=ev["map50_95"],
                                    map50=ev["map50"], delta_map50_95=ev["map50_95"] - ev["base_map50_95"]))
        extra[ev["config"]] = {"encoder_macs": enc, "host_quant_zstd_ms": tq, "host_decoder_ms": td}
    if extra != cached:
        json.dump(extra, open(tf, "w"), indent=1)
    devs = []
    for d, t in b.devices():
        devs.append((d, t * (rp if d.startswith("Pi") else rh)))
    return jpeg, others, devs, hf11, extra, prof


def cmd_analyse(a):
    jpeg, others, devs, hf11, extra, prof = configs()
    rows, viol, checked, wins = b.analyse(jpeg, others, devs=devs, hfull=hf11)
    out = {"detector": NAME, "rows": rows, "violations": viol, "wins_checked": checked, "wins_total": wins,
           "devices": devs, "host_full_ms": hf11, "codes": extra, "profile": prof,
           "options": [{"name": c.name, "kind": c.kind, "payload_bytes": c.payload_bytes, "map50_95": c.map50_95,
                        "edge_flop_frac": c.edge_flop_frac, "host_edge_proc_ms": c.host_edge_proc_ms,
                        "cloud_ms": c.cloud_ms} for c in jpeg + others]}
    json.dump(out, open(OUT / "break_even.json", "w"), indent=1)
    q95 = next(c for c in jpeg if c.name == "jpeg_q95")
    by = {(r["device"], r["code"]): r for r in rows}
    pi = next(d for d, _ in devs if d.startswith("Pi"))
    codes = sorted((c for c in others if c.name.startswith("learned_")), key=lambda c: c.payload_bytes)
    m = {"SdBaseMap": f"{others[0].map50_95:.3f}", "SdHostRatio": f"{prof['ratio_host']:.2f}",
         "SdPiRatio": f"{prof['ratio_pi']:.2f}", "SdWins": str(wins), "SdExc": str(len(viol)),
         "SdCodes": str(len(codes))}
    ph = next((c for c in others if c.name == f"k{CUT}_int8_zstd"), None)
    if ph:
        m["SdPosthocKib"] = f"{ph.payload_bytes / 1024:.0f}"
        m["SdPosthocOverQnf"] = f"{ph.payload_bytes / q95.payload_bytes:.1f}"
    if codes:
        m["SdCodeKibMin"], m["SdCodeKibMax"] = f"{codes[0].payload_bytes / 1024:.1f}", f"{codes[-1].payload_bytes / 1024:.1f}"
        m["SdCodeMapMin"] = f"{min(c.map50_95 for c in codes):.3f}"
        m["SdCodeMapMax"] = f"{max(c.map50_95 for c in codes):.3f}"
        for dn, dev in (("Pi", pi), ("Fast", "Jetson Orin Nano")):
            rs = [by[(dev, c.name)] for c in codes if (dev, c.name) in by]
            be = [r["b_be_mbps"] for r in rs if r["b_be_mbps"] is not None]
            w = [r["max_win_mbps"] for r in rs if r["max_win_mbps"] is not None]
            m[f"Sd{dn}BeMax"] = f"{max(be):.2f}" if be else "--"
            m[f"Sd{dn}WinMax"] = f"{max(w):.2f}" if w else "--"
            m[f"Sd{dn}WinCodes"] = str(len(w))
            m[f"Sd{dn}BeMin"] = f"{min(be):.2f}" if be else "--"
            m[f"Sd{dn}OnboardMs"] = f"{min(r['onboard_ms'] for r in rs):.0f}"
        m["SdEdgeFrac"] = f"{100 * min(c.edge_flop_frac for c in codes):.0f}"
        from simulation.system_model import DEADLINE_MS
        m["SdDeadlineMs"] = f"{DEADLINE_MS:.0f}"
    (OUT / "sd_metrics.tex").write_text("% Generated by evaluation/second_detector.py analyse -- do not edit.\n"
                                        + "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in m.items()))
    print(f"wins {wins}, checked {checked}, exceptions {len(viol)}")
    for k, v in m.items():
        print(k, v)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("profile")
    sub.add_parser("analyse")
    a = ap.parse_args()
    {"profile": cmd_profile, "analyse": cmd_analyse}[a.cmd](a)


if __name__ == "__main__":
    main()
