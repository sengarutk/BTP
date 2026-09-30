"""Symmetric per-tensor n-bit quantization (2 <= n <= 8) and its lossless wire size.

Used by the generalization study to ask how far the bit width must drop before a split payload
becomes smaller than an image codec. For n = 8 this is exactly the INT8 mode of
``FeatureMapQuantizer`` (S = max|X| / 127, float32 scale, division by a float32 tensor).

    S = max|X| / (2^(n-1) - 1),  q = clamp(round(X / S), -(2^(n-1)), 2^(n-1) - 1),  X_hat = q * S
    ||X - X_hat||_inf <= S / 2

Wire size: codes are either kept one per byte or bit-packed (n bits each), then zstd-compressed;
the smaller of the two is reported (a real sender would pick the better layout), plus a
16-byte descriptor per tensor. The wire protocol in protocol/packet.py carries 8-bit codes only,
so sizes for n < 8 are computed here rather than by serializing packets.
"""

from typing import Dict, Iterable, Tuple

import numpy as np
import torch
import zstandard as zstd

DESCRIPTOR_BYTES = 16
HEADER_BYTES = 16 + 4  # packet header + CRC32


def qmax(bits: int) -> int:
    if not 2 <= bits <= 8:
        raise ValueError(f"bits must be in [2, 8], got {bits}")
    return (1 << (bits - 1)) - 1


def quantize(x: torch.Tensor, bits: int) -> Tuple[torch.Tensor, float]:
    m = qmax(bits)
    max_val = float(torch.max(torch.abs(x)).item())
    scale = 1.0 if max_val < 1e-6 else float(np.float32(max_val / m))
    q = torch.clamp(torch.round(x.float() / torch.tensor(scale, dtype=torch.float32, device=x.device)), -m - 1, m)
    return q.to(torch.int8), scale


def dequantize(q: torch.Tensor, scale: float, dtype: torch.dtype = torch.float32) -> torch.Tensor:
    return q.to(dtype) * torch.tensor(scale, dtype=dtype, device=q.device)


def roundtrip(x: torch.Tensor, bits: int) -> torch.Tensor:
    q, s = quantize(x, bits)
    return dequantize(q, s, x.dtype)


def pack(q: np.ndarray, bits: int) -> bytes:
    """Bit-packs signed codes (offset to unsigned) into ceil(n * len / 8) bytes."""
    u = (q.astype(np.int16) + (1 << (bits - 1))).astype(np.uint8).ravel()
    bit_planes = np.unpackbits(u[:, None], axis=1)[:, 8 - bits:]
    return np.packbits(bit_planes.ravel()).tobytes()


def unpack(buf: bytes, bits: int, n: int) -> np.ndarray:
    planes = np.unpackbits(np.frombuffer(buf, dtype=np.uint8))[: n * bits].reshape(n, bits)
    full = np.concatenate([np.zeros((n, 8 - bits), dtype=np.uint8), planes], axis=1)
    return (np.packbits(full, axis=1).ravel().astype(np.int16) - (1 << (bits - 1))).astype(np.int8)


def wire_bytes(tensors: Iterable[torch.Tensor], bits: int, zstd_level: int = 1) -> Dict[str, int]:
    """Bytes on the wire for the given activations at n bits: raw packed, and best lossless coding."""
    cctx = zstd.ZstdCompressor(level=zstd_level)
    raw = coded = HEADER_BYTES
    for t in tensors:
        q, _ = quantize(t, bits)
        codes = q.cpu().numpy()
        packed = pack(codes, bits) if bits < 8 else codes.tobytes()
        raw += DESCRIPTOR_BYTES + len(packed)
        coded += DESCRIPTOR_BYTES + min(len(cctx.compress(packed)), len(cctx.compress(codes.tobytes())))
    return {"raw": raw, "zstd": coded}
