"""Brief tables of Part 18 against the full-precision summary JSONs (header-driven)."""
import json, re, math
HW = "/home/sengar/BTP/uav-split-perception/experiments/results/hardware/"
L = open("/home/sengar/BTP/AEGIS-UAV Results Brief.md").read().split("\n")
SC = {"normal": "static_good", "mesh mission": "mesh_mission", "multihop": "multihop", "all three": "ALL", "both": "ALL",
      "all": "ALL", "out of range": "out_of_range", "mission": "mission", "mesh mission (24-min)": "mesh_mission"}
ST = {"v4.1: Pi energy + freshness": "v41", "v4.1 + Jetson energy": "v41e", "heat + freshness": "heat",
      "heat + Jetson energy + freshness": "heate", "no prices (stream objective)": "noprice",
      "fixed Pi → laptop, YOLOv8m q90": "fixlap", "freshness threshold (literature)": "aoithr", "hierarchical chain": "hier",
      "v4.1 (direct three-tier)": "v41", "v4.1 + Jetson energy (1.2 W)": "v41e12", "v4.1 (Pi energy + freshness)": "v41",
      "Pi → Jetson (YOLOv8s)": "jet_s", "Pi → laptop (YOLOv8m)": "lap_m", "relay Pi → Jetson → laptop (YOLOv8m)": "relay_m",
      "v4.1 (all paths)": "v41", "v4.1": "v41"}
def num(s):
    m = re.findall(r"[+−-]?\d+(?:\.\d+)?", s.replace("−", "-")); return [(float(x), len(x.split(".")[1]) if "." in x else 0) for x in m]
def eq(v, d, x): return x is not None and not (isinstance(x, float) and math.isnan(x)) and abs(round(x, d) - v) <= 0.5 * 10 ** -d + 1e-9
def check(a, b, src):
    J = json.load(open(HW + src))["cells"]; hdr = None; n = bad = 0
    for i in range(a, b + 1):
        l = L[i - 1]
        if not l.startswith("|"): hdr = None; continue
        c = [x.strip().replace("**", "") for x in l.strip().strip("|").split("|")]
        if hdr is None: hdr = c; continue
        if c[0].startswith("---"): continue
        sc, st = SC.get(c[0]), ST.get(c[1])
        if sc is None or st is None or f"{sc}|{st}" not in J: continue
        cell = J[f"{sc}|{st}"]; errs = []; n += 1
        for h, v in zip(hdr[2:], c[2:]):
            hl = h.lower(); vals = num(v)
            def g(k, j=0):
                x = cell.get(k); return x[j] if isinstance(x, list) else x
            if hl == "runs" or hl == "n":
                if vals and vals[0][0] != cell["n"]: errs.append(f"n {cell['n']}")
            elif hl == "sap" and vals:
                if not eq(*vals[0], g("sAP")): errs.append(f"sAP {g('sAP'):.4f}")
            elif hl.startswith("sap + f") and vals:
                if not eq(*vals[0], g("sAP_fc")) or (len(vals) > 1 and not eq(*vals[1], g("sAP_fc", 1))): errs.append(f"sAP_fc {g('sAP_fc'):.4f}±{g('sAP_fc',1):.4f}")
            elif hl.startswith("sap50") and vals:
                if not eq(*vals[0], g("sAP50_fc")): errs.append(f"sAP50 {g('sAP50_fc'):.4f}")
            elif hl == "map" and vals:
                if not eq(*vals[0], g("mAP")): errs.append(f"mAP {g('mAP'):.4f}")
            elif hl.startswith("p(aoi") and vals:
                x = g("p_aoi300") if "p_aoi300" in cell else g("fresh_share")
                if not (eq(vals[0][0], vals[0][1], x) or eq(vals[0][0], vals[0][1], 100 * x)): errs.append(f"pAoI {x:.4f}")
            elif "95th" in hl and vals:
                x = g("aoi_p95_ms") if "aoi_p95_ms" in cell else g("age_p95_ms")
                v0, d0 = vals[0]
                if not (eq(v0, d0, x) or eq(v0, d0, x / 1000)): errs.append(f"p95 {x:.0f}")
            elif "median latency" in hl and vals:
                if not eq(*vals[0], g("lat_median_ms")): errs.append(f"lat {g('lat_median_ms'):.1f}")
            elif "deadline" in hl and vals:
                if not eq(*vals[0], g("deadline_met_fps")): errs.append(f"dm {g('deadline_met_fps'):.2f}")
            elif hl.startswith("pi") and vals:
                pw = g("pi_w"); tc = g("pi_temp_c") if "pi_temp_c" in cell else g("temp_c")
                if not eq(*vals[0], pw): errs.append(f"piW {pw:.3f}")
                if len(vals) > 1 and not eq(*vals[1], tc): errs.append(f"temp {tc:.2f}")
                if len(vals) > 2 and not eq(vals[2][0], vals[2][1], 100 * g("pi_throttled")): errs.append(f"thr {g('pi_throttled'):.3f}")
            elif "jetson" in hl and "w" in hl and vals:
                if not eq(*vals[0], g("jetson_w")): errs.append(f"jetW {g('jetson_w')}")
            elif "processed" in hl or "servers" in hl:
                share = cell.get("processed_at") or cell.get("server_share") or {}
                for name, pct in re.findall(r"(laptop|jetson|onboard|relay) (\d+) %", v):
                    x = share.get(name, 0)
                    if abs(round(100 * x) - int(pct)) > 0.5 + 1e-9: errs.append(f"{name} {100*x:.1f}%")
        if errs: bad += 1; print(f"  line {i} {c[0]} | {c[1]}: {errs}")
    print(f"  {src}: rows {n}, rows with mismatches {bad}")
for a, b, s in ((1445, 1470, "vid_campaign_b_summary.json"), (1552, 1575, "vid_campaign_mesh_summary.json"),
                (1600, 1650, "vid_campaign_mesh2_summary.json"), (1670, 1685, "vid_campaign_mesh2_long_summary.json"),
                (1727, 1742, "vid_campaign_mesh3_summary.json")):
    print(f"lines {a}-{b}"); check(a, b, s)
