#!/usr/bin/env python3
"""Phase G exhaustive-audit verification: recomputes every remaining G4/G5/G6/G7 number
from the rescored result files. Read-only; prints claims vs recomputed values."""
import json, os

B = "experiments/results/hardware/energy/"
R = "experiments/results/hardware/"


def load(p):
    return json.load(open(os.path.join(B, p)) if os.path.exists(os.path.join(B, p))
                     else open(os.path.join(R, os.path.basename(p))))


def mean(es, k):
    return sum(e[k] for e in es) / len(es)


def agg_by(summary, camp, keyf):
    pols = {}
    for e in summary[camp]:
        k = keyf(e)
        pols.setdefault(k, []).append(e)
    return pols


s = load("energy_all_summary.json")

print("=" * 72)
print("G5 — v1/v2 campaign means per policy (energy_all_summary.json)")
for camp in ["v1", "v2"]:
    pols = agg_by(s, camp, lambda e: e["policy"])
    print(f"== {camp}: {len(pols)} policies")
    for p, es in sorted(pols.items()):
        def m(k):
            return round(mean(es, k), 3)
        row = f"  {p:34s} n={len(es):2d} on={m('on_time_fps'):7} pw={m('camera_w'):7} ew={m('edge_w'):7} T={m('steady_temp_c'):7}"
        if "acc_on_time" in es[0]:
            row += f" accOn={m('acc_on_time'):7}"
        print(row)

print("=" * 72)
print("G4 — v1 placements: drone energy per frame above idle (W_above/fps)")
v1_runs = load("energy_v1.json")
# per-run entries: campaign/scenario/policy/rep + fps + breakdown_w
pol_runs = {}
for e in v1_runs:
    if not isinstance(e, dict) or "policy" not in e:
        continue
    pol_runs.setdefault(e["policy"], []).append(e)
for p, es in sorted(pol_runs.items()):
    fps = mean(es, "on_time_fps") if "on_time_fps" in es[0] else None
    # above-idle drone watts = camera_w - idle (1.894)  [+ edge handled separately]
    pw = mean(es, "camera_w") - 1.894
    jpf = pw / fps * 1000 if fps else float("nan")
    print(f"  {p:34s} fps={fps:.2f} W_above_idle={pw:.3f} -> {jpf:7.1f} mJ/frame")

print("=" * 72)
print("G6 — 80-run campaign (wifi_fc2) pooled per policy")
fc2 = load("energy_wifi_fc2.json")
runs = [e for e in fc2 if isinstance(e, dict) and "policy" in e]
pol_runs = {}
for e in runs:
    pol_runs.setdefault(e["policy"], []).append(e)
for p, es in sorted(pol_runs.items()):
    def m(k):
        return round(mean(es, k), 3)
    extra = ""
    for k in ("sAP", "fresh_share", "camera_w", "edge_w", "steady_temp_c",
              "sap_per_w", "endur_mini_249g", "endur_quad_1.2kg"):
        if k in es[0]:
            extra += f" {k}={m(k)}"
    print(f"  {p:34s} n={len(es):2d}{extra}")

print("-- 108-run campaign (wifi) pooled ranges per policy")
wf = load("energy_wifi.json")
runs = [e for e in wf if isinstance(e, dict) and "policy" in e]
pol_runs = {}
for e in runs:
    pol_runs.setdefault(e["policy"], []).append(e)
for p, es in sorted(pol_runs.items()):
    def rng(k):
        vals = [e[k] for e in es if k in e]
        return f"{min(vals):.2f}-{max(vals):.2f}" if vals else "-"
    extra = " ".join(f"{k}={rng(k)}" for k in ("camera_w", "edge_w"))
    print(f"  {p:34s} n={len(es):2d}{extra}")

print("=" * 72)
print("G7 — 100-run campaign measured Pi power per policy (energy_campaign_measured.json)")
cm = load("energy_campaign_measured.json")
pol_runs = {}
for e in cm:
    pol_runs.setdefault(e["pol"], []).append(e)
for p, es in sorted(pol_runs.items()):
    ws = [e["W"] for e in es]
    Ts = [e["Tmean"] for e in es]
    print(f"  {p:14s} n={len(es):2d} W={min(ws):.2f}-{max(ws):.2f} Tmean={min(Ts):.1f}-{max(Ts):.1f}")

print("-- swarm_calibrated_mp_summary.json (--measured-power)")
mp = load("swarm_calibrated_mp_summary.json") if os.path.exists(os.path.join(R, "swarm_calibrated_mp_summary.json")) \
    else json.load(open("swarm_calibrated_mp_summary.json"))
print(json.dumps(mp, indent=1)[:3000])

print("=" * 72)
print("G6/G8 — smoke_v4 measured vs old estimate")
sv = json.load(open(os.path.join(R, "smoke_v4/a2_smoke_v4.json")))
tot = sv["total"]
print(f"  old in-run estimate (total pi_power_w) = {tot['pi_power_w']:.4f} W  (claim: 1.22)")
print(f"  measured = {sv['energy_j']:.2f} J / {sv['duration_s']:.2f} s = {sv['energy_j']/sv['duration_s']:.3f} W  (claim: 3.56)")
print(f"  budget = {sv.get('power_budget_w')} W  (claim: 3.5)")
