# What is measured, what is validated, what is assumed

Every number in the paper is produced by code from result files (`docs/claims_*.md` trace each one
to its source). "Produced by code" is not the same as "true of the real world": a simulation output is
only as good as its inputs. This file lists every input of the study and its status.

Status legend:
- **Measured**: obtained from real data or real hardware in this repository.
- **Validated (ns-3)**: compared against the independent ns-3.48 simulator (`validation/`).
- **Validated (OMNeT++)**: compared against OMNeT++ 6.3 with INET 4.5.4 / Simu5G 1.6.0 (section 5).
- **Validated (real stack)**: compared against the real Linux TCP stack with real frames and models (section 6).
- **Proved / tested**: mathematical statement proved and checked by `scripts/verify_math_proofs.py` and tests.
- **Assumption**: a chosen value. Its effect is bounded by a sweep or Monte Carlo where noted, but it is
  not checked against reality.

## 1. Perception (measured; no network simulator involved)

| Quantity | Status | Evidence |
|---|---|---|
| Split exactness at every cut (19 detectors, 432 cuts) | Measured + tested | `tests/test_submodels.py`, `gen_model_survey.py` |
| Accuracy (mAP) of every split, bit width, codec | Measured | COCO val2017 (5,000 images), VisDrone val (548) |
| Payload and codec sizes | Measured | real packets / encoded files on real frames |
| Per-stage compute times on the server side | Measured | RTX 4050 Laptop GPU, 200 frames |
| Quantization error bound S/2 | Proved + tested | Proposition 1, `tests/test_quantizer.py` |

These do not need OMNeT++ or ns-3: they are not network quantities.

## 2. Onboard hardware and energy (assumptions; network simulators cannot check them)

| Quantity | Value | Status | How its effect is bounded |
|---|---|---|---|
| Onboard full-model latency t_full | 40, 90, 180, 360 ms | Assumption | swept; 10-1000 ms in the Monte Carlo |
| Other onboard work scales like the DNN | t_full / 11.93 ms | Assumption | conservative for JPEG (hardware encoders are faster) |
| Compute power busy / idle | 10 / 2 W | Assumption (Jetson Nano 10 W mode) | 5-30 / 1-4 W in the Monte Carlo; Proposition 5 |
| Modem transmit / idle | 3.8 / 1.2 W | Assumption | 1.5-6 / 0.5-1.5 W in the Monte Carlo |
| A2A radio | 1.5 W | Assumption | - |
| Hover power | 109.9 W | Model (momentum theory: 1.2 kg, 0.2 m^2, FoM 0.7, eta 0.75) | mass 0.25-5 kg in the Monte Carlo |
| Battery / avionics | 55.5 Wh / 15 W | Assumption | 3-20 W avionics in the Monte Carlo |

Only measurements on a real UAV computer (e.g. a Jetson) can validate this section.

## 3. Application and policy (design choices)

| Quantity | Value | Status |
|---|---|---|
| Deadline / camera rate | 300 ms / 30 FPS | Choice; 100-1000 ms, 10-60 FPS in the Monte Carlo |
| Policy: EWMA 200 ms, sigma floor 0.1 mu, hysteresis 5 %, energy weight 0.05, assumed delay 20 ms | - | Choice; varied in the Monte Carlo (|rho| <= 0.12) |

## 4. Network (the part network simulators can validate)

| Model element | Value in code | Status |
|---|---|---|
| SINR process: mean + Gudmundson shadowing + Rician fading (Clarke/Jakes) + blackouts | per profile (Section 3.4 of the paper) | **Statistically validated (C1)** against theory: K-factor 8.99/3.03/0.10 dB for 9/3/0 dB, unit mean power, Clarke autocorrelation error <= 0.012, shadowing std 4.01 dB for 4 dB and correlation 0.825/0.362/0.130 vs 0.819/0.368/0.135 at 6/30/60 m, blackout depth 40 dB (`tests/test_channel_statistics.py`, `validation/run_channel_statistics.py` -> `experiments/results/validation/channel_statistics.json`). The profile values themselves (mean SINR etc.) remain **assumptions**. |
| SINR to rate (3GPP TR 36.942: alpha 0.4, 2 bit/s/Hz, -10 dB) | `trace_generator.py` | **Validated (ns-3 LTE, V2)**: pessimistic above ~21 dB, 1.1-2.8x optimistic up to ~15 dB; conclusions re-checked with the ns-3 curve |
| One-way delay: base + 10 ms x (1 - load) + exponential jitter (mean 2 ms) | `trace_generator.py` | **Assumption** |
| Residual loss: 0.1 exp(-(SINR+10)/3), <= 5 %, 100 % in outage | `trace_generator.py` | **Assumption** |
| Fluid transmission, newest-frame-wins, deadline aborts | `stream_sim.py` | **Validated (ns-3, V3/V4; real stack, V5)**: real TCP, r = 0.98, our model never below ns-3; over the real Linux stack within 0.9 frames/s in 6 settings with the same uplink-release rule |
| Cell sharing by water-filling | `stream_sim.py` | **Validated (ns-3, V3; Simu5G O2/O2b)**: mean share and mixed-demand allocation exact; with >= 10 saturated UAVs Simu5G's PF scheduler serves 7 and starves the rest. **Sensitivity** (`run_sharing_sensitivity.py`): with that capped sharing or persistent unequal shares, JPEG >= split and adaptive best at every swarm size; adaptive per-UAV throughput at N = 20 drops from 16.6 to 11.7-14.1 frames/s and some UAVs get 0; relay gain <= 0.55 frames/s |
| A2A 802.11ax link (path loss n = 2.2, shadowing 3 dB, MCS table, PER, MAC 0.65) | `stream_sim.py` | **Validated (ns-3 Wi-Fi, V1; INET, O4)**: goodput 1.4-3.2x conservative vs. ns-3; the range of every MCS equals INET's in 7 of 9 MCSs and is one grid step away in the other 2 (ns-3 reaches further for 8 of 9); conclusions re-checked with the ns-3 curve |
| Relaying decision and two-hop forwarding | `stream_sim.py` | **Validated (ns-3, O5)**: conservative. The A2A hop is 1.3-2.6x and the whole relay path 1.3-3.1x faster in ns-3 (TCP, 802.11ax, packet forwarding) than modelled; deadline verdicts agree in 7 of 12 cases, every disagreement in the conservative direction. Re-running the swarm grid with packet forwarding (`relay_forwarding="packet"`) and ns-3 A2A rates: relay gain at most 0.43 frames/s, at most 2.6 % of relayed split frames on time (paper model: 0.41, 1.6 %). The *decision rule* (thresholds 5 / 15 Mbit/s) remains a design choice. |
| A2A interference, UAV motion | not modelled | **Assumption** (stated as limitations) |

## 5. OMNeT++ 6.3 / INET 4.5.4 / Simu5G 1.6.0 validation (`validation/omnetpp/`, `run_omnetpp_validation.py`)

| Check | Result | Status |
|---|---|---|
| O1: 5G-NR uplink goodput vs. SINR (20 MHz, 3.5 GHz) | 92 Mbit/s peak (TR 36.942 caps at 40); 35.6 / 15.1 / 7.0 Mbit/s at 17 / 10 / 5 dB vs. 40 / 27.7 / 16.5 from TR 36.942; no data below about -2 dB. Agrees with ns-3 LTE (V2) within about 10-40 %. | **Done**: confirms V2 independently. The TR 36.942 mapping is pessimistic at high SINR and 1.9-2.4x optimistic at 5-10 dB. |
| O2: N saturated UAVs, one gNB, proportional-fair uplink scheduler | Cell goodput 115.7 Mbit/s for N >= 2 (91.8 for one UAV, which is power-limited); per-UAV share exactly C/N for N = 2, 5 (Jain 1.0). For N = 10, 20 the PF scheduler serves 7 UAVs at 16.5 Mbit/s and starves the rest (Jain 0.70, 0.35); MAX-C/I serves all, unequally. Identical in Simu5G 1.5.2 and 1.6.0. | **Done**: mean share C/N confirmed; the *distribution* among many saturated UAVs depends on the scheduler, and is less fair than water-filling for N >= 10 |
| O2b: 5 light (1/2/4 Mbit/s) + 5 saturated UAVs | light UAVs get exactly their demand; saturated get 22.13/21.13/19.13 vs. water-filling 22.14/21.14/19.14 Mbit/s | **Done**: water-filling confirmed |
| O3: frame streaming over the full 5G stack | Simu5G's uplink does not carry large bursts after idle periods reliably: with RLC UM, bursts of more than ~50 datagrams lose segments at reassembly (every 93 KB frame incomplete); with RLC AM (1.5.2 crashes; 1.6.0 runs), frames take ~400-530 ms. Steady traffic is unaffected (O1, O2). | **Not usable yet**: simulator behaviour for bursts, still being investigated |
| O4: INET 802.11ac A2A, every MCS vs. distance (`run_omnetpp_a2a.py`) | INET has no 802.11ax, and its DCF does not aggregate, so INET and ns-3 both run 802.11ac, VHT MCS 0-8, no aggregation. Range of each MCS (normalised goodput >= 0.5): INET = Python model in 7 of 9 MCSs, one grid step apart in 2; mean normalised difference 0.024 (INET-Python), 0.118 (ns-3-Python). ns-3's error model reaches about one step further (e.g. MCS 8: 100 m vs. 50 m). All three reach 700 m at MCS 0. INET's MAC delivers 0.73-0.92x ns-3's goodput at 10 m. | **Done**: the Python PHY thresholds match INET's NIST error model and are conservative against ns-3 |
| O5: relaying over two hops (ns-3 `relay.cc`, `run_relay_validation.py`) | A -> 802.11ax (IdealWifiManager, aggregation) -> B -> 20 Mbit/s, 20 ms uplink (FQ-CoDel) -> server, TCP, frames sent back to back. Hop 1: 7-181 ms for JPEG/split at 25-600 m, 1.3-2.6x faster than the Python model. Whole path: 42-268 ms, 1.3-3.1x faster (partly because ns-3 forwards packets as they arrive). A split frame relayed via a UAV that also sends its own frames takes 260-268 ms on average (p95 306-352 ms) against the 300 ms deadline. | **Done** (in ns-3; INET has no 802.11ax) |

Notes: Simu5G 1.6.0 exhausts memory when saturated UAVs offer far more than their share at N >= 10, so the
offered load is max(20, 150/N) Mbit/s per UAV (still saturating) and every run has a 4 GB memory cap.
The raw 1.5.2 results are kept in `experiments/results/validation/simu5g_1.5.2/`.

## 6. Real network stack (V5, `validation/run_emulation.py`)

Real COCO frames, the real codecs (INT8 + zstd split packets in the authenticated wire format, JPEG
Q90), the real server-side models on the GPU, real Linux TCP over loopback, shaped by `tc netem`
(5 / 15 / 40 Mbit/s, 20 ms one-way delay). The UAV side runs the simulator's frame logic with the
onboard time padded to the model's value (t_full = 180 ms).

| Config | Link | Simulator (same release rule) | Emulation | Simulator without waiting for the result |
|---|---|---|---|---|
| Split k4 INT8+zstd | 5 Mbit/s | 0.00 | 0.00 | 0.00 |
| Split k4 INT8+zstd | 15 Mbit/s | 0.03 | 0.40 | 1.50 |
| Split k4 INT8+zstd | 40 Mbit/s | 9.27 | 8.40 | 9.97 |
| JPEG Q90 | 5 Mbit/s | 4.23 | 4.17 | 5.00 |
| JPEG Q90 | 15 Mbit/s | 9.50 | 10.27 | 14.97 |
| JPEG Q90 | 40 Mbit/s | 15.00 | 14.97 | 29.97 |

On-time frames/s; largest difference 0.9 frames/s. The emulated UAV sends the next frame only after all
bytes are acknowledged and the server has returned the result (about two one-way delays per frame);
the simulator reproduces this with `release_extra_ms = 2 x delay`. That rule halves JPEG throughput
at 40 Mbit/s, so the paper's simulator (which releases the link when the last byte is sent) assumes a
pipelined sender. **Status: validated** for the frame logic, codecs and transport on a constant link;
it is not a radio or flight measurement.

## 7. What remains an assumption

- Onboard speed, power and hover model (section 2): only hardware measurements can validate them.
- The channel profiles' mean SINR, speeds, blackout times, delay and loss formulas: synthetic, checked
  only for internal statistics (C1); measured aerial traces can replace them.
- The adaptive policy's parameters and the relay decision thresholds: design choices (varied in the
  Monte Carlo).
- A2A interference between concurrent transmissions and UAV motion: not modelled (both would make relaying
  less effective than modelled).
- Frame streaming over a full 5G stack (O3): Simu5G does not carry large bursts reliably, so this is
  checked in ns-3 and over the real stack only.

