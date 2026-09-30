"""Per-frame quantization of the tensors that cross a split.

Wire modes: fp32, fp16, symmetric INT8 per tensor (S = max|X| / 127) or per channel,
INT8 dequantized in fp16 (``int8_fp16_accum``), affine UINT8, and affine UINT8 after clipping
|X| at its 99.9th percentile. ``*_zstd`` modes quantize like their base mode; protocol/packet.py
applies the zstd coding.

Symmetric modes satisfy ||X - X_hat||_inf <= S / 2 (per channel: S_c / 2) in exact arithmetic
(Proposition 1 in paper/main.tex; checked by scripts/verify_math_proofs.py).
"""

import math
from typing import Any, Dict, Tuple, Union

import numpy as np
import torch

DTYPE_FP32 = "fp32"
DTYPE_FP16 = "fp16"
DTYPE_INT8 = "int8"
DTYPE_INT8_PER_TENSOR = "int8_per_tensor"
DTYPE_INT8_PER_CHANNEL = "int8_per_channel"
DTYPE_INT8_FP16_ACCUM = "int8_fp16_accum"
DTYPE_UINT8 = "uint8"
DTYPE_UINT8_CLIP = "uint8_clip"
DTYPE_INT8_ZSTD = "int8_zstd"
DTYPE_UINT8_ZSTD = "uint8_zstd"

VALID_DTYPES = {
    DTYPE_FP32,
    DTYPE_FP16,
    DTYPE_INT8,
    DTYPE_INT8_PER_TENSOR,
    DTYPE_INT8_PER_CHANNEL,
    DTYPE_INT8_FP16_ACCUM,
    DTYPE_UINT8,
    DTYPE_UINT8_CLIP,
    DTYPE_INT8_ZSTD,
    DTYPE_UINT8_ZSTD,
}

EPSILON = 1e-6


def compute_reconstruction_metrics(original: torch.Tensor, reconstructed: torch.Tensor) -> Dict[str, float]:
    """L_inf error, MSE, SQNR (dB; 120 for an exact copy) and cosine similarity."""
    orig_f = original.detach().float().flatten()
    rec_f = reconstructed.detach().float().flatten()

    diff = orig_f - rec_f
    max_abs_err = float(torch.max(torch.abs(diff)).item())
    mse = float(torch.mean(diff ** 2).item())

    orig_power = float(torch.sum(orig_f ** 2).item())
    noise_power = float(torch.sum(diff ** 2).item())
    if noise_power == 0:
        sqnr_db = 120.0
    elif orig_power > 0:
        sqnr_db = 10.0 * math.log10(orig_power / noise_power)
    else:
        sqnr_db = 0.0

    orig_norm = float(torch.norm(orig_f, 2).item())
    rec_norm = float(torch.norm(rec_f, 2).item())
    if orig_norm > 0 and rec_norm > 0:
        cos_sim = float(torch.dot(orig_f, rec_f).item() / (orig_norm * rec_norm))
    else:
        # Two all-zero tensors agree; a zero tensor against a non-zero one does not.
        cos_sim = 1.0 if orig_norm == rec_norm else 0.0

    return {
        "max_abs_error": round(max_abs_err, 6),
        "mse": round(mse, 8),
        "sqnr_db": round(sqnr_db, 2),
        "cosine_similarity": round(cos_sim, 6),
    }


class FeatureMapQuantizer:
    @classmethod
    def quantize_tensor(
        cls,
        x: torch.Tensor,
        dtype: str = DTYPE_INT8,
    ) -> Tuple[torch.Tensor, Union[float, torch.Tensor, Tuple[float, float]]]:
        """Returns (codes, scale); scale is a float, a per-channel tensor, or (scale, zero_point)."""
        if not torch.isfinite(x).all():
            raise ValueError("Input tensor contains NaN or Inf values")

        norm_dtype = dtype.lower()
        if norm_dtype == DTYPE_FP32:
            return x.to(torch.float32), 1.0

        if norm_dtype == DTYPE_FP16:
            return x.to(torch.float16), 1.0

        if norm_dtype in [DTYPE_INT8, DTYPE_INT8_PER_TENSOR, DTYPE_INT8_FP16_ACCUM, DTYPE_INT8_ZSTD]:
            max_val = float(torch.max(torch.abs(x)).item())
            # Round the scale to float32 so the value carried in the wire descriptor is
            # exactly the one used here, keeping the S/2 bound exact end-to-end.
            scale = 1.0 if max_val < EPSILON else float(np.float32(max_val / 127.0))

            # Divide by a float32 tensor: true IEEE division on every device (a Python scalar
            # divisor is turned into a reciprocal multiply on CUDA), so results are device-independent.
            # fp16 inputs are promoted, otherwise the scale would be rounded to fp16 and no longer
            # match the float32 scale on the wire.
            scaled = x.float() / torch.tensor(scale, dtype=torch.float32, device=x.device)
            q_tensor = torch.clamp(torch.round(scaled), -128, 127).to(torch.int8)
            return q_tensor, scale

        if norm_dtype == DTYPE_INT8_PER_CHANNEL:
            if x.dim() == 4:
                max_c = torch.amax(torch.abs(x), dim=(0, 2, 3), keepdim=True)  # (1, C, 1, 1)
            elif x.dim() == 3:
                max_c = torch.amax(torch.abs(x), dim=(1, 2), keepdim=True)  # (C, 1, 1)
            else:
                raise ValueError(f"Per-channel quantization needs a CHW or NCHW tensor, got {tuple(x.shape)}")

            scales_c = torch.where(max_c >= EPSILON, max_c / 127.0, torch.ones_like(max_c)).to(torch.float32)
            q_tensor = torch.clamp(torch.round(x / scales_c), -128, 127).to(torch.int8)
            return q_tensor, scales_c.reshape(-1)

        if norm_dtype in [DTYPE_UINT8, DTYPE_UINT8_CLIP, DTYPE_UINT8_ZSTD]:
            # Affine, so the short negative SiLU tail (down to about -0.28) does not waste half the codes.
            x_work = x.float()
            if norm_dtype == DTYPE_UINT8_CLIP:
                flat = torch.abs(x_work.detach()).reshape(-1)
                k = max(1, int(math.ceil(0.999 * flat.numel())))
                p999 = float(torch.kthvalue(flat.cpu() if flat.device.type == "mps" else flat, k).values.item())
                x_work = torch.clamp(x_work, -p999, p999)

            # The range always contains 0 (as in PyTorch's observers): zero is then exact, and a
            # constant tensor such as all -3.0 is still representable.
            x_min = min(float(torch.min(x_work).item()), 0.0)
            x_max = max(float(torch.max(x_work).item()), 0.0)
            val_range = x_max - x_min
            if val_range < EPSILON:
                scale = 1.0
                zero_point = 0.0
            else:
                scale = float(np.float32(val_range / 255.0))
                zero_point = float(round(-x_min / scale))

            scaled = torch.round(x_work / torch.tensor(scale, dtype=torch.float32, device=x_work.device)) + zero_point
            q_tensor = torch.clamp(scaled, 0, 255).to(torch.uint8)
            return q_tensor, (scale, zero_point)

        raise ValueError(f"Unsupported dtype: '{dtype}'. Must be one of {VALID_DTYPES}")

    @classmethod
    def dequantize_tensor(
        cls,
        q_tensor: torch.Tensor,
        scale: Union[float, torch.Tensor, Tuple[float, float], Dict[str, float]],
        dtype: str = DTYPE_INT8,
        target_dtype: torch.dtype = torch.float32,
        device: Union[str, torch.device] = "cpu",
    ) -> torch.Tensor:
        """Inverse of ``quantize_tensor``; returns ``target_dtype`` on ``device``."""
        norm_dtype = dtype.lower()
        t = q_tensor.to(device=device)

        if norm_dtype == DTYPE_INT8_FP16_ACCUM:
            # Rescale in half precision (as a half-precision cloud would), then hand the
            # result back in the dtype the consuming model expects.
            scale_val = float(scale) if not isinstance(scale, torch.Tensor) else float(scale.item())
            return (t.to(torch.float16) * torch.tensor(scale_val, dtype=torch.float16, device=t.device)).to(target_dtype)

        if norm_dtype == DTYPE_FP32:
            return t.to(target_dtype)

        if norm_dtype == DTYPE_FP16:
            return t.to(target_dtype)

        if norm_dtype in [DTYPE_INT8, DTYPE_INT8_PER_TENSOR, DTYPE_INT8_ZSTD]:
            scale_val = float(scale) if not isinstance(scale, torch.Tensor) else float(scale.item())
            return (t.to(target_dtype) * scale_val)

        if norm_dtype == DTYPE_INT8_PER_CHANNEL:
            if isinstance(scale, (int, float)):
                s_t = torch.tensor([scale], dtype=target_dtype, device=device).view(1, 1, 1, 1)
            else:
                s = torch.as_tensor(scale).to(device=device, dtype=target_dtype).reshape(-1)
                s_t = s.view(-1, 1, 1) if t.dim() == 3 else s.view(1, -1, 1, 1)
            return (t.to(target_dtype) * s_t)

        if norm_dtype in [DTYPE_UINT8, DTYPE_UINT8_CLIP, DTYPE_UINT8_ZSTD]:
            if isinstance(scale, (tuple, list)):
                s_val = float(scale[0])
                z_val = float(scale[1])
            elif isinstance(scale, dict) and "zero_point" in scale:
                s_val = float(scale["scale"])
                z_val = float(scale["zero_point"])
            else:
                s_val = float(scale) if not isinstance(scale, torch.Tensor) else float(scale.item())
                z_val = 0.0
            return (t.to(target_dtype) - z_val) * s_val

        raise ValueError(f"Unsupported dtype: '{dtype}'. Must be one of {sorted(VALID_DTYPES)}")

    @classmethod
    def quantize(
        cls,
        data: Union[torch.Tensor, Dict[str, torch.Tensor]],
        dtype: str = DTYPE_INT8,
    ) -> Tuple[Union[torch.Tensor, Dict[str, torch.Tensor]], Union[float, torch.Tensor, Tuple[float, float], Dict[str, Any]]]:
        """Quantizes one tensor, or each tensor of a {layer: tensor} live set."""
        if isinstance(data, torch.Tensor):
            return cls.quantize_tensor(data, dtype=dtype)
        elif isinstance(data, dict):
            q_dict = {}
            scale_dict = {}
            for k, tensor in data.items():
                q_t, s = cls.quantize_tensor(tensor, dtype=dtype)
                q_dict[k] = q_t
                scale_dict[k] = s
            return q_dict, scale_dict
        else:
            raise TypeError(f"Unsupported data type: {type(data)}")

    @classmethod
    def dequantize(
        cls,
        quantized_data: Union[torch.Tensor, Dict[str, torch.Tensor]],
        scales: Union[float, torch.Tensor, Tuple[float, float], Dict[str, Any]],
        dtype: str = DTYPE_INT8,
        target_dtype: torch.dtype = torch.float32,
        device: Union[str, torch.device] = "cpu",
    ) -> Union[torch.Tensor, Dict[str, torch.Tensor]]:
        """Dequantizes one tensor, or each tensor of a live set (``scales`` keyed alike)."""
        if isinstance(quantized_data, torch.Tensor):
            return cls.dequantize_tensor(quantized_data, scale=scales, dtype=dtype, target_dtype=target_dtype, device=device)
        elif isinstance(quantized_data, dict):
            deq_dict = {}
            for k, q_t in quantized_data.items():
                s = scales[k] if isinstance(scales, dict) else scales
                deq_dict[k] = cls.dequantize_tensor(q_t, scale=s, dtype=dtype, target_dtype=target_dtype, device=device)
            return deq_dict
        else:
            raise TypeError(f"Unsupported quantized_data type: {type(quantized_data)}")
