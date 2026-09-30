# AEGIS-UAV Split Perception System: Comprehensive Walkthrough

---

## 1. System Architecture Overview

AEGIS-UAV is an asynchronous, multi-objective split perception framework for edge UAV platforms offloading YOLOv8 object detection over dynamic 5G cellular links.

```
┌───────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 AEGIS-UAV Full System Architecture                                │
├───────────────────────────────────────────────────────────────────────────────────────────────────┤
│ [ 1. Edge Flight Node (Jetson Nano / RPi 5) ]                                                     │
│   ├── Video Capture Pipeline: 640x640 RGB @ 30 FPS                                                │
│   ├── Dynamic Split Policy: Evaluates J(k, dtype) every 300 ms based on live channel state        │
│   ├── Runtime Submodel Switchboard: Routes to EdgeSubmodel (k4, k9, or Full Edge)                 │
│   └── Fused C++/CUDA Quantization: INT8 Dynamic Symmetric Quantization (S = max|X| / 127)         │
│                                           │                                                       │
│                                           ▼  (ZeroMQ IPC/TCP + Wire Framing)                      │
│ [ 2. 5G Wireless Channel Emulation ]                                                              │
│   ├── 3GPP TR 38.901 Fast Fading (UMa / UMi, Path Loss, Rayleigh/Rician, Doppler)                 │
│   ├── Asynchronous ChannelProxy & Token-Bucket Rate Limiter                                       │
│   └── Realistic Link Duty-Cycle Bounded Power Calculation                                         │
│                                           │                                                       │
│                                           ▼                                                       │
│ [ 3. Cloud GPU Inference Server ]                                                                 │
│   ├── Asynchronous Multi-Process Socket Worker                                                    │
│   ├── CRC32 Wire Frame Validation & Deserialization                                               │
│   ├── Dequantization Engine (INT8 -> FP32 / FP16 Mixed Precision)                                 │
│   └── CloudSubmodel (Layers (k+1)..22) -> Decoded Bounding Boxes & NMS                            │
└───────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Track 2: Phase 2 Preparation & Closed-Loop Dynamic Optimizer

### 2.1 Physical Duty-Cycle Bounded Power & Battery Model Correction
- Enforces physical link-capacity limits on the 5G RF Power Amplifier ($P_{\text{tx\_rf}} = 3.8\text{ W}$, $P_{\text{rx\_idle}} = 1.2\text{ W}$):
  $$\text{Capacity FPS} = \frac{B_{\text{bps}}}{\text{Payload}_{\text{bits}}} \quad (\text{for } \text{Payload} > 0)$$
  $$\text{Delivered FPS} = \min\left(\text{Target FPS}, \text{Capacity FPS}\right)$$
  $$\text{Duty Cycle}_{\text{tx}} = \min\left(1.0, \frac{\text{Delivered FPS} \times T_{\text{tx\_ms}}}{1000.0}\right)$$
  $$P_{\text{tx\_avg}} = P_{\text{tx\_rf}} \times \text{Duty Cycle}_{\text{tx}} + P_{\text{rx\_idle}} \times (1.0 - \text{Duty Cycle}_{\text{tx}})$$
  $$P_{\text{perception}} = \frac{E_{\text{edge}}(\text{mJ}) \times \text{Delivered FPS}}{1000.0} + P_{\text{tx\_avg}}$$
  $$\text{Mission Lifetime (Hours)} = \frac{\text{Battery Capacity (Wh)}}{P_{\text{avionics}} + P_{\text{perception}}}$$
- **Result**: On a $5000\text{ mAh}$ ($55.5\text{ Wh}$) 3S LiPo battery with $P_{\text{avionics}} = 15.0\text{ W}$, calculated UAV flight lifetimes range from **$2.94\text{ to }3.08\text{ hours}$** across all operational regimes.

### 2.2 TensorRT Submodel Export Pipeline (`deployment/jetson/export_trt.py`)
- Exports decoupled $k_4$ and $k_9$ submodels to ONNX format:
  - `experiments/checkpoints/yolov8s_edge_k4.onnx` ($1 \times 3 \times 640 \times 640 \to 1 \times 128 \times 80 \times 80$)
  - `experiments/checkpoints/yolov8s_cloud_k4.onnx` ($1 \times 128 \times 80 \times 80 \to 1 \times 84 \times 8400$)
  - `experiments/checkpoints/yolov8s_edge_k9.onnx` ($1 \times 3 \times 640 \times 640 \to [F_4, F_6, F_9]$)
  - `experiments/checkpoints/yolov8s_cloud_k9.onnx` ($[F_4, F_6, F_9] \to 1 \times 84 \times 8400$)
- Serializes TensorRT runtime `.engine` files into `experiments/checkpoints/`.
- Includes `TensorRTRuntimeWrapper` for seamless edge execution.

### 2.3 Production Fused C++/CUDA INT8 Quantization Kernel (`deployment/jetson/cuda_quant/`)
- `kernel.cu`:
  - `FindMaxAbsKernel`: Block-level shared memory reduction computing $M = \max |X|$.
  - `FusedQuantizeINT8Kernel`: Single-pass element-wise division by $S = M / 127.0$, rounding, clamping $[-128, 127]$, and casting directly to `int8_t`.
  - `DequantizeINT8Kernel`: Scaled transformation from `int8_t` to `float32`.
- `bindings.cpp`: Zero-copy Torch/PyBind11 extension.
- Verified exact bitwise numerical equivalence against PyTorch reference ($\max |X - \hat{X}| \le S / 2$).

### 2.4 Closed-Loop Dynamic Split Policy & Switchboard (`pipeline/dynamic_policy.py`)
- Multi-Objective Cost Function:
  $$J(k, \text{dtype}, B) = \alpha \frac{E_{\text{uav}}(k, \text{dtype}, B)}{E_{\max}} + \beta \frac{T_{\text{total}}(k, \text{dtype}, B)}{T_{\max}} + \gamma \left(1.0 - \frac{\text{mAP}(k, \text{dtype})}{\text{mAP}_{\text{baseline}}}\right) + \mathcal{P}_{\text{deadline}}(T_{\text{total}})$$
- Controls live decision making with $\Delta J \ge 0.05$ hysteresis switching guard:
  - **Constrained Bandwidth (5 Mbps)**: Full Edge ($50.0\text{ ms}$) prevents link saturation.
  - **Moderate Bandwidth (30 Mbps)**: $k_4$-INT8 ($800\text{ KiB}$) delivers optimal balance ($239.9\text{ ms}$, cost $0.3711$).
  - **High Bandwidth (100 Mbps)**: $k_4$-INT8 / $k_9$-INT8 achieves ultra-low latency ($87.0\text{ ms}$, cost $0.1498$).
  - **Blackout (0 Mbps)**: Automatic fallback to Full Edge onboard inference.

---

## 3. Master Verification Ledger (23 Modules)

| Stage | Module Name | Command Executed | Duration | Status |
| :---: | :--- | :--- | :---: | :---: |
| 1 | Graph Inspection & Topologies | `python3 core/inspect_graph.py` | 2.03s | ★ PASSED |
| 2 | Submodel Decoupling & Parity | `python3 evaluation/verify_submodels.py` | 4.04s | ★ PASSED |
| 3 | Dynamic Submodel Slicing Engine | `python3 core/dynamic_submodels.py` | 2.81s | ★ PASSED |
| 4 | Quantization & Wire Protocol | `python3 evaluation/verify_quantization.py` | 3.33s | ★ PASSED |
| 5 | ZeroMQ IPC/TCP Streaming Runtimes | `python3 evaluation/verify_pipeline_ipc.py` | 14.99s | ★ PASSED |
| 6 | COCO128 Real-World mAP Evaluation | `python3 evaluation/evaluate_mAP.py` | 14.84s | ★ PASSED |
| 7 | Statistical Micro-Benchmarking | `python3 evaluation/benchmark_suite.py` | 28.41s | ★ PASSED |
| 8 | Granular Split Pareto Benchmarking | `python3 evaluation/benchmark_split_pareto.py` | 116.00s | ★ PASSED |
| 9 | Quantization Deep Dive Benchmarking | `python3 evaluation/benchmark_quant_modes.py` | 42.23s | ★ PASSED |
| 10 | ZeroMQ Stress & Backpressure | `python3 evaluation/stress_test_zmq.py` | 24.82s | ★ PASSED |
| 11 | 3GPP 5G Trace Generator | `python3 simulation/trace_generator.py` | 0.31s | ★ PASSED |
| 12 | ChannelProxy IPC/ZMQ Broadcast | `python3 simulation/channel_proxy.py --test` | 0.59s | ★ PASSED |
| 13 | Netem Traffic Shaper Engine | `python3 simulation/netem_controller.py` | 0.03s | ★ PASSED |
| 14 | Dynamic 5G Trace Benchmark | `python3 evaluation/benchmark_5g_traces.py --quick` | 1.80s | ★ PASSED |
| 15 | Publication Artifacts Generation | `python3 evaluation/plot_artifacts.py` | 1.76s | ★ PASSED |
| 16 | 3D/2D Pareto Visualization Suite | `python3 evaluation/plot_pareto_3d.py` | 1.78s | ★ PASSED |
| 17 | Quantization Deep Dive Visualizations | `python3 evaluation/plot_quant_deepdive.py` | 4.36s | ★ PASSED |
| 18 | 5G Channel Emulation Visualizations | `python3 evaluation/plot_5g_traces.py` | 3.13s | ★ PASSED |
| 19 | UAV Energy & Power Benchmark | `python3 evaluation/benchmark_energy.py` | 0.26s | ★ PASSED |
| 20 | Publication Energy Visualizations | `python3 evaluation/plot_energy.py` | 1.85s | ★ PASSED |
| 21 | TensorRT Submodel Export Engine | `python3 deployment/jetson/export_trt.py` | 3.57s | ★ PASSED |
| 22 | Fused CUDA INT8 Kernel Parity | `python3 deployment/jetson/cuda_quant/test_cuda_quant.py` | 1.74s | ★ PASSED |
| 23 | Closed-Loop Dynamic Split Policy | `python3 pipeline/dynamic_policy.py` | 1.80s | ★ PASSED |

**Total Suite Duration**: 260.45s | **Compliance**: **100% (23/23 Stages PASSED)**
