#!/usr/bin/env python3
"""Every placement of YOLOv8s over Raspberry Pi 5 (camera), Jetson Orin Nano and laptop GPU.

Inputs (experiments/results/hardware/raw/): one hwbench JSON per device engine, one netbench JSON
per link, and accuracy from experiments/cache/val_stats (single boundary) and
experiments/results/hardware/cascade_accuracy.csv (two boundaries).

A placement is a chain of devices starting at the camera, cuts -1 <= k1 <= k2 <= 22 between them,
and an encoding for each hop (jpeg only for the camera frame; int8_zstd or fp16 for tensors).
Chains: P (Pi only), P>J, P>C, P>J>C, and the single heavy UAV alternatives J (camera on the
Jetson) and J>C. A hop with an empty segment on the middle device forwards the bytes unchanged.

Per frame, from measured medians:
  latency  = pre + sum over devices (decode + segment + encode) + sum over links transfer(bytes)
             + NMS on the last device + return of the detections to the camera (2 KB per link)
  stages   = camera device (pre + segment + encode), each link, each later device; with one
             frame buffered per link (newest wins), throughput = min(camera fps, 1 / slowest stage)
  on_time  = throughput if latency <= deadline else 0
  energy   = per UAV-carried device: (active - idle power) x busy time per frame
Transfer time of b bytes on a link: linear fit t = t0 + b / rate to the measured frame transfers.
Output: experiments/results/hardware/placements.csv, placements_summary.json
"""

import argparse
import csv
import json
import pickle
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
RAW = ROOT / "experiments" / "results" / "hardware" / "raw"
OUT = ROOT / "experiments" / "results" / "hardware"
VAL = ROOT / "experiments" / "cache" / "val_stats" / "coco_val2017"
L = 23
DET_BYTES = 2048
_rp = RAW / "pi_radio_power.json"
PI_RADIO_W = (lambda r: r["transmitting"]["wifi_rail_w"] - r["idle"]["wifi_rail_w"])(json.load(open(_rp))) \
    if _rp.exists() else None


class Device:
    def __init__(self, path):
        self.r = json.load(open(path))
        # GPUs: directly timed segments (per-layer sums include launch overhead). CPUs: per-layer
        # sums, which match timed segments within 1 % at the same thermal state (the directly
        # timed pass runs later and hotter on a throttling Pi).
        gpu = str(self.r.get("device", "cpu")).startswith("cuda")
        self.seg = {tuple(map(int, k.split(","))): v for k, v in self.r.get("segment_ms", {}).items()} if gpu else {}

    def seg_ms(self, a, b):
        if b <= a:
            return 0.0
        if (a, b) in self.seg:
            return self.seg[(a, b)]
        return sum(self.r["layer_ms"][a + 1: b + 1])

    def enc(self, k, mode):
        if k == -1:
            return self.r["jpeg"]["enc_ms"] if mode == "jpeg" else 0.0
        return self.r["codec"][str(k)][mode]["enc_ms"]

    def dec(self, k, mode):
        if k == -1:
            return self.r["jpeg"]["dec_ms"] + self.r["pre_ms"] if mode == "jpeg" else self.r["pre_ms"]
        return self.r["codec"][str(k)][mode]["dec_ms"]

    def nbytes(self, k, mode):
        if k == -1:
            return self.r["jpeg"]["bytes"] if mode == "jpeg" else 640 * 640 * 3
        return self.r["codec"][str(k)][mode]["bytes"]

    def power_dyn(self):
        p = self.r.get("power")
        return max(0.0, p["active_w"] - p["idle_w"]) if p else float("nan")


class Link:
    def __init__(self, path):
        self.r = json.load(open(path))
        xs = np.array([float(s) for s in self.r["frame"]])
        ys = np.array([v["median_ms"] for v in self.r["frame"].values()])
        self.slope, self.t0 = np.polyfit(xs, ys, 1)          # ms per byte, ms
        self.rtt = self.r["rtt_ms_median"]

    def ms(self, nbytes):
        return max(self.t0 + self.slope * nbytes, nbytes * 8 / (self.r["bulk_mbps"] * 1e3))

    def mbps(self):
        return 8 / (self.slope * 1e3)


def accuracy_table():
    """mAP@[.5:.95] by boundary list, e.g. ((4, 'int8'),) or ((-1, 'jpeg'), (9, 'int8'))."""
    acc = {}
    if VAL.exists():
        base = pickle.load(open(VAL / "full_fp32.pkl", "rb"))["map50_95"]
        acc[()] = base
        for f in VAL.glob("k*_*.pkl"):
            k, mode = f.stem[1:].split("_", 1)
            if mode in ("int8", "fp16"):
                acc[((int(k), mode),)] = pickle.load(open(f, "rb"))["map50_95"]
        if (VAL / "codec_jpeg_90.pkl").exists():
            acc[((-1, "jpeg"),)] = pickle.load(open(VAL / "codec_jpeg_90.pkl", "rb"))["map50_95"]
    casc = OUT / "cascade_accuracy.csv"
    if casc.exists():
        for r in csv.DictReader(open(casc)):
            first = (-1, "jpeg") if r["first"] == "jpeg90" else (int(r["k1"]), "int8")
            acc[(first, (int(r["k2"]), r["second"]))] = float(r["map50_95"])
    return acc


def lookup_accuracy(acc, bounds):
    """Exact entry if measured; otherwise the nearest measured cut with the same encodings (flagged)."""
    key = tuple((k, "int8" if m == "int8_zstd" else m) for k, m in bounds if k < L - 1)
    if key in acc:
        return acc[key], "measured"
    cands = [(sum(abs(a[0] - b[0]) for a, b in zip(kk, key)), v) for kk, v in acc.items()
             if len(kk) == len(key) and all(a[1] == b[1] for a, b in zip(kk, key))]
    if not cands:
        return float("nan"), "none"
    return min(cands)[1], "nearest"


def evaluate(devs, links, chain, cuts, encs, fps_cam, deadline, acc):
    """chain: device names; cuts: boundaries between consecutive devices; encs: encoding per hop."""
    bounds = [-1] + list(cuts) + [L - 1]
    lat, stages, energy = 0.0, [], {}
    for i, name in enumerate(chain):
        d = devs[name]
        a, b = bounds[i], bounds[i + 1]
        relay = i > 0 and a == b and i < len(chain) - 1       # forwards bytes unchanged
        t = 0.0
        if i == 0:
            t += d.r["pre_ms"]
        elif not relay:
            t += d.dec(a, encs[i - 1])
        t += d.seg_ms(a, b)
        if i < len(chain) - 1 and not relay:
            t += d.enc(b, encs[i])
        if i == len(chain) - 1:
            t += d.r["post_ms"]
        lat += t
        stages.append(t)
        if name in ("pi", "jetson"):
            energy[name] = d.power_dyn() * t / 1e3
        if i < len(chain) - 1:
            enc_bytes = devs[chain[0] if i == 0 else name].nbytes(b, encs[i]) if not relay else \
                devs[chain[i - 1]].nbytes(b, encs[i - 1])
            lk = links[(name, chain[i + 1])]
            tx = lk.ms(enc_bytes)
            lat += tx + lk.ms(DET_BYTES)                     # data out, detections back
            stages.append(tx)
            if name == "pi" and PI_RADIO_W is not None:      # Pi Wi-Fi rail while transmitting
                energy["pi_radio"] = PI_RADIO_W * tx / 1e3
    # a 30 fps camera: the camera device can only start on a frame boundary, so its period is
    # its stage time rounded up to whole frame intervals; later stages are newest-wins buffers
    frame_ms = 1000.0 / fps_cam
    cam_period = np.ceil(stages[0] / frame_ms - 1e-9) * frame_ms
    fps = min(1000.0 / cam_period, 1000.0 / max(stages[1:]) if len(stages) > 1 else fps_cam)
    hop_bounds = [(bounds[i + 1], encs[i]) for i in range(len(chain) - 1)
                  if not (i > 0 and bounds[i] == bounds[i + 1] and i < len(chain) - 1)]
    m, src = lookup_accuracy(acc, hop_bounds)
    return {"chain": ">".join(chain), "cuts": ",".join(map(str, cuts)), "encs": ",".join(encs),
            "latency_ms": round(lat, 2), "bottleneck_ms": round(max(stages), 2), "fps": round(fps, 2),
            "fps_on_time": round(fps if lat <= deadline else 0.0, 2),
            "energy_uav_j": round(sum(energy.values()), 4), "map50_95": round(m, 4), "acc_source": src,
            "stages_ms": ";".join(f"{s:.1f}" for s in stages)}


def enumerate_placements(devs, links, fps_cam, deadline, acc):
    rows = []
    tensor_encs = ["int8_zstd", "fp16"]
    for cam in ("pi", "jetson"):
        if cam not in devs:
            continue
        rows.append(evaluate(devs, links, [cam], [], [], fps_cam, deadline, acc))
        for nxt in ("jetson", "laptop"):
            if nxt == cam or nxt not in devs or (cam, nxt) not in links:
                continue
            for k in range(-1, L - 1):
                for e in (["jpeg"] if k == -1 else tensor_encs):
                    rows.append(evaluate(devs, links, [cam, nxt], [k], [e], fps_cam, deadline, acc))
        if cam == "pi" and "jetson" in devs and "laptop" in devs and ("pi", "jetson") in links \
                and ("jetson", "laptop") in links:
            for k1 in range(-1, L - 1):
                for k2 in range(k1, L - 1):
                    for e1 in (["jpeg"] if k1 == -1 else tensor_encs):
                        for e2 in (["jpeg"] if k2 == -1 else tensor_encs):
                            if k1 == k2 and e2 != e1:
                                continue
                            rows.append(evaluate(devs, links, ["pi", "jetson", "laptop"], [k1, k2], [e1, e2],
                                                 fps_cam, deadline, acc))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pi", default="pi5_cpu_4t_sustained.json")
    ap.add_argument("--jetson", default="jetson_gpu_fp16.json")
    ap.add_argument("--laptop", default="laptop_gpu_fp16.json")
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--deadline", type=float, default=300.0)
    a = ap.parse_args()
    devs = {n: Device(RAW / f) for n, f in (("pi", a.pi), ("jetson", a.jetson), ("laptop", a.laptop))
            if (RAW / f).exists()}
    links = {}
    for src, dst in (("pi", "jetson"), ("pi", "laptop"), ("jetson", "laptop")):
        p = RAW / f"link_{src}_{dst}.json"
        if p.exists():
            links[(src, dst)] = links[(dst, src)] = Link(p)
    acc = accuracy_table()
    rows = enumerate_placements(devs, links, a.fps, a.deadline, acc)
    rows.sort(key=lambda r: (-r["fps_on_time"], r["latency_ms"]))
    with open(OUT / "placements.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    summary = {"devices": {n: {"full_ms": d.r["full_ms"], "power": d.r.get("power")} for n, d in devs.items()},
               "links": {f"{s}>{t}": {"rtt_ms": l.rtt, "mbps_fit": round(l.mbps(), 2), "bulk_mbps": l.r["bulk_mbps"]}
                         for (s, t), l in links.items() if s < t or (s, t) == ("pi", "laptop")},
               "n_placements": len(rows), "deadline_ms": a.deadline}
    best = {}
    for chain in sorted({r["chain"] for r in rows}):
        rs = [r for r in rows if r["chain"] == chain]
        best[chain] = {"by_on_time_fps": rs[0], "by_latency": min(rs, key=lambda r: r["latency_ms"])}
    summary["best_per_chain"] = best
    summary["top10"] = rows[:10]
    json.dump(summary, open(OUT / "placements_summary.json", "w"), indent=1)
    print(json.dumps({c: (b["by_on_time_fps"]["cuts"], b["by_on_time_fps"]["encs"], b["by_on_time_fps"]["fps_on_time"],
                          b["by_on_time_fps"]["latency_ms"]) for c, b in best.items()}, indent=1))


if __name__ == "__main__":
    main()
