"""Live onboard run vs the emulation's detections on the SAME frames: fresh AP of each."""
import json, sys, glob
import numpy as np
from pathlib import Path
R = Path("/home/sengar/BTP/uav-split-perception"); HW = R / "experiments/results/hardware"
sys.path.insert(0, str(R / "validation/hardware"))
from stream_ap import VID, Acc, unletterbox, frame_shape
labels = json.load(open(VID / "labels.json"))
emu = np.load(HW / "onboard_sap/dets_yolov8s_vd.npz"); vdv = np.load(HW / "vd_variant_dets/s640.npz")
for f in sorted(glob.glob(str(HW / "vid_campaign_onboard_vd_pi*/a2_*s640*__r*.json")))[:4]:
    run = json.load(open(f)); dets = np.load(f[:-5] + "_dets.npz")
    a_live, a_emu, a_vdv = Acc(), Acc(), Acc()
    for fr in run["frames"]:
        if fr.get("t_res") is None or str(fr["id"]) not in dets: continue
        sq, k = fr["frame"]; h, w = frame_shape(sq)
        gt = np.array(labels[sq].get(str(k), []), np.float32).reshape(-1, 5)
        a_live.add(unletterbox(dets[str(fr["id"])], fr["res"], h, w), gt)
        a_emu.add(unletterbox(emu[f"{sq}/{k}"], 640, h, w), gt)
        a_vdv.add(unletterbox(vdv[f"{sq}/{k}"], 640, h, w), gt)
    print(Path(f).parent.name, Path(f).stem, "results", len(a_live.tp), "fresh AP live %.4f | emulation dets %.4f | vd_variant s640 %.4f" % (a_live.ap()[0], a_emu.ap()[0], a_vdv.ap()[0]))
