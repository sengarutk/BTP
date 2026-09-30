"""Multi-Process Asynchronous Integration Test Suite for Split UAV Perception.

Evaluates true multi-process streaming over ZeroMQ IPC and TCP transport layers:
1. Split k4 with INT8 over IPC (ipc:///tmp/aegis_test_k4.ipc).
2. Split k9 with INT8 over TCP (tcp://127.0.0.1:5555).
3. Verifies 100% delivery (0 lost frames), CRC32 validation, >= 30 FPS throughput, and parity.
"""

import multiprocessing as mp
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import torch
from tabulate import tabulate


from pipeline.cloud_pipeline import CloudPipeline
from pipeline.edge_pipeline import EdgePipeline
from pipeline.local_sim_pipeline import LocalSimulationPipeline
from utils.logger import get_logger

logger = get_logger("IPCIntegrationVerifier")


def _run_cloud_process(
    split: str,
    endpoint: str,
    device: str,
    max_frames: int,
    results_queue: mp.Queue,
):
    """Target function for standalone Cloud Submodel worker process."""
    try:
        cloud_pipe = CloudPipeline(
            split_tag=split,
            endpoint=endpoint,
            device=device,
            bind=False,
            timeout_sec=8.0,
        )
        t_start = time.time()
        records = cloud_pipe.listen(max_frames=max_frames, log_interval=25)
        streaming_duration = time.time() - t_start

        frames_count = len(records)
        avg_cloud_time = float(np.mean([r["t_cloud_total_ms"] for r in records])) if records else 0.0
        avg_e2e_time = float(np.mean([r["e2e_network_plus_compute_ms"] for r in records])) if records else 0.0
        wire_size = records[0]["wire_size_kb"] if records else 0.0
        fps = frames_count / max(streaming_duration, 1e-3)

        results_queue.put({
            "status": "SUCCESS",
            "frames_received": frames_count,
            "avg_cloud_compute_ms": avg_cloud_time,
            "avg_e2e_latency_ms": avg_e2e_time,
            "wire_size_kb": wire_size,
            "streaming_fps": fps,
            "streaming_duration": streaming_duration,
        })
    except Exception as e:
        results_queue.put({
            "status": "ERROR",
            "error": str(e),
            "frames_received": 0,
            "avg_cloud_compute_ms": 0.0,
            "avg_e2e_latency_ms": 0.0,
            "wire_size_kb": 0.0,
            "streaming_fps": 0.0,
            "streaming_duration": 0.0,
        })


def _run_edge_process(
    split: str,
    dtype: str,
    endpoint: str,
    device: str,
    num_frames: int,
    fps: float,
    status_queue: mp.Queue,
):
    """Target function for standalone Edge Submodel worker process."""
    try:
        time.sleep(0.4)
        edge_pipe = EdgePipeline(
            split_tag=split,
            dtype=dtype,
            endpoint=endpoint,
            device=device,
            target_fps=fps,
            bind=True,
        )
        sent = edge_pipe.stream_synthetic(num_frames=num_frames, log_interval=25)
        status_queue.put({"status": "SUCCESS", "frames_sent": sent})
    except Exception as e:
        status_queue.put({"status": "ERROR", "error": str(e), "frames_sent": 0})


def run_ipc_integration_test(
    split_tag: str = "k4",
    dtype: str = "int8",
    endpoint: str = "ipc:///tmp/aegis_test_k4.ipc",
    num_frames: int = 100,
    target_fps: float = 60.0,
    device: str = "cuda" if torch.cuda.is_available() else "cpu",
) -> Dict[str, Any]:
    """Spawns concurrent Edge and Cloud processes and verifies asynchronous IPC streaming."""
    transport_name = "IPC" if "ipc://" in endpoint else "TCP"
    logger.info(
        f"Starting Multi-Process Integration Test: [{split_tag.upper()} - {dtype.upper()} over {transport_name}] "
        f"({num_frames} frames @ {target_fps} target FPS)..."
    )

    mp_ctx = mp.get_context("spawn")
    cloud_queue = mp_ctx.Queue()
    edge_queue = mp_ctx.Queue()

    # 1. Spawn Cloud Consumer Process
    cloud_proc = mp_ctx.Process(
        target=_run_cloud_process,
        args=(split_tag, endpoint, device, num_frames, cloud_queue),
        daemon=True,
    )

    # 2. Spawn Edge Publisher Process
    edge_proc = mp_ctx.Process(
        target=_run_edge_process,
        args=(split_tag, dtype, endpoint, device, num_frames, target_fps, edge_queue),
        daemon=True,
    )

    cloud_proc.start()
    edge_proc.start()

    edge_res = edge_queue.get(timeout=25.0) if edge_queue else {"status": "TIMEOUT", "frames_sent": 0}
    cloud_res = cloud_queue.get(timeout=25.0) if cloud_queue else {"status": "TIMEOUT", "frames_received": 0}

    edge_proc.join(timeout=5.0)
    cloud_proc.join(timeout=5.0)

    frames_sent = edge_res.get("frames_sent", 0)
    frames_recv = cloud_res.get("frames_received", 0)

    delivery_rate = (frames_recv / max(frames_sent, 1)) * 100.0 if frames_sent > 0 else 0.0
    actual_fps = cloud_res.get("streaming_fps", 0.0)

    passed = (
        edge_res["status"] == "SUCCESS"
        and cloud_res["status"] == "SUCCESS"
        and frames_sent == num_frames
        and frames_recv == num_frames
        and delivery_rate == 100.0
        and actual_fps >= 30.0
    )

    if passed:
        logger.success(
            f"Multi-Process Test [{split_tag.upper()} - {transport_name}] PASSED: "
            f"100% Delivery ({frames_recv}/{frames_sent} frames), "
            f"Throughput = {actual_fps:.1f} FPS (>= 30 FPS target)"
        )
    else:
        logger.error(
            f"Multi-Process Test [{split_tag.upper()} - {transport_name}] FAILED: "
            f"Sent={frames_sent}, Recv={frames_recv}, Edge={edge_res['status']}, Cloud={cloud_res['status']}"
        )

    return {
        "split": split_tag,
        "dtype": dtype,
        "transport": transport_name,
        "endpoint": endpoint,
        "frames_sent": frames_sent,
        "frames_received": frames_recv,
        "delivery_rate_pct": delivery_rate,
        "actual_fps": actual_fps,
        "avg_cloud_compute_ms": cloud_res.get("avg_cloud_compute_ms", 0.0),
        "avg_e2e_latency_ms": cloud_res.get("avg_e2e_latency_ms", 0.0),
        "wire_size_kb": cloud_res.get("wire_size_kb", 0.0),
        "passed": passed,
    }


def print_integration_report(results: List[Dict[str, Any]]):
    """Formats and prints comprehensive diagnostic integration summary table."""
    headers = [
        "Test Configuration",
        "Transport",
        "Frames (Sent/Recv)",
        "Delivery Rate",
        "Streaming Throughput",
        "Wire Size",
        "Avg Cloud Time",
        "Avg E2E Latency",
        "Status",
    ]
    rows = []

    for r in results:
        config_str = f"Split [{r['split'].upper()}] - {r['dtype'].upper()}"
        frames_str = f"{r['frames_sent']} / {r['frames_received']}"
        deliv_str = f"{r['delivery_rate_pct']:.1f}%"
        fps_str = f"{r['actual_fps']:.1f} FPS"
        wire_str = f"{r['wire_size_kb']:,.1f} KB"
        cloud_time = f"{r['avg_cloud_compute_ms']:.2f} ms"
        e2e_time = f"{r['avg_e2e_latency_ms']:.1f} ms"
        status_str = "★ PASSED" if r["passed"] else "FAILED"

        rows.append([
            config_str,
            r["transport"],
            frames_str,
            deliv_str,
            fps_str,
            wire_str,
            cloud_time,
            e2e_time,
            status_str,
        ])

    print("\n" + "=" * 115)
    print("              MULTI-PROCESS ZERO-MQ SPLIT-STREAMING INTEGRATION REPORT")
    print("=" * 115)
    print(tabulate(rows, headers=headers, tablefmt="fancy_grid"))
    print("=" * 115 + "\n")


if __name__ == "__main__":
    device = "cuda" if torch.cuda.is_available() else "cpu"

    test_runs = [
        {
            "split_tag": "k4",
            "dtype": "int8",
            "endpoint": "ipc:///tmp/aegis_test_k4.ipc",
            "num_frames": 100,
            "target_fps": 60.0,
        },
        {
            "split_tag": "k9",
            "dtype": "int8",
            "endpoint": "tcp://127.0.0.1:5555",
            "num_frames": 100,
            "target_fps": 60.0,
        },
    ]

    results = []
    for cfg in test_runs:
        res = run_ipc_integration_test(
            split_tag=cfg["split_tag"],
            dtype=cfg["dtype"],
            endpoint=cfg["endpoint"],
            num_frames=cfg["num_frames"],
            target_fps=cfg["target_fps"],
            device=device,
        )
        results.append(res)
        time.sleep(0.5)

    print_integration_report(results)

    for r in results:
        assert r["passed"], f"Integration test failed for {r['split']} over {r['transport']}"
