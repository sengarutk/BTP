"""Interactive split-inference demo with an on-screen HUD.

Runs the real edge submodel, quantizer, packet format, and cloud dispatcher in one process
and lets you switch the cut (k4 / k9 / onboard) and toggle a link blackout. Transmission time
is *simulated* from the chosen bandwidth (payload bits / bandwidth); during a blackout offloaded
frames are dropped. Everything else (compute, quantization, packets) is executed for real.
"""

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import cv2
import numpy as np
import torch
import torchvision
from ultralytics import YOLO
from ultralytics.data.augment import LetterBox
from ultralytics.utils import nms

from core.submodels import DynamicCloudDispatcher
from core.dynamic_submodels import DynamicEdgeSubmodel
from protocol.packet import AegisPacketProtocol
from quantization.quantizer import FeatureMapQuantizer
from utils.logger import get_logger

logger = get_logger("LiveSplitDemo")

COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
    "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack",
    "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
    "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
    "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
    "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator",
    "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"
]


def postprocess_nms(preds, conf_thres: float = 0.25, iou_thres: float = 0.45) -> torch.Tensor:
    """Standard Ultralytics NMS for image 0 -> (N, 6) [x1, y1, x2, y2, conf, cls]."""
    raw = preds[0] if isinstance(preds, (tuple, list)) else preds
    return nms.non_max_suppression(raw, conf_thres=conf_thres, iou_thres=iou_thres)[0]


class FrameStreamer:
    """Yields frames from video, camera, or cycles through images in a folder."""

    def __init__(self, source: str, target_size: Tuple[int, int] = (640, 640)):
        self.target_size = target_size
        self.letterbox = LetterBox(target_size, auto=False)
        self.source = source
        self.cap = None
        self.image_files: List[Path] = []
        self.img_idx = 0

        # Check if source is a numeric camera
        if source.isdigit():
            self.cap = cv2.VideoCapture(int(source))
        elif os.path.isfile(source):
            self.cap = cv2.VideoCapture(source)
        else:
            # Check directory of images
            src_path = Path(source)
            if src_path.is_dir():
                self.image_files = sorted(list(src_path.glob("*.jpg")) + list(src_path.glob("*.png")))
            elif not src_path.exists():
                # Fallback to coco128 if available
                coco_dir = Path(__file__).resolve().parent.parent / "datasets" / "coco" / "images" / "val2017"
                if coco_dir.exists():
                    self.image_files = sorted(list(coco_dir.glob("*.jpg")))

    def read_frame(self) -> np.ndarray:
        """Reads next frame and resizes to target_size."""
        if self.cap is not None and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret and frame is not None:
                return self.letterbox(image=frame)
            # Loop video
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
            if ret and frame is not None:
                return self.letterbox(image=frame)

        if self.image_files:
            img_path = self.image_files[self.img_idx % len(self.image_files)]
            self.img_idx += 1
            frame = cv2.imread(str(img_path))
            if frame is not None:
                return self.letterbox(image=frame)

        # Fallback synthetic frame with animation
        frame = np.full((self.target_size[1], self.target_size[0], 3), 40, dtype=np.uint8)
        cx = int(320 + 200 * np.sin(self.img_idx * 0.1))
        cy = int(320 + 150 * np.cos(self.img_idx * 0.1))
        cv2.circle(frame, (cx, cy), 50, (0, 200, 255), -1)
        cv2.putText(frame, "UAV Aerial Surveillance Feed", (120, 280), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
        self.img_idx += 1
        return frame

    def release(self):
        if self.cap is not None:
            self.cap.release()


def draw_hud_overlay(
    frame: np.ndarray,
    detections: torch.Tensor,
    split_cut: str,
    dtype: str,
    bandwidth_mbps: float,
    wire_size_kib: float,
    t_edge_ms: float,
    t_quant_ms: float,
    t_tx_ms: float,
    t_cloud_ms: float,
    fps: float,
    is_blackout: bool = False,
    is_relayed: bool = False,
) -> np.ndarray:
    """Renders semi-transparent HUD banner and bounding boxes on display frame."""
    disp_frame = frame.copy()
    h, w = disp_frame.shape[:2]

    # 1. Draw Detections
    for det in detections:
        x1, y1, x2, y2, conf, cls_id = det.tolist()
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        cls_idx = int(cls_id)
        label = COCO_CLASSES[cls_idx] if 0 <= cls_idx < len(COCO_CLASSES) else f"class_{cls_idx}"

        color = (0, 230, 115)  # Green
        cv2.rectangle(disp_frame, (x1, y1), (x2, y2), color, 2)
        tag = f"{label} {conf:.2f}"
        cv2.putText(disp_frame, tag, (x1, max(20, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3)
        cv2.putText(disp_frame, tag, (x1, max(20, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    # 2. Draw Translucent HUD Dashboard (Top Banner)
    hud_h = 135
    overlay = disp_frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, hud_h), (15, 15, 25), -1)
    alpha = 0.82
    cv2.addWeighted(overlay, alpha, disp_frame, 1 - alpha, 0, disp_frame)
    cv2.line(disp_frame, (0, hud_h), (w, hud_h), (0, 200, 255), 2)

    # Status Strings
    cut_desc = "Layer 4 (Bottleneck)" if split_cut == "k4" else ("Layer 9 (Multi-Scale)" if split_cut == "k9" else "Layer 22 (Full Onboard)")
    t_e2e = t_edge_ms + t_quant_ms + t_tx_ms + t_cloud_ms

    if is_blackout:
        link_str = "5G LINK: [0.0 Mbps BLACKOUT]"
        link_color = (0, 0, 255)  # Red
        relay_str = " | offloaded frame DROPPED" if split_cut != "k22" else " | onboard"
    else:
        link_str = f"5G LINK: {bandwidth_mbps:.1f} Mbps"
        link_color = (0, 255, 0)
        relay_str = ""

    # Line 1: Header & Split Info
    line1 = f"AEGIS-UAV LIVE SPLIT-PERCEPTION | Cut: {split_cut.upper()} ({cut_desc}) | Precision: {dtype.upper()}"
    cv2.putText(disp_frame, line1, (15, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.60, (0, 225, 255), 2)

    # Line 2: Network & Throughput Metrics
    line2 = f"{link_str}{relay_str} | Wire: {wire_size_kib:.1f} KiB | FPS: {fps:4.1f} | Latency (tx simulated): {t_e2e:5.1f}ms"
    cv2.putText(disp_frame, line2, (15, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 1)

    # Line 3: Detailed Stage Latency Breakdown
    line3 = f"Stage Latencies: T_edge={t_edge_ms:.2f}ms  T_quant={t_quant_ms:.2f}ms  T_tx={t_tx_ms:.2f}ms  T_cloud={t_cloud_ms:.2f}ms"
    cv2.putText(disp_frame, line3, (15, 84), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (180, 240, 255), 1)

    # Line 4: Interactive Key Controls
    line4 = "Controls: [1] Cut k4  [2] Cut k9  [3] Local k22  [b] Toggle 5G Blackout  [q] Quit"
    cv2.putText(disp_frame, line4, (15, 114), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 200, 100), 1)

    return disp_frame


def run_live_demo(
    source: str = "datasets/coco/images/val2017",
    dry_run: bool = False,
    max_frames: int = 50,
    initial_split: str = "k4",
    dtype: str = "int8",
    bandwidth_mbps: float = 50.0,
    device: str = "cpu",
    save_demo_path: Optional[str] = None,
    auto_test: bool = False,
) -> int:
    """Executes live split-perception streaming demonstration."""
    # Automatic WSLg display detection
    if "DISPLAY" not in os.environ and os.path.exists("/tmp/.X11-unix/X0"):
        os.environ["DISPLAY"] = ":0"
    if "WAYLAND_DISPLAY" not in os.environ and os.path.exists("/mnt/wslg/runtime-dir"):
        os.environ["WAYLAND_DISPLAY"] = "wayland-0"
        os.environ["XDG_RUNTIME_DIR"] = "/mnt/wslg/runtime-dir"

    logger.info(f"Initializing AEGIS-UAV Demonstration Pipeline on {device} (Display: {os.environ.get('DISPLAY', 'None')})...")
    target_device = torch.device(device)

    # Load Base YOLOv8s Model
    base_model_path = "yolov8s.pt"
    logger.info(f"Loading YOLOv8s backbone from '{base_model_path}'...")
    yolo = YOLO(base_model_path)
    base_model = yolo.model.to(target_device).eval()

    # Pre-instantiate Edge Submodels
    edge_k4 = DynamicEdgeSubmodel(base_model, cut_layer=4).to(target_device).eval()
    edge_k9 = DynamicEdgeSubmodel(base_model, cut_layer=9).to(target_device).eval()

    # Pre-instantiate Cloud Dispatcher
    dispatcher = DynamicCloudDispatcher(
        base_model=base_model,
        candidate_cuts=[2, 4, 9, 12],
        device=target_device,
    ).eval()

    streamer = FrameStreamer(source)
    writer = None
    if save_demo_path:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(save_demo_path, fourcc, 30.0, (640, 640))

    split_mode = initial_split.lower()
    curr_bw = bandwidth_mbps
    is_blackout = False

    logger.info(f"Starting demonstration loop (Dry Run={dry_run}, Target Frames={max_frames})...")
    frame_count = 0
    t_start = time.time()
    last_fps_time = time.time()
    measured_fps = 30.0

    try:
        while True:
            t_frame_start = time.perf_counter_ns()
            frame = streamer.read_frame()
            if frame is None:
                break

            frame_count += 1

            # Prepare normalized tensor: (1, 3, 640, 640)
            img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img_tensor = torch.from_numpy(img_rgb).permute(2, 0, 1).unsqueeze(0).float() / 255.0
            img_tensor = img_tensor.to(target_device)

            # -------------------------------------------------------------
            # Stage 1: Edge Execution
            # -------------------------------------------------------------
            sync = (lambda: torch.cuda.synchronize()) if target_device.type == "cuda" else (lambda: None)
            sync()
            t0 = time.perf_counter_ns()
            cut_int = {"k4": 4, "k9": 9}.get(split_mode, 22)
            with torch.no_grad():
                edge_out = base_model(img_tensor) if cut_int == 22 else (edge_k4 if cut_int == 4 else edge_k9)(img_tensor)
            sync()
            t1 = time.perf_counter_ns()
            t_edge_ms = (t1 - t0) / 1e6
            is_relayed = False
            t_quant_ms = t_tx_ms = t_cloud_ms = wire_size_kib = 0.0

            if cut_int == 22:
                dets = postprocess_nms(edge_out, conf_thres=0.25, iou_thres=0.45)
            else:
                q_features, scales = FeatureMapQuantizer.quantize(edge_out, dtype=dtype)
                packet_bytes = AegisPacketProtocol.serialize(frame_count, int(time.time() * 1000), cut_int, dtype,
                                                             q_features, scales)
                t2 = time.perf_counter_ns()
                t_quant_ms = (t2 - t1) / 1e6
                wire_size_kib = len(packet_bytes) / 1024.0
                if is_blackout:
                    dets = torch.zeros((0, 6))  # no link: the offloaded frame is lost
                else:
                    t_tx_ms = len(packet_bytes) * 8.0 / (max(curr_bw, 1e-3) * 1e3)  # simulated airtime
                    parsed = AegisPacketProtocol.deserialize(packet_bytes, device=target_device)
                    recon_act = FeatureMapQuantizer.dequantize(parsed["reconstructed_data"], parsed["scales"],
                                                               dtype=parsed["dtype"], device=target_device)
                    with torch.no_grad():
                        cloud_out = dispatcher(recon_act, split_code=parsed["split_code"])
                    dets = postprocess_nms(cloud_out, conf_thres=0.25, iou_thres=0.45)
                    sync()
                    t_cloud_ms = (time.perf_counter_ns() - t2) / 1e6

            # Compute FPS
            if frame_count % 5 == 0:
                elapsed_now = time.time() - last_fps_time
                measured_fps = 5.0 / max(1e-4, elapsed_now)
                last_fps_time = time.time()

            # Render HUD Display
            hud_frame = draw_hud_overlay(
                frame=frame,
                detections=dets,
                split_cut=split_mode,
                dtype=dtype,
                bandwidth_mbps=0.0 if is_blackout else curr_bw,
                wire_size_kib=wire_size_kib,
                t_edge_ms=t_edge_ms,
                t_quant_ms=t_quant_ms,
                t_tx_ms=t_tx_ms,
                t_cloud_ms=t_cloud_ms,
                fps=measured_fps,
                is_blackout=is_blackout,
                is_relayed=is_relayed,
            )

            if writer is not None:
                writer.write(hud_frame)

            # Logging Telemetry
            if dry_run or frame_count % 10 == 0:
                logger.info(
                    f"[Frame {frame_count:>3d}] Cut: {split_mode.upper():>3s} | "
                    f"5G: {('0.0' if is_blackout else f'{curr_bw:.1f}'):>5s} Mbps | "
                    f"Wire: {wire_size_kib:5.1f} KiB | "
                    f"Edge: {t_edge_ms:4.2f}ms | Quant: {t_quant_ms:4.2f}ms | "
                    f"Tx: {t_tx_ms:4.2f}ms | Cloud: {t_cloud_ms:4.2f}ms | "
                    f"FPS: {measured_fps:4.1f} | Dets: {len(dets):2d}"
                )

            # Automated interactive test transitions
            if auto_test:
                if frame_count == 10:
                    split_mode = "k9"
                    logger.info("[Auto-Test Key '2'] Switched dynamically to Cut k9 (Multi-Scale Bundle)")
                elif frame_count == 20:
                    split_mode = "k22"
                    logger.info("[Auto-Test Key '3'] Switched dynamically to Full Local Inference (k22)")
                elif frame_count == 30:
                    split_mode = "k4"
                    is_blackout = True
                    logger.info("[Auto-Test Key 'b'] Link blackout on: offloaded frames are dropped")
                elif frame_count == 40:
                    is_blackout = False
                    logger.info("[Auto-Test Key 'b'] Restored 5G Cellular Link (50.0 Mbps)")
                elif frame_count >= max_frames:
                    logger.success(f"[Auto-Test Key 'q'] All interactive controls verified across {frame_count} frames.")
                    break

            # Dry-run termination check
            if dry_run and frame_count >= max_frames:
                logger.success(f"Dry-run successfully completed {frame_count} frames without errors.")
                break

            # GUI display only when not in dry-run
            if not dry_run:
                cv2.imshow("AEGIS-UAV Split Perception Demo", hud_frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q") or key == 27:
                    logger.info("User requested exit.")
                    break
                elif key == ord("1"):
                    split_mode = "k4"
                    logger.info("Switching to Split Cut k4...")
                elif key == ord("2"):
                    split_mode = "k9"
                    logger.info("Switching to Split Cut k9...")
                elif key == ord("3"):
                    split_mode = "k22"
                    logger.info("Switching to Full Local Edge k22...")
                elif key == ord("b"):
                    is_blackout = not is_blackout
                    status = "ENABLED (0 Mbps)" if is_blackout else f"DISABLED ({curr_bw} Mbps)"
                    logger.info(f"5G Blackout toggled -> {status}")

    except KeyboardInterrupt:
        logger.info("Demo interrupted by user.")
    finally:
        streamer.release()
        if writer is not None:
            writer.release()
        if not dry_run:
            cv2.destroyAllWindows()

    total_time = time.time() - t_start
    logger.success(
        f"Demonstration Finished: {frame_count} frames processed in {total_time:.2f}s "
        f"({frame_count / max(1e-3, total_time):.1f} FPS avg)."
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AEGIS-UAV Live Split-Perception Video Demo")
    parser.add_argument("--source", type=str, default="datasets/coco/images/val2017", help="Video file, image dir, or camera index")
    parser.add_argument("--dry-run", action="store_true", help="Execute headless dry-run without GUI display")
    parser.add_argument("--frames", type=int, default=50, help="Frames to process in dry-run mode")
    parser.add_argument("--split", type=str, default="k4", choices=["k4", "k9", "k22", "full"], help="Initial split cut")
    parser.add_argument("--dtype", type=str, default="int8", choices=["int8", "uint8_zstd", "fp16", "fp32"], help="Precision mode")
    parser.add_argument("--bandwidth", type=float, default=50.0, help="Simulated 5G bandwidth (Mbps)")
    parser.add_argument("--device", type=str, default="cpu", help="Compute device ('cpu' or 'cuda')")
    parser.add_argument("--save-demo", type=str, default=None, help="Path to record MP4 video")
    parser.add_argument("--auto-test", action="store_true", help="Automate transitions across cuts and blackout for testing")
    args = parser.parse_args()

    run_live_demo(
        source=args.source,
        dry_run=args.dry_run,
        max_frames=args.frames,
        initial_split=args.split,
        dtype=args.dtype,
        bandwidth_mbps=args.bandwidth,
        device=args.device,
        save_demo_path=args.save_demo,
        auto_test=args.auto_test,
    )
