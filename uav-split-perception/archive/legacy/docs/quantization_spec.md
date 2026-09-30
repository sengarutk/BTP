# AEGIS-UAV Quantization & Wire Protocol Specification

## 1. Mathematical Framework & Quantization Schemes

The AEGIS-UAV Split Perception framework supports 5 distinct precision paradigms across the Edge-Cloud boundary:

1. **FP32 (Baseline)**: IEEE 754 32-bit single-precision floating point (4 bytes/element).
2. **FP16 (Half-Precision)**: IEEE 754 16-bit half-precision floating point (2 bytes/element).
3. **INT8 Per-Tensor Dynamic Symmetric Quantization**: Uniform symmetric 8-bit integer quantization with 1 global scale factor per feature map tensor (1 byte/element + 4 bytes scale metadata).
4. **INT8 Per-Channel Dynamic Symmetric Quantization**: Fine-grained channel-wise symmetric 8-bit integer quantization with dedicated scale vector $S \in \mathbb{R}^C$ (1 byte/element + $4 \times C$ bytes scale metadata).
5. **INT8 Transmission with FP16 Cloud Accumulation**: INT8 wire payload dequantized into `torch.float16` for half-precision Cloud Submodel inference (50% reduction in Cloud VRAM).

---

## 2. Dynamic Symmetric Quantization Formulations

### 2.1 Per-Tensor Symmetric INT8 Quantization

For an intermediate activation tensor $X \in \mathbb{R}^{B \times C \times H \times W}$:

$$M = \max_{b, c, h, w} |X_{b, c, h, w}|$$

$$S = \begin{cases} \frac{M}{127.0}, & \text{if } M \ge 10^{-6} \\ 1.0, & \text{if } M < 10^{-6} \end{cases}$$

$$X_{\text{INT8}} = \text{clamp}\left(\left\lfloor \frac{X}{S} \right\rceil, -128, 127\right)$$

$$\hat{X} = X_{\text{INT8}} \times S$$

#### Point-Wise Error Bound:
$$\Vert{}X - \hat{X}\Vert{}_\infty \le \frac{S}{2}$$

---

### 2.2 Per-Channel Symmetric INT8 Quantization

In deep feature representations, different feature channels exhibit wide variations in dynamic ranges. Per-Channel quantization computes individual scale factors for each channel $c \in [0, C-1]$:

$$M_c = \max_{b, h, w} |X_{b, c, h, w}| \quad \forall c \in [0, C-1]$$

$$S_c = \begin{cases} \frac{M_c}{127.0}, & \text{if } M_c \ge 10^{-6} \\ 1.0, & \text{if } M_c < 10^{-6} \end{cases} \quad (S \in \mathbb{R}^{1 \times C \times 1 \times 1})$$

$$X_{\text{INT8}} = \text{clamp}\left(\left\lfloor \frac{X}{S} \right\rceil, -128, 127\right)$$

$$\hat{X} = X_{\text{INT8}} \times S$$

#### Channel-Wise Error Bound Theorem:
$$\Vert{}X_{c,:,:} - \hat{X}_{c,:,:}\Vert{}_\infty \le \frac{S_c}{2} \quad \forall c \in [0, C-1]$$

*Proof*: For any element $x \in X_{c, :, :}$, the scaled value $u = \frac{x}{S_c} \in [-127.0, 127.0]$. The rounding operation satisfies $|u - \lfloor u \rceil| \le 0.5$. Since clamping is non-expansive for $|u| \le 127.0$:
$$|x - \hat{x}| = S_c \cdot \left|\frac{x}{S_c} - \left\lfloor \frac{x}{S_c} \right\rceil\right| \le S_c \cdot 0.5 = \frac{S_c}{2} \quad \blacksquare$$

---

## 3. Reconstruction Fidelity Metrics

To quantify reconstruction quality across quantization schemes, we formulate:

1. **Max Absolute Error ($L_\infty$ Norm)**:
   $$\Delta_{\max} = \max_{i} |X_i - \hat{X}_i|$$

2. **Mean Squared Error (MSE)**:
   $$\text{MSE} = \frac{1}{N} \sum_{i=1}^N (X_i - \hat{X}_i)^2$$

3. **Signal-to-Quantization-Noise Ratio (SQNR in dB)**:
   $$\text{SQNR (dB)} = 10 \log_{10} \left(\frac{\sum_{i=1}^N X_i^2}{\sum_{i=1}^N (X_i - \hat{X}_i)^2}\right)$$

4. **Cosine Similarity**:
   $$\cos(X, \hat{X}) = \frac{X \cdot \hat{X}}{\Vert{}X\Vert{}_2 \, \Vert{}\hat{X}\Vert{}_2}$$

---

## 4. Binary Wire Framing Protocol & Memory Layout

The `AegisPacketProtocol` packs tensor descriptors and per-channel scale vectors into contiguous little-endian buffers with CRC32 checksums.

### 4.1 Packet Layout

```
+-----------------------------------------------------------------------+
|                       PRIMARY HEADER (16 Bytes)                       |
| uint8_t version | uint32_t frame_id | uint64_t timestamp_ms           |
| uint8_t split_code | uint8_t num_tensors | uint8_t reserved           |
+-----------------------------------------------------------------------+
|                     TENSOR DESCRIPTORS (16 Bytes each)                 |
| uint8_t layer_idx | uint8_t dtype_code | uint16_t C | H | W           |
| float32_t mean_scale_factor | uint32_t payload_len                    |
+-----------------------------------------------------------------------+
|                           PAYLOAD DATA                                |
| For Per-Channel INT8 (dtype_code = 3):                                |
|   - Scale Vector: float32_t scale[C] (4 * C Bytes)                    |
|   - Quantized Tensor: int8_t data[C * H * W] (C * H * W Bytes)        |
| For Per-Tensor INT8 / FP16 / FP32:                                    |
|   - Raw Contiguous Tensor Bytes                                       |
+-----------------------------------------------------------------------+
|                       CRC32 TRAILER (4 Bytes)                         |
| uint32_t crc32 (IEEE 802.3 Ethernet Polynomial 0xEDB88320)           |
+-----------------------------------------------------------------------+
```

### 4.2 Codec Identifiers

| `dtype_code` | Identifier | Storage Layout | Scale Metadata |
| :--- | :--- | :--- | :--- |
| `0` | `fp32` | 4 bytes / float | None |
| `1` | `fp16` | 2 bytes / half | None |
| `2` | `int8_per_tensor` | 1 byte / int8 | 1 float in Descriptor |
| `3` | `int8_per_channel` | 1 byte / int8 | $C$ floats prepended in payload |
| `4` | `int8_fp16_accum` | 1 byte / int8 | 1 float in Descriptor |

---

## 5. Experimental Benchmark Results (COCO128 Validation)

```
========================================================================================================================
                 AEGIS-UAV QUANTIZATION DEEP DIVE BENCHMARK (COCO128)
========================================================================================================================
| Configuration                    | mAP@0.5 | Δ_rel (%)   | Δ_max  | SQNR     | Cosine Sim | Wire Footprint        | Compute Lat (ms) |
| :------------------------------- | :------ | :---------- | :----- | :------- | :--------- | :-------------------- | :--------------- |
| Monolithic - FP32 (Base YOLOv8s) | 0.4140  | 0.00% (Ref) | 0.0000 | 120.0 dB | 1.0000     | 0.0 KiB               | 6.81 ± 0.31      |
| K4 - FP32                        | 0.4140  | +0.00%      | 0.0000 | 120.0 dB | 1.0000     | 3200.0 KiB (3.13 MiB) | 12.89 ± 0.22     |
| K4 - FP16                        | 0.4156  | +0.39%      | 0.0019 | 73.6 dB  | 1.0000     | 1600.0 KiB (1.56 MiB) | 10.10 ± 0.26     |
| K4 - INT8 (Per-Tensor)           | 0.4146  | +0.14%      | 0.0250 | 30.0 dB  | 0.9995     | 800.0 KiB (0.78 MiB)  | 8.05 ± 0.33      |
| K4 - INT8 (Per-Channel)          | 0.4154  | +0.34%      | 0.0250 | 40.4 dB  | 1.0000     | 800.5 KiB (0.78 MiB)  | 8.68 ± 0.43      |
| K4 - INT8 -> FP16 Accum          | 0.4152  | +0.29%      | 0.0264 | 30.0 dB  | 0.9995     | 800.0 KiB (0.78 MiB)  | 9.23 ± 0.83      |
| K9 - FP32                        | 0.4140  | +0.00%      | 0.0000 | 120.0 dB | 1.0000     | 5600.1 KiB (5.47 MiB) | 19.49 ± 1.15     |
| K9 - FP16                        | 0.4129  | -0.27%      | 0.0019 | 73.4 dB  | 1.0000     | 2800.1 KiB (2.73 MiB) | 14.37 ± 0.49     |
| K9 - INT8 (Per-Tensor)           | 0.4166  | +0.63%      | 0.0250 | 34.2 dB  | 0.9998     | 1400.1 KiB (1.37 MiB) | 9.98 ± 0.30      |
| K9 - INT8 (Per-Channel)          | 0.4162  | +0.53%      | 0.0250 | 44.9 dB  | 1.0000     | 1403.6 KiB (1.37 MiB) | 11.68 ± 0.53     |
| K9 - INT8 -> FP16 Accum          | 0.4166  | +0.63%      | 0.0264 | 34.2 dB  | 0.9998     | 1400.1 KiB (1.37 MiB) | 12.17 ± 0.48     |
========================================================================================================================
```

### Key Insights:
1. **Per-Channel Fidelity Boost**: Per-Channel INT8 increases SQNR by **$+10.4\text{ dB}$ on $k_4$** ($30.0 \rightarrow 40.4\text{ dB}$) and **$+10.7\text{ dB}$ on $k_9$** ($34.2 \rightarrow 44.9\text{ dB}$), achieving Cosine Similarity $= \mathbf{1.0000}$ with an overhead of only $0.5\text{ KiB}$ ($k_4$) and $3.5\text{ KiB}$ ($k_9$).
2. **Detection Robustness**: All INT8 variants achieve $|\Delta_{\text{rel}}\%| \le 1.0\%$, with slight positive regularization benefits near confidence thresholds.
3. **FP16 Accumulation Efficiency**: Matches TensorRT FP16 execution semantics with half-precision Cloud compute, delivering identical detection parity while halving Cloud activation VRAM.
