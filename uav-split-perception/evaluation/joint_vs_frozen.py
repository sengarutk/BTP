#!/usr/bin/env python3
"""Paired test of each jointly trained code against the same code trained on the frozen detector (independent audit
of paper 1's v2 drafts, 11 Nov 2026). The eval files only bootstrap each code against the unsplit detector, so the
small joint gains had no confidence interval of their own.

Both codes are evaluated on the same 548 VisDrone-DET val frames, batch 1, and their per-image statistics are cached by
evaluation/detection_eval.run_validation (frozen: lb_yolov8s_visdrone_<tag>.pkl from learned_bottleneck.py eval;
joint: jb_yolov8s_visdrone_<tag>.pkl from joint_bottleneck.py eval, run 2). Before testing, the script checks that
the cached statistics reproduce the mAP stored in each eval file, so a stale cache cannot be used by mistake.
Paired image-level bootstrap of mAP(joint) - mAP(frozen) with detection_eval.paired_bootstrap (the paper's own).

usage: joint_vs_frozen.py [--n-boot 1000] [--workers 4]  -> experiments/results/joint_bottleneck/paired_joint_vs_frozen.json
"""
import argparse
import json
import pickle
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RES = REPO / "experiments" / "results"
CACHE = REPO / "experiments" / "cache" / "val_stats" / "visdrone_val"
OUT = RES / "joint_bottleneck"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    from evaluation.detection_eval import map_from_stats, paired_bootstrap
    rows = []
    for f in sorted(OUT.glob("eval_joint_*.json")):
        ev = json.load(open(f))
        tag = ev["config"][len("joint_"):]
        fz_eval = json.load(open(RES / "learned_bottleneck" / f"eval_{tag}.json"))
        joint = pickle.load(open(CACHE / f"jb_yolov8s_visdrone_{tag}.pkl", "rb"))
        frozen = pickle.load(open(CACHE / f"lb_yolov8s_visdrone_{tag}.pkl", "rb"))
        for name, res, ref in (("joint", joint, ev), ("frozen", frozen, fz_eval)):
            m50, m = map_from_stats(res["stats"])
            assert abs(m - ref["map50_95"]) < 1e-6 and res["num_images"] == ref["num_images"], \
                (name, tag, m, ref["map50_95"], res["num_images"])
        pb = paired_bootstrap(frozen, joint, n_boot=a.n_boot, workers=a.workers)
        row = {"code": tag, "payload_bytes_joint": ev["payload_bytes_mean"],
               "payload_bytes_frozen": fz_eval["payload_bytes_mean"], "map50_95_frozen": frozen["map50_95"],
               "map50_95_joint": joint["map50_95"], "gain": joint["map50_95"] - frozen["map50_95"],
               "images": joint["num_images"], "n_boot": a.n_boot, **{f"boot_{k}": v for k, v in pb.items()}}
        row["significant"] = bool(row["boot_delta_map50_95_ci_low"] > 0 or row["boot_delta_map50_95_ci_high"] < 0)
        rows.append(row)
        print(f"{tag:22s} frozen {row['map50_95_frozen']:.4f} joint {row['map50_95_joint']:.4f} gain {row['gain']:+.4f}"
              f"  95% CI [{row['boot_delta_map50_95_ci_low']:+.4f}, {row['boot_delta_map50_95_ci_high']:+.4f}]"
              f"  {'significant' if row['significant'] else 'not significant'}", flush=True)
    json.dump({"method": "paired image-level bootstrap (evaluation/detection_eval.paired_bootstrap), joint minus frozen, "
                         "same 548 VisDrone-DET val frames; cached per-image statistics checked against the eval files",
               "rows": rows}, open(OUT / "paired_joint_vs_frozen.json", "w"), indent=1)


if __name__ == "__main__":
    main()
