# AEGIS-UAV Neural Model Split Specification

## 1. Graph Inspection & Partitioning Overview
YOLOv8s is comprised of 23 sequential layer modules (Backbone: Layers 0–9, Neck: Layers 10–21, Detection Head: Layer 22).

---

## 2. Comprehensive 8-Point Candidate Split Topologies ($k \in \{2, 4, 5, 7, 9, 12, 15, 18\}$)

| Split Tag | Cut Layer | Partition Location | Required Transmitted Layers | Elements | INT8 Wire Size | Edge Params (%) | Structural Characterization |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **$k_2$** | Layer 2 | Early Backbone | $L_2$ | $1,638,400$ | $1,600.0\text{ KiB } (1.56\text{ MiB})$ | $0.4\%$ | Large wire footprint ($1.56\text{ MiB}$); minimal edge compute relief. |
| **$k_4$** | Layer 4 | Mid Backbone ($P_3$) | $L_4$ ($P_3$) | $819,200$ | **$800.0\text{ KiB } (0.78\text{ MiB})$** | **$2.9\%$** | **Pareto Optimal**: Minimal single-tensor wire footprint. |
| **$k_5$** | Layer 5 | Mid Backbone | $L_4, L_5$ | $1,228,800$ | $1,200.0\text{ KiB } (1.17\text{ MiB})$ | $5.5\%$ | Dominated by $k_4$ (larger payload with negligible edge relief). |
| **$k_7$** | Layer 7 | Deep Backbone | $L_4, L_6, L_7$ | $1,433,600$ | $1,400.1\text{ KiB } (1.37\text{ MiB})$ | $23.1\%$ | Dominated by $k_9$ (same payload size, but $k_9$ finishes full backbone). |
| **$k_9$** | Layer 9 | Complete Backbone | **k9 Multi-Scale Bundle (L4 + L6 + L9)** | $1,433,600$ | **$1,400.1\text{ KiB } (1.37\text{ MiB})$** | **$45.5\%$** | **Pareto Optimal**: Offloads 100% of spatial backbone compute. |
| **$k_{12}$** | Layer 12 | Top-Down Neck | $L_4, L_{12}$ | $1,433,600$ | $1,400.1\text{ KiB } (1.37\text{ MiB})$ | $54.3\%$ | Intermediate neck cut; high edge memory buffering. |
| **$k_{15}$** | Layer 15 | Bottom Neck ($P_3$ Out) | $L_{12}, L_{15}$ | $1,433,600$ | $1,400.1\text{ KiB } (1.37\text{ MiB})$ | $62.7\%$ | Fuses top-down path; retains multi-tensor payload. |
| **$k_{18}$** | Layer 18 | Bottom-Up Neck | $L_9, L_{15}, L_{18}$ | $1,433,600$ | $1,400.1\text{ KiB } (1.37\text{ MiB})$ | $76.3\%$ | Deep neck cut; dominated by full edge or $k_9$. |
| **Full** | Layer 22 | Monolithic Local | None (Local Detections) | $0$ | **$0.0\text{ KiB } (0.0\text{ MiB})$** | **$100.0\%$** | Local inference with zero wireless transmission. |

---

## 3. Explicit Multi-Scale Bundle Taxonomy for $k_9$ (L4 + L6 + L9)

The $k_9$ split requires transmitting intermediate multi-scale activations from three distinct backbone hierarchy levels:
1. **$L_4$ ($P_3$ at stride 8)**: Shape $(1, 128, 80, 80) \to 819,200\text{ elements}$ ($800.0\text{ KiB}$ INT8, $3,200.0\text{ KiB}$ FP32)
2. **$L_6$ ($P_4$ at stride 16)**: Shape $(1, 256, 40, 40) \to 409,600\text{ elements}$ ($400.0\text{ KiB}$ INT8, $1,600.0\text{ KiB}$ FP32)
3. **$L_9$ ($P_5$ at stride 32)**: Shape $(1, 512, 20, 20) \to 204,800\text{ elements}$ ($200.0\text{ KiB}$ INT8, $800.0\text{ KiB}$ FP32)

**Total Multi-Scale Bundle**:
$$1,433,600\text{ elements} \to \mathbf{1,400.1\text{ KiB } (1.37\text{ MiB})}\text{ in INT8} \quad / \quad \mathbf{5,600.1\text{ KiB } (5.47\text{ MiB})}\text{ in FP32}$$

---

## 4. Pareto Optimality Proofs & Structural Dominance Analysis

### Theorem 1: $k_4$ Optimality for Bandwidth-Constrained Links ($< 20\text{ Mbps}$)
- At $k_4$, only the $P_3$ activation ($80\times 80\times 128$) is required downstream. Downstream convolutions downsample spatial dimensions before subsequent branching occurs.
- INT8 payload is **$800.0\text{ KiB}$**, which is **$42.9\%$ smaller** than the $k_9$ multi-scale bundle ($1,400.1\text{ KiB}$).
- Under $5\text{ Mbps}$ wireless uplink, $k_4\text{-INT8}$ achieves total latency of $1,319.4\text{ ms}$ vs. $2,305.7\text{ ms}$ for $k_9\text{-INT8}$ ($42.8\%$ faster).

### Theorem 2: $k_9$ Optimality for Compute-Constrained Edge Platforms
- At $k_9$, the complete feature extraction backbone (Layers 0–9 including SPPF) is computed on the edge ($45.5\%$ of model parameters).
- The intermediate activations $P_3 (80\times 80), P_4 (40\times 40), P_5 (20\times 20)$ total $1,433,600$ elements ($1,400.1\text{ KiB}$ in INT8).
- Intermediate cuts $k_5, k_7, k_{12}$ require transmitting 2 or 3 tensors with equal or higher payload footprint without completing the backbone feature extraction, making them strictly Pareto-dominated by $k_4$ and $k_9$.
