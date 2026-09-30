"""Runtime switchboard: applies the adaptive policy to real frames on the edge device.

The decision logic is simulation.system_model.AdaptivePolicy -- the same object the
trace-driven experiments evaluate -- so the deployed behaviour matches the reported one.
For each frame the switchboard asks the policy for a configuration and produces what would
be sent: nothing (onboard inference), a feature packet (split), or a JPEG/WebP image (codec).
"""

import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Union

import cv2
import numpy as np
import torch
from ultralytics import YOLO

from core.dynamic_submodels import DynamicEdgeSubmodel
from protocol.packet import AegisPacketProtocol
from quantization.quantizer import FeatureMapQuantizer
from simulation.system_model import AdaptivePolicy, EdgeHardware, OffloadConfig, load_offload_configs, make_hardware
from utils.logger import get_logger

logger = get_logger("RuntimeSwitchboard")


@dataclass
class FrameOutput:
    frame_id: int
    config: str
    kind: str
    payload: Optional[bytes]            # bytes to transmit (None for onboard)
    detections: Optional[torch.Tensor]  # raw onboard predictions (onboard kind only)
    t_process_ms: float


class RuntimeSplitSwitchboard:
    def __init__(self, weights: str = "yolov8s.pt", device: str = "cpu", t_full_ms: float = 180.0,
                 candidates: Optional[List[str]] = None, configs: Optional[Dict[str, OffloadConfig]] = None,
                 hardware: Optional[EdgeHardware] = None):
        self.configs = configs or load_offload_configs()
        names = candidates or list(self.configs)
        missing = [n for n in names if n not in self.configs]
        if missing:
            raise KeyError(f"Unknown configurations: {missing}")
        self.device = torch.device(device)
        self.hw = hardware or make_hardware(t_full_ms)
        self.policy = AdaptivePolicy([self.configs[n] for n in names], self.hw)
        self.base = YOLO(weights).model.to(self.device).eval()
        self.edges: Dict[int, DynamicEdgeSubmodel] = {}
        for n in names:
            c = self.configs[n]
            if c.kind == "split" and c.cut not in self.edges:
                self.edges[c.cut] = DynamicEdgeSubmodel(self.base, c.cut).to(self.device)
        self.frame_seq = 0

    @torch.no_grad()
    def process_frame(self, frame_bgr: np.ndarray, bandwidth_estimate_mbps: float) -> FrameOutput:
        """``frame_bgr`` is a letterboxed 640x640 uint8 BGR image."""
        self.frame_seq += 1
        capture_ms = int(time.time() * 1000)  # stamp on arrival, as edge_pipeline does
        cfg = self.policy.decide(bandwidth_estimate_mbps)
        t0 = time.perf_counter()
        payload, dets = None, None
        if cfg.kind == "codec":
            ext, flag = (".jpg", cv2.IMWRITE_JPEG_QUALITY) if cfg.name.startswith("jpeg") else (".webp", cv2.IMWRITE_WEBP_QUALITY)
            ok, enc = cv2.imencode(ext, frame_bgr, [flag, int(cfg.dtype.lstrip("q"))])
            if not ok:
                raise RuntimeError(f"{cfg.name} encoding failed")
            payload = enc.tobytes()
        else:
            x = torch.from_numpy(np.ascontiguousarray(frame_bgr[:, :, ::-1])).permute(2, 0, 1)[None]
            x = x.to(self.device).float().div(255.0)
            if cfg.kind == "onboard":
                dets = self.base(x)
            else:
                q, s = FeatureMapQuantizer.quantize(self.edges[cfg.cut](x), dtype=cfg.dtype)
                payload = AegisPacketProtocol.serialize(self.frame_seq, capture_ms, cfg.cut, cfg.dtype, q, s)
        return FrameOutput(self.frame_seq, cfg.name, cfg.kind, payload, dets, (time.perf_counter() - t0) * 1000.0)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--image", default="datasets/coco/images/val2017/000000000139.jpg")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()
    from ultralytics.data.augment import LetterBox

    img = LetterBox((640, 640), auto=False)(image=cv2.imread(args.image))
    sb = RuntimeSplitSwitchboard(device=args.device)
    for bw in (0.0, 5.0, 20.0, 60.0, 200.0):
        out = sb.process_frame(img, bw)
        size = len(out.payload) / 1024 if out.payload else 0.0
        print(f"{bw:6.1f} Mbps -> {out.config:<18} ({out.kind}), {size:7.1f} KiB, {out.t_process_ms:6.1f} ms on host")
