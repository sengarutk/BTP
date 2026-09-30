"""ZeroMQ Stress Testing & Backpressure Harness for Split UAV Perception.

Executes extreme transport stability and backpressure tests:
1. High-Rate Burst Streaming: 300 frames at 60 FPS and 120 FPS over IPC/TCP.
2. Queue Backpressure & Buffer Saturation: hwm=5 with artificial 50ms consumer delay.
3. Warmup-Exempted Jitter Profiling (N_warmup = 15 frames exempted).
4. Resource Profiling: Host CPU (%), Process RSS RAM (MiB), and GPU VRAM (MiB) via psutil.
5. Exports structured results to experiments/results/zmq_stress_results.json.
"""

import argparse
import json
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import psutil
import torch
import zmq
from tabulate import tabulate


from protocol.packet import AegisPacketProtocol, SENTINEL_SPLIT_CODE
from protocol.transport import AegisZMQPublisher, AegisZMQSubscriber
from quantization.quantizer import FeatureMapQuantizer, DTYPE_INT8
from utils.logger import get_logger

logger = get_logger("ZMQStressTest")
WARMUP_EXEMPT_FRAMES = 15


def _stress_cloud_worker(
    endpoint: str,
    artificial_delay_ms: float,
    max_frames: int,
    results_queue: mp.Queue,
):
    """Stress test consumer process with configurable compute latency injection and warmup-exempted jitter."""
    try:
        sub = AegisZMQSubscriber(endpoint=endpoint, bind=False, timeout_ms=800)
        received_frames = 0
        timestamps = []
        idle_timeouts = 0

        while True:
            packet_bytes = sub.recv_packet()
            if packet_bytes is None:
                idle_timeouts += 1
                if idle_timeouts >= 3 and received_frames > 0:
                    break
                continue

            idle_timeouts = 0
            t_recv = time.time()
            timestamps.append(t_recv)

            parsed = AegisPacketProtocol.deserialize(packet_bytes, device="cpu")
            if parsed.get("is_sentinel", False):
                break

            received_frames += 1

            if artificial_delay_ms > 0:
                time.sleep(artificial_delay_ms / 1000.0)

            if 0 < max_frames <= received_frames:
                break

        sub.close()

        # Warmup-Exempted Inter-Frame Jitter Calculation (Discard first N_warmup = 15 frames)
        if len(timestamps) > WARMUP_EXEMPT_FRAMES + 1:
            steady_state_timestamps = timestamps[WARMUP_EXEMPT_FRAMES:]
            diffs = np.diff(steady_state_timestamps) * 1000.0  # ms
            jitter_ms = float(np.std(diffs))
            mean_interval_ms = float(np.mean(diffs))
        elif len(timestamps) > 1:
            diffs = np.diff(timestamps) * 1000.0  # ms
            jitter_ms = float(np.std(diffs))
            mean_interval_ms = float(np.mean(diffs))
        else:
            jitter_ms = 0.0
            mean_interval_ms = 0.0

        results_queue.put({
            "status": "SUCCESS",
            "frames_received": received_frames,
            "jitter_ms": round(jitter_ms, 3),
            "mean_interval_ms": round(mean_interval_ms, 3),
            "warmup_exempted": len(timestamps) > WARMUP_EXEMPT_FRAMES,
        })
    except Exception as e:
        results_queue.put({
            "status": "ERROR",
            "error": str(e),
            "frames_received": 0,
            "jitter_ms": 0.0,
            "mean_interval_ms": 0.0,
            "warmup_exempted": False,
        })


def _stress_edge_worker(
    endpoint: str,
    target_fps: float,
    num_frames: int,
    hwm: int,
    non_blocking: bool,
    status_queue: mp.Queue,
):
    """Stress test publisher process with burst transmission and HWM control."""
    try:
        time.sleep(0.3)
        pub = AegisZMQPublisher(endpoint=endpoint, bind=True, hwm=hwm)
        interval = 1.0 / max(target_fps, 1.0)

        # Create realistic dummy INT8 activation payload (~800 KiB)
        dummy_act = torch.randn(1, 128, 80, 80)
        q_data, scales = FeatureMapQuantizer.quantize(dummy_act, dtype=DTYPE_INT8)

        frames_sent = 0
        frames_dropped = 0
        t_start = time.time()

        for f_idx in range(1, num_frames + 1):
            t_frame_start = time.perf_counter()
            pkt_bytes = AegisPacketProtocol.serialize(
                frame_id=f_idx,
                timestamp_ms=int(time.time() * 1000),
                split_mode="k4",
                dtype="int8",
                feature_data=q_data,
                scales=scales,
            )

            sent = pub.send_packet(pkt_bytes, non_blocking=non_blocking)
            if sent:
                frames_sent += 1
            else:
                frames_dropped += 1

            elapsed = time.perf_counter() - t_frame_start
            sleep_time = max(0.0, interval - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)

        total_tx_time = time.time() - t_start

        # Send sentinel
        sentinel_pkt = AegisPacketProtocol.serialize(
            frame_id=num_frames + 1,
            timestamp_ms=int(time.time() * 1000),
            split_mode=SENTINEL_SPLIT_CODE,
        )
        pub.send_packet(sentinel_pkt, non_blocking=True)
        pub.close()

        status_queue.put({
            "status": "SUCCESS",
            "frames_sent": frames_sent,
            "frames_dropped": frames_dropped,
            "total_tx_time_s": round(total_tx_time, 3),
        })
    except Exception as e:
        status_queue.put({
            "status": "ERROR",
            "error": str(e),
            "frames_sent": 0,
            "frames_dropped": 0,
            "total_tx_time_s": 0.0,
        })


def profile_system_resources() -> Dict[str, float]:
    """Captures CPU, RAM, and GPU VRAM resource consumption in IEC binary units (MiB)."""
    process = psutil.Process(os.getpid())
    cpu_pct = float(psutil.cpu_percent(interval=None))
    ram_mib = float(process.memory_info().rss / (1024 * 1024))

    vram_mib = 0.0
    if torch.cuda.is_available():
        vram_mib = float(torch.cuda.memory_allocated() / (1024 * 1024))

    return {
        "cpu_percent": round(cpu_pct, 1),
        "ram_mib": round(ram_mib, 1),
        "vram_mib": round(vram_mib, 1),
    }


def run_single_stress_test(
    test_name: str,
    endpoint: str,
    target_fps: float,
    num_frames: int,
    hwm: int,
    non_blocking: bool,
    artificial_delay_ms: float = 0.0,
) -> Dict[str, Any]:
    """Runs a single stress test scenario and measures throughput, drops, and warmup-exempted jitter."""
    logger.info(f"Running Stress Scenario: [{test_name}] (Target FPS={target_fps}, HWM={hwm}, Delay={artificial_delay_ms}ms)...")

    res_before = profile_system_resources()

    mp_ctx = mp.get_context("spawn")
    cloud_queue = mp_ctx.Queue()
    edge_queue = mp_ctx.Queue()

    cloud_proc = mp_ctx.Process(
        target=_stress_cloud_worker,
        args=(endpoint, artificial_delay_ms, num_frames, cloud_queue),
        daemon=True,
    )
    edge_proc = mp_ctx.Process(
        target=_stress_edge_worker,
        args=(endpoint, target_fps, num_frames, hwm, non_blocking, edge_queue),
        daemon=True,
    )

    t0 = time.time()
    cloud_proc.start()
    edge_proc.start()

    edge_res = edge_queue.get(timeout=30.0) if edge_queue else {"status": "TIMEOUT", "frames_sent": 0, "frames_dropped": 0}
    cloud_res = cloud_queue.get(timeout=30.0) if cloud_queue else {"status": "TIMEOUT", "frames_received": 0}

    edge_proc.join(timeout=5.0)
    cloud_proc.join(timeout=5.0)
    wall_time = time.time() - t0

    res_after = profile_system_resources()

    frames_sent = edge_res.get("frames_sent", 0)
    frames_dropped = edge_res.get("frames_dropped", 0)
    frames_recv = cloud_res.get("frames_received", 0)

    delivery_rate = (frames_recv / max(num_frames, 1)) * 100.0
    actual_fps = frames_recv / max(cloud_res.get("total_tx_time_s", wall_time), 1e-3)

    is_backpressure_test = artificial_delay_ms > 0
    passed = (
        edge_res["status"] == "SUCCESS"
        and cloud_res["status"] == "SUCCESS"
        and (frames_dropped > 0 if is_backpressure_test else (frames_recv == num_frames and delivery_rate == 100.0))
    )

    result_record = {
        "test_name": test_name,
        "endpoint": endpoint,
        "target_fps": target_fps,
        "total_frames": num_frames,
        "frames_sent": frames_sent,
        "frames_dropped": frames_dropped,
        "frames_received": frames_recv,
        "delivery_rate_pct": round(delivery_rate, 2),
        "actual_fps": round(actual_fps, 1),
        "jitter_ms": cloud_res.get("jitter_ms", 0.0),
        "warmup_exempted_frames": WARMUP_EXEMPT_FRAMES,
        "cpu_pct": max(res_before["cpu_percent"], res_after["cpu_percent"]),
        "ram_mib": res_after["ram_mib"],
        "vram_mib": res_after["vram_mib"],
        "passed": passed,
    }

    status_str = "PASSED" if passed else "FAILED"
    logger.success(
        f"[{test_name}] {status_str}: Sent={frames_sent}, Dropped={frames_dropped}, Recv={frames_recv} "
        f"({delivery_rate:.1f}%), Jitter (Warmup-Exempted)={result_record['jitter_ms']}ms, RAM={res_after['ram_mib']} MiB"
    )
    return result_record


def run_all_stress_tests(output_dir: str = "experiments/results") -> List[Dict[str, Any]]:
    """Runs complete stress test suite covering burst rates and backpressure saturation."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("Starting ZeroMQ Transport Stress & Backpressure Test Suite (300 frames/run)...")

    scenarios = [
        {
            "test_name": "Burst Rate Test (60 FPS - IPC)",
            "endpoint": "ipc:///tmp/aegis_stress_60fps.ipc",
            "target_fps": 60.0,
            "num_frames": 300,
            "hwm": 10,
            "non_blocking": False,
            "artificial_delay_ms": 0.0,
        },
        {
            "test_name": "Ultra-Burst Test (120 FPS - TCP)",
            "endpoint": "tcp://127.0.0.1:5560",
            "target_fps": 120.0,
            "num_frames": 300,
            "hwm": 10,
            "non_blocking": False,
            "artificial_delay_ms": 0.0,
        },
        {
            "test_name": "Backpressure & Saturation (HWM=5, 50ms Delay)",
            "endpoint": "ipc:///tmp/aegis_stress_backpressure.ipc",
            "target_fps": 60.0,
            "num_frames": 300,
            "hwm": 5,
            "non_blocking": True,
            "artificial_delay_ms": 50.0,
        },
    ]

    results = []
    for sc in scenarios:
        res = run_single_stress_test(
            test_name=sc["test_name"],
            endpoint=sc["endpoint"],
            target_fps=sc["target_fps"],
            num_frames=sc["num_frames"],
            hwm=sc["hwm"],
            non_blocking=sc["non_blocking"],
            artificial_delay_ms=sc["artificial_delay_ms"],
        )
        results.append(res)
        time.sleep(0.5)

    # Export to JSON
    json_path = os.path.join(output_dir, "zmq_stress_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "warmup_exempted_frames": WARMUP_EXEMPT_FRAMES,
            "scenarios": results,
            "notes": "Inter-frame jitter computed as std(delta t) after discarding first 15 warmup frames."
        }, f, indent=2)
    logger.success(f"Exported ZeroMQ stress test results to '{json_path}'")

    print_stress_report(results)
    return results


def print_stress_report(results: List[Dict[str, Any]]):
    """Formats and prints ASCII diagnostic stress test report table."""
    headers = [
        "Stress Test Scenario",
        "Target FPS",
        "Frames (Sent/Drop/Recv)",
        "Delivery Rate",
        "Steady Jitter (ms)",
        "RAM (MiB)",
        "CPU (%)",
        "Status",
    ]
    rows = []

    for r in results:
        f_str = f"{r['frames_sent']} / {r['frames_dropped']} / {r['frames_received']}"
        deliv = f"{r['delivery_rate_pct']:.1f}%"
        status_str = "★ PASSED" if r["passed"] else "FAILED"

        rows.append([
            r["test_name"],
            f"{r['target_fps']:.0f} FPS",
            f_str,
            deliv,
            f"{r['jitter_ms']:.2f} ms",
            f"{r['ram_mib']:.1f} MiB",
            f"{r['cpu_pct']:.1f}%",
            status_str,
        ])

    print("\n" + "=" * 130)
    print("           ZEROMQ TRANSPORT STRESS & BACKPRESSURE REPORT (300 Frames/Run, N_warmup=15 Exempted)")
    print("=" * 130)
    print(tabulate(rows, headers=headers, tablefmt="fancy_grid"))
    print("=" * 130 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ZeroMQ Transport Stress Testing Suite")
    parser.add_argument("--output-dir", type=str, default="experiments/results")
    args = parser.parse_args()

    results = run_all_stress_tests(output_dir=args.output_dir)
    for r in results:
        assert r["passed"], f"Stress test failed for scenario: {r['test_name']}"
