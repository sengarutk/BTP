import numpy as np
import pytest
import torch

from quantization.quantizer import FeatureMapQuantizer as Q

EPS32 = float(np.finfo(np.float32).eps)


def _fp_slack(x: torch.Tensor) -> float:
    """Float32 evaluation of X_hat = q*S and X - X_hat adds at most ~1 ulp of max|X| (2 roundings)."""
    return 2 * EPS32 * float(x.abs().max())


def _distributions(n=60, seed=0):
    g = torch.Generator().manual_seed(seed)
    rng = np.random.default_rng(seed)
    for i in range(n):
        shape = (1, int(rng.integers(4, 48)), int(rng.integers(4, 32)), int(rng.integers(4, 32)))
        kind = i % 4
        if kind == 0:
            x = torch.randn(shape, generator=g) * float(rng.uniform(0.01, 50))
        elif kind == 1:
            x = torch.distributions.StudentT(3.0).sample(shape)
        elif kind == 2:
            x = torch.nn.functional.silu(torch.randn(shape, generator=g) * 4)  # YOLO-like activations
        else:
            x = torch.rand(shape, generator=g) * 1e-3
        yield x


def test_per_tensor_bound_theorem():
    """||X - X_hat||_inf <= S/2 in exact arithmetic; float32 evaluation adds <= 2 eps max|X|."""
    for x in _distributions():
        q, s = Q.quantize_tensor(x, "int8")
        err = (x - Q.dequantize_tensor(q, s, "int8")).abs().max().item()
        assert err <= s / 2 + _fp_slack(x)


def test_per_channel_bound_theorem():
    for x in _distributions():
        q, s = Q.quantize_tensor(x, "int8_per_channel")
        err = (x - Q.dequantize_tensor(q, s, "int8_per_channel")).abs().amax(dim=(0, 2, 3))
        assert torch.all(err <= s / 2 + _fp_slack(x))


def test_uint8_bound_without_clipping():
    for x in _distributions():
        q, (s, z) = Q.quantize_tensor(x, "uint8")
        assert q.dtype == torch.uint8
        err = (x - Q.dequantize_tensor(q, (s, z), "uint8")).abs().max().item()
        assert err <= s / 2 + 2 * EPS32 * (float(x.abs().max()) + abs(z) * s)


@pytest.mark.parametrize("fill", [-3.0, 0.5, 300.0])
def test_uint8_constant_tensor_round_trips(fill):
    x = torch.full((1, 2, 4, 4), fill)
    q, (s, z) = Q.quantize_tensor(x, "uint8")
    err = (x - Q.dequantize_tensor(q, (s, z), "uint8")).abs().max().item()
    assert err <= s / 2 + 2 * EPS32 * abs(fill)


@pytest.mark.parametrize("lo, hi", [(2.0, 5.0), (-7.0, -1.0)])
def test_uint8_one_signed_tensors_keep_zero_exact(lo, hi):
    x = torch.linspace(lo, hi, 64).reshape(1, 1, 8, 8)
    q, (s, z) = Q.quantize_tensor(x, "uint8")
    assert 0 <= z <= 255
    assert Q.dequantize_tensor(torch.tensor([z], dtype=torch.uint8), (s, z), "uint8").item() == 0.0
    err = (x - Q.dequantize_tensor(q, (s, z), "uint8")).abs().max().item()
    assert err <= s / 2 + 2 * EPS32 * (float(x.abs().max()) + abs(z) * s)


@pytest.mark.parametrize("mode", ["int8", "uint8"])
def test_fp16_input_is_quantized_with_the_float32_wire_scale(mode):
    """The scale sent on the wire is float32; fp16 inputs must be divided by exactly that value."""
    x = (torch.randn(1, 16, 20, 20) * 7).half()
    q16, s16 = Q.quantize_tensor(x, mode)
    q32, s32 = Q.quantize_tensor(x.float(), mode)
    assert s16 == s32 and torch.equal(q16, q32)


def test_reconstruction_metrics_handle_zero_tensors():
    from quantization.quantizer import compute_reconstruction_metrics as metrics

    z = torch.zeros(10)
    assert metrics(z, z)["cosine_similarity"] == 1.0 and metrics(z, z)["sqnr_db"] == 120.0
    assert metrics(z, torch.ones(10))["cosine_similarity"] == 0.0


def test_scale_is_float32_exact():
    q, s = Q.quantize_tensor(torch.randn(1, 8, 8, 8) * 3.3, "int8")
    assert s == float(np.float32(s))


def test_edge_cases():
    q, s = Q.quantize_tensor(torch.zeros(1, 2, 3, 3), "int8")
    assert s == 1.0 and torch.all(q == 0)
    x = torch.randn(1, 2, 3, 3)
    x[0, 0, 0, 0] = float("nan")
    with pytest.raises(ValueError):
        Q.quantize_tensor(x, "int8")
    with pytest.raises(ValueError):
        Q.quantize_tensor(torch.randn(1, 2, 3, 3), "int4")
    with pytest.raises(ValueError):
        Q.dequantize_tensor(torch.zeros(1, dtype=torch.int8), 1.0, "int4")


def test_per_channel_keeps_3d_shape():
    x = torch.randn(8, 5, 5)
    q, s = Q.quantize_tensor(x, "int8_per_channel")
    assert q.shape == x.shape and s.shape == (8,)
    assert Q.dequantize_tensor(q, s, "int8_per_channel").shape == x.shape


def test_fp16_accumulation_mode_returns_model_dtype():
    q, s = Q.quantize_tensor(torch.randn(1, 4, 4, 4), "int8_fp16_accum")
    assert Q.dequantize_tensor(q, s, "int8_fp16_accum").dtype == torch.float32


@pytest.mark.skipif(not torch.cuda.is_available(), reason="needs CUDA")
@pytest.mark.parametrize("mode", ["int8", "int8_per_channel", "uint8"])
def test_quantization_is_device_independent(mode):
    for x in _distributions(20, seed=3):
        qc, sc = Q.quantize_tensor(x, mode)
        qg, sg = Q.quantize_tensor(x.cuda(), mode)
        assert torch.equal(qc, qg.cpu())
