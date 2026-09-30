import pytest
import torch

from core.dynamic_submodels import (DynamicCloudSubmodel, DynamicEdgeSubmodel, analyze_split_dependencies,
                                    load_submodel, save_submodel_checkpoint)
from core.submodels import CloudSubmodel, DynamicCloudDispatcher, EdgeSubmodel


def _ref(model, x):
    with torch.no_grad():
        out = model(x)
    return out[0] if isinstance(out, (list, tuple)) else out


def test_live_sets_match_yolov8s_topology(yolo_model):
    expected = {2: [2], 4: [4], 5: [4, 5], 7: [4, 6, 7], 9: [4, 6, 9], 12: [4, 9, 12], 15: [9, 12, 15], 18: [9, 15, 18]}
    for k, live in expected.items():
        assert analyze_split_dependencies(yolo_model, k)[1] == live


def test_every_cut_reproduces_the_monolithic_output_exactly(yolo_model, image_tensor):
    ref = _ref(yolo_model, image_tensor)
    for k in range(0, 22):
        edge, cloud = DynamicEdgeSubmodel(yolo_model, k), DynamicCloudSubmodel(yolo_model, k)
        with torch.no_grad():
            out = cloud(edge(image_tensor))[0]
        assert torch.equal(out, ref), f"cut {k}"


def test_cloud_rejects_wrong_inputs(yolo_model):
    cloud = DynamicCloudSubmodel(yolo_model, 9)
    with pytest.raises(ValueError):
        cloud(torch.zeros(1, 512, 20, 20))
    with pytest.raises(ValueError):
        cloud({"4": torch.zeros(1, 128, 80, 80)})
    with pytest.raises(ValueError):
        DynamicEdgeSubmodel(yolo_model, 40)


def test_dispatcher_shares_weights_and_validates_codes(yolo_model, image_tensor):
    d = DynamicCloudDispatcher(yolo_model, candidate_cuts=[4], device="cpu")
    n = sum(p.numel() for p in d.parameters())
    for code in (2, 5, 9, "k12", "15"):
        d.get_branch(code)
    assert sum(p.numel() for p in d.parameters()) == n  # new branches add no parameters
    for bad in ("k-3", "kx", 100, -1, 3.5):
        with pytest.raises((ValueError, TypeError)):
            d.get_branch(bad)
    assert d.get_branch("full") is None and d.get_branch(22) is None
    edge = DynamicEdgeSubmodel(yolo_model, 9)
    with torch.no_grad():
        out = d(edge(image_tensor), split_code=9)[0]
    assert torch.equal(out, _ref(yolo_model, image_tensor))


class _Op(torch.nn.Module):
    def __init__(self, i, f, fn):
        super().__init__()
        self.i, self.f, self.fn = i, f, fn

    def forward(self, x):
        return self.fn(x)


@pytest.mark.parametrize("cut", [0, 1])
def test_cloud_resolves_relative_sources_below_minus_one(cut):
    """Layer 2 reads layer 0 as f = -2; the cloud must resolve it relative to layer 2."""
    seq = torch.nn.Sequential(_Op(0, -1, lambda x: 2 * x), _Op(1, -1, lambda x: x + 1),
                              _Op(2, [-1, -2], lambda xs: xs[0] * xs[1]))
    x = torch.rand(1, 3, 4, 4)
    y0 = 2 * x
    ref = (y0 + 1) * y0
    out = DynamicCloudSubmodel(seq, cut)(DynamicEdgeSubmodel(seq, cut)(x))
    assert torch.equal(out, ref)


def test_dispatcher_empty_candidates_and_bool_codes(yolo_model):
    d = DynamicCloudDispatcher(yolo_model, candidate_cuts=[], device="cpu")
    assert len(d.branches) == 0
    with pytest.raises(TypeError):
        d.get_branch(True)


def test_standalone_checkpoints_need_no_original_weights(yolo_model, image_tensor, tmp_path):
    ref = _ref(yolo_model, image_tensor)
    for tag in ("k4", "k9"):
        e, c = tmp_path / f"e_{tag}.pt", tmp_path / f"c_{tag}.pt"
        save_submodel_checkpoint(EdgeSubmodel(yolo_model, tag), e, "edge")
        save_submodel_checkpoint(CloudSubmodel(yolo_model, tag), c, "cloud")
        with torch.no_grad():
            out = load_submodel(c)(load_submodel(e)(image_tensor))[0]
        assert torch.equal(out, ref)
        assert EdgeSubmodel(weights_path=str(e)).split_tag == tag
