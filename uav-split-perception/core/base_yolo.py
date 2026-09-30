"""Base YOLOv8 wrapper with hardware-aware device placement and baseline inference."""

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import numpy as np
import torch
from ultralytics import YOLO


from utils.logger import get_logger

logger = get_logger("BaseYOLO")


class BaseYOLO:
    """Production wrapper for YOLOv8 baseline model with automatic hardware detection."""

    def __init__(
        self,
        weights: str = "yolov8s.pt",
        device: Optional[str] = None,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
    ):
        """Initializes the BaseYOLO model with hardware awareness.

        Args:
            weights: Path to weights or model tag (e.g., 'yolov8s.pt').
            device: Explicit device ('cuda', 'cuda:0', 'cpu') or None for auto-detection.
            conf_threshold: Confidence threshold for NMS filtering.
            iou_threshold: IoU threshold for NMS box suppression.
        """
        self.weights_name = weights
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold

        # 1. Resolve and configure execution device
        self.device, self.device_info = self._configure_device(device)

        # 2. Load model
        logger.info(f"Loading YOLO model weights from '{self.weights_name}' onto {self.device}...")
        self.yolo = YOLO(self.weights_name)
        self.model = self.yolo.model.to(self.device)
        self.model.eval()

        logger.success(
            f"Successfully initialized {self.weights_name} on {self.device_info['device_name']} "
            f"(Total Params: {sum(p.numel() for p in self.model.parameters()):,})"
        )

    def _configure_device(self, requested_device: Optional[str]) -> Tuple[torch.device, Dict[str, Any]]:
        """Detects available hardware, logs platform diagnostics, and configures device."""
        if requested_device is not None:
            target_device = torch.device(requested_device)
        else:
            target_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        device_info: Dict[str, Any] = {"type": target_device.type}

        if target_device.type == "cuda" and torch.cuda.is_available():
            cuda_idx = target_device.index if target_device.index is not None else 0
            gpu_name = torch.cuda.get_device_name(cuda_idx)
            cap_major, cap_minor = torch.cuda.get_device_capability(cuda_idx)
            total_vram_gb = torch.cuda.get_device_properties(cuda_idx).total_memory / (1024**3)

            device_info.update(
                {
                    "device_name": gpu_name,
                    "device_index": cuda_idx,
                    "compute_capability": f"{cap_major}.{cap_minor}",
                    "total_vram_gb": round(total_vram_gb, 2),
                }
            )

            logger.info(
                f"CUDA Acceleration Detected: {gpu_name} | "
                f"Compute Capability {cap_major}.{cap_minor} | "
                f"Total VRAM: {total_vram_gb:.2f} GB"
            )
        else:
            cpu_cores = torch.get_num_threads()
            device_info.update(
                {
                    "device_name": f"Multi-threaded CPU ({cpu_cores} threads)",
                    "cpu_threads": cpu_cores,
                }
            )
            logger.info(f"Running on CPU ({cpu_cores} PyTorch threads).")

        return target_device, device_info

    def warmup(self, input_size: Tuple[int, int] = (640, 640), iterations: int = 3):
        """Warms up the execution engine to stabilize CUDA kernels."""
        logger.info(f"Warming up model with {iterations} iterations on dummy input {input_size}...")
        dummy_tensor = torch.zeros((1, 3, *input_size), dtype=torch.float32, device=self.device)
        with torch.no_grad():
            for _ in range(iterations):
                _ = self.model(dummy_tensor)
        if self.device.type == "cuda":
            torch.cuda.synchronize()
        logger.success("Model warmup complete.")

    def predict(
        self,
        source: Union[str, np.ndarray, torch.Tensor],
        conf: Optional[float] = None,
        iou: Optional[float] = None,
        imgsz: int = 640,
    ):
        """Performs end-to-end baseline inference using Ultralytics engine.

        Args:
            source: Image path, numpy array (H, W, C), or tensor.
            conf: Override confidence threshold.
            iou: Override IoU threshold.
            imgsz: Input inference image resolution.

        Returns:
            List of ultralytics Results objects containing boxes, scores, classes, and raw outputs.
        """
        conf_val = conf if conf is not None else self.conf_threshold
        iou_val = iou if iou is not None else self.iou_threshold

        results = self.yolo.predict(
            source=source,
            conf=conf_val,
            iou=iou_val,
            imgsz=imgsz,
            device=str(self.device),
            verbose=False,
        )
        return results

    def forward_raw(self, x: torch.Tensor) -> Any:
        """Executes raw forward pass through PyTorch model returning head feature maps or raw outputs."""
        if x.device != self.device:
            x = x.to(self.device)
        with torch.no_grad():
            return self.model(x)


if __name__ == "__main__":
    yolo_wrapper = BaseYOLO("yolov8s.pt")
    yolo_wrapper.warmup()
    # Test dummy inference
    dummy_img = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
    res = yolo_wrapper.predict(dummy_img)
    logger.info(f"Baseline inference test complete. Detected objects: {len(res[0].boxes)}")
