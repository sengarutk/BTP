#!/usr/bin/env python3
"""Energy, thermal and endurance rescoring of every hardware campaign with the measured model (energy_model.py).

Per run: camera-drone power (W) and its breakdown, edge-drone power when the Jetson served frames, predicted
steady Pi temperature under that average power (throttles above 85 C), and endurance of the camera drone for
each drone class. Joined with the run's own task metrics:
  v1 (adaptive/), v2 (adaptive2/): on-time and accuracy-weighted on-time results/s (proxy metrics)
  task-level campaigns: streaming AP without forecasting, with forecaster v2 (energy then includes the
  forecaster's power, as the drone would run it), availability
Derived per run: accuracy per watt (sAP / camera W), mission perception (sAP x endurance, "sAP-minutes"),
energy per on-time result (J), and three explicitly-labelled SYSTEM views of the whole drone swarm
(camera drone + edge drone, energy_model.system_views — never mixed):
  system_*_extra     edge drone flies anyway: camera + Jetson extra work only (infer + rx);
  system_*_board     Jetson carried for perception: + its whole board power incl. 4.08 W idle;
  system_*_dedicated Jetson flies only for perception: + board + 153.6 W edge flight power.
Plus sAP per system watt for each view, per-drone flight time (camera and edge drone), and swarm
lifetime = the first drone to land, with swarm mission perception (sAP x swarm lifetime).
Per (campaign, scenario, policy): mean and 95 % t-interval over repetitions.
Output: experiments/results/hardware/energy/energy_<campaign>.json and energy_all_summary.json
"""
import glob
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from energy_model import (Board, E_DIR, endurance_min, drone_classes, run_energy, run_energy_v1,  # noqa: E402
                          system_views)
from summarize_vid import tci  # noqa: E402

HW = Path(__file__).resolve().parent.parent.parent / "experiments" / "results" / "hardware"
SCEN = ["mission_mirror", "static_good", "mission", "random"]


def parse(stem):
    """(scenario, policy, rep, camera) from a run file stem."""
    if "__" in stem:
        p = stem[3:].split("__")
        return p[0], p[1], int(p[2][1:]), (p[3] if len(p) > 3 else "pi")
    body = stem.split("_", 1)[1]
    m = re.match(r"(.*)_r(\d+)$", body)
    if not m:
        return None
    body, rep = m.group(1), int(m.group(2))
    for sc in SCEN:
        if body.startswith(sc + "_"):
            return sc, body[len(sc) + 1:], rep, "pi"
    return None


def per_run(pi, jet, campaign, d, cache_keys):
    rows = []
    cache = json.load(open(d / "_eval_cache.json")) if (d / "_eval_cache.json").exists() else {}
    for f in sorted(glob.glob(str(d / "a*.json"))):
        stem = Path(f).stem
        if stem.endswith(("_dets", "_livefc")) or stem.startswith(("a2w", "adw")):
            continue
        ps = parse(stem)
        if not ps:
            continue
        sc, pol, rep, cam = ps
        r = json.load(open(f))
        if "frames" not in r:
            continue
        live_fc = "live_forecast" in r
        row = {"campaign": campaign, "scenario": sc, "policy": pol, "rep": rep, "camera": cam}
        if campaign == "v1":
            e = run_energy_v1(r, pi, jet)
            row.update(on_time_fps=r["total"]["on_time_fps"], acc_on_time=r["total"]["acc_weighted_on_time"])
            e_fc = None
        else:
            e = run_energy(r, pi, jet, camera="jetson" if cam == "jetson" else "pi", forecast=live_fc)
            e_fc = e if live_fc else run_energy(r, pi, jet, camera="jetson" if cam == "jetson" else "pi",
                                                forecast=True)
            t = r["total"]
            row.update(on_time_fps=t["on_time_fps"], acc_on_time=t["acc_on_time_fps"],
                       availability=t["availability"])
            key = stem[3:]
            c = cache.get(key, {})
            for name, k in cache_keys.items():
                if k in c:
                    row[name] = c[k]
        board = jet if cam == "jetson" else pi
        row.update(camera_w=e["camera_w"], edge_w=e["edge_w"] if e["edge_used"] else 0.0,
                   edge_used=e["edge_used"], breakdown_w={k: v / e["duration_s"] for k, v in
                                                          e["camera_breakdown_j"].items()},
                   steady_temp_c=board.steady_temp(e["camera_w"]) if cam == "pi" else None)
        if e_fc is not None:
            row["camera_w_fc"] = e_fc["camera_w"]
            row["steady_temp_c_fc"] = board.steady_temp(e_fc["camera_w"]) if cam == "pi" else None
        for cls in drone_classes():
            row[f"endur_{cls}"] = endurance_min(cls, e["camera_w"])
            if e_fc is not None:
                row[f"endur_fc_{cls}"] = endurance_min(cls, e_fc["camera_w"])
        if row.get("on_time_fps"):
            row["j_per_on_time"] = e["camera_w"] / row["on_time_fps"]
        if row.get("sAP") is not None:
            row["sAP_per_w"] = row["sAP"] / e["camera_w"]
        if row.get("sAP_fc") is not None and e_fc is not None:
            row["sAP_fc_per_w"] = row["sAP_fc"] / e_fc["camera_w"]
            for cls in drone_classes():
                row[f"mission_fc_{cls}"] = row["sAP_fc"] * row[f"endur_fc_{cls}"]
        # system views (whole swarm) and sAP per system watt, per view
        sv, sv_fc = system_views(e, jet), (system_views(e_fc, jet) if e_fc is not None else None)
        for name in ("extra", "board", "dedicated"):
            row[f"system_w_{name}"] = sv[f"system_w_{name}"]
            row[f"system_j_{name}"] = sv[f"system_j_{name}"]
            if row.get("sAP") is not None:
                row[f"sAP_per_w_{name}"] = row["sAP"] / sv[f"system_w_{name}"] if sv[f"system_w_{name}"] else None
            if sv_fc is not None:
                row[f"system_w_fc_{name}"] = sv_fc[f"system_w_{name}"]
                if row.get("sAP_fc") is not None:
                    row[f"sAP_fc_per_w_{name}"] = (row["sAP_fc"] / sv_fc[f"system_w_{name}"]
                                                   if sv_fc[f"system_w_{name}"] else None)
        if cam == "pi":
            # swarm = camera drone + edge drone: per-drone flight time and swarm lifetime (first to land)
            # (a run that never used the edge drone has no edge drone: its swarm is the camera drone alone)
            inf = float("inf")
            row["edge_endur_min"] = endurance_min("edge_1.5kg", e["edge_w"]) if e["edge_used"] else None
            row["edge_endur_fc_min"] = (endurance_min("edge_1.5kg", e_fc["edge_w"])
                                        if e_fc is not None and e_fc["edge_used"] else None)
            for cls in drone_classes():
                row[f"swarm_lifetime_{cls}"] = min(row[f"endur_{cls}"], row["edge_endur_min"] or inf)
                if e_fc is not None:
                    row[f"swarm_lifetime_fc_{cls}"] = min(row[f"endur_fc_{cls}"], row["edge_endur_fc_min"] or inf)
                if row.get("sAP") is not None:
                    row[f"mission_perception_swarm_{cls}"] = row["sAP"] * row[f"swarm_lifetime_{cls}"]
                if row.get("sAP_fc") is not None and e_fc is not None:
                    row[f"mission_perception_swarm_fc_{cls}"] = row["sAP_fc"] * row[f"swarm_lifetime_fc_{cls}"]
        rows.append(row)
    return rows


def summarize(rows):
    by = defaultdict(list)
    for r in rows:
        by[(r["scenario"], r["policy"], r["camera"])].append(r)
    out = []
    for (sc, pol, cam), rs in sorted(by.items()):
        s = {"scenario": sc, "policy": pol, "camera": cam, "reps": len(rs)}
        keys = [k for k in rs[0] if isinstance(rs[0][k], (int, float)) and not isinstance(rs[0][k], bool)
                and k not in ("rep",)]
        for k in keys:
            vals = [r[k] for r in rs if r.get(k) is not None]
            if vals:
                mu, hw = tci(vals)
                s[k], s[k + "_ci"] = mu, hw
        s["edge_used_share"] = float(np.mean([r["edge_used"] for r in rs]))
        bw = defaultdict(list)
        for r in rs:
            for k, v in r["breakdown_w"].items():
                bw[k].append(v)
        s["breakdown_w"] = {k: float(np.mean(v)) for k, v in bw.items()}
        out.append(s)
    return out


def main():
    pi, jet = Board("pi"), Board("jetson")
    camps = {"v1": (HW / "adaptive", {}),
             "v2": (HW / "adaptive2", {}),
             "wifi": (HW / "vid_campaign_wifi", {"sAP": "sAP_quality", "sAP_fc": "sAP_quality_fcv2"}),
             "wifi_fc": (HW / "vid_campaign_wifi_fc", {"sAP": "sAP_quality", "sAP_fc": "sAP_quality_fcv2"}),
             "wifi_fc2": (HW / "vid_campaign_wifi_fc2", {"sAP": "sAP_quality", "sAP_fc": "sAP_quality_fcv2live"}),
             "energy": (HW / "vid_campaign_energy", {"sAP": "sAP_quality", "sAP_fc": "sAP_quality_fcv2live"}),
             "v42": (HW / "vid_campaign_v42", {"sAP": "sAP_quality", "sAP_fc": "sAP_quality_fcv2live"}),
             "swarm_duo": (HW / "swarm_duo", {"sAP": "sAP", "sAP_fc": "sAP_fc"})}
    allsum = {}
    for name, (d, keys) in camps.items():
        rows = per_run(pi, jet, name, d, keys)
        summ = summarize(rows)
        json.dump({"rows": rows, "summary": summ}, open(E_DIR / f"energy_{name}.json", "w"), indent=1,
                  default=float)
        allsum[name] = summ
        print(f"== {name}: {len(rows)} runs")
        for s in summ:
            print(f"  {s['scenario']:15s} {s['policy']:24s} {s['camera']:6s} n={s['reps']} "
                  f"camW={s.get('camera_w', 0):.2f} fcW={s.get('camera_w_fc', float('nan')):.2f} "
                  f"edgeW={s.get('edge_w', 0):.2f} T={s.get('steady_temp_c') or float('nan'):.0f}C "
                  f"sysX={s.get('system_w_fc_extra', s.get('system_w_extra', 0)):.2f}W "
                  f"sysB={s.get('system_w_fc_board', s.get('system_w_board', 0)):.2f}W "
                  f"sysD={s.get('system_w_fc_dedicated', s.get('system_w_dedicated', 0)):.2f}W "
                  f"sAPfc={s.get('sAP_fc', float('nan')):.4f} sAPfc/W={s.get('sAP_fc_per_w', float('nan')):.4f} "
                  f"sAPfc/sysX={s.get('sAP_fc_per_w_extra', float('nan')):.4f} "
                  f"end1.2kg={s.get('endur_fc_quad_1.2kg', s.get('endur_quad_1.2kg', 0)):.2f}min "
                  f"endMini={s.get('endur_fc_mini_249g', s.get('endur_mini_249g', 0)):.2f}min "
                  f"swarmMini={s.get('swarm_lifetime_fc_mini_249g', s.get('swarm_lifetime_mini_249g', float('nan'))):.2f}min")
    json.dump(allsum, open(E_DIR / "energy_all_summary.json", "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
