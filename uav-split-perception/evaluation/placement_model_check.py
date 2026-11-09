#!/usr/bin/env python3
"""How well the placement model (validation/hardware/placement.py) predicts the live pipeline runs.

Reads (experiments/results/hardware/):
  placements.csv     the model's prediction for every placement (chain, cuts, encodings -> frames/s)
  live_summary.csv   the live runs (median delivered frames/s over runs, per placement)
Matches every live placement to its model row by (chain, cuts, encodings) and computes model fps / live median fps.
Writes a NEW result file, experiments/results/hardware/placement_model_check.json, with every matched pair, the
ratio range for one- and two-device chains and for three-device chains, and whether model and live runs both rank
every image-offload placement from the Pi above every split placement from the Pi. No existing file is modified.

usage: python -m evaluation.placement_model_check [--out PATH]
"""
import argparse
import csv
import json
from pathlib import Path

HW = Path(__file__).resolve().parent.parent / "experiments" / "results" / "hardware"
OUT = HW / "placement_model_check.json"

# Live placement (live_summary.csv) -> model row (placements.csv: chain, cuts, encs). Cut -1 is the camera frame
# (JPEG Q90); the live splits sent INT8+zstd (validation/hardware/pipeline_node.py), as the model rows assume.
LIVE_TO_MODEL = {
    "jetson_solo": ("jetson", "", ""),
    "pi_solo": ("pi", "", ""),
    "pi_laptop_jpeg": ("pi>laptop", "-1", "jpeg"),
    "pi_jetson_jpeg": ("pi>jetson", "-1", "jpeg"),
    "jetson_laptop_jpeg": ("jetson>laptop", "-1", "jpeg"),
    "pi_laptop_k1": ("pi>laptop", "1", "int8_zstd"),
    "pi_laptop_k2": ("pi>laptop", "2", "int8_zstd"),
    "pi_laptop_k4": ("pi>laptop", "4", "int8_zstd"),
    "pi_jetson_k4": ("pi>jetson", "4", "int8_zstd"),
    "tier3_jpeg_relay": ("pi>jetson>laptop", "-1,-1", "jpeg,jpeg"),
    "tier3_jpeg_j9": ("pi>jetson>laptop", "-1,9", "jpeg,int8_zstd"),
    "tier3_k4_j9": ("pi>jetson>laptop", "4,9", "int8_zstd,int8_zstd"),
}


def devices(chain: str) -> int:
    return chain.count(">") + 1


def check(hw_dir: Path = HW) -> dict:
    model = {}
    for r in csv.DictReader(open(hw_dir / "placements.csv", newline="", encoding="utf-8")):
        model.setdefault((r["chain"], r["cuts"], r["encs"]), []).append(float(r["fps"]))
    live = {r["placement"]: r for r in csv.DictReader(open(hw_dir / "live_summary.csv", newline="", encoding="utf-8"))}
    pairs, unmatched = [], []
    for key, r in live.items():
        m = LIVE_TO_MODEL.get(key)
        rows = model.get(m) if m else None
        if not rows or len(rows) != 1:          # no row, or no single unambiguous row: leave it out and say so
            unmatched.append({"placement": key, "description": r["description"],
                              "reason": "no mapping" if m is None else f"{0 if not rows else len(rows)} model rows"})
            continue
        lv = float(r["fps_median"])
        pairs.append({"placement": key, "description": r["description"], "chain": m[0], "cuts": m[1], "encs": m[2],
                      "devices": devices(m[0]), "runs": int(r["runs"]), "live_fps_median": lv,
                      "model_fps": rows[0], "ratio_model_over_live": round(rows[0] / lv, 4)})
    short = [p for p in pairs if p["devices"] <= 2]
    three = [p for p in pairs if p["devices"] == 3]
    # Image offload vs split, both from the Pi camera on one or two devices
    img = [p for p in short if p["chain"].startswith("pi>") and p["encs"] == "jpeg"]
    spl = [p for p in short if p["chain"].startswith("pi>") and p["encs"] == "int8_zstd"]

    def above(key):
        return min(p[key] for p in img) > max(p[key] for p in spl)

    def order(key):
        return [p["placement"] for p in sorted(short, key=lambda p: -p[key])]

    rng = lambda ps: {"n": len(ps), "min_ratio": min(p["ratio_model_over_live"] for p in ps),  # noqa: E731
                      "max_ratio": max(p["ratio_model_over_live"] for p in ps)}
    return {
        "description": "placement model (placements.csv) against live runs (live_summary.csv): model fps / live median fps",
        "generated_by": "evaluation/placement_model_check.py",
        "pairs": pairs,
        "unmatched": unmatched,
        "one_or_two_devices": rng(short),
        "three_devices": rng(three),
        "pi_image_vs_split": {"image_placements": [p["placement"] for p in img],
                              "split_placements": [p["placement"] for p in spl],
                              "model_ranks_every_image_above_every_split": above("model_fps"),
                              "live_ranks_every_image_above_every_split": above("live_fps_median")},
        "one_or_two_devices_order": {"model": order("model_fps"), "live": order("live_fps_median"),
                                     "same_order": order("model_fps") == order("live_fps_median")},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    res = check()
    a.out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    print(f"{'live placement':20s} {'model row (chain | cuts | encs)':42s} {'live':>6s} {'model':>7s} {'ratio':>6s}")
    for p in res["pairs"]:
        row = f"{p['chain']} | {p['cuts'] or '-'} | {p['encs'] or '-'}"
        print(f"{p['placement']:20s} {row:42s} {p['live_fps_median']:6.2f} {p['model_fps']:7.2f} "
              f"{p['ratio_model_over_live']:6.2f}")
    for u in res["unmatched"]:
        print(f"UNMATCHED {u['placement']}: {u['reason']}")
    print("one/two devices:", res["one_or_two_devices"], " three devices:", res["three_devices"])
    print("image above split:", res["pi_image_vs_split"], " same order:", res["one_or_two_devices_order"]["same_order"])
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
