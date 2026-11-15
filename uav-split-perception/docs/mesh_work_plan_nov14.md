# Mesh work plan (14 Nov 2026; trimmed plan agreed in the chat, status updated 14 Nov 23:15 IST)

Sources: Results Brief Part 19 (19.8-19.23), Part 23, Parts 17, 18 and 20; `docs/board_session_predictions_nov.md`,
`docs/novelty_roadmap_nov11.md`. The first, longer version of this plan (items A-H) is in this file's git history
(commit e84ce5dc). Session record: `docs/mesh_session_nov14.md`. Predictions: `docs/board_session_predictions_nov.md`
(T1-T3) and `docs/mesh_predictions_nov14.md` (T4, T6, T7, T9).

## Testbed (verified 14 Nov; map in `validation/hardware/tools/mesh_hosts.sh`)

| Role | Board | Mesh address | Notes |
|---|---|---|---|
| Ground radio | pi-sender (`dubey`) | 10.1.0.12 | cable to the laptop, eth0 10.230.3.10 (temporary) |
| Sense drone S1 | pi-relayyy (`sengar`) | 10.1.0.11 | the camera of every campaign |
| Sense drone S2 | pi-receiver (`sengar`) | 10.1.0.13 | **off the mesh since ~21:46 14 Nov; needs a physical check** |
| Edge drone E1 | Nano1 (`nano`) | 10.1.0.14 | Orin Nano, 15 W mode |
| Edge drone E2 | Nano2 (`nano2`) | 10.1.0.15 | Orin Nano Super, 25 W mode; mesh runtime-only |

Rules: predictions committed before runs; no change to the mesh configuration; temporary nft/tc rules removed; results
never deleted (archived in `_superseded/` with the reason); passwords only in environment variables; the laptop on its
charger during campaigns.

## Setup and code

| ID | Item | Status |
|---|---|---|
| S1 | Mesh scripts for five boards (`mesh_hosts.sh`, ssh/scp/tunnel/askpass, push with md5 check, health check, multihop relay kept on Nano1) | done, tested live |
| S2 | pi-receiver camera stack, Nano2 edge stack, code pushed, md5 equal on all four drones | done |
| S3 | Profiles of pi-receiver and Nano2 | energy profiles done (no radio states); pi-receiver's steady-state levels interrupted when it dropped off; radio states pending |
| S4 | v4.1 with two edge drones (`jetson2` path, own netem band, power log, `--jetson2-m`), frame destinations logged | code done; board test pending |
| S5 | Capped hold `--hold-max-c`, hard guard `--guard-hard-c` | code done; board test pending |
| S6 | Pull-one-ahead coordinator | not started (needs `adaptive.py`, in use by tonight's campaigns; model: no effect with 2 Pis, needs ~6 streams) |
| S7 | Encode ahead `--encode-ahead` | code done; board test pending |

## Tests

| ID | Test | Script / predictions | Status |
|---|---|---|---|
| T1 | Planner: v4.1 vs AccuMO-style vs LEAF-style | `campaign_mesh4.sh`, REPS=2 | **done 14 Nov: 18/18 runs** |
| T2 | Energy price on/off (Theorem 1, Proposition, mechanism) | `campaign_energy_nov.sh` | running (4/12 at 23:15) |
| T3 | Noisy relay | `campaign_relaynoise_nov.sh` | queued tonight |
| T4 | Capped hold + guard, 24-min `mission` runs, pre-cool | `campaign_heat_nov.sh`; T4.1-T4.5 | ready (after push + smoke test); ~7 h |
| ~~T5~~ | ~~Airflow (fan over the camera Pi)~~ | **removed 15 Nov (no fan available): stated as a limitation in paper 2 (heat results are for a board without forced airflow; propeller wash untested)** | — |
| T6 | Two sense + one/two edge drones, frame destinations, temperatures | `arun_two.sh`, `campaign_two_nov.sh`; T6.1-T6.5 | ready; needs pi-receiver back; ~1.4 h |
| T7 | Frame rate 15/30/60, encode ahead | `campaign_fps_nov.sh`; T7.1-T7.3 | ready; ~1.2 h |
| T8 | v4.1+ (capped hold, room budget, contention-aware, YOLO11n) | to write | after T4/T7 |
| T9 | Topology reversal in one campaign | `campaign_topology_nov.sh`; T9.1-T9.4 | ready; ~2.2 h |
| T10 | Break-even goodput, predict then measure (paper 1) | `split_live.py`, `t10_predict.py` | tools ready; bench → prediction → sweep; ~0.5 day |
| T11 | Board timings (x264/x265 on the Pi, code encoders, YOLO11s prefix) | partly in `split_live.py bench` | ~2 h |
| — | Calibration and per-frame decisions from the `pred` logs; theorem and price checks on the new runs | `calib_hw.py`, `paper2/*check*.py` | after T1-T3 |

## Decisions waiting on the user

- A7: make pi-sender's cable address permanent? A8: a layer-2 bridge instead of SSH tunnels? A9: Nano2's mesh setup
  permanent? Until decided, all three stay as they are.

## Order from here

1. Tonight: T2, T3 (running), then commit and score T1-T3.
2. Next board slot: push the new code to all drones; smoke tests of S4, S5, S7; T7; T9; T6 (once pi-receiver is back);
   T4 overnight.
3. T10 and T11; S6 and an emulated many-camera test; T8.
4. After each block: held / did-not-hold lines, the checks, the Results Brief, Final Report, Novelty Brief and papers.

## Removed (15 Nov 2026, the user's decision: no extra fan, no drone to fly)

- **T5 airflow** and **G1 outdoor or tethered flight**: not possible with the equipment available. Both are stated as
  limitations in paper 2: every heat result is for a fanless board in still air, and no test was flown, so propeller
  wash, real distances and in-flight vibration are untested.

## Order of the remaining work (15 Nov 2026 15:45 IST, agreed with the user; highest return first)

Board phases run as `tools/session_nov14.sh` chains (resumable, health check between campaigns). Laptop work runs while
the boards are busy only when it cannot disturb a measurement (no scoring during runs that use the laptop worker).

| Phase | Work | Why first | Board | Laptop |
|---|---|---|---|---|
| 0 | **A7** pi-sender's cable address persistent; **A9** Nano2 joins the mesh at boot (same settings) | protects every later test from a reboot; no runtime change | 5 min | — |
| 1 | **T6** 2 sense + 1/2 edge drones; **S6 fair re-run** on two camera Pis (S6.5-S6.6) | the only real-swarm results; unblocked now | ~2.5 h | score T4/T8 meanwhile |
| 2 | **T10** break-even goodput, predict then measure (bench → committed prediction → rate sweep) | paper 1's strongest open objection | ~0.5 day | prediction |
| 3 | **Fixes of the failures**: room-following budget with a fit valid at high power; YOLO11n at a size that meets the deadline; Theorem 3 floor term from this board's data; then their board re-tests | turns three failed predictions into found-and-fixed results | ~3 h | ~1 day |
| 4 | **5 repetitions** for every headline comparison still at 2-4 | statistical power | ~0.5 day | — |
| 5 | **DVFS third knob** (D5): per-frequency power/latency on the Pi, frequency-aware price, board runs | the largest new novelty for paper 2 | ~1 h + 0.5 day | ~2 days |
| 6 | **Joint fades** on the shared channel (D6, Nano2 as traffic source); C8 governor; D7 cheaper camera-motion step; D4 YOLO11m on the ground; **T11** board timings; pi-receiver's remaining profiles (watched) | cheap strengtheners | ~1 day | — |
| 7 | Laptop: hardware calibration of the deadline probabilities (B4); theorem and price checks on every new run; paused L5 (HEVC features), L7 (bias fit), L8 (conformal); **second dataset** (L6); **reproducibility package**; **2025-2026 related-work check** | completes both papers' evidence | — | ~4 days |
| 8 | **A8** layer-2 bridge on pi-sender instead of SSH tunnels, then re-run the key comparisons both ways; **G2** BATMAN-adv overhead vs raw IBSS (temporary, everything restored and verified) | removes a stated artefact; changes the network, so last | ~1 day | — |
| 9 | Results Brief, Final Report, Novelty Brief; rewrite of both papers with every verdict (failures as written) and the limitations (indoor, no flight, no airflow, few boards); **independent audit** of every number | the deliverables | — | ~3 days |

Totals: about 3.5 board days and 8-9 laptop days, partly in parallel.
