"""The learned-bottleneck baseline (evaluation/learned_bottleneck.py): code shapes, the uint8 quantizer and its
straight-through gradient, configuration names, and the warm-up drop of the validator's extra forward pass."""
import argparse

import pytest
import torch

L = pytest.importorskip("evaluation.learned_bottleneck")


def test_quantizer_roundtrip_and_straight_through():
    z = torch.randn(2, 8, 10, 6, requires_grad=True)
    zq, q, lo, sc = L.Bottleneck.quantize(z)
    assert q.dtype == torch.uint8 and q.shape == z.shape
    assert float((zq - z).detach().abs().max()) <= float(sc.detach().max()) / 2 + 1e-6      # within half a step
    zq.sum().backward()
    assert torch.allclose(z.grad, torch.ones_like(z))                     # straight-through
    per_image = [int(q[b].min()) == 0 and int(q[b].max()) == 255 for b in range(2)]
    assert all(per_image)                                                 # per-image min-max scaling


@pytest.mark.parametrize("stride,code_hw", [(2, (40, 24)), (1, (80, 48))])
def test_shapes(stride, code_hw):
    bn = L.Bottleneck(128, 16, width=32, stride=stride, dec_layers=2).eval()
    x = torch.randn(1, 128, 80, 48)
    r, q = bn(x)
    assert r.shape == x.shape and tuple(q.shape[2:]) == code_hw and q.shape[1] == 16


def test_tag_keeps_the_first_name():
    a = argparse.Namespace(cut=4, channels=8, width=64, stride=2, dec_layers=1)
    assert L.tag(a) == "k4_c8"
    a = argparse.Namespace(cut=2, channels=16, width=128, stride=1, dec_layers=2)
    assert L.tag(a) == "k2_c16_w128_s1_d2"


def test_drop_warmup():
    assert L.drop_warmup([9, 1, 2, 3], 3) == [1, 2, 3]
    assert L.drop_warmup([1, 2, 3], 3) == [1, 2, 3]
    with pytest.raises(AssertionError):
        L.drop_warmup([1, 2, 3, 4, 5], 3)
