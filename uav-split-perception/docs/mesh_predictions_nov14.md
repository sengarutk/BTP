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

## After the runs

One line per prediction: held / did not hold, the measured value and the result file.
