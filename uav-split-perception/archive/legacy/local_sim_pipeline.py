"""Reference Local Simulation Pipeline for Split YOLOv8 Perception.

Executes sequential end-to-end edge-to-cloud split inference within a single process:
1. Edge Submodel inference (Layers 0..k)
2. Dynamic feature map quantization (FP16 / INT8)
3. Aegis binary packet serialization
4. Aegis binary packet deserialization
5. Cloud feature map dequantization
6. Cloud Submodel inference (Layers k+1..22)
7. Direct NMS post-processing on reconstructed logits
Measures per-stage micro-latencies strictly isolating:
T_e2e = T_edge + T_quant + T_ser + T_tx + T_deser + T_dequant + T_cloud + T_nms
using IEC binary units (KiB, MiB).
"""

import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import torch
from ultralytics import YOLO
from ultralytics.utils import nms


from core.submodels import EdgeSubmodel, CloudSubmodel, build_split_submodels
from protocol.packet import AegisPacketProtocol
from quantization.quantizer import (
    FeatureMapQuantizer,
    DTYPE_FP32,
    DTYPE_FP16,
    DTYPE_INT8,
)
from utils.logger import get_logger

logger = get_logger("LocalSimPipeline")

BANDWIDTH_SCENARIOS = {
    5: 5.0 * 1e6,      # 5 Mbps
    20: 20.0 * 1e6,    # 20 Mbps
    50: 50.0 * 1e6,    # 50 Mbps
    100: 100.0 * 1e6,  # 100 Mbps
}


class LocalSimulationPipeline:
    """Sequential in-memory Edge-Cloud simulation pipeline with stage-wise micro-profiling."""

    def __init__(
        self,
        weights_path: str = "yolov8s.pt",
        split_tag: str = "k4",
        dtype: str = DTYPE_INT8,
        device: Optional[str] = None,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
    ):
        self.weights_path = weights_path
        self.split_tag = split_tag
        self.dtype = dtype
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold

        logger.info(f"Initializing LocalSimulationPipeline [Split: {split_tag.upper()}, DType: {dtype.upper()}, Device: {self.device}]...")
        self.yolo = YOLO(weights_path)
        self.edge_submodel, self.cloud_submodel = build_split_submodels(self.weights_path, split_tag=self.split_tag)
        self.edge_submodel = self.edge_submodel.to(self.device).eval()
        if self.cloud_submodel is not None:
            self.cloud_submodel = self.cloud_submodel.to(self.device).eval()

    def warmup(self, num_warmup: int = 5):
        """Runs warmup forward passes to eliminate GPU kernel launch overhead."""
        dummy_img = torch.rand(1, 3, 640, 640, device=self.device)
        for _ in range(num_warmup):
            with torch.no_grad():
                if self.split_tag == "full":
                    _ = self.edge_submodel(dummy_img)
                else:
                    edge_out = self.edge_submodel(dummy_img)
                    q_data, scales = FeatureMapQuantizer.quantize(edge_out, dtype=self.dtype)
                    deq_data = FeatureMapQuantizer.dequantize(q_data, scales, dtype=self.dtype, device=self.device)
                    _ = self.cloud_submodel(deq_data)
        if self.device.startswith("cuda"):
            torch.cuda.synchronize()

    def process_frame(
        self,
        img_tensor: torch.Tensor,
        frame_id: int = 1,
    ) -> Tuple[Any, Dict[str, float]]:
        """Processes a single image tensor through all stages strictly isolating micro-latencies."""
        metrics: Dict[str, float] = {}

        # Handle full edge local inference
        if self.split_tag == "full":
            t0 = time.perf_counter()
            with torch.no_grad():
                preds = self.edge_submodel(img_tensor)
            if self.device.startswith("cuda"):
                torch.cuda.synchronize()
            t_edge = (time.perf_counter() - t0) * 1000.0

            # Direct NMS post-processing on output tensor
            t_nms_start = time.perf_counter()
            raw_preds = preds[0] if isinstance(preds, (list, tuple)) else preds
            nms_results = nms.non_max_suppression(
                raw_preds,
                conf_thres=self.conf_threshold,
                iou_thres=self.iou_threshold,
            )
            if self.device.startswith("cuda"):
                torch.cuda.synchronize()
            t_nms = (time.perf_counter() - t_nms_start) * 1000.0

            metrics["t_edge_ms"] = t_edge
            metrics["t_quant_ms"] = 0.0
            metrics["t_serialize_ms"] = 0.0
            metrics["t_deserialize_ms"] = 0.0
            metrics["t_dequant_ms"] = 0.0
            metrics["t_cloud_ms"] = 0.0
            metrics["t_nms_ms"] = t_nms
            metrics["t_e2e_compute_ms"] = t_edge + t_nms
            metrics["wire_size_bytes"] = 0
            metrics["wire_size_kib"] = 0.0
            metrics["wire_size_mib"] = 0.0
            metrics["compression_ratio"] = 1.0

            for bw_mbps, bw_bps in BANDWIDTH_SCENARIOS.items():
                metrics[f"tx_{bw_mbps}mbps_ms"] = 0.0

            return nms_results, metrics

        # Stage 1: Edge Submodel Inference
        t0 = time.perf_counter()
        with torch.no_grad():
            edge_features = self.edge_submodel(img_tensor)
        if self.device.startswith("cuda"):
            torch.cuda.synchronize()
        metrics["t_edge_ms"] = (time.perf_counter() - t0) * 1000.0

        # Stage 2: Feature Map Quantization
        t0 = time.perf_counter()
        quantized_payload, scales = FeatureMapQuantizer.quantize(edge_features, dtype=self.dtype)
        if self.device.startswith("cuda"):
            torch.cuda.synchronize()
        metrics["t_quant_ms"] = (time.perf_counter() - t0) * 1000.0

        # Stage 3: Packet Serialization (Wire Framing)
        t0 = time.perf_counter()
        timestamp_ms = int(time.time() * 1000)
        packet_bytes = AegisPacketProtocol.serialize(
            frame_id=frame_id,
            timestamp_ms=timestamp_ms,
            split_mode=self.split_tag,
            dtype=self.dtype,
            feature_data=quantized_payload,
            scales=scales,
        )
        metrics["t_serialize_ms"] = (time.perf_counter() - t0) * 1000.0

        # Wire Payload Metrics in explicit IEC binary units
        wire_size_bytes = len(packet_bytes)
        metrics["wire_size_bytes"] = wire_size_bytes
        metrics["wire_size_kib"] = wire_size_bytes / 1024.0
        metrics["wire_size_mib"] = wire_size_bytes / (1024.0 * 1024.0)

        # Baseline uncompressed FP32 raw feature size
        if isinstance(edge_features, torch.Tensor):
            raw_elem_count = edge_features.numel()
        else:
            raw_elem_count = sum(t.numel() for t in edge_features.values())
        raw_fp32_bytes = raw_elem_count * 4
        metrics["compression_ratio"] = raw_fp32_bytes / max(wire_size_bytes, 1)

        # Stage 4: Packet Deserialization & CRC32 Validation
        t0 = time.perf_counter()
        deserialized_packet = AegisPacketProtocol.deserialize(packet_bytes, device=self.device)
        metrics["t_deserialize_ms"] = (time.perf_counter() - t0) * 1000.0

        # Stage 5: Cloud Dequantization
        t0 = time.perf_counter()
        dequantized_features = FeatureMapQuantizer.dequantize(
            quantized_data=deserialized_packet["reconstructed_data"],
            scales=deserialized_packet["scales"],
            dtype=self.dtype,
            device=self.device,
        )
        if self.device.startswith("cuda"):
            torch.cuda.synchronize()
        metrics["t_dequant_ms"] = (time.perf_counter() - t0) * 1000.0

        # Stage 6: Cloud Submodel Inference
        t0 = time.perf_counter()
        with torch.no_grad():
            cloud_raw_outputs = self.cloud_submodel(dequantized_features)
        if self.device.startswith("cuda"):
            torch.cuda.synchronize()
        metrics["t_cloud_ms"] = (time.perf_counter() - t0) * 1000.0

        # Stage 7: Direct NMS Post-Processing on Reconstructed Cloud Outputs
        t0 = time.perf_counter()
        raw_preds = cloud_raw_outputs[0] if isinstance(cloud_raw_outputs, (list, tuple)) else cloud_raw_outputs
        nms_results = nms.non_max_suppression(
            raw_preds,
            conf_thres=self.conf_threshold,
            iou_thres=self.iou_threshold,
        )
        if self.device.startswith("cuda"):
            torch.cuda.synchronize()
        metrics["t_nms_ms"] = (time.perf_counter() - t0) * 1000.0

        # End-to-End Computational Latency (Excluding wireless channel transmission)
        metrics["t_e2e_compute_ms"] = (
            metrics["t_edge_ms"]
            + metrics["t_quant_ms"]
            + metrics["t_serialize_ms"]
            + metrics["t_deserialize_ms"]
            + metrics["t_dequant_ms"]
            + metrics["t_cloud_ms"]
            + metrics["t_nms_ms"]
        )

        # Theoretical Channel Transmission Times across Bandwidths
        wire_bits = wire_size_bytes * 8.0
        for bw_mbps, bw_bps in BANDWIDTH_SCENARIOS.items():
            tx_time_ms = (wire_bits / bw_bps) * 1000.0
            metrics[f"tx_{bw_mbps}mbps_ms"] = tx_time_ms

        return nms_results, metrics
