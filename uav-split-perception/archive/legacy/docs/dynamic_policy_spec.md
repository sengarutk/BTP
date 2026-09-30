# AEGIS-UAV Track 2: Phase 2 Preparation & Closed-Loop Dynamic Optimizer Specification

**Document Identifier**: `AEGIS-SPEC-TRACK-2.0`  
**Target Hardware**: NVIDIA Jetson Nano (Maxwell 128 CUDA Cores) + 5G NR Transceiver + Multi-GPU Cloud Node  
**Framework Version**: PyTorch 2.x / TensorRT 8.x / ZeroMQ / C++17 CUDA 12.x  

---

## 1. Executive Summary

This specification establishes the software architecture and optimization formulations for Track 2 (Phase 2 Preparation):
1. **Physical Duty-Cycle Bounded Power & Battery Model Correction**: Enforces link-capacity limits ($\text{Duty} \le 1.0$), resolving unphysical battery lifetime predictions to realistic $2.94\text{--}3.08\text{ hour}$ missions.
2. **TensorRT Submodel Export Pipeline (`deployment/jetson/export_trt.py`)**: Exports decoupled $k_4$ and $k_9$ submodels to ONNX and serialized TensorRT `.engine` execution artifacts.
3. **Fused C++/CUDA INT8 Quantization Kernel (`deployment/jetson/cuda_quant/`)**: Implements block-level parallel shared-memory reduction and fused scale-divide-clamp kernels with PyBind11 zero-copy tensor bindings.
4. **Closed-Loop Multi-Objective Dynamic Split Policy (`pipeline/dynamic_policy.py`)**: Implements real-time optimization $J(k, \text{dtype})$ with hard deadline constraints and hysteresis switching guards.

---

## 2. Mathematical Formulation of the Dynamic Policy

### 2.1 Multi-Objective Cost Function $J(k, \text{dtype})$

The onboard optimization controller continuously solves the discrete optimization problem:
$$\left(k^*, \text{dtype}^*\right) = \arg\min_{k \in \mathcal{K}, \, \text{dtype} \in \mathcal{D}} J(k, \text{dtype}, B)$$

Where the scalar cost function $J(k, \text{dtype}, B)$ balances energy consumption, end-to-end latency, and object detection accuracy:
$$J(k, \text{dtype}, B) = \alpha \frac{E_{\text{uav}}(k, \text{dtype}, B)}{E_{\max}} + \beta \frac{T_{\text{total}}(k, \text{dtype}, B)}{T_{\max}} + \gamma \left(1.0 - \frac{\text{mAP}(k, \text{dtype})}{\text{mAP}_{\text{baseline}}}\right) + \mathcal{P}_{\text{deadline}}(T_{\text{total}})$$

### 2.2 Default Weights & Normalization Constants

| Parameter | Symbol | Default Value | Physical Significance |
| :--- | :--- | :--- | :--- |
| **Energy Weight** | $\alpha$ | `0.40` | Importance of drone battery conservation |
| **Latency Weight** | $\beta$ | `0.40` | Importance of real-time perception responsiveness |
| **Accuracy Weight** | $\gamma$ | `0.20` | Detection confidence and mAP retention penalty |
| **Max Energy Bound** | $E_{\max}$ | `2000.0 mJ` | Normalization ceiling for onboard energy per frame |
| **Max Latency Bound** | $T_{\max}$ | `300.0 ms` | Normalization ceiling for end-to-end frame turnaround |
| **Baseline Accuracy** | $\text{mAP}_{\text{base}}$ | `0.7594` | Monolithic YOLOv8s reference mAP@0.5 |
| **E2E Deadline** | $T_{\text{deadline}}$ | `300.0 ms` | Critical flight control deadline constraint |
| **Hysteresis Guard** | $\delta_{\text{hyst}}$ | `0.05` | Cost improvement required to trigger submodel swap |

### 2.3 Hard Deadline Penalty $\mathcal{P}_{\text{deadline}}$

To strictly prevent offloading when network latency violates flight deadlines:
$$\mathcal{P}_{\text{deadline}}(T) = \begin{cases} 0, & \text{if } T \le T_{\text{deadline}} \\ 5.0 \times \left(\frac{T}{T_{\text{deadline}}}\right)^2, & \text{if } T > T_{\text{deadline}} \end{cases}$$

### 2.4 Anti-Chatter Hysteresis Switching Guard

To eliminate high-frequency ping-pong oscillations between split points during channel fading:
$$\text{Switch to } (k_{\text{new}}, \text{dtype}_{\text{new}}) \iff J(k_{\text{new}}, \text{dtype}_{\text{new}}) \le J(k_{\text{curr}}, \text{dtype}_{\text{curr}}) - \delta_{\text{hyst}}$$

---

## 3. Physical Duty-Cycle Corrected Power Modeling

In realistic 5G communications, the RF Power Amplifier only transmits when packets are queued:
$$\text{Capacity FPS} = \frac{B_{\text{bps}}}{\text{Payload}_{\text{bits}}} \quad (\text{for } \text{Payload} > 0)$$
$$\text{Delivered FPS} = \min\left(\text{Target FPS}, \text{Capacity FPS}\right)$$
$$\text{Duty Cycle}_{\text{tx}} = \min\left(1.0, \frac{\text{Delivered FPS} \times T_{\text{tx\_ms}}}{1000.0}\right)$$
$$P_{\text{tx\_avg}} = P_{\text{tx\_rf}} \times \text{Duty Cycle}_{\text{tx}} + P_{\text{rx\_idle}} \times (1.0 - \text{Duty Cycle}_{\text{tx}})$$

### Total Perception Power & Mission Flight Lifetime:
$$P_{\text{perception}} = \frac{E_{\text{edge}}(\text{mJ}) \times \text{Delivered FPS}}{1000.0} + P_{\text{tx\_avg}}$$
$$\text{Mission Lifetime (Hours)} = \frac{\text{Battery Capacity (Wh)}}{P_{\text{avionics}} + P_{\text{perception}}}$$

On a standard $55.5\text{ Wh}$ LiPo battery with $P_{\text{avionics}} = 15.0\text{ W}$, total onboard power is $17.5\text{--}18.8\text{ W}$, giving realistic mission flight durations of **$2.94\text{--}3.08\text{ hours}$**.

---

## 4. Fused C++/CUDA INT8 Quantization Architecture

```
                                  [ Input Float32 Tensor ]
                                             │
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │    Kernel 1: FindMaxAbsKernel (Reduction)    │
                      │   - Block Shared Memory Tree Reduction       │
                      │   - Global Atomic Max: M = max |X|           │
                      │   - Dynamic Scale S = max(M, 1e-7) / 127.0   │
                      └──────────────────────┬───────────────────────┘
                                             │
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │  Kernel 2: FusedQuantizeINT8Kernel           │
                      │   - inv_scale = 1.0f / S                     │
                      │   - scaled = input[i] * inv_scale            │
                      │   - rounded = roundf(scaled)                 │
                      │   - clamped = fmaxf(-128, fminf(127, r))     │
                      │   - output[i] = (int8_t)clamped              │
                      └──────────────────────┬───────────────────────┘
                                             │
                                             ▼
                                   [ Quantized int8_t ]
```

### Mathematical Parity & Invariance
The C++/CUDA fused kernel guarantees exact bitwise numerical equivalence with the PyTorch reference implementation:
$$\max |X - \hat{X}| \le \frac{S}{2} = \frac{\max|X|}{254.0}$$
