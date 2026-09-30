"""Exports standalone edge/cloud checkpoints for the k4 and k9 splits and verifies them.

Each checkpoint stores its role, cut layer, architecture config, and weights, so it can be
reloaded with ``core.dynamic_submodels.load_submodel`` without the original yolov8s.pt.
"""

import argparse
import os
from pathlib import Path
from typing import Dict

import torch
from ultralytics import YOLO

from core.dynamic_submodels import load_submodel, save_submodel_checkpoint
from core.submodels import SPLIT_LAYER_MAP, CloudSubmodel, EdgeSubmodel
from utils.logger import get_logger

logger = get_logger("SubmodelExporter")
REPO_ROOT = Path(__file__).resolve().parent.parent


def export_submodel_weights(weights_path: str = "yolov8s.pt",
                            output_dir: str = str(REPO_ROOT / "experiments" / "checkpoints")) -> Dict[str, str]:
    os.makedirs(output_dir, exist_ok=True)
    base = YOLO(weights_path).model.eval()
    paths: Dict[str, str] = {}
    for tag in ["k4", "k9"]:
        for role, cls in (("edge", EdgeSubmodel), ("cloud", CloudSubmodel)):
            sub = cls(base_model=base, split_tag=tag)
            path = os.path.join(output_dir, f"yolov8s_{role}_{tag}.pt")
            save_submodel_checkpoint(sub, path, role=role)
            n = sum(p.numel() for p in sub.parameters())
            logger.success(f"Exported {role} [{tag}] -> {path} ({n:,} params, {os.path.getsize(path) / 2**20:.2f} MiB)")
            paths[f"{role}_{tag}"] = path

    # Verify: reload from checkpoints alone and compare with the monolithic model.
    torch.manual_seed(0)
    x = torch.rand(1, 3, 640, 640)
    with torch.no_grad():
        ref = base(x)[0]
        for tag in ["k4", "k9"]:
            edge = load_submodel(paths[f"edge_{tag}"])
            cloud = load_submodel(paths[f"cloud_{tag}"])
            out = cloud(edge(x))[0]
            diff = float((ref - out).abs().max())
            if diff != 0.0:
                raise AssertionError(f"Reloaded {tag} checkpoints differ from monolithic model (max |diff| = {diff})")
            logger.success(f"Standalone reload of [{tag}] reproduces the monolithic output exactly")
    return paths


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--weights", default="yolov8s.pt")
    ap.add_argument("--output-dir", default=str(REPO_ROOT / "experiments" / "checkpoints"))
    args = ap.parse_args()
    export_submodel_weights(args.weights, args.output_dir)
