"""s960q90 detections on VisDrone-VID val, same pipeline as vd_variant_dets.py (letterbox, cv2 JPEG, FP16, fast_nms).
up: from the 640x360 camera frames (upscaled); hr: from the original frames resized to <res> wide."""
import json, sys
from pathlib import Path
import cv2, numpy as np, torch
R = Path("/home/sengar/BTP/uav-split-perception")
sys.path.insert(0, str(R / "validation/hardware"))
from hwbench import fast_nms, load_model
from ultralytics.data.augment import LetterBox
VID = R / "datasets/visdrone_vid_640"
ORIG = R / "datasets/visdrone_vid/VisDrone2019-VID-val/VisDrone2019-VID-val/sequences"
OUT = Path(sys.argv[1])
keys = [(sq, i) for sq, n in json.load(open(VID / "sequences.json")) for i in range(1, n + 1)]
dev = torch.device("cuda")
m = load_model(str(R / "weights/yolov8s_visdrone.pt"), dev, True)
sizes = {}
for var, res, q, src in [("s640q90_chk", 640, 90, "cam"), ("s960q90_up", 960, 90, "cam"),
                         ("s960q90_hr", 960, 90, "hr"), ("s1280q90_hr", 1280, 90, "hr"), ("s960q75_hr", 960, 75, "hr")]:
    lb, out, nb = LetterBox((res, res), auto=False), {}, []
    with torch.inference_mode():
        for k in keys:
            if src == "cam":
                im = cv2.imread(str(VID / k[0] / ("%07d.jpg" % k[1])))
            else:
                o = cv2.imread(str(ORIG / k[0] / ("%07d.jpg" % k[1])))
                im = cv2.resize(o, (res, round(o.shape[0] * res / o.shape[1])), interpolation=cv2.INTER_AREA)
            im = lb(image=im)
            ok, buf = cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, q]); nb.append(len(buf))
            im = cv2.imdecode(buf, cv2.IMREAD_COLOR)
            x = torch.from_numpy(np.ascontiguousarray(im[..., ::-1].transpose(2, 0, 1))).to(dev).half() / 255.0
            o = m(x.unsqueeze(0))
            out[f"{k[0]}/{k[1]}"] = fast_nms(o[0] if isinstance(o, (list, tuple)) else o, 0.01, 0.45, 100).float().cpu().numpy()
    np.savez_compressed(OUT / f"{var}.npz", **out)
    sizes[var] = round(float(np.mean(nb)) / 1024, 1)
    print(var, "done", len(out), "frames, mean JPEG", sizes[var], "KiB", flush=True)
json.dump(sizes, open(OUT / "jpeg_kib.json", "w"), indent=1)
