#!/usr/bin/env python3
"""Learned image codecs as the image family of the break-even rule (paper 1, roadmap P1-3, 11 Nov 2026).

Why. JPEG is a weak image codec; a reviewer can ask whether a learned image codec, sent whole, does what the split
tries to do (fewer bits at the same accuracy) without splitting the detector. Proposition prop:be-family holds for any
image family with payload b_q, onboard time e_q and accuracy A_q, so the rule can be evaluated with them.

Codecs (CompressAI 1.2.8 pretrained models, MSE-optimised, real bitstreams from compress(), the range/ANS coder):
  bmshj2018-hyperprior  quality 1-8   (Balle et al., ICLR 2018)
  mbt2018-mean          quality 1-8   (Minnen et al., NeurIPS 2018, mean-scale hyperprior without context model)
  cheng2020-anchor      quality 1-6   (Cheng et al., CVPR 2020; autoregressive context, slow to decode)
Method: exactly as the JPEG rows (benchmark_codecs.make_codec_hook): a forward pre-hook on layer 0 of the VisDrone
YOLOv8s replaces each letterboxed input by its encode -> decode version (padded to a multiple of 64 with edge pixels,
cropped back), on the 548 VisDrone-DET val frames, batch 1, mAP@[.5:.95]. Payload = the bytes of the compressed
strings + 4 bytes for the latent shape, per image. Every decode is from the bitstream.
Timings (host): the analysis transform's MACs at 640 x 640 (thop, the convention of the split rows' edge fraction:
onboard time = t_full x MACs ratio + host CPU time x the device scale), the entropy coding time on this CPU, and the
decode wall time on this GPU (decompress, incl. the context model's serial decoding).
Environment: /home/sengar/BTP/venv_lic (CompressAI installed there only; the main venv is not changed).
usage: learned_image_codecs.py eval [--codec NAME] [--q Q ...] | analyse -> experiments/results/learned_image_codecs/
"""
import argparse
import copy
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
OUT = REPO / "experiments" / "results" / "learned_image_codecs"
CODECS = {"bmshj2018-hyperprior": range(1, 9), "mbt2018-mean": range(1, 9), "cheng2020-anchor": range(1, 7)}


def load(name, q, dev):
    from compressai.zoo import bmshj2018_hyperprior, cheng2020_anchor, mbt2018_mean
    fn = {"bmshj2018-hyperprior": bmshj2018_hyperprior, "mbt2018-mean": mbt2018_mean,
          "cheng2020-anchor": cheng2020_anchor}[name]
    net = fn(quality=q, metric="mse", pretrained=True).eval().to(dev)
    net.update(force=True)
    return net


def roundtrip(net, x):
    """x: (3, H, W) in [0, 1] on the GPU. Returns the decoded image, the payload in bytes and the timings."""
    h, w = x.shape[1:]
    H, W = (h + 63) // 64 * 64, (w + 63) // 64 * 64
    xp = F.pad(x[None], (0, W - w, 0, H - h), mode="replicate")
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    with torch.no_grad():
        y = net.g_a(xp)
        torch.cuda.synchronize()
        t1 = time.perf_counter()
        enc = net.compress(xp)
        torch.cuda.synchronize()
        t2 = time.perf_counter()
        dec = net.decompress(enc["strings"], enc["shape"])
        torch.cuda.synchronize()
        t3 = time.perf_counter()
    nbytes = sum(len(s[0]) for s in enc["strings"]) + 4
    del y
    return dec["x_hat"][0, :, :h, :w].clamp(0, 1), nbytes, {"g_a_ms": (t1 - t0) * 1e3, "compress_ms": (t2 - t1) * 1e3,
                                                            "decompress_ms": (t3 - t2) * 1e3}


def cmd_eval(a):
    from ultralytics import YOLO
    from evaluation.detection_eval import paired_bootstrap, run_validation
    import thop
    dev = "cuda"
    yolo = YOLO(str(REPO / "weights" / "yolov8s_visdrone.pt"))
    base = run_validation(yolo, "visdrone_val", dev, name="lb_base_yolov8s_visdrone_full_fp32")
    OUT.mkdir(parents=True, exist_ok=True)
    for name, qs in CODECS.items():
        if a.codec and name != a.codec:
            continue
        for q in (a.q or qs):
            f = OUT / f"{name}_q{q}.json"
            if f.exists():
                continue
            net = load(name, q, dev)
            cpu = copy.deepcopy(net).cpu()          # thop adds buffers to what it profiles: a CPU copy
            x640 = torch.zeros(1, 3, 640, 640)
            with torch.no_grad():
                enc_macs, _ = thop.profile(cpu.g_a, inputs=(x640,), verbose=False)
                hyper_macs = thop.profile(cpu.h_a, inputs=(cpu.g_a(x640),), verbose=False)[0] if hasattr(cpu, "h_a") else 0.0
            del cpu
            log = {"bytes": [], "t": []}

            def hook(module, args):
                x = args[0]
                out = torch.empty_like(x)
                for b in range(x.shape[0]):
                    # Ultralytics' warm-up pass sends an uninitialised tensor (it can hold NaN); images are in [0, 1]
                    xb = torch.nan_to_num(x[b].float(), nan=0.0, posinf=1.0, neginf=0.0).clamp(0.0, 1.0)
                    dec, n, t = roundtrip(net, xb)
                    log["bytes"].append(n)
                    log["t"].append(t)
                    out[b] = dec.to(x.dtype)
                return (out,) + tuple(args[1:])
            res = run_validation(yolo, "visdrone_val", dev, name=f"lic_{name}_q{q}_yolov8s_visdrone",
                                 pre_forward_hook=hook, cache=False)
            n = res["num_images"]
            by, ts = log["bytes"][-n:], log["t"][-n:]            # the validator's warm-up pass comes first
            pb = paired_bootstrap(base, res, n_boot=a.n_boot)
            row = {"config": f"{name}_q{q}", "codec": name, "q": q, "n": len(by),
                   "payload_bytes_mean": float(np.mean(by)), "payload_bytes_p95": float(np.percentile(by, 95)),
                   "encoder_macs_640": float(enc_macs + hyper_macs), "g_a_macs_640": float(enc_macs),
                   **{k + "_median": float(np.median([t[k] for t in ts])) for k in ts[0]},
                   "map50_95": res["map50_95"], "map50": res["map50"], "base_map50_95": base["map50_95"],
                   **{f"boot_{k}": v for k, v in pb.items()}}
            json.dump(row, open(f, "w"), indent=1)
            print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()}), flush=True)
            del net
            torch.cuda.empty_cache()


def cmd_analyse(a):
    """B_be with the image family = JPEG, the learned codecs, and both (break_even_rule.analyse)."""
    from dataclasses import replace
    from evaluation import break_even_rule as b
    from evaluation.learned_bottleneck_system import family, measured_configs
    rows = {f.stem: json.load(open(f)) for f in OUT.glob("*_q*.json")}
    base = measured_configs()
    jpeg = b.jpeg_grid(base)
    q50 = next(c for c in jpeg if c.name == "jpeg_q50")
    topo = json.load(open(REPO / "experiments" / "results" / "yolov8s_graph_topology.json"))
    total = topo["summary"]["total_gmacs"] * 1e9
    jdec = 0.5      # ms: OpenCV decode of a 640-pixel JPEG on this CPU (video_codecs jpeg rows: 0.41-0.49 ms)
    lic = []
    for n, r in sorted(rows.items()):
        lic.append(replace(q50, name=f"lic_{n}", dtype=n, payload_bytes=r["payload_bytes_mean"],
                           edge_flop_frac=r["encoder_macs_640"] / total,
                           host_edge_proc_ms=max(0.0, r["compress_ms_median"] - r["g_a_ms_median"]),
                           cloud_ms=q50.cloud_ms - jdec + r["decompress_ms_median"], map50_95=r["map50_95"],
                           map50=r["map50"], delta_map50_95=r["map50_95"] - r["base_map50_95"]))
    codes = b.learned_and_joint() + b.entropy_codes()
    others = [c for c in base if family(c) != "image"] + codes
    out = {"method": cmd_analyse.__doc__, "options": [{"name": c.name, "payload_bytes": c.payload_bytes,
                                                       "map50_95": c.map50_95, "edge_flop_frac": c.edge_flop_frac,
                                                       "host_edge_proc_ms": c.host_edge_proc_ms,
                                                       "cloud_ms": c.cloud_ms} for c in lic], "cases": {}}
    m = {}
    for key, fam in (("jpeg", jpeg), ("lic", lic), ("both", jpeg + lic)):
        ar, viol, checked, wins = b.analyse(fam, others)
        out["cases"][key] = {"rows": ar, "violations": viol, "wins": wins}
        by = {(r["device"], r["code"]): r for r in ar}
        tag = {"jpeg": "Jpeg", "lic": "Lic", "both": "Both"}[key]
        m[f"Lic{tag}Wins"], m[f"Lic{tag}Exc"] = str(wins), str(len(viol))
        for dn, dev in (("Pi", "Pi 5 (throttled)"), ("Fast", "Jetson Orin Nano")):
            r = by.get((dev, "joint_k4_c4_w128_d2"))
            if r:
                m[f"Lic{tag}Joint{dn}Be"] = "--" if r["b_be_mbps"] is None else f"{r['b_be_mbps']:.2f}"
                m[f"Lic{tag}Joint{dn}Qstar"] = str(r["q_star"]).replace("lic_", "").replace("jpeg_q", "Q")
        print(f"{key}: wins {wins} exceptions {len(viol)}")
    # bytes at the accuracy of each JPEG quality: the smallest learned-codec payload that reaches it
    sv = []
    for q in jpeg:
        ok = [c.payload_bytes for c in lic if c.map50_95 >= q.map50_95]
        if ok:
            sv.append(1 - min(ok) / q.payload_bytes)
    m["LicSaveMedian"] = f"{100 * float(np.median(sv)):.0f}" if sv else "--"
    m["LicEncFracMin"] = f"{100 * min(c.edge_flop_frac for c in lic):.0f}"
    m["LicEncFracMax"] = f"{100 * max(c.edge_flop_frac for c in lic):.0f}"
    json.dump(out, open(OUT / "analysis.json", "w"), indent=1)
    (OUT / "lic_metrics.tex").write_text("% Generated by evaluation/learned_image_codecs.py analyse -- do not edit.\n"
                                         + "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in m.items()))
    for k, v in m.items():
        print(k, v)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("eval")
    e.add_argument("--codec", choices=list(CODECS))
    e.add_argument("--q", type=int, nargs="+")
    e.add_argument("--n-boot", type=int, default=300)
    sub.add_parser("analyse")
    a = ap.parse_args()
    {"eval": cmd_eval, "analyse": cmd_analyse}[a.cmd](a)


if __name__ == "__main__":
    main()
