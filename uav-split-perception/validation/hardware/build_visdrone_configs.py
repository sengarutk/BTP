#!/usr/bin/env python3
"""Task R3 (25 Oct 2026): the swarm study's offload configurations with VisDrone accuracy. Copies
experiments/results/{split_pareto_analysis,codec_offload}.csv to experiments/results/visdrone_ft_split/ and replaces
ONLY the accuracy columns (map50, map50_95, delta_map50_95 and its CI) with the VisDrone fine-tuned YOLOv8s on
VisDrone2019-DET val: split configs from evaluate_mAP.py (visdrone_ft_split/accuracy_mAP_results.csv), codec configs
from codec_accuracy_visdrone.py (visdrone_ft_split/codec_accuracy.json). Payloads and times stay the measured ones.
A *_zstd config has the accuracy of its config without zstd (lossless), a kX_fp32 split that of the full model.
"""
import csv
import json
from pathlib import Path

R = Path(__file__).resolve().parent.parent.parent / "experiments" / "results"
D = R / "visdrone_ft_split"
COLS = ["map50", "map50_95", "delta_map50_95", "delta_map50_95_ci_low", "delta_map50_95_ci_high"]


def main():
    acc = {r["config"]: r for r in csv.DictReader(open(D / "accuracy_mAP_results.csv"))}
    for r in list(acc.values()):                   # lossless variants
        acc.setdefault(r["config"] + "_zstd", r)
    full = acc["full_fp32"]
    rows = list(csv.DictReader(open(R / "split_pareto_analysis.csv")))
    for r in rows:
        src = acc.get(r["config"]) or (full if r["dtype"] == "fp32" else None)
        if src is None:
            raise SystemExit(f"no VisDrone accuracy for {r['config']}")
        for k in COLS:
            r[k] = src[k] if k in src and src[k] != "" else ("0.0" if k.startswith("delta") else src["map50_95"])
    with open(D / "split_pareto_analysis.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    ca = json.load(open(D / "codec_accuracy.json"))
    base = ca["full_fp32"]["map50_95"]
    rows = list(csv.DictReader(open(R / "codec_offload.csv")))
    for r in rows:
        x = ca[r["config"]]
        r["map50"], r["map50_95"] = repr(x["map50"]), repr(x["map50_95"])
        r["delta_map50_95"] = repr(x["map50_95"] - base)
        r["delta_map50_95_ci_low"] = r["delta_map50_95_ci_high"] = ""   # no bootstrap for the codec settings
    with open(D / "codec_offload.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("wrote", D / "split_pareto_analysis.csv", D / "codec_offload.csv")


if __name__ == "__main__":
    main()
