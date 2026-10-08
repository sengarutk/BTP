# Novelty check: closest prior work and the claims we can make

Status as of the literature check of 5 Oct 2026, re-checked 7 Oct 2026 after the forecasting, controller and swarm work. Every row is to be verified against the full papers
before submission.

## Closest prior work

| Work | What it does | How we differ |
|---|---|---|
| Elf (MobiCom 2021) | Partitions each high-resolution frame into regions and offloads them to several edge servers in parallel | Our scheduler places whole frames across heterogeneous tiers (the UAV CPU, an airborne edge GPU, a ground GPU) and picks model, resolution and codec quality per frame and per server under link uncertainty. Elf parallelises one frame's inference over homogeneous edge servers |
| Chameleon, AWStream, configuration-and-bandwidth adaptation (e.g. IEEE TNSE 2022) | Adapt resolution, frame rate and model to the available bandwidth on one path | We adapt across several paths and onboard at once, and the objective is streaming accuracy on aerial video rather than per-frame accuracy. Re-implemented as the `abr:<path>` baseline |
| Wang et al., "Bandwidth-efficient live video analytics for drones via edge computing" (SEC 2018); hybrid onboard plus edge | Onboard early-discard and filtering to save bandwidth on the way to the edge | They reduce bandwidth for one edge path; we schedule frames across tiers and fall back to onboard models in blackouts. Rule-based switching is re-implemented as `rule_fallback` |
| Context-aware or online-learning offloading (e.g. IEEE TMC 2024), DRL offloading for UAV-MEC | Choose offload or local per frame, usually in simulation or for one edge | We run on real hardware with three tiers, controlled impairments and repeated runs, and use an explicit uncertainty-aware value with no training |
| Streaming perception: Li, Wang and Ramanan (ECCV 2020); StreamYOLO (CVPR 2022) | Define streaming AP; forecast to compensate latency on one device | We use sAP to evaluate a distributed UAV system. We measure that aerial detections lose 18 % of AP after 33 ms and 58 % after 100 ms (VisDrone-VID), and design the scheduler around that decay |
| Neurosurgeon, split computing (Matsubara et al., Kang et al.) | Choose a DNN split point between device and server | Our hardware study shows that no split of YOLOv8s beats JPEG offload on any measured link. The scheduler therefore works on whole-model placement and content variants |
| Odessa (MobiSys 2011) | Adaptive offloading and parallelism decisions across device and server for interactive perception | Adaptive device-plus-server use is not new; our contribution is the measured evidence on drone tiers with sAP |
| Glimpse (SenSys 2015); Liu et al., edge-assisted detection for mobile AR (MobiCom 2019) | Track objects on the device from stale server results (active cache; motion vectors) to hide offloading latency | Latency-compensating tracking is not new. New: the measured aerial decay with and without correction, and using the post-forecasting decay as the scheduler's objective |
| PVT / PVT++ (ICCV 2023) | Latency-aware prediction for UAV single-object tracking (Kalman baselines, learned predictor) | Latency forecasting on UAVs exists; ours is for offloaded multi-object detection in a distributed system |
| BoT-SORT (2022) | Camera-motion compensation by sparse optical flow and a RANSAC affine fit in a tracker | Our ego-motion estimate (egomotion.py) is the same standard technique |
| JCAB (INFOCOM 2020; IEEE/ACM ToN 2022) | Joint configuration adaptation and bandwidth allocation for several cameras sharing one uplink | Shared-link coordination is not new; ours is admission with radio link health, calibrated to hardware, simulation-only gains |

## Claims we can support (updated 7 Oct 2026)

1. Measured negative result: no split of YOLOv8s beats JPEG offload across 1,150 placements over a Pi 5,
   a Jetson Orin Nano and a ground GPU, nor in live runs. The serial sense -> edge -> cloud chain is the
   worst networked design. Backed by a dominance proposition that holds for any deadline, and by 19 detectors.
2. Measurement: aerial detection decay on VisDrone-VID, kept accuracy at 100 / 267 ms: 41 % / 7 % with no
   correction, 77 % / 47 % with velocity forecasting, 85 % / 60 % with camera-motion-aligned forecasting.
3. Most novel: the offloading scheduler's objective uses the post-forecasting decay. The best policy
   changes with the forecaster, and the controller rebuilt for forecaster v2 beats v2 significantly
   (+0.0045 +- 0.0035 sAP, median +8.9 %, 20 pairs) with 99.5-99.8 % availability. Verify against
   recent offloading work before submission.
4. Real three-tier drone testbed with the forecaster running live on the Pi (live = offline scores),
   task-level sAP on labeled aerial video, controlled impairments, paired tests, controller inputs
   from data disjoint from the test set.
5. Practical hardware facts: live forecasting slows onboard inference (CPU contention); slow link
   recovery after blackouts; simulator matches the hardware with r = 0.91 except in that recovery.
6. Moderate: swarm admission with radio link health. Simulation gains (worst loss <= 1.9 %, held-out
   seeds); with two real cameras it rarely acts. Needs the 3-5 camera test.

## Claims we must not make

- That parallel offloading, adaptive device-plus-server use, or per-frame configuration adaptation is new
  (Elf, Odessa, Chameleon, AWStream).
- That forecasting or tracking to compensate offloading latency is new (Glimpse, Liu et al. 2019,
  streaming perception, PVT++).
- That optical-flow camera-motion compensation is our technique (BoT-SORT and others).
- That coordinating cameras on a shared link is new (JCAB).
- That our evaluation is a flight test: links are lab Wi-Fi with injected impairments.
