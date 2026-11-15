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
- *Note, 15 Nov 2026 02:33, before any T8 run:* two board smoke tests showed that the replay's derivative estimator
  (a = T + τ dT/dt − c P) does not work on the Pi (first estimate 108 °C, then pinned at its 15 °C clip). It was
  replaced by a model-based observer (a = T − T_m, T_m the controller's model driven by the measured power; commit
  18d181f1). Replayed on tonight's 6-minute energy-run logs it moves from 37.3 to 30-33 °C, budget 2.8 → 3.0-3.4 W, still
  drifting at 6 minutes and dipping briefly to 2.2 W after a hot start. T8.1 is kept as written; whether 6 minutes is
  long enough to reach 3.1-3.7 W is part of what it tests.
- *Note, 15 Nov 2026 06:40, after the first T8 run and before any valid one:* that run priced onboard YOLO11n at 0 J
  (no entry in `energy_constants.json`), ran it onboard throughout (4.68 W, peak 87 °C) and was archived
  (`_superseded/vid_campaign_plus_nov_yolo11n_unpriced/`). YOLO11n is now priced at its measured 0.96 J (commit 99dd89c3).
  The predictions are kept as written.
- **T8.4 (heat)** Neither strategy is at or above 80 °C for more than 2 % of any run (6-minute runs: one 40-s total
  blackout), and neither throttles.

## After the runs

One line per prediction: held / did not hold, the measured value and the result file.

### Results: T7 (`vid_campaign_fps_nov/`, 12 runs, 15 Nov 2026 02:43-03:50 IST)

On-time results per second (3 reps): 15 frames/s 14.9 / 15.0 / 14.9; 30 frames/s 24.2 / 26.3 / 26.4 (mean 25.6); 60 frames/s
30.8 / 31.0 / 31.1 (mean 31.0); encode ahead at 30 frames/s 26.7 / 29.1 / 29.1 (mean 28.3). Median latency (median of the
phase medians): 53-55 / 48-53 / 60-64 / 53-59 ms. Ticks run: 99.9 / 99.8 / 96.8-97.6 / 99.8 %.
- **T7.1 held.** 14.9-15.0 results/s; latency within 10 ms of 30 frames/s.
- **T7.2 did not hold.** 60 frames/s gives +20.8 % on-time results (not within ±5 %), latency +11 ms (just over the 10 ms
  allowed), and the camera loop ran 97 % of the 60-per-second ticks (predicted < 90 %). At 30 frames/s v4.1 leaves the
  radio idle while it waits for the next tick; a faster camera shortens that wait. The 19.13 model's assumption that
  30 frames/s already saturates the paths is wrong on these boards.
- **T7.3 mostly held.** Encode ahead +10.4 % (within 0-14 %), 17-20 % of sends encoded ahead (≥ 5 %), but latency
  +5-6 ms, just over the 5 ms predicted.

### Results: T9 (`vid_campaign_topology_nov/`, 20 runs, 15 Nov 2026 03:50-05:49 IST; `vid_campaign_topology_nov_summary.json`)

sAP with forecaster: direct link v41 0.2010 ± 0.0013, hier 0.1495 ± 0.0016; multihop v41 0.1355 ± 0.0028, hier
0.1497 ± 0.0017.
- **T9.1 held.** Direct link: v41 ahead by 0.0515 ± 0.0024, 5 of 5 pairs.
- **T9.2 held.** Multihop: hier ahead by 0.0142 ± 0.0013, 5 of 5 pairs.
- **T9.3 held.** The reversal (hier − v41 in multihop minus on the direct link) is +0.064 to +0.069 in every one of the
  5 repetitions (one-sided permutation p = 1/32).
- **T9.4 held.** Camera power differs by 0.005 W (direct) and 0.012 W (multihop).
- This replaces the brief's two-campaign evidence (23 and 24 Oct, 3 multihop pairs) with one campaign, the two topologies
  alternating in time.

### Results: S6 pull test (`pull_nov/`, 20 runs of 60 s, 15 Nov 2026 05:49-06:25 IST)

Total on-time results per second (rep 1 / rep 2), v4.1 rule: 1 stream 13.2 / 14.2, 2 30.2 / 30.1, 4 29.8 / 29.9, 6 21.2 / 21.2,
8 19.5 / 20.2 (median latency 97-100, 128-139, 214-223, 317-366, 421-479 ms). Pull one ahead: 24.1 / 24.0, 27.1 / 27.3,
29.1 / 29.1, 28.7 / 28.6, 28.5 / 28.6 (median latency 97, 125, 125, 125-129, 124-127 ms).
- **S6.1 partly held.** v4.1 flat to 4 streams and falling beyond, latency above 250 ms at 8; but at 8 streams it keeps
  66 % of its 2-stream total, not below half.
- **S6.2 held.** Pull's total at 6 and 8 streams within 20 % of its 2-stream value; latency below 200 ms throughout.
- **S6.3 did not hold.** At 8 streams pull delivers 1.44× v4.1's on-time results, not 2×.
- **S6.4 partly held.** Within 25 % at 2 streams (v4.1 10 % ahead); at 1 stream pull is 76 % ahead (24.0 vs 13.7), as
  the model's one-stream gap (25.5 vs 22.1) in direction but larger.
- **Problem found (tool, not idea): pull is unfair across hosts.** With 4-8 streams, each pi-relayyy stream got about 1
  on-time result per second against 6-13.5 for each Nano2 stream (v4.1: 6.2-6.8 against 7.5-9.2). Candidates:
  `pull_bench.py`'s oldest-first turn compares the streams' capture times (each board's clock; Nano1 is +40 s, the Pi
  +0.4 s against the laptop) with the server's grant times, or the Pi answers grants slowly while encoding several
  streams in Python. To be checked when the Pi is idle, before any fairness claim; the totals are unaffected.

### Results: T8 (`vid_campaign_plus_nov/`, 16 valid runs, 15 Nov 2026 06:25-08:12 IST)

Per strategy (4 runs each): mission v41 3.29-3.39 W, second-half 75.4-76.1 °C, at or above 80 °C 13.9-15.2 % of the time,
throttled 1.4-2.7 %, peak 85.3-85.9 °C; mission v41plus 3.04-3.14 W, 72.7-73.2 °C, 0-0.8 %, 0 %, 79.8-82.6 °C; random v41
2.85-3.06 W, 64.0-68.1 °C, 0 %, 0 %; random v41plus 2.75-3.06 W, 65.1-68.8 °C, 0 %, 0 %.
- **T8.1 did not hold.** The room-following budget ended at 2.66-2.90 W (not 3.1-3.7), and v4.1+ drew less power than v41
  on the mission. The observer took the blackout heating for a warmer room: at high power the board heats faster than
  the controller's linear fit (11.3 °C/W) predicts, so T − T_m rose (offset estimate 38-40 °C, not ~30).
- **T8.2 did not hold.** YOLO11n ran on 0 of the 135-141 onboard frames of each total blackout. With the hold on, the
  freshness price adds λ_F·p_on only to an onboard setting that meets the 300 ms deadline: s320 (~180 ms) does, YOLO11n
  (~305 ms) misses it by ~5 ms.
- **T8.3 held.** sAP with forecaster: mission v41 0.1354, v41plus 0.1357 (+0.0003 ± 0.0165, 2 of 4 pairs ahead); random
  v41 0.1185, v41plus 0.1213 (+0.0027 ± 0.0116); overall +0.0015 ± 0.0070 (`vid_campaign_plus_nov_summary.json`).
- **T8.4 did not hold for v41, held for v4.1+.** Plain v4.1 was hot 14-15 % of each 6-minute mission and throttled, from
  a single 40-s total blackout (the hold); v4.1+ with the hold capped at 78 °C was hot 0-0.8 % and never throttled. This
  reproduces the hold's heat on a mesh board (pi-relayyy), not only on the original Pi, and shows the capped hold
  removing it.

### Results: T4 (`vid_campaign_heat_nov/`, 15 runs of 24 minutes, 15 Nov 2026 08:12-15:08 IST; every run started at 54.3-54.9 °C)

Per strategy (5 runs): v41 3.12-3.30 W, at or above 80 °C 16.4 / 16.7 / 16.9 / 17.3 / 26.2 % (mean 18.7 %), throttled
3.2-10.9 %, peak 85.9-87.0 °C; v41cap 3.04-3.08 W, 0.2-0.8 % (mean 0.5 %), never throttled, peak 80.4-81.5 °C; v41guard
3.04-3.08 W, 0.2-0.8 % (mean 0.4 %), never throttled, peak 80.4-81.5 °C. Availability 0.81-0.86 for all three.
- **T4.1 held.** v4.1's hold heats the board: 18.7 % of the time at or above 80 °C (predicted 5-25 %), peaks 85.9-87.0 °C
  (predicted 83-86; one run 1 °C above). This reproduces the original Pi's Wi-Fi result (19-27 %) on a mesh board.
- **T4.2 partly held.** Capped hold: mean 0.5 % (below 2 % and far below a third of v4.1's), never throttled; but the peak
  passed 80.5 °C in 4 of 5 runs (80.95-81.5 °C).
- **T4.3 did not hold.** With the hard guard the peak was 80.4-81.5 °C in every run (bound 79.93 °C) and the board was at
  or above 80 °C for 0.2-0.8 % of the time. The guard stops new onboard inference at 78 °C, but the board still rises
  1-2 °C above the bound under offload-only load: the floor term of Theorem 3 (b) (from the original Pi) is too low for
  this board, or the Pi's fast die response overshoots the first-order model.
- **T4.4 held.** sAP with forecaster: v41 0.1281, v41cap 0.1267 (−0.0014 ± 0.0051), v41guard 0.1263 (−0.0017 ± 0.0031),
  both within 0.005; freshness (share of time with a detection younger than 300 ms) 0.854 for all three
  (`vid_campaign_heat_nov_summary.json`).
- **T4.5 held** (`paper2/theory_check.py`, 15 Nov 2026 21:10): every logged price update of the 15 heat runs is one the
  coded rule allows (0 unexplained steps); average power exceeds the budget by at most 0.515 W, always inside the bound
  (budget + price term + held term; the hold held the price in up to 28 % of the updates). The same holds on all 121
  runs of the 14-15 Nov mesh campaigns and all 497 recorded runs (110,076 updates, identity error ~1e-15 W). The check
  now uses the per-step budget B_t where the room-following budget varies it (14 v4.1+ runs), so the bound is
  stated with the run's mean budget.

## S6 fair re-run with two camera Pis (`HOST2=camera2 PULL_OUT=pull_nov_fair tools/campaign_pull_nov.sh`; written 15 Nov 2026 15:25, before any of these runs)

The same 20 runs as S6, with the streams split between pi-relayyy and pi-receiver (two camera Pis, as a swarm would
have) and pull one ahead's turn order on the server's clock (commit cf8edb50). S6.1-S6.4 apply unchanged, plus:
- **S6.5 (fairness)** With pull one ahead at 4, 6 and 8 streams, every stream gets at least half of the mean on-time rate
  per stream (the first runs, with mixed board clocks, gave pi-relayyy's streams about a fifth of the mean).
- **S6.6** Under v4.1's rule the two Pis' streams get similar shares (within a factor of 2), as in the first runs.

## T8 re-test: room-following budget with the per-board fit (`PLUS_OUT=vid_campaign_plus_nov2 tools/campaign_plus_nov.sh`; written 15 Nov 2026 18:18, before any of these runs)

Change (commit c7f90d3e): `energy_constants.json` has per-board thermal fits; pi-relayyy 29.72 + 11.66 P (from the
energy test). The budget rule's target stays 68.9 °C (the shared fit at 2.8 W); this board's fit turns it into
(68.9 − 29.7) / 11.66 = 3.36 W at the start, and the estimate then updates only while the power is steady (smoothing
600 s). Offline on the T8 and energy logs the earlier observer settled at 34-41 °C against the board's 29.7, because the
Pi never reaches thermal steady state in 6 minutes; hence the per-board start. Same design as T8 (mission, random, v41
vs v41plus, 4 reps).
- **T8R.1** v4.1+'s budget stays within 3.1-3.6 W in every run; its mean power is 0.2-0.7 W above v41's in the random
  scenario, and its second-half mean temperature stays at or below 72 °C (target + 3).
- **T8R.2** On the mission v4.1+ stays at or above 80 °C for at most 3 % of the time and never throttles, although its
  budget is higher than v41's (the capped hold, not the budget, governs the blackout heat).
- **T8R.3** sAP (forecaster): v4.1+ at least v41's in the mean of 4 pairs in each scenario, or within 0.005.

## Theorem 3 re-test: the guard lowered by the measured fast-mode overshoot (`HEAT_OUT=vid_campaign_heat_nov2 HEAT_STRATS=v41guard765 HEAT_REPS=3 tools/campaign_heat_nov.sh`; written 15 Nov 2026 18:20, before any of these runs)

Finding behind it (T4 guard runs, 24 crossings of 78 °C): after each crossing the measured temperature rose another
1.6-3.5 °C (mean 2.1), peaking 16-27 s later, with the power right after the crossing at 3.7-4.2 W. A first-order plant
with τ = 149 s cannot rise 2.5 °C in 20 s at that power; this is a fast thermal mode (heat stored near the die reaching
the sensor), which Theorem 3's single time constant omits. Corrected bound: peak ≤ guard + δ_fast, δ_fast = 3.5 °C (the
largest measured): 81.5 °C with the 78 °C guard, which every T4 guard run meets (80.4-81.5 °C). Strategy v41guard765:
hold cap and guard at 76.5 °C (= 80 − 3.5).
- **G.1** Peak at most 80.0 °C in every one of the 3 runs; 0 % of the time at or above 80 °C.
- **G.2** sAP (forecaster) within 0.01 of T4's v41guard (0.1263) and freshness within 3 points of its 0.854.

### Results: T6 / D1 (`vid_campaign_two_nov/`, 12 valid runs × 2 cameras, 15 Nov 2026; `vid_campaign_two_nov_summary.json`)

pi-relayyy and pi-receiver at the same time. Total on-time results per second (both cameras): static_good v41j1 38.7 /
38.5 / 42.6, v41j2 34.5 / 35.5 / 36.3; mesh_mission v41j1 33.7 / 34.8 / 34.2, v41j2 33.5 / 34.1 / 34.4. sAP with forecaster
(per camera): static_good v41j1 0.1813, v41j2 0.1436; mesh_mission v41j1 0.1667, v41j2 0.1294. Freshness 0.994-0.998
(one Jetson) against 0.972-0.975 (two). Pi 2.82-2.92 W, 66-69 °C; onboard 1.4-2.5 % of frames.
- **T6.1 held.** 38.5-42.6 in total with one Jetson, each camera 18.5-21.7 (below its single-camera 26.3).
- **T6.2 did not hold.** Adding Nano2 lowered the total by 11 % (static_good) and each camera's sAP by 0.038 (−21 %). On
  the one shared channel v4.1 keeps more paths busy at once (laptop, Nano1, Nano2 per camera): Jetson results' median
  latency rose from 125 to 170-175 ms and the laptop path's from 54 to 76 ms. This is the overload model's prediction
  (one shared channel: a second Jetson adds nothing; per-Pi load spreading backfires), now on two real camera drones and
  two edge drones. v4.1 values each path on its own and does not see that its paths share the air.
- **T6.3 partly held.** In `edge_link_slow` v41j2 sent about twice as many frames to Nano2 as to Nano1 (as predicted), and
  in `camera_out_of_range` it split them evenly between the two Jetsons; but over the mission its sAP was 0.037 lower.
- **T6.4 held.** Onboard on 1.4-2.5 % of frames; mean Pi temperature 66-69 °C in both strategies.
- **T6.5 held.** Nano2 ran YOLOv8m on 831 and 858 of its frames (the two cameras, mission rep 1).
- Three runs made while the laptop ran on battery were archived and re-run on mains
  (`_superseded/vid_campaign_two_nov_laptop_on_battery/`).
- **T8R.4 (YOLO11n at 480 px, added 15 Nov 2026 19:02 before any re-test run)** v4.1+ now offers YOLO11n at 480 px onboard
  (mAP 0.1666 on DET val, against s320's 0.1367; expected ~175-200 ms on the Pi, inside the deadline) instead of 640 px.
  In the mission's total blackout at least half of v4.1+'s onboard frames use it.

### Results: T8 re-test (`vid_campaign_plus_nov2/`, 15 Nov 2026 19:17-20:48 IST, 12 runs)

Reps: 3 per scenario and controller (mission v41 r1-r3, v41plus r2-r4; random r1-r3 each). The 4th repetition was cut as
low value (the conclusions were already clear) to make room for the guard and channel-aware tests; mission v41plus r1 is
the run archived before the onboard-timing fix (`_superseded/vid_campaign_plus_nov2_before_onboard_timing`), hence r4.
Per run: budget, mean Pi power, second-half mean temperature, time at >= 80 °C, peak, throttled samples (bit 0x4).

| run | budget W | mean W | 2nd-half °C | >= 80 °C | peak °C | throttled |
|---|---|---|---|---|---|---|
| mission v41 r1 / r2 / r3 | 2.8 | 3.37 / 3.27 / 3.31 | 77.8 / 78.3 / 78.6 | 20.0 / 20.9 / 21.6 % | 85.9 | 9 / 10 / 11 |
| mission v41plus r2 / r3 / r4 | 3.29-3.36 | 3.35 / 3.29 / 3.52 | 76.7 / 77.2 / 72.1 | 5.5 / 6.8 / 0.9 % | 84.2 / 84.8 / 82.6 | 0 |
| random v41 r1 / r2 / r3 | 2.8 | 2.81 / 3.33 / 3.11 | 66.8 / 73.1 / 67.7 | 0 / 18.1 / 1.1 % | 76.5 / 85.9 / 82.0 | 0 / 7 / 0 |
| random v41plus r1 / r2 / r3 | 3.31-3.36 | 3.35 / 3.37 / 3.42 | 74.2 / 76.1 / 75.7 | 5.5 / 12.8 / 7.7 % | 84.2 / 85.3 / 83.2 | 0 / 1 / 0 |

sAP (forecaster), mean of 3: mission v41 0.1312, v41plus 0.1342; random 0.1088, 0.1133. P(AoI <= 300 ms) mission 0.906 /
0.890, 95th-pct AoI 367 / 500 ms (YOLO11n-480 at ~192 ms is slower than s320 onboard); random 0.940 / 0.947.

- **T8R.1 partly held.** The budget stayed at 3.29-3.36 W in every run (held), and v4.1+'s mean power was +0.30 W above
  v41's in the random scenario (paired +0.54 / +0.04 / +0.31; mean inside 0.2-0.7). Its second-half mean temperature
  was 72.1-77.2 °C, above 72 °C in 5 of 6 runs: **not held.** The per-board fit (made from steady 2.8-3.6 W runs) does not
  predict this board under bursty load, and the room-following budget should not be claimed as a temperature target.
- **T8R.2 partly held.** v4.1+ never throttled on the mission (0 samples in 3 runs; v41 9-11 in each) and spent 0.9-6.8 %
  of the time at >= 80 °C against v41's 20.0-21.6 % (3-23× less), but above the 3 % bound in 2 of 3 runs.
- **T8R.3 held.** sAP (forecaster) v4.1+ − v41: mission −0.0012 (2 pairs), random +0.0045 (3/3 pairs positive), all
  +0.0022; means 0.1342 vs 0.1312 and 0.1133 vs 0.1088. (3 reps, not 4.)
- **T8R.4 held.** YOLO11n-480 timed 192 ms at start-up and took 78-83 % of v4.1+'s onboard frames on the mission
  (273/352, 293/371, 395/478) and 96/96, 89/89 and 179/188 of those in the total blackout.

### Results: S6 fair re-run (`pull_nov_fair/`, 20 runs of 60 s on pi-relayyy + pi-receiver, 15 Nov 2026 18:40-19:16 IST)

Total on-time results per second (rep 1 / rep 2) and median latency: v4.1 rule 1 stream 13.7 / 13.3 (98-100 ms), 2 21.4 /
20.4 (127-129), 4 21.1 / 18.1 (232-234), 6 11.1 / 10.1 (311-321), 8 3.7 / 2.9 (391-411); pull one ahead 22.1 / 22.1 (100),
21.0 / 20.9 (114-115), 22.0 / 21.5 (115-117), 21.6 / 21.5 (112-114), 19.9 / 21.6 (114-120).
- **S6.1 held** on two camera Pis: v4.1's rule is flat to 4 streams, then collapses (2.9-3.7 at 8 streams, below half of
  its 2-stream value), with latency above 250 ms.
- **S6.2 held.** Pull one ahead stays at 20-22 on-time results per second at every count, latency 112-120 ms.
- **S6.3 held** on two camera Pis: at 8 streams pull delivers 5.8-7.4× v4.1's on-time results (19.9-21.6 against 2.9-3.7);
  with Nano2 as the second host (first runs) it was 1.44×.
- **S6.4 partly held.** Within 25 % at 2 streams; at 1 stream pull is 63 % ahead (22.1 against 13.5).
- **S6.5 did not hold.** With one stream per Pi pull is fair (worst/mean 0.98-1.0), but with 2-4 streams per Pi each
  pi-relayyy stream got 1.2-1.6 on-time results/s against 3.7-9.2 for each pi-receiver stream (worst/mean 0.28-0.48), on
  the server's clock: not a clock effect. pi-relayyy's streams hold their grants longer before sending; the cause (the
  tool's multi-stream loop on that board or its radio timing) is not found. No fairness claim is made for pull one ahead.
- **S6.6 held.** Under v4.1's rule the two Pis' streams got similar shares (worst/mean 0.46-1.0, no host pattern).

## T6 follow-up: channel-aware sending (`TWO_OUT=vid_campaign_two_cap TWO_STRATS="v41j2 v41j2cap" TWO_REPS=2 tools/campaign_two_nov.sh`; written 15 Nov 2026 19:21, before any of these runs)

`--max-paths-busy 2`: a camera starts no new offload while 2 of its paths are in flight (laptop, Nano1, Nano2 all
available; Nano2 also YOLOv8m). Interleaved with plain v41j2, 2 reps × static_good and mesh_mission. References (T6):
per-camera sAP static_good v41j1 0.1813 / v41j2 0.1436; mesh_mission 0.1667 / 0.1294.
- **C.1** v41j2cap's per-camera sAP (forecaster) is at least 0.02 above v41j2's in each scenario (mean of the pairs).
- **C.2** v41j2cap is within 0.015 of T6's v41j1 in each scenario (the cap recovers most of the loss).
- **C.3** v41j2cap's Jetson results' median latency is at least 25 ms below v41j2's.

## T10: break-even goodput of paper 1's learned split codes, predict then measure (written 15 Nov 2026 21:25 IST, before any sweep run)

Pair: camera pi-receiver (Pi 5, CPU, 4 threads) → server Nano2 (25 W, `jetson_clocks`, CUDA fp16), over the mesh.
Inputs, board-measured only (`experiments/results/hardware/t10/`): `split_live.py bench` on each board (60 VisDrone-VID
frames), one-way delay 1.9 ms (20 pings, RTT 3.8 ms); accuracy = mAP@[.5:.95] on DET val from the learned-bottleneck
study. The first server bench used ultralytics' NMS (161 ms on the Jetson against 29.5 ms for the detector) and is
archived (`t10/_superseded_ultralytics_nms/`); split_live now uses the campaigns' fast NMS.

| option | onboard ms (Pi) | payload KB | server ms (Nano2) | mAP |
|---|---|---|---|---|
| jpeg_q20 | 2.3 | 19.7 | 36.4 | 0.1597 |
| jpeg_q35 | 2.3 | 26.9 | 36.4 | 0.1883 |
| jpeg_q90 | 2.7 | 80.6 | 37.5 | 0.2563 |
| k4_c4 | 226.5 | 4.3 | 28.3 | 0.1417 |
| k4_c8 | 227.8 | 8.3 | 28.3 | 0.1810 |
| k2_c8 | 174.4 | 27.0 | 31.7 | 0.2332 |

Paper 1's model (`t10_predict.py`, `t10/t10_prediction.json`), U = f · p_on · A/A_ref per goodput (Mbit/s):

| goodput | best | jpeg_q20 | jpeg_q35 | jpeg_q90 | k4_c4 | k4_c8 | k2_c8 |
|---|---|---|---|---|---|---|---|
| 0.5 | (none useful) | 0.01 | 0 | 0 | 0 | 0 | 0 |
| 0.75 | jpeg_q20 | 2.44 | 0.21 | 0 | 0.48 | 0 | 0 |
| 1 | jpeg_q20 | 3.59 | 2.82 | 0 | 2.21 | 0 | 0 |
| 2 | jpeg_q20 | 5.98 | 5.29 | 0.01 | 2.27 | 2.82 | 0.10 |
| 4 | jpeg_q35 | 8.97 | 10.58 | 5.76 | 2.27 | 2.91 | 4.37 |
| 8 | jpeg_q35 | 17.93 | 21.16 | 9.60 | 2.27 | 2.91 | 4.37 |

- **T10.1** No learned code delivers the highest accuracy-weighted on-time rate (on-time results/s × mAP/base) at any
  swept goodput: on a Pi 5 camera there is **no break-even goodput**; the code's encoder prefix (174-228 ms on the CPU)
  caps it at 4.3-5 frames/s, and below ~0.7 Mbit/s, where its small payload would matter, the prefix plus transmission
  already misses the 300 ms deadline.
- **T10.2** The codes' measured frame rate stays at or below 5 frames/s at every goodput; jpeg_q20 reaches at least
  12 frames/s at 4 Mbit/s or more.
- **T10.3** At 1 and 2 Mbit/s the measured on-time rate of jpeg_q20 and k4_c4 is within 30 % of the model's f · p_on
  (6.0 / 4.3 at 1 Mbit/s, 10.0 / 4.3 at 2 Mbit/s).
- **T10.4** At 0.75 Mbit/s k4_c4 meets the deadline on fewer than half of its frames (model p_on 0.21) and jpeg_q20
  on most (0.95).

Sweep (after the channel-aware test, so the channel is otherwise quiet): `split_live.py send` from pi-receiver to
Nano2, rates 0.5, 0.75, 1, 2, 4, 8 Mbit/s (htb on the destination port only) × jpeg_q20, jpeg_q35, k4_c4, k4_c8, k2_c8
× 45 s, order shuffled, 1 repetition (2 at 0.75-2 Mbit/s, where the options are closest).
