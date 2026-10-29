"""Streaming AP of offloaded variants: the camera (30 fps) sends its newest frame every `gap` ms, each result
arrives L ms after capture; scored with stream_ap.evaluate ('newest', with/without forecaster v2) like onboard_sap.py."""
import json, sys
from pathlib import Path
import numpy as np
R = Path("/home/sengar/BTP/uav-split-perception")
sys.path.insert(0, str(R / "validation/hardware"))
from stream_ap import evaluate
VID, HW, SP = R / "datasets/visdrone_vid_640", R / "experiments/results/hardware", Path(sys.argv[1])
labels = json.load(open(VID / "labels.json"))
fp = json.load(open(HW / "forecast_tuning_v2.json"))["best"]["params"]
ks = [(sq, i) for sq, n in json.load(open(VID / "sequences.json")) for i in range(1, n + 1)]
P = 1 / 30
V = {"s640q90": (HW / "vd_variant_dets/s640q90.npz", 640), "s640q90_chk": (SP / "s640q90_chk.npz", 640),
     "s960q90_up": (SP / "s960q90_up.npz", 960), "s960q90_hr": (SP / "s960q90_hr.npz", 960),
     "s960q75_hr": (SP / "s960q75_hr.npz", 960), "s1280q90_hr": (SP / "s1280q90_hr.npz", 1280)}
def run(name, gap, L):
    z = np.load(V[name][0]); dets = {k: z[k] for k in z.files}
    frames, nxt, rid = [], 0.0, {}
    for t in range(len(ks)):
        rec = {"id": t, "phase": "p", "frame": list(ks[t])}
        if t * P >= nxt - 1e-9:
            nxt = t * P + gap / 1e3
            rec.update(server="x", variant=name, res=V[name][1], t_res=round(t * P + L / 1e3, 4))
            rid[str(t)] = dets[f"{ks[t][0]}/{ks[t][1]}"]
        frames.append(rec)
    p = SP / "tmp_run.json"
    json.dump({"policy": name, "scenario": "static", "frames": frames}, open(p, "w"))
    np.savez_compressed(str(p)[:-5] + "_dets.npz", **rid)
    r0, r1 = evaluate(p, labels, "newest"), evaluate(p, labels, "newest", forecast=fp)
    return {"fresh_AP": round(r0["fresh_AP"], 4), "sAP": round(r0["sAP"], 4), "sAP_fc": round(r1["sAP"], 4)}
res = {}
grid = [(0, 0)] + [(60, L) for L in (45, 60, 75, 100, 150, 200)] + [(100, L) for L in (60, 75, 100, 150, 200)] + [(150, 150), (150, 200)]
for name in V:
    for gap, L in (grid if name not in ("s640q90_chk",) else [(0, 0)]):
        r = run(name, gap, L); res[f"{name}|gap{gap}|L{L}"] = r
        print(f"{name:12s} gap {gap:3d} L {L:3d}  {r}", flush=True)
json.dump(res, open(SP / "emu.json", "w"), indent=1)
