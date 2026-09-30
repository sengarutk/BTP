# AEGIS-UAV Split Perception: Phase 1 Master Architecture & Specification

## 1. System Architecture
The **AEGIS-UAV Perception Framework** splits neural computation between constrained aerial edge platforms and high-throughput cloud receivers using hardware-aware boundary points ($k_4$, $k_9$) and dynamic symmetric quantization.

```
+-----------------------------------------------------------------------------------------+
|                                    EDGE SUBSYSTEM (UAV)                                 |
|                                                                                         |
|  [ RGB Camera ] ---> [ EdgeSubmodel ] ---> [ Quantizer ] ---> [ Wire Packet ]           |
|  (640x640x3)        (Layers 0..k)          (FP16 / INT8)      (Aegis Wire V1)           |
+---------------------------------------------------|-------------------------------------+
                                                    | (ZeroMQ PUSH/PULL Transport)
                                                    v (IPC / Wireless 5G TCP)
+-----------------------------------------------------------------------------------------+
|                                   CLOUD SUBSYSTEM (BASE)                                |
|                                                                                         |
|  [ Detections ] <--- [ Ultralytics NMS ] <--- [ CloudSubmodel ] <--- [ Deserializer ]   |
|  (Boxes, Conf)       (conf=0.25,iou=0.45)     (Layers k+1..22)       (Dequantize FP32)  |
+-----------------------------------------------------------------------------------------+
```

---

## 2. Hardened Multi-Tensor Split Topologies ($k_4$ vs. $k_9$, IEC Binary Units)

| Split Tag | Cut Layer | Topology Type | Transmitted Activations | Elements | Wire Size (FP32) | Wire Size (FP16) | Wire Size (INT8) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **$k_4$** | Layer 4 | Single Tensor | $P_3: (1, 128, 80, 80)$ | $819,200$ | $3,200.0\text{ KiB } (3.12\text{ MiB})$ | $1,600.0\text{ KiB } (1.56\text{ MiB})$ | **$800.0\text{ KiB } (0.78\text{ MiB})$** |
| **$k_9$** | Layer 9 | Multi-Scale Bundle | $P_3 (80\times 80) + P_4 (40\times 40) + P_5 (20\times 20)$ | $1,433,600$ | $5,600.1\text{ KiB } (5.47\text{ MiB})$ | $2,800.1\text{ KiB } (2.73\text{ MiB})$ | **$1,400.1\text{ KiB } (1.37\text{ MiB})$** |
| **Full** | Layer 22 | Monolithic Local | None (Local Detections) | $0$ | $0.0\text{ KiB } (0.0\text{ MiB})$ | $0.0\text{ KiB } (0.0\text{ MiB})$ | **$0.0\text{ KiB } (0.0\text{ MiB})$** |

---

## 3. Statistical Benchmarking & Crossover Frontiers (N=3 Runs, IEC Units)

| System Configuration | Edge (ms) | Quant+Framing (ms) | Dequant+Deser (ms) | Cloud (ms) | E2E Compute (ms) | Wire Size (KiB / MiB) | Total @ 20 Mbps | FPS (Compute) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Split $k_4$ (INT8)** | $1.90 \pm 0.65$ | $1.39$ | $0.80$ | $7.58 \pm 2.30$ | $22.07 \pm 13.54$ | **$800.0\text{ KiB } (0.78\text{ MiB})$** | **$349.8\text{ ms}$** | **$45.3\text{ FPS}$** |
| **Split $k_4$ (FP16)** | $1.93 \pm 0.64$ | $1.72$ | $1.31$ | $7.61 \pm 2.15$ | $21.25 \pm 5.19$ | $1,600.0\text{ KiB } (1.56\text{ MiB})$ | $676.6\text{ ms}$ | $47.1\text{ FPS}$ |
| **Split $k_4$ (FP32)** | $2.00 \pm 0.63$ | $7.85$ | $2.55$ | $7.87 \pm 2.37$ | $28.99 \pm 5.25$ | $3,200.0\text{ KiB } (3.12\text{ MiB})$ | $1339.7\text{ ms}$ | $34.5\text{ FPS}$ |
| **Split $k_9$ (INT8)** | $3.78 \pm 1.28$ | $2.77$ | $1.51$ | $5.70 \pm 1.99$ | $22.55 \pm 5.72$ | **$1,400.1\text{ KiB } (1.37\text{ MiB})$** | **$596.0\text{ ms}$** | **$44.3\text{ FPS}$** |
| **Split $k_9$ (FP16)** | $3.95 \pm 1.14$ | $3.37$ | $2.39$ | $5.86 \pm 2.02$ | $24.71 \pm 7.68$ | $2,800.1\text{ KiB } (2.73\text{ MiB})$ | $1171.6\text{ ms}$ | $40.5\text{ FPS}$ |
| **Split $k_9$ (FP32)** | $3.58 \pm 1.26$ | $12.76$ | $4.22$ | $5.42 \pm 1.61$ | $34.11 \pm 6.35$ | $5,600.1\text{ KiB } (5.47\text{ MiB})$ | $2327.9\text{ ms}$ | $29.3\text{ FPS}$ |
| **Monolithic (Workstation GPU)** | $8.04 \pm 2.32$ | $0.00$ | $0.00$ | $0.00$ | $16.29 \pm 4.47$ | $0.0\text{ KiB } (0.0\text{ MiB})$ | $16.3\text{ ms}$ | $61.4\text{ FPS}$ |
| **Full Edge (Estimated Compute x5.5)**| $44.21 \pm 12.76$ | $0.00$ | $0.00$ | $0.00$ | $89.59 \pm 24.59$ | $0.0\text{ KiB } (0.0\text{ MiB})$ | $89.6\text{ ms}$ | **$11.2\text{ FPS}$** |

---

## 4. ZeroMQ High-Rate Stress & Backpressure Evaluation ($N_{\text{warmup}}=15$ Exempted)

| Test Scenario | Target Stream Rate | Frames (Sent / Dropped / Received) | Delivery Rate | Steady Jitter | Process RAM | CPU Load | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Burst Rate (IPC)** | $60\text{ FPS}$ | $300\text{ / }0\text{ / }300$ | $100.0\%$ | **$0.34\text{ ms}$** | $513.8\text{ MiB}$ | $12.4\%$ | **★ PASSED** |
| **Ultra-Burst (TCP)** | $120\text{ FPS}$ | $300\text{ / }0\text{ / }300$ | $100.0\%$ | **$0.23\text{ ms}$** | $513.8\text{ MiB}$ | $7.3\%$ | **★ PASSED** |
| **Backpressure (HWM=5, 50ms Delay)** | $60\text{ FPS}$ | $110\text{ / }190\text{ / }106$ | $35.3\%$ (Safe Drop) | **$1.12\text{ ms}$** | $513.8\text{ MiB}$ | $8.4\%$ | **★ PASSED** |

---

## 5. Failure Modes, Error Handling & Recovery Protocols

The AEGIS-UAV perception architecture enforces deterministic fail-safe recovery protocols across all pipeline stages:

### 5.1 CRC32 Checksum Corruption
- **Failure Trigger**: Packet transmission corruption across lossy wireless RF links.
- **Handling Protocol**:
  The cloud receiver deserializer recalculates the IEEE 802.3 32-bit CRC across the packet body. If `actual_crc != expected_crc`, the corrupted frame is **immediately dropped**, a diagnostic warning is logged, the drop counter is incremented, and the PULL consumer loop remains non-blocking to service the next incoming frame.

### 5.2 Network Queue Saturation & Backpressure
- **Failure Trigger**: Wireless transmission bandwidth throttling or cloud consumer processing stalls.
- **Handling Protocol**:
  Edge PUSH sockets are configured with High Water Mark (`HWM=10` or `HWM=5`) and non-blocking transmission (`zmq.NOBLOCK`). When socket buffers saturate, `AegisZMQPublisher.send_packet()` catches `zmq.Again`, drops the oldest overflow frame, and logs a throttled warning. Heap memory and RSS RAM remain bounded without unbounded buffer queuing or OOM crashes.

### 5.3 Non-Finite Value Injection (NaN / ±Inf)
- **Failure Trigger**: Numerical gradient anomalies, sensor saturation, or zero-division at edge inference.
- **Handling Protocol**:
  `FeatureMapQuantizer` executes pre-quantization tensor validation via `torch.isfinite(x)`. If non-finite values are detected, a sanitized exception is caught, scale calculation defaults to safe bounded fallbacks, and the cloud pipeline safely yields an empty detection tensor without kernel panics.

### 5.4 Transport Connection Disruption & Link Flapping
- **Failure Trigger**: Transient UAV wireless disconnects or base station IP migrations.
- **Handling Protocol**:
  Sockets configure `zmq.LINGER=0` for instant teardown without socket blocking. ZeroMQ background I/O threads handle automatic reconnection with exponential backoff while keeping the edge inference pipeline responsive.

---

## 6. Verification Suite Summary
All 8 verification test suites run under `python3 evaluation/run_phase1_master_test.py`:
1. `core/inspect_graph.py`
2. `evaluation/verify_submodels.py`
3. `evaluation/verify_quantization.py`
4. `evaluation/verify_pipeline_ipc.py`
5. `evaluation/evaluate_mAP.py`
6. `evaluation/benchmark_suite.py`
7. `evaluation/stress_test_zmq.py`
8. `evaluation/plot_artifacts.py`
