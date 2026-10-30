#!/usr/bin/env python3
"""System-level value of the learned bottlenecks (learned_bottleneck.py) against image offload, with the paper's own
model (30 Oct 2026).

Every option is scored with simulation/system_model.py exactly as the paper's adaptive policy scores it (Section
"Adaptive policy"): U = f * p_on * A / A_ref, the expected number of accuracy-weighted on-time results per second, for
goodput B (Gaussian, sigma = 0.1 B, the policy's floor) and onboard speed t_full. Options, all on VisDrone2019-DET val
with the VisDrone YOLOv8s (experiments/results/visdrone_ft_split/, the measured CSVs the loader reads):
  JPEG q10-q95, post-hoc INT8 + zstd at k2, k4  payloads measured on the same frames as the learned codes
                                                 (measured_configs); host times from the VisDrone table
  onboard                                        visdrone_ft_split/split_pareto_analysis.csv (full_fp32)
  learned bottlenecks                            eval_*.json of learned_bottleneck.py, as OffloadConfig rows:
      edge FLOP fraction = (MACs of layers 0..k + MACs of the encoder) / MACs of YOLOv8s (thop, 640 x 640, the
      convention of core/inspect_graph.py); onboard non-DNN work = uint8 quantisation + zstd-1, measured on this
      host; server time = the post-hoc split's server time at the same cut + the decoder, measured on this host GPU
Onboard speeds: the paper's sweep (HARDWARE_SCENARIOS_MS) and the Pi 5 measured (placements_summary.json, throttled).
For each (t_full, B): the best option of each family and where the best learned bottleneck beats the best image.
usage: learned_bottleneck_system.py      -> experiments/results/learned_bottleneck/system.json
"""
import json
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from evaluation import learned_bottleneck as L  # noqa: E402
from simulation.system_model import (HARDWARE_SCENARIOS_MS, AdaptivePolicy, EdgeHardware, OffloadConfig,  # noqa: E402
                                     host_full_ms, load_offload_configs)

RES = REPO / "experiments" / "results"
VD = RES / "visdrone_ft_split"
GOODPUT = np.round(np.geomspace(0.25, 50.0, 31), 3)


def macs(module, x):
    import thop
    m, _ = thop.profile(module, inputs=(x,), verbose=False)
    return float(m)


def learned_rows(dev):
    import zstandard
    import copy
    det = L.load_detector(dev)
    x = torch.zeros(1, 3, 640, 640, device=dev)
    cpu = torch.device("cpu")                    # the encoder is profiled on a CPU copy: thop adds buffers to it
    # layers 0..k: the topology file the post-hoc split rows of split_pareto_analysis.csv use, so learned and post-hoc
    # rows share one basis; the encoder is counted with the same tool (thop) and added
    topo = json.load(open(RES / "yolov8s_graph_topology.json"))
    total = topo["summary"]["total_gmacs"] * 1e9
    post = {r.name: r for r in load_offload_configs(VD).values()}
    out = []
    for f in sorted((RES / "learned_bottleneck").glob("eval_*.json")):
        ev = json.load(open(f))
        if ev.get("width", 64) != 128 or ev.get("dec_layers", 1) != 2:
            continue                             # the pilot (width 64, 12 epochs) is not part of the family
        bn, ck = L.load_bottleneck(L.CKPT / f"{ev['config']}.pt", dev)
        feat = L.run_detector(det, x, ev["cut"])["cut"]
        edge = topo["splits"][f"k{ev['cut']}"]["edge_gmacs"] * 1e9
        enc = macs(copy.deepcopy(bn.enc).to(cpu), feat.cpu())
        cz = zstandard.ZstdCompressor(level=1)
        with torch.no_grad():                    # host times: quantise + zstd (CPU) and the decoder (GPU), median of 50
            z = bn.enc(feat)
            tq, td = [], []
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
        ref = post[f"k{ev['cut']}_int8_zstd"]
        cfg = OffloadConfig(name=f"learned_{ev['config']}", kind="split", cut=ev["cut"],
                            dtype=f"learned_{ev['config']}", payload_bytes=ev["payload_bytes_mean"],
                            edge_flop_frac=(edge + enc) / total, host_edge_proc_ms=float(np.median(tq)),
                            cloud_ms=ref.cloud_ms + float(np.median(td)), map50_95=ev["map50_95"], map50=ev["map50"],
                            delta_map50_95=ev["map50_95"] - ev["base_map50_95"])
        out.append((cfg, {"encoder_macs": enc, "edge_macs": edge, "total_macs": total,
                          "host_quant_zstd_ms": float(np.median(tq)), "host_decoder_ms": float(np.median(td))}))
    return out


def family(c):
    if c.kind == "onboard":
        return "onboard"
    if c.kind == "codec":
        return "image"
    return "learned" if c.dtype.startswith("learned") else "posthoc_split"


def measured_configs():
    """The options whose payload was measured on the same VisDrone DET val frames as the learned codes: JPEG at every
    quality (learned_bottleneck.py jpeg) and the post-hoc INT8 + zstd splits at k2 and k4 (learned_bottleneck.py
    posthoc), plus onboard. The VisDrone table (visdrone_ft_split/) keeps the COCO-measured payloads by design
    (build_visdrone_configs.py), so its sizes are replaced; its host times are kept, and JPEG qualities missing from
    it (q10-q35) take the q50 row's encode and server times."""
    tab = load_offload_configs(VD)
    out = [tab["full_fp32"]]
    for f in sorted((RES / "learned_bottleneck").glob("jpeg_q*.json")):
        m = json.load(open(f))
        ref = tab.get(m["config"], tab["jpeg_q50"])
        out.append(replace(ref, name=m["config"], dtype=f"q{m['q']}", payload_bytes=m["payload_bytes_mean"],
                           map50_95=m["map50_95"], map50=m["map50"], delta_map50_95=m["map50_95"] - m["base_map50_95"]))
    for f in sorted((RES / "learned_bottleneck").glob("posthoc_k*_int8_zstd.json")):
        m = json.load(open(f))
        out.append(replace(tab[m["config"]], payload_bytes=m["payload_bytes_mean"]))
    return out


def main():
    dev = torch.device("cuda")
    cfgs = measured_configs()
    lr = learned_rows(dev)
    cfgs += [c for c, _ in lr]
    pi_ms = json.load(open(RES / "hardware" / "placements_summary.json"))["devices"]["pi"]["full_ms"]
    hfull = host_full_ms(None, VD)
    out = {"learned": [dict(vars(c), **extra) for c, extra in lr], "goodput_mbps": GOODPUT.tolist(), "grid": []}
    for t_full in list(HARDWARE_SCENARIOS_MS) + [round(pi_ms, 1)]:
        hw = EdgeHardware(name=f"t_full={t_full:g}ms", t_full_ms=t_full, host_full_ms=hfull)
        pol = AdaptivePolicy(cfgs, hw)
        for B in GOODPUT:
            best = {}
            for c in cfgs:
                p = pol.predict(c, float(B))
                u = p["fps"] * p["p_on_time"] * c.map50_95 / pol.base_map
                fm = family(c)
                if fm not in best or u > best[fm][1]:
                    best[fm] = (c.name, u, p["latency_ms"])
            out["grid"].append({"t_full_ms": t_full, "goodput_mbps": float(B),
                                **{f: {"best": v[0], "utility": v[1], "latency_ms": v[2]} for f, v in best.items()}})
    # where does a learned bottleneck beat the best image option? The gain is reported only where the image delivers at
    # least USABLE accuracy-weighted on-time results per second (a ratio over a near-zero utility is meaningless)
    USABLE = 0.5
    wins = [g for g in out["grid"] if "learned" in g and g["learned"]["utility"] > g["image"]["utility"] * (1 + 1e-9)]
    by = {}
    for t in sorted({g["t_full_ms"] for g in out["grid"]}):
        w = [g for g in wins if g["t_full_ms"] == t]
        both = [g for g in w if g["image"]["utility"] >= USABLE]
        by[str(t)] = {"goodput_mbps": [g["goodput_mbps"] for g in w],
                      "max_goodput_mbps": max([g["goodput_mbps"] for g in w], default=None),
                      "max_gain_pct_where_image_usable": max([100 * (g["learned"]["utility"] / g["image"]["utility"] - 1)
                                                              for g in both], default=None),
                      "only_learned_usable_mbps": [g["goodput_mbps"] for g in w if g["image"]["utility"] < USABLE
                                                   <= g["learned"]["utility"]],
                      "best_learned": sorted({g["learned"]["best"] for g in w})}
    out["learned_beats_image"] = {"usable_threshold": USABLE, "cells": len(wins), "of": len(out["grid"]), "by_t_full": by}
    (RES / "learned_bottleneck").mkdir(parents=True, exist_ok=True)
    json.dump(out, open(RES / "learned_bottleneck" / "system.json", "w"), indent=1)
    for c, e in lr:
        print(f"{c.name:16s} {c.payload_bytes / 1e3:7.1f} kB  mAP {c.map50_95:.4f}  edge FLOPs {100 * c.edge_flop_frac:5.2f} %"
              f"  (encoder {e['encoder_macs'] / 1e6:.0f} MMACs)  quant+zstd {e['host_quant_zstd_ms']:.2f} ms  decoder "
              f"{e['host_decoder_ms']:.2f} ms")
    for t, v in out["learned_beats_image"]["by_t_full"].items():
        g = v["max_gain_pct_where_image_usable"]
        print(f"t_full {t:>6s} ms: learned beats image at {len(v['goodput_mbps'])} of {len(GOODPUT)} goodputs, up to "
              f"{v['max_goodput_mbps']} Mbit/s; max gain where the image is usable "
              f"{'n/a' if g is None else f'{g:.0f} %'}; only the learned code usable at {v['only_learned_usable_mbps']}"
              f" Mbit/s; {v['best_learned']}")

if __name__ == "__main__":
    main()
