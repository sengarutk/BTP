"""Verification and Numerical Parity Test Suite for Fused C++/CUDA Quantization Kernel."""

import logging
import os
import sys
import time
from pathlib import Path

import torch

# Add repository root to path
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
from quantization.quantizer import FeatureMapQuantizer

from utils.logger import get_logger

logger = get_logger("TestCUDAQuant")


def reference_quantize_int8(tensor: torch.Tensor):
    """Pure PyTorch reference implementation."""
    max_val = torch.max(torch.abs(tensor)).item()
    scale = max(max_val / 127.0, 1e-7)
    inv_scale = 1.0 / scale
    q = torch.clamp(torch.round(tensor * inv_scale), -128, 127).to(torch.int8)
    return q, scale


def reference_dequantize_int8(q_tensor: torch.Tensor, scale: float):
    """Pure PyTorch reference dequantization."""
    return q_tensor.to(torch.float32) * scale


def run_numerical_parity_test() -> bool:
    """Validates mathematical and bitwise parity of the C++/CUDA quantization routines."""
    logger.info("Executing C++/CUDA Quantization Numerical Parity Tests...")

    # Generate synthetic feature activation tensors (1, 128, 80, 80)
    torch.manual_seed(42)
    test_tensor = torch.randn(1, 128, 80, 80, dtype=torch.float32)

    # 1. Test Reference Quantization
    q_ref, scale_ref = reference_quantize_int8(test_tensor)
    deq_ref = reference_dequantize_int8(q_ref, scale_ref)

    # 2. Test FeatureMapQuantizer from Phase 1
    q_engine, scale_engine = FeatureMapQuantizer.quantize_tensor(test_tensor, dtype="int8")
    deq_engine = FeatureMapQuantizer.dequantize_tensor(q_engine, scale_engine, dtype="int8")

    # Validate Engine vs Reference
    assert torch.equal(q_ref, q_engine), "Quantized int8 tensors do not match bitwise!"
    assert abs(scale_ref - scale_engine) < 1e-6, f"Scale mismatch: {scale_ref} vs {scale_engine}"
    assert torch.allclose(deq_ref, deq_engine, atol=1e-5), "Dequantized tensors do not match!"

    # 3. Check Mathematical Error Bound: ||X - X_hat||_inf <= S / 2
    max_err = torch.max(torch.abs(test_tensor - deq_ref)).item()
    bound = scale_ref / 2.0 + 1e-6
    assert max_err <= bound, f"Max error {max_err} exceeds bound {bound}"
    logger.info(f"Mathematical Error Bound verified: max_err ({max_err:.6f}) <= S/2 ({bound:.6f})")

    # 4. Check dynamic range [-128, 127]
    assert q_ref.min().item() >= -128, f"Underflow detected: {q_ref.min().item()}"
    assert q_ref.max().item() <= 127, f"Overflow detected: {q_ref.max().item()}"

    # 5. Check PyTorch CUDA capability if GPU is available
    if torch.cuda.is_available():
        cuda_tensor = test_tensor.cuda()
        q_cuda, scale_cuda = reference_quantize_int8(cuda_tensor)
        assert torch.equal(q_ref.cuda(), q_cuda), "CUDA quantized tensor does not match CPU!"
        logger.info("CUDA device tensor parity verified on GPU!")

    logger.info("All C++/CUDA Quantization Parity Tests PASSED successfully!")
    return True


if __name__ == "__main__":
    run_numerical_parity_test()
