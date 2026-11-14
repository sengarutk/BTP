# Everything to do on the mesh (14 Nov 2026)

## Sources

- Results Brief: Part 19 (19.8-19.23), Part 23 ("What is left") and Parts 17, 18 and 20.
- `docs/board_session_predictions_nov.md`, `docs/novelty_roadmap_nov11.md`, `docs/laptop_tasks_nov11.md`.
- Decisions made in the 12-14 Nov chat.

## Testbed (verified 14 Nov)

All drones are reached as `ssh -J dubey@10.230.3.10`.

| Role | Board | Mesh address | Access |
|---|---|---|---|
| Ground radio | pi-sender (`dubey`) | 10.1.0.12 | Cabled to the laptop (eth0 10.230.3.10/20); the laptop's entry to the mesh |
| Sense drone S1 | pi-relayyy (`sengar`) | 10.1.0.11 | Through pi-sender |
| Sense drone S2 | pi-receiver (`sengar`) | 10.1.0.13 | Through pi-sender |
| Edge drone E1 | Nano1 (`nano`) | 10.1.0.14 | Through pi-sender |
| Edge drone E2 | Nano2 (`nano2`) | 10.1.0.15 | Through pi-sender; Jetson Orin Nano Super, BATMAN-adv 2026.4 |

Status codes:
- **R**: ready (code and predictions exist).
- **C**: needs code first.
- **P**: needs predictions written and committed first.
- **D**: needs a decision by the user.
- **H**: needs extra hardware.

Every campaign follows the standing rules:
- predictions are committed before the runs;
- no change to the mesh configuration;
- temporary `tc`/`nft` rules are removed afterwards;
- at most 6 heavy processes;
- results are never deleted (move them to `_superseded/`);
- passwords only through environment variables.

## A. Setup before any test

| ID | Task | Why | Status |
|---|---|---|---|
| A1 | Update `tools/mesh_ssh.sh`, `mesh_scp.sh`, `mesh_tunnel.sh`, `mesh_askpass.sh`, `push_code_mesh.sh`, `arun_mesh.sh` and `campaign_mesh*.sh` to the new map. Old map: pi-sender .11, camera pi-relayyy .12, Jetson .13. New map: above. Add pi-receiver and Nano2 as targets. | Every script still points to the 23 Oct addresses | C |
| A2 | Install the camera stack on pi-receiver: Python environment, ultralytics, VisDrone weights, `adaptive2.py`, forecaster, power and thermal logging, the camera stream (VisDrone-VID replay). Check that the stream matches pi-relayyy's. | It has never run a campaign | C |
| A3 | Install the edge stack on Nano2: `edge_node.py`, the worker, VisDrone weights, the FP16 engine, `jetson_clocks`, its power logging (INA / tegrastats). Check its server times. Nano2 is an Orin Nano **Super**, likely faster than Nano1, so its timing priors must be measured. | It has never served frames | C |
| A4 | Push the current code to every board (`push_code_mesh.sh`). The camera Pis must get the per-frame `pred` logging (19.8, item 4) and the `multihop_loss2/5` scenarios. Compare md5 sums of `adaptive2.py`, `edge_node.py` and `energy_constants.json` across boards and against the repository. | 19.8 says the logging "must be pushed before the next campaign"; the board-side constants were never compared | R |
| A5 | Per-board energy and thermal profiles: pi-receiver (idle, inference J, radio, thermal fit a, b, τ) and Nano2 (idle W, J per inference per model). | The prices and the guard theorem use per-board constants; pi-receiver and Nano2 have none | C |
| A6 | Health check (`dryrun_board_session.sh` adapted to five boards): mesh neighbours, `jetson_clocks`, Pi power save off, Pi clock/throttle flags, free disk, time sync (chrony), the laptop keep-awake ping for the Ethernet energy-saving problem. | — | C |
| A7 | **Decision:** make pi-sender's Ethernet address 10.230.3.10 permanent (it is temporary now)? | Access is lost if pi-sender reboots | D |
| A8 | **Decision:** a Layer-2 bridge on pi-sender (eth0 + bat0) so the laptop gets its own mesh address, instead of SSH tunnels that acknowledge data early (a stated limitation). This changes pi-sender's network configuration. | Removes a measurement artefact; old campaigns used tunnels (comparability) | D |
| A9 | **Decision:** make Nano2's mesh setup permanent? It is runtime-only now; after a reboot someone must run `sudo ~/aegisswarm_up.sh`. | It no longer has a cable | D |
| A10 | Extend `adaptive2.py` from one Jetson path to several edge drones (E1, E2) plus the ground, and `edge_node.py` to serve several cameras with its newest-frame queue. | All two-edge tests below need it | C |

## B. The prepared board session (19.23; predictions committed 10-11 Nov)

| ID | Campaign | Claim it tests | Status | Time |
|---|---|---|---|---|
| B1 | Planner campaign: v4.1 against the AccuMO-style planner against the LEAF-style weight. `REPS=2 tools/campaign_mesh4.sh`; static_good, mesh_mission, multihop; 18 runs. | "A greedy priced choice does as well as a 30-frame planner" (19.10-19.11; replay only so far). Predictions P1.1-P1.2. | R (after A1/A4) | ~2 h |
| B2 | Energy test: the energy price on and off, paths fixed (`campaign_energy_nov.sh`); v41, freshonly, v41b36; 12 runs. Also Part 23's "ablation of the energy mechanism". | Theorem 1 on fresh runs, the budget-temperature proposition, the mechanism (the price prevents throttling). P2.1-P2.4. | R | ~1.5 h |
| B3 | Noisy relay (`campaign_relaynoise_nov.sh`): multihop with 2 % / 5 % loss; v41, hier, fixed laptop; 12 runs. | The order hier ≥ v41 > fixed laptop holds under relay noise. P3.1-P3.3. | R | ~1.5 h |
| B4 | Hardware calibration of the deadline probabilities (`calib_hw.py`) on the `pred` logs of B1-B3. Also recompute v4.1's per-frame decisions from their logged inputs. | 19.8 and 19.20: calibration and decisions have so far been checked only in the replay | R | no extra runs |

## C. Paper 2: strengthen the core claims

| ID | Test | Claim | Status | Time |
|---|---|---|---|---|
| C1 | **Capped hold** (hold only below 78 °C) against v4.1 on 24-minute missions with blackouts, ≥ 5 runs each | The heat left on long missions (19-27 % ≥ 80 °C) comes from the blackout hold; capping it removes the heat at the same sAP (19.21; replay only) | C (port `hold_max_c` from the replay) + P | ~5 h |
| C2 | **Hard guard** (Theorem 3: no onboard inference starts ≥ 78 °C) on 24-minute missions; peak against the 79.9 °C bound | Theorem 3 (b) on hardware (replay only so far) | C + P | ~2.5 h |
| C3 | **Airflow** (P2-2): a bench fan at 2-3 speeds over the camera Pi. Refit b(airflow); rerun the throttling cost (onboard sAP at full against throttled clock) and v4.1 against no prices | The most dangerous reviewer question: does the heat cost survive propeller wash? | P (+ a fan) | ~0.5-1 day |
| C4 | **Room-following budget + higher price cap**; a warmer room made with an enclosure or heater (optional, if a controlled warm room is possible) | 19.21: 0 % hot at +5 / +10 °C (replay extrapolation) | C + P + H (warm box) | ~0.5 day |
| C5 | 5 repetitions of the headline mesh comparisons and the 24-minute missions (Part 23) | More statistical power; mesh cells had 3 reps | R | ~1 day |
| C6 | Topology reversal in **one** campaign: direct and forced multihop, v4.1 and the hierarchical chain, 5 reps (Part 23; Part 20 §7) | "The topology decides the architecture" (now from two campaigns a day apart, 3 pairs) | R (`campaign_mesh*.sh` variant) + P | ~4 h |
| C7 | Relay follow-up: 5 reps per scenario; v4.1's good-link ranking and the ground-congested drop (Part 23, Part 18) | Settles open relay results | R + P | ~3 h |
| C8 | Clock governor "performance" against the default (19.14), 2 scenarios × 3 runs | "Keep the default governor" (now a model estimate) | R + P | ~1 h |

## D. Paper 2: new novelty to add and test

| ID | Item | Status | Time |
|---|---|---|---|
| D1 | **Two edge drones:** v4.1 choosing among E1, E2 and the ground (needs A10). The edge drones differ (Orin Nano against Orin Nano Super), so this is heterogeneous edge selection. | C + P | ~0.5 day |
| D2 | **v4.1+:** v4.1 with the capped hold, the room-following budget, contention-aware latency (onboard inference slows offloads by 6-14 ms, L7) and YOLO11n allowed onboard; against v4.1 on the mission, random faults and 24 minutes | C + P | ~0.5 day |
| D3 | **Encode ahead** (19.13): keep the newest frame encoded and send it the moment the radio frees; one camera, against v4.1. Model: up to +40 % on-time results on Wi-Fi, +14 % on the mesh | C + P | ~2 h |
| D4 | **Better detector choices inside v4.1:** YOLO11n onboard, YOLO11m on the ground (Part 17.7: YOLO11n gives 2.7× YOLOv8s's onboard sAP; YOLO11m +6 % mAP over YOLOv8m) | C (variants and accuracy tables) + P | ~2 h |
| D5 | **DVFS as a third knob** (P2-5): per-frequency power and latency of the Pi (1.5 / 1.8 / 2.1 / 2.4 GHz); then a frequency-aware price in the replay and on the board | measurements R; controller C | 1 h board + 2 days laptop |
| D6 | **Joint fades / co-channel interference** (19.9): how often both paths fade together on the real shared channel; the replay predicts 0.002-0.006 sAP | P + H (traffic source) | ~0.5 day |
| D7 | **Cheaper camera-motion step** (19.9): forecaster at 160 px; the Pi's step time and the onboard speed-up (`campaign_ego160.sh`, 12 runs) | R + P | ~1.5 h |

## E. Many drones (19.13; model only so far)

| ID | Test | Model prediction (19.13) | Status | Time |
|---|---|---|---|---|
| E1 | One sense Pi at 30 fps: naive queue against v4.1 | Naive: 0 on time; v4.1 flat latency | C (naive mode) + P | ~30 min |
| E2 | **Two sense Pis on one Jetson**, v4.1; each Pi's temperature and onboard share logged | Within capacity; the overload → onboard → heat link is reasoned, not measured | R (after A2) + P | ~1 h |
| E3 | **Pull-one-ahead coordinator** on the Jetson (grant the newest frame when the GPU can take it, one ahead), against v4.1 with 2 Pis | Model: at capacity with any number of Pis; freshest detections | C (protocol in `edge_node.py` + camera) + P | ~0.5 day |
| E4 | **2 Pis + 2 Jetsons on one shared channel:** fixed assignment, load-aware sending, global pull | Model: more than 2 Jetsons add nothing on one channel; Pi-side load balancing backfires; global pull best | C + P | ~0.5 day |
| E5 | Sense drones' own cameras (the Jetsons as cameras, as in the 18.x two-camera test) for 3-4 camera streams | Coordinator matters from about 3-5 cameras per Jetson | C + P | ~0.5 day |
| E6 | Jetson heat under sustained 2-camera load (not modelled) | — | R (logging) | with E2 |
| E7 | Separate channels per Jetson group | Model: capacity grows with each Jetson | **D + H:** needs a mesh-config change and two-radio gateways; not allowed under the no-mesh-change rule without the user's decision | — |
| E8 | Swarm-coordinator check (Part 13 admission control with link health) with 2 sense Pis | Part 13: the coordinator rarely acted with 2 cameras | R (`campaign_swarm.sh`, update) + P | ~2 h |

## F. Paper 1 on the boards

| ID | Test | Why | Status | Time |
|---|---|---|---|---|
| F1 | **Predict-then-measure the break-even goodput:** the Pi with the smallest code against JPEG. Shape the Pi's link rate with `tc` on the boards (temporary, removed afterwards). Predict the crossover from B_be before measuring. | Turns the rule from model-checked into hardware-confirmed (P1-5; the strongest open objection) | C + P | ~0.5 day |
| F2 | Pi encode times: x264/x265 low-delay on the Pi 5 (no hardware H.264 encoder) | Replaces the scaled encode times of 19.19 | R (script) | ~1 h |
| F3 | Onboard times of the learned codes' encoders and the YOLO11s prefix on the Pi and Jetson | 19.19 scales YOLO11s device times from YOLOv8s | C (small) | ~1 h |
| F4 | Optional: Pi 5 + Hailo-8 (P1-7), a fast drone-class board where the camera rate binds | Tests the fading rule where the constant rule failed | H (purchase) | ~1 day |

## G. Longer term

| ID | Item | Status |
|---|---|---|
| G1 | Outdoor or tethered flight with real distances (P2-10): what top venues value most | H |
| G2 | BATMAN-adv overhead against raw IBSS (latency and throughput with and without bat0): characterises a stated limitation | P |
| G3 | Nano2 BATMAN-adv: rebuild after any kernel update (module in `updates/`); optionally DKMS | — |

## H. After each block of runs

- Write held / did-not-hold lines in the predictions files.
- Run `theory_check.py`, `price_rules_check.py` and `price_input_checks.py` on the new runs.
- Update the Results Brief (new 19.x / Part 18 sections), the Final Report, the Novelty Brief and both papers.
- Rewrite and audit the papers last.

## Suggested order

1. A1-A6, A10, and the decisions A7-A9.
2. B1-B4: ready, predictions committed.
3. C1-C3: the paper-2 critical tests (capped hold, guard, airflow).
4. E2-E3 and D1: two sense drones, two edge drones.
5. F1-F3.
6. C4-C8, D2-D7, E4-E8.
7. G1 when possible.

Rough total: about 2 days of setup and code, 4-6 board days, 3-5 laptop days of analysis and write-up.
