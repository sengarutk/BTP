"""Binary wire format for split-computing feature maps (AegisPacketProtocol).

Packet layout (all fields little-endian):

    primary header   16 B   <B I Q B B B>
                            version, frame_id (u32), timestamp_ms (u64),
                            split_code, num_tensors, flags
    descriptors      16 B x num_tensors   <B B H H H f I>
                            layer_idx, dtype_code, C, H, W, scale (f32), payload_len
    payloads         sum(payload_len) bytes
    [hmac]           32 B   HMAC-SHA256 over everything before it (only if FLAG_HMAC)
    crc32             4 B   CRC32 over everything before it

Every tensor is sent with batch size 1 in NCHW layout. Per-channel INT8 payloads are
prefixed with C float32 scales; UINT8 payloads are prefixed with a float32 zero point.
The CRC detects transmission corruption only; use ``auth_key`` for tamper detection.
"""

import hashlib
import hmac
import struct
import threading
import zlib
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import torch
import zstandard as zstd


class CorruptedPacketException(ValueError):
    """Raised when a packet is truncated, corrupted, or inconsistent with its descriptors."""


# Protocol constants
PROTOCOL_VERSION = 0x01
RESERVED_BYTE = 0x00
FLAG_RAW = 0x00
FLAG_INT8_ZSTD = 0x04
FLAG_UINT8_ZSTD = 0x05
FLAG_HMAC = 0x80
SENTINEL_SPLIT_CODE = 255
MAX_DIM = 0xFFFF
MAX_TENSOR_BYTES = 256 * 1024 * 1024  # hard cap on any decompressed payload

PRIMARY_HEADER_FORMAT = "<BIQBBB"
PRIMARY_HEADER_SIZE = struct.calcsize(PRIMARY_HEADER_FORMAT)  # 16 bytes

DESCRIPTOR_FORMAT = "<BBHHHfI"
DESCRIPTOR_SIZE = struct.calcsize(DESCRIPTOR_FORMAT)  # 16 bytes

CRC_TRAILER_FORMAT = "<I"
CRC_TRAILER_SIZE = struct.calcsize(CRC_TRAILER_FORMAT)  # 4 bytes
HMAC_SIZE = 32

DTYPE_STR_TO_CODE = {
    "fp32": 0,
    "fp16": 1,
    "int8": 2,
    "int8_per_tensor": 2,
    "int8_per_channel": 3,
    "int8_fp16_accum": 4,
    "uint8": 5,
    "uint8_clip": 5,
    "int8_zstd": 6,
    "uint8_zstd": 7,
}
DTYPE_CODE_TO_STR = {
    0: "fp32",
    1: "fp16",
    2: "int8",
    3: "int8_per_channel",
    4: "int8_fp16_accum",
    5: "uint8",
    6: "int8_zstd",
    7: "uint8_zstd",
}
TORCH_DTYPE_MAP = {
    0: torch.float32,
    1: torch.float16,
    2: torch.int8,
    3: torch.int8,
    4: torch.int8,
    5: torch.uint8,
    6: torch.int8,
    7: torch.uint8,
}
DTYPE_BYTES_PER_ELEM = {0: 4, 1: 2, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1}
NUMPY_DTYPE_MAP = {
    0: np.float32,
    1: np.float16,
    2: np.int8,
    3: np.int8,
    4: np.int8,
    5: np.uint8,
    6: np.int8,
    7: np.uint8,
}
ZSTD_CODES = (6, 7)
ZERO_POINT_CODES = (5, 7)

SPLIT_STR_TO_CODE = {"k2": 2, "k4": 4, "k5": 5, "k6": 6, "k7": 7, "k9": 9, "k12": 12, "k15": 15, "k18": 18, "full": 22, "sentinel": 255}
SPLIT_CODE_TO_STR = {v: k for k, v in SPLIT_STR_TO_CODE.items()}

# zstd contexts are not thread-safe; keep one pair per thread.
_zstd_local = threading.local()


def _zstd_contexts() -> Tuple[zstd.ZstdCompressor, zstd.ZstdDecompressor]:
    if not hasattr(_zstd_local, "cctx"):
        _zstd_local.cctx = zstd.ZstdCompressor(level=1)
        _zstd_local.dctx = zstd.ZstdDecompressor()
    return _zstd_local.cctx, _zstd_local.dctx


def parse_split_mode(split_mode: Union[str, int]) -> int:
    """Parses 'k4' / 'full' / 'sentinel' / 4 into a split code in [0, 255]."""
    if isinstance(split_mode, (int, np.integer)):
        code = int(split_mode)
    else:
        s = str(split_mode).strip().lower()
        if s in SPLIT_STR_TO_CODE:
            code = SPLIT_STR_TO_CODE[s]
        elif s.startswith("k") and s[1:].isdigit():
            code = int(s[1:])
        elif s.isdigit():
            code = int(s)
        else:
            raise ValueError(f"Unrecognized split mode {split_mode!r}")
    if not 0 <= code <= 255:
        raise ValueError(f"Split code {code} outside [0, 255]")
    return code


def parse_dtype(dtype: Union[str, int]) -> int:
    """Parses a dtype name or code, rejecting anything the protocol does not define."""
    if isinstance(dtype, str):
        key = dtype.lower()
        if key not in DTYPE_STR_TO_CODE:
            raise ValueError(f"Unsupported dtype {dtype!r}; expected one of {sorted(DTYPE_STR_TO_CODE)}")
        return DTYPE_STR_TO_CODE[key]
    code = int(dtype)
    if code not in DTYPE_CODE_TO_STR:
        raise ValueError(f"Unsupported dtype code {code}")
    return code


def _scalar(value: Any, what: str) -> float:
    if isinstance(value, torch.Tensor):
        if value.numel() != 1:
            raise ValueError(f"{what} must be a scalar, got tensor with {value.numel()} elements")
        return float(value.item())
    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value)
    raise TypeError(f"{what} must be a number, got {type(value).__name__}")


def _as_nchw(tensor: torch.Tensor) -> Tuple[torch.Tensor, int, int, int]:
    t = tensor.detach().cpu().contiguous()
    if t.dim() == 3:
        t = t.unsqueeze(0)
    if t.dim() != 4:
        raise ValueError(f"Feature tensors must be CHW or NCHW, got shape {tuple(t.shape)}")
    if t.shape[0] != 1:
        raise ValueError(f"Batch size {t.shape[0]} > 1 is not supported by the wire format")
    _, c, h, w = t.shape
    if max(c, h, w) > MAX_DIM:
        raise ValueError(f"Tensor dimensions {tuple(t.shape)} exceed the 16-bit descriptor limit")
    return t, c, h, w


class AegisPacketProtocol:
    """Serializer/deserializer for split-computing feature packets."""

    @classmethod
    def make_sentinel(cls, frame_id: int, timestamp_ms: int, auth_key: Optional[bytes] = None) -> bytes:
        """Builds an end-of-stream control packet."""
        flags = FLAG_HMAC if auth_key else RESERVED_BYTE
        header = struct.pack(
            PRIMARY_HEADER_FORMAT,
            PROTOCOL_VERSION,
            int(frame_id) & 0xFFFFFFFF,
            int(timestamp_ms) & 0xFFFFFFFFFFFFFFFF,
            SENTINEL_SPLIT_CODE,
            0,
            flags,
        )
        return cls._seal(header, auth_key)

    @staticmethod
    def _seal(body: bytes, auth_key: Optional[bytes]) -> bytes:
        if auth_key:
            body = body + hmac.new(auth_key, body, hashlib.sha256).digest()
        return body + struct.pack(CRC_TRAILER_FORMAT, zlib.crc32(body) & 0xFFFFFFFF)

    @classmethod
    def serialize(
        cls,
        frame_id: int,
        timestamp_ms: int,
        split_mode: Union[str, int],
        dtype: Union[str, int] = "int8",
        feature_data: Optional[Union[torch.Tensor, Dict[str, torch.Tensor]]] = None,
        scales: Union[float, torch.Tensor, Tuple[float, float], Dict[str, Any]] = 1.0,
        auth_key: Optional[bytes] = None,
    ) -> bytes:
        """Serializes quantized feature maps and their metadata into one packet.

        ``feature_data`` must already have the storage dtype implied by ``dtype``
        (e.g. torch.int8 for 'int8'); use FeatureMapQuantizer.quantize first.
        """
        split_code = parse_split_mode(split_mode)
        if split_code == SENTINEL_SPLIT_CODE:
            return cls.make_sentinel(frame_id, timestamp_ms, auth_key)
        if feature_data is None:
            raise ValueError("feature_data is required for data packets; use make_sentinel() to end a stream")

        dtype_code = parse_dtype(dtype)
        expected_torch_dtype = TORCH_DTYPE_MAP[dtype_code]

        if isinstance(feature_data, torch.Tensor):
            entries = [(split_code, feature_data, scales)]
        elif isinstance(feature_data, dict):
            entries = []
            for key, tensor in feature_data.items():
                scale = scales.get(key, scales.get(str(key))) if isinstance(scales, dict) else scales
                if scale is None:
                    raise ValueError(f"Missing scale for tensor {key!r}")
                entries.append((int(key), tensor, scale))
        else:
            raise TypeError(f"Unsupported feature_data type {type(feature_data).__name__}")

        if not 1 <= len(entries) <= 255:
            raise ValueError(f"num_tensors must be in [1, 255], got {len(entries)}")

        flags = FLAG_INT8_ZSTD if dtype_code == 6 else FLAG_UINT8_ZSTD if dtype_code == 7 else FLAG_RAW
        if auth_key:
            flags |= FLAG_HMAC

        header = struct.pack(
            PRIMARY_HEADER_FORMAT,
            PROTOCOL_VERSION,
            int(frame_id) & 0xFFFFFFFF,
            int(timestamp_ms) & 0xFFFFFFFFFFFFFFFF,
            split_code,
            len(entries),
            flags,
        )

        cctx, _ = _zstd_contexts()
        descriptors = bytearray()
        payloads = bytearray()
        for layer_idx, tensor, scale_val in entries:
            if not isinstance(tensor, torch.Tensor):
                raise TypeError(f"Tensor for layer {layer_idx} is {type(tensor).__name__}, not torch.Tensor")
            if tensor.dtype != expected_torch_dtype:
                raise TypeError(
                    f"dtype '{DTYPE_CODE_TO_STR[dtype_code]}' requires {expected_torch_dtype} tensors, "
                    f"got {tensor.dtype}; quantize before serializing"
                )
            if not 0 <= layer_idx <= 254:
                raise ValueError(f"Layer index {layer_idx} outside [0, 254]")
            t, c, h, w = _as_nchw(tensor)
            raw = t.numpy().tobytes()

            zero_point = 0.0
            if dtype_code == 3:
                if isinstance(scale_val, torch.Tensor):
                    scale_arr = scale_val.detach().cpu().to(torch.float32).numpy().reshape(-1)
                else:
                    scale_arr = np.asarray(scale_val, dtype=np.float32).reshape(-1)
                if scale_arr.size == 1:
                    scale_arr = np.full(c, scale_arr[0], dtype=np.float32)
                if scale_arr.size != c:
                    raise ValueError(f"Per-channel scale length {scale_arr.size} != channel count {c}")
                desc_scale = float(scale_arr.mean())
                entry = scale_arr.astype(np.float32).tobytes() + raw
            else:
                if isinstance(scale_val, (tuple, list)):
                    desc_scale, zero_point = _scalar(scale_val[0], "scale"), _scalar(scale_val[1], "zero_point")
                elif isinstance(scale_val, dict):
                    desc_scale = _scalar(scale_val["scale"], "scale")
                    zero_point = _scalar(scale_val.get("zero_point", 0.0), "zero_point")
                else:
                    desc_scale = _scalar(scale_val, "scale")
                entry = (struct.pack("<f", zero_point) + raw) if dtype_code in ZERO_POINT_CODES else raw

            if dtype_code in ZSTD_CODES:
                entry = cctx.compress(entry)

            descriptors += struct.pack(DESCRIPTOR_FORMAT, layer_idx, dtype_code, c, h, w, desc_scale, len(entry))
            payloads += entry

        return cls._seal(header + bytes(descriptors) + bytes(payloads), auth_key)

    @classmethod
    def deserialize(
        cls,
        packet_bytes: bytes,
        device: Union[str, torch.device] = "cpu",
        auth_key: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        """Validates and parses a packet, returning tensors in their quantized storage dtype."""
        packet_bytes = bytes(packet_bytes)
        n = len(packet_bytes)
        if n < PRIMARY_HEADER_SIZE + CRC_TRAILER_SIZE:
            raise CorruptedPacketException(f"Packet too small ({n} bytes) for header and CRC")

        body = packet_bytes[:-CRC_TRAILER_SIZE]
        received_crc = struct.unpack(CRC_TRAILER_FORMAT, packet_bytes[-CRC_TRAILER_SIZE:])[0]
        calculated_crc = zlib.crc32(body) & 0xFFFFFFFF
        if received_crc != calculated_crc:
            raise CorruptedPacketException(
                f"CRC32 Checksum Mismatch! (Expected 0x{received_crc:08X}, Computed 0x{calculated_crc:08X})"
            )

        version, frame_id, timestamp_ms, split_code, num_tensors, flags = struct.unpack(
            PRIMARY_HEADER_FORMAT, body[:PRIMARY_HEADER_SIZE]
        )
        if version != PROTOCOL_VERSION:
            raise CorruptedPacketException(f"Incompatible protocol version 0x{version:02X}")

        has_hmac = bool(flags & FLAG_HMAC)
        if auth_key is not None and not has_hmac:
            raise CorruptedPacketException("Unauthenticated packet rejected (auth_key configured)")
        if has_hmac:
            if len(body) < PRIMARY_HEADER_SIZE + HMAC_SIZE:
                raise CorruptedPacketException("Packet too small for HMAC")
            tag = body[-HMAC_SIZE:]
            body = body[:-HMAC_SIZE]
            if auth_key is not None:
                expected = hmac.new(auth_key, body, hashlib.sha256).digest()
                if not hmac.compare_digest(tag, expected):
                    raise CorruptedPacketException("HMAC verification failed")

        base = {
            "version": version,
            "frame_id": frame_id,
            "timestamp_ms": timestamp_ms,
            "split_code": split_code,
            "wire_size_bytes": n,
            "authenticated": has_hmac and auth_key is not None,
        }

        if split_code == SENTINEL_SPLIT_CODE:
            if num_tensors != 0 or len(body) != PRIMARY_HEADER_SIZE:
                raise CorruptedPacketException("Malformed sentinel packet")
            return {**base, "split_mode": "sentinel", "dtype": None, "num_tensors": 0,
                    "reconstructed_data": None, "scales": None, "is_sentinel": True}
        if num_tensors == 0:
            raise CorruptedPacketException("Data packet declares zero tensors")

        desc_end = PRIMARY_HEADER_SIZE + num_tensors * DESCRIPTOR_SIZE
        if len(body) < desc_end:
            raise CorruptedPacketException("Packet truncated inside descriptor table")

        _, dctx = _zstd_contexts()
        tensors: Dict[str, torch.Tensor] = {}
        scales: Dict[str, Any] = {}
        dtype_codes = set()
        offset = desc_end
        for i in range(num_tensors):
            d0 = PRIMARY_HEADER_SIZE + i * DESCRIPTOR_SIZE
            layer_idx, dtype_code, c, h, w, desc_scale, payload_len = struct.unpack(
                DESCRIPTOR_FORMAT, body[d0:d0 + DESCRIPTOR_SIZE]
            )
            if dtype_code not in DTYPE_CODE_TO_STR:
                raise CorruptedPacketException(f"Unknown dtype code {dtype_code} for layer {layer_idx}")
            if min(c, h, w) == 0:
                raise CorruptedPacketException(f"Zero-sized tensor for layer {layer_idx}")
            if str(layer_idx) in tensors:
                raise CorruptedPacketException(f"Duplicate layer {layer_idx}")
            dtype_codes.add(dtype_code)

            tensor_bytes = c * h * w * DTYPE_BYTES_PER_ELEM[dtype_code]
            prefix = 4 * c if dtype_code == 3 else (4 if dtype_code in ZERO_POINT_CODES else 0)
            expected_len = prefix + tensor_bytes
            if expected_len > MAX_TENSOR_BYTES:
                raise CorruptedPacketException(f"Tensor for layer {layer_idx} exceeds size cap")

            if offset + payload_len > len(body):
                raise CorruptedPacketException(
                    f"Payload boundary {offset + payload_len} exceeds packet body {len(body)}"
                )
            raw = body[offset:offset + payload_len]
            offset += payload_len

            if dtype_code in ZSTD_CODES:
                try:
                    raw = dctx.decompress(raw, max_output_size=expected_len)
                except zstd.ZstdError as e:
                    raise CorruptedPacketException(f"Decompression failure for layer {layer_idx}: {e}") from e
            if len(raw) != expected_len:
                raise CorruptedPacketException(
                    f"payload_len {len(raw)} does not match descriptor C={c}, H={h}, W={w}, "
                    f"dtype={dtype_code} (expected {expected_len})"
                )

            np_dtype = NUMPY_DTYPE_MAP[dtype_code]
            arr = np.frombuffer(raw, dtype=np_dtype, offset=prefix).reshape(1, c, h, w).copy()
            key = str(layer_idx)
            tensors[key] = torch.from_numpy(arr).to(device=device)
            if dtype_code == 3:
                s = np.frombuffer(raw[:prefix], dtype=np.float32).copy()
                scales[key] = torch.from_numpy(s).to(device=device)
            elif dtype_code in ZERO_POINT_CODES:
                scales[key] = (desc_scale, struct.unpack("<f", raw[:4])[0])
            else:
                scales[key] = desc_scale

        if offset != len(body):
            raise CorruptedPacketException(f"{len(body) - offset} trailing bytes after last payload")
        if len(dtype_codes) != 1:
            raise CorruptedPacketException("Mixed dtypes within one packet are not supported")
        dtype_code = dtype_codes.pop()
        expected_flag = FLAG_INT8_ZSTD if dtype_code == 6 else FLAG_UINT8_ZSTD if dtype_code == 7 else FLAG_RAW
        if (flags & ~FLAG_HMAC) != expected_flag:
            raise CorruptedPacketException(f"Flags 0x{flags:02X} inconsistent with dtype code {dtype_code}")

        if num_tensors == 1 and str(split_code) in tensors:
            data, sc = tensors[str(split_code)], scales[str(split_code)]
        else:
            data, sc = tensors, scales

        return {
            **base,
            "split_mode": SPLIT_CODE_TO_STR.get(split_code, f"k{split_code}"),
            "dtype": DTYPE_CODE_TO_STR[dtype_code],
            "num_tensors": num_tensors,
            "reconstructed_data": data,
            "scales": sc,
            "is_sentinel": False,
        }
