# Phase 0 novelty check (11 Oct 2026)

Closest prior work for the publication plan's main idea (docs/publication_plan.md), read beyond the
abstract where available. Still to do before submission: full read of Chanakya, OffloaD and Sela et al.,
and CrossRef verification of every citation (the crossref MCP server failed to connect this session).

## What we found

| Work | What it does | Overlap with us | What it lacks that we have |
| --- | --- | --- | --- |
| **AccuMO** (Kong, Xu, Meng, Hu; MobiCom 2023), full text read | Multitask offloading for mobile AR (depth estimation, odometry). Lightweight task-specific models **predict the accuracy drop as a function of offloading frequency and frame content**. Observation K1: "local tracking accuracy drop rates are content-dependent" (odometry's drop rate depends on camera angular velocity). MPC over a 30-frame horizon balances offloading among tasks; a per-task loop switches between local tracking and a local algorithm | **High.** Content- and motion-dependent accuracy decay of stale results, used to schedule offloading, is AccuMO's core idea | One edge server, phones, AR tasks (not detection, not streaming AP). No energy pricing, no thermal model, no heterogeneous tiers (onboard / airborne edge / ground), no link-failure risk (p_on), no aerial video |
| **Qiu et al.**, "Optimizing Edge Offloading Decisions for Object Detection" (SEC 2024, arXiv 2410.18919) | Embedded device with an onboard detector; per image, a **reward** = estimated accuracy gain from offloading, estimated from local detections only; offload the highest-reward images under a limited edge capacity | **Medium-high.** Per-frame value of offloading for detection | No staleness or forecasting, no streaming metric, two tiers, no energy or thermal |
| **Chanakya** (Ghosh et al.; NeurIPS 2023) | Learned runtime decisions (resolution, model, etc.) for streaming perception, using intrinsic (content) and extrinsic (system load) context; reward balances accuracy and latency | **Medium.** Context-aware decisions under the streaming paradigm | On-device configuration choice, not offloading across tiers; no energy or thermal; learned (RL) rather than measured-decay objective |
| **OffloaD** (Gómez et al.; ACM TECS 2024) | Offload when the on-device detector is likely to fail, combined with network conditions; physical testbed | Medium: a detection-specific offload trigger | No staleness, no energy or thermal; two tiers |
| **LEAF + AIO** (Wang et al.; IEEE TMC 2022) | Edge-assisted energy-aware detection for mobile AR: weighted sum of device energy and IoU accuracy; picks the offloading frequency | **Medium on energy**: energy vs accuracy for offloaded detection | No thermal, no staleness decay, no heterogeneous tiers, fixed weights instead of a measured power budget |
| A2-UAV (2023), E3-UAV (2023), 5G drone offload study (2024) | Edge-assisted UAV detection with Pi / Jetson boards; energy-efficient UAV detection | Low-medium: UAV + boards | Not staleness-driven, no thermal control |

Searches for "thermal-aware" + "offloading" + "detection" + "power budget / dual ascent" found **no paper
combining thermal throttling with offloading decisions** for detection; the nearest are Lyapunov
energy-budget offloading papers (no accuracy or heat) and Phoenix (thermal-aware *on-device* multi-DNN
inference, ACM TECS 2026, no offloading).

## Consequence for our claims

1. **Do not claim** "a scheduler driven by a content/motion-dependent accuracy decay" as new: AccuMO did
   this for AR. Our new measurement (camera ego-motion changes the aerial decay ~2x, decay_context.py)
   is *consistent with* AccuMO's K1 and must be presented as such.
2. **What remains distinct, and becomes the headline:** pricing a refresh by its decayed value **jointly
   with the energy it costs on each drone and the heat it adds**, on a heterogeneous three-tier aerial
   system with link-failure risk. The measured mechanism no prior paper reports: pricing energy *raised*
   accuracy (+0.0074 sAP, 17/20 pairs) because it kept the fanless camera out of thermal throttling
   (time >= 80 °C: 76 % -> 17 %). Plus whole-swarm energy accounting (the airborne edge drone's cost).
3. Positioning sentence: *AccuMO and Qiu et al. decide when an offload is worth it in accuracy; we show
   that on a drone the same decision must also be priced in joules and degrees, and that doing so changes
   the decision and improves accuracy.*
4. Baselines to implement (Phase 2): an AccuMO-style decay-rate scheduler without energy/heat (this is
   essentially our v3 + context, so it is the "accuracy-only value" ablation), a Qiu-style per-frame
   reward, OffloaD-style failure trigger, LEAF-style fixed-weight energy-accuracy sum (vs our measured
   budget with dual ascent).

## Sources
- AccuMO: https://ranger.uta.edu/~jmeng/pubs/mobicom23.pdf (DOI 10.1145/3570361.3592531)
- Qiu et al.: https://arxiv.org/abs/2410.18919
- Chanakya: https://proceedings.neurips.cc/paper_files/paper/2023/hash/ae2d574d2c309f3a45880e4460efd176-Abstract.html
- OffloaD: https://doi.org/10.1145/3677321
- LEAF + AIO: https://arxiv.org/pdf/2205.13770
- A2-UAV: https://arxiv.org/pdf/2301.06363 ; E3-UAV: https://arxiv.org/pdf/2308.04774 ;
  5G drone offloading: https://arxiv.org/pdf/2403.19729

## Phase 1 result that changes the plan (decay_context.py, 11 Oct)

Decay of stale detections split by live-computable context (VisDrone-VID, tertile thresholds fixed on
train, checked on the 7 held-out val sequences; files experiments/results/hardware/decay_context_*.json):

| Share of fresh AP kept at 100 ms (val) | fast camera (> 48 px/s) | slow / medium camera |
| --- | --- | --- |
| no forecasting | 13 % | 47–50 % |
| forecaster v1 (velocity only) | 25 % | 68–71 % |
| forecaster v2 (camera-motion aligned) | **79 %** | 80–86 % |

- Without alignment the decay depends strongly on camera motion (as AccuMO's K1 found for AR odometry).
- **With camera-motion alignment that dependence disappears**: one global curve predicts the held-out
  per-context decay better than per-context curves (mean abs. error 0.046 global vs 0.054 conditioned
  for ego-motion; 0.040 vs 0.077 for small-object share). Without forecasting, conditioning on ego-motion
  helps (0.075 -> 0.031), as expected.
- The v2 global curve transfers from train to val: kept 85 % / 58 % at 100 / 267 ms on train,
  82 % / 52 % on val.
- Caveat: 8 train and 7 val sequences (only 8 of VisDrone-VID's 56 train sequences are downloaded); the
  fast-camera val tertile has 195 captures.

Consequences:
1. **Drop context-conditioned decay from v5** (plan decision point after Phase 1). v5 = v4.2 + a smooth
   thermal price.
2. A new, clean differentiator from AccuMO: AccuMO needs per-task content-feature predictors of the drop
   rate; on aerial video, aligning for camera motion makes a single measured curve sufficient, so the
   scheduler needs no learned predictor. This is a measurement claim we can support with these numbers.
