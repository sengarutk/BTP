# Related-work check, 16 Nov 2026 (plan Phase 7: 2025-2026 work and the claims the mesh sessions added)

Scope: what was published since the Novelty Brief's check (12 Nov 2026), and the prior work for the claims added by
the 14-16 Nov mesh sessions (T6/C swarm sharing one channel, S6 pull-one-ahead, G guard overshoot, T10 break-even
on a Pi 5). Web search, 16 Nov 2026 01:10-01:13 IST. Each entry: what it is, and what it changes for our claims.

## New closest work

| Work | What it does | Consequence |
|---|---|---|
| Sun, Li, Kloda, Abdelzaher, Caccamo, "AI Inference in the Heat", RTAS 2026 (pp. 247-260, DOI 10.1109/RTAS68450.2026.00031) | thermal-aware strict partitioning of real-time gang tasks on low-end embedded boards without cooling (fans would disturb acoustic/vibration sensing); deadline misses from firmware throttling | **cite in paper 2** as the closest heat work. It is single-device real-time scheduling: no offloading, no network, no streaming accuracy. Our heat claim stays: heat priced inside a three-tier offloading controller, scored as streaming accuracy, with the guard's overshoot measured. Their motivation (no fan on the board) matches our stated limitation (T5 airflow not tested) and supports it |
| Du, Xu, Yu, "Joint Scheduling of Sensing Data Offloading and Edge Inference for Multi-UAV Networks", arXiv 2605.03898 (May 2026) | several UAVs upload sensing streams to one edge server running a multi-branch DNN; genetic-algorithm schedulers minimise end-to-end latency; simulation | **cite in paper 2** (swarm section). Simulation only, latency only, no UAV energy or heat, no shared-channel measurement. Our T6/C/S6 results are measured on two camera drones and two edge drones sharing one channel |

## Prior work for the claims added by the mesh sessions

| Our result | Prior work | Framing |
|---|---|---|
| S6: a pull-one-ahead coordinator holds a shared channel at capacity (20-22 on-time/s at 8 streams vs 2.9-3.7 for v4.1's rule) | receiver-driven transport in datacentres: NDP (Handley et al., SIGCOMM 2017), Homa (Montazeri et al., SIGCOMM 2018); token-bucket rate control for edge offloading (2020, arXiv 2010.13737); multi-stream bandwidth fairness for video analytics (BiSwift, arXiv 2312.15740); AoPI-optimal joint bandwidth allocation (arXiv 2406.14820) | **not a new mechanism**: an application of receiver-driven scheduling to a shared drone channel, measured. Claim the measurement (6-7×, and the failure of per-camera rules, C.1-C.3), not the idea. Fairness is not claimed (S6.5) |
| T6, C: on one shared channel a second edge drone costs accuracy; a per-camera cap does not fix it | multi-user offloading under channel contention is NP-hard centrally, game-theoretic distributed schemes (Chen et al., multi-channel wireless contention; ~2016-2018) | consistent with that line: contention is a swarm-wide problem; our contribution is measuring it on a real mesh with streaming accuracy and showing a per-camera rule cannot see it |
| G: the hard guard's peak overshoots by up to 3.9 °C (fast thermal mode) | Pi 4 throttling under CNN load (arXiv 2010.06291, hysteresis active cooling); thermal-aware CPU-GPU scheduling (6-12 °C lower peak, ACM TECS 2019); Tan & Cao TMC 2024 (NPU/GPU choice by thermal state) | Theorem 3 (b) with a measured δ_fast is a small, honest refinement; claim the measurement on a Pi 5 inside offloading, not a new thermal model |
| T10: no break-even goodput for learned split codes on a Pi 5 camera; on a shared-radio (token-bucket) link the 4 KB code wins at 0.5 Mbit/s | SC2 benchmark (Matsubara et al.); supervised compression (WACV 2022: earlier splits barely beat codecs); HECS-B (arXiv 2504.15295, beats JPEG across bandwidths in its setup); embedded traffic-camera split inference (ACM 2025, delay on a fixed 100 Mbit/s link) | none sweeps goodput on embedded hardware against a JPEG family with predictions first, or separates a rate-limited from a shared link. Claim: the end-to-end result depends on the camera's compute and on how the link is slow; rate-accuracy wins (prior work) do not imply end-to-end wins |

## No new work found for

- Energy- and heat-priced offloading of drone video scored with streaming accuracy (the core of paper 2): searches for
  energy/thermal-aware drone video offloading with freshness returned only older work already cited (DroneCOCoNet
  2021, energy-aware multi-UAV offloading ~2019, AoI-energy UAV data collection 2023). The narrow claim of the Novelty
  Brief stands.

## Actions for Phase 9

1. Paper 2 related work: add RTAS 2026 (heat), arXiv 2605.03898 (multi-UAV), NDP/Homa + BiSwift (S6 framing).
2. Paper 2 swarm section: S6 written as "receiver-driven scheduling, measured on a drone mesh"; C.1-C.3 as a negative
   result; fairness not claimed.
3. Paper 1: cite HECS-B and the embedded split-inference paper; state T10's link-type dependence.
4. Verify every new citation's metadata with Crossref before submission. Done 16 Nov (api.crossref.org, arxiv.org): Sun_2026's full title is "AI Inference in the Heat: Thermal-Aware Strict Partitioning for Configurable Real-Time Gang Tasks" (corrected in paper2/references.bib); Handley_2017, Montazeri_2018 and Du_2026 match their records.

Sources: https://dblp.org/db/conf/rtas/rtas2026.html ; https://arxiv.org/abs/2605.03898 ; https://arxiv.org/abs/2010.06291 ;
https://arxiv.org/html/2504.15295 ; https://arxiv.org/pdf/2312.15740 ; https://arxiv.org/pdf/2406.14820 ;
https://arxiv.org/pdf/2010.13737.pdf ; https://dl.acm.org/doi/10.1145/3763400.3763445 ; https://dl.acm.org/doi/abs/10.1145/3358235
