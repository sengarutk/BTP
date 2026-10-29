import json, re
HW = "/home/sengar/BTP/uav-split-perception/experiments/results/hardware/"
L = open("/home/sengar/BTP/AEGIS-UAV Results Brief.md").read().split("\n")
ST = {"v4.1: Pi energy + freshness": "v41", "v4.1 + Jetson energy": "v41e", "heat + freshness": "heat",
      "heat + Jetson energy + freshness": "heate", "no prices (stream objective)": "noprice",
      "fixed Pi → laptop, YOLOv8m q90": "fixlap", "freshness threshold (literature)": "aoithr", "hierarchical chain": "hier"}
def P(s): return [float(x) for x in re.findall(r"[+-]?\d+\.?\d*", s.replace("−", "-"))]
def close(a, b, s): return abs(a - b) <= 0.5 * 10 ** -s + 1e-9
def dec(t): return len(t.split(".")[1]) if "." in t else 0
bad = 0; n = 0
# 18.9 big paired table
J = json.load(open(HW + "vid_campaign_mesh2_summary.json"))["paired"]
for i in range(1652, 1662):
    c = [x.strip() for x in L[i - 1].strip("|").split("|")]
    if " − " not in c[0]: continue
    a, b = c[0].split(" − "); key = f"{ST[a]}-{ST[b]}"
    for sc, cell in zip(("static_good", "mesh_mission", "multihop", "ALL"), c[1:5]):
        if cell == "–": continue
        k = f"{key}|{sc}"
        if k not in J: print("missing", k); bad += 1; continue
        r = J[k]["sAP_fc"]; m = re.match(r"([+-]?\d\.\d+) \((\d)/(\d), p (\d\.\d+)\)", cell.replace("−", "-")); n += 1
        if not (close(float(m.group(1)), r["mean_diff"], dec(m.group(1))) and int(m.group(2)) == r["first_ahead"] and int(m.group(3)) == r["pairs"] and close(float(m.group(4)), r["p_perm"], 3)):
            bad += 1; print(f"line {i} {key} {sc}: brief {cell} data {r['mean_diff']:+.4f} {r['first_ahead']}/{r['pairs']} p {r['p_perm']:.3f}")
    for col, fld in ((5, "pi_w"), (6, "pi_temp_c")):
        v = P(c[col])[0]; r = J[f"{key}|ALL"][fld]["mean_diff"]; n += 1
        if not close(v, r, 3): bad += 1; print(f"line {i} {key} {fld}: brief {v} data {r:.4f}")
# 24-min table
J2 = json.load(open(HW + "vid_campaign_mesh2_long_summary.json"))["paired"]
for i in range(1684, 1690):
    c = [x.strip() for x in L[i - 1].strip("|").split("|")]
    if " − " not in c[0]: continue
    a, b = c[0].split(" − "); k = f"{ST[a]}-{ST[b]}|mesh_mission"
    if k not in J2: print("missing", k); bad += 1; continue
    r = J2[k]; s = r["sAP_fc"]; mu, ci = P(c[2]); fa, pr = c[3].split("/"); n += 1
    e = []
    if not (close(mu, s["mean_diff"], 4) and close(ci, s["ci95"], 4)): e.append(f"sAP {s['mean_diff']:+.4f}±{s['ci95']:.4f}")
    if int(fa) != s["first_ahead"] or int(pr) != s["pairs"]: e.append("ahead")
    if not close(float(c[4]), s["p_perm"], 3): e.append(f"p {s['p_perm']:.3f}")
    if not close(P(c[5])[0], r["pi_w"]["mean_diff"], 2): e.append(f"W {r['pi_w']['mean_diff']:+.3f}")
    if not close(P(c[6])[0], r["pi_temp_c"]["mean_diff"], 1): e.append(f"T {r['pi_temp_c']['mean_diff']:+.2f}")
    if e: bad += 1; print(f"line {i} {k}: {e}")
# 18.10
J3 = json.load(open(HW + "vid_campaign_mesh3_summary.json"))["paired"]
for i in range(1744, 1750):
    c = [x.strip() for x in L[i - 1].strip("|").split("|")]
    sc = {"normal": "static_good", "mesh mission": "mesh_mission", "multihop": "multihop", "all three": "ALL"}.get(c[0])
    if not sc: continue
    r = J3[f"v41e12-v41|{sc}"]
    for cell, fld in zip(c[1:5], ("sAP_fc", "deadline_met_fps", "jetson_w", "pi_w")):
        m = re.match(r"([+-]?\d+\.\d+) \((\d)/(\d), p (\d\.\d+)\)", cell.replace("−", "-")); x = r[fld]; n += 1
        if not (close(float(m.group(1)), x["mean_diff"], 4) and int(m.group(2)) == x["first_ahead"] and int(m.group(3)) == x["pairs"] and close(float(m.group(4)), x["p_perm"], 3)):
            bad += 1; print(f"line {i} {sc} {fld}: brief {cell} data {x['mean_diff']:+.4f} {x['first_ahead']}/{x['pairs']} p {x['p_perm']:.3f}")
# 18.8
J4 = json.load(open(HW + "vid_campaign_mesh_summary.json"))["paired_v41_minus_hier"]
FL = {"sAP + forecaster": "sAP_fc", "sAP": "sAP", "P(AoI ≤ 300 ms)": "p_aoi300", "Pi power (W)": "pi_w"}
for i in range(1570, 1590):
    c = [x.strip() for x in L[i - 1].strip("|").split("|")]
    sc = {"normal": "static_good", "mesh mission": "mesh_mission", "both": "ALL"}.get(c[0])
    if not sc or len(c) < 6 or c[1] not in FL: continue
    x = J4[sc][FL[c[1]]]; mu, ci = P(c[3]); a, pr = c[4].split("/"); n += 1
    if not (close(mu, x["mean_diff"], 4) and close(ci, x["ci95"], 4) and int(a) == x["v41_ahead"] and int(pr) == x["pairs"] and close(float(c[5]), x["p_perm"], 3)):
        bad += 1; print(f"line {i} {sc} {c[1]}: data {x}")
print("paired cells checked", n, "mismatches", bad)
