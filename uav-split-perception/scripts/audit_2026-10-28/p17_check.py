import json, re
D = "/home/sengar/BTP/uav-split-perception/experiments/results/hardware/onboard_sap/"
L = open("/home/sengar/BTP/AEGIS-UAV Results Brief.md").read().split("\n")
COND = {"hot short": "short_hot", "cool short": "short_cool", "long": "long_cool"}
def chk(a, b, f, models):
    S = json.load(open(D + f))["summary"]; n = bad = 0
    for i in range(a, b + 1):
        c = [x.strip().replace("**", "") for x in L[i - 1].strip("|").split("|")]
        m = re.match(r"(YOLO\S+), (hot short|cool short|long) \((\d)\)", c[0]) if c else None
        if not m: continue
        if m.group(1) not in models: continue
        key = models[m.group(1)]; r = S[COND[m.group(2)]][key]; n += 1
        exp = [("n", int(m.group(3)), r["n"], 0), ("mAP", c[1], r["fresh_AP"], 3), ("sAP", c[2], r["sAP"], 4), ("fc", c[3], r["sAP_fc"], 4),
               ("sAP50", c[4], r["sAP50"], 4), ("lat", c[5].split()[0], r["lat_ms"], 0), ("W", c[6].split()[0], r["pi_w"], 2),
               ("clock", c[8].split()[0], r["clock_mhz"], 0), ("thr", c[9].split()[0], 100 * r["throttled_share"], 0)]
        t = re.findall(r"\d+", c[7]); exp += [("Tstart", t[0], r["temp_start"], 0), ("Tmean", t[1], r["temp_mean"], 0)] + ([("Tmax", t[2], r["temp_max"], 0)] if len(t) > 2 else [])
        errs = [f"{k}: brief {v} data {x:.4f}" for k, v, x, d in exp if abs(float(v) - round(x, d)) > 0.5 * 10 ** -d + 1e-9]
        if errs: bad += 1; print(f"line {i} {c[0]}: {errs}")
    print(f, "rows", n, "mismatches", bad)
chk(1286, 1298, "throttle_analysis_visdrone.json", {"YOLOv8s": "s640vd", "YOLOv8m": "m640vd", "YOLOv8l": "l640vd"})
chk(1364, 1384, "throttle_analysis_yolo11.json", {"YOLO11n": "n640y11", "YOLO11s": "s640y11", "YOLO11m": "m640y11"})
chk(1364, 1384, "throttle_analysis_visdrone.json", {"YOLOv8s": "s640vd", "YOLOv8m": "m640vd", "YOLOv8l": "l640vd"})
