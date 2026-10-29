import json, sys
import numpy as np
from pathlib import Path
R = Path("/home/sengar/BTP/uav-split-perception"); HW = R / "experiments/results/hardware"
sys.path.insert(0, str(R / "validation/hardware"))
from stream_ap import VID, Acc, unletterbox, frame_shape
labels = json.load(open(VID / "labels.json"))
keys = [(sq, i) for sq, n in json.load(open(VID / "sequences.json")) for i in range(1, n + 1)]
for name in ("yolov8s_vd", "yolov8m_vd", "yolo11n_vd", "yolo11s_vd", "yolo11m_vd"):
    z = np.load(HW / f"onboard_sap/dets_{name}.npz"); a = Acc(); b = Acc()
    for j, (sq, i) in enumerate(keys):
        h, w = frame_shape(sq); gt = np.array(labels[sq].get(str(i), []), np.float32).reshape(-1, 5)
        d = unletterbox(z[f"{sq}/{i}"], 640, h, w); a.add(d, gt)
        if j % 180 == 0: b.add(d, gt)        # 6 s at 30 fps: the frames the last emulated latency samples
    print(name, "fresh AP all 2,846 frames %.4f | every 180th frame %.4f" % (a.ap()[0], b.ap()[0]))
