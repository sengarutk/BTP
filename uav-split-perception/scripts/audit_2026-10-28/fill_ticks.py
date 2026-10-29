"""Re-score runs with the camera ticks the loop skipped put back (they hold the newest result, as the drone would).
Copies each run to the audit dir with the missing frames inserted, then scores both with stream_ap.evaluate (fc)."""
import json, sys, shutil, glob
from pathlib import Path
import numpy as np
R = Path("/home/sengar/BTP/uav-split-perception"); HW = R / "experiments/results/hardware"
sys.path.insert(0, str(R / "validation/hardware"))
from stream_ap import evaluate, VID
labels = json.load(open(VID / "labels.json"))
fp = json.load(open(HW / "forecast_tuning_v2.json"))["best"]["params"]
out = Path(sys.argv[1]); res = {}
for f in sys.argv[2:]:
    d = json.load(open(f)); fr = {x["id"]: x for x in d["frames"]}; ids = sorted(fr)
    filled, nf = [], 0
    for i in range(ids[0], ids[-1] + 1):
        if i in fr: filled.append(fr[i]); continue
        a = max(k for k in ids if k < i); b = min(k for k in ids if k > i)
        sa, ka = fr[a]["frame"]; sb, kb = fr[b]["frame"]
        if sa == sb and kb - ka == b - a:
            filled.append({"id": i, "phase": fr[a]["phase"], "frame": [sa, ka + (i - a)]}); nf += 1
    d2 = dict(d, frames=filled)
    p = out / Path(f).name
    json.dump(d2, open(p, "w")); shutil.copy(f[:-5] + "_dets.npz", str(p)[:-5] + "_dets.npz")
    live = Path(f[:-5] + "_livefc.npz")
    if live.exists(): shutil.copy(live, str(p)[:-5] + "_livefc.npz")
    kw = {"forecast": fp, "live": live.exists()}
    r0 = evaluate(Path(f), labels, "newest", **kw)["sAP"]; r1 = evaluate(p, labels, "newest", **kw)["sAP"]
    res[f] = (len(ids), nf, r0, r1)
    print(Path(f).parent.name, Path(f).stem, "missing", ids[-1] - ids[0] + 1 - len(ids), "filled", nf,
          "sAP+fc %.4f -> %.4f (%+.2f %%)" % (r0, r1, 100 * (r1 / r0 - 1)), flush=True)
json.dump(res, open(out / "fill_ticks.json", "w"), indent=1)
