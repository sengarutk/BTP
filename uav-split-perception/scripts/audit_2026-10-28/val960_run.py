import json, sys, time
from ultralytics import YOLO
from evaluation.detection_eval import resolve_dataset
from evaluation.benchmark_codecs import make_codec_hook
R = "/home/sengar/BTP/uav-split-perception"
data = str(resolve_dataset("visdrone_val"))
out = {}
for imgsz, q in [(640, None), (960, None), (960, 90), (960, 50), (800, 90), (1280, None)]:
    y = YOLO(f"{R}/weights/yolov8s_visdrone.pt")
    h = None
    if q is not None:
        h = y.model.model[0].register_forward_pre_hook(make_codec_hook("JPEG", q, {"bytes": [], "pixels": [], "enc_ms": []}))
    t = time.time()
    m = y.val(data=data, split="val", batch=1, imgsz=imgsz, device="0", plots=False, save_json=False,
              verbose=False, seed=0, workers=4, project=sys.argv[1], name=f"{imgsz}_{q}")
    if h: h.remove()
    k = f"{imgsz}_{'raw' if q is None else 'q%d' % q}"
    out[k] = {"map50_95": round(float(m.box.map), 4), "map50": round(float(m.box.map50), 4),
              "ms_inf": round(m.speed["inference"], 2), "wall_s": round(time.time() - t)}
    print(k, out[k], flush=True)
    json.dump(out, open(f"{sys.argv[1]}/val960.json", "w"), indent=1)
