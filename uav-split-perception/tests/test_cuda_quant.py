"""Builds the C++/CUDA quantization extension and checks bit-exact parity with the Python quantizer."""
import shutil
from pathlib import Path

import pytest
import torch

from quantization.quantizer import FeatureMapQuantizer as Q

SRC = Path(__file__).resolve().parent.parent / "deployment" / "jetson" / "cuda_quant"


def _build(cuda: bool):
    from torch.utils.cpp_extension import load

    try:
        if cuda:
            return load("aegis_cuda_quant_gpu", [str(SRC / "bindings.cpp"), str(SRC / "kernel.cu")],
                        extra_cflags=["-O3", "-DWITH_CUDA"], extra_cuda_cflags=["-O3", "-DWITH_CUDA"])
        return load("aegis_cuda_quant_cpu", [str(SRC / "bindings.cpp")], extra_cflags=["-O3"])
    except Exception as e:  # missing compiler / toolkit mismatch
        pytest.skip(f"extension build unavailable: {str(e).splitlines()[-1][:120]}")


def _tensors(device):
    torch.manual_seed(0)
    yield torch.zeros(1, 8, 8, 8, device=device)
    for i in range(20):
        yield (torch.randn(1, 64, 40, 40) * (0.01 + i)).to(device)


def _check(ext, device):
    for x in _tensors(device):
        q1, s1 = ext.quantize_int8(x)
        q2, s2 = Q.quantize_tensor(x, "int8")
        assert s1 == s2
        assert torch.equal(q1, q2)
        assert torch.equal(ext.dequantize_int8(q1, s1), Q.dequantize_tensor(q2, s2, "int8", device=device))


@pytest.mark.skipif(shutil.which("c++") is None and shutil.which("g++") is None, reason="no C++ compiler")
def test_cpu_extension_bit_exact():
    _check(_build(cuda=False), "cpu")


@pytest.mark.skipif(not torch.cuda.is_available() or shutil.which("nvcc") is None, reason="needs CUDA + nvcc")
def test_cuda_extension_bit_exact():
    _check(_build(cuda=True), "cuda")
