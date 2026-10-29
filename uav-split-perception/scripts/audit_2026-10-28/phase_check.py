import json, re
HW = "/home/sengar/BTP/uav-split-perception/experiments/results/hardware/"
L = open("/home/sengar/BTP/AEGIS-UAV Results Brief.md").read().split("\n")
ST = {"v4.1: Pi energy + freshness": "v41", "v4.1 + Jetson energy": "v41e", "heat + freshness": "heat",
      "heat + Jetson energy + freshness": "heate", "no prices (stream objective)": "noprice", "fixed Pi → laptop, YOLOv8m q90": "fixlap",
      "freshness threshold (literature)": "aoithr", "hierarchical chain": "hier", "v4.1 (direct three-tier)": "v41",
      "Pi → Jetson (YOLOv8s)": "jet_s", "Pi → laptop (YOLOv8m)": "lap_m", "relay Pi → Jetson → laptop (YOLOv8m)": "relay_m", "v4.1": "v41", "v4.1 (all paths)": "v41"}
n = bad = 0
for a, b, f in ((1584, 1592, "vid_campaign_mesh_summary.json"), (1662, 1675, "vid_campaign_mesh2_summary.json"), (1462, 1497, "vid_campaign_b_summary.json"), (1727, 1760, "vid_campaign_mesh3_summary.json")):
    ph = json.load(open(HW + f))["mission_phases_fc"]
    if isinstance(ph, dict) and "mesh_mission" in ph: ph = ph["mesh_mission"]
    if isinstance(ph, dict) and "mission" in ph and not any(k in ph for k in ST.values()): ph = ph["mission"]
    hdr = None
    for i in range(a, b + 1):
        l = L[i - 1]
        if not l.startswith("|"): hdr = None; continue
        c = [x.strip().replace("**", "") for x in l.strip("|").split("|")]
        if hdr is None: hdr = c; continue
        if c[0].startswith("---") or c[0] not in ST or ST[c[0]] not in ph: continue
        keys = list(ph[ST[c[0]]])
        if len(keys) != len(c) - 1: continue
        for k, v in zip(keys, c[1:]):
            if not re.fullmatch(r"\d\.\d{3}", v): continue
            n += 1
            if abs(round(ph[ST[c[0]]][k], 3) - float(v)) > 0.0005 + 1e-9: bad += 1; print(f"{f} line {i} {c[0]} {k}: brief {v} data {ph[ST[c[0]]][k]:.4f}")
print("phase cells checked", n, "mismatches", bad)
