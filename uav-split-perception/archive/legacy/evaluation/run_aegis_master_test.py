"""Canonical Master Automated Test Runner & Verification Suite for AEGIS-UAV Split Perception.

Executes all 23 end-to-end verification modules in sequential order:
1.  Programmatic Graph Inspection & Routing Topologies (core/inspect_graph.py)
2.  Submodel Decoupling & Numerical Equivalence Parity (evaluation/verify_submodels.py)
3.  Dynamic Submodel Slicing Engine (core/dynamic_submodels.py)
4.  Dynamic Symmetric INT8 Quantization & Wire Protocol (evaluation/verify_quantization.py)
5.  ZeroMQ IPC/TCP Multi-Process Streaming Runtimes (evaluation/verify_pipeline_ipc.py)
6.  COCO128 Real-World High-Precision mAP Evaluation (evaluation/evaluate_mAP.py)
7.  Multi-Pass Statistical Micro-Benchmarking Suite (evaluation/benchmark_suite.py)
8.  Granular Split-Point Pareto Frontier Analysis (evaluation/benchmark_split_pareto.py)
9.  Quantization Deep Dive Benchmarking Suite (evaluation/benchmark_quant_modes.py)
10. ZeroMQ Stress & Backpressure Profiling (evaluation/stress_test_zmq.py)
11. 3GPP 5G Channel Trace Synthesis Engine (simulation/trace_generator.py)
12. Asynchronous ChannelProxy IPC/ZMQ Broadcast (simulation/channel_proxy.py --test)
13. Netem Traffic Shaper Engine (simulation/netem_controller.py)
14. Dynamic 5G Trace Multi-Channel Benchmark (evaluation/benchmark_5g_traces.py --quick)
15. Publication Artifacts Figure Generation (evaluation/plot_artifacts.py)
16. 3D/2D Pareto Visualization Suite (evaluation/plot_pareto_3d.py)
17. Quantization Deep Dive Visualization Suite (evaluation/plot_quant_deepdive.py)
18. 5G Channel Emulation Publication Visualizations (evaluation/plot_5g_traces.py)
19. UAV Energy & Power Modeling Benchmark (evaluation/benchmark_energy.py)
20. Publication Energy & Power Visualizations (evaluation/plot_energy.py)
21. TensorRT Submodel Export Engine (deployment/jetson/export_trt.py)
22. Fused CUDA INT8 Kernel Parity (deployment/jetson/cuda_quant/test_cuda_quant.py)
23. Closed-Loop Dynamic Split Policy & Switchboard (pipeline/dynamic_policy.py)
"""

import argparse
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Tuple

from tabulate import tabulate

from utils.logger import get_logger

logger = get_logger("AegisMasterTestRunner")


def get_test_stages(quick: bool = False) -> List[Tuple[str, List[str]]]:
    """Constructs test stages with dynamic quick/full benchmarking parameters."""
    bench_args = ["--passes", "1", "--frames", "10"] if quick else ["--passes", "3", "--frames", "50"]

    return [
        ("Graph Inspection & Topologies", [sys.executable, "core/inspect_graph.py"]),
        ("Submodel Decoupling & Parity", [sys.executable, "evaluation/verify_submodels.py"]),
        ("Dynamic Submodel Slicing Engine", [sys.executable, "core/dynamic_submodels.py"]),
        ("Quantization & Wire Protocol", [sys.executable, "evaluation/verify_quantization.py"]),
        ("ZeroMQ IPC/TCP Streaming Runtimes", [sys.executable, "evaluation/verify_pipeline_ipc.py"]),
        ("COCO128 Real-World mAP Evaluation", [sys.executable, "evaluation/evaluate_mAP.py"]),
        ("Statistical Micro-Benchmarking", [sys.executable, "evaluation/benchmark_suite.py"] + bench_args),
        ("Granular Split Pareto Benchmarking", [sys.executable, "evaluation/benchmark_split_pareto.py"] + bench_args),
        ("Quantization Deep Dive Benchmarking", [sys.executable, "evaluation/benchmark_quant_modes.py"] + bench_args),
        ("ZeroMQ Stress & Backpressure", [sys.executable, "evaluation/stress_test_zmq.py"]),
        ("3GPP 5G Trace Generator", [sys.executable, "simulation/trace_generator.py"]),
        ("ChannelProxy IPC/ZMQ Broadcast", [sys.executable, "simulation/channel_proxy.py", "--test"]),
        ("Netem Traffic Shaper Engine", [sys.executable, "simulation/netem_controller.py"]),
        ("Dynamic 5G Trace Benchmark", [sys.executable, "evaluation/benchmark_5g_traces.py", "--quick"]),
        ("Publication Artifacts Generation", [sys.executable, "evaluation/plot_artifacts.py"]),
        ("3D/2D Pareto Visualization Suite", [sys.executable, "evaluation/plot_pareto_3d.py"]),
        ("Quantization Deep Dive Visualizations", [sys.executable, "evaluation/plot_quant_deepdive.py"]),
        ("5G Channel Emulation Visualizations", [sys.executable, "evaluation/plot_5g_traces.py"]),
        ("UAV Energy & Power Benchmark", [sys.executable, "evaluation/benchmark_energy.py"]),
        ("Publication Energy Visualizations", [sys.executable, "evaluation/plot_energy.py"]),
        ("TensorRT Submodel Export Engine", [sys.executable, "deployment/jetson/export_trt.py"]),
        ("Fused CUDA INT8 Kernel Parity", [sys.executable, "deployment/jetson/cuda_quant/test_cuda_quant.py"]),
        ("Closed-Loop Dynamic Split Policy", [sys.executable, "pipeline/dynamic_policy.py"]),
    ]


def run_master_verification(quick: bool = False, timeout: int = 180) -> bool:
    """Runs all 23 validation stages sequentially and prints the summary matrix."""
    logger.info("=" * 90)
    logger.info(f"     AEGIS-UAV MASTER VERIFICATION SUITE: 23 INTEGRATED MODULES (Quick={quick})")
    logger.info("=" * 90)

    test_stages = get_test_stages(quick=quick)
    summary_rows = []
    overall_success = True
    total_start = time.perf_counter()

    for stage_name, cmd in test_stages:
        cmd_str = " ".join(cmd)
        logger.info(f"Executing Test Stage: [{stage_name}] -> `{cmd_str}`")
        stage_start = time.perf_counter()

        try:
            result = subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout,
            )
            elapsed = time.perf_counter() - stage_start
            logger.info(f"Test Stage [{stage_name}] PASSED in {elapsed:.2f}s")
            summary_rows.append([stage_name, cmd_str, f"{elapsed:.2f}s", "★ PASSED"])
        except subprocess.TimeoutExpired as e:
            elapsed = time.perf_counter() - stage_start
            logger.error(f"Test Stage [{stage_name}] TIMED OUT after {timeout}s!")
            summary_rows.append([stage_name, cmd_str, f"{elapsed:.2f}s", "✖ TIMEOUT"])
            overall_success = False
            break
        except subprocess.CalledProcessError as e:
            elapsed = time.perf_counter() - stage_start
            logger.error(f"Test Stage [{stage_name}] FAILED with returncode {e.returncode} in {elapsed:.2f}s!")
            logger.error(f"Error Output:\n{e.output}")
            summary_rows.append([stage_name, cmd_str, f"{elapsed:.2f}s", "✖ FAILED"])
            overall_success = False
            break
        except Exception as e:
            elapsed = time.perf_counter() - stage_start
            logger.error(f"Test Stage [{stage_name}] encountered unexpected exception: {e}")
            summary_rows.append([stage_name, cmd_str, f"{elapsed:.2f}s", "✖ ERROR"])
            overall_success = False
            break

    total_duration = time.perf_counter() - total_start
    headers = ["Test Module", "Command Executed", "Duration", "Status"]

    print("\n" + "=" * 135)
    print(f"                      AEGIS-UAV MASTER TEST SUITE RESULTS (Total Time: {total_duration:.2f}s)")
    print("=" * 135)
    print(tabulate(summary_rows, headers=headers, tablefmt="fancy_grid"))
    print("=" * 135 + "\n")

    return overall_success


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AEGIS-UAV Master Automated Test Suite")
    parser.add_argument("--quick", action="store_true", help="Run in fast mode with reduced bench passes")
    parser.add_argument("--timeout", type=int, default=180, help="Per-stage timeout in seconds (default: 180)")
    args = parser.parse_args()

    success = run_master_verification(quick=args.quick, timeout=args.timeout)
    sys.exit(0 if success else 1)
