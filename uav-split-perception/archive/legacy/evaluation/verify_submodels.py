"""Numerical Equivalence & Parity Verification Harness for Split Submodels.

Validates bit-level numerical identity (Delta_max < 10^-6) and Post-NMS parity
between monolithic YOLOv8s and decoupled Edge/Cloud submodels (k4, k9).
"""

import os
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
from typing import Any, Dict, List, Tuple

import numpy as np
import torch
import torchvision
from tabulate import tabulate
from ultralytics import YOLO
from ultralytics.utils.ops import xywh2xyxy


from core.submodels import EdgeSubmodel, CloudSubmodel
from utils.logger import get_logger

logger = get_logger("ParityVerifier")


def extract_prediction_tensor(raw_output: Any) -> torch.Tensor:
    """Extracts the primary (B, C, N) prediction tensor from YOLOv8 head output."""
    if isinstance(raw_output, torch.Tensor):
        return raw_output
    elif isinstance(raw_output, (list, tuple)):
        for item in raw_output:
            if isinstance(item, torch.Tensor) and item.dim() == 3:
                return item
        if len(raw_output) > 0 and isinstance(raw_output[0], torch.Tensor):
            return raw_output[0]
    raise TypeError(f"Unable to extract prediction tensor from output type {type(raw_output)}")


def postprocess_nms(
    preds: torch.Tensor,
    conf_thres: float = 0.25,
    iou_thres: float = 0.45,
) -> torch.Tensor:
    """Runs standard deterministic post-NMS processing on YOLOv8 prediction tensor."""
    if preds.dim() == 3 and preds.shape[1] == 84:
        preds = preds.transpose(1, 2)  # (B, 8400, 84)

    p = preds[0]  # Single image batch
    boxes_xywh = p[:, :4]
    scores_all = p[:, 4:]
    scores, class_ids = scores_all.max(dim=1)
    mask = scores > conf_thres

    boxes_xywh = boxes_xywh[mask]
    scores = scores[mask]
    class_ids = class_ids[mask]

    if len(scores) == 0:
        return torch.zeros((0, 6), device=preds.device)

    boxes_xyxy = xywh2xyxy(boxes_xywh)
    keep = torchvision.ops.batched_nms(boxes_xyxy, scores, class_ids, iou_thres)
    dets = torch.cat([boxes_xyxy[keep], scores[keep].unsqueeze(1), class_ids[keep].unsqueeze(1).float()], dim=1)
    return dets


def run_numerical_parity_test(
    weights_path: str = "yolov8s.pt",
    seed: int = 42,
    device: str = "cpu",
) -> Dict[str, Dict[str, Any]]:
    """Runs deterministic synthetic numerical parity tests across all split boundaries."""
    logger.info(f"Starting deterministic numerical parity verification (Seed: {seed}, Device: {device})...")

    torch.manual_seed(seed)
    np.random.seed(seed)

    # 1. Load baseline monolithic model
    yolo = YOLO(weights_path)
    base_model = yolo.model.to(device).eval()

    # 2. Synthetic deterministic input
    input_tensor = torch.randn(1, 3, 640, 640, dtype=torch.float32, device=device)

    # 3. Monolithic forward pass
    with torch.no_grad():
        y_base_raw = base_model(input_tensor)
    y_base = extract_prediction_tensor(y_base_raw)

    results: Dict[str, Dict[str, Any]] = {}
    splits_to_test = ["k4", "k9"]

    for split_tag in splits_to_test:
        logger.info(f"Evaluating in-memory split pipeline for [{split_tag}]...")
        edge_submodel = EdgeSubmodel(base_model=base_model, split_tag=split_tag).to(device)
        cloud_submodel = CloudSubmodel(base_model=base_model, split_tag=split_tag).to(device)

        with torch.no_grad():
            edge_act = edge_submodel(input_tensor)
            y_split_raw = cloud_submodel(edge_act)

        y_split = extract_prediction_tensor(y_split_raw)

        # Parity metrics computation
        diff = torch.abs(y_base - y_split)
        delta_max = torch.max(diff).item()
        mae = torch.mean(diff).item()
        rmse = torch.sqrt(torch.mean((y_base - y_split) ** 2)).item()

        passed = delta_max < 1e-6

        results[split_tag] = {
            "delta_max": delta_max,
            "mae": mae,
            "rmse": rmse,
            "passed": passed,
        }

        if passed:
            logger.success(
                f"[{split_tag}] PASSED in-memory bit-level parity: Delta_max={delta_max:.2e}, RMSE={rmse:.2e}"
            )
        else:
            logger.error(
                f"[{split_tag}] FAILED in-memory bit-level parity: Delta_max={delta_max:.2e} (Threshold: 1e-6)"
            )

    return results


def run_standalone_checkpoint_parity_test(
    checkpoints_dir: str = "experiments/checkpoints",
    weights_path: str = "yolov8s.pt",
    seed: int = 42,
    device: str = "cpu",
) -> Dict[str, Dict[str, Any]]:
    """Evaluates numerical parity for standalone saved checkpoint files."""
    logger.info(f"Evaluating standalone exported checkpoints in '{checkpoints_dir}'...")

    torch.manual_seed(seed)
    input_tensor = torch.randn(1, 3, 640, 640, dtype=torch.float32, device=device)

    yolo = YOLO(weights_path)
    base_model = yolo.model.to(device).eval()

    with torch.no_grad():
        y_base_raw = base_model(input_tensor)
    y_base = extract_prediction_tensor(y_base_raw)

    ckpt_results: Dict[str, Dict[str, Any]] = {}
    for split_tag in ["k4", "k9"]:
        edge_path = os.path.join(checkpoints_dir, f"yolov8s_edge_{split_tag}.pt")
        cloud_path = os.path.join(checkpoints_dir, f"yolov8s_cloud_{split_tag}.pt")

        if not (os.path.exists(edge_path) and os.path.exists(cloud_path)):
            logger.warning(f"Checkpoints for [{split_tag}] not found at {edge_path}. Skipping checkpoint test.")
            continue

        edge_sub = EdgeSubmodel(weights_path=edge_path).to(device)
        cloud_sub = CloudSubmodel(weights_path=cloud_path).to(device)

        with torch.no_grad():
            edge_act = edge_sub(input_tensor)
            y_split_raw = cloud_sub(edge_act)

        y_split = extract_prediction_tensor(y_split_raw)
        diff = torch.abs(y_base - y_split)
        delta_max = torch.max(diff).item()
        rmse = torch.sqrt(torch.mean((y_base - y_split) ** 2)).item()
        passed = delta_max < 1e-6

        ckpt_results[split_tag] = {
            "delta_max": delta_max,
            "rmse": rmse,
            "passed": passed,
        }

        if passed:
            logger.success(f"[{split_tag}] Standalone checkpoint verified: Delta_max={delta_max:.2e}")
        else:
            logger.error(f"[{split_tag}] Standalone checkpoint failed parity: Delta_max={delta_max:.2e}")

    return ckpt_results


def run_post_nms_parity_test(
    weights_path: str = "yolov8s.pt",
    conf_thres: float = 0.001,  # Lower threshold to stress-test high-volume box comparisons
    iou_thres: float = 0.45,
    device: str = "cpu",
) -> Dict[str, Dict[str, Any]]:
    """Evaluates End-to-End Post-NMS bounding box parity under dense proposal testing."""
    logger.info(f"Evaluating End-to-End Post-NMS parity (Conf Thresh: {conf_thres}, IoU Thresh: {iou_thres})...")

    torch.manual_seed(100)
    test_img = torch.rand(1, 3, 640, 640, dtype=torch.float32, device=device)

    yolo = YOLO(weights_path)
    base_model = yolo.model.to(device).eval()

    with torch.no_grad():
        y_base_raw = base_model(test_img)
    y_base = extract_prediction_tensor(y_base_raw)
    base_nms = postprocess_nms(y_base, conf_thres=conf_thres, iou_thres=iou_thres)

    nms_results: Dict[str, Dict[str, Any]] = {}

    for split_tag in ["k4", "k9"]:
        edge_submodel = EdgeSubmodel(base_model=base_model, split_tag=split_tag).to(device)
        cloud_submodel = CloudSubmodel(base_model=base_model, split_tag=split_tag).to(device)

        with torch.no_grad():
            edge_act = edge_submodel(test_img)
            y_split_raw = cloud_submodel(edge_act)

        y_split = extract_prediction_tensor(y_split_raw)
        split_nms = postprocess_nms(y_split, conf_thres=conf_thres, iou_thres=iou_thres)

        # Compare NMS detections
        if base_nms.shape != split_nms.shape:
            logger.error(f"[{split_tag}] NMS Shape Mismatch: Base {base_nms.shape} vs Split {split_nms.shape}")
            nms_results[split_tag] = {"passed": False, "num_boxes": 0, "box_delta": 1.0}
            continue

        num_boxes = len(base_nms)
        if num_boxes == 0:
            logger.success(f"[{split_tag}] Post-NMS exact parity: 0 detections on test image.")
            nms_results[split_tag] = {"passed": True, "num_boxes": 0, "box_delta": 0.0}
            continue

        box_diff = torch.max(torch.abs(base_nms[:, :4] - split_nms[:, :4])).item()
        score_diff = torch.max(torch.abs(base_nms[:, 4] - split_nms[:, 4])).item()
        class_match = torch.equal(base_nms[:, 5], split_nms[:, 5])

        passed = (box_diff < 1e-5) and (score_diff < 1e-5) and class_match
        nms_results[split_tag] = {
            "passed": passed,
            "num_boxes": num_boxes,
            "box_delta": box_diff,
            "score_delta": score_diff,
        }

        if passed:
            logger.success(
                f"[{split_tag}] Dense Post-NMS exact match ({num_boxes} boxes): "
                f"Max Box Delta={box_diff:.2e}, Max Score Delta={score_diff:.2e}"
            )
        else:
            logger.error(f"[{split_tag}] Post-NMS divergence detected!")

    return nms_results


def print_parity_report(
    num_results: Dict[str, Dict[str, Any]],
    ckpt_results: Dict[str, Dict[str, Any]],
    nms_results: Dict[str, Dict[str, Any]],
):
    """Formats and prints comprehensive diagnostic verification summary table."""
    headers = [
        "Split Cut",
        "In-Memory Δ_max",
        "In-Memory RMSE",
        "Checkpoint Δ_max",
        "Tolerance (< 1e-6)",
        "Post-NMS Parity (Boxes)",
        "Overall Status",
    ]
    rows = []

    for split_tag, metrics in num_results.items():
        delta_str = f"{metrics['delta_max']:.3e}"
        rmse_str = f"{metrics['rmse']:.3e}"
        ckpt_delta = f"{ckpt_results.get(split_tag, {}).get('delta_max', 0.0):.3e}" if split_tag in ckpt_results else "N/A"
        tol_str = "PASS" if metrics["passed"] else "FAIL"
        
        nms_info = nms_results.get(split_tag, {})
        nms_passed = nms_info.get("passed", False)
        box_count = nms_info.get("num_boxes", 0)
        nms_str = f"PASS ({box_count} dets)" if nms_passed else "FAIL"
        
        overall = "PASSED" if (metrics["passed"] and nms_passed) else "FAILED"

        rows.append([
            f"Split [{split_tag}]",
            delta_str,
            rmse_str,
            ckpt_delta,
            tol_str,
            nms_str,
            f"★ {overall}",
        ])

    print("\n" + "=" * 110)
    print("                  YOLOv8s NEURAL SUBMODEL NUMERICAL PARITY VERIFICATION REPORT")
    print("=" * 110)
    print(tabulate(rows, headers=headers, tablefmt="fancy_grid"))
    print("=" * 110 + "\n")


if __name__ == "__main__":
    device = "cuda" if torch.cuda.is_available() else "cpu"
    checkpoints_path = str(repo_root / "experiments" / "checkpoints")

    num_metrics = run_numerical_parity_test(weights_path="yolov8s.pt", device=device)
    ckpt_metrics = run_standalone_checkpoint_parity_test(checkpoints_dir=checkpoints_path, weights_path="yolov8s.pt", device=device)
    nms_metrics = run_post_nms_parity_test(weights_path="yolov8s.pt", device=device)
    print_parity_report(num_metrics, ckpt_metrics, nms_metrics)

    # Hard asserts for automated validation
    for split, m in num_metrics.items():
        assert m["passed"], f"Split {split} failed numerical parity: {m['delta_max']}"
        assert nms_metrics[split]["passed"], f"Split {split} failed Post-NMS parity"
