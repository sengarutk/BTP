import numpy as np
import pytest
import torch

from core.dynamic_submodels import DynamicCloudSubmodel, DynamicEdgeSubmodel
from evaluation.detection_eval import install_split_quant_hooks, map_from_stats, paired_bootstrap
from quantization.quantizer import FeatureMapQuantizer as Q


@pytest.mark.parametrize("cut,dtype", [(4, "int8"), (5, "int8"), (9, "int8"), (12, "fp16"), (18, "uint8")])
def test_hooks_equal_real_split_pipeline(yolo_model, image_tensor, cut, dtype):
    """The accuracy hooks must reproduce edge -> quantize -> dequantize -> cloud exactly."""
    edge, cloud = DynamicEdgeSubmodel(yolo_model, cut), DynamicCloudSubmodel(yolo_model, cut)
    with torch.no_grad():
        feats = edge(image_tensor)
        q, s = Q.quantize(feats, dtype=dtype)
        expected = cloud(Q.dequantize(q, s, dtype=dtype))[0]
        handles = install_split_quant_hooks(yolo_model, cut, dtype)
        try:
            hooked = yolo_model(image_tensor)[0]
        finally:
            for h in handles:
                h.remove()
        clean = yolo_model(image_tensor)[0]
    assert torch.equal(hooked, expected)
    assert not torch.equal(hooked, clean) or dtype == "fp16"  # quantization really happened


def _fake_stats(n_img, seed, noise=0.0):
    rng = np.random.default_rng(seed)
    stats = {k: [] for k in ("tp", "conf", "pred_cls", "target_cls")}
    for _ in range(n_img):
        n = int(rng.integers(1, 6))
        stats["tp"].append(rng.random((n, 10)) < 0.7 - noise)
        stats["conf"].append(rng.random(n))
        stats["pred_cls"].append(rng.integers(0, 3, n).astype(float))
        stats["target_cls"].append(rng.integers(0, 3, n).astype(float))
    return stats


def test_paired_bootstrap_identical_configs_has_zero_interval():
    s = _fake_stats(80, 0)
    m50, m95 = map_from_stats(s)
    res = {"stats": s, "num_images": 80, "map50": m50, "map50_95": m95}
    b = paired_bootstrap(res, res, n_boot=30)
    assert b["delta_map50_95"] == 0 and b["delta_map50_95_ci_low"] == 0 and b["delta_map50_95_ci_high"] == 0
