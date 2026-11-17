# Laptop strengthening of both papers: predictions before any analysis (16 Nov 2026)

The boards and the mesh will not be set up again (the user's decision, 16 Nov). Every item below is done on the
laptop, from data already recorded. The items that would have needed the boards (1, 7, 10) are replaced by analyses of
the recorded board data, plus the validated trace replay. Each verdict is written under its prediction, as before.
Order (agreed with the user): 5, 6, 8, 2, then the data-based versions of 1, 7, 10, then 9, 3, 4, then the papers, the
reports and the audit.

## Item 5 (paper 2): "same accuracy" stated as a tested equivalence

Every "same accuracy at less power or heat" claim becomes a two one-sided t-test (TOST, α = 0.05). The margin is
±0.005 sAP, the replay's resolution and the smallest difference the paper treats as meaningful. The power and heat
differences are reported as the main effect, with their paired intervals.

Comparisons, all paired within one campaign:
- mesh2: noprice − v4.1
- final_nov: v41final − v41 (both scenarios)
- heat_nov: v41cap − v41
- budget_nov: 2.4 − 2.8 W
- the Wi-Fi energy campaign: v4 − v3+fc

Predictions:
- 5.1: v41final − v41 is equivalent within ±0.005 on mesh_mission. On multihop it is not, because the multihop
  difference is −0.0032 ± 0.0032.
- 5.2: mesh2 noprice − v4.1 is equivalent (9 pairs, −0.002).
- 5.3: heat_nov v41cap − v41 (5 pairs, about −0.0014) is equivalent.
- 5.4: budget_nov (3 pairs) is not shown equivalent: too few pairs. It is reported as not shown.
- 5.5: the power differences are significant in every comparison where a price or budget changes.

## Item 6 (paper 2): how much airflow removes the heat cost (replaces the airflow test)

Airflow lowers the board's thermal resistance. In the validated replay, both the plant's slope (12.73 °C/W) and its
time constant (148.8 s, which is R·C) are scaled by k ∈ {1.0, 0.9, 0.8, 0.7, 0.6, 0.5}. Runs: the 24-minute mission
with its 4-minute total blackout, and the 2-minute mission. Policies: v4.1 (hold always), v4.1 with the capped hold,
the final controller (guard 76.5 °C), and the unpriced controller. 5 seeds, common random numbers.

Predictions:
- 6.1: v4.1's hot time (≥ 80 °C) on the 24-minute blackout mission falls to 0 at k ≤ 0.8. The hold draws about
  4.5 W, and 34.4 + 0.8 · 12.73 · 4.5 ≈ 80.2 °C.
- 6.2: the unpriced controller's heat cost (throttling, hot time) vanishes at k ≤ 0.75.
- 6.3: the energy price's power saving (W) does not depend on k, since the budget sets it. Only its heat benefit
  vanishes.
- Conclusion expected: any airflow that lowers the board's thermal resistance by more than about 25 % removes the
  heat cost. The energy saving remains.

## Item 8 (paper 2): a calibrated deadline probability

- 8a. The hardware logs (calib_hw.py's frames) are split by date: fit on 14–15 Nov, test on 16 Nov. Two mappings
  of the logged p_on are fitted: isotonic regression, and a split-conformal correction.
  - 8a.1: ECE on the held-out 16 Nov frames falls from about 0.05 to ≤ 0.02 with either mapping.
  - 8a.2: the lowest bin (p_on < 0.1) maps to 0.5–0.7.
- 8b. Replay, using the predictions already committed on 12 Nov (docs/conformal_predictions_nov12.md, items 1–4):
  v4.1 against v41_conf, 4 scenarios × 10 seeds.

## Item 2 (paper 1): the rule applied to published split-computing results

From 5–8 published split-computing papers that report payload sizes, accuracy, device times and the image baseline,
compute the rule's break-even goodput from their own numbers and compare it with where they report wins.

- 2.1: every reported end-to-end win lies below the B_be computed from that paper's numbers (0 exceptions).
- 2.2: where a paper claims a win at a goodput above B_be, its image baseline is weaker than the rule's (one fixed
  JPEG quality, PNG, raw frames) or its device is much faster than a Pi.

Papers whose numbers are incomplete are listed, not guessed.

## Item 1 (paper 1, data-based): the rule's prediction for a fast camera, on measured times

- 1a. The T10 timing model is checked against every measured cell of the Pi sweep (6 options × 6 goodputs).
  - 1a.1: the median absolute error of the predicted on-time rate is ≤ 20 %.
  - 1a.2: the predicted best option matches the measured one at every goodput.
- 1b. The Jetson measured as a camera (t10_bench_jetson2.json: codes and JPEG timed on Nano2) goes through the rule
  with the full 18-quality JPEG family and the video family, as pi_measured_break_even.py does for the Pi. Jetson CPU
  encode times not measured are scaled by the measured JPEG Jetson/laptop ratio.
  - 1b.1: on a Jetson camera the smallest codes win below a positive B_be against JPEG (of the order of the rule's
    9.8 Mbit/s for the smallest joint code). With video in the image family the window shrinks to ≤ 2 Mbit/s.
  - 1b.2: 0 exceptions to the rule.
- Stated limit: no live sweep with a Jetson as the camera was run.

## Item 7 (paper 2, data-based): is the late-path skip post hoc?

- 7a. Held-out board logs, never used to design the skip: the multihop and lossy-relay v4.1 runs of topology_nov and
  relaynoise_nov, and the one-hop runs of final_nov and topology_nov. Every frame the skip would have removed is
  identified: a network frame with p_on < 0.5 sent while another path's last decision (≤ 0.5 s earlier) had
  p_on ≥ 0.5. Their observed on-time share is measured.
  - 7a.1: in multihop, most such frames (≥ 70 %) missed 300 ms.
  - 7a.2: on one hop, most of them were on time (the cost seen in FX.2).
- 7b. Replay, held-out seeds 11–20, scenarios random, mission_mirror and static_good, with and without a shared radio:
  v4.1 against v4.1 + skip (0.5).
  - 7b.1: |ΔsAP| < 0.003 without a shared radio.
  - 7b.2: with a shared radio the skip is ≥ 0.

## Item 10 (paper 2, data-based): more camera hosts

overload_model.py's pull-one-ahead and v4.1 sending rules are checked against the measured two-host pull bench
(1–8 streams), then extrapolated to 3–4 hosts on one channel.

- 10.1: the model's on-time rate is within 15 % of the measured one for pull1 at every stream count.
- 10.2: the v4.1-rule collapse point (≥ 6 streams) is reproduced.

The extrapolation is labelled as model-only.

## Item 9 (paper 2): Theorem 3's overshoot from a two-time-constant model

A two-time-constant thermal model (die and board) is fitted to the temperature and power logs of the 78 °C-guard
runs (heat_nov v41guard). It is then used to predict the overshoot of the held-out 76.5 °C runs (heat_nov2,
heat_final).

- 9.1: the predicted overshoot is within 0.5 °C of the measured 2.4–3.9 °C.
- 9.2: the fast time constant is ≤ 20 s.

## Item 3 (paper 1): a conference version of 6–10 pages

The rule, the hardware check (T10, T11, item 1) and the stress tests as one table. Every number stays generated.

## Item 4 (paper 1): an open feature-coding baseline

Check whether CompressAI-Vision (open source) or an open FCTM build can serve as the MPEG feature-coding baseline on
the laptop. If neither builds and runs within about 2 hours, it stays a stated limitation.

---
# Results (written after each analysis)

## Item 5: verdicts (validation/hardware/equivalence_tost.py -> experiments/results/hardware/equivalence/equivalence.json)

| comparison (pairs) | ΔsAP, 90 % CI | equivalent within ±0.005? | ΔPi W (95 % CI) | Δ time ≥ 80 °C (points) |
|---|---|---|---|---|
| no prices − v4.1, mesh2 (9) | −0.0021 [−0.0035, −0.0008] | yes (TOST p 0.002) | +1.47 ± 0.09 | +92.5 |
| heat − Pi energy price, mesh2 (9) | −0.0002 [−0.0020, +0.0015] | yes (p 0.001) | +0.46 ± 0.08 | +1.8 |
| same, 24 min (5) | −0.0008 [−0.0021, +0.0004] | yes (p 0.001) | +0.34 ± 0.20 | +0.3 |
| final − v4.1, both scenarios (10) | −0.0013 [−0.0032, +0.0005] | yes (p 0.003) | +0.01 ± 0.03 | 0 |
| final − v4.1, one hop (5) | +0.0006 [−0.0019, +0.0030] | yes (p 0.009) | −0.00 | 0 |
| final − v4.1, multihop (5) | −0.0032 [−0.0057, −0.0008] | not shown (p 0.100) | +0.02 | 0 |
| capped hold − hold always, 24 min (5) | −0.0014 [−0.0053, +0.0025] | not shown (p 0.061) | −0.11 ± 0.08 | −17.6 ± 5.3 |
| capped hold + guard − hold always (5) | −0.0017 [−0.0041, +0.0007] | yes (p 0.022) | −0.12 ± 0.08 | −17.7 ± 5.4 |
| budget 2.4 − 2.8 W, both scenarios (6) | −0.0009 [−0.0028, +0.0009] | yes (p 0.003) | −0.35 ± 0.04 | 0 |
| late-path skip − none, one hop (5) | −0.0031 [−0.0153, +0.0091] | not shown (p 0.380) | +0.02 | 0 |
| clock knob − none, 24 min (3) / short (5) | +0.0022 / −0.0047 | not shown (p 0.072 / 0.460) | −0.02 / +0.02 | 0 |

- 5.1 held: equivalent on one hop and on both scenarios pooled; not shown on multihop alone.
- 5.2 held.
- 5.3 narrowly not held: the capped hold alone has TOST p 0.061. The capped hold with the guard is equivalent.
- 5.4 not held, in the better direction: pooled over both scenarios (6 pairs), the 2.4 W budget is shown equivalent.
- 5.5 held: every price or budget change moves power significantly. The clock knob and the skip do not.

Paper 2 now states "same accuracy" only where it is shown, and "not shown" elsewhere.

## Item 8a: verdicts (validation/hardware/calib_recal.py -> calibration/calib_recal_nov16.json)

Fit on 14–15 Nov, tested on the held-out 16 Nov frames (387,075).

- 8a.1 held. ECE on the held-out day falls from 0.057 to 0.0055 (isotonic), 0.0028 (logistic, Platt) and 0.0046
  (10-bin). The second mapping planned as "split-conformal" became logistic (Platt) scaling; the conformal estimate is
  tested in the replay (8b).
- 8a.2 held: the lowest bin maps to 0.645.
- Found: the miscalibration differs by path. Held-out frames predicted late (p_on < 0.5) arrived on time 94 % of the
  time on the Jetson path but 49 % on the laptop path. A per-path isotonic map (ECE 0.0040 Jetson, 0.0066 laptop)
  lifts every such Jetson frame to ≥ 0.5 and 24 % of the laptop's. With a per-path recalibrated p_on, the late-path
  skip would keep the Jetson frames it wrongly skipped on one hop (item 7).

## Item 2: verdicts (experiments/results/literature/published_splits.json; 5 papers, arXiv versions read 16 Nov)

- 2.1 is consistent in all 5 papers, but it is close to a tautology for papers whose latency model is additive. It is
  reported as consistency, not as evidence.
- 2.2 held in all 5: none uses an accuracy-matched image baseline.
  - Uncompressed image: Auto-Split (headline Table 8); raw input tensor: Matsubara & Levorato EMDL 2020.
  - One fixed JPEG quality while the split loses accuracy: Matsubara & Levorato ICPR 2020, whose code reaches 0.355
    against the teacher's 0.370; BottleFit.
  - WebP or PNG at one setting: HECS-B.
- Auto-Split's own appendix quantifies the effect. Against the accuracy-matched JPEG (q60, mAP 0.35) its latency
  advantage falls from 12.5× (against the raw image) to 1.9×.
- HECS-B's split path takes less non-transfer time than its image path (9.30 against 22.15 ms). That is the
  fast-device case where the rule gives no finite break-even, consistent with its table.

## Item 1: verdicts (evaluation/t10_model_check.py, evaluation/jetson_measured_break_even.py)

### 1a. The timing model against the 30 measured cells of the Pi sweep (t10/t10_model_check.json)

- 1a.1 held. Over the 18 cells with ≥ 1 on-time result/s, the median absolute error of the predicted on-time rate is
  7.8 % (r = 0.98 over all 30 cells, median absolute error 0.20 results/s). The large errors are at the deadline edge:
  for example k4_c8 at 2 Mbit/s, predicted 4.16 and measured 0.63 (p90 relative error 198 %).
- 1a.2 held at 5 of 6 goodputs. At 4 Mbit/s the model picked jpeg_q35 and the measurement jpeg_q20. The best family,
  JPEG, was right at all 6 goodputs.

### 1b. A Jetson as the camera, with measured times (video_codecs/analysis_jetson_measured.json)

Measured on the Jetson: codes take 6.6–9.5 ms onboard, against 227 ms on the Pi. JPEG is 7.5× the laptop's time.

- 1b.1, against JPEG: held. The smallest joint code wins below a positive B_be of 9.84 Mbit/s, the rule's scaled
  value, and below 4.8–23.5 Mbit/s for the other codes. There are 218 winning cells. The rule's prediction for a fast
  camera holds on measured times.
- 1b.1, with video in the family: partly held. The window is 1.51–4.40 Mbit/s for the smallest joint code, depending
  on the Jetson's video encode cost, which was not measured. The upper value assumes video is as slow as JPEG
  relative to the laptop (7.5×); the lower one uses the Pi's measured video/JPEG ratio (×0.34). The prediction
  (≤ 2 Mbit/s) held only at the lower end.
- 1b.2 held: 0 exceptions in every family and version (39–75 winning cells with video, 218 without).
- Limit, stated in paper 1: no live sweep with a Jetson camera; video encode times on the Jetson not measured.

## Item 7a: verdicts (validation/hardware/skip_counterfactual.py -> skip_counterfactual/skip_cf.json)

Frames the skip would act on (a network frame with p_on < 0.5 while the other path's latest decision ≤ 0.5 s earlier
had p_on ≥ 0.5), in runs without the skip:

| data | frames acted on (share of network frames) | observed on time |
|---|---|---|
| held out, multihop (mesh4, topology_nov, relaynoise_nov; 11 runs) | 5,908 (19.2 %), all laptop | 46 % (median 315 ms) |
| held out, one hop (13 runs) | 311 (0.3 %) | laptop 66 %, Jetson 31 % |
| design data (final_nov), multihop | 2,464 (16.4 %) | 19 % (median 380 ms) |
| 16 Nov, fix_nov without the skip, one hop: raw p_on | 877 (3.9 %) | laptop 59 %, Jetson 71 % |
| same, p_on recalibrated per path (maps fitted on 14–15 Nov) | 99 (0.4 %) | 15 % |

- 7a.1 not held. In held-out multihop runs only 54 % of the frames the skip acts on missed 300 ms (predicted ≥ 70 %);
  the design data (81 %) overstated it.
  - The skip's measured multihop gain (+0.0151, fix_nov) is therefore not explained by skipping late frames alone.
  - The other measured effect is the relay radio it frees: the Jetson path's median latency fell from 108 to 90 ms.
  - Paper 2 states the mechanism as both, and says the late-frame part is weaker on held-out data.
- 7a.2 partly held. On one hop the skip rarely acts (0.3–3.9 % of frames), and the frames it acts on were often on
  time: Jetson 31–71 %, laptop 59–66 %. This is the measured one-hop cost.
- With a per-path recalibrated p_on (item 8a), the one-hop frames the skip acts on fall from 877 to 99, and 85 % of
  those were late: the recalibration removes almost all wrong skips on one hop, on a day held out from its fit.
  Multihop is unchanged (2,958 → 2,951). This is an offline counterfactual from logs, not a board run.

## Item 10: verdicts (validation/hardware/pull_model_check.py -> overload_handling/pull_model_check.json)

The model's grid (mesh_jetson case) was committed on 13 Nov, before the two-host pull bench of 15 Nov: a genuine
predict-then-measure.

| streams | v4.1 rule: model / measured on-time/s | pull one ahead: model / measured |
|---|---|---|
| 1 | 22.1 / 13.5 | 25.5 / 22.1 |
| 2 | 26.3 / 20.9 | 25.6 / 21.0 |
| 4 | 26.3 / 19.6 | 25.6 / 21.7 |
| 6 | 19.7 / 10.6 | 25.6 / 21.6 |
| 8 | 1.6 / 3.3 | 25.5 / 20.8 |

- 10.1 not held: the model overstates the pull coordinator's capacity by 15–23 % (measured/model 0.84).
- 10.2 held: the shape is reproduced. The pull coordinator stays flat at capacity; the v4.1 rule degrades from 6
  streams and collapses at 8.
- Extrapolation, model only: at 12 and 16 streams (3–4 camera hosts with 4 streams each), the pull coordinator stays
  at 25.6 in the model (about 21.5 scaled by 0.84), and the v4.1 rule delivers 0.

**Change of scope, item 6 (17 Nov, before any result).** The laptop restarted at about 21:35 IST on 16 Nov, during the
sweep, probably from memory pressure with 6 replay processes running. The sweep is resumed with 3 processes,
seeds 1–3 (seeds 1–5 already exist for v4.1 and the capped hold at k = 1) and k ∈ {1.0, 0.9, 0.8, 0.7, 0.6}.
k = 0.5 is dropped: predictions 6.1–6.2 put the threshold at 0.75–0.8.

## Item 9: verdicts (paper2/thermal_two_mode.py -> theory_check/thermal_two_mode.json)

The fit is on the five 78 °C-guard runs (each run with its own intercept): τ_fast = 5 s, τ_slow = 100 s,
b_f = 3.86 and b_s = 9.28 °C/W (steady 13.1 °C/W, against the one-mode fit's 12.7). RMSE 2.3 °C.
The derived bound adds the fast-mode swing of one inference to the guard's reading lag (0.24 s) and one
quantisation step (0.55 °C): δ = 3.2 °C.

- 9.2 held: the fast time constant is 5 s (≤ 20 s).
- 9.1 not held. From each run's logged power, the model's simulated peaks are 2–7 °C below the measured peaks.
  - The derived bound held in 8 of 11 runs.
  - It was exceeded in 3: two of the six held-out 76.5 °C runs (by 0.1 and 0.7 °C) and one fit run.
  - The die swings 5–10 °C within seconds (for example 68.3 → 78.8 → 71.1 °C in 10 s), faster than the 0.24 s power
    log and a linear two-mode model capture.
- Conclusion for paper 2: Theorem 3 (b)'s fast-mode term must be measured on the board (3.9 °C over 8 guarded runs),
  as the paper already states. A model-derived term is not safe. This is reported as a negative result.

## Item 4: verdict

CompressAI-Vision (InterDigital, BSD-3-Clause-Clear; GitHub page read on 17 Nov) is open. It provides MPEG FCM-style
split-inference pipelines.
- It needs the VVC reference codec (VTM, built separately from Fraunhofer HHI's repository) and a Python 3.10
  environment (ours is 3.12).
- Its pipelines support Detectron2 Faster/Mask R-CNN, YOLOX, JDE and SAM, not Ultralytics YOLOv8. Running our
  YOLOv8s split through it would need a model wrapper and a VTM build.
- The FCTM reference software itself is not included.

This is beyond the 2-hour limit set before the check, so the MPEG feature-coding baseline stays a stated limitation
of paper 1, now with these reasons, and CompressAI-Vision is cited as the open route.

Also done (item 2): paper/generated_tables/published_splits.tex, generated from
literature/published_splits.json. Four references were added to paper/references.bib, each checked that day against
Crossref (Auto-Split KDD 2021, BottleFit WoWMoM 2022, Matsubara & Levorato EMDL 2020) or arXiv (HECS-B 2504.15295).

## Item 8b: verdicts

All four predictions of docs/conformal_predictions_nov12.md held; see that file's results section. ECE fell from 0.040
to 0.017, the miss rate among frames sent with p_on ≥ 0.95 is 1.1 %, and ΔsAP = +0.00004 ± 0.00032 over 40 pairs.

## Added 17 Nov (user's question): streaming AP at 15 and 60 fps, and a fix

**The fault.** The T7 summary (vid_campaign_fps_nov_summary.*) had been committed empty. mesh2_summary.py made cells
only for strategies in its fixed ORDER list.
- Fixed: other strategies are appended. Only fps_nov is affected; the final_nov and two_nov summaries regenerate
  byte-identical.
- At 15 and 60 fps the camera plays one clip frame per tick, while stream_ap assumes the dataset's 30-fps timeline.
  Their sAP, mAP and AoI scores (about 0, a negative AoI) are therefore artefacts. The summary now withholds them and
  says so.

**The estimate** (validation/hardware/fps_sap_estimate.py -> hardware/fps_sap_estimate.json). The held result's age is
reconstructed in real time from each run's log, at its own frame period. Its value is acc(variant) × r(age), with r
the measured accuracy-vs-age curve after forecasting. The time average is calibrated on 50 runs at 30 fps from 6
campaigns: r = 0.992, median error 2.8 %, p90 13.9 %.

| camera rate | estimated sAP_fc | held age (median) | fresh | on-time/s |
|---|---|---|---|---|
| 15 fps | 0.189 | 100 ms | 100 % | 14.9 |
| 30 fps | 0.191 (measured 0.197) | 67 ms | 99.3 % | 25.6 |
| 30 fps + encode-ahead | 0.191 (measured 0.196) | 67 ms | 99.1 % | 28.3 |
| 60 fps | 0.192 | 83 ms | 100 % | 31.0 |

With v4.1, streaming AP is flat in the camera rate (within about 1 %, inside the estimate's error). The extra frames
are not sent, and the delivered ones are not fresher: latency rises from 50 to 61 ms. The forecaster flattens the
cost of age. What grows is the Pi's power and heat: 2.13 → 3.18 W and 57 → 67 °C from 15 to 60 fps.

## Item 7b: verdicts (replay_skip.py -> replay/skip_nov16/skip_summary.json; seeds 11–20, 3 scenarios)

| radios | late-path rule − v4.1, sAP (30 pairs) | per scenario |
|---|---|---|
| independent | +0.0000 ± 0.0001 | random +0.0001, mission_mirror −0.0001, static_good +0.0000 |
| one shared radio | +0.0002 ± 0.0002 | random +0.0001, mission_mirror +0.0004, static_good +0.0000 |

- 7b.1 held: |ΔsAP| < 0.003 with independent radios.
- 7b.2 held, marginally: ≥ 0 with a shared radio.
- On held-out replay settings the rule does no harm. It rarely acts there, because the replay has no two-hop relay,
  which is where it pays on the boards.

## Item 6: verdicts (replay_airflow.py -> replay/airflow_nov16/airflow_summary.json; seeds 1–3, k = 1.0–0.6)

24-minute mission with its 4-minute total blackout. Time at or above 80 °C (Pi W):

| k (thermal resistance) | no prices | v4.1 (hold always) | capped hold (78 °C) | capped hold + guard (76.5 °C) |
|---|---|---|---|---|
| 1.0 | 80.1 % (4.80 W) | 18.0 % (3.41 W) | 0 % (3.11 W) | 0 % (3.08 W) |
| 0.9 | 71.6 % (4.73) | 14.2 % (3.40) | 0 % | 0 % |
| 0.8 | 46.5 % (4.56) | 7.7 % (3.36) | 0 % | 0 % |
| 0.7 | 0 % (4.37) | 0 % (3.34) | 0 % | 0 % |
| 0.6 | 0 % (4.37) | 0 % (3.34) | 0 % | 0 % |

The 2-minute mission is hot only for the unpriced controller at k = 1 (7.5 %).

- 6.1 not held: v4.1's hot time vanishes at k = 0.7, not 0.8. Airflow must lower the board's thermal resistance by
  about 30 % (predicted 20 %).
- 6.2 held: the unpriced controller's hot time vanishes at k = 0.7 (predicted ≤ 0.75).
- 6.3 held approximately. The energy price saves 1.03–1.39 W at every k. The saving shrinks a little with airflow,
  because the unpriced controller's own onboard runs get faster when the board is cooler.
- Found: with airflow the capped hold and guard become identical to v4.1 (at k ≤ 0.7 the hold never reaches 78 °C).
  The unpriced controller still trails v4.1 by 0.004 sAP at k ≤ 0.7 with no hot time: in the replay its cost is not
  only heat. This difference is inside the replay's known bias of +0.005 towards less onboard work, so it is not a
  claim.
- Caveat, as for every replay heat result: the replay ranks hot time correctly (r 0.98) but its level is 16 points off
  the hardware's, so the 30 % is an estimate from the measured plant, not a measurement.
