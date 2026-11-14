# Predictions for the next mesh tests (written 14 Nov 2026, before any of these runs)

Fixed in the repository before the runs (see this file's commit). After the runs each prediction gets a "held / did
not hold" line with the measured value; nothing above that line is edited. Testbed: `docs/mesh_session_nov14.md`.

## T4. Capped hold and hard guard on 24-minute missions (`tools/campaign_heat_nov.sh`)

Scenario `mission` (240-s phases, with a 4-minute total blackout), camera pi-relayyy over the mesh, every run started
below 55 °C. v41, v41cap (hold only below 78 °C), v41guard (v41cap + no onboard start at ≥ 78 °C) × 5 reps.

What the claim rests on so far (found while writing these predictions):
- The "hot 19-27 % of the time" result is **two Wi-Fi runs on 12 Oct on the original Pi** (`vid_campaign_long/
  a2_mission__v41__r{1,2}.json`: 19 % and 27 %, peak 85.9 °C, 3.20 / 3.34 W), not a mesh board.
- On the mesh, pi-relayyy's 24-minute v4.1 runs (`vid_campaign_mesh2_long`, 5 runs) were hot 0-0.1 % of the time
  (peaks 73-81.5 °C), because `mesh_mission` has no total blackout, so the hold never lasts long.
- The replay (19.21, 24-minute missions): v4.1 18 % hot; capped hold 0 % at +0.0000 ± 0.0001 sAP; guard + capped
  hold peak 78.0 °C, 0 % hot; Theorem 3 (b) bound 79.93 °C.

Model estimate for this board (fit 34.43 + 12.73 P, τ 149 s; onboard-only power about 4.2 W, as the unpriced runs of
`vid_campaign_mesh2` static_good): from about 72 °C, the 4-minute blackout reaches about 85 °C and the board is at or
above 80 °C for about 2-3.5 minutes per run (8-15 % of 24 minutes).

- **T4.1** v41 is at or above 80 °C for 5-25 % of each run (mean of 5 runs), with peaks of 83-86 °C. If it is below
  5 %, the hold's heat does not appear on this board and the capped hold cannot be shown to remove it here; that is
  reported as such.
- **T4.2** v41cap: mean hot time below 2 % and at most a third of v41's; peak at most 80.5 °C (an inference started
  just below 78 °C can still finish above it).
- **T4.3 (Theorem 3 (b))** v41guard: peak at most 79.9 °C in every run; 0 % of the time at or above 80 °C.
- **T4.4 (cost)** v41cap and v41guard differ from v41 by less than 0.005 sAP (with forecaster) in the mean of 5
  pairs; their freshness (share of time with a detection younger than 300 ms) is at most 3 points lower.
- **T4.5 (Theorem 1)** every logged energy-price update is one the coded rule allows (`paper2/theory_check.py`).

## T9. Topology reversal in one campaign (`tools/campaign_topology_nov.sh`)

static_good (direct ground link) and multihop (relay through Nano1), v41 and hier × 5 reps, alternating in time.
Reference: direct link (18.8) v41 0.193 against the chain 0.146 sAP with forecaster (6 of 6 pairs); multihop
(`vid_campaign_mesh2_summary.json`) hier 0.1506 ± 0.0024 against v41 0.1373 ± 0.0076 (+0.0133, 3 of 3 pairs).

- **T9.1** Direct link: v41 ahead of hier by at least 0.02 sAP (forecaster) in the mean, in at least 4 of 5 pairs.
- **T9.2** Multihop: hier ahead of v41 by 0.005-0.025 in the mean, in at least 4 of 5 pairs.
- **T9.3** The reversal: (hier − v41) in multihop minus (hier − v41) on the direct link is positive in all 5
  repetitions (permutation p = 1/32 one-sided).
- **T9.4** Power: the two strategies' camera power differs by less than 0.1 W in each topology (both priced at 2.8 W).

## T7. Camera frame rate and encode ahead (`tools/campaign_fps_nov.sh`)

static_good, one camera (pi-relayyy), paths laptop and Nano1; v41 at 15, 30 and 60 frames/s and v41ea (encode ahead)
at 30 frames/s × 3 reps. References: today's v41 static_good run (`vid_campaign_mesh4/a2_static_good__v41__r1.json`:
26.3 on-time results/s, median latency 47 ms, 7,186 of 7,200 ticks run; forecaster steps 6.1 + 3.2 + 0.2 ms per
tick); the 19.13 model for one mesh hop (v4.1 14.9 / 22.1 results/s at 15 / 30 frames/s on one path; latest frame
wins 25.2 at 30, +14 %).

- **T7.1** 15 frames/s: on-time results per second between 13.5 and 15 (the camera rate binds), median latency within
  10 ms of the 30 frames/s runs.
- **T7.2** 60 frames/s: on-time results per second within ±5 % of the 30 frames/s runs (the paths bind, not the
  camera), and no queue builds: median latency within 10 ms of 30 frames/s. The camera loop cannot keep 60 ticks per
  second with the live forecaster (about 10 ms of 16.7 ms per tick, plus the decision and encode), so fewer than 90 %
  of the 60-per-second ticks run.
- **T7.3** Encode ahead at 30 frames/s: on-time results per second 0-14 % above v41 (the model's one-path gain is
  the upper bound; with two paths the radio idles less), median latency not more than 5 ms higher, and the
  encode-ahead sends are at least 5 % of all sends.

## T6 / D1. Two sense drones, one or two edge drones (`tools/campaign_two_nov.sh`)

pi-relayyy and pi-receiver run v4.1 at the same time; v41j1 = laptop + Nano1 (both cameras share Nano1's GPU, one
worker each), v41j2 = laptop + Nano1 + Nano2 (Nano2 also offers YOLOv8m). static_good and mesh_mission × 3 reps.
References: one camera, v4.1, static_good today: 26.3 on-time results/s (`vid_campaign_mesh4`). The overload model on
one shared channel, Jetson paths only (`overload_multi/summary.json`): 2 Pis on 1 Jetson 26.3 in total, on 2 Jetsons
38.4, the channel's limit about 45 (4 Pis, 2 Jetsons: 45.1). Profiles (14 Nov): YOLOv8s equally fast on both Nanos
(29.1 / 27.6 ms), YOLOv8m 56.4 against 40.3 ms. Here the laptop is already a second server, so Nano2 adds less
than in the model.

- **T6.1** v41j1, static_good: the two cameras together deliver 30-46 on-time results per second, each camera less
  than its single-camera 26.3 (they share the channel and Nano1).
- **T6.2** v41j2 against v41j1, static_good: the total changes by −5 % to +20 % (the shared channel, not the servers,
  binds); per-camera sAP (forecaster) differs by less than 0.01.
- **T6.3** mesh_mission (Nano1's link slowed to 2 Mbit/s in `edge_link_slow`; the laptop link cut in
  `camera_out_of_range`, where v41j1's two cameras both depend on Nano1): in `edge_link_slow` v41j2 sends a larger
  share of its frames to Nano2 than in `good`; in `camera_out_of_range` v41j2 delivers more on-time results per second
  (both cameras together) than v41j1 in every pair; over the whole mission v41j2's mean sAP (forecaster) is at least
  v41j1's for each camera (mean of 3 pairs).
- **T6.4** No overload-to-heat chain with two cameras: in static_good each Pi runs onboard on less than 5 % of its
  frames and its mean temperature stays below 75 °C, in both strategies.
- **T6.5** With `--jetson2-m`, a non-zero share of Nano2's frames use YOLOv8m when its link is good.

## S6 / E3-E4. Many camera streams on one Jetson: v4.1's rule against pull one ahead (`tools/campaign_pull_nov.sh`)

Light JPEG streams (640 q90, 30 frames/s) from pi-relayyy and Nano2 to Nano1 (YOLOv8s FP16), 1-8 streams, 60 s,
2 reps. Model (`overload_handling/summary.json`, mesh_jetson, one shared radio), total on-time results per second
and median latency: v4.1 22.1 / 26.3 / 26.3 / 19.7 / 1.6 at 1 / 2 / 4 / 6 / 8 streams (p50 74 → 363 ms); pull one
ahead 25.5-25.6 at every count (p50 98-101 ms).

- **S6.1** v4.1's rule: the total stays within 20 % of its 2-stream value up to 4 streams, then falls; at 8 streams it
  is below half of the 2-stream value, and its median latency rises with the count (at 8 streams above 250 ms).
- **S6.2** Pull one ahead: the total at 6 and 8 streams is within 20 % of its 2-stream value, and its median latency
  stays below 200 ms at every count.
- **S6.3** At 8 streams pull one ahead delivers at least twice v4.1's on-time results per second.
- **S6.4** With 1-2 streams the two differ by less than 25 % (the model: pull ahead at 1 stream, v4.1 at 2).
- Two radios (Pi and Nano2) instead of the model's one shared queue, so the collapse may come at a different count;
  the direction (v4.1 collapses, pull does not) is the claim tested.

## T8 / D2. v4.1+ against v4.1 (`tools/campaign_plus_nov.sh`)

v4.1+ = v4.1 with the hold capped at 78 °C, the room-following budget (`--budget-rule`, target = the controller fit at
2.8 W = 37.26 + 11.31 × 2.8 = 68.9 °C), contention-aware latency (10 ms while onboard inference runs) and YOLO11n
allowed onboard (`n640y11`). mission and random, 40-s phases, × 4 reps, camera below 60 °C at each start.
Inputs: tonight's energy test on this board (`vid_campaign_energy_nov`: v41 at 2.8 W held a second-half mean of
60.9-63.8 °C, so its room-and-board offset is about 62 − 11.31 × 2.8 ≈ 30 °C against the fit's 37.3); YOLO11n onboard
sAP 0.047 against YOLOv8s's 0.017 (brief 17.7, 296 ms per frame); replay (19.21): capped hold +0.0000, room-following
budget +0.0008 in the lab.

- **T8.1 (room-following budget on hardware)** v4.1+'s budget settles at 3.1-3.7 W (from the offset ≈ 30 °C: (68.9 −
  30) / 11.31 ≈ 3.4 W), so its mean power is 0.3-0.9 W above v4.1's, while its second-half mean temperature stays at
  or below 72 °C (the target + 3). This is the proposition's own correction: a cooler board gets a larger budget.
- **T8.2 (YOLO11n)** In the mission's blackout phases (`ground_blackout` excluded: the Jetson is up; `total_blackout`),
  at least half of v4.1+'s onboard frames use YOLO11n.
- **T8.3 (accuracy)** mission: v4.1+'s sAP (forecaster) is at least v4.1's in the mean of 4 pairs; random: the two
  differ by less than 0.01, and v4.1+ is never more than 0.005 below in the mean.
- **T8.4 (heat)** Neither strategy is at or above 80 °C for more than 2 % of any run (6-minute runs: one 40-s total
  blackout), and neither throttles.

## After the runs

One line per prediction: held / did not hold, the measured value and the result file.
