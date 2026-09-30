import pytest
import torch
from ultralytics import YOLO

from core.submodels import DynamicCloudDispatcher
from core.dynamic_submodels import DynamicEdgeSubmodel


@pytest.fixture(scope="module")
def base_yolo_model():
    """Load base YOLOv8s model once for module tests."""
    yolo = YOLO("yolov8s.pt")
    model = yolo.model.eval()
    return model


@pytest.mark.parametrize("k", [2, 4, 9, 12])
def test_dynamic_cloud_dispatcher_routing(base_yolo_model, k):
    """Test DynamicCloudDispatcher routing across candidate cuts {k2, k4, k9, k12}.

    Assert output tensor shapes match [1, 84, 8400] without shape errors.
    """
    dispatcher = DynamicCloudDispatcher(
        base_model=base_yolo_model,
        candidate_cuts=[2, 4, 9, 12],
        device="cpu",
    )

    edge_sub = DynamicEdgeSubmodel(base_model=base_yolo_model, cut_layer=k).eval()
    dummy_input = torch.randn(1, 3, 640, 640)

    with torch.no_grad():
        edge_features = edge_sub(dummy_input)
        cloud_output = dispatcher(edge_features, split_code=k)

    if isinstance(cloud_output, (list, tuple)):
        pred_tensor = cloud_output[0]
    else:
        pred_tensor = cloud_output

    assert pred_tensor is not None
    assert pred_tensor.shape == (1, 84, 8400), (
        f"Cut k={k}: expected shape (1, 84, 8400), got {pred_tensor.shape}"
    )
