import os
import struct
import zlib

import numpy as np
import pytest
import torch

from protocol.packet import (CRC_TRAILER_SIZE, AegisPacketProtocol as P, CorruptedPacketException,
                             SENTINEL_SPLIT_CODE)
from quantization.quantizer import FeatureMapQuantizer as Q

MODES = ["fp32", "fp16", "int8", "int8_per_channel", "int8_fp16_accum", "uint8", "uint8_clip", "int8_zstd", "uint8_zstd"]


def _reseal(body: bytes) -> bytes:
    return body + struct.pack("<I", zlib.crc32(body))


@pytest.mark.parametrize("mode", MODES)
def test_round_trip_is_lossless_on_the_wire(mode):
    torch.manual_seed(1)
    x = torch.randn(1, 16, 12, 10) * 3
    q, s = Q.quantize(x, dtype=mode)
    parsed = P.deserialize(P.serialize(7, 123, "k4", mode, q, s))
    assert parsed["frame_id"] == 7 and parsed["timestamp_ms"] == 123 and parsed["split_code"] == 4
    assert torch.equal(parsed["reconstructed_data"], q)
    # Dequantizing the received data gives exactly what dequantizing locally gives.
    local = Q.dequantize(q, s, dtype=mode)
    remote = Q.dequantize(parsed["reconstructed_data"], parsed["scales"], dtype=parsed["dtype"])
    assert torch.equal(local, remote)


def test_multi_tensor_bundle_round_trip():
    feats = {"4": torch.randn(1, 8, 16, 16), "6": torch.randn(1, 16, 8, 8), "9": torch.randn(1, 32, 4, 4)}
    q, s = Q.quantize(feats, dtype="int8")
    parsed = P.deserialize(P.serialize(1, 0, "k9", "int8", q, s))
    assert set(parsed["reconstructed_data"]) == {"4", "6", "9"}
    for k in feats:
        assert torch.equal(parsed["reconstructed_data"][k], q[k])
        assert parsed["scales"][k] == pytest.approx(s[k], rel=0, abs=0)


@pytest.mark.parametrize("scale", [np.float32(0.05), np.float64(0.05), torch.tensor(0.05), 0.05])
def test_scalar_scale_types_are_preserved(scale):
    q = torch.randint(-128, 127, (1, 4, 4, 4), dtype=torch.int8)
    parsed = P.deserialize(P.serialize(1, 0, "k4", "int8", q, scale))
    assert parsed["scales"] == pytest.approx(0.05, rel=1e-7)


@pytest.mark.parametrize("mode", ["int8", "int8_per_channel", "uint8", "fp16", "fp32"])
def test_wrong_storage_dtype_is_rejected(mode):
    wrong = torch.randn(1, 4, 4, 4, dtype=torch.float64)
    with pytest.raises(TypeError):
        P.serialize(1, 0, "k4", mode, wrong, 1.0)


def test_invalid_arguments_are_rejected():
    q = torch.zeros(1, 4, 4, 4, dtype=torch.int8)
    with pytest.raises(ValueError):
        P.serialize(1, 0, "k4", "int4", q, 1.0)
    with pytest.raises(ValueError):
        P.serialize(1, 0, "k4", "int8", None)
    with pytest.raises(ValueError):
        P.serialize(1, 0, "kx", "int8", q, 1.0)
    with pytest.raises(ValueError):
        P.serialize(1, 0, "k4", "int8", torch.zeros(2, 4, 4, 4, dtype=torch.int8), 1.0)
    with pytest.raises(ValueError):
        P.serialize(1, 0, "k4", "int8", torch.zeros(70000, dtype=torch.int8), 1.0)
    with pytest.raises(ValueError):
        P.serialize(1, 0, "k4", "int8_per_channel", q, torch.ones(3))


def test_sentinel():
    parsed = P.deserialize(P.make_sentinel(99, 5))
    assert parsed["is_sentinel"] and parsed["split_code"] == SENTINEL_SPLIT_CODE and parsed["reconstructed_data"] is None
    assert P.deserialize(P.serialize(99, 5, "sentinel"))["is_sentinel"]


def test_crc_detects_corruption():
    pkt = bytearray(P.serialize(1, 0, "k4", "int8", torch.zeros(1, 4, 8, 8, dtype=torch.int8), 0.1))
    pkt[len(pkt) // 2] ^= 0xFF
    with pytest.raises(CorruptedPacketException, match="CRC32"):
        P.deserialize(bytes(pkt))


def test_structural_inconsistencies_are_rejected_even_with_valid_crc():
    pkt = P.serialize(1, 0, "k4", "int8", torch.zeros(1, 4, 8, 8, dtype=torch.int8), 0.1)
    body = pkt[:-CRC_TRAILER_SIZE]
    with pytest.raises(CorruptedPacketException, match="trailing"):
        P.deserialize(_reseal(body + b"junk"))
    with pytest.raises(CorruptedPacketException):
        P.deserialize(_reseal(body[:-10]))
    bad_dtype = bytearray(body)
    bad_dtype[16 + 1] = 42  # descriptor dtype byte
    with pytest.raises(CorruptedPacketException, match="dtype"):
        P.deserialize(_reseal(bytes(bad_dtype)))
    bad_flags = bytearray(body)
    bad_flags[15] = 0x04  # claims zstd for a raw int8 payload
    with pytest.raises(CorruptedPacketException, match="Flags"):
        P.deserialize(_reseal(bytes(bad_flags)))


def test_decompression_is_capped():
    import zstandard as zstd

    q = torch.zeros(1, 1, 4, 4, dtype=torch.int8)
    pkt = P.serialize(1, 0, "k4", "int8_zstd", q, 1.0)
    body = bytearray(pkt[:-CRC_TRAILER_SIZE])
    bomb = zstd.ZstdCompressor().compress(b"\0" * 10_000_000)
    desc = bytearray(body[16:32])
    desc[-4:] = struct.pack("<I", len(bomb))
    body = body[:16] + desc + bomb
    with pytest.raises(CorruptedPacketException):
        P.deserialize(_reseal(bytes(body)))


def test_hmac_authentication():
    key = b"shared-secret"
    q = torch.zeros(1, 4, 4, 4, dtype=torch.int8)
    pkt = P.serialize(1, 0, "k4", "int8", q, 1.0, auth_key=key)
    assert P.deserialize(pkt, auth_key=key)["authenticated"]
    tampered = bytearray(pkt[:-CRC_TRAILER_SIZE])
    tampered[40] ^= 1
    with pytest.raises(CorruptedPacketException, match="HMAC"):
        P.deserialize(_reseal(bytes(tampered)), auth_key=key)
    with pytest.raises(CorruptedPacketException, match="Unauthenticated"):
        P.deserialize(P.serialize(1, 0, "k4", "int8", q, 1.0), auth_key=key)
    with pytest.raises(CorruptedPacketException, match="HMAC"):
        P.deserialize(pkt, auth_key=b"wrong")


@pytest.mark.parametrize("length", [0, 5, 19, 20, 36, 128, 1024])
def test_random_bytes_never_parse(length):
    with pytest.raises(CorruptedPacketException):
        P.deserialize(os.urandom(length))
