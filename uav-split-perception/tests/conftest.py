from pathlib import Path

import pytest
import torch

REPO_ROOT = Path(__file__).resolve().parent.parent
WEIGHTS = REPO_ROOT / "yolov8s.pt"


@pytest.fixture(scope="session")
def yolo_model():
    if not WEIGHTS.exists():
        pytest.skip("yolov8s.pt not present")
    from ultralytics import YOLO

    return YOLO(str(WEIGHTS)).model.eval()


@pytest.fixture(scope="session")
def image_tensor():
    torch.manual_seed(0)
    return torch.rand(1, 3, 640, 640)
