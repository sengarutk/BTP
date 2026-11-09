# Hardware measurements: where should YOLOv8s run? (Raspberry Pi 5, Jetson Orin Nano, laptop GPU)

Measured on 3 Oct 2026 with the scripts in `validation/hardware/` (see its README). Raw results:
`experiments/results/hardware/` (`raw/` per device and link, `live/` per live run,
`placements.csv`, `live_summary.csv`, `cascade_accuracy.csv`).

## 1. Setup

| Role | Device | Software | Engine |
|---|---|---|---|
| Camera / sense UAV | Raspberry Pi 5 8 GB (4x Cortex-A76 2.4 GHz), Debian 13, **no active cooling** | torch 2.14.1 CPU, ultralytics 8.4.170 | CPU FP32, 4 threads |
| Edge / mothership | Jetson Orin Nano 8 GB, JetPack 7.2.1 (CUDA 13.2), 15 W mode (the highest this board offers), clocks locked (`jetson_clocks`) for live runs | torch 2.14.1+cu130 | GPU FP16 (FP32 also measured) |
| Cloud / ground | Laptop RTX 4050 6 GB (WSL2) | torch 2.13.0+cu130 | GPU FP16 (FP32 also measured) |

All three are Wi-Fi clients of the same home access point, so the "A2A" link (Pi to Jetson) is
**router-mediated Wi-Fi, not a direct air-to-air radio**: each packet crosses the air twice, and all
links share one channel.

Workload: YOLOv8s (Conv+BN fused), 640x640 letterboxed COCO val2017 frames, batch 1. Cuts follow the
paper: cut k = layers 0..k on the upstream device; k = -1 is the camera frame. Tensors cross as
INT8 + zstd-1 (per-tensor symmetric) or FP16; the camera frame as JPEG Q90.

Checks before measuring:
- The weights are identical on all devices (same SHA-256).
- The Jetson's CUDA build has no native sm_87 code (it runs the sm_80 binaries). Its detections
  match the CPU on 10 images, box coordinates within 0.02 px.
- On GPUs, every one of the 276 segments (a, b] was timed directly, because summed per-layer times
  over-count launch overhead. On the Pi, per-layer sums match timed segments within 1% at the same
  thermal state.

## 2. Devices

| | Full model | Layers 0-4 (k4 prefix) | k4 INT8+zstd encode | Pre / NMS | Board power idle -> active | Inference energy (active - idle) |
|---|---|---|---|---|---|---|
| Pi 5, cool start | 576 ms | 210 ms | 11 ms | 3.6 / 1.7 ms | 2.6 -> 4.8 W (PMIC rails) | 1.3 J/frame |
| Pi 5, sustained (throttled to 1.5 GHz, 85-89 C, flags 0xe0006) | **758 ms** | 252 ms | 11 ms | 3.7 / 2.2 ms | 2.0 -> 4.7 W | **2.0 J/frame** |
| Pi 5, 1 thread | 950 ms | 325 ms | 10 ms | | | |
| Jetson Orin Nano GPU FP16 | **22.7 ms** | 7.4 ms | 6.1 ms | 2.4 / 9.6 ms | 3.2 -> 10.5 W (INA3221 VDD_IN) | 0.17 J/frame |
| Jetson Orin Nano GPU FP32 | 41.7 ms | 13.0 ms | 8.7 ms | 4.4 / 9.5 ms | 3.3 -> 9.7 W | 0.27 J/frame |
| Laptop RTX 4050 FP16 | 5.5 ms | 1.0 ms | 2.0 ms | 1.5 / 3.3 ms | 2.7 -> 49 W (GPU only) | |

- **Payload sizes, measured on every device (identical everywhere):**
  - JPEG Q90 frame: 84-87 KB.
  - k4 INT8+zstd: 315 KB.
  - k9 INT8+zstd (three tensors): 546 KB.
  - k4 FP16: 1.64 MB.
- **Pi radio:** its Wi-Fi rail rises from 0.08 W to 0.40 W while transmitting (+0.31 W). The
  compute rails rise by +2.7 W during inference.
- **Pi power caveat:** the PMIC rail sum excludes 5 V conversion losses and USB peripherals, so the
  Pi powers are lower bounds.

## 3. Links (TCP, application-level frame transfer, n = 20-30 per size)

| Link | RTT | Bulk goodput | JPEG 85 KB | k4 INT8 315 KB | k4 FP16 1.64 MB |
|---|---|---|---|---|---|
| Pi -> laptop (first) | 4.9 ms | 30.0 Mbit/s | 25 ms | 84 ms | 430 ms |
| Pi -> laptop (5 h later) | 4.2-9.2 ms | 21 Mbit/s | 58-77 ms | 121-145 ms | 650-687 ms |
| Pi -> Jetson | 2.7 ms | 13.3 Mbit/s | 72 ms | 224 ms | 1231 ms |
| Jetson -> laptop | 4.0 ms | 18.5 Mbit/s | 43 ms | 161 ms | 535 ms |

## 4. Accuracy (COCO val2017, 5,000 images, paired bootstrap 95 % CI vs FP32, mAP@[.5:.95] points)

| Boundary encodings | Change in mAP |
|---|---|
| INT8 at one cut (k = 2...18, from the paper) | -0.05 to +0.02 |
| JPEG Q90 camera frame | about -0.33 |
| JPEG Q90 then INT8 at k4, k9 or k15 (two hops) | -0.32 to -0.35 (CI about +/-0.13) |
| INT8 then INT8 (pairs (2,9), (4,9), (4,15), (4,18), (9,15), (9,18)) | -0.04 to +0.01 |
| INT8 then FP16 (pairs (4,9), (4,15), (9,15)) | -0.03 to -0.01 |

Quantizing twice costs no measurable accuracy. Only JPEG has a visible cost, about one third of a
point.

## 5. Live distributed pipelines

Each run is 60 s with a 30 fps camera on the capturing device. One frame at a time is on each link
and stale frames are dropped (newest wins). Detections are sent back to the camera, so latency is
capture-to-result on one clock. Repetitions were interleaved over about 4 h, and Wi-Fi quality
changed during that time; on-time means latency of at most 300 ms.

| Placement | Runs | Frames/s, median [min, max] | On-time frames/s, median [min, max] | Latency p50 / p95 (ms) |
|---|---|---|---|---|
| **Jetson GPU alone** (camera on the Jetson) | 3 | **18.45** [18.45, 18.45] | **18.45** | **35 / 61** |
| **Pi JPEG -> laptop** | 4 | 15.2 [11.6, 25.9] | 14.7 [11.1, 25.8] | 107 / 232 |
| Pi JPEG -> Jetson | 3 | 10.9 [7.7, 20.6] | 10.1 [6.4, 20.5] | 150 / 340 |
| Jetson JPEG -> laptop (camera on the Jetson) | 3 | 9.0 [5.7, 20.0] | 8.1 [4.4, 19.8] | 139 / 370 |
| Pi k1 INT8 -> laptop (best split per the model) | 1 | 7.0 | 2.5 | 324 / 467 |
| Pi k4 INT8 -> laptop | 3 | 4.2 [4.0, 4.2] | 0.0 | 419 / 644 |
| Pi k2 INT8 -> laptop | 1 | 2.9 | 0.0 | 688 / 1099 |
| Pi k4 INT8 -> Jetson (the PDF's "mothership") | 3 | 2.7 [2.7, 4.2] | 0.0 | 691 / 1150 |
| Pi JPEG -> Jetson relay -> laptop | 3 | 3.4 [3.3, 6.3] | 0.5 [0.4, 2.5] | 570 / 1278 |
| Pi JPEG -> Jetson k9 INT8 -> laptop (two-hop split) | 1 | 2.3 | 0.0 | 801 / 1965 |
| Pi k4 INT8 -> Jetson k9 INT8 -> laptop (two-hop split) | 1 | 2.1 | 0.0 | 1413 / 1982 |
| Pi 5 CPU alone | 3 | 1.6 [1.55, 1.63] | 0.0 | 589 / 656 |

The composition model (`placement.py`) enumerates all 1,150 placements. For the 9 one- and two-device
placements that ran live, its frame rate is 0.8-2.0x the live median (Pi JPEG -> laptop: 30.0 predicted
against 15.2 live), and it ranks every image-offload placement from the Pi above every split placement
from the Pi, as the live runs do; the order among the other placements differs. For the 3 three-device
chains it is 1.6-4.2x too optimistic, because both Wi-Fi hops share one channel; the live runs are the
reference there. (Corrected 9 Nov 2026; computed by `evaluation/placement_model_check.py`, output
`experiments/results/hardware/placement_model_check.json`. The earlier text said "within about 30 %
and ranks them in the same order", which the result files do not support.)

## 6. Conclusions

1. **Splitting YOLOv8s never wins.**
   - JPEG offload beats every split on every link and in every repetition. Against the best split
     (k1 to the laptop), it delivered about 2x the frames and about 5x the on-time frames
     (13.6 vs 7.0, and 13.0 vs 2.5 per s, in the same period).
   - A k4 split never met a 300 ms deadline on any device pair.
   - The reasons:
     - the Pi needs 210-250 ms just for layers 0-4;
     - the 315 KB k4 tensor is 3.7x a Q90 JPEG;
     - the JPEG costs the Pi only 4 ms to encode.
   - This confirms the paper's main result on real hardware.
2. **The three-tier "sense -> edge -> cloud" architecture is the worst networked option measured.**
   - Splitting the network twice: 2.1-2.3 frames/s and 0.8-1.4 s latency.
   - Even relaying the JPEG unchanged through the Jetson cuts Pi -> laptop throughput from 15 to
     3.4 frames/s.
   - The cause is that every additional hop competes for the same Wi-Fi airtime.
   - A three-tier design could only pay off with separate radio channels for the A2A and
     air-to-ground links. That is untested here, and is a prerequisite, not a given.
3. **If a mothership Jetson is used, send it the JPEG, not features.** Pi JPEG -> Jetson reached
   10.9 frames/s (all on time), against 2.7 frames/s for Pi k4 -> Jetson.
4. **The best single configuration is YOLOv8s on the Jetson GPU next to the camera**:
   - 18.45 frames/s with 35 ms latency, identical in all three runs;
   - no network dependence, and no JPEG accuracy loss.
   - Its frame rate is set by the 30 fps camera: 22.7 ms of inference plus 9.6 ms of NMS just
     misses every other frame.
   - Its cost is weight and power, about 7 W more under load. Its mass and the resulting flight-time
     penalty were not measured here.
5. **On a Pi-class drone, offload the JPEG to the most capable reachable GPU**, laptop or Jetson,
   and fall back to onboard inference only when no link exists.
   - Onboard inference on the Pi gives 1.6 frames/s at 0.6-0.76 s latency and about 2 J per frame.
   - Sending the JPEG costs about 4 ms of compute and about 10-25 mJ of radio energy per frame.
6. **Thermal behaviour matters.** Without a cooler, the Pi 5 throttles to 1.5 GHz and runs YOLOv8s
   30 % slower (576 -> 758 ms). Any onboard-inference claim should state the cooling.

## 7. Corrections to "Hardware Testing.pdf"

| PDF claim | Measured |
|---|---|
| Pi 5 t_full 786 ms | 576 ms cool, 758 ms throttled, 950 ms with 1 thread (ultralytics caps torch at 1 thread unless reset) |
| JPEG 359 KiB per frame | 84-87 KB at Q90, 640x640 |
| A2A link "measured" 59.66 Mbit/s | 59.66 is the simulator's model value at 50 m; the measured Pi -> Jetson link is 13.3 Mbit/s |
| JPEG -> cloud 38.8 ms, 57.8 frames/s over a 17 Mbit/s link | Impossible at 17 Mbit/s; measured 107 ms p50 and 15 frames/s (best run 25.9) |
| Pi k4 -> Jetson 497.7 ms, three-tier "hierarchical" best | 691 ms p50, 2.7 frames/s, never on time; JPEG -> Jetson is 4x better |
| Double INT8 loses 3.81 dB SQNR, so FP16 is needed at the second hop | No accuracy loss: INT8 -> INT8 changes mAP by -0.04 to +0.01 points |
| Jetson 41.3 ms | Confirmed for FP32 (41.7 ms); FP16 is 22.7 ms |
| Adaptive mission: 96.8 % deadline compliance, +42.6 % endurance | Not reproducible; it is a scripted scenario, and its onboard power (60.75 W) assumes 10 frames/s on a 1.3 frames/s device |
