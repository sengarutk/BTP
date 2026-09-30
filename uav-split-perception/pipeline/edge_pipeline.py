"""Edge (UAV) streaming process: capture -> edge submodel -> quantize -> packet -> ZeroMQ.

Frames come from an image directory, a video file, or a camera index and are letterboxed to
640x640 exactly as Ultralytics does. The packet timestamp is the *capture* time, so the
latency the cloud reports includes onboard compute, quantization, and transmission.
"""

import argparse
import time
from pathlib import Path
from typing import Iterator, Optional, Union

import cv2
import numpy as np
import torch
from ultralytics import YOLO
from ultralytics.data.augment import LetterBox

from core.dynamic_submodels import DynamicEdgeSubmodel, load_submodel
from protocol.packet import AegisPacketProtocol
from protocol.transport import AegisZMQPublisher
from quantization.quantizer import VALID_DTYPES, FeatureMapQuantizer
from utils.logger import get_logger

logger = get_logger("EdgePipeline")
REPO_ROOT = Path(__file__).resolve().parent.parent


def frame_source(source: Union[str, int], imgsz: int = 640, loop: bool = True) -> Iterator[np.ndarray]:
    """Yields letterboxed BGR frames from a directory of images, a video file, or a camera index."""
    lb = LetterBox((imgsz, imgsz), auto=False)
    src = str(source)
    path = Path(src)
    if path.is_dir():
        files = sorted(p for p in path.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
        if not files:
            raise FileNotFoundError(f"No images in {path}")
        while True:
            for f in files:
                img = cv2.imread(str(f))
                if img is not None:
                    yield lb(image=img)
            if not loop:
                return
    cap = cv2.VideoCapture(int(src) if src.isdigit() else src)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video source {src!r}")
    try:
        while True:
            ok, img = cap.read()
            if not ok:
                if loop and not src.isdigit():
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                return
            yield lb(image=img)
    finally:
        cap.release()


class EdgePipeline:
    def __init__(self, cut_layer: int = 4, dtype: str = "int8", endpoint: str = "ipc:///tmp/aegis_split.ipc",
                 weights: str = "yolov8s.pt", checkpoint: Optional[str] = None, device: str = "cpu",
                 target_fps: float = 30.0, bind: bool = True, auth_key: Optional[bytes] = None):
        if dtype not in VALID_DTYPES:
            raise ValueError(f"Unsupported dtype {dtype!r}")
        self.device = torch.device(device)
        if checkpoint:
            self.edge = load_submodel(checkpoint, device=self.device)
        else:
            self.edge = DynamicEdgeSubmodel(YOLO(weights).model, cut_layer).to(self.device)
        if self.edge.is_full:
            raise ValueError("The full model has nothing to offload; run it onboard instead of streaming")
        self.cut = self.edge.cut_layer
        self.dtype = dtype
        self.interval_s = 1.0 / max(target_fps, 1e-3)
        self.auth_key = auth_key
        self.publisher = AegisZMQPublisher(endpoint=endpoint, bind=bind)
        self.frames_sent = 0
        self.bytes_sent = 0
        self.last_frame_id = 0

    @torch.no_grad()
    def encode(self, frame_bgr: np.ndarray, frame_id: int, capture_ms: int) -> bytes:
        x = torch.from_numpy(np.ascontiguousarray(frame_bgr[:, :, ::-1])).permute(2, 0, 1)[None]
        x = x.to(self.device).float().div(255.0)
        q, s = FeatureMapQuantizer.quantize(self.edge(x), dtype=self.dtype)
        return AegisPacketProtocol.serialize(frame_id, capture_ms, self.cut, self.dtype, q, s, auth_key=self.auth_key)

    def stream(self, source: Union[str, int], num_frames: int = 100, log_interval: int = 25) -> int:
        start = time.perf_counter()
        try:
            # Frame ids count captured frames, so a dropped send leaves a gap instead of a reused id.
            for frame_id, frame in enumerate(frame_source(source), start=1):
                t_frame = time.perf_counter()
                capture_ms = int(time.time() * 1000)
                pkt = self.encode(frame, frame_id, capture_ms)
                if self.publisher.send_packet(pkt):
                    self.frames_sent += 1
                    self.bytes_sent += len(pkt)
                    self.last_frame_id = frame_id
                    if self.frames_sent % log_interval == 0:
                        el = time.perf_counter() - start
                        logger.info(f"[edge] {self.frames_sent} frames, {self.frames_sent / el:.1f} FPS, "
                                    f"{self.bytes_sent * 8 / el / 1e6:.1f} Mbps, {len(pkt) / 1024:.1f} KiB/frame")
                    if 0 < num_frames <= self.frames_sent:
                        break
                time.sleep(max(0.0, self.interval_s - (time.perf_counter() - t_frame)))
        except KeyboardInterrupt:
            logger.info("Interrupted")
        finally:
            self.stop()
        return self.frames_sent

    def stop(self) -> None:
        if self.publisher.is_open:
            self.publisher.send_packet(AegisPacketProtocol.make_sentinel(self.last_frame_id + 1, int(time.time() * 1000),
                                                                         self.auth_key))
            self.publisher.close()  # default linger lets the sentinel flush


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cut", type=int, default=4)
    ap.add_argument("--dtype", default="int8", choices=sorted(VALID_DTYPES))
    ap.add_argument("--source", default=str(REPO_ROOT / "datasets" / "coco" / "images" / "val2017"))
    ap.add_argument("--endpoint", default="ipc:///tmp/aegis_split.ipc")
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--num-frames", type=int, default=100)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--checkpoint", default=None, help="standalone edge checkpoint (core/export_submodels.py)")
    ap.add_argument("--auth-key", default=None, help="shared secret enabling HMAC-SHA256 packet authentication")
    args = ap.parse_args()
    EdgePipeline(args.cut, args.dtype, args.endpoint, checkpoint=args.checkpoint, device=args.device,
                 target_fps=args.fps, auth_key=args.auth_key.encode() if args.auth_key else None
                 ).stream(args.source, args.num_frames)
