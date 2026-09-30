"""Cloud (ground server) process: ZeroMQ -> validate packet -> dequantize -> cloud submodel -> NMS.

One model copy serves every split point through DynamicCloudDispatcher. Any malformed or
inconsistent packet is dropped and counted; it never stops the server. Reported end-to-end
latency uses the capture timestamp in the packet and is only meaningful when edge and cloud
clocks are synchronised (same host, or PTP/NTP-disciplined hosts).
"""

import argparse
import time
from collections import deque
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional

import numpy as np
import torch
from ultralytics import YOLO
from ultralytics.utils import nms

from core.submodels import DynamicCloudDispatcher
from protocol.packet import AegisPacketProtocol, CorruptedPacketException
from protocol.transport import AegisZMQSubscriber
from quantization.quantizer import FeatureMapQuantizer
from utils.logger import get_logger

logger = get_logger("CloudPipeline")


def postprocess_nms(preds: Any, conf_thres: float = 0.25, iou_thres: float = 0.45, max_det: int = 300) -> torch.Tensor:
    """Standard Ultralytics NMS; returns an (N, 6) tensor [x1, y1, x2, y2, conf, cls] for image 0."""
    raw = preds[0] if isinstance(preds, (list, tuple)) else preds
    return nms.non_max_suppression(raw, conf_thres=conf_thres, iou_thres=iou_thres, max_det=max_det)[0]


class CloudPipeline:
    def __init__(self, endpoint: str = "ipc:///tmp/aegis_split.ipc", weights: str = "yolov8s.pt",
                 device: str = "cuda" if torch.cuda.is_available() else "cpu", conf_thres: float = 0.25,
                 iou_thres: float = 0.45, bind: bool = False, idle_timeout_s: float = 10.0,
                 auth_key: Optional[bytes] = None, keep_records: int = 1000,
                 on_detections: Optional[Callable[[int, torch.Tensor], None]] = None):
        self.device = torch.device(device)
        self.dispatcher = DynamicCloudDispatcher(YOLO(weights).model, device=self.device)
        self.conf_thres, self.iou_thres = conf_thres, iou_thres
        self.idle_timeout_s = idle_timeout_s
        self.auth_key = auth_key
        self.on_detections = on_detections
        self.subscriber = AegisZMQSubscriber(endpoint=endpoint, bind=bind, timeout_ms=500)
        self.records: Deque[Dict[str, Any]] = deque(maxlen=keep_records)
        self.frames_processed = 0
        self.frames_rejected = 0

    def _sync(self) -> None:
        if self.device.type == "cuda":
            torch.cuda.synchronize()

    @torch.no_grad()
    def handle(self, packet: bytes) -> Optional[Dict[str, Any]]:
        """Processes one packet; returns a telemetry record, or None for the end-of-stream sentinel."""
        t0 = time.perf_counter()
        parsed = AegisPacketProtocol.deserialize(packet, device=self.device, auth_key=self.auth_key)
        if parsed["is_sentinel"]:
            return None
        feats = FeatureMapQuantizer.dequantize(parsed["reconstructed_data"], parsed["scales"],
                                               dtype=parsed["dtype"], device=self.device)
        self._sync()
        t1 = time.perf_counter()
        out = self.dispatcher(feats, split_code=parsed["split_code"])
        self._sync()
        t2 = time.perf_counter()
        dets = postprocess_nms(out, self.conf_thres, self.iou_thres)
        self._sync()
        t3 = time.perf_counter()
        if self.on_detections:
            self.on_detections(parsed["frame_id"], dets)
        return {"frame_id": parsed["frame_id"], "split": parsed["split_mode"], "dtype": parsed["dtype"],
                "wire_bytes": parsed["wire_size_bytes"], "t_decode_ms": (t1 - t0) * 1e3,
                "t_cloud_ms": (t2 - t1) * 1e3, "t_nms_ms": (t3 - t2) * 1e3, "num_detections": int(dets.shape[0]),
                "capture_to_result_ms": time.time() * 1000.0 - parsed["timestamp_ms"]}

    def listen(self, max_frames: int = 0) -> List[Dict[str, Any]]:
        last = time.monotonic()
        try:
            while True:
                pkt = self.subscriber.recv_packet()
                if pkt is None:
                    if self.idle_timeout_s and time.monotonic() - last > self.idle_timeout_s:
                        logger.info(f"No packets for {self.idle_timeout_s:.0f} s; stopping")
                        break
                    continue
                last = time.monotonic()
                try:
                    rec = self.handle(pkt)
                except (CorruptedPacketException, ValueError, TypeError, KeyError, RuntimeError) as e:
                    self.frames_rejected += 1
                    logger.warning(f"Rejected packet ({type(e).__name__}): {e}")
                    continue
                if rec is None:
                    logger.info("End-of-stream sentinel received")
                    break
                self.records.append(rec)
                self.frames_processed += 1
                if self.frames_processed % 25 == 0:
                    logger.info(f"[cloud] {self.frames_processed} frames, last latency {rec['capture_to_result_ms']:.1f} ms")
                if 0 < max_frames <= self.frames_processed:
                    break
        except KeyboardInterrupt:
            logger.info("Interrupted")
        finally:
            self.subscriber.close()
        logger.success(f"Processed {self.frames_processed} frames, rejected {self.frames_rejected}")
        return list(self.records)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--endpoint", default="ipc:///tmp/aegis_split.ipc")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--weights", default="yolov8s.pt")
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--auth-key", default=None)
    args = ap.parse_args()
    CloudPipeline(args.endpoint, args.weights, args.device, idle_timeout_s=args.timeout,
                  auth_key=args.auth_key.encode() if args.auth_key else None).listen()
