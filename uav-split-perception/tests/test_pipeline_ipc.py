"""End-to-end check of the real edge and cloud processes over a ZeroMQ IPC socket."""
import threading
import uuid

import numpy as np
import pytest
import torch

from pipeline.cloud_pipeline import CloudPipeline
from pipeline.edge_pipeline import EdgePipeline
from protocol.transport import AegisZMQPublisher

from .conftest import WEIGHTS


@pytest.mark.skipif(not WEIGHTS.exists(), reason="yolov8s.pt not present")
@pytest.mark.parametrize("cut,dtype", [(4, "int8"), (9, "int8_zstd")])
def test_edge_to_cloud_over_ipc(tmp_path, cut, dtype):
    endpoint = f"ipc://{tmp_path}/aegis-{uuid.uuid4().hex[:8]}.ipc"
    key = b"test-key"
    cloud = CloudPipeline(endpoint=endpoint, weights=str(WEIGHTS), device="cpu", bind=True,
                          idle_timeout_s=30.0, auth_key=key)
    result = {}
    t = threading.Thread(target=lambda: result.setdefault("records", cloud.listen()))
    t.start()
    edge = EdgePipeline(cut, dtype, endpoint, weights=str(WEIGHTS), device="cpu", bind=False, auth_key=key)
    frames = [np.full((640, 640, 3), 114, np.uint8)]
    rng = np.random.default_rng(0)
    frames += [rng.integers(0, 255, (640, 640, 3), dtype=np.uint8) for _ in range(3)]
    for i, fr in enumerate(frames):
        edge.publisher.send_packet(edge.encode(fr, i + 1, 0))
    # A malformed packet must be rejected without stopping the server.
    edge.publisher.send_packet(b"\x00" * 64)
    edge.stop()
    t.join(timeout=60)
    assert not t.is_alive()
    recs = result["records"]
    assert [r["frame_id"] for r in recs] == [1, 2, 3, 4]
    assert all(r["split"] == f"k{cut}" for r in recs)
    assert cloud.frames_rejected == 1
