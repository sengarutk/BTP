Full project report · state on 22 Oct 2026, 23:00

# AEGIS-UAV: the complete record of what was built, tested and found

A drone has a camera and must detect objects in every frame. It can run the detector on its own small computer, send the image to a more powerful computer nearby (another drone or a ground station), or split the neural network between them. This project measures which option works best, first in simulation and then on real hardware, and builds a controller that switches between options as conditions change.

Labels used throughout: Validated measured, repeated and cross-checked; Pending built, but the decisive run has not finished; Invalidated results found to be affected by a fault and set aside; Inconclusive measured, but the difference is within the confidence interval; the same color marks Not supported, a claim the data did not bear out.

**Contents**

1. [Where things stand right now](#now)
2. [The technology, explained](#concepts)
3. [Phase A: the split-inference toolkit and paper](#toolkit)
4. [Phase B: checking the simulator](#simval)
5. [Phase C: the hardware testbed](#testbed)
6. [Device and link measurements](#devices)
7. [Every placement of the model](#placement)
8. [Corrections to Hardware Testing.pdf](#pdf)
9. [Adaptive controller v1](#v1)
10. [Adaptive controller v2: multi-server scheduling](#v2)
11. [Literature check and novelty (re-checked)](#novelty)
12. [Phase D: task-level test on drone video](#task)
13. [Phase E: swarm simulation calibrated to the hardware](#swarm)
14. [Phase F: motion forecasting of stale detections](#forecast)
15. [Phase G: energy, power and heat](#energy)
16. [The controllers' objective functions, explained](#objective)
17. [VisDrone-trained detectors on the Pi: streaming accuracy and throttling](#visdrone)
18. [Offloading with the VisDrone weights, and the relay path](#relay)
19. [Every campaign rescored with the standard metrics](#rescore)
20. [What it all means: the argument for the paper](#argument)
21. [Faults found and fixed](#bugs)
22. [Code status and reproducibility](#code)
23. [What is left](#next)
24. [Where everything is](#files)
25. [Glossary](#glossary)

## PART 1Where things stand right now

**State on 22 Oct 2026, 23:00 (checkpoint): VisDrone detectors, onboard study, relay campaign and standard-metric rescoring done; VisDrone replay of the earlier campaigns waiting**

- **Onboard (Part 17, done):** YOLOv8s, m and l fine-tuned on VisDrone (mAP50-95 on DET val 0.107 → 0.267, 0.146 → 0.297, 0.164 → 0.313). On two Pi 5s (30 runs): mAP 0.24–0.27 but sAP only 0.006 / 0.005 / 0.001 (0.017 / 0.008 / 0.0015 with the forecaster), because a frame takes 0.7 / 1.6 / 3.3 s; the Pi throttles within about a minute even from a cool start; throttling leaves mAP unchanged and roughly halves sAP.
- **Relay campaign (Part 18, done, 36 runs):** offloading gives 0.13–0.18 sAP with the forecaster, about 10× onboard, with the Pi at 2–3.4 W and below 70 °C. Out of the ground station's range the direct path delivers nothing while the relay Pi → Jetson → laptop delivers 0.161 and v4.1 switches to it by itself (0.143); in the mission v4.1 is best (0.124) and the only policy still perceiving in a total blackout; on a good link the direct laptop path is best (0.182).
- **Rescoring (Part 19, C1–C6 done, 776 runs):** the standard holding rule and the masking of ignored regions change no verdict; energy pricing, the win over the literature baselines and the staleness ablations survive the Holm correction; v5 over fixed JPEG offloading and v2's lead in Part 12 do not.
- **Hierarchical chain (the professor's design, 18.6):** composed from the measured runs at 0.144–0.159 (normal), 0.155–0.161 (out of range) and about 0.12 (mission), about as good as v4.1 and cooler on the Pi; to be built and measured on the mesh.
- **Waiting for the go-ahead:** the VisDrone replay of the 776 earlier runs (YOLOv8n fine-tuning, about 1.5 h, then about 2.5 h on the laptop), then the AegisSwarm mesh work.

**Current state: the real-world Wi-Fi campaign, motion forecasting and swarm coordination are finished; the mesh campaign comes next**

- The task-level test on labeled drone video ran on the current shared Wi-Fi: 9 policies × 4 scenarios × 3 repetitions, 108 runs, 01:33–06:21 on 6 October, with no outages or failed runs (Part 12).
- Motion forecasting, tuned on training videos only, raised streaming AP for every policy by 32–67 % (median) on those 108 runs. The camera-aligned forecaster v2 roughly doubles it (+80 % to +156 %) and beats v1 in all 144 runs (Part 14).
- Swarm-level coordination was added to the calibrated swarm simulation and confirmed on held-out seeds (Part 13).
- v3 rebuilt on the forecasting decay curve ("v3 + forecasting") ran in a paired Wi-Fi campaign against v2 and the old v3: 36 runs, 06:52–08:29, no outages (Part 14).
- Done today (6 October): 80-run campaign with v3 + forecasting v2 and the live forecaster; 24-run two-camera swarm campaign; simulator-vs-hardware check; coordinator with radio link health.
- Code: all 118 project tests pass, the simulator's default behaviour is bit-for-bit unchanged, and nothing is running. Nothing is committed to git yet (Part 22).
- The controlled version of the campaign, planned for the AegisSwarm mesh, has 3 of its 180 runs.
- The plan is to move the Pi, the Jetson and the laptop onto the AegisSwarm ad-hoc (IBSS) mesh, a private channel with real drone-to-drone links. The laptop keeps internet through an Ethernet cable so Claude stays connected.
- Waiting on you: the Ethernet cable connected, and AegisSwarm's channel, band, IP range and whether batman-adv runs on top.

### Results so far

- **Splitting the network never beats sending a JPEG**Shown in simulation, in theory (a closed-form bound), on 19 detectors, and now on real hardware: across 1,150 placements over the Pi, the Jetson and the laptop, and in live runs. Validated
- **An adaptive multi-server scheduler beats every fixed strategy**59–62 % more accuracy-weighted on-time detections than the best fixed strategy on impaired links, 19 % on a clean link, and best in all 8 paired comparisons. This is scored with COCO accuracy weights, a proxy metric. Validated
- **Perception survives a total blackout**The scheduler switches to YOLOv8n on the Pi and keeps about 10 on-time detections per second. Availability (newest detection under 300 ms old) was 0.999 in every scenario. Validated
- **Aerial detections lose 58 % of their accuracy in 100 ms**A new measurement on VisDrone video: a 300 ms deadline badly overstates real perception quality on drones. Validated
- **In a simulated swarm, adaptive degrades gracefully where fixed offload collapses**With measured Pi and Wi-Fi numbers, fixed JPEG falls to 5.5 frames/s per drone at 5 drones and 0 at 10. Adaptive holds 15.0 at 5 and 8.3 at 10. It is best or tied in 78 of 95 comparisons, and at most 8.3 % behind in the rest. Large swarms need coordination between drones. Validated (simulation)
- **On real accuracy over real Wi-Fi, the multi-server controller v2 is the best policy**Across 108 runs scored by streaming AP on VisDrone video, v2 beats every other policy on average in paired comparisons: by 4.5 % over all servers without adaptation, 14 % over single-path rate adaptation, 37 % over the best fixed server, and 75–201 % over rule-based fallback, the Jetson and onboard. The margin is statistically significant (95 % interval above zero) against rule-based fallback, the Jetson and onboard, but not yet against the others. Validated (Wi-Fi)
- **Motion forecasting recovers much of the staleness loss**Moving each old box forward by its estimated velocity raised streaming AP for all 9 policies, by a median of 32–67 %, with no extra traffic. On training videos a result shown 100 ms late keeps 77 % of fresh accuracy (41 % without), and 47 % at 267 ms (7 % without). Validated
- **Energy-aware control is both more efficient and more accurate**Measured on both boards and applied to every campaign (Part 15): earlier controllers ran the fanless Pi at 4.2–5.3 W, above the about 3.6 W it can sustain without throttling. Onboard inference was 40–54 % of the power for 3–5 % of the accuracy. Controller v4 prices energy against a measured power budget. It cuts measured Pi power by about 1 W (−25 %) and time in the throttling region from 76 % to 17 %, and it is significantly **more accurate** than every other controller: +0.0074 ± 0.0028 sAP over v3 + forecasting v2, 17 of 20 pairs. The cost is freshness (87 % against 99 %). Validated (100 runs, measured energy)
- **Measuring the camera's motion doubles streaming accuracy**Forecaster v2 tracks the background between frames (2.7 ms per frame on the Pi), carries old boxes with the camera's motion, then adds each object's own velocity. Kept accuracy at 267 ms rises to 60 % (v1 47 %, none 7 %). On all 144 real runs it beats v1 every time (median +51 %) and roughly doubles streaming AP compared with no forecasting. Validated
- **A controller built for the forecaster it runs with wins, significantly**v3 rebuilt on the camera-aligned forecaster's decay curve, with the forecaster running live on the Pi, beats v2 by +0.0045 ± 0.0035 sAP over 20 paired runs (median +8.9 %). It is best in 3 of 4 scenarios, including the clean link where fixed laptop YOLOv8m had won before, and keeps a fresh detection 99.5–99.8 % of the time. Validated (Wi-Fi, 5 repetitions)
- **Swarm coordination fixes congestion collapse and starvation**In the calibrated simulation, a ground-side admission rule turns the collapse of 20 Pi drones into about 4.1 detections/s each, raises Jetson-class swarms on Wi-Fi by up to 27 %, and stops the router from starving drones (worst drone 0 → 7.65 frames/s at 10 drones). With each radio's own link health added, its worst loss shrinks from −7.4 % to −1.9 %. Same results on held-out seeds. Validated (simulation)
- **A real two-camera swarm: sharing costs, adaptation pays**With the Pi and the Jetson both as camera drones sharing the laptop, the Pi loses 11–19 % of its streaming accuracy to sharing (significant). Adaptive control beats fixed offloading for the swarm in 6 of 6 pairs. The live coordinator works but rarely acts with two cameras, as the simulation predicted. Validated · Inconclusive (coordinator)
- **The simulator matches the hardware in every phase**Rebuilt from 44 real runs (528 phases) with nothing fitted, it predicts on-time results per phase with correlation 0.947 (average error 1.6/s) once the controller's one-frame-in-flight rule and the conditions actually applied are modelled. (Corrected 13 Oct: the apparent slow recovery after blackouts was a bandwidth limit our emulation left in place; G14.) Validated (with that limit)
- **v3 rebuilt with forecasting keeps a fresh detection 99–100 % of the time**In a paired 36-run campaign it held a detection under 300 ms old 99.0–99.9 % of the time in every scenario, against 75–92 % for v2 under impairment. Its accuracy is level with v2: the difference is not significant, it is ahead on the mean and behind in 8 of 12 pairs. Validated (availability) · Inconclusive (accuracy)
- **The original staleness-aware controller v3 did not win**v3 beat the fixed strategies, but trailed v2 by a median 14 % (10 of 12 pairs). Its objective was built on the steep decay curve measured without forecasting, which makes it over-favour fast results. Rebuilt on the forecasting curve, it became "v3 + forecasting" (above). Not supported (original v3)

## PART 2The technology, explained

### The detector: YOLOv8

YOLOv8 is a family of real-time object detectors (n, s, m, l, x, from small to large). YOLOv8s, the main model here, has 23 layers numbered 0 to 22. Layers 0–9 form the backbone, which extracts features. Layers 10–21 form the neck, which combines them at three scales. Layer 22 is the detection head. After the network, non-maximum suppression (NMS) removes duplicate boxes.

### Split computing

Split computing runs the first layers on the drone and sends the intermediate result to a server, which runs the rest. A cut `k` means layers 0 to k run on the drone. Some later layers also need outputs from earlier ones (skip connections), so a cut can require sending several tensors. At cut `k4` this is one tensor of 128×80×80 numbers; at `k9` it is three. To make that payload small, each number is quantized to 8 bits (INT8) and compressed losslessly with zstd.

### The alternative: image offload

Instead of splitting, the drone can compress the camera frame as a JPEG and send it. The server runs the whole detector. JPEG quality 90 (q90) is near-lossless for detection; q50 is smaller but costs some accuracy.

### The three tiers

| Tier | Device here | Role |
| --- | --- | --- |
| Sense (camera drone) | Raspberry Pi 5, 4-core ARM CPU, no GPU | Captures at 30 fps; can run small models onboard |
| Edge (mothership drone) | NVIDIA Jetson Orin Nano, 1024-core GPU, 15 W mode | A flying GPU near the camera drone |
| Cloud (ground station) | Laptop with RTX 4050 GPU | The most compute, the farthest away |

### Measuring quality

- **mAP@\[.5:.95\]:** the standard detection accuracy, averaged over overlap thresholds from 0.5 to 0.95.
- **On-time frames/s:** detections that come back within a deadline (300 ms in early tests).
- **Streaming AP (sAP):** at every camera frame, whatever detections the drone holds, possibly from an older frame, are scored against what the camera sees now. Latency, dropped frames and accuracy count together. It is the standard real-time perception metric (Li, Wang and Ramanan, ECCV 2020).
- **Availability:** the share of time the drone holds a detection less than 300 ms old.
- **Age of information (AoI):** the age of the newest detection the drone holds.

### The three controller versions

- **v1** picks one strategy at a time (onboard, or one server with one setting), scoring each by expected on-time results per second, and switches with hysteresis.
- **v2** uses all three computers at once. For every frame it picks a computer that is free and the best setting for it: model, image size and JPEG quality. Its score is accuracy × probability of arriving on time ÷ time the computer is busy. "A_full" is v2 with COCO accuracy, "A_full_aer" v2 with aerial accuracy.
- **v3** ("A_stream") keeps v2's dispatch but scores a result by the accuracy it will actually provide while it is held: accuracy × probability on time × the average staleness factor over the time it is shown. The staleness factor comes from the decay curve measured on training videos.

### Staleness and motion forecasting

A detection describes where objects were when the frame was captured. By the time it is shown, the drone and the objects have moved, so its boxes no longer line up with the scene. On aerial video this decay is fast: with no correction, a detection 100 ms old keeps about 40 % of its accuracy. Motion forecasting estimates each box's velocity from successive results and moves it forward by velocity × age before it is used. It only uses results that have already arrived, so a drone can run it live.

### Swarm coordination

When many drones share one network, each one deciding alone sees only its own link. Together they can send more than the network carries: every frame then arrives late, or a router serves some drones and starves the rest. A coordinator on the ground side decides how many drones may offload at once and which settings fit. Drones take turns, and the others process onboard or wait. This is admission control, the same idea networks use to keep calls from overloading a link.

### Statistics used

- **95 % interval (±):** the range in which the true mean lies with 95 % confidence, from a t-distribution over repetitions. With 3 repetitions it is wide.
- **Paired comparison:** two policies run under the same scenario and repetition are compared directly. The mean of those differences and its interval tell whether one is reliably better: the interval must not cross zero.
- **Held-out data or seeds:** settings are chosen on one set (training videos, tuning seeds) and results are reported on a different set, so nothing is fitted to the test.

### Network emulation

To create repeatable bad networks, the Linux tool `tc netem` on the Pi limits rate (e.g. 3 Mbit/s) or drops every packet (blackout). The rules apply only to the experiment's data ports, so the SSH control connection is never cut.

## PART 3Phase A: the split-inference toolkit and paper

The first phase built AEGIS-UAV, an exact split-inference toolkit for YOLOv8, and a full simulation study written up as a paper (`paper/main.tex`).

| Result | Value | Status |
| --- | --- | --- |
| Splitting is exact at every cut, for 19 detectors | Bit-identical outputs | Validated |
| INT8 quantization of the crossing tensors | At most 0.04 mAP points lost at any cut (COCO val2017, 5,000 images) | Validated |
| Smallest split payload | 310.7 KiB at k4 (INT8+zstd), 2.4× a JPEG q95 frame, which loses only 0.21 points | Validated |
| Across 19 detectors from 5 YOLO families | Smallest split is 2.0–11.5× a JPEG q90 frame | Validated |
| System simulation (16 channel × hardware settings) | JPEG is the best fixed strategy in all 16; splitting beats onboard in 10 | Validated |
| Monte Carlo (1,000 single + 300 swarm random systems) | A split beats JPEG by at most 0.47 %; the adaptive policy falls below JPEG in 112 of 1,300 systems, by at most 7 % | Validated |
| Closed-form theory (Propositions 1–5) | Quantization bound, offload dominance, break-even, swarm capacity, endurance; 40 checks pass | Validated |

## PART 4Phase B: checking the simulator

The paper's system results come from a Python simulator, so it was checked against independent tools.

| Check | Tool | Result |
| --- | --- | --- |
| C1 Channel statistics | Theory | Rician K estimated 8.99/3.03/0.10 dB for 9/3/0 dB; Clarke autocorrelation within 0.012 |
| V1 Drone-to-drone Wi-Fi | ns-3 802.11ax | Our model is conservative: ns-3 gives 1.4–3.2× more throughput |
| V2 / O1 Cellular uplink | ns-3 LTE, Simu5G 5G NR | Our mapping is pessimistic at high signal and optimistic at low; conclusions re-checked with the measured curves |
| V3/V4 Frame streaming | ns-3, real TCP | 44 settings, correlation 0.98, same best strategy in 8 of 8 |
| Calibrated rerun | ns-3 link curves | JPEG still best in 16 of 16; adaptation gains up to 1.54× |
| O2 Cell sharing | Simu5G | Fair sharing confirmed up to 5 drones; at 10+ the real scheduler serves 7 and starves the rest |
| O4 Wi-Fi range per rate | INET (OMNeT++) | Matches our model for 7 of 9 rates |
| O5 Two-hop relay | ns-3 | Our relay model is conservative: the real path is 1.3–3.1× faster |
| V5 Real network stack | Linux TCP + netem | Within 0.9 frames/s in 6 settings |

Status: Validated. Every conclusion of the paper survived the calibrated reruns. Details: `docs/assumptions_and_validation.md`.

## PART 5Phase C: the hardware testbed

### Setup work

- **Access:** SSH to both boards, with passwords passed only at run time and never stored. The Jetson's host-key change was verified against the fingerprint you read on the device.
- **Jetson:** it had been reflashed without CUDA. Installed JetPack 7.2.1 (CUDA 13.2, cuDNN 9.20, TensorRT 10.16) and CUDA PyTorch 2.14.1. That build has no native Orin kernels and runs the sm_80 ones, so detections were checked against the CPU: identical on 10 images, boxes within 0.02 px. Clocks are locked with `jetson_clocks` for every run, because the GPU otherwise down-clocks at low load.
- **Pi:** two findings. Importing ultralytics silently caps PyTorch at one thread (950 ms per frame against 576 ms with four), so the scripts reset it. The Pi has no cooler and throttles from 2.4 to 1.5 GHz at 85–89 °C.
- **Laptop:** the code runs in WSL2 behind Windows' address translation, so the boards cannot open connections to it. Every protocol therefore has the laptop connect out.

### Tools written (`validation/hardware/`)

| Script | Purpose |
| --- | --- |
| `hwbench.py` | Times every layer and all 276 model segments on each device, plus INT8/FP16 encoding at every cut, JPEG, and board power (Jetson INA3221 sensor, Pi PMIC rails, laptop nvidia-smi) |
| `netbench.py` | Link round-trip time, bulk throughput and per-frame transfer time |
| `placement.py` | Combines the measurements into all 1,150 placements |
| `cascade_accuracy.py` | Accuracy when data is encoded twice (two hops) |
| `pipeline_node.py` | A live distributed pipeline across the three devices |
| `adaptive.py`, `adaptive2.py` | Adaptive controllers v1, v2 and v3, and the workers |
| `forecast.py` | Motion forecaster (v1 velocity, v2 camera-aligned): train detections, two tuning stages, decay curves |
| `sim_vs_real.py` | Rebuilds real runs in the simulator and compares predicted with measured on-time rates |
| `coordinator.py`, `tools/arun2.sh`, `tools/campaign_swarm.sh`, `summarize_swarm.py` | Two-camera swarm: live coordinator, run script, campaign, scoring |
| `egomotion.py` | Camera motion between frames: optical flow and RANSAC similarity transform, chained per sequence |
| `swarm_calibrated.py` | Swarm simulation with the measured hardware numbers, with and without coordination |
| `stream_ap.py`, `summarize_*.py` | Streaming-AP scoring and campaign statistics |
| `tools/` | Campaign harness: SSH helpers, run script with stale-process cleanup and clock locking, resumable campaigns with an outage guard |

## PART 6Device and link measurements

| Device | YOLOv8s full | Layers 0–4 | Power idle → active | Energy per frame |
| --- | --- | --- | --- | --- |
| Pi 5, 4 threads, cool | 576 ms | 210 ms | 2.6 → 4.8 W | 1.3 J |
| Pi 5, sustained (1.5 GHz) | 758 ms | 252 ms | 2.0 → 4.7 W | 2.0 J |
| Pi 5, 1 thread | 950 ms | 325 ms | — | — |
| Jetson Orin Nano FP16 | 22.7 ms | 7.4 ms | 3.2 → 10.5 W | 0.17 J |
| Jetson Orin Nano FP32 | 41.7 ms | 13.0 ms | 3.3 → 9.7 W | 0.27 J |
| Laptop RTX 4050 FP16 | 5.5 ms | 1.0 ms | 2.7 → 49 W | — |

Pi power is the sum of its PMIC rails, which excludes 5 V conversion losses, so it is a lower bound. The Pi's Wi-Fi rail rises by 0.31 W while transmitting, against 2.7 W for inference.

### Small models and resolutions (per frame, including pre- and post-processing)

| Device | Variant | Time |
| --- | --- | --- |
| Pi (4 threads) | YOLOv8n @ 320 / 416 / 640 | 72 / 107 / 235 ms |
| Pi (4 threads) | YOLOv8s @ 320 / 640 | 153 / 584 ms |
| Jetson | YOLOv8s @ 320 / 480 / 640 | 29 / 31 / 33 ms |
| Laptop | YOLOv8s @ 320 / 640; YOLOv8m @ 640 | 9.0 / 9.9; 13.6 ms |

JPEG of a 640 px frame: 87 KB at q90, 36 KB at q50; 26 KB and 11 KB at 320 px. Encoding takes at most 3 ms on the Pi.

### Links on 3 October (all through one router)

| Link | Round trip | Throughput | 85 KB frame | 315 KB frame |
| --- | --- | --- | --- | --- |
| Pi → laptop | 4.9 ms | 30 Mbit/s | 25 ms | 84 ms |
| Pi → Jetson | 2.7 ms | 13 Mbit/s | 72 ms | 224 ms |
| Jetson → laptop | 4.0 ms | 18.5 Mbit/s | 43 ms | 161 ms |

Pi → Jetson is slowest because both are Wi-Fi clients of the router, so every packet crosses the air twice. On 5 October the same links measured about 5.6 Mbit/s.

## PART 7Every placement of the model

A placement chooses which device runs which layers and how data is encoded between them. `placement.py` evaluated all 1,150. Live runs then checked the important ones, with a 30 fps camera, 60 s runs, up to 4 repetitions, and detections returned to the camera.

| Placement | Frames/s | On time (≤300 ms) | Latency p50 |
| --- | --- | --- | --- |
| Jetson alone (camera on the Jetson) | 18.5 | 18.5 | 35 ms |
| Pi JPEG → laptop | 15.2 | 14.7 | 107 ms |
| Pi JPEG → Jetson | 10.9 | 10.1 | 150 ms |
| Jetson JPEG → laptop | 9.0 | 8.1 | 139 ms |
| Pi split k1 → laptop (best split) | 7.0 | 2.5 | 324 ms |
| Pi split k4 → laptop | 4.2 | 0.0 | 419 ms |
| Pi split k4 → Jetson (PDF's "mothership") | 2.7 | 0.0 | 691 ms |
| Pi JPEG → Jetson relay → laptop | 3.4 | 0.5 | 570 ms |
| Pi k4 → Jetson k9 → laptop (two splits) | 2.1 | 0.0 | 1,413 ms |
| Pi alone | 1.6 | 0.0 | 589 ms |

The model predicts two-device placements within about 30 %. It is too optimistic for three devices, because both Wi-Fi hops share one channel.

### Encoding twice costs nothing

| Hop 1 | Hop 2 | mAP change (points, 95 % CI) |
| --- | --- | --- |
| JPEG q90 | INT8 at k4, k9 or k15 | −0.32 to −0.35 |
| INT8 at k1 | INT8 at k2 (6 pairs) | −0.04 to +0.01 |
| INT8 at k1 | FP16 at k2 (3 pairs) | −0.03 to −0.01 |

Status: Validated. Full write-up: `docs/hardware_results.md`.

## PART 8Corrections to Hardware Testing.pdf

| PDF claim | Measured |
| --- | --- |
| Pi YOLOv8s 786 ms | 576 ms cool, 758 ms throttled, 950 ms on 1 thread |
| JPEG 359 KiB per frame | 84–87 KB at q90 |
| Drone-to-drone link "measured" 59.66 Mbit/s | That is our simulator's value; the real Pi → Jetson link was 13 Mbit/s |
| JPEG → cloud 38.8 ms at 57.8 frames/s over 17 Mbit/s | Not possible at that rate; measured 107 ms and 15 frames/s |
| Pi k4 → Jetson mothership as the best design | 2.7 frames/s, never on time; JPEG to the Jetson is 4× better |
| Double INT8 loses 3.81 dB, so FP16 is needed | No accuracy loss (−0.04 to +0.01 points) |
| Jetson 41.3 ms | Correct for FP32; FP16 is 22.7 ms |
| Adaptive mission: 96.8 % compliance, +42.6 % endurance | A scripted scenario whose onboard power assumes 10 frames/s on a 1.3 frames/s device |

## PART 9Adaptive controller v1

**Design.** The Pi chooses one option per frame: onboard YOLOv8s, JPEG q90 or q50 to the laptop or the Jetson, or the k1 split. It scores each option by predicted frame rate × probability of meeting the deadline × relative accuracy, minus an energy cost. Link speed is estimated from every frame. Probes test unused links. A stalled link is closed and reconnected, and switches use hysteresis.

**Test.** A scripted six-phase mission, 30 s per phase: good link, ground link congested, ground blackout, both links degraded, total blackout, recovery at low battery. 7 policies × 3 repetitions. (As applied, the recovery phase kept the previous phase's bandwidth limits; G14.)

| Policy | On-time frames/s over the mission |
| --- | --- |
| Adaptive v1 | 13.85 |
| Best fixed (JPEG q50 → Jetson) | 12.79 |
| JPEG q50 → laptop | 7.71 |
| Hindsight best fixed per phase | 14.43 |

Result: 96 % of the hindsight optimum and +8 % over the best fixed strategy. It won 2 of 3 repetitions; in the noisiest one it switched too often (56 times). The gain was modest because v1 could only pick one option at a time.

## PART 10Adaptive controller v2: multi-server scheduling

**What changed.** The Pi, the laptop path and the Jetson path become three servers working in parallel, each holding at most one frame. For every camera frame the scheduler hands the newest frame to the idle server whose best variant adds the most accuracy-weighted on-time results per second. The variants are:

- **Onboard:** YOLOv8n@320, YOLOv8s@320, YOLOv8s@640.
- **Each path:** JPEG q90 or q50 at 640, 480 or 320 px for YOLOv8s.
- **Laptop only:** YOLOv8m@640.

Accuracy per variant comes from 5,000 COCO images, and timings are learned online.

**Test.** 4 scenarios (ground fails first, Jetson fails first, random link changes, no impairment) × 11 policies × 2 repetitions = 88 runs, in shuffled order. (As applied, a phase without a bandwidth limit kept the previous phase's limit; G14.)

Accuracy-weighted on-time detections per second, median of 2 repetitions. Green: adaptive v2 (A_full). Grey: best fixed strategy in that scenario.

| Scenario | A_full | All servers, no adaptation | Paths only | One server | Best fixed | Hindsight fixed |
| --- | --- | --- | --- | --- | --- | --- |
| Ground fails first | 18.8 | 16.9 | 16.4 | 13.8 | 11.6 | 15.1 |
| Jetson fails first | 20.5 | 17.0 | 18.5 | 16.0 | 13.2 | 16.7 |
| Random changes | 20.0 | 18.0 | 18.2 | 14.9 | 12.6 | 17.2 |
| No impairment | 30.2 | 24.6 | 19.7 | 20.2 | 25.4 | 25.4 |

- **Paired comparisons:** A_full was best in all 8 scenario × repetition pairs.
- **Availability:** 0.999 everywhere.
- **Pi power:** 0.7–3.1 W, against 2.4–3.1 W without adaptation.
- **Where the gain comes from:** parallel servers give most of the raw on-time count. Adaptation adds 10–23 % in accuracy-weighted terms and saves power.
- **Limits:** only 2 repetitions, and the scoring uses COCO accuracy weights, a proxy.

Status: Validated on the proxy metric. Write-up: `docs/adaptive_results.md`.

## PART 11Literature check and novelty (re-checked 7 Oct 2026)

The check was redone after the forecasting, controller and swarm work, searching specifically for prior work on each new piece. Several ideas we use turn out to be **established**. The novelty is narrower than "forecasting" or "coordination" in general: it lies in specific measurements, in one coupling of forecaster and scheduler, and in the real-hardware evaluation. Rows need checking against the full papers before submission.

### Prior work that already covers parts of what we do

| Prior work | What it already does | Consequence for us |
| --- | --- | --- |
| Elf (MobiCom 2021) | Offloads parts of one frame to several edge servers in parallel | Parallel offloading is not new |
| Odessa (MobiSys 2011) | Adaptively decides offloading and parallelism across device and server for interactive perception | Adaptive device-plus-server use is not new |
| Chameleon, AWStream | Adapt resolution, frame rate and model to bandwidth on one path | Per-frame configuration adaptation is not new |
| Glimpse (SenSys 2015) | Tracks objects on the phone from stale server results to hide offloading delay | **Compensating offloading delay by tracking is not new** |
| Liu et al., edge-assisted detection for mobile AR (MobiCom 2019) | Offloads detection to the edge and tracks with motion vectors on the device to cover the delay | Same: latency-compensating tracking for offloaded detection is established |
| Streaming perception (ECCV 2020); PVT / PVT++ (ICCV 2023) | Define streaming AP; forecasting (Kalman, learned) to counter latency, including latency-aware tracking on UAVs | The metric and latency forecasting on drones are not new |
| BoT-SORT (2022) and similar trackers | Camera-motion compensation by sparse optical flow and a RANSAC affine fit between frames | **Our camera-motion estimation technique is standard** |
| JCAB (INFOCOM 2020, IEEE/ACM ToN 2022) | Jointly adapts each camera's settings and splits a shared uplink among several cameras | Coordinating cameras that share a link is not new |
| Drone edge analytics (e.g. SEC 2018); multi-UAV offloading studies | Onboard filtering; offloading and scheduling for several UAVs, mostly in simulation | Multi-UAV offloading is an active area |
| Split computing (Neurosurgeon and others) | Chooses a split point between device and server | We test this approach and find it loses |

### What we can claim as new

- **1. A measured negative result for split computing on drone hardware**None of the 1,150 placements of YOLOv8s over a Pi 5, a Jetson Orin Nano and a ground GPU, nor the live runs, beats sending a JPEG. The professor's serial sense → edge → cloud chain is the worst networked design. Backed by a closed-form dominance result that holds for any deadline, and by 19 detectors. Strong
- **2. Measurements of how fast aerial detections go stale, with and without correction**On VisDrone video a detection keeps 41 % of its accuracy at 100 ms and 7 % at 267 ms. With a velocity forecaster: 77 % and 47 %. With camera-motion alignment: 85 % and 60 %. We found no prior measurement of this decay for aerial detection. Strong (measurement)
- **3. Matching the offloading scheduler's objective to the forecaster in use**Our scheduler values each candidate result by the accuracy it will have *after* forecasting, using the measured post-forecasting decay curve. We show the choice of best policy changes with the forecaster: under strong forecasting a fixed big model won the clean link until the controller was rebuilt. The rebuilt controller then significantly beats v2 (+8.9 % median over 20 paired runs) and keeps a fresh detection 99.5–99.8 % of the time. Prior systems (Glimpse, Liu et al.) track to hide delay but do not feed the forecaster's effect back into which server and setting to choose. Most novel (verify against more recent offloading work)
- **4. A real three-tier drone testbed evaluated with streaming accuracy**Whole-frame scheduling across a drone CPU, an airborne-class edge GPU and a ground GPU, with the forecaster running live on the Pi. Live and offline scores are identical. Evaluated with task-level streaming AP on labeled aerial video, controlled impairments, 3–5 repetitions, paired tests, and controller inputs measured on data disjoint from the test videos. The method is a combination of known parts; the contribution is the measured evidence. Strong (evaluation)
- **5. Hardware facts that matter for practice**Running the forecaster live slows the Pi's onboard inference (YOLOv8s-320: 170 → 412 ms) because they share the CPU. A drone-scale simulator rebuilt from 44 real runs matches the hardware in all 528 phases (r = 0.947). (Retracted 13 Oct: "after a blackout the real link stays slow" was a bandwidth limit our network emulation kept from the previous phase; G14.) Useful (measurement)
- **6. Swarm admission with radio link health**A coordinator that decides how many drones offload at once, rotates turns, and uses each radio's own link health to tell a drone's own outage apart from congestion. In calibrated simulation it removes collapse and starvation and keeps every loss at or below 1.9 %, on held-out seeds too. On real hardware with two cameras it rarely acts. Shared-link coordination itself is known (JCAB). The specific rule and the hardware calibration are ours, but the gains are simulation-only so far. Moderate (needs the 3–5-camera test)

- **7. (Added 7 Oct) Energy pricing that raises accuracy, measured on drone hardware**On a fanless drone computer, pricing energy against a live-measured power budget cut power by about 25 % and throttling-region time from 76 % to 17 %, and *increased* streaming accuracy significantly (+13 % median), because low-value onboard work also costs heat and CPU. Energy-aware offloading as such is a crowded field, so the claim is the measured three-way coupling and the result, not energy awareness itself. Strong (needs a literature check before submission)

### Claims we must not make

- That parallel offloading, adaptive device-plus-server use, or per-frame configuration adaptation is new (Elf, Odessa, Chameleon, AWStream).
- That forecasting or tracking to compensate offloading delay is new (Glimpse, Liu et al. 2019, streaming perception, PVT++).
- That camera-motion compensation by optical flow and RANSAC is our technique (BoT-SORT and others).
- That coordinating cameras on a shared link is new (JCAB).
- That the evaluation is a flight test: links are lab Wi-Fi with injected impairments; the mesh campaign is pending.

Full notes: `docs/novelty_and_related_work.md`.

## PART 12Phase D: task-level test on drone video

### Why it is needed

The v2 result scores each on-time result by its model's COCO accuracy. A reviewer will ask how accurate the drone's view really is. Phase D measures that directly on labeled drone video.

### Data

- **Test set:** VisDrone2019-VID validation, 7 videos, 2,846 frames, about 108,000 labeled objects. Resized to 640 px wide; classes mapped to COCO exactly as in the paper.
- **Controller inputs, kept off the test set:** aerial accuracy per variant from VisDrone-DET val (548 images), and staleness decay from 8 VisDrone-VID training videos chosen by a fixed rule.

### Aerial accuracy per variant

| Variant | COCO mAP | Aerial mAP |
| --- | --- | --- |
| YOLOv8m 640 raw / q90 / q50 | 0.498 / 0.494 / 0.450 | 0.146 / 0.138 / 0.098 |
| YOLOv8s 640 raw / q90 / q50 | 0.444 / 0.441 / 0.409 | 0.107 / 0.105 / 0.083 |
| YOLOv8s 480 q90 / q50 | 0.413 / 0.380 | 0.073 / 0.058 |
| YOLOv8s 320 raw / q90 / q50 | 0.357 / 0.350 / 0.317 | 0.040 / 0.039 / 0.028 |
| YOLOv8n 640 / 320 raw | 0.368 / 0.281 | 0.072 / 0.026 |

On aerial images 320 px loses 63 % of accuracy, against 20 % on COCO, because objects are tiny.

### Staleness decay

AP of detections from an older frame, scored on the current frame, relative to fresh detections (YOLOv8s 640, VisDrone-VID train).

### Controller v3 (A_stream)

For each idle server and variant, v3 predicts the result's latency L and how long it will stay the drone's newest result, T. Its value is the variant's aerial accuracy times the average freshness over that window, times the chance it arrives within 1 s. The drone keeps whichever delivered result currently has the highest accuracy × freshness. For a single server, this rule maximizes the long-run average quality exactly; with several servers it is a greedy approximation. Model write-up: `docs/controller_model.md`.

### Verification of the evaluation

- The streaming-AP scorer reproduces the official ultralytics validator: 0.0967 against 0.0976 mAP, with the residual from FP16.
- The fast NMS gives the same AP as ultralytics' (0.0845 vs 0.0844).

### Campaign design

- **Scenarios:** 4 (as in v2).
- **Policies:** 9.
  - Three controller versions as ablations: v3, v2 with aerial accuracy, and v2 with COCO accuracy.
  - Three literature-style baselines: all servers with no adaptation, single-path bitrate adaptation, and rule-based fallback.
  - Three fixed strategies: laptop YOLOv8m q90, Jetson YOLOv8s q90, Pi YOLOv8n 320.
- **Repetitions:** 5. That makes 180 runs of about 3 minutes, in shuffled order, with 95 % confidence intervals and paired tests.

### Campaign history

| Attempt | What happened | Outcome |
| --- | --- | --- |
| 1 | A network outage, then the Jetson's clock lock was found cleared by a reboot (GPU at 306 MHz) | Invalidated 6 runs |
| 2 | NMS at the low confidence needed for AP took up to 130 ms on the Jetson, hurting remote servers unevenly | Invalidated 59 runs |
| 3 | The controller stopped using a server after its slow warm-up frames, so the Jetson and YOLOv8m went unused | Invalidated 50 runs |
| 4 | All fixes in; the smoke test shows the Jetson used throughout and availability 0.91–0.99. Paused for congested Wi-Fi | Pending 3 of 180 runs |
| 5 | Real-world version on the current shared Wi-Fi (Pi to laptop 22 Mbit/s, Pi to Jetson 18.5 Mbit/s, Pi signal −79 dBm): same code, 3 repetitions. No outages or errors | Validated 108 of 108 runs |

**What the invalid runs showed**

In attempt 3 (1–2 repetitions per cell), the adaptive controllers were not ahead. In the ground-fails-first scenario, "all servers, no adaptation" scored 0.021 sAP against 0.015 for v3. On a clean network, fixed laptop YOLOv8m scored 0.044 against 0.035. Part of this was the warm-up bug, which kept v3 off the Jetson and off YOLOv8m. Whether v3 wins once it is fixed is the open question this campaign will answer.

**Answer (attempt 5 below and Part 14):** the original v3 did not win. Rebuilt with forecasting it matches v2 on accuracy and clearly beats it on availability.

### Results on the shared Wi-Fi (attempt 5, 108 runs)

Streaming AP (mAP@\[.5:.95\] of what the drone holds at every frame, scored on VisDrone-VID val), mean ± 95 % interval over 3 repetitions, with the quality-aware holding rule. The last column applies the motion forecaster of Part 14.

| Policy | Ground fails first | Jetson fails first | Random | No impairment | Median gain from forecasting |
| --- | --- | --- | --- | --- | --- |
| **v2 multi-server (A_full)** | **0.0207 ± 0.0018** | 0.0168 ± 0.0252 | **0.0201 ± 0.0017** | 0.0349 ± 0.0092 | +37 % |
| All servers, no adaptation | 0.0204 ± 0.0041 | 0.0211 ± 0.0027 | 0.0186 ± 0.0082 | 0.0311 ± 0.0031 | +32 % |
| v2 with aerial accuracy | 0.0185 ± 0.0037 | 0.0202 ± 0.0064 | 0.0180 ± 0.0040 | 0.0246 ± 0.0253 | +48 % |
| v3 staleness-aware (A_stream) | 0.0160 ± 0.0027 | 0.0211 ± 0.0042 | 0.0170 ± 0.0052 | 0.0216 ± 0.0332 | +48 % |
| Single-path rate adaptation (laptop) | 0.0127 ± 0.0039 | **0.0216 ± 0.0063** | 0.0173 ± 0.0031 | 0.0309 ± 0.0099 | +47 % |
| Fixed laptop YOLOv8m q90 | 0.0096 ± 0.0032 | 0.0195 ± 0.0077 | 0.0121 ± 0.0053 | **0.0356 ± 0.0069** | +47 % |
| Rule-based fallback | 0.0091 ± 0.0025 | 0.0156 ± 0.0045 | 0.0095 ± 0.0044 | 0.0299 ± 0.0040 | +53 % |
| Fixed Jetson YOLOv8s q90 | 0.0169 ± 0.0048 | 0.0070 ± 0.0012 | 0.0074 ± 0.0051 | 0.0220 ± 0.0081 | +39 % |
| Fixed onboard YOLOv8n 320 | 0.0073 ± 0.0005 | 0.0071 ± 0.0013 | 0.0069 ± 0.0013 | 0.0070 ± 0.0003 | +67 % |

### Paired comparison: v2 (A_full) against each policy

| Against | Mean difference ± 95 % | v2 ahead | Median relative gain |
| --- | --- | --- | --- |
| Fixed onboard YOLOv8n 320 | +0.0160 ± 0.0048 | 11 / 12 | +201 % |
| Rule-based fallback | +0.0071 ± 0.0039 | 10 / 12 | +75 % |
| Fixed Jetson YOLOv8s q90 | +0.0098 ± 0.0034 | 11 / 12 | +68 % |
| Fixed laptop YOLOv8m q90 | +0.0039 ± 0.0047 | 9 / 12 | +37 % |
| v3 staleness-aware | +0.0042 ± 0.0049 | 10 / 12 | +16 % |
| v2 with aerial accuracy | +0.0028 ± 0.0045 | 11 / 12 | +16 % |
| Single-path rate adaptation | +0.0025 ± 0.0038 | 10 / 12 | +14 % |
| All servers, no adaptation | +0.0003 ± 0.0030 | 8 / 12 | +4.5 % |

- **v2 is the best policy overall.** It is ahead of every other policy on average and first or within the interval of first in every scenario except "Jetson fails first", where one bad repetition widened its interval (± 0.025).
- **It is statistically significant against three baselines** (onboard, Jetson, rule-based fallback). Against the other five the 95 % interval still crosses zero, because 3 repetitions on a shared Wi-Fi give wide intervals. The mesh campaign with 5 repetitions is meant to settle these.
- **On a clean link, a fixed strong server is as good.** Fixed laptop YOLOv8m (0.0356) and v2 (0.0349) are tied. Adaptation pays off when links fail.
- **v3 did not deliver.** Its staleness objective, built from the no-forecasting decay curve, favours fast, low-accuracy results too strongly. Its availability was 0.77–0.90.
- **Availability:** all servers without adaptation keeps 0.999 everywhere, but at 2.3–3.1 W of Pi power. v2 reaches 0.77–0.98 at 0.9–2.7 W.

Files: `experiments/results/hardware/vid_campaign_wifi/` (runs and the evaluation cache), `vid_campaign_wifi_summary.json/.csv`, logs `vid_campaign_wifi_summary.log` (paired against v3) and `vid_campaign_wifi_summary_refA_full.log` (paired against v2).

## PART 13Phase E: swarm simulation calibrated to the hardware

### Why it is needed

The testbed has one camera drone. A swarm means several drones sharing one network, and the question is how each strategy behaves as the swarm grows. Buying ten Pis is not needed for that: the simulator from Phase B (checked against ns-3, Simu5G and OMNeT++) was rerun with the numbers measured on the hardware instead of the paper's assumed ones.

### Calibration

| Input | Value | Source |
| --- | --- | --- |
| Camera drone, Pi 5 | 758 ms per YOLOv8s frame | Measured, sustained and throttled (Part 6) |
| Camera drone, Jetson-class | 35 ms per frame | Measured Jetson Orin Nano, FP16 with pre- and post-processing |
| Shared network, Wi-Fi access point | 25 Mbit/s | Measured goodput of the testbed router (22–30 Mbit/s) |
| Shared network, cellular cell | 100 Mbit/s | The paper's cell |
| How the capacity is divided | Water-filling (equal shares) or capped | Capped reproduces the Simu5G result that a real scheduler serves about 7 drones and starves the rest (check O2) |
| Payload sizes, server times, deadline | Measured; 300 ms deadline; 30 fps camera | As in the paper |

Grid: 2 camera drones × 2 networks × 2 sharing rules × 2 channel profiles (moderate fading, blackouts) × 6 swarm sizes (1, 2, 3, 5, 10, 20) × 4 strategies (onboard, split at layer 4 with INT8+zstd, JPEG q90, adaptive) = 384 cells, each 5 seeds of 120 s. Metric: on-time frames per second per drone. Script `validation/hardware/swarm_calibrated.py`; it ran on the laptop CPU in 15 minutes. Validated as a simulation; it is not a swarm measurement.

### Pi camera drones, moderate channel, capped sharing

| Drones | Onboard | Split k4 | JPEG q90, Wi-Fi | Adaptive, Wi-Fi | JPEG q90, cell | Adaptive, cell |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 0 | 0 | 14.8 | 15.0 | 14.8 | 15.0 |
| 2 | 0 | 0 | 14.8 | 15.0 | 14.8 | 15.0 |
| 3 | 0 | 0 | 11.1 | 15.0 | 14.8 | 15.0 |
| 5 | 0 | 0 | 5.5 | 15.0 | 14.8 | 15.0 |
| 10 | 0 | 0 | 0 | 8.3 | 11.2 | 14.9 |
| 20 | 0 | 0 | 0 | 4.2 | 5.2 | 12.6 |

### Jetson-class camera drones, moderate channel, Wi-Fi 25 Mbit/s

| Drones | Onboard | Split k4 | JPEG q90 | Adaptive, equal shares | Adaptive, capped |
| --- | --- | --- | --- | --- | --- |
| 1 | 15.0 | 7.7 | 25.8 | 29.6 | 29.6 |
| 2 | 15.0 | 4.5 | 16.5 | 29.6 | 29.6 |
| 3 | 15.0 | 0 | 11.1 | 20.1 | 20.1 |
| 5 | 15.0 | 0 | 6.7 | 18.3 | 18.3 |
| 10 | 15.0 | 0 | 0 / 3.3 | 16.5 | 16.8 |
| 20 | 15.0 | 0 | 0 / 1.7 | 14.0 | 14.9 |

JPEG q90 at 10 and 20 drones: equal shares / capped. On the 100 Mbit/s cell the Jetson-class adaptive drone keeps 29.5 frames/s up to 10 drones and 18.9–19.2 at 20.

### What it shows

- **A Pi swarm must offload**At 758 ms per frame, the Pi alone, and the Pi running the first layers of a split, never meet the 300 ms deadline at any swarm size. Every useful frame comes from sending a JPEG. The simulated Pi prepares at most every other camera frame, so 15 frames/s is its ceiling.
- **Fixed JPEG collapses as the swarm grows; adaptive degrades gracefully**On the shared 25 Mbit/s Wi-Fi, fixed JPEG q90 falls from 14.8 frames/s per drone (1–2 drones) to 5.5 at 5 drones and 0 at 10. The adaptive controller holds 15.0 up to 5 drones (2.7× fixed JPEG) by moving to JPEG q50, at a 7 % accuracy cost (mAP 0.409 against 0.440), and still delivers 8.3 at 10 drones.
- **With a GPU on board, adaptive doubles the onboard rate in small swarms**A Jetson-class drone alone gives 15 frames/s (35 ms is just over one camera period). Offloading the rest gives 29.6 at 1–2 drones and 18.3 at 5.
- **Splitting is worse than JPEG in every cell**The split at layer 4 never beats JPEG q90, at any size, on either network. This matches the paper and the hardware placements.
- **Adaptive is best or tied in 78 of 95 comparisons**Here a comparison is one setting at one swarm size where some strategy delivers frames; each pits adaptive against the best fixed strategy for that setting.
  - In 12 of the 17 losses it is behind by at most 0.5 %. These are small Pi swarms during blackouts, where it occasionally tries a lower JPEG quality.
  - The other 5 losses are Jetson-class swarms of 10–20 drones on Wi-Fi. There, staying onboard is best and adaptive is 0.8–8.3 % behind, because it keeps probing a network that is too crowded to help.
- **The limit is coordination, not the per-drone controller**Each drone decides alone and cannot see the others' load. With 20 Pi drones on Wi-Fi and equal shares, every drone gets about 1.25 Mbit/s, which is too little for any frame to arrive on time, and output falls to 0. Under capped sharing the mean is 4.2 frames/s, but some drones get 0 (the minimum per drone is 0 at 10 and 20 drones). A swarm-level admission rule (only as many drones offload as the network can carry, the rest degrade) should fix both; it is tested below.

### Swarm coordination (added)

A coordinator on the ground side knows the shared capacity and each drone's reported link estimate (a few bytes per drone per second). Once a second it picks how many drones K may offload at the same time, the K that maximizes the swarm's expected on-time detections. For each drone it lists the offload settings that still fit when K drones use them at their predicted frame rate. Admitted drones keep choosing frame by frame among those settings and onboard. The others run onboard if that is useful, and otherwise skip the frame. The admitted set rotates round-robin for fairness. When there is no contention, coordination switches off and every drone behaves exactly as before. Code: `coordination="admission"` in `simulation/stream_sim.py`.

The one setting, the capacity multiple the coordinator plans with (1.1), was chosen on separate tuning seeds (100–101). The design went through four versions checked on the study seeds 0–4, so the final version was also run on fresh seeds 5–9.

| Case (moderate channel) | Uncoordinated | Coordinated | Change |
| --- | --- | --- | --- |
| 20 Pi drones, Wi-Fi, equal shares | 0.0 (worst drone 0.0) | 4.15 (worst 4.08) | collapse removed |
| 10 Pi drones, Wi-Fi, capped router | 8.32 (worst drone 0.0) | 8.29 (worst 7.65) | no starvation |
| 20 Pi drones, Wi-Fi, capped router | 4.16 (worst drone 0.0) | 4.12 (worst 3.62) | no starvation |
| 5 Jetson-class drones, Wi-Fi | 18.3 | 22.4 | +22 % |
| 10 Jetson-class drones, Wi-Fi | 16.5 | 18.7 | +13 % |
| 20 Jetson-class drones, Wi-Fi | 14.0 (below onboard 15) | 16.9 (above onboard) | +21 % |
| 20 Jetson-class drones, cell, equal shares | 18.9 | 22.6 | +20 % |
| 20 Jetson-class drones, cell, capped router | 19.2 | 17.8 | −7.4 % |

- **Better in 16, tied in 74, worse in 6 of 96 cases, and identical on held-out seeds**Seeds 0–4 and fresh seeds 5–9 give the same split. Five of the six losses are within 1.7 %. Validated (simulation)
- **The one real loss is a scheduler the coordinator cannot see**On the cell with the capped router (serves 7 drones at a time), admitting 10 drones starves 3 of them. Learning K from each drone's achieved throughput closes this gap, but costs elsewhere (ablation below).
- **One case it does not catch**3 Jetson-class drones on Wi-Fi stay at 20.1, because every drone's own choice looks admissible. An earlier version that locked settings reached 27, but cost 2–8 % in small swarms.

### Ablation: a coordinator that learns from feedback

To close the two gaps above, a feedback layer was tried (`coord_feedback` in `stream_sim.py`), evaluated on the tuning seeds 100–101 over 80 cases:

| Variant | Mean gain over uncoordinated | Better / worse | Capped-router case (20 Jetson, cell) | Worst loss |
| --- | --- | --- | --- | --- |
| Coordinator (main result) | +16.0 % | 16 / 6 | −7.6 % | −7.6 % |
| + cap K at the number of drones actually served | +15.7 % | 16 / 6 | −7.1 % | −7.4 % |
| + that, and shared lateness cuts planned capacity (AIMD) | +15.7 % | 19 / 6 | +0.7 % | −8.4 % (Pi, blackout) |
| First AIMD version (any late drone counts) | +15.0 % | 19 / 21 | +3.7 % | −10 % (Pi, blackout) |

Feedback fixes the capped-router loss, but it mistakes blackouts on individual links for contention and costs Pi swarms in blackouts. Overall it does not beat the plain coordinator, so the plain coordinator stays the main result and feedback is reported as a negative ablation. The 3-drone case never shows late frames, only a lower frame rate, so lateness cannot detect it. Telling an own-link blackout apart from contention (for example from the radio's signal level) is the open problem. Not supported (feedback from goodput estimates)

### Coordinator with link health from the radio (new main result)

**The fix.** A modem knows its own link quality instantly from its signal level, while the coordinator above only had a smoothed goodput estimate. In this version each drone also reports its radio's own link capacity over the last window, its worst 10 ms slot (`coord_feedback="rssi"`). A drone whose own link was down is then excluded from both feedback rules. Its late frames no longer count as congestion, and its empty window no longer counts as the router starving it. On the tuning seeds, the first version that applied this only to lateness did not help (+15.7 %, worst −7.6 %). Applying it to the starvation rule as well did.

| Seeds | Coordinator | Better / tied / worse (96 cases) | Worst loss | Capped-router case (20 Jetson, cell) |
| --- | --- | --- | --- | --- |
| Study 0–4 | Plain | 16 / 74 / 6 | −7.4 % | 17.78 (uncoordinated 19.24) |
| Study 0–4 | **With radio link health** | **18 / 72 / 6** | **−1.9 %** | **19.33** |
| Held-out 5–9 | Plain | 16 / 74 / 6 | −7.3 % | 17.76 (uncoordinated 19.20) |
| Held-out 5–9 | **With radio link health** | **18 / 73 / 5** | **−1.7 %** | **19.29** |

It keeps every large gain unchanged (20 Pi drones 0 → 4.15; Jetson-class +22 % at 5 and +21 % at 20 on Wi-Fi; +20 % at 20 on the cell) and removes the one real loss. All remaining losses are at most 1.9 %. Same result on held-out seeds. Validated (simulation)

### Two camera drones on real hardware

**Setup.** The Jetson ran as a second camera drone: the same controller, onboard YOLOv8 on its GPU (FP16; YOLOv8s-640 in 39 ms), offloading to the laptop. It also kept serving the Pi's edge path, so its GPU was shared. Both cameras streamed the same labeled video and sent to the one laptop, which ran one worker per camera on its single GPU over its single Wi-Fi link, plus the live coordinator. The coordinator connects out to both cameras, takes a report from each every second and decides which cameras may use the laptop (`coordinator.py`, `tools/arun2.sh`). Every camera ran forecaster v2 live.

**Campaign.** 2 scenarios (clean link; failure mission) × 4 settings × 3 repetitions = 24 runs, shuffled, 21:48–22:58 on 6 October, no outages. Settings:

- **Pi alone:** the reference;
- **two cameras, v2, coordinator logging only;**
- **two cameras, v2, coordinator active;**
- **two cameras, fixed JPEG to the laptop's YOLOv8m.**

| Scenario | Setting | Pi camera sAP | Jetson camera sAP | Swarm mean | Pi availability |
| --- | --- | --- | --- | --- | --- |
| Clean link | Pi alone | 0.0806 ± 0.0164 | — | — | 0.987 |
| Clean link | Two cameras, v2 | 0.0715 ± 0.0184 | 0.0782 ± 0.0025 | 0.0749 ± 0.0082 | 0.988 |
| Clean link | Two cameras, v2 + coordinator | 0.0718 ± 0.0167 | 0.0786 ± 0.0016 | 0.0752 ± 0.0078 | 0.979 |
| Clean link | Two cameras, fixed laptop | 0.0772 ± 0.0165 | 0.0631 ± 0.0060 | 0.0702 ± 0.0102 | 0.962 |
| Failure mission | Pi alone | 0.0443 ± 0.0072 | — | — | 0.757 |
| Failure mission | Two cameras, v2 | 0.0360 ± 0.0035 | 0.0784 ± 0.0007 | 0.0572 ± 0.0018 | 0.682 |
| Failure mission | Two cameras, v2 + coordinator | 0.0394 ± 0.0028 | 0.0787 ± 0.0013 | 0.0590 ± 0.0015 | 0.695 |
| Failure mission | Two cameras, fixed laptop | 0.0215 ± 0.0019 | 0.0663 ± 0.0303 | 0.0439 ± 0.0152 | 0.190 |

Streaming AP with forecaster v2 (live camera motion), mean ± 95 % interval over 3 repetitions. The Jetson camera's link was not impaired in the mission (netem acts on each camera's own interface for the paths it has).

- **Sharing the ground station has a real cost**The Pi camera loses 0.0088 ± 0.0021 sAP when a second camera shares the laptop (paired, 6 of 6): −11 % on a clean link, −19 % in the failure mission. Validated (hardware, 2 cameras)
- **Adaptive control beats fixed offloading in a swarm too**Swarm-mean sAP +0.0090 ± 0.0062 (v2) and +0.0101 ± 0.0074 (v2 + coordinator) over two cameras both sending to the laptop, ahead in 6 of 6 pairs each. The fixed Pi camera's availability collapses to 0.19 in the mission. Validated (hardware, 2 cameras)
- **With two cameras the coordinator rarely acts**It admitted both cameras in about 124 of 125 one-second windows: by its own rule, two cameras sharing the laptop are worth more than taking turns. Coordinated and uncoordinated runs therefore differ only by noise (+0.0011 ± 0.0027 swarm mean, not significant). The live mechanism works (reports every second, decisions logged, no failures). Its benefit is expected from 3–5 cameras on, as in simulation, which needs the extra boards. Inconclusive (needs more cameras)

Files: `experiments/results/hardware/swarm_duo/` (per-camera runs, detections, live forecaster data, coordinator logs `coord_*.json`), `swarm_duo_summary.json`, log `swarm_duo.log`.

### Does the simulator match the hardware?

To make the swarm simulation credible, the simulator was checked against the real runs (`validation/hardware/sim_vs_real.py`). Every live run of a fixed single-server strategy was rebuilt in the simulator from that run's own measurements, with nothing fitted:

- link speed in unimpaired phases: the median the camera measured in that run;
- rate-limited phases: the configured limit, capped by that speed;
- blackouts: zero;
- frame size, encoding time, server time and round trip: measured.

The simulator then predicted on-time results per second for each of 528 phases (44 runs across the three Wi-Fi campaigns), compared with the measured values.

| Phase type | Phases | Measured | Predicted (pipelined) | Predicted (stop-and-wait) | Error, stop-and-wait |
| --- | --- | --- | --- | --- | --- |
| Unimpaired | 191 | 14.2 | about 2× | 15.2 | 3.7 /s (r = 0.81) |
| Rate-limited | 211 | 2.6 | — | 3.6 | 1.4 /s (r = 0.77) |
| Blackout | 85 | 0.0 | 0.0 | 0.0 | 0.0 |
| Unimpaired, right after a blackout | 41 | 3.4 | — | 14.6 | 12.2 /s |
| **All except post-blackout** | **487** | **6.7** | — | **7.5** | **2.0 /s (r = 0.91)** |
| **All phases, conditions as actually applied (13 Oct)** | **528** | **6.4** | — | **7.1** | **1.6 /s (r = 0.947)** |

- **Protocol matters.** The simulator first predicted about twice the measured rate on clean links. The cause was not the network model but the controller's protocol. On the hardware, a path gets its next frame only after the previous result has returned (one frame in flight), while the simulator pipelined. With that rule modelled through the simulator's existing link-hold parameter (server time + round trip), it matches with correlation 0.91 and an average error of 2.0 results/s outside the post-blackout phases, and 0.947 / 1.6 results/s over all 528 phases once the conditions actually applied are modelled (correction below).
- **Correction (13 Oct): there is no blackout-recovery gap.** Those 41 "unimpaired, right after a blackout" phases were not unimpaired: our emulation kept the previous phase's bandwidth limit (G14). Rebuilt with the conditions actually applied, the simulator matches all 528 phases with correlation 0.947 and an average error of 1.57 results/s (`sim_vs_real_stopwait_persist.json`). The earlier reading (slow TCP recovery, latency 389 ms) is retracted.

Files: `experiments/results/hardware/sim_vs_real.json` (pipelined), `sim_vs_real_stopwait.json` (with the protocol rule; all rows and the recovery times).

**Limits of this simulation**

The simulated adaptive controller is the paper's single-path one. It does not have the hardware controller's parallel multi-server dispatch, its smaller models, or its 480 and 320 px variants. Accuracy here is COCO mAP, not aerial accuracy, and the 300 ms deadline overstates quality on drone video (Part 12). Treat the numbers as trends with swarm size. The two-camera hardware test planned for the mesh is the real-world check.

## PART 14Phase F: motion forecasting of stale detections

### Why it is needed

Part 12 measured that aerial detections lose most of their accuracy within a few frames: 58 % gone at 100 ms and 93 % at 267 ms, because the drone and the objects move. Every offloading strategy shows the drone results that are 50–300 ms old. Instead of only choosing fresher results, the drone can move each old box to where its object should be now.

### Method

- When a result arrives, its boxes are matched to the previous result's boxes: same class, IoU at least 0.3, with the previous boxes first moved forward to the new capture time.
- Each matched box gets a velocity: 0.3 × (displacement / time) + 0.7 × its previous velocity. Unmatched boxes get zero velocity.
- When a result is shown, every box is shifted by velocity × its age (at most 1 s). The box size is kept.
- It is causal: it only uses results that have already arrived. It needs no extra traffic. On the Pi 5 it costs 3.9 ms per arriving result (100 boxes) and 0.06 ms per displayed frame (measured). Code: `validation/hardware/forecast.py`, `--forecast` in `stream_ap.py`.

### Tuning, kept apart from the test

The five settings (smoothing, match threshold, minimum confidence, camera-motion fallback, horizon; 128 combinations) were chosen on VisDrone-VID **train**: 2,241 frames, YOLOv8s detections computed on the laptop CPU so the campaign's GPU was untouched. The replay used one result every 2 frames, shown 0–600 ms late. The chosen setting was then frozen and applied to the 108 campaign runs on VisDrone-VID **val**.

The decay curve below was then measured with the frozen forecaster: each result is shown exactly the stated time after its capture, with one result every 2 frames. The curve without forecasting reproduces the earlier GPU measurement of Part 12 (41 % against 42 % kept at 100 ms; 22 % against 21 % at 167 ms), which cross-checks the CPU detections.

| Age of the shown result | 0 ms | 100 ms | 167 ms | 267 ms | 400 ms | 600 ms |
| --- | --- | --- | --- | --- | --- | --- |
| Accuracy kept, no forecasting | 100 % | 41 % | 22 % | 7 % | 2.6 % | 1.4 % |
| Accuracy kept, velocity forecaster (v1) | 100 % | 77 % | 63 % | 47 % | 33 % | 20 % |
| **Accuracy kept, camera-aligned forecaster (v2)** | 100 % | **85 %** | **75 %** | **60 %** | **45 %** | **30 %** |

Share of fresh accuracy kept when a detection is shown late, VisDrone-VID train, one result every 2 frames, each result shown exactly the stated time after capture. Both forecasters frozen before this measurement (`staleness_decay_forecast.json`, `staleness_decay_forecast_v2.json`).

### On the real campaign

On the 108 Wi-Fi runs it raised streaming AP for **every** policy: median +32 % (all servers, no adaptation), +37 % (v2), +48 % (v3), +47 % (fixed laptop), +53 % (rule-based fallback), +67 % (onboard). The ranking of the policies hardly changes. Forecasting stacks on top of any scheduler. Validated

**What it changes for the controller**

v3's staleness objective was built on the no-forecasting decay curve, which drops to 7 % at 267 ms. With forecasting the real curve is far flatter (47 % at 267 ms). So v3 values freshness too much. v3 was therefore rebuilt on the forecasting curve and tested next.

### Forecaster v2: measuring the camera's own motion

**Idea.** On a drone most of the apparent motion in the image is the camera's own: the drone flies, turns and climbs. The first forecaster could only guess it from the boxes. But the drone holds every camera frame, so it can **measure** it. For each new frame: about 200 corner points on the background, tracked from the previous frame with pyramidal Lucas–Kanade optical flow, and a RANSAC fit of a similarity transform (rotation, scale, shift). Moving objects are rejected as outliers. Chaining these per-frame steps gives the camera motion between any two frames (`validation/hardware/egomotion.py`).

**Forecast.** An old detection is first carried from its capture frame to the current frame with the measured camera motion, then moved by its object's own velocity. That velocity is estimated after removing the camera motion, so it describes only the object.

**Tuning, again on train only.** 24 new settings (smoothing, match threshold, with or without object velocity, with or without box-size extrapolation) were run alongside the v1 winner on the same training replay. The best uses camera alignment plus object velocity (smoothing 0.3, IoU 0.3). Size extrapolation slightly hurt, and camera alignment alone barely helps (AP 0.039 against 0.029 at 167 ms). It raised mean AP over the lags from 0.0755 (v1) to 0.0942 (+25 %). This setting was frozen before any test run was scored. The old forecaster reproduces its earlier numbers exactly in the new code (0.1002 and 0.0513 at 167 and 400 ms).

**Cost on the drone.** Camera tracking takes 2.7 ms per frame on the Pi 5 (p95 3.1 ms, measured on VisDrone frames), about 8 % of one core at 30 fps.

**On all 144 real Wi-Fi runs** (rescored offline with the frozen setting):

- **Better than the v1 forecaster in every one of the 144 runs**Over the 108-run campaign: median +51 %, smallest gain +25 %, 108 of 108 runs improved. Over the 36-run campaign: median +37 % to +45 % per policy, 36 of 36 improved. Validated
- **Roughly doubles streaming AP compared with no forecasting**Median gain per policy: +80 % (all servers, no adaptation) to +156 % (rule-based fallback). For v2 +85 %, for v3 + forecasting +92 %, for fixed laptop YOLOv8m +133 %. Validated

### Strong forecasting changes which policy wins

Streaming AP with the v2 forecaster, 108-run campaign (mean ± 95 % interval, best in each scenario in bold):

| Policy | Ground fails first | Jetson fails first | Random | No impairment |
| --- | --- | --- | --- | --- |
| v2 with aerial accuracy | **0.0391 ± 0.0026** | 0.0444 ± 0.0148 | **0.0402 ± 0.0123** | 0.0534 ± 0.0433 |
| v2 multi-server (A_full) | 0.0385 ± 0.0052 | 0.0338 ± 0.0412 | 0.0360 ± 0.0112 | 0.0610 ± 0.0130 |
| v3 (original) | 0.0375 ± 0.0077 | **0.0486 ± 0.0084** | 0.0347 ± 0.0129 | 0.0474 ± 0.0618 |
| Single-path rate adaptation | 0.0252 ± 0.0080 | 0.0465 ± 0.0174 | 0.0359 ± 0.0015 | 0.0679 ± 0.0232 |
| All servers, no adaptation | 0.0368 ± 0.0057 | 0.0385 ± 0.0022 | 0.0343 ± 0.0149 | 0.0535 ± 0.0072 |
| Fixed laptop YOLOv8m q90 | 0.0195 ± 0.0021 | 0.0476 ± 0.0064 | 0.0337 ± 0.0175 | **0.0799 ± 0.0071** |
| Rule-based fallback | 0.0246 ± 0.0013 | 0.0377 ± 0.0040 | 0.0273 ± 0.0122 | 0.0633 ± 0.0083 |
| Fixed Jetson YOLOv8s q90 | 0.0378 ± 0.0020 | 0.0151 ± 0.0008 | 0.0249 ± 0.0239 | 0.0553 ± 0.0115 |
| Fixed onboard YOLOv8n 320 | 0.0186 ± 0.0010 | 0.0183 ± 0.0028 | 0.0181 ± 0.0022 | 0.0178 ± 0.0009 |

- **When links fail, an adaptive controller is still best.** In all three impaired scenarios the top policy is adaptive (v2 with aerial accuracy twice, v3 once). Fixed strategies collapse when their one server fails: the laptop to 0.0195 when the ground link fails, the Jetson to 0.0151 when the Jetson fails.
- **On a clean link, the big model wins clearly.** Fixed laptop YOLOv8m reaches 0.0799 against 0.0610 for v2. With strong forecasting, a slower but more accurate result loses little to its age, so accuracy matters more than speed.
- **Why the controllers lag there.** All controllers were built for no forecasting or the v1 forecaster. Their objectives still over-value speed and under-use YOLOv8m. The fix follows directly from claim 4 in Part 20: rebuild the objective on the v2 decay curve. That is the next hardware test.
- **Paired over all scenarios**, v2 still beats onboard (+119 %, significant) and the Jetson (+9 %, significant). Against the other policies, intervals cross zero.

Files: `experiments/results/hardware/forecast_tuning_v2.json`, `staleness_decay_forecast_v2.json`, `vid_campaign_wifi_summary_v2.json/.log`, `vid_campaign_wifi_fc_summary_v2.json/.log`; camera-motion chains in `datasets/*/egomotion.npz`.

### v3 rebuilt on the forecasting decay curve: paired Wi-Fi campaign

v3's objective was rebuilt on the forecasting decay curve above (`--decay staleness_decay_forecast.json`; policy "v3 + forecasting"). It ran in a paired campaign against v2 and the old v3 on the same Wi-Fi: 4 scenarios × 3 repetitions × 3 policies = 36 runs in shuffled order, 06:52–08:29 on 6 October, no outages. Results are scored with forecasting applied. The quality-aware holding rule uses the forecasting curve, as the drone would if it forecasts.

| Scenario | v2 sAP | old v3 sAP | v3 + forecasting sAP | v2 availability | old v3 availability | v3 + forecasting availability |
| --- | --- | --- | --- | --- | --- | --- |
| Ground fails first | 0.0223 ± 0.0116 | 0.0232 ± 0.0071 | **0.0242 ± 0.0216** | 0.83 ± 0.11 | 0.75 ± 0.01 | **0.997 ± 0.006** |
| Jetson fails first | 0.0243 ± 0.0388 | 0.0327 ± 0.0203 | **0.0349 ± 0.0089** | 0.75 ± 0.37 | 0.81 ± 0.12 | **0.999 ± 0.001** |
| Random | 0.0273 ± 0.0105 | **0.0277 ± 0.0128** | 0.0218 ± 0.0033 | 0.92 ± 0.17 | 0.88 ± 0.17 | **0.999 ± 0.000** |
| No impairment | **0.0618 ± 0.0081** | 0.0616 ± 0.0051 | 0.0559 ± 0.0184 | **0.998 ± 0.004** | 0.99 ± 0.02 | 0.99 ± 0.04 |

- **Accuracy: no significant difference.** Over the 12 pairs, v3 + forecasting is ahead of v2 on the mean by 0.0003 ± 0.0062 sAP, but v2 is ahead in 8 of 12 pairs (median +13.5 % for v2). v3 + forecasting wins both failure scenarios and loses the random and clean ones. Inconclusive
- **Availability: a clear, consistent gain.** v3 + forecasting held a detection under 300 ms old 99.0–99.9 % of the time in every scenario, with very tight intervals. v2 managed 75–92 % under impairment and the old v3 75–88 %. Mean age of information fell from 191–212 ms (v2) to 142–156 ms in the two failure scenarios. Validated (Wi-Fi, 3 repetitions)
- **The earlier v2 lead over the old v3 did not repeat.** In campaign A, v2 led the old v3 by a median 16 %. In this session they are tied (median +0.2 %). Between-session variation on a shared Wi-Fi is as large as the differences between adaptive controllers. Only the controlled mesh campaign with 5 repetitions can rank them.
- **Forecasting again helped every policy:** median +41 % (v2), +42 % (old v3), +35 % (v3 + forecasting).

Files: `experiments/results/hardware/vid_campaign_wifi_fc/`, `vid_campaign_wifi_fc_summary.json/.csv/.log`. The forecaster costs 3.9 ms per arriving result (100 boxes) and 0.06 ms per displayed frame on the Pi 5 (measured).

### Controller rebuilt for forecaster v2, with the forecaster running live: 80-run campaign

**What ran.** v3 rebuilt on the decay curve of the camera-aligned forecaster ("v3 + forecasting v2", `--decay staleness_decay_forecast_v2.json`) was compared with v2, fixed laptop YOLOv8m and v3 + forecasting v1. Setup: 4 scenarios × 5 repetitions × 4 policies = 80 runs, shuffled, on the shared Wi-Fi, 16:14–21:37 on 6 October. In **every** run the forecaster ran live in the Pi's camera loop: camera motion every frame, velocities on every arriving result, the held result forecast every frame. The extra load on the Pi was therefore the same for all policies. Each run saved what the Pi computed, and the scores below use the Pi's live camera motion.

**Interruption.** The Pi's Wi-Fi dropped at about 17:55 (the board did not reboot). The outage guard paused the campaign until it came back at 19:31. One run in progress was lost and rerun at the end, so all 80 are complete. Wi-Fi power saving on the Pi, which was on, was then switched off (runtime setting only).

| Scenario | v3 + forecasting v2 | v3 + forecasting v1 | v2 | Fixed laptop YOLOv8m |
| --- | --- | --- | --- | --- |
| Ground fails first | **0.0434 ± 0.0060** | 0.0428 ± 0.0051 | 0.0342 ± 0.0098 | 0.0188 ± 0.0056 |
| Jetson fails first | **0.0529 ± 0.0062** | 0.0494 ± 0.0115 | 0.0475 ± 0.0140 | 0.0506 ± 0.0045 |
| Random | 0.0304 ± 0.0104 | **0.0357 ± 0.0046** | 0.0332 ± 0.0137 | 0.0257 ± 0.0161 |
| No impairment | **0.0766 ± 0.0325** | 0.0607 ± 0.0455 | 0.0701 ± 0.0367 | 0.0684 ± 0.0479 |
| *Availability (range over scenarios)* | **0.995–0.998** | 0.995–0.997 | 0.805–0.914 | 0.177–0.778 |

Streaming AP with forecaster v2 (quality-aware holding with the v2 decay curve), mean ± 95 % interval over 5 repetitions.

- **v3 + forecasting v2 beats v2, and the difference is significant**Paired over 20 runs: +0.0045 ± 0.0035 sAP (the interval excludes zero), median +8.9 %, ahead in 13 of 20. With the newest-result rule: +0.0038 ± 0.0037, ahead in 14 of 20. It is best in 3 of 4 scenarios. Validated (Wi-Fi, 5 repetitions)
- **It closes the clean-link gap**With the earlier controllers, fixed laptop YOLOv8m won on a clean link (Part 14 above). Rebuilt on the v2 curve, v3 now leads there too (0.0766 against 0.0684). The objective now values accuracy correctly.
- **It keeps a fresh detection 99.5–99.8 % of the time**That holds in every scenario, against 81–91 % for v2 and 18–78 % for fixed laptop.
- **The live forecaster gives exactly the offline result**Scores using the camera motion computed live on the Pi are identical to the offline ones. The live forecaster ran over 80 runs with 0 errors.
- **v2 still beats the fixed laptop**+0.0054 ± 0.0054 (at the edge of significance), ahead in 15 of 20.
- **Cost found: onboard inference slows down**Camera tracking and the forecaster share the Pi's 4 CPU cores with onboard inference. Median YOLOv8s-320 time rose from 170 to 412 ms and YOLOv8n-320 from 93 to 110 ms, which weakens the onboard fallback in blackouts. Tracking every other frame, or at a lower resolution, is the obvious fix; not yet tested.

Files: `experiments/results/hardware/vid_campaign_wifi_fc2/` (runs with `_livefc.npz`), `vid_campaign_wifi_fc2_summary_v2_live.json/.log` (live camera motion), `vid_campaign_wifi_fc2_summary_v2.*` (offline), log `vid_campaign_wifi_fc2.log`.

## PART 15Phase G: energy, power and heat

**Why this part exists.** Until now the controllers optimized accuracy and freshness only. Energy was reported afterwards as a rough estimate (v1 had a tiny energy tie-breaker; v2 and v3 had none). This part measures energy and heat properly on both boards, rescores **every** earlier campaign with the measured model, and adds an energy- and heat-aware controller (v4).

### G1. What was measured

Script `validation/hardware/energy_profile.py`, run on each board. Whole-board power was sampled 10 times a second from the Pi's power-management chip (all rails) and the Jetson's INA3221 input sensor. SoC temperature and CPU clock were logged alongside. Each state ran for 20 s. Inference ran back to back, with the same thread counts as the controller.

| State | Pi 5 power | Jetson power | Energy per frame above idle |
| --- | --- | --- | --- |
| Idle (Jetson with clocks locked, as in all campaigns) | 1.89 W | 4.08 W | — |
| JPEG encoding, 30 fps (640 q90 / 640 q50 / 320 q50) | +0.16–0.21 W | — | 5–7 mJ |
| YOLOv8n 320 onboard | 6.0 W, 78 ms | 5.7 W, 25 ms | Pi 324 mJ · Jetson 40 mJ |
| YOLOv8s 320 onboard | 6.1 W, 176 ms | 6.8 W, 25 ms | Pi 741 mJ · Jetson 67 mJ |
| YOLOv8s 640 onboard | 5.0 W, 718 ms (throttled) | 9.7 W, 29 ms | Pi 2,229 mJ · Jetson 163 mJ |
| YOLOv8m 640 | — | 10.6 W, 57 ms | Jetson 371 mJ |
| Radio transmit at 2 / 5 / 10 Mbit/s; flat out | +0.27 / +0.30 / +0.33 W; +1.05 W at 52 Mbit/s | +0.09 W at 5 Mbit/s | ≈ 0.2 W + 0.016 W per Mbit/s while sending (linear fit of the Pi's measured points) |
| Live motion forecaster (camera tracking every frame + velocity updates) | +0.29 W (6-min steady test) | — | — |

The Pi PMIC rails exclude 5 V conversion losses, so Pi numbers are a lower bound. The Jetson's receive power was measured once, at 21 Mbit/s (+0.21 W above idle), and the model applies it at every link speed — at lower link rates that slightly over-counts the edge drone's receive energy. The Jetson profile was re-measured on 9 October after the board was reflashed (`energy/energy_profile_jetson_20261009.json`): idle and all five inference states matched the 8 October values within 0.1 W (idle 4.17 against 4.08 W), so the same constants stand. A short forecaster measurement taken right after a hot inference state read +0.67 W: hot silicon leaks more power. The 6-minute steady measurement (+0.29 W) is used.

- **On the Pi, thinking costs far more than talking**One YOLOv8s-640 inference costs 2.2 J; sending the same frame as a JPEG costs about 0.03 J (encode plus radio), roughly **80× less**. Onboard inference roughly triples the Pi's power (1.9 → 5–6 W).
- **The Jetson is about 14× more energy-efficient per inference than the Pi**0.16 J against 2.2 J for YOLOv8s-640. But it idles at 4.1 W even when doing nothing, so as a flying edge drone it is a large fixed cost.

### G2. Heat: how much the Pi can sustain

Script `validation/hardware/thermal_steady.py`: constant load levels held for 6 minutes each, steady temperature taken over the last minute, actual ARM clock read from the firmware.

| Sustained load | Mean power | Steady temperature | ARM clock (last minute) |
| --- | --- | --- | --- |
| Idle | 1.66 W | 54 °C | 1,500 MHz |
| JPEG encoding 30 fps | 1.86 W | 59 °C | 1,670 MHz |
| Live forecaster 30 fps | 1.95 W | 60 °C | 1,769 MHz |
| YOLOv8n onboard 15 % of the time | 2.71 W | 68 °C | 2,291 MHz |
| YOLOv8n onboard 30 % of the time | 3.49 W | 76 °C | 2,365 MHz |
| YOLOv8n onboard 50 % of the time | 3.69 W | 84 °C | **2,070 MHz (throttling)** |
| YOLOv8n onboard all the time | 4.15 W | 85 °C | **1,568 MHz (−35 %)** |

- **+12.7 °C per extra watt; throttling from about 3.6 W sustained**A linear fit of the steady levels below the throttle limit gives T = 34.4 °C + 12.7 °C/W × P (the fitted constants are stored in `energy_constants.json`). The firmware starts lowering the clock at about 80 °C (about 3.6 W) and holds 85 °C at about 4 W by cutting the clock by 35 %. That is why YOLOv8s slowed from 576 to 718–758 ms in earlier tests. Heating is fast: 72 → 85 °C in 17 s under YOLOv8s. Cooling takes minutes (87 → 64 °C in 150 s).
- **The Jetson does not overheat**Measured with a 24-minute sustained YOLOv8m @ 640 heat run (9 October, 1 Hz power/temperature/clock log, `energy_profile_jetson_20261009.json`): 10.7 W throughout, temperature 52 → 61 °C and **steady over the last minute** (61.0–61.7 °C, mean 61.2), clock pinned at 1,510 MHz the whole time, **no throttling**; it cools back to 50 °C in 5 minutes. At its hottest sustained load the fan holds the Jetson about 19 °C below the Pi's ~80 °C throttling point. A shorter 5-minute heat run on 8 October had peaked at 60.3 °C and was still creeping — the 24-minute run shows where it settles.
- **A 24-minute Pi heat run confirms the throttling onset**The same 7 load levels held 24 minutes each instead of 6 (`energy/thermal_steady_pi_24min.json`, 9–10 October, board clock 03:04–06:16). The four YOLOv8n duty rows measured 2.62 W / 62.3 °C (clock 2,314 MHz), 3.38 W / 71.5 °C (2,339 MHz), 3.77 W / 81.8 °C (2,347 MHz with dips to 1,600 — throttling onset), 4.46 W / 84.4 °C (1,834 MHz — throttled). Throttling again begins between the 30 % and 50 % duty levels, and the 6-minute fit above predicts the 50 %-duty row to within half a degree (82.3 predicted, 81.8 measured). The run's low-power rows are **not** a clean replication of the table, and the logs say why: the idle level started from a board still warm after setup (67.8 °C) and settled at 64 °C at 1.81 W (the run's completion poll opened an SSH connection every minute, against 1.66 W in the table); in the encode level the encoder stopped part-way (its power fell to a near-idle 1.65 W, so its 54 °C row is a near-idle temperature, not encode); and the forecaster's temperature was still creeping at 24 minutes (64 → 73 °C), though its power (2.17 W, +0.36 W over that run's idle) supports the table's +0.29 W constant. The steady temperature of this fanless board is sensitive to ambient and to the board's thermal history — the two runs bracket it (the duty rows sit 1–6 °C apart, idle 54 vs 64 °C) — but every throttling conclusion holds in both runs.
- **Energy and accuracy are coupled through heat**More onboard work → hotter → throttled → slower inference → staler results → lower accuracy. The fanless Pi cannot sustain the onboard load the adaptive controllers put on it.

### G3. The energy model and flight time

`validation/hardware/energy_model.py` turns the measurements into energy per run:

- **Camera drone:** Pi idle × duration, plus each onboard inference's measured energy, plus each JPEG's encoding, plus radio energy for its bytes at the link speed measured in that run, plus the forecaster's power when forecasting is used.
- **Edge drone:** the Jetson's idle power plus every inference it served plus receiving. It counts only when a strategy uses it; the laptop is on the ground and not counted.
- **Flight time:** usable battery ÷ (flight power + perception power), for three drone classes:

| Drone class | Flight power | Usable battery | Source |
| --- | --- | --- | --- |
| 249 g mini drone | 33.5 W | 17.3 Wh | DJI Mini 2 published spec (2,250 mAh × 7.7 V, 31 min) |
| 1.2 kg quadcopter | 110 W | 59 Wh | Paper's hover model; 4S 5,000 mAh, 80 % usable |
| 1.5 kg drone carrying the Jetson | 154 W | 89 Wh | Same hover model; 6S 5,000 mAh, 80 % usable |

The flight powers and usable-battery fractions above are the only **estimates** in this part: a momentum-theory hover model with assumed 80 % usable charge, not measured on a flying drone. Everything they are divided against — the perception powers, inference energies, radio and encoding — is measured on the boards or from a campaign log.

**What this means.** Perception is 2–5 W against 33–154 W of flight power. On a 1.2 kg drone the choice of strategy changes flight time by only about 2–3 %; on a 249 g drone by up to about 9 %. Energy matters most through **heat** (throttling), through the **edge drone's** 4–6 W, and for **small drones**. The metric that combines everything is **mission perception** = streaming AP × flight time ("accuracy-minutes").

### G4. Every placement with energy (Part 7 rescored)

| Placement | On time (model) | Drone energy per frame |
| --- | --- | --- |
| Pi alone (YOLOv8s) | 0 | 2,046 mJ |
| Pi split at layer 4 → Jetson (PDF's mothership) | 0 | 999 mJ |
| Pi split at layer 4 → laptop | 0 | 743 mJ |
| Pi JPEG → Jetson processes | 17.0 /s | 317 mJ |
| Jetson alone (camera on the Jetson) | 15.0 /s | 254 mJ |
| Jetson JPEG → laptop | 14.4 /s | 44 mJ |
| Pi JPEG → Jetson relay → laptop | 14.2 /s | 39 mJ |
| **Pi JPEG → laptop** | **30.0 /s** | **28 mJ** |

Energy above idle on the drone-carried devices (Pi incl. radio; Jetson when it flies), from the Part 6 measured powers. Frame rates are the placement model's; live runs were lower (Part 7).

**The professor's sense → edge → cloud pipeline (mothership split) costs about 35× more drone energy per frame than sending a JPEG to the ground, and is never on time.** Splitting is worst on every axis: speed, accuracy and energy.

### G5. Controllers v1 and v2 rescored (Parts 9–10)

| Policy (v2 campaign, mean over 4 scenarios) | Accuracy-weighted on-time /s | Pi power | Edge drone | Per Pi watt | Steady Pi temperature |
| --- | --- | --- | --- | --- | --- |
| v2 (A_full) | **22.4** | 4.05 W | 5.0 W | 5.5 | ≈ 86 °C → throttles |
| All servers, no adaptation | 19.1 | 5.11 W | 5.3 W | 3.7 | would throttle |
| v2 without onboard (A_paths) | 18.2 | 2.66 W | 4.9 W | **6.9** | 68 °C |
| Fixed laptop JPEG q50 640 | 13.7 | 2.16 W | — | 6.4 | 62 °C |
| Fixed onboard YOLOv8n | 6.2 | 5.08 W | — | 1.2 | would throttle |

Pi power and edge-drone power here are the **model reconstruction** from each run's logs (these campaigns predate the power logger); the first live-measured Pi power is in G9.

In v1, the adaptive controller ran at 2.95 W against 2.35–2.68 W for fixed JPEG offloading; the layer-1 split (5.6 W) and onboard-only (4.8 W) were worst. **In both campaigns the most energy-efficient adaptive policy is the one that does not use onboard inference.**

### G6. Task-level campaigns with energy (Parts 12 and 14)

| Policy (80-run campaign, pooled) | sAP (forecaster v2) | Fresh-detection share | Pi power | Steady Pi temp | Edge drone | sAP per Pi watt | Flight: 1.2 kg / 249 g | Mission perception, 249 g |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v3 + forecasting v2 | **0.0508** | **99.6 %** | 4.17 W | ≈ 87 °C, throttles | 4.8 W | 0.0122 | 31.1 / 27.6 min | **1.41** |
| v3 + forecasting v1 | 0.0472 | 99.6 % | 4.28 W | ≈ 89 °C | 4.9 W | 0.0110 | 31.1 / 27.5 min | 1.31 |
| v2 | 0.0463 | 85 % | 4.38 W | ≈ 90 °C | 4.9 W | 0.0106 | 31.1 / 27.4 min | 1.28 |
| Fixed laptop YOLOv8m | 0.0409 | 43 % | **2.41 W** | 65 °C | — | **0.0170** | **31.6 / 28.9 min** | 1.18 |

Pi power includes the forecaster. Pi and edge power in this table are the model reconstruction — the first live-measured Pi power is in G9; the Jetson was not power-logged live in any campaign so far, which the next campaign fixes. Mission perception = sAP × flight minutes of a 249 g drone. In the 108-run campaign the same pattern holds: adaptive policies 4.7–5.3 W, fixed offloading 2.4–2.6 W, onboard only 5.2 W; fixed laptop YOLOv8m and single-path rate adaptation have about 2× the accuracy per watt of the adaptive policies.

- **Our best controller wins on accuracy, freshness and mission perception, but not on energy**It uses about 1.8 W more on the Pi than fixed offloading, would throttle in sustained flight, and keeps a 4.8 W edge drone working. On a 249 g drone its accuracy gain outweighs its 1.3 minutes shorter flight (mission perception 1.41 against 1.18).
- **Onboard inference is the energy problem: about 40–54 % of the Pi's power for 3–5 % of the accuracy**Rescoring the adaptive runs with their onboard results removed (an offline estimate that ignores scheduling side effects) cuts Pi power from 4.2–5.3 W to about 2.4–2.5 W. Accuracy falls by only a median 2.7–5.3 %. For "all servers, no adaptation" accuracy even **rises** by 5.8 %: its low-quality onboard results displace better ones.
- **The earlier energy estimates were far too low**The old in-run estimate (onboard time × 2.7 W + transmit time × 0.31 W) left out the idle floor, encoding and the forecaster. In the same v4 test run it said 1.22 W where the board measured 3.56 W. All energy numbers in this part replace those estimates.

### G7. Swarms with energy

- **Two real cameras (Part 13).** The Pi camera runs at 4.2–5.0 W in the adaptive settings, about 89–98 °C steady, so it would throttle; with fixed offloading it runs at 2.3–2.5 W. The Jetson as a camera draws about 7.4 W with adaptive control (mostly onboard GPU inference; model reconstruction from the runs' logs — the Jetson was not power-logged live) and 4.2 W with fixed offloading. Serving the Pi adds about 1 W, so the Jetson board totals about 8.5 W (model).
- **Calibrated simulation with measured board powers** (`swarm_calibrated.py --measured-power`):
  - In large Pi swarms the coordinator lowers per-drone power: 4.5 → 3.5 W at 10 drones and 2.7 W at 20, because drones waiting their turn skip work, while delivering more.
  - Jetson-class drones under congestion shift to onboard GPU inference, so per-drone power rises from 4.6 to 6.9 W at 20 drones. The coordinator trims that slightly while delivering 21 % more.
  - Caveat: the simulator charges JPEG preparation at full compute power, scaled for the Pi's slow CPU, so its offloading energy is pessimistic against the measured +0.2 W.

### G8. Controller v4: energy- and heat-aware

**Objective.** For every candidate (server, setting): v3's value minus μ × the candidate's **measured** energy per frame. The energy is the onboard inference energy, or encoding plus radio at the current link speed (`energy_constants.json`).

**The price μ is not hand-tuned.** It follows the Pi's **live measured** power, sampled 5 times a second, against a power budget by dual ascent: every second, μ ← max(0, μ + η (P̄ − budget)), with η = 0.1. This keeps the average power at the budget, the standard way to enforce an average constraint online.

**Budgets.** 3.5 W (thermal-safe, below the throttling region from G2) and 2.8 W (energy-saving, about 70 °C).

**Guards.**

- Above 78 °C, μ jumps to at least 1, which makes onboard inference expensive.
- When no link can deliver, onboard is not priced (unless the Pi is at 85 °C), because it is then the only source of perception.

Every run of the new campaign logs measured power, temperature and μ. Code: `--energy-aware --power-budget` in `adaptive2.py`; with the options off the controller is unchanged.

**Smoke test.** μ rose when the Pi hit 5.1 W, onboard inference dropped to a few frames in good phases and stayed on in the total blackout (82 frames), and the measured mean power was 3.56 W against a 3.5 W budget.

### G9. Energy campaign: v4 against the best controllers, with measured energy

**Setup.** v4 at a 3.5 W and a 2.8 W budget against v3 + forecasting v2, v2 and fixed laptop YOLOv8m. 4 scenarios × 5 repetitions = 100 runs, shuffled, on the shared Wi-Fi, 14:53–19:19 on 7 October, no outages, all 100 complete. Every run logged the Pi's measured power, temperature and (for v4) the energy price, 5 times a second, and ran the forecaster live. Accuracy is streaming AP with forecaster v2, using the live camera motion.

| Policy (pooled, 20 runs each) | sAP | Measured Pi power | sAP per **camera-drone** watt | Fresh-detection share | Mean Pi temp | Time at ≥ 80 °C | Flight: 1.2 kg / 249 g | Mission perception: 249 g / 1.2 kg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **v4, 2.8 W budget** | **0.0543 ± 0.0069** | 3.33 ± 0.11 W | 0.0166 | 87.1 % | 74.0 °C | **17 %** | 31.4 / 28.2 min | **1.53 / 1.71** |
| **v4, 3.5 W budget** | 0.0525 ± 0.0072 | 3.61 ± 0.10 W | 0.0147 | 86.8 % | 76.7 °C | 19 % | 31.3 / 28.0 min | 1.47 / 1.64 |
| v3 + forecasting v2 | 0.0470 ± 0.0080 | 4.47 ± 0.17 W | 0.0109 | **99.3 %** | 82.1 °C | 76 % | 31.1 / 27.3 min | 1.29 / 1.46 |
| v2 | 0.0465 ± 0.0067 | 4.24 ± 0.14 W | 0.0113 | 88.7 % | 81.5 °C | 67 % | 31.1 / 27.5 min | 1.28 / 1.45 |
| Fixed laptop YOLOv8m | 0.0463 ± 0.0105 | **2.65 ± 0.07 W** | **0.0171** | 51.1 % | 70.2 °C | 0 % | **31.6 / 28.7 min** | 1.33 / 1.46 |

The "sAP per camera-drone watt" column prices **only the Pi**; it is not a system-level efficiency (G10 below prices the whole swarm).

Mission perception = sAP × flight minutes. The adaptive policies also keep the Jetson edge drone busy at about 4.8–4.9 W (model-based; the Jetson was not power-logged live); the fixed laptop policy does not use it.

| Paired comparison (20 pairs) | sAP difference | Ahead in | Measured Pi power | Mission perception, 249 g |
| --- | --- | --- | --- | --- |
| v4 (2.8 W) − v3 + forecasting v2 | **+0.0074 ± 0.0028** | 17 / 20 | **−1.14 ± 0.19 W** | +0.245 ± 0.081 |
| v4 (2.8 W) − v2 | **+0.0078 ± 0.0034** | 18 / 20 | −0.91 ± 0.13 W | +0.250 ± 0.097 |
| v4 (2.8 W) − fixed laptop YOLOv8m | **+0.0080 ± 0.0052** | 16 / 20 | +0.68 ± 0.15 W | +0.205 ± 0.148 |
| v4 (3.5 W) − v3 + forecasting v2 | +0.0055 ± 0.0043 | 15 / 20 | −0.87 ± 0.18 W | +0.182 ± 0.123 |
| v4 (2.8 W) − v4 (3.5 W) | +0.0018 ± 0.0031 | 10 / 20 | −0.28 ± 0.09 W | +0.063 ± 0.086 |

- **The energy-aware controller is the most accurate controller, and uses 19–25 % less camera-drone power**v4 with a 2.8 W budget beats v3 + forecasting v2 by +0.0074 ± 0.0028 sAP (median +13 %, 17 of 20) and v2 by +0.0078 ± 0.0034, both significant, while measured Pi power falls by about 1 W. It also has the highest mission perception for both drone classes. Validated (Wi-Fi, 5 repetitions, measured energy) — for the camera drone. At whole-swarm level the picture reverses (G10).
- **Why saving energy raised accuracy**The onboard inferences v4 cuts were mostly low-quality (YOLOv8n/s at 320 px on aerial video) and competed with better offloaded results. They also loaded the Pi's 4 CPU cores and heat: with them, the Pi spent 76 % of the run at ≥ 80 °C, in the throttling region, slowing encoding, the camera loop and the forecaster for every result. v4 cuts that to 17 %. Energy, heat and accuracy are coupled, and pricing energy properly improves all three.
- **It nearly matches the most frugal strategy's accuracy per camera-drone watt while being far more accurate — but that prices only the Pi**0.0166 sAP per camera watt against 0.0171 for fixed laptop offloading, with +0.0080 sAP (significant) and 87 % against 51 % fresh-detection share. This column leaves out the edge drone entirely; the whole-swarm comparison is the opposite (G10).
- **The price: freshness**v4 keeps a detection under 300 ms old 87 % of the time against 99 % for v3 + forecasting v2. Onboard results were what filled short gaps. A mission that needs a continuous fresh detection should use v3 + forecasting v2 or a higher budget.
- **The 2.8 W budget is below what v4 can reach**Measured 3.33 W. The Pi's fixed floor (idle, forecaster, encoding, radio and the power logger itself) is already about 2.65 W, and v4 deliberately keeps onboard inference during blackouts. The 3.5 W budget was held (3.61 W).
- **The energy model matches the measurements**Model-predicted Pi power is within 0.1–0.4 W (about 5–10 %) of the live-measured power in all five policies.

Files: `experiments/results/hardware/vid_campaign_energy/` (runs with `measured_energy` logs), `vid_campaign_energy_summary.log`, `energy/energy_campaign_measured.json`, `energy/energy_campaign_summary.json`; profiles and constants in `energy/`.

### G10. The whole swarm: system-level energy (rescored, 9 Oct 2026)

Every run of every campaign has been rescored with the measured model in three **explicitly labelled** views of the whole drone swarm (camera drone + edge drone; code `energy_model.system_views`, outputs `energy/energy_<campaign>.json`, `energy/energy_all_summary.json`). The views are never mixed:

- **extra** — the edge drone flies anyway (it is on a mission regardless): system power = camera drone + the Jetson's **extra work only** (inference + receive, above its 4.08 W idle);
- **board** — the Jetson is carried for perception: + its **whole board** power including the 4.08 W idle;
- **dedicated** — the edge drone flies **only** for perception: + board + its 153.6 W flight power.

Pooled over the 100-run energy campaign (G9; 20 runs each; camera power is the model reconstruction, within 0.1–0.4 W of the live-measured power; edge power is model-based — the Jetson was not power-logged live in that campaign, which the next campaign fixes):

| Policy | sAP (fc v2) | Camera W | Edge W | System W: extra / board / dedicated | sAP per W: camera / extra / board | Swarm lifetime: 249 g / 1.2 kg | Swarm mission perception (249 g) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| v4, 2.8 W (A_eco_tight) | **0.0543** | 3.04 | 4.94 | 3.90 / 7.97 / 161.6 | 0.0183 / 0.0142 / 0.0069 | 28.4 / 31.5 min | **1.55** |
| v4, 3.5 W (A_eco) | 0.0525 | 3.22 | 4.92 | 4.05 / 8.13 / 161.7 | 0.0168 / 0.0132 / 0.0065 | 28.3 / 31.4 min | 1.49 |
| v2 (A_full) | 0.0465 | 4.14 | 4.93 | 5.00 / 9.08 / 162.7 | 0.0118 / 0.0097 / 0.0052 | 27.6 / 31.1 min | 1.29 |
| v3 + forecasting v2 | 0.0470 | 4.31 | 4.84 | 5.07 / 9.15 / 162.8 | 0.0116 / 0.0098 / 0.0053 | 27.5 / 31.1 min | 1.30 |
| Fixed laptop YOLOv8m | 0.0463 | 2.41 | 0 | 2.41 / 2.41 / 2.41 | **0.0189** / **0.0189** / **0.0189** | **28.9 / 31.6 min** | 1.34 |

Swarm lifetime = the **first drone to land**; in every setting that is the 249 g camera drone (28–29 min against about 33.6 min for the Jetson-carried edge drone), so swarm mission perception (sAP × swarm lifetime) tracks the camera drone's. Per-drone flight time for every class is in the same files.

- **Correcting the G9 efficiency claims at whole-swarm level**The G9 "sAP per Pi watt" numbers price only the camera drone. Counting the edge drone the picture changes: in the **extra** view (edge drone flies anyway) fixed offloading is 1.33× more energy-efficient than v4 at 2.8 W (0.0189 against 0.0142 sAP per watt); in the **board** view (the Jetson is carried only for perception) it is 2.7× (0.0189 against 0.0069), because v4's accuracy depends on a Jetson that idles at 4.08 W; in the **dedicated** view about 55×.
- **The stronger statement is across systems, not policies**A deployment that offloads JPEG to the laptop needs **no airborne edge drone at all**: 2.65 W measured, 0.0175 sAP per watt. v4's accuracy depends on keeping one in the air: Pi 3.33 W measured + Jetson 4.94 W model ≈ 8.3 W, 0.0066 sAP per watt — fixed offloading is **≈ 2.6× more energy-efficient as a whole system**. The edge drone earns its place through robustness (perception continues when the ground link fails), not through energy; this is the gap controller v4.2 prices (below).
- **What changes with v4.2**v4 priced only the camera drone's energy. v4.2 adds a second dual variable μ_edge on the **edge drone's extra power** with its own budget in watts above the Jetson's idle (the budget must be positive: extra power is never negative, so with a 0 budget μ_edge could only rise and would price the Jetson out for the rest of the run after its first use — a flaw in the first v4.2 draft, fixed 11 October; the campaign uses a binding 0.5 W budget and a non-binding battery-derived one), derives both budgets from battery + flight power when asked, takes live Jetson power from the worker's response headers, and lets the swarm coordinator give turns preferentially to more- or less-charged drones (`--energy-pref low|high|off`, both orderings measured). Every run of the new campaign logs both boards' power live (5 Hz power logger on the Jetson, measured power log on the Pi).

### G11. Campaign with live power on BOTH boards: v4.1, v4.2 (11 Oct 2026)

**Setup.** 6 policies × 4 scenarios × 5 repetitions = 120 runs, shuffled, on the shared Wi-Fi, 13:46–19:10 on 11 October, no outages, all 120 complete. For the first time **every watt is measured**: the Pi's power log (5 Hz) and the Jetson's live INA3221 log (`power_logger.py`, 5 Hz), plus the Jetson worker reporting its board power in every response. Accuracy = streaming AP with forecaster v2 running live. Reference = v4 at 2.8 W. Code `validation/hardware/summarize_measured.py`; data `vid_campaign_v42/`, `vid_campaign_v42_measured_summary.json`, `vid_campaign_v42_summary_v2_live.*`.

| Policy (pooled, 20 runs each) | sAP | Fresh-detection share | Pi W (measured) | Jetson W (measured, live) | Time ≥ 80 °C | Mean Pi temp | sAP per W: camera / extra / board | Mission perception, 249 g |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v4.1 (freshness target 95 %) | **0.0566** | **97.9 %** | 3.56 | 5.01 | 12 % | 72.6 °C | 0.0162 / 0.0128 / 0.0066 | **1.59** |
| v4.2 (edge drone priced, 0.5 W budget) | 0.0551 | 86.1 % | 3.36 | **4.78** | 10 % | 71.2 °C | **0.0165 / 0.0135 / 0.0067** | 1.55 |
| v4.2, budgets from battery (28-min mission) | 0.0536 | 87.4 % | 3.84 | 4.95 | 16 % | 74.2 °C | 0.0142 / 0.0115 / 0.0061 | 1.49 |
| v4 (2.8 W), reference | 0.0541 | 87.5 % | 3.48 | 4.97 | 13 % | 72.0 °C | 0.0158 / 0.0125 / 0.0064 | 1.52 |
| v3 + forecasting v2 | 0.0485 | 99.4 % | 4.73 | 4.94 | **67 %** | 80.9 °C | 0.0104 / 0.0088 / 0.0050 | 1.32 |
| Fixed laptop YOLOv8m | 0.0450 | 50.2 % | **2.79** | 0 (no edge drone) | 0 % | 68.1 °C | 0.0160 / 0.0160 / **0.0160** | 1.29 |

| Paired against v4 (20 pairs) | sAP | Fresh-detection share | Pi W | Jetson W | Time ≥ 80 °C |
| --- | --- | --- | --- | --- | --- |
| v4.1 | +0.0025 ± 0.0038 (13/20) | **+10.4 ± 3.3 points (19/20)** | +0.08 ± 0.10 | +0.04 ± 0.04 | −0.8 ± 4.3 points |
| v4.2 | +0.0009 ± 0.0040 (10/20) | −1.3 ± 4.0 points | −0.12 ± 0.11 | **−0.19 ± 0.10 (lower in 19/20)** | −3.8 ± 4.1 points |
| v4.2, battery-derived budgets | −0.0005 ± 0.0050 | 0.0 ± 3.6 points | **+0.36 ± 0.09 (20/20)** | −0.02 ± 0.05 | +2.4 ± 2.8 points |
| v3 + forecasting v2 | **−0.0056 ± 0.0034 (v4 ahead 18/20)** | +12.0 ± 3.5 points | **+1.25 ± 0.16 (20/20)** | −0.03 ± 0.05 | **+54 ± 9 points (20/20)** |
| Fixed laptop | **−0.0091 ± 0.0057 (v4 ahead 15/20)** | −37 ± 12 points | −0.69 ± 0.16 | −4.97 (no edge drone) | −13 ± 6 points |

- **The main energy result replicates with independent runs**Pricing the camera's energy (v4) again beats v3 + forecasting v2 on accuracy (+0.0056 ± 0.0034 sAP, ahead in 18 of 20; the 7 October campaign gave +0.0074 ± 0.0028), uses 1.25 W less Pi power, and cuts the time the Pi spends at or above 80 °C from 67 % to 13 %. Two campaigns, 40 pairs: saving energy keeps the fanless camera out of throttling and raises accuracy.
- **v4.1 recovers freshness at no cost**The freshness price raises the share of time the drone holds a detection under 300 ms old from 87.5 % to 97.9 % (+10.4 points, 19 of 20), close to v3's 99.4 %, while Pi power (+0.08 W), heat and accuracy stay those of v4 (sAP +0.0025, not significant). It has the highest accuracy and mission perception of all six policies. v4.1 removes the one cost v4 had.
- **v4.2 lowers the edge drone's power, but the effect is small**Pricing the Jetson's energy cut its measured board power by 0.19 ± 0.10 W (lower in 19 of 20), about a fifth of its extra work, with unchanged accuracy, and gave the best accuracy per watt of the adaptive policies in every view. Because the Jetson's 4.1 W idle floor dominates, the whole-swarm gain is modest. At realistic battery numbers (the battery-derived budget, 36.7 W for the edge drone) the edge price never binds, and the looser camera budget (3.57 W) only burns 0.36 W more for no accuracy. **The edge drone's energy is decided by whether it flies at all, not by how it is used.**
- **Measured Jetson power confirms the model**Live 4.8–5.0 W against the model's 4.8–4.9 W in the 100-run campaign (G9–G10). The system-level conclusions of G10 therefore stand on measured numbers.
- **Whole-swarm accuracy per watt (board view): fixed offloading 0.0160, v4.x 0.0061–0.0067, about 2.5×** less efficient, as G10 found. Fixed offloading needs no edge drone, but it is the least accurate (−0.0091 sAP) and holds a fresh detection only half the time (50 %). The adaptive policies buy accuracy and freshness with an airborne edge drone.

### Staleness by context, and the novelty re-check (11 Oct 2026)

**Does the decay depend on the situation?** `validation/hardware/decay_context.py` splits the measured decay by what a drone can compute live at decision time: camera speed (from the camera-motion tracker), crowding and the share of small objects, plus object size. Groups are fixed on the 8 training sequences and checked on the 7 held-out ones.

| Share of fresh accuracy kept at 100 ms (held-out) | Fast camera (> 48 px/s) | Slow / medium camera |
| --- | --- | --- |
| No forecasting | 13 % | 47–50 % |
| Forecaster v1 (velocity only) | 25 % | 68–71 % |
| Forecaster v2 (camera-motion aligned) | **79 %** | 80–86 % |

- Without camera-motion alignment, staleness hurts a fast-moving camera far more. **With alignment the difference disappears**, and one decay curve predicts the held-out data better than per-context curves (error 0.046 against 0.054). The curve also transfers: 85 % / 58 % kept at 100 / 267 ms on training, 82 % / 52 % held out. So the controller needs no context-dependent model. (Only 8 of VisDrone-VID's 56 training sequences are downloaded so far.)
- **Novelty re-check** (`docs/novelty_check_phase0.md`):
  - **AccuMO (MobiCom 2023)** already predicts content-dependent accuracy drop of stale results and schedules offloading with it (AR, one edge server, phones), so "staleness-driven offloading" alone is not our claim.
  - **No paper found combines heat or throttling with offloading for detection.**
  - The paper's headline therefore becomes pricing a fresh detection in **accuracy, energy and heat together** on a three-tier drone system; G9 and G11 show that doing so changes the decision and raises accuracy.
  - All 29 citations from the literature reports were verified against CrossRef/doi.org (`paper/references_verified.bib`).

### G12. Main campaign: v5, decay ablation and literature baselines (11–12 Oct 2026)

**Setup.** 12 policies × 4 scenarios × 5 repetitions = 240 runs, shuffled, on the shared Wi-Fi, 11–12 October, live power on both boards and the live forecaster in every run. Two runs were invalid (one overlapped a large GitHub upload, one was hit by the laptop going to sleep); both were set aside and re-run. Every alternative differs from v5 in one thing only (ablations) or is a literature decision rule under the same harness (baselines, "-style" = the paper's rule with a simple proxy for its learned estimator). Code `validation/hardware/tools/campaign_main.sh`; data `vid_campaign_main/`, `vid_campaign_main_measured_summary.json`, `vid_campaign_main_summary_v2_live.*`.

| Policy (20 runs each) | sAP | Fresh-detection share | Pi W | Jetson W | Time ≥ 80 °C | sAP per W: camera / board | Mission perception, 249 g |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **v5** (reference) | **0.0519** | 87.2 % | 3.12 | 4.80 | 6 % | 0.0168 / 0.0066 | **1.47** |
| v4.2 (no heat price) | 0.0501 | 84.2 % | 3.13 | 4.77 | 6 % | 0.0162 / 0.0063 | 1.42 |
| v5, generic linear decay | 0.0523 | 91.3 % | 3.09 | 4.75 | 5 % | 0.0171 / 0.0067 | 1.49 |
| v5, generic exponential decay | 0.0517 | 85.5 % | 3.12 | 4.75 | 6 % | 0.0168 / 0.0066 | 1.47 |
| v5, decay without forecasting | 0.0459 | 81.2 % | 3.20 | 4.56 | 11 % | 0.0148 / 0.0060 | 1.30 |
| v5, no staleness (flat) | 0.0465 | 62.0 % | 3.53 | 4.79 | 22 % | 0.0139 / 0.0057 | 1.31 |
| LEAF-style fixed energy weight | 0.0515 | 87.8 % | 3.10 | 4.94 | 7 % | 0.0171 / 0.0064 | 1.46 |
| Fixed laptop YOLOv8m | 0.0443 | 50.2 % | **2.39** | 0 (none) | 0 % | 0.0182 / **0.0182** | 1.28 |
| Freshness threshold (150 ms) | 0.0407 | 69.1 % | 2.57 | 4.68 | 0 % | 0.0159 / 0.0056 | 1.17 |
| Shortest queue | 0.0373 | 99.8 % | 4.80 | 4.74 | 69 % | 0.0078 / 0.0039 | 1.01 |
| OffloaD-style confidence trigger | 0.0305 | 98.7 % | 4.71 | 4.79 | 60 % | 0.0065 / 0.0032 | 0.83 |
| Qiu-style offloading reward | 0.0241 | 98.7 % | 4.66 | 4.42 | 72 % | 0.0052 / 0.0027 | 0.66 |

| Paired against v5 (20 pairs) | sAP | Fresh-detection share | Pi W | Time ≥ 80 °C |
| --- | --- | --- | --- | --- |
| v4.2 (heat price removed) | −0.0018 ± 0.0022 (v5 ahead 11/20) | −3.0 ± 2.8 points | +0.01 ± 0.06 | −0.4 ± 2.1 points |
| generic linear decay | +0.0005 ± 0.0014 (12/20) | +4.1 ± 3.7 points | −0.03 ± 0.04 | −0.7 ± 1.4 points |
| generic exponential decay | −0.0002 ± 0.0025 (8/20) | −1.7 ± 2.9 points | −0.00 ± 0.04 | −0.2 ± 1.8 points |
| decay without forecasting | **−0.0059 ± 0.0039 (v5 ahead 14/20)** | −6.0 ± 6.4 points | +0.08 ± 0.09 | +4.5 ± 2.6 points |
| no staleness (flat) | **−0.0054 ± 0.0032 (v5 ahead 16/20)** | **−25 ± 8 points** | **+0.41 ± 0.15** | **+16 ± 6 points** |
| LEAF-style fixed weight | −0.0004 ± 0.0015 (9/20) | +0.6 ± 2.9 points | −0.02 ± 0.16 | +0.5 ± 5.7 points |
| Fixed laptop | **−0.0076 ± 0.0053 (v5 ahead 16/20)** | −37 ± 11 points | −0.74 ± 0.13 | −6 ± 4 points |
| Freshness threshold | **−0.0112 ± 0.0030 (20/20)** | −18 ± 6 points | −0.55 ± 0.10 | −6 ± 4 points |
| Shortest queue | **−0.0146 ± 0.0024 (20/20)** | +13 ± 4 points | +1.68 ± 0.14 | +63 ± 12 points |
| OffloaD-style trigger | **−0.0214 ± 0.0025 (20/20)** | +12 ± 4 points | +1.59 ± 0.13 | +54 ± 10 points |
| Qiu-style reward | **−0.0278 ± 0.0033 (20/20)** | +12 ± 4 points | +1.54 ± 0.15 | +66 ± 9 points |

- **v5 beats every literature baseline, significantly.**Against the OffloaD-style confidence trigger, the Qiu-style offloading reward, shortest-queue and freshness-threshold scheduling it is ahead in 20 of 20 pairs (+0.011 to +0.028 sAP, +29 % to +111 % median), and against fixed JPEG offloading in 16 of 20 (+0.0076 ± 0.0053). The three baselines that keep the onboard detector busy hold a fresh detection more often (99 %) but run the Pi at 4.7–4.8 W and spend 60–72 % of the time at or above 80 °C; v5 runs at 3.1 W and 6 %.
- **Staleness awareness matters, and the curve must match the forecaster.**Removing staleness from the value (flat) costs −0.0054 sAP (v5 ahead 16/20), 25 points of freshness and +0.41 W, because the controller then values slow onboard results as much as fresh ones. Using the steep decay measured *without* forecasting costs −0.0059 (14/20): the controller over-values speed. But two generic curves (linear to zero at 600 ms, exponential with a 300 ms half-life) do as well as the measured curve. They keep 83 % / 79 % at 100 ms and 56 % / 54 % at 267 ms, close to the measured forecaster-v2 curve (85 % / 60 %), so on this data a well-chosen generic decay is as good. **The claim we can make is that the value curve must match the forecaster in use; the measured curve is how we found the right one, not something a generic curve cannot match.**
- **The heat price makes no measurable difference in 3-minute runs.**v5 against v4.2 (identical except for the heat price): +0.0018 ± 0.0022 sAP (not significant), the same power and the same 6 % time hot. The energy price already keeps the Pi cool here (mean 68.7 °C), so the heat price rarely rises (mean λ_T 0.20). Heat builds up over minutes, so the 24-minute runs are the real test of v5.
- **A fixed energy weight does as well as the adaptive price in these runs.**The LEAF-style weight was set to 2.0, the median price v4's dual ascent itself settled at in the 100-run campaign, so it is the best fixed weight we know rather than an independent guess. It matches v5 (−0.0004 ± 0.0015). The adaptive price's advantage is that it needs no tuning and follows a changing budget or temperature; showing that needs a budget or ambient condition different from the one the weight was tuned for.
- **Fixed laptop offloading is still the most energy-efficient for the whole swarm.**0.0182 sAP per watt with no edge drone against 0.0066 for v5 (board view), but it is the least accurate of the good policies and holds a fresh detection only half the time (50 % against 87 %).

### G13. 24-minute missions and the same-day comparison table (12–13 Oct 2026)

**Why.** The 3-minute runs cannot show heat building up: the Pi's thermal time constant is about 2.5 minutes. These runs hold each of the six mission phases for 4 minutes (24 minutes per run), long enough for the board to reach its steady temperature in every phase. A second, same-day campaign compares the best candidates directly.

**Setup (missions).** `vid_campaign_long/`: v4.1, v4.2, v5, v5.1, v3 + forecasting v2 and fixed laptop YOLOv8m, scenario mission (good, ground congested, ground blackout, both degraded, total blackout, final phase; the final phase kept 2 / 1.5 Mbit/s limits, see G14), 2 repetitions each, 12 runs, live power on both boards, 12 October 19:03 – 00:10. Controllers include the anti-windup rule. A first launch failed (the laptop worker gave up during the 4-minute blackout) and was discarded; the three faults it exposed were fixed and verified before this launch (Part 21).

| Policy (2 runs each) | sAP | Pi W | Time ≥ 80 °C | Time ≥ 80 °C, first / last 6 min | Mean temp, first / last 6 min | Fresh-detection share |
| --- | --- | --- | --- | --- | --- | --- |
| **v4.1** | **0.0433** | 3.27 | 23 % | 0 % / 56 % | 69.8 / 80.8 °C | 96.8 % |
| v4.2 | 0.0373 | 3.06 | 16 % | 0 % / 33 % | 69.2 / 76.5 °C | 89.1 % |
| v5 | 0.0317 | 3.16 | 23 % | 0 % / 60 % | 68.2 / 80.9 °C | 85.4 % |
| v5.1 | 0.0317 | 3.29 | 17 % | 0 % / 34 % | 70.9 / 78.5 °C | 92.5 % |
| v3 + forecasting v2 | 0.0264 | 4.31 | **92 %** | 69 % / 100 % | 80.8 / 84.6 °C | 97.4 % |
| Fixed laptop YOLOv8m | 0.0191 | 2.26 | 0 % | 0 % / 0 % | 67.1 / 61.2 °C | 18.2 % |

- **Heat builds up over a mission.** Without an energy price, v3 + forecasting v2 sends 25–51 % of its frames to onboard inference, runs the Pi at 4.3 W and sits at the 85 °C throttling limit from about minute 4 to the end (92 % of the mission). The energy-priced controllers stay mostly below 80 °C until the total blackout, when onboard inference is the only source. **v4.1 is 1.6× more accurate than v3 + forecasting v2 over the mission**, against +0.006–0.007 sAP (about +12 %) in 3-minute runs: the energy–heat–accuracy coupling grows with mission length.
- **v4.1 is the most accurate policy over a mission.** The difference shows in the ground blackout, when the Jetson is the only remote server: v4.1 sends it 97 % of frames at full quality (accuracy-weighted 3.59 on-time results/s, 98 % fresh). The edge price makes v4.2 and v5 choose cheaper settings there (3.36 at 85 % fresh; 2.54 at 72 %); v5.1, with every price stacked, falls back to onboard YOLOv8n for 18 % of frames (1.24). Part 16 explains why.
- **The heat price did not help.** v5 and v5.1 rose to λ_T 0.7–1.1 on average and were the least accurate of the priced controllers: heat follows the same camera joules μ already prices, and the prediction stays high for minutes after a blackout.
- **Limit.** Two runs per policy: the paired differences are not statistically significant on their own. Five repetitions (about 5 hours) are needed to confirm the mission ranking.

**Setup (same-day table).** `vid_campaign_table/`: v4.1, v5, v5.1 and onboard-only YOLOv8n-320, 4 scenarios × 5 repetitions = 80 runs (20-s phases), shuffled, 13 October 00:10 – 03:45, no outages. Same anti-windup controllers.

| Policy (20 runs each) | sAP | Fresh-detection share | Pi W | Jetson W | Time ≥ 80 °C | sAP per W (board view) | Mission perception, 249 g |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **v4.1** | **0.0596** | **98.1 %** | 3.28 | 4.95 | 14 % | 0.0073 | **1.69** |
| v5 | 0.0593 | 87.1 % | 3.19 | 4.82 | 11 % | 0.0074 | 1.68 |
| v5.1 | 0.0590 | 97.9 % | 3.26 | 4.88 | 11 % | 0.0073 | 1.67 |
| Onboard YOLOv8n only | 0.0169 | 98.7 % | 4.49 | 0 (none) | 89 % | 0.0038 | 0.46 |

| Paired against v4.1 (20 pairs) | sAP | Pi W |
| --- | --- | --- |
| v5 | −0.0003 ± 0.0017 (10/20) | −0.10 ± 0.08 |
| v5.1 | −0.0006 ± 0.0012 (10/20) | −0.03 ± 0.07 |
| Onboard only | **−0.0428 ± 0.0079 (0/20)** | +1.20 ± 0.13 |

- **In short runs the three priced controllers tie.** v4.1, v5 and v5.1 reach the same accuracy (differences under 0.001 sAP, intervals across zero). v4.1 and v5.1 keep 98 % freshness, v5 87 % (it has no freshness price).
- **Onboard-only is 3.5× worse** and spends 89 % of the time at or above 80 °C: on this board the Pi alone cannot keep up with aerial video.
- **Conclusion of both campaigns.** v4.1 is the best controller: tied in short runs, best over a mission, and the simplest. Separate heat and edge-energy prices are unnecessary on this hardware.

### G14. Corrections made on 13 October 2026

The long runs and a closer look at the network emulation found four problems that change how some earlier results must be described. No run had to be repeated and no measured number changes: within every campaign all policies ran under identical conditions, so every paired comparison and ranking stands.

- **1. Scenario conditions as actually applied.** Each phase was applied with `tc qdisc change ... netem <phase>`. Tested on the Pi: netem then resets packet loss but **keeps the previous phase's bandwidth limit** when the new phase sets none (`replace` behaves the same). So in every campaign up to 13 October: in mission, the final "recovered" phase kept the laptop at 2 Mbit/s and the Jetson at 1.5 Mbit/s; in mission_mirror it kept 1.5 / 2 Mbit/s; in random, an "unimpaired" state kept the last limit; static_good was never limited. Every per-phase result labelled "recovered" or "after a blackout" in this report means "still rate-limited". The same applies to the v1 mission (Part 9) and the v2 scenarios (Part 10).
- **2. Retracted: "after a blackout the real link stays slow (389 ms)".** It was the leftover limit, not real link behaviour (corrected in Parts 1, 11, 13 and 17).
- **3. The simulator matches the hardware in every phase.** Rebuilt with the conditions actually applied (`sim_vs_real.py --stop-and-wait --netem-persist`): correlation 0.947, average error 1.57 results/s over all 528 phases. The earlier figure (0.91) had to exclude the 41 "post-blackout" phases; there is no exception now.
- **4. Controller versions.** The anti-windup rule (μ frozen while onboard is forced, μ and μ_e capped at 5, λ_F at 2) was added on 12 October. The 7 and 11–12 October campaigns (G9, G11, G12) ran v4 / v4.1 / v4.2 / v5 without it; in 20-s phases the price stayed small (about 6 at most) and those results are valid for those versions. G13 used the versions with anti-windup. The main-campaign results of G12 for v5 and the G13 table are therefore for slightly different versions, which is why G13 repeats v5 on the same day.
- **5. Jetson Wi-Fi power saving.** It had been switched off on 11 October but was found on again on 12 October (the network manager re-enables it on reconnect; when is unknown). It affected all policies of a campaign alike; it is another reason the report compares policies only within a campaign. Every run now switches it off on both boards.
- **Fixed for all future campaigns.** `adaptive.tc_phase` now deletes and re-adds each path's impairment every phase (verified on the Pi: the final mission phase returns to 12.5 results/s, as fast as the first). Each run records `"netem": "per-phase-reset"`; `--netem-legacy` reproduces the old behaviour exactly for re-running an earlier campaign. The replay tool has the same switch (`--netem reset|legacy`).

## PART 16The controllers' objective functions, explained

Every adaptive controller after v1 makes the same kind of decision, and they differ only in the function they maximise. This part writes that function down exactly as the code computes it (checked line by line against `adaptive.py` and `adaptive2.py` on 12 October, units included; reference copy `docs/controller_formulas.md`), explains why each term is there and why it has that form, and shows with the measurements why each version replaced the previous one. **Bottom line: v4.1 is the best controller we have**: it prices exactly the two things that change accuracy on this system, the camera drone's energy (because on a fanless Pi energy is heat, and heat is throttling) and freshness. The later additions (an edge-drone energy price, a heat price) add nothing measurable in short runs and cost accuracy over a 24-minute mission.

### 16.1 The decision every controller makes

- **What is decided.** Every camera frame (30 per second) can go to at most one idle server: the Pi itself (YOLOv8n-320, YOLOv8s-320, YOLOv8s-640), the Jetson path (JPEG of the frame at 640 / 480 / 320 px, quality 90 or 50, YOLOv8s on the Jetson) or the laptop path (the same, plus YOLOv8m-640 at q90 or q50). Each server holds at most one frame at a time.
- **How.** Each idle server proposes its best setting v\*(s) = argmax over v of value(s, v); the frame goes to the idle server with the highest value, if that value is above 0. Otherwise the frame is skipped.
- **Why a greedy per-frame choice, and not planning or learning.** A decision has to be made 30 times a second on the Pi's CPU, from quantities the drone measures itself (link speed, server times, power, temperature). A greedy choice of the highest-value server takes well under a millisecond and needs no training data. Planning ahead over a horizon (model-predictive control, as in AccuMO) needs a predictive model of every future frame; reinforcement learning (as in Chanakya) needs training episodes and does not transfer to a new link or board without retraining. Long-run goals that a single frame cannot see (an average power budget, a freshness target) are handled by **prices** that move slowly, once per second (16.3, v4 onward). Choosing the best frame under the current prices and moving the prices towards their targets is the standard online primal-dual method for maximising an average reward under average constraints.

### 16.2 The building blocks

| Symbol | Meaning | Unit |
| --- | --- | --- |
| A_v / A_ref | measured accuracy of setting v divided by YOLOv8s-640's (same table: COCO for v1–v2, VisDrone-DET for the aerial runs) | – |
| D | deadline, 300 ms (age at which a detection still counts as fresh) | ms |
| b | JPEG size of the setting (running average of real frames) | bytes |
| r, σ | estimated goodput of the path and its spread (running estimate of every frame and probe) | Mbit/s |
| t_enc, t_rem, rtt | JPEG encoding on the Pi, server inference, round trip | ms |
| t_tx = 8b / (1000 r) | transfer time | ms |
| L = t_enc + t_tx + t_rem + rtt | latency of the result (onboard: the measured inference time) | ms |
| T_busy | time the server stays busy: max(t_tx + rtt, one frame) for a path, the onboard time rounded up to whole frames | ms |
| n_active | number of servers whose best setting has p_on > 0.2 | – |
| ρ(age) | measured share of fresh accuracy a detection keeps at that age (decay curve) | – |
| E_cam, E_edge | measured energy per frame on the Pi / on the Jetson | J |

**Probability of arriving in time.** For a time budget X the code computes

```
P(X) = Φ( ( r − 8b / (1000 · (X − t_enc − t_rem − rtt)) ) / σ )        (0 if X − t_enc − t_rem − rtt ≤ 0)
p_on = P(300 ms),   p_late = P(1000 ms)
```

- The term 8b / (1000 · ms) is the link rate this frame **needs** (Mbit/s); Φ, the normal distribution function, turns "needed rate minus expected rate, in units of its spread" into a probability. So the argument is dimensionless.
- **Why a probability and not the expected latency.** Wi-Fi goodput swings by a factor of 10 within seconds (measured: 5–83 Mbit/s on the laptop link). A rule that uses only the mean sends the 87 KB YOLOv8m frame whenever the average says it fits, and half of those frames then miss the deadline. With the probability, a large frame is chosen only when it fits with a margin; otherwise a smaller JPEG or the Jetson wins. This is the uncertainty-aware rule of the simulation paper (Part 3).

### 16.3 Each controller, its function, and why it replaced the previous one

**v1 — one option at a time** (Part 9)

```
U(a) = f(a) · q(a) · A_a / A_ref  −  λ(SoC) · E(a) · f(a)
q = p_on + 0.25 · max(0, p_late − p_on)
```

- f(a): results per second option a can deliver (1/s). E(a): Pi energy per frame (J), so E·f is a power (W). λ = 0.01 · (1 + (0.15/SoC)²) is a price per joule (1/J) that rises as the battery runs down. Both terms are "value per second".
- **Why this form.** It maximises accuracy-weighted on-time results per second minus the cost of the power used. A late result (within 1.5 s) is worth a quarter of an on-time one, so the controller degrades gracefully when nothing can meet the deadline.
- **Its limit.** Only one option at a time: all frames to one server. It reached 96 % of the hindsight optimum and +8 % over the best fixed strategy, but it could not use the Pi, the Jetson and the laptop together.

**v2 — all servers in parallel, rate objective** (Part 10)

```
value(s, v) = (A_v / A_ref) · q(s, v) / T_busy(s, v)          [results per second]
```

- **Why this form.** Dividing by the time the server stays busy turns "how good is this result" into "how much accuracy per second this server adds", which is what matters when three servers work in parallel: a slow but good result blocks its server for longer.
- **What it improved.** Using all servers at once: 59–62 % more accuracy-weighted on-time results than the best fixed strategy on impaired links, best in all 8 paired comparisons, and the best policy on real streaming accuracy in the 108-run campaign (Part 12).
- **Its limit.** It counts results, not what the drone actually sees. Streaming AP scores, at every frame, the detection the drone is *holding*, and a held detection loses accuracy as it ages (on aerial video, 58 % within 100 ms without correction). v2 values a 250 ms-old result the same as a 40 ms-old one.

**v3 — streaming objective** (Part 12)

```
value(path s, v)  = (A_v / A_ref) · H(L, T) · p_late
value(onboard, v) = (A_v / A_ref) · H(t_onboard, T)
H(L, T) = mean of ρ(L + f·T) for f = 0, ¼, ½, ¾, 1          T = T_busy / n_active
```

- **Why this form.** It is the expected streaming accuracy the result will provide: a result arrives L ms after its frame was captured and is then held until the next result replaces it, about T = T_busy / n_active later (with n servers delivering in turn, a new result comes roughly every T_busy / n). Its accuracy while held is ρ(age) times its fresh accuracy; H averages that over the holding time at five points. p_late multiplies in the chance that it arrives at all. The value is dimensionless (accuracy per decision), so no division by time is needed: the time dimension is already inside H.
- **Why it first failed.** Plain v3 used the decay curve measured *without* forecasting (41 % kept at 100 ms, 7 % at 267 ms). With that steep curve, every few milliseconds look precious, so v3 over-valued fast, low-accuracy results. It trailed v2 by a median 14 % (10 of 12 pairs).
- **The fix: the curve must match the forecaster in use.** The drone runs a forecaster that moves stale boxes forward; with forecaster v2 a detection keeps 85 % at 100 ms and 60 % at 267 ms. v3 rebuilt on *that* curve ("v3 + forecasting v2") beat v2 by +0.0045 ± 0.0035 sAP (median +8.9 %, 20 pairs) with 99.5–99.8 % freshness.
- **What the ablation showed (G12).** Removing staleness altogether (ρ = 1) costs −0.0054 ± 0.0032 sAP (16 of 20) and 25 points of freshness; using the no-forecasting curve costs −0.0059 ± 0.0039 (14 of 20). Two generic curves that happen to lie close to forecaster v2's (linear to zero at 600 ms; exponential, half-life 300 ms) do as well as the measured one. So the claim is: **the decay used for decisions must match the forecaster**; the measurement is how we know which curve that is.

**v4 — camera-drone energy price** (G9)

```
value = value_v3 − μ · E_cam(s, v)
E_cam(onboard) = 0.324 / 0.741 / 2.229 J (YOLOv8n-320 / s-320 / s-640, measured)
E_cam(path)    = J_encode + (0.211 + 0.016 · r) W × 8b / (10⁶ · r) s        (about 0.03 J for a 640 px JPEG)
μ ← clip( μ + 0.1 · (P̄_measured − 2.8 W), 0, 5 )   once per second
```

- **Why a price.** The goal is "most accuracy subject to average Pi power ≤ budget". In that constrained problem μ is the Lagrange multiplier: the accuracy one joule is worth at the moment. It is in 1/J, so μ × J is in the same units as the value. It rises while measured power is above the budget and falls when below, so the controller finds the right exchange rate itself, under any link condition, with no hand tuning.
- **Why not a fixed weight (as in LEAF+AIO).** A fixed weight is right for only one operating condition. In G12 a fixed weight did as well as v5, but only because we set it to 2.0, the value v4's own price settles at; nobody could have chosen it without running v4 first.
- **Three safety rules.** Thermal guard: μ is at least 1 while the Pi measures ≥ 78 °C. Blackout exemption: when no link can deliver (no path with p_on > 0.2), onboard inference is not priced, because it is then the only source of perception. Anti-windup (added 12 October): μ is frozen while the exemption is active and capped at 5; without this, μ grew to 41 in a 90-s blackout and priced out every offload after the links returned (Part 21).
- **What it improved, and why.** Onboard inference costs 10–80× more energy per frame than a JPEG offload. The price makes it rare except when it is needed. The Pi then runs about 1–1.25 W cooler, spends 13–17 % of the time at or above 80 °C instead of 67–76 %, and is **more accurate**: +0.0074 ± 0.0028 sAP over v3 + forecasting v2 on 7 October (17 of 20) and +0.0056 ± 0.0034 on 11 October (18 of 20). Throttling slows everything on the Pi (encoding, the camera loop, the forecaster), so less heat means fresher and better results for every server.
- **Its cost.** Onboard results had been filling short gaps; without them freshness fell from 99 % to about 87 %.

**v4.1 — freshness price**

```
value = value_v4 + λ_F · p_on · 1[ AoI + L ≥ 300 ms ]
λ_F ← clip( λ_F + 2 · (0.95 − F̂_5s), 0, 2 )   once per second
AoI = age of the newest result received; F̂_5s = share of the last 5 s with AoI ≤ 300 ms
```

- **Why this form.** It adds a second constraint, "fresh detection at least 95 % of the time", with its own price. The bonus is paid only to a result that would arrive before the held detection goes stale (the indicator), and only in proportion to the chance it arrives in time (p_on). So the controller buys freshness only where it can actually be bought, usually with a cheap small JPEG or a YOLOv8n result at the moment of a gap, and not by running onboard all the time.
- **What it improved.** Freshness 87.5 % → 97.9 % (+10.4 ± 3.3 points, 19 of 20 pairs) at the same power (+0.08 W, not significant) and the same accuracy (+0.0025, not significant) as v4 (G11). It removes v4's one cost.

**v4.2 — edge-drone energy price** (G11)

```
value(jetson, v) −= μ_e · E_edge(v)
E_edge = 0.040–0.371 J per Jetson inference (measured) + 0.211 W × 8b / (10⁶ · r) s
μ_e ← clip( μ_e + 0.1 · (P_Jetson,live − 4.079 W − 0.5 W), 0, 5 )   once per second
```

- **Why.** v4 prices only the camera drone; the Jetson's work was free to it. μ_e prices the Jetson's measured extra power against its own budget.
- **What it did.** Jetson power −0.19 ± 0.10 W (lower in 19 of 20), accuracy unchanged in short runs. Over a 24-minute mission it lost accuracy (0.0373 against v4.1's 0.0433, 2 runs each): the 0.5 W budget is below what the Jetson needs when it is the main server (about 0.9 W extra), so μ_e stays high (mean 2.7) and pushes the controller to cheaper, lower-resolution Jetson settings exactly in the 4-minute ground blackout, when the Jetson is the only remote server (freshness there 85 % against 98 %).
- **Why it is not worth it.** It saves 0.1–0.2 W on a drone that needs 154 W to fly. The edge drone's energy is decided by whether it flies, not by how its GPU is used (G10).

**v5 — predictive heat price** (G12)

```
value = value_v3 − (μ + λ_T) · E_cam − μ_e · E_edge
T_steady = 34.43 °C + 12.73 °C/W × P̄_10s          (measured fit)
T̂ = T_now + (T_steady − T_now) · (1 − e^(−60 s / 148.8 s))      (temperature predicted 60 s ahead)
λ_T ← clip( λ_T + 0.01 · (T̂ − 75 °C), 0, 2 )   once per second;  hard guard raised to 84 °C
```

- **Why.** To act before throttling, from where the temperature is heading, rather than reacting at 78 °C.
- **What it did.** No measurable effect in 3-minute runs (v5 against v4.2: +0.0018 ± 0.0022) and no gain over v4.1 on the same day (−0.0003 ± 0.0017); over a 24-minute mission it was behind (0.0317 against 0.0433).
- **Why it does not help.** The Pi's heat comes from the same joules that μ already prices: the steady temperature is a straight line in power (12.7 °C per watt). A separate heat price therefore **counts the same cost twice**. It also lags: after the onboard-only blackout the predicted temperature stays high for minutes (time constant 149 s), so λ_T stays near its cap and the controller stays over-cautious after the links return.

**v5.1 — every price at once**

```
value = value_v3 − (μ + λ_T) · E_cam − μ_e · E_edge + λ_F · p_on · 1[AoI + L ≥ 300 ms]
```

- Freshness recovers (97.9 %, like v4.1), but over a mission the stacked prices (camera about 5.7, edge about 2.5) make remote frames expensive. In the ground blackout the freshness bonus then pushes it onto onboard YOLOv8n (18 % of frames) instead of the Jetson, and that phase's accuracy-weighted rate falls to 1.24 against v4.1's 3.59.

**Rate objective with prices** (implemented for completeness, never used in a campaign): every price term is divided by T_busy, so price × energy per frame becomes price × power and keeps the units of value per second.

### 16.4 All controllers side by side

| Controller | Value term | μ camera energy | λ_F freshness | μ_e edge energy | λ_T heat | Main result |
| --- | --- | --- | --- | --- | --- | --- |
| v1 | results/s × accuracy − λ·power | fixed λ(SoC) | – | – | – | +8 % over best fixed; one option at a time |
| v2 | accuracy × q / T_busy | – | – | – | – | parallel servers; best policy in the 108-run campaign |
| v3 | accuracy × H × p_late (no-forecast curve) | – | – | – | – | trailed v2 by 14 % (curve too steep) |
| v3 + forecasting v2 | as v3, forecaster-v2 curve | – | – | – | – | beat v2 +0.0045 sAP; 99.5 % fresh; but throttled (67–92 % ≥ 80 °C) |
| v4 | v3 + fc2 | ✓ | – | – | – | +0.006–0.007 sAP over v3 + fc2, −1.1 W; freshness 87 % |
| **v4.1** | v3 + fc2 | ✓ | ✓ | – | – | **best: v4 accuracy and power with 98 % freshness; best over 24 min** |
| v4.2 | v3 + fc2 | ✓ | – | ✓ | – | Jetson −0.19 W; no accuracy gain; behind over 24 min |
| v5 | v3 + fc2 | ✓ | – | ✓ | ✓ | tie in short runs; behind over 24 min |
| v5.1 | v3 + fc2 | ✓ | ✓ | ✓ | ✓ | tie in short runs; behind over 24 min |

### 16.5 The evidence, head to head

| Comparison | Campaign | sAP difference | Other effects |
| --- | --- | --- | --- |
| v3 + fc2 − v2 | Wi-Fi fc2, 20 pairs | +0.0045 ± 0.0035 | 99.5–99.8 % fresh |
| v4 − v3 + fc2 | energy, 7 Oct, 20 pairs | +0.0074 ± 0.0028 (17/20) | Pi −1.14 W; ≥ 80 °C 76 % → 17 % |
| v4 − v3 + fc2 | v4.2 campaign, 11 Oct, 20 pairs | +0.0056 ± 0.0034 (18/20) | Pi −1.25 W; ≥ 80 °C 67 % → 13 % |
| v4.1 − v4 | 11 Oct, 20 pairs | +0.0025 ± 0.0038 (n.s.) | freshness +10.4 ± 3.3 points (19/20) |
| v4.2 − v4 | 11 Oct, 20 pairs | +0.0009 ± 0.0040 (n.s.) | Jetson −0.19 ± 0.10 W (19/20) |
| v5 − v4.2 | main, 12 Oct, 20 pairs | +0.0018 ± 0.0022 (n.s.) | same heat |
| v5 − v4.1 | table, 13 Oct, 20 pairs | −0.0003 ± 0.0017 (n.s.) | freshness 87 % against 98 % |
| v5.1 − v4.1 | table, 13 Oct, 20 pairs | −0.0006 ± 0.0012 (n.s.) | same freshness and power |
| onboard only − v4.1 | table, 13 Oct, 20 pairs | −0.0428 ± 0.0079 (0/20) | +1.2 W; 89 % of the time ≥ 80 °C |
| 24-minute mission | long, 2 runs each | v4.1 0.0433 · v4.2 0.0373 · v5 0.0317 · v5.1 0.0317 · v3 + fc2 0.0264 · fixed laptop 0.0191 | v3 + fc2 at ≥ 80 °C 92 % of the mission; v4.1 23 % |

Literature baselines (G12, same harness, against v5, which ties with v4.1 on the same day): ahead of the Qiu-style offloading reward, the OffloaD-style failure trigger, shortest-queue and freshness-threshold scheduling in 20 of 20 pairs each (+29 % to +111 % median), and of fixed JPEG offloading in 16 of 20. A LEAF-style fixed energy weight tied, but only with the weight taken from our own price. Caveat: these are our re-implementations of each paper's decision rule with simple estimators, not the original systems.

### 16.6 The best strategy: v4.1 in full

```
Every camera frame, for each idle server s and setting v:
  value(s, v) = (A_v / A_ref) · H(L, T) · p_late                       accuracy that survives staleness, if it arrives
              − μ · E_cam(s, v)                                         camera-drone energy (and so heat)
              + λ_F · p_on · 1[AoI + L ≥ 300 ms]                        freshness rescue
  send the frame to the idle server with the highest value > 0
Every second:
  μ   ← clip(μ + 0.1 (P̄ − 2.8 W), 0, 5)    frozen while onboard is forced; ≥ 1 at ≥ 78 °C
  λ_F ← clip(λ_F + 2 (0.95 − F̂), 0, 2)
ρ = measured decay of forecaster v2 (running live on the Pi); onboard unpriced when no link can deliver
```

- **Configuration.** `adaptive2.py --objective stream --decay staleness_decay_forecast_v2.json --live-forecast forecast_tuning_v2.json --energy-aware --power-budget 2.8 --fresh-target 0.95` (anti-windup defaults --mu-max 5, --lam-f-max 2).
- **What it does in a mission (24-minute runs).** Good link: 76 % of frames to the laptop (YOLOv8m), 24 % to the Jetson, no onboard work. Ground link congested: the Jetson takes 75 %. Ground blackout: the Jetson takes 97 %, freshness stays at 98 %. Both links degraded: small JPEGs on both. Total blackout: onboard YOLOv8n (exempt from the price), freshness 93 %. Afterwards it returns to both links. Mean energy price 4.3: high enough that onboard work appears only when it rescues freshness or is the only option.
- **Why it is the best.** (1) It keeps the camera drone out of thermal throttling, which is what limits accuracy on a fanless board: over a mission the controller without an energy price spends 92 % of the time at the 85 °C limit and is 1.6× less accurate. (2) It keeps a fresh detection 97–98 % of the time, as v3 did, without v3's heat. (3) It leaves the remote servers unpriced, so in a ground blackout it uses the Jetson at full quality; the controllers that price the Jetson or add a heat price lose accuracy exactly there.
- **How it compares.** Short runs: tied with v5 and v5.1 on accuracy (all three priced controllers reach about 0.059 sAP on the same day), better freshness than v5, 3.5× the accuracy of onboard-only, ahead of every literature-style baseline. Over a 24-minute mission: the most accurate of all six policies.
- **What it does not do.** It does not price the edge drone's energy; doing so saves 0.1–0.2 W of Jetson power, negligible against 154 W of flight, and costs accuracy. The 24-minute ranking rests on 2 runs per policy and needs the 5-repetition campaign to be statistically confirmed. All tests are on lab Wi-Fi with emulated impairments and one camera drone.

### 16.7 Why not something else

| Alternative | Why we did not choose it |
| --- | --- |
| Maximise results per second (v2) | ignores how old the held detection is; streaming accuracy depends on age |
| Minimise latency (shortest queue) | ignores accuracy and heat: keeps the Pi busy, 69 % of the time ≥ 80 °C, −0.015 sAP |
| Offload when onboard looks unsure (OffloaD-style) or by estimated gain (Qiu-style) | both keep onboard inference running on every frame: 60–72 % of the time ≥ 80 °C, −0.021 to −0.028 sAP |
| Offload when the detection gets old (AoI threshold) | freshness alone, no accuracy or energy trade: −0.011 sAP |
| A fixed energy weight (LEAF-style) | equal only when set to the value our price finds by itself; wrong under other links or budgets |
| A learned, content-dependent decay (as AccuMO) | with camera-motion alignment the decay no longer depends on camera speed, crowding or detector (Part 15, decay by context); one measured curve suffices |
| Reinforcement learning (as Chanakya) | needs training on the deployment; our controller needs only measured constants |
| A separate heat price (v5) | heat follows camera power linearly, so it double-counts μ, and it lags after blackouts |
| Pricing the edge drone (v4.2) | saves 0.1–0.2 W against 154 W of flight and costs accuracy when the Jetson is the only server |

## PART 17VisDrone-trained detectors on the Pi: streaming accuracy and thermal throttling (20–21 Oct 2026)

Question from the professor: what streaming AP do YOLOv8s, YOLOv8m and YOLOv8l reach when they run ONBOARD the camera drone (Raspberry Pi 5) on the VisDrone video test clips, and how does thermal throttling change it, in short and in long runs? Until now every detector was the COCO-trained model, which has never seen aerial imagery; all results in this Part use detectors fine-tuned on VisDrone. Validated

### 17.1 Fine-tuning on VisDrone

- **Data** (`scripts/prepare_visdrone_finetune.py`): VisDrone2019-DET train (6,471 aerial images) plus the VisDrone2019-VID *train* clips (every 5th frame, resized to 640 px wide exactly like the camera stream). VisDrone classes mapped to the COCO ids the whole project uses (pedestrian, people → person; car, van → car; truck; bus; motor → motorcycle; bicycle), 8 output classes, ignored regions and tricycles dropped. Model selection on VisDrone2019-DET val. The 7 VID *val* clips, the test stream of every live run, were never used for training or selection.
- **Training** (`scripts/train_visdrone.py`, laptop RTX 4050 6 GB): from the COCO weights, 640 px, seed 0; YOLOv8s 80 epochs (batch 8, 2.8 h), YOLOv8m 60 epochs (batch 4, 4.1 h), YOLOv8l 50 epochs (batch 4, 5.1 h); best epoch by DET-val mAP. Weights: `weights/yolov8{s,m,l}_visdrone.pt`.

| Model | COCO weights: mAP50-95 on VisDrone-DET val | VisDrone weights (training) | VisDrone weights (re-measured, project pipeline) | Gain |
| --- | --- | --- | --- | --- |
| YOLOv8s | 0.107 | 0.266 | 0.2671 | ×2.5 |
| YOLOv8m | 0.146 | 0.296 | 0.2972 | ×2.0 |
| YOLOv8l | 0.164 | 0.313 | 0.3131 | ×1.9 |

The re-measurement with the project's own validation code (batch 1, `validation/hardware/variant_accuracy.py`) matches the training numbers, which also confirms that the class mapping is consistent end to end. The same code measured every setting the controller can choose (input size × JPEG quality) with the VisDrone weights, for the offloading tests of Part 18 (`experiments/results/hardware/variant_accuracy_visdrone_ft.json`; the COCO entries in it are unchanged):

| VisDrone-trained model, input | raw frame | JPEG q90 | JPEG q50 | JPEG q35 |
| --- | --- | --- | --- | --- |
| YOLOv8s 640 px | 0.2671 | 0.2563 | 0.2030 | 0.1883 |
| YOLOv8s 480 px | – | 0.2022 | 0.1570 | – |
| YOLOv8s 320 px | 0.1367 | 0.1296 | 0.0957 | – |
| YOLOv8m 640 px | 0.2972 | 0.2759 | 0.2097 | – |
| YOLOv8l 640 px | 0.3131 | – | – | – |

### 17.2 The onboard test

- **Boards:** two new Raspberry Pi 5 (8 GB, fanless, Debian 13, PyTorch 2.14 CPU): pi2 `sengar@192.168.0.129` ("pi-relayyy") and pi3 `dubey@192.168.0.247` ("pi-sender"), run in parallel, one model alone on each Pi (policy `fixed:onboard:<model>`, 3 CPU threads, conf 0.01), streaming the 7 test clips at 30 fps.
- **Runs per model and Pi:** 2 **hot-start short** runs (4 min, started straight after the previous run, board 63–74 °C), 2 **cool-start short** runs (the Pi first cooled below 55 °C on pi2 and 61 °C on pi3, its idle floor), 1 **long** run (24 min = six 4-minute windows, cool start). 10 runs per model, 30 in all (all files checked: 7,196 frames per short run, results = detections, clock log present, model as intended).
- **Logged at 1 Hz:** Pi power (PMIC), temperature, ARM clock (`vcgencmd measure_clock arm`) and the firmware throttle flag (`get_throttled`, bit 2 = throttled now).
- **Scored** (`validation/hardware/onboard_throttle_analysis.py`): sAP with the standard newest-result rule, with and without forecaster v2; sAP50; mAP (each result against its own frame, i.e. accuracy without delay). Folders `vid_campaign_onboard{,_cool,_long}_vd_{pi2,pi3}` (s, m) and `*_vd_l_{pi2,pi3}` (l); summary `onboard_sap/throttle_analysis_visdrone.json`.

### 17.3 Results

| Model, runs | mAP | sAP | sAP + forecaster | sAP50 | time per frame | Pi power | temp start → mean (max) | clock | time throttled |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| YOLOv8s, hot short (4) | 0.242 | 0.0062 | 0.0162 | 0.0183 | 728 ms | 4.43 W | 70 → 85 °C (87) | 1668 MHz | 73 % |
| YOLOv8s, cool short (4) | 0.243 | 0.0061 | 0.0172 | 0.0168 | 718 ms | 4.71 W | 60 → 84 °C (87) | 1759 MHz | 64 % |
| YOLOv8s, long (2) | 0.232 | 0.0051 | 0.0139 | 0.0147 | 752 ms | 4.29 W | 60 → 85 °C (88) | 1570 MHz | 89 % |
| YOLOv8m, hot short (4) | 0.256 | 0.0053 | 0.0082 | 0.0114 | 1615 ms | 4.80 W | 63 → 85 °C (88) | 1675 MHz | 77 % |
| YOLOv8m, cool short (4) | 0.254 | 0.0046 | 0.0080 | 0.0104 | 1635 ms | 4.75 W | 62 → 85 °C (88) | 1651 MHz | 78 % |
| YOLOv8m, long (2) | 0.245 | 0.0035 | 0.0057 | 0.0082 | 1726 ms | 4.38 W | 62 → 87 °C (89) | 1487 MHz | 95 % |
| YOLOv8l, hot short (4) | 0.274 | 0.0011 | 0.0014 | 0.0035 | 3257 ms | 4.57 W | 74 → 86 °C (89) | 1542 MHz | 94 % |
| YOLOv8l, cool short (4) | 0.268 | 0.0008 | 0.0015 | 0.0025 | 3238 ms | 4.71 W | 63 → 86 °C (89) | 1598 MHz | 84 % |
| YOLOv8l, long (2) | 0.253 | 0.0008 | 0.0011 | 0.0021 | 3474 ms | 4.42 W | 64 → 88 °C (91) | 1426 MHz | 97 % |

Long runs window by window (mean of the two 24-minute runs; mAP in each window is the accuracy of the results delivered in it):

| Model | minutes | sAP + forecaster | mAP | time per frame | temperature | clock | throttled |
| --- | --- | --- | --- | --- | --- | --- | --- |
| YOLOv8s | 0–4 | 0.0168 | 0.245 | 725 ms | 84.1 °C | 1714 MHz | 69 % |
| YOLOv8s | 4–8 | 0.0127 | 0.223 | 752 ms | 85.5 °C | 1544 MHz | 93 % |
| YOLOv8s | 12–16 | 0.0123 | 0.229 | 755 ms | 85.6 °C | 1526 MHz | 94 % |
| YOLOv8s | 20–24 | 0.0125 | 0.228 | 755 ms | 85.7 °C | 1560 MHz | 92 % |
| YOLOv8m | 0–4 | 0.0090 | 0.247 | 1650 ms | 84.9 °C | 1651 MHz | 81 % |
| YOLOv8m | 4–8 | 0.0055 | 0.239 | 1686 ms | 86.9 °C | 1503 MHz | 97 % |
| YOLOv8m | 12–16 | 0.0061 | 0.242 | 1747 ms | 87.3 °C | 1442 MHz | 99 % |
| YOLOv8m | 20–24 | 0.0052 | 0.239 | 1761 ms | 87.3 °C | 1435 MHz | 98 % |
| YOLOv8l | 0–4 | 0.0015 | 0.265 | 3225 ms | 85.3 °C | 1622 MHz | 84 % |
| YOLOv8l | 4–8 | 0.0016 | 0.244 | 3400 ms | 87.6 °C | 1438 MHz | 100 % |
| YOLOv8l | 12–16 | 0.0015 | 0.240 | 3492 ms | 88.6 °C | 1379 MHz | 100 % |
| YOLOv8l | 20–24 | 0.0015 | 0.266 | 3559 ms | 89.0 °C | 1349 MHz | 100 % |

### 17.4 What throttling costs

The firmware lowers the ARM clock from 2.4 GHz once the Pi reaches about 80 °C. Each run's sAP at the inference time the full clock would give (measured time × mean clock / 2,400 MHz) was read off the emulation curve of 17.5 (the same detections and the same scorer, only the delay changed):

| Model (all 10 runs) | time per frame: measured → at 2.4 GHz | sAP: measured → at 2.4 GHz | sAP + forecaster: measured → at 2.4 GHz |
| --- | --- | --- | --- |
| YOLOv8s | ≈ 730 → 490–525 ms | 0.005 → 0.008 | 0.018 → 0.030–0.033 |
| YOLOv8m | ≈ 1620–1730 → 1070–1120 ms | 0.005 → 0.0065 | 0.0067 → 0.012 |
| YOLOv8l | ≈ 3240–3470 → 2060–2160 ms | 0.0017 → 0.0018 | 0.0019 → 0.0044–0.0048 |

- **Throttling roughly halves streaming accuracy** (with the forecaster: s −42 %, m −43 %, l −58 %). It does **not** change mAP: the detector is as accurate as before, its results simply arrive later and are held longer.
- **Cooling the board first barely helps.** A cool start throttles within about a minute (64–84 % of the short run throttled), and its sAP is the same as a hot start within the run-to-run spread. Over 24 minutes the clock keeps sinking (s 1714 → 1560 MHz, l 1622 → 1349 MHz) and inference slows by 4–10 %.

### 17.5 Why onboard sAP is so low, and what would raise it

Emulation (`validation/hardware/onboard_sap.py`): the laptop computes each model's detections on every test frame exactly as the Pi does; a single engine then takes the newest frame every L ms and the drone holds each result until the next one arrives. Same scorer as the live runs:

| Delay per result L | YOLOv8s-VisDrone sAP / + forecaster | YOLOv8m-VisDrone | YOLOv8l-VisDrone |
| --- | --- | --- | --- |
| 33 ms (keeps up with 30 fps) | 0.165 / 0.217 | 0.175 / 0.230 | 0.184 / 0.241 |
| 100 ms | 0.060 / 0.152 | 0.063 / 0.159 | 0.068 / 0.171 |
| 300 ms | 0.013 / 0.056 | 0.016 / 0.058 | 0.014 / 0.068 |
| 600 ms | 0.007 / 0.023 | 0.009 / 0.025 | 0.007 / 0.026 |
| 1000 ms | 0.003 / 0.010 | 0.007 / 0.013 | 0.005 / 0.013 |
| 3000 ms | 0.002 / 0.002 | 0.002 / 0.002 | 0.002 / 0.002 |

- **The detectors work; the delay is what destroys sAP.** mAP is 0.24–0.27 on the test clips (at the level published for these models on VisDrone, a hard dataset: 91 % of the test objects are smaller than 32 × 32 px). sAP charges for the delay: after 0.7–3.3 s a small object seen from a moving drone has moved further than its own size, so the old box no longer overlaps it (IoU < 0.5) and counts as a miss.
- **The most accurate model is the worst onboard.** YOLOv8l has the best mAP but, at 3.3 s per frame, the lowest sAP; on the Pi alone YOLOv8s is the right choice.
- **A Pi alone cannot deliver usable streaming perception on drone video.** 15–20 % sAP needs results within about 100 ms plus forecasting; only offloading provides that (Part 18). This is the motivation for the three-tier system, measured now with the right weights.

### 17.6 What the VisDrone weights changed

The same onboard test was first run with the COCO weights (hot short, cool short and long runs on both Pis, 20–21 Oct; folders `vid_campaign_onboard{,_cool,_long}_{pi2,pi3}`; superseded by this Part and kept only for this comparison):

| Hot-start short runs | mAP COCO → VisDrone | sAP COCO → VisDrone | sAP + forecaster COCO → VisDrone |
| --- | --- | --- | --- |
| YOLOv8s | 0.088 → 0.242 (×2.7) | 0.0014 → 0.0062 (×4.4) | 0.0045 → 0.0162 (×3.6) |
| YOLOv8m | 0.117 → 0.256 (×2.2) | 0.0025 → 0.0053 (×2.1) | 0.0042 → 0.0082 (×2.0) |
| YOLOv8l | 0.134 → 0.274 (×2.0) | 0.0004 → 0.0011 (×2.8) | 0.0005 → 0.0014 (×2.8) |

Timing, power and throttling were the same with both weight sets (identical architectures). Caveats: at 2–3.5 s per frame a 4-minute run holds only about 75 YOLOv8l results, so its sAP values are small and noisy; the full-clock figures are computed from the emulation, not measured; one camera at a time, lab temperature, fanless boards.

## PART 18Offloading with the VisDrone weights, and the relay path Pi → Jetson → laptop (22 Oct 2026)

Part 17 shows that the camera drone cannot perceive well alone: the detector is accurate, but a Pi needs 0.7–3.3 s per frame. This Part measures the offloading paths with the VisDrone weights and adds the professor's chain, the camera drone sending through the edge drone to the ground station, as a **fallback path** of the adaptive controller for a camera beyond the ground station's range. The direct three-tier design stays the main system: the relay is one more option, not a replacement. Validated (36 runs)

### 18.1 What was built

- **Relay** (`validation/hardware/relay.py`, on the Jetson): toward the camera it behaves like a worker (connects to the Pi, port 48103); toward the ground like a camera (a normal laptop worker connects to it, port 48104). Frames, probes and the final message pass unchanged both ways, so relayed results are scored exactly like direct ones and the camera's probe round trip covers both hops. The relay keeps its camera link only while a ground worker is connected, so an unreachable ground station appears to the camera as a dead path.
- **Controller** (`adaptive2.py --paths laptop,jetson,relay`): the relay is a third path with the laptop's settings (YOLOv8s at 640/480/320 px, YOLOv8m at 640 px, JPEG q90/q50). Its rate is measured on the Pi → Jetson hop, its round trip includes both hops. v4.1 chooses among onboard, Jetson, laptop and relay with its unchanged objective (Part 16); no new decision logic.
- **Network emulation** (`adaptive.py`): a third netem band for the relay port. The relay's first hop is the Pi → Jetson radio link, so it follows the Jetson path's impairment; the Jetson → laptop hop is not impaired (the edge drone stays in the ground station's range). New scenario **out_of_range**: the direct Pi → laptop link is cut (100 % loss) for the whole run. Verified on the Pi during the first such run: the laptop band dropped every packet, the Jetson band carried 5.9 MB, the relay band was untouched.
- **VisDrone weights everywhere** (`--weight-suffix _visdrone`): onboard models, the laptop and Jetson workers, and the controller's accuracy table (17.1, all 13 settings). Fault found: a worker picks its model by name and silently fell back to its first model for an unknown name, so a YOLOv8m request would have been served by YOLOv8s with the fine-tuned files; workers now also answer to the plain model name.
- **Kept:** v4.1's staleness-decay curve (forecaster v2, measured with the COCO YOLOv8s on the VID train clips). Re-measuring it with the VisDrone weights would be in-sample (those clips are in their training data); the curve is a ratio of accuracy at age t to fresh accuracy and carries over.
- **Scripts:** `tools/arun_b.sh` (one run), `tools/campaign_b.sh` (the campaign), `tools/push_code.sh TARGETS="pi2 nano"`.

### 18.2 The campaign

|  | Design |
| --- | --- |
| Policies (4) | fixed Pi → Jetson YOLOv8s q90; fixed Pi → laptop YOLOv8m q90; fixed relay Pi → Jetson → laptop YOLOv8m q90; v4.1 over onboard + Jetson + laptop + relay (live forecaster, power budget 2.8 W, freshness target 0.95) |
| Scenarios (3) | normal (all links good); mission (good → ground congested → ground blackout → both degraded → total blackout → recovered); out of range (direct Pi → laptop link cut for the whole run) |
| Repetitions | 3 → 36 runs of 4 minutes (six 40-s phases); camera pi2, edge drone Jetson Orin Nano (15 W), ground station laptop RTX 4050 |
| Fairness | all three paths connected in every run, so the policies differ only in their decisions |
| Scoring | standard sAP with and without forecaster, sAP50, mAP, freshness, Pi power and temperature, path shares; paired differences with exact permutation tests and Holm correction (Part 19) |

**Shortened on 22 Oct to free the boards for the mesh work, without losing any of the questions:**

- **Run time halved by a fix, not a cut.** Each run took 10.7 min, of which about 5 were spent waiting: the relay passed the camera's end-of-run message on and closed the connection at once, the worker keeps only the newest message, so the end of the connection replaced the unread end message and the worker waited for its 10-minute timeout. The relay now waits for the worker to close first (tested), and the run script stops a lingering relay worker after 20 s. Runs now take about 5.5 min; no measurement was affected (the camera's part of every run was complete).
- **Dropped:** the two 24-minute runs (the heat behaviour is covered by Part 17, and an offloading Pi stays at about 50 °C) and the wait for a VisDrone YOLOv8n: v4.1's onboard fallback uses the VisDrone YOLOv8s at 320 and 640 px (it only matters in a total blackout).
- **Kept:** 3 repetitions. With 2, a comparison has 6 pairs and the smallest possible exact p-value is 0.031, which cannot pass the Holm correction over 3 comparisons; with 3 repetitions (9 pairs) it is 0.004.
- Order: the 9 Pi → Jetson runs were made first (they do not use the laptop GPU, which was training), so they ran at a different time of day than the others.
- The laptop restarted twice during the work (17:29 and about 18:40); every run finished before each restart was kept (one was collected from the Pi afterwards), and the campaign resumed.

### 18.3 Results (all 36 runs)

Mean over 3 repetitions, standard sAP with the live forecaster ± 95 % CI (`experiments/results/hardware/vid_campaign_b_summary.json` / `.md`, `validation/hardware/b_summary.py`):

| Scenario | Policy | sAP | sAP + forecaster | sAP50 + fc | mAP | fresh | age p95 | Pi | servers |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| normal | Pi → Jetson (YOLOv8s) | 0.062 | **0.159 ± 0.039** | 0.362 | 0.228 | 96 % | 0.28 s | 2.23 W, 54 °C | jetson 100 % |
| normal | Pi → laptop (YOLOv8m) | 0.086 | **0.181 ± 0.002** | 0.399 | 0.244 | 98 % | 0.21 s | 2.47 W, 60 °C | laptop 100 % |
| normal | relay Pi → Jetson → laptop (YOLOv8m) | 0.052 | **0.144 ± 0.043** | 0.331 | 0.243 | 90 % | 0.44 s | 2.20 W, 57 °C | relay 100 % |
| normal | v4.1 (all paths) | 0.058 | **0.143 ± 0.092** | 0.328 | 0.229 | 93 % | 0.32 s | 2.93 W, 62 °C | laptop 56 %, relay 21 %, jetson 21 %, onboard 2 % |
| mission | Pi → Jetson (YOLOv8s) | 0.040 | **0.102 ± 0.016** | 0.239 | 0.237 | 64 % | 29.91 s | 2.10 W, 55 °C | jetson 100 % |
| mission | Pi → laptop (YOLOv8m) | 0.023 | **0.055 ± 0.004** | 0.134 | 0.280 | 32 % | 35.74 s | 2.05 W, 59 °C | laptop 100 % |
| mission | relay Pi → Jetson → laptop (YOLOv8m) | 0.037 | **0.096 ± 0.027** | 0.225 | 0.247 | 61 % | 30.10 s | 2.09 W, 60 °C | relay 100 % |
| mission | v4.1 (all paths) | 0.047 | **0.124 ± 0.007** | 0.283 | 0.222 | 91 % | 0.37 s | 3.41 W, 69 °C | laptop 33 %, relay 33 %, jetson 28 %, onboard 6 % |
| out of range | Pi → Jetson (YOLOv8s) | 0.062 | **0.155 ± 0.052** | 0.351 | 0.227 | 93 % | 0.32 s | 2.24 W, 55 °C | jetson 100 % |
| out of range | Pi → laptop (YOLOv8m) | 0.000 | **0.000 ± 0.000** | 0.000 | 0.000 | 0 % | 227.97 s | 1.76 W, 54 °C | laptop 100 % |
| out of range | relay Pi → Jetson → laptop (YOLOv8m) | 0.062 | **0.161 ± 0.032** | 0.367 | 0.243 | 98 % | 0.23 s | 2.17 W, 56 °C | relay 100 % |
| out of range | v4.1 (all paths) | 0.053 | **0.143 ± 0.060** | 0.330 | 0.230 | 95 % | 0.31 s | 2.91 W, 64 °C | relay 57 %, jetson 41 %, onboard 2 % |
| all | Pi → Jetson (YOLOv8s) | 0.055 | **0.139 ± 0.023** | 0.317 | 0.231 | 84 % | 10.17 s | 2.19 W, 55 °C | jetson 100 % |
| all | Pi → laptop (YOLOv8m) | 0.036 | **0.079 ± 0.062** | 0.178 | 0.175 | 44 % | 87.97 s | 2.09 W, 58 °C | laptop 100 % |
| all | relay Pi → Jetson → laptop (YOLOv8m) | 0.050 | **0.134 ± 0.024** | 0.308 | 0.244 | 83 % | 10.26 s | 2.15 W, 58 °C | relay 100 % |
| all | v4.1 (all paths) | 0.053 | **0.137 ± 0.019** | 0.314 | 0.227 | 93 % | 0.33 s | 3.08 W, 65 °C | relay 37 %, laptop 30 %, jetson 30 %, onboard 3 % |

Mission, per phase (sAP with the forecaster, mean of 3):

| Policy | good | ground congested | ground blackout | both degraded | total blackout | recovered low battery |
| --- | --- | --- | --- | --- | --- | --- |
| Pi → Jetson (YOLOv8s) | 0.208 | 0.090 | 0.165 | 0.032 | 0.001 | 0.189 |
| Pi → laptop (YOLOv8m) | 0.248 | 0.029 | 0.000 | 0.024 | 0.001 | 0.216 |
| relay Pi → Jetson → laptop (YOLOv8m) | 0.208 | 0.079 | 0.172 | 0.031 | 0.001 | 0.170 |
| v4.1 (all paths) | 0.239 | 0.068 | 0.163 | 0.058 | 0.042 | 0.186 |

Paired comparisons (reference minus policy; exact permutation p-values, Holm within each reference):

| Comparison | Scope | pairs | Δ sAP + fc | wins | p | p Holm |
| --- | --- | --- | --- | --- | --- | --- |
| v4.1 vs Pi → Jetson (YOLOv8s) | all | 9 | -0.0018 ± 0.0212 | 5/9 | 0.863 | 1.000 |
| v4.1 vs Pi → laptop (YOLOv8m) | all | 9 | +0.0580 ± 0.0630 | 6/9 | 0.078 | 0.234 |
| v4.1 vs relay Pi → Jetson → laptop (YOLOv8m) | all | 9 | +0.0031 ± 0.0230 | 5/9 | 0.770 | 1.000 |
| relay vs Pi → laptop (YOLOv8m) | all | 9 | +0.0549 ± 0.0674 | 6/9 | 0.121 | 0.121 |
| v4.1 vs Pi → Jetson (YOLOv8s) | mission | 3 | +0.0216 ± 0.0214 | 3/3 | 0.250 | 0.750 |
| v4.1 vs Pi → laptop (YOLOv8m) | mission | 3 | +0.0691 ± 0.0032 | 3/3 | 0.250 | 0.750 |
| v4.1 vs relay Pi → Jetson → laptop (YOLOv8m) | mission | 3 | +0.0275 ± 0.0300 | 3/3 | 0.250 | 0.750 |
| v4.1 vs Pi → Jetson (YOLOv8s) | out of range | 3 | -0.0117 ± 0.0255 | 0/3 | 0.250 | 0.750 |
| v4.1 vs Pi → laptop (YOLOv8m) | out of range | 3 | +0.1428 ± 0.0597 | 3/3 | 0.250 | 0.750 |
| v4.1 vs relay Pi → Jetson → laptop (YOLOv8m) | out of range | 3 | -0.0181 ± 0.0461 | 0/3 | 0.250 | 0.750 |
| v4.1 vs Pi → Jetson (YOLOv8s) | normal | 3 | -0.0154 ± 0.0997 | 2/3 | 1.000 | 1.000 |
| v4.1 vs Pi → laptop (YOLOv8m) | normal | 3 | -0.0380 ± 0.0914 | 0/3 | 0.250 | 0.750 |
| v4.1 vs relay Pi → Jetson → laptop (YOLOv8m) | normal | 3 | -0.0003 ± 0.0954 | 2/3 | 1.000 | 1.000 |
| relay vs Pi → laptop (YOLOv8m) | mission | 3 | +0.0416 ± 0.0292 | 3/3 | 0.250 | 0.250 |
| relay vs Pi → laptop (YOLOv8m) | out of range | 3 | +0.1609 ± 0.0322 | 3/3 | 0.250 | 0.250 |
| relay vs Pi → laptop (YOLOv8m) | normal | 3 | -0.0378 ± 0.0454 | 0/3 | 0.250 | 0.250 |

### 18.4 What the results show

- **Out of range, the relay keeps the drone perceiving.** With the direct ground link cut, fixed Pi → laptop delivers nothing (0.000 in 3 of 3 runs) while the relay delivers 0.161 ± 0.032, the best of all policies there, and the Jetson path 0.155. v4.1 moved its laptop-bound frames to the relay and the Jetson by itself (relay 57 %, Jetson 41 %, laptop 0 %) and reached 0.143, slightly below the two fixed paths it switched to (in 3 of 3 pairs, by 0.012–0.018): the cost of trying the dead direct path and of the probes.
- **In the mission, adaptation wins.** v4.1 has the highest sAP (0.124 ± 0.007; ahead of the Jetson path by 0.022, the relay by 0.028 and the laptop path by 0.069, in 3 of 3 pairs each), and it is the only policy that still perceives in the total blackout (0.042 against 0.001, onboard YOLOv8s fallback). In the ground blackout the relay (0.172) and the Jetson (0.165) keep working while the laptop path drops to 0.000.
- **On a good link the direct laptop path is best.** Fixed laptop YOLOv8m 0.182 ± 0.002, Jetson YOLOv8s 0.159, relay 0.144, v4.1 0.143 ± 0.092 (one weak repetition). The extra hop costs the relay about 0.04 against the direct laptop path (p95 age 444 against 211 ms). v4.1 sent 56 % of its frames to the laptop and the rest to the Jetson and the relay; with all three remote paths sharing one Wi-Fi channel, spreading frames did not pay on a good link here.
- **Overall (9 pairs per comparison):** v4.1 0.137, Jetson 0.139, relay 0.134, laptop 0.079 (pulled down by the out-of-range runs); v4.1 holds a detection younger than 300 ms 93 % of the time against 44–84 % for the fixed paths, with a 95th-percentile age of 0.33 s against 10–88 s.
- **Cost on the camera drone:** every policy keeps the Pi far below its throttling point (2.1–3.4 W, 54–69 °C, against 4.4 W and 85 °C onboard); v4.1 uses about 0.9 W more than the fixed paths because of its onboard fallback.
- **Statistics:** with 3 repetitions per scenario no single-scenario comparison can pass a permutation test (smallest possible p = 0.25), and the pooled comparisons mix scenarios in which the ranking reverses, so none is significant after Holm. The out-of-range effect of the relay is nonetheless unambiguous (0.161 against 0.000, 3 of 3, the 95 % interval far from zero). Settling the normal-link ranking of v4.1 needs more repetitions (5 per scenario would allow p = 0.03 per scenario).
- **Phase-to-phase changes are partly the video:** the Jetson and relay paths score 0.08–0.09 in the mission's "ground congested" phase, which limits only the direct laptop path, but they score the same in the same phase of the normal-link runs (0.07–0.09), where nothing is impaired: the 7 test clips play in a fixed order and that phase holds the hardest scenes (figure in 18.7). Policies are therefore compared within a phase, never across phases.

### 18.5 Expected against measured

| Question | Expected | Measured |
| --- | --- | --- |
| Out of range: does the relay keep perception alive? | laptop ≈ 0; relay and Jetson ≈ 0.15–0.17; v4.1 moves to them | **Yes**: laptop 0.000, relay 0.161, Jetson 0.155, v4.1 0.143 with 57 % relay / 41 % Jetson |
| Mission: does adaptation pay? | v4.1 best | **Yes**: 0.124, 3 of 3 against every fixed policy; only one perceiving in the total blackout |
| Good link: v4.1 at least as good as the best fixed path? | yes, as in earlier campaigns | **No** in this campaign: laptop YOLOv8m 0.182 against v4.1 0.143 (high variance) |
| Cost on the camera drone | ≈ 2–2.5 W, ≈ 50 °C | 2.1–2.5 W fixed, 2.9–3.4 W v4.1; 54–69 °C |

### 18.6 The hierarchical chain (the professor's design)

The design asked for: the Pi processes a frame onboard or sends it to the Jetson; the Jetson processes it on its own GPU or, when it is busy or its result would be worse, forwards it to the laptop; there is **no direct Pi → laptop link**. This differs from what B ran: the fixed relay only forwarded (the Jetson never decided), and v4.1 made every decision on the Pi with a direct laptop link available. The chain was not run as one system; its results are **composed** from B's measured runs, because it only ever uses options B measured directly: Pi → Jetson with local detection (the fixed Jetson runs), Pi → Jetson → laptop (the fixed relay runs, same hop and forwarding), and the Pi's onboard fallback when no link works (v4.1 in the total blackout). Lower bound: a Jetson that always detects locally or always forwards, whichever is worse; upper bound: the better of the two in each scenario or mission phase. Pending (composed from measured runs; to be run as one system on the mesh)

| Scenario (sAP with forecaster) | Hierarchical chain (from measured runs) | v4.1 direct three-tier (measured) | Best fixed path (measured) |
| --- | --- | --- | --- |
| Normal link | **0.144–0.159** | 0.143 | Pi → laptop 0.181 |
| Out of range | **0.155–0.161** (unaffected: it has no direct link to lose) | 0.143 | relay 0.161 |
| Mission (mean of the six phases) | **0.121–0.122** | 0.126 | Pi → Jetson 0.114 |
| Pi power, temperature | **≈ 2.1–2.3 W, ≈ 55 °C** | 2.9–3.4 W, 62–69 °C | – |

| Mission phase | Hierarchical (from measured runs) | v4.1 (measured) | Why |
| --- | --- | --- | --- |
| good | 0.208 | **0.239** | v4.1 also uses the direct laptop link |
| ground congested | **0.090** | 0.068 | the chain does not depend on the ground link |
| ground blackout | **0.165–0.172** | 0.163 | about equal: both use the Jetson |
| both degraded | 0.032 | **0.058** | v4.1 uses two links in parallel |
| total blackout | 0.042 | 0.042 | both fall back to the Pi onboard |
| recovered | 0.189 | 0.186 | about equal |

- **In this setup the hierarchical chain is about as good as v4.1:** slightly better on a normal link and out of range (+0.012 to +0.018), about equal in the mission, with the Pi 0.7–1 W cooler (no onboard work except in a total blackout).
- **v4.1's advantage is two independent links:** when both are degraded it uses them in parallel (0.058 against 0.032), and on a perfect link the direct laptop path is the single best option (0.181). Out of range the chain wins by construction.
- **Limits:** the results are assembled phase by phase from separate runs, not from a run of the chain itself. The Jetson's own decision was never exercised: with one camera drone its GPU is rarely busy, and in B the Jetson → laptop link was never impaired. All links shared one Wi-Fi channel in the lab.
- **Next (mesh):** the Jetson-side decision program (detect locally or forward, by expected accuracy after delay, never forwarding over a bad ground link) is written and the chain is run on the AegisSwarm mesh, where the Pi → Jetson and Jetson → laptop links are separate radio links, with impairments on the Jetson → laptop link as well, and with several camera drones so that the Jetson does get busy.

### 18.7 Graphs: throttling, time and clock speed (hierarchical chain against the Pi alone)

All three from measured runs: the chain's parts (B, 18 runs of fixed Pi → Jetson and relay) and Part 17's onboard runs (30). Hover a mark for its values. Data: `experiments/results/hardware/figs_hier_data.json`; figures also in `docs/figs/hier_*.svg` (`scripts/report_figs_hier.py`).


![sAP against throttling](uav-split-perception/docs/figs/hier_sap_vs_throttling.svg)

![sAP over time](uav-split-perception/docs/figs/hier_sap_vs_time.svg)

![Clock speed against temperature and throttling](uav-split-perception/docs/figs/hier_clock_vs_throttling.svg)

## PART 19Every campaign rescored with the standard metrics and replayed with the VisDrone weights (22 Oct 2026; C1–C6 done, VisDrone replay waiting)

Corrections to how the earlier hardware results (Parts 12–15, 776 runs in 8 campaigns, 6–13 Oct) are scored and reported, from the data already recorded: no new runs. Each run is scored without and with its forecaster (`validation/hardware/report_rescore.py`; numbers in `experiments/results/hardware/report_c_summary*.json`, tables in `report_c_tables*.md`). Pending

### 19.1 The fixes

| # | Fix | How |
| --- | --- | --- |
| C1 | State the holding rule; report the **standard** sAP (newest result held) everywhere | The Phase G tables reported the 'quality' rule (the held result with the highest expected accuracy). The verdicts were checked to be the same under the standard rule (G14); the standard values now stand next to every reported one |
| C2 | Score with VisDrone's **ignored regions masked**, as the official protocol does | A detection or ground-truth box more than 50 % inside an ignored region (category 0) is removed (VisDrone toolkit rule). The 7 test clips have 3,994 ignored-region boxes on 1,434 frames of 5 clips (2 clips have none) |
| C3 | Add **sAP50**, **sAP by object size** and **worst-case freshness** | Sizes: COCO area ranges in the 640-px frame; of 108,645 test objects 91.2 % are small, 8.8 % medium and only 7 large, so 'large' is not reported. Freshness: 95th-percentile and maximum age of the held result, the longest stretch older than 300 ms, the fresh share |
| C4 | Results **per scenario**, and per phase inside the missions | Normal phases separate from congestion and blackouts |
| C5 | State the **assumptions** | see 19.4 |
| C6 | **Holm correction** for multiple comparisons | Paired differences against each campaign's reference controller with 95 % t-intervals, exact sign-flip permutation p-values (all 2^n sign patterns, no distribution assumed) and Holm-adjusted p-values within each campaign and metric |
| C7 | **Replay every campaign with the VisDrone weights** (added 22 Oct) | Each recorded result keeps its frame, server, setting (model, input size, JPEG quality) and arrival time; its detections are replaced by those of the same setting from the VisDrone-trained model, computed exactly as the live system does (letterbox, JPEG encode and decode, FP16 on the GPU for offloaded settings; `validation/hardware/vd_variant_dets.py`). The architectures are the same, so the timing holds. The controllers made their choices with the COCO accuracy table, so this is 'the same schedules with VisDrone detectors', not what a VisDrone-aware controller would have chosen; that is what Part 18 measures live |

### 19.2 Status and expected results

| Step | Status | Expected result | Output |
| --- | --- | --- | --- |
| C1–C6 on the recorded (COCO) detections | **done** (all 776 runs) | results in 19.4 | `report_c_summary.json`, `report_c_tables.md` (every campaign: pooled table, per scenario, per mission phase, paired tests) |
| C7: VisDrone detections of every setting | waiting for the go-ahead (checkpoint, 22 Oct 23:00); the VisDrone YOLOv8n fine-tuning is paused at epoch 24 of 80 and resumes from there | 11 settings × 2,846 test frames | `vd_variant_dets/` |
| C7: replay of all 776 runs | after the step above | Absolute sAP about 2–4× higher (the fine-tuning raised mAP 2–2.7× and onboard sAP 2–4× in Part 17); the rankings of policies expected to hold, because the schedules are the same and the gain applies to every setting | `report_c_summary_visdrone.json`, `report_c_tables_visdrone.md` |
| Final report | after both | Parts 12–15 restated with VisDrone-weight numbers next to the original ones | this report |

### 19.3 Results of C1–C6 (all 776 runs, recorded detections)

Every campaign's headline comparison, now with the standard sAP and the campaign's forecaster (the metric of record), with exact permutation p-values corrected by Holm within each campaign. Differences are reference minus policy, mean ± 95 % CI over scenario × repetition pairs:

| Campaign | Comparison | Δ sAP (standard + fc) | wins | p | p Holm | p Holm, quality rule | p Holm, masked |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Part 12 (108 runs, shared Wi-Fi) | A_full vs fixed_onboard_n320 | +0.0245 ± 0.0082 | 11/12 | 0.001 | **0.008** | 0.008 | 0.008 |
| Part 12 (108 runs, shared Wi-Fi) | A_full vs fixed_jetson_s640q90 | +0.0084 ± 0.0062 | 10/12 | 0.006 | **0.044** | 0.031 | 0.048 |
| Part 12 (108 runs, shared Wi-Fi) | A_full vs rule_fallback | +0.0041 ± 0.0073 | 9/12 | 0.236 | **1.000** | 1.000 | 1.000 |
| Part 12 (108 runs, shared Wi-Fi) | A_full vs static_multi | +0.0034 ± 0.0056 | 11/12 | 0.214 | **1.000** | 1.000 | 1.000 |
| Part 12 (108 runs, shared Wi-Fi) | A_full vs A_stream | -0.0003 ± 0.0095 | 5/12 | 0.930 | **1.000** | 1.000 | 1.000 |
| Part 12 (108 runs, shared Wi-Fi) | A_full vs abr_laptop | -0.0015 ± 0.0084 | 7/12 | 0.721 | **1.000** | 1.000 | 1.000 |
| Part 12 (108 runs, shared Wi-Fi) | A_full vs A_full_aer | -0.0025 ± 0.0082 | 2/12 | 0.538 | **1.000** | 1.000 | 1.000 |
| Part 12 (108 runs, shared Wi-Fi) | A_full vs fixed_laptop_m640q90 | -0.0035 ± 0.0110 | 4/12 | 0.502 | **1.000** | 1.000 | 1.000 |
| Part 14 (forecaster v1 campaign) | A_full vs A_stream_fc | -0.0005 ± 0.0085 | 7/12 | 0.924 | **0.924** | 0.663 | 0.908 |
| Part 14 (forecaster v1 campaign) | A_full vs A_stream | -0.0066 ± 0.0045 | 1/12 | 0.002 | **0.005** | 0.097 | 0.004 |
| Part 14 (80-run campaign, live forecaster v2) | A_full vs fixed_laptop_m640q90 | +0.0046 ± 0.0057 | 14/20 | 0.107 | **0.215** | 0.137 | 0.226 |
| Part 14 (80-run campaign, live forecaster v2) | A_full vs A_stream_fc | -0.0002 ± 0.0079 | 7/20 | 0.983 | **0.983** | 0.911 | 0.976 |
| Part 14 (80-run campaign, live forecaster v2) | A_full vs A_stream_fc2 | -0.0038 ± 0.0039 | 6/20 | 0.055 | **0.166** | 0.063 | 0.150 |
| Part 14 (80-run campaign, live forecaster v2) | A_stream_fc2 vs fixed_laptop_m640q90 | +0.0084 ± 0.0054 | 15/20 | 0.004 | **0.012** | 0.001 | 0.012 |
| Part 14 (80-run campaign, live forecaster v2) | A_stream_fc2 vs A_full | +0.0038 ± 0.0039 | 14/20 | 0.055 | **0.111** | 0.042 | 0.100 |
| Part 14 (80-run campaign, live forecaster v2) | A_stream_fc2 vs A_stream_fc | +0.0036 ± 0.0069 | 11/20 | 0.334 | **0.334** | 0.348 | 0.336 |
| G9 (energy campaign) | A_stream_fc2 vs A_full | -0.0012 ± 0.0044 | 11/20 | 0.573 | **1.000** | 1.000 | 1.000 |
| G9 (energy campaign) | A_stream_fc2 vs fixed_laptop_m640q90 | -0.0016 ± 0.0059 | 11/20 | 0.580 | **1.000** | 1.000 | 1.000 |
| G9 (energy campaign) | A_stream_fc2 vs A_eco | -0.0066 ± 0.0053 | 4/20 | 0.019 | **0.056** | 0.067 | 0.058 |
| G9 (energy campaign) | A_stream_fc2 vs A_eco_tight | -0.0089 ± 0.0038 | 3/20 | 0.000 | **0.000** | 0.000 | 0.001 |
| G11 (live power on both boards) | A_eco_tight vs fixed_laptop_m640q90 | +0.0087 ± 0.0061 | 15/20 | 0.009 | **0.036** | 0.026 | 0.037 |
| G11 (live power on both boards) | A_eco_tight vs A_stream_fc2 | +0.0083 ± 0.0042 | 19/20 | 0.001 | **0.003** | 0.025 | 0.004 |
| G11 (live power on both boards) | A_eco_tight vs A_eco42d | +0.0015 ± 0.0054 | 14/20 | 0.551 | **1.000** | 1.000 | 1.000 |
| G11 (live power on both boards) | A_eco_tight vs A_eco42 | -0.0001 ± 0.0042 | 10/20 | 0.988 | **1.000** | 1.000 | 1.000 |
| G11 (live power on both boards) | A_eco_tight vs A_eco41 | -0.0019 ± 0.0040 | 8/20 | 0.410 | **1.000** | 0.622 | 1.000 |
| G12 (main campaign, 240 runs) | v5 vs reward_offload | +0.0265 ± 0.0037 | 20/20 | 0.000 | **0.000** | 0.000 | 0.000 |
| G12 (main campaign, 240 runs) | v5 vs conf_trigger | +0.0221 ± 0.0028 | 20/20 | 0.000 | **0.000** | 0.000 | 0.000 |
| G12 (main campaign, 240 runs) | v5 vs jsq | +0.0168 ± 0.0027 | 20/20 | 0.000 | **0.000** | 0.000 | 0.000 |
| G12 (main campaign, 240 runs) | v5 vs aoi_thr | +0.0110 ± 0.0032 | 20/20 | 0.000 | **0.000** | 0.000 | 0.000 |
| G12 (main campaign, 240 runs) | v5 vs fixed_laptop_m640q90 | +0.0065 ± 0.0055 | 16/20 | 0.026 | **0.131** | 0.065 | 0.143 |
| G12 (main campaign, 240 runs) | v5 vs v5_flat | +0.0061 ± 0.0034 | 16/20 | 0.001 | **0.008** | 0.020 | 0.008 |
| G12 (main campaign, 240 runs) | v5 vs v5_nofc | +0.0058 ± 0.0039 | 14/20 | 0.004 | **0.024** | 0.044 | 0.024 |
| G12 (main campaign, 240 runs) | v5 vs v42 | +0.0018 ± 0.0026 | 12/20 | 0.173 | **0.693** | 0.559 | 0.717 |
| G12 (main campaign, 240 runs) | v5 vs leaf | +0.0001 ± 0.0016 | 9/20 | 0.843 | **1.000** | 1.000 | 1.000 |
| G12 (main campaign, 240 runs) | v5 vs v5_lin | +0.0001 ± 0.0013 | 10/20 | 0.855 | **1.000** | 1.000 | 1.000 |
| G12 (main campaign, 240 runs) | v5 vs v5_exp | +0.0000 ± 0.0027 | 8/20 | 0.978 | **1.000** | 1.000 | 1.000 |
| G13 (same-day table) | v41 vs onboard_n320 | +0.0431 ± 0.0083 | 20/20 | 0.000 | **0.000** | 0.000 | 0.000 |
| G13 (same-day table) | v41 vs v5 | +0.0008 ± 0.0017 | 9/20 | 0.345 | **0.690** | 0.716 | 0.783 |
| G13 (same-day table) | v41 vs v51 | +0.0004 ± 0.0010 | 8/20 | 0.508 | **0.690** | 0.663 | 0.783 |
| G13 (same-day table) | v5 vs onboard_n320 | +0.0423 ± 0.0083 | 20/20 | 0.000 | **0.000** | 0.000 | 0.000 |
| G13 (same-day table) | v5 vs v51 | -0.0004 ± 0.0016 | 13/20 | 0.591 | **0.690** | 1.000 | 0.783 |
| G13 (same-day table) | v5 vs v41 | -0.0008 ± 0.0017 | 11/20 | 0.345 | **0.690** | 1.000 | 0.783 |
| G13 (24-minute missions) | v41 vs fixed_laptop_m640q90 | +0.0247 ± 0.0042 | 2/2 | 0.500 | **1.000** | 1.000 | 1.000 |
| G13 (24-minute missions) | v41 vs stream_fc2 | +0.0159 ± 0.1337 | 2/2 | 0.500 | **1.000** | 1.000 | 1.000 |
| G13 (24-minute missions) | v41 vs v51 | +0.0108 ± 0.0358 | 2/2 | 0.500 | **1.000** | 1.000 | 1.000 |
| G13 (24-minute missions) | v41 vs v5 | +0.0093 ± 0.0306 | 2/2 | 0.500 | **1.000** | 1.000 | 1.000 |
| G13 (24-minute missions) | v41 vs v42 | +0.0049 ± 0.0028 | 2/2 | 0.500 | **1.000** | 1.000 | 1.000 |
| G13 (24-minute missions) | v5 vs fixed_laptop_m640q90 | +0.0154 ± 0.0348 | 2/2 | 0.500 | **1.000** | 1.000 | 1.000 |
| G13 (24-minute missions) | v5 vs stream_fc2 | +0.0065 ± 0.1031 | 1/2 | 1.000 | **1.000** | 1.000 | 1.000 |
| G13 (24-minute missions) | v5 vs v51 | +0.0015 ± 0.0052 | 2/2 | 0.500 | **1.000** | 1.000 | 1.000 |
| G13 (24-minute missions) | v5 vs v42 | -0.0045 ± 0.0334 | 0/2 | 0.500 | **1.000** | 1.000 | 1.000 |
| G13 (24-minute missions) | v5 vs v41 | -0.0093 ± 0.0306 | 0/2 | 0.500 | **1.000** | 1.000 | 1.000 |

- **The holding rule changes no verdict.** The standard and the 'quality' sAP differ by at most a few percent in every campaign, and every comparison that was significant under one rule is significant under the other (C1).
- **Masking the ignored regions changes no verdict.** It raises sAP by about 1–2 % uniformly (C2).
- **Survive the Holm correction:** energy pricing (v4) over v3 + forecasting (G9: +0.0089, 17 of 20; G11: +0.0083, 19 of 20); v5 over the four literature baselines (+0.011 to +0.027, 20 of 20 each, p < 0.001); the staleness ablations (no staleness −0.0061, p = 0.008; no-forecast curve −0.0058, p = 0.024); v4.1 and v5 over onboard-only (+0.043, 20 of 20).
- **Do not survive it (corrections to earlier wording):** v5 over fixed JPEG offloading to the laptop (+0.0065, 16 of 20, Holm p = 0.13; the earlier report called it a win); in the Part 12 campaign, with the forecaster applied, v2 (A_full) is significantly better only than onboard and the fixed Jetson path, and the fixed laptop YOLOv8m has the highest mean (0.046 against 0.043, not significant). The 24-minute missions have 2 runs per policy, so no comparison there can be significant (smallest possible p = 0.5): the long-run ranking of v4.1 remains a trend.
- **Ties confirmed:** v4.1, v5 and v5.1 (G13, 20 pairs each, p = 0.69); the generic decay curves and LEAF-style fixed weight against v5 (G12).
- **Object size (C3):** medium objects score about 4–5× higher than small ones for every policy (e.g. Part 12 laptop YOLOv8m: small 0.028, medium 0.139); 91 % of the objects are small, so small objects set the overall sAP.
- **Worst-case freshness (C3):** the adaptive controllers hold a detection younger than 300 ms 86–100 % of the time with a 95th-percentile age of 0.2–0.4 s and no stale stretch longer than 0.2 s on the Part 12 campaign, while fixed remote paths have 95th-percentile ages of 11–13 s and stale stretches of 46 s (the blackout phases), a difference the mean sAP does not show.

**First check.** Scoring a G12 mission run (freshness-threshold baseline) gives sAP 0.0159 unmasked (identical to the value cached for G12) and 0.0161 masked; small objects 0.010, medium 0.057; the held result was older than 300 ms 34 % of the time, with a longest stale stretch of 22 s (the blackout phase).

### 19.4 Assumptions, stated explicitly (C5)

- VisDrone-VID frames are replayed at 30 fps; the dataset does not publish its frame rate, so every age in milliseconds scales with this choice.
- The camera stream is the clips resized to 640 px wide; full resolution would help the small objects but costs transfer and compute.
- The controller v1 and v2 results (Parts 9–10) used looped COCO photographs and an accuracy-weighted on-time rate, a proxy without sAP; they cannot be rescored.
- Every campaign up to 13 Oct ran the COCO-trained detectors; their absolute sAP is therefore low and not comparable with VisDrone literature, while comparisons between policies within a campaign stand. C7 replays them with the VisDrone weights; from Part 17 on, all live detectors are VisDrone-trained.
- Numbers from different campaigns are not comparable (Wi-Fi conditions and board state differ by day): compare within one campaign only.

## PART 20What it all means: the argument for the paper

This part ties the results into one line of reasoning: what can be claimed, why the evidence supports it, and where it stops.

### 1. Where to compute: send the image, don't split the network

**Claim.** For YOLO-class detectors on drone hardware, offloading a compressed image beats every split of the network.\
**Why.** A split has to send intermediate features. Even INT8+zstd, the smallest split (k4, 310.7 KiB), is 2.0–11.5× a JPEG frame across 19 detectors. The drone also has to compute the first layers, which on a Pi takes 210–252 ms. Both costs push latency up, and they buy no accuracy, because JPEG q90 is near-lossless for detection.\
**Evidence.** A closed-form bound, simulation, all 1,150 placements on real hardware, live runs (best split 7.0 frames/s against 15.2 for JPEG), and the calibrated swarm study (the split never beats JPEG in any cell).\
**Limit.** A learned, trained compressor for the features could change this; that test is still to do.

### 2. How to schedule: use every computer, adapt per frame

**Claim.** A scheduler that keeps the onboard CPU, the edge GPU and the ground GPU busy in parallel and picks model, resolution and JPEG quality per frame gives the best perception when links fail.\
**Why.** Each tier fails differently: the ground link drops out, the drone-to-drone link congests, and onboard is slow but never disconnected. Running them in parallel turns the failure of one into a lower rate rather than an outage. Adapting the setting to each path's current speed keeps results on time.\
**Evidence.** On the proxy metric, +59–62 % over the best fixed strategy (88 runs). On real streaming accuracy over real Wi-Fi, v2 is ahead of every other policy on average, by +4.5 % up to +201 % (108 runs). This is significant against onboard, the Jetson and rule-based fallback.\
**Limit.** Against all-servers-without-adaptation, single-path rate adaptation and the fixed laptop, the intervals still cross zero with 3 repetitions. Parallel offloading, adaptive device-plus-server use and per-frame adaptation are each known (Elf, Odessa, Chameleon). The contribution is the measured evidence on real drone tiers with streaming AP, not the mechanism.

### 3. What quality means on a drone: staleness, and how to undo it

**Claim.** On aerial video a detection loses most of its value within 100–200 ms, and motion forecasting recovers much of it cheaply.\
**Why.** The camera platform itself moves, so even static objects shift across the image. A 300 ms "on-time" deadline counts a result as fully useful when it has already lost over 90 % of its accuracy. Forecasting moves each box along its observed motion, which is mostly smooth over a few hundred milliseconds.\
**Evidence.** The decay is measured twice (GPU and CPU detections agree within 1 point). Forecasting raises kept accuracy at 267 ms from 7 % to 47 % on training videos, and raises streaming AP for all 9 policies on the 108 test runs (median +32 % to +67 %), with settings fixed before the test. On the Pi it costs 3.9 ms per arriving result.\
**Stronger version.** Measuring the camera's own motion from the images (2.7 ms per frame on the Pi) and forecasting only the objects' residual motion keeps 60 % of accuracy at 267 ms, and roughly doubles streaming AP on the real runs. It beats the simple forecaster in all 144 runs.\
**Prior work.** Tracking to hide offloading delay (Glimpse 2015; Liu et al., MobiCom 2019), latency forecasting (streaming perception; PVT++ on UAVs) and optical-flow camera-motion compensation (BoT-SORT) are all established. What is ours: the measured aerial decay curves with and without correction, and the measured gains on a real distributed drone system.\
**Limit.** Constant velocity per object, zero velocity for newly seen objects, and a similarity transform for the camera (no perspective). An IMU-assisted or learned forecaster may add more.

### 4. Scheduling for the decay you actually have

**Claim.** The scheduler's objective must use the decay curve the drone really experiences. With forecasting that curve is far flatter, and a scheduler built on it keeps a fresh detection almost all the time.\
**Why.** Built on the steep curve, v3 chased the fastest results and lost accuracy (−14 % against v2). Rebuilt on the forecasting curve, it values steady, slightly older results correctly.\
**Evidence.** In a paired 36-run campaign, v3 + forecasting held a detection under 300 ms old 99.0–99.9 % of the time in every scenario (v2: 75–92 % under impairment), with accuracy level with v2.\
**Limit.** Accuracy ranking against v2 is inconclusive with 3 repetitions on a shared Wi-Fi, where session-to-session variation is as large as the gap between controllers.\
**Further support.** With the stronger forecaster v2 the decay is flatter still, and the policy that wins on a clean link changes to the big accurate model. Every controller built for a steeper curve under-uses it.\
**Confirmed.** v3 rebuilt on the v2 curve, with the forecaster running live on the Pi, beats v2 significantly over 20 paired runs (+0.0045 ± 0.0035 sAP) and wins the clean link too. This is the clearest evidence for the principle: match the objective to the forecaster in use.

### 5. Many drones: decide together, not alone

**Claim.** When drones share a network, per-drone adaptation is not enough; a light admission coordinator prevents collapse and starvation.\
**Why.** Each drone sees only its own link and plans as if it had a fair share. Together they overload the network: frames arrive late everywhere, or the router serves some drones and starves others. Limiting how many offload at once, and rotating turns, keeps the shared link inside its capacity.\
**Evidence.** Calibrated simulation over 96 cases: better in 16, tied in 74, worse in 6. Same split on held-out seeds. 20 Pi drones go from 0 to 4.15 detections/s each, and the worst-served drone from 0 to 7.65.\
**Stronger version.** With each drone's radio reporting its own link health, the coordinator stops mistaking a drone's own blackout for congestion or starvation. The one real loss disappears (−7.4 % → +0.5 %), and every remaining loss is at most 1.9 %, on held-out seeds too.\
**Credibility.** The simulator, rebuilt from 44 real runs, predicts on-time rates per phase with correlation 0.947, in every phase.\
**Hardware.** With two real camera drones, sharing the ground station costs the Pi 11–19 % of its accuracy, and adaptive control beats fixed offloading in 6 of 6 pairs. The coordinator rarely acts with two cameras, as the simulation predicts for small swarms.\
**Prior work.** Splitting a shared uplink among cameras with per-camera adaptation is established (JCAB, INFOCOM 2020). Ours is the admission rule with radio link health and its hardware calibration.\
**Limit.** The coordinator's gains are still simulation results. The extra boards will allow 3–5 real cameras, where the gains should appear.

### 6. Energy, heat and accuracy are coupled: price energy, and accuracy rises

**Claim.** On a small fanless drone computer, energy-aware scheduling is not a trade-off against accuracy; done right, it improves it.\
**Why.** Onboard inference costs about 80× the energy of sending a JPEG, heats the Pi into throttling within seconds, and steals CPU from encoding, the camera loop and forecasting. Pricing energy against a measured power budget (dual ascent on live power) removes the low-value onboard work and keeps the board out of the throttling region.\
**Evidence.** Measured power and temperature on both boards. Every earlier campaign was rescored. In a 100-run campaign v4 cut measured Pi power by about 1 W and throttling-region time from 76 % to 17 %, while being significantly more accurate than every other controller (+0.0074 ± 0.0028 sAP over v3 + forecasting v2). It also has the highest mission perception for 249 g and 1.2 kg drones.\
**Prior work.** Energy-aware offloading for drones and mobile devices is a large field, and DVFS and thermal-aware scheduling are known. What needs checking: whether the measured coupling, where energy pricing *raises* streaming accuracy through heat and CPU contention, has been shown before.\
**Limit.** Freshness falls from 99 % to 87 %. The Jetson's power was modelled, not logged live. Runs last 2 minutes; longer flights would heat the Pi more, which should favour v4 further.

### Honest negatives, also part of the paper

- The original staleness-aware v3 did not beat v2.
- Feedback learning in the coordinator did not pay off overall.
- On a clean link, a fixed strong server is as good as any adaptive policy.
- The PDF's mothership split design was the worst placement measured (Part 8).

## PART 21Faults found and fixed

| Fault | Effect | Fix |
| --- | --- | --- |
| Ultralytics caps PyTorch at 1 thread | Pi 65 % slower | Threads reset after import |
| Jetson GPU down-clocks at low load; reboot clears the lock | Remote times doubled | `jetson_clocks` before every run |
| Frames queued in the kernel send buffer | 1.3 s latency | Send the next frame only after the previous one has left |
| Old result files read as new | Stale live numbers | Delete before each run |
| Onboard scored below sending to a dead link | No blackout fallback | Late results keep 25 % value; energy weight reduced |
| TCP back-off after blackouts | 10+ s recovery | Reconnect stalled links; 2.5 s worker liveness timeout |
| Stall rule judged total transfer time | Large payloads penalized | Stall = no acknowledged bytes for 1.5 s |
| Leftover workers from earlier runs | Jetson path crippled (27 runs discarded) | Kill stale processes before every run |
| Sender thread died on a closed socket | Link dead for the rest of a run (10 runs rerun) | Closed socket treated as a failed link; thread cannot die |
| Slow NMS at confidence 0.01 | Up to 130 ms per frame | Vectorized GPU NMS, same AP |
| Stuck remote-time estimates after warm-up | Servers abandoned | Warm-up at all sizes; stale estimates relax toward the measured prior |
| Temp-file cleanup wiped the helper scripts | Lost tools | Helpers moved into the repo |
| Network outages during campaigns | Runs failing in a loop | Outage guard pauses until both boards respond |
| Heat-run completion poll matched its own SSH command line | Run finished but the watcher polled for another 90 min; fetch never ran | Character-class pgrep pattern (`thermal_[s]teady.py`) so the poll cannot match itself |
| Laptop worker gave up after ~70 s without a connection | First 24-minute runs lost in the 4-minute blackout | Give up only after 30 min without a connection; clock restarts when a connection ends |
| Energy price kept integrating while onboard was forced (blackout) | Price reached 41, priced out offloading after the links returned | Anti-windup: price frozen while forced, capped at 5 (λ_F at 2) |
| Result file copied while still being written | Truncated result of a long run | Result written once, last, via a temporary file and rename |
| netem 'change' kept the previous phase's rate limit | 'Recovered' phases still rate-limited in every campaign up to 13 Oct; a false 'slow recovery' finding | Each phase deletes and re-adds the impairment; --netem-legacy reproduces the old behaviour |
| Jetson Wi-Fi power saving re-enabled by the network manager | Latency spikes on the Jetson link | Switched off on both boards before every run |
| Laptop went to sleep overnight | One run invalid, campaign paused 2 h 47 min | Run set aside and redone; keep-awake helper during campaigns |
| A 300 MB git push during a campaign | One run possibly disturbed | Run set aside and redone; no large uploads during campaigns |
| Replay seeded each policy's randomness with Python's hash() | Unpaired, non-reproducible replay comparisons | Common random numbers per seed |
| Worker served an unknown model name with its first model | With fine-tuned files a YOLOv8m request would have run YOLOv8s | Workers also answer to the plain model name (22 Oct) |
| Two copies of the YOLOv8l onboard tests started on the same Pis (a watcher left from an earlier session) | Runs killed each other (21 Oct) | All stopped, partial folders archived (`_superseded/l_duplicate_launch/`), rerun once; one campaign per board, checked before every launch |
| Campaign recovery pulled same-named runs of another campaign on the same Pi | Short and long runs mixed (21 Oct) | Duplicates set aside after checksum comparison; distinct labels and empty folders per campaign |
| Throttle analysis read the VisDrone model names and folders wrongly | Empty / NaN summary | Fixed before any number was reported |

## PART 22Code status and reproducibility

State on 6 October 2026, 15:25, after all campaigns finished:

- **Nothing is running**All campaigns and simulations have finished; the Pi and the Jetson are idle.
- **All 118 project tests pass**`python -m pytest tests`, 17 s, including the simulator tests. This matters because `simulation/stream_sim.py` gained the coordinator. Validated
- **The simulator's default behaviour is unchanged**Three swarm cells computed before the coordinator existed (Pi adaptive 5 drones, Jetson JPEG 10 drones, Jetson adaptive 20 drones) were recomputed with the new code. They are bit-for-bit identical. The coordinator and its feedback layer only act when switched on (`coordination="admission"`, `coord_feedback`), so every earlier paper and simulation result stays valid. Validated
- **Every new or changed script compiles**`forecast.py`, `stream_ap.py`, `summarize_vid.py`, `swarm_calibrated.py`, `adaptive2.py`, `stream_sim.py`, plus a syntax check of `campaign_vid.sh`.
- **Not committed yet**`simulation/stream_sim.py` is the only modified tracked file (+124 lines). `validation/hardware/`, the new docs and `experiments/results/hardware/` are untracked. Ready to commit on `publication-overhaul` when you say so.

| Piece | File | State |
| --- | --- | --- |
| Swarm coordinator and feedback ablation | `simulation/stream_sim.py` | Working; confirmed on held-out seeds |
| Motion forecaster | `validation/hardware/forecast.py` | Working; timed on the Pi |
| Streaming-AP scoring with forecasting | `stream_ap.py`, `summarize_vid.py` | Working; scored all 144 Wi-Fi runs |
| Calibrated swarm study | `validation/hardware/swarm_calibrated.py` | Working; resumable per-cell cache |
| Campaign runner | `validation/hardware/tools/campaign_vid.sh` | Working; policy subsets, heartbeat log, result recovery, outage guard; 144 runs without failures |

### How to reproduce

| Result | Command (from `uav-split-perception/`, venv active) |
| --- | --- |
| Swarm study, with held-out seeds | `python -m validation.hardware.swarm_calibrated`; then `--seed0 5` |
| Forecaster: detections, tuning, decay | `cd validation/hardware; python forecast.py dets; python forecast.py tune; python forecast.py decay` |
| Campaign statistics | `python summarize_vid.py --dir ../../experiments/results/hardware/vid_campaign_wifi --ref A_full` |
| A hardware campaign | `OUTDIR=… REPS=3 ONLY="A_stream_fc A_full A_stream" validation/hardware/tools/campaign_vid.sh` (board passwords from environment variables only) |

## PART 23What is left

| Task | Needs | Time |
| --- | --- | --- |
| Move the three devices onto AegisSwarm; laptop internet over Ethernet; measure each mesh link | Your cable and mesh details | 1–2 h |
| ~~v4 refinements: recover freshness; live Jetson power logging; 20–30 min runs to show sustained heating~~ **Done 9 Oct 2026 in code**: v4.1 (`--fresh-target`), v4.2 (`--edge-energy-aware`: the edge drone priced, budgets derived from battery + flight power, live Jetson power from the worker headers, coordinator `--energy-pref`), system-view rescoring of every campaign (G10) and the 24-min heat-run tool. **Still needs**: the campaign night itself (v4.2/v4.1/v4/v3+fc2/fixed, live logging on both boards) + the 24-min heat runs | Code done; one campaign night | 1–2 days |
| Make the live forecaster cheaper on the Pi (camera tracking every other frame or at lower resolution) | Code + short campaign | half a day |
| Task-level campaign on the mesh: the 9 policies plus v3 + forecasting v1 and v2, 4 scenarios × 5 repetitions (220 runs). Settles the accuracy ranking of v2 against v3 + forecasting | Mesh set up; unattended | about 9–10 h |
| Swarm test with 3 Pis and 2 Jetsons (5 cameras) on the mesh | Your new boards set up | 3–5 days |
| Learned-split test: can a trained compressed split beat JPEG? | The laptop GPU free | 1–2 weeks, overnight |
| Commit the work to git (branch `publication-overhaul`) | Your go-ahead | minutes |
| Paper and professor report update | — | 1–2 weeks |
| **Task C7** (Part 19): VisDrone replay of the 776 earlier runs (YOLOv8n fine-tuning resumes from epoch 24 of 80, VisDrone detections of every setting, rescoring), then Parts 12–15 restated | Laptop GPU and CPU only; waiting for the go-ahead | about 4 h |
| Hierarchical chain on the mesh (18.6): Jetson-side decision program (detect locally or forward to the laptop), then the chain against v4.1 with impairments on both links and several camera drones | Code on the laptop (about 2 h), then the mesh | about 2 h + runs |
| Relay campaign follow-up: 5 repetitions per scenario to settle the good-link ranking of v4.1; the ground-congested drop of the Jetson and relay paths | pi2, Jetson, laptop (or the mesh) | about 3 h |

## PART 24Where everything is

| Path (in `uav-split-perception/`) | Contents |
| --- | --- |
| `paper/main.tex` | The paper (simulation study, theory, validation) |
| `docs/hardware_results.md` | Device, link and placement results |
| `docs/adaptive_results.md` | v2 scheduler results |
| `docs/controller_model.md` | Formal model of controller v3 |
| `docs/novelty_and_related_work.md` | Literature check and claims |
| `docs/assumptions_and_validation.md` | Every model input and its validation status |
| `validation/hardware/` | All hardware scripts and the campaign tools |
| `experiments/results/hardware/` | Raw results; invalid campaigns kept in `*_invalid_*` folders |
| `experiments/results/hardware/vid_campaign_wifi/` | Real-world Wi-Fi campaign (log: `vid_campaign_wifi.log`) |
| `experiments/results/hardware/swarm_calibrated.csv`, `_summary.json` | Calibrated swarm simulation, with coordination (per-cell cache in `swarm_calibrated_cache/`; held-out seeds in `swarm_calibrated_seeds5-9.*`) |
| `experiments/results/hardware/vid_campaign_wifi_fc/` | Paired campaign: v3 + forecasting, v2, old v3 (log: `vid_campaign_wifi_fc.log`) |
| `experiments/results/hardware/staleness_decay_forecast.json` | Decay curve with and without forecasting (exact ages, train) |
| `experiments/results/hardware/_superseded/`, `swarm_calibrated_cache_superseded_coord_v1/` | Files set aside, not deleted: copies wrongly pulled into a campaign folder, and simulation cells from an older coordinator |
| `experiments/results/hardware/energy/`, `vid_campaign_energy/` | Energy profiles, thermal steady states, constants, rescoring of every campaign (system views in `energy_<campaign>.json` / `energy_all_summary.json`), the v4 energy campaign |
| `experiments/results/hardware/vid_campaign_v42/` | The v4.2 campaign (both drones priced, live power on both boards) — to be filled by `validation/hardware/tools/campaign_energy.sh` |
| `validation/hardware/energy_profile.py`, `thermal_steady.py`, `energy_model.py`, `energy_rescore.py` | Energy and heat measurement, model, rescoring |
| `experiments/results/hardware/forecast_tuning_v2.json`, `staleness_decay_forecast_v2.json`, `*_summary_v2.*` | Forecaster v2: tuning on train, decay curve, rescored campaigns |
| `experiments/results/hardware/forecast_tuning.json` | Forecaster tuning on train (all 128 settings) and the frozen setting |
| `weights/yolov8{s,m,l}_visdrone.pt`, `experiments/finetune/`, `scripts/prepare_visdrone_finetune.py`, `scripts/train_visdrone.py` | VisDrone fine-tuning: weights, training runs, data preparation |
| `experiments/results/hardware/onboard_sap/`, `vid_campaign_onboard*_vd*` | Part 17: onboard runs, emulation, throttling analysis (`throttle_analysis_visdrone.json`) |
| `validation/hardware/relay.py`, `tools/campaign_b.sh`, `tools/arun_b.sh`, `experiments/results/hardware/vid_campaign_b*/` | Part 18: relay path and its campaign |
| `validation/hardware/report_rescore.py`, `experiments/results/hardware/report_c_*` | Part 19: standard-metric rescoring |

## PART 25Glossary

Cut k

Layers 0 to k run on the drone; the rest run on the server.

INT8 + zstd

Each number rounded to 8 bits, then losslessly compressed.

JPEG q90 / q50

JPEG quality 90 (high) or 50 (smaller, less accurate).

NMS

Non-maximum suppression: removes duplicate boxes after the network.

mAP

Mean average precision, the standard detection accuracy.

sAP

Streaming AP: accuracy of what the drone holds at each instant.

Availability

Share of time the newest detection is under 300 ms old.

netem

Linux tool used to impose rate limits and blackouts.

IBSS / batman-adv

Ad-hoc Wi-Fi without a router, and a mesh routing protocol on top of it.

Staleness / decay curve

How much accuracy a detection keeps as it ages; measured on training videos.

Motion forecasting

Moving each old box forward by its estimated velocity × its age.

Ego-motion

The camera's own motion between frames, here measured by tracking background points (optical flow) and fitting a rotation/scale/shift.

Admission control

Letting only as many drones offload as the shared network can carry.

Water-filling / capped sharing

Two models of how a network divides capacity: equal fair shares, or a scheduler that serves a few drones and starves the rest.

AIMD

Additive increase, multiplicative decrease: the TCP rule of cutting fast on trouble and growing back slowly.

Held-out seeds

Random seeds not used while designing, kept to confirm a result.

v1 / v2 / v3

The three adaptive controllers: single-path, multi-server, and staleness-aware.

Dual ascent

Adjusting a price (here, of energy) up when a constraint is exceeded and down when not, so the average meets a budget.

Throttling

The Pi's firmware lowering its clock to stay below about 85 °C, making everything slower.

Mission perception

Streaming AP × flight minutes: accuracy and endurance in one number.

v4

The energy- and heat-aware controller: v3 + forecasting v2 with an energy price held to a measured power budget.

Phase oracle

The best fixed strategy per phase, chosen with hindsight.