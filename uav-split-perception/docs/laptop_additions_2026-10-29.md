# Laptop-only additions, 29 Oct 2026

Three checks that needed no boards, plus one logging change for the next campaign. Nothing existing was
re-scored or overwritten; every output is a new file. In the Results Brief as 19.8 (`scripts/report_laptop_oct29.py`).

**Update, later on 29 Oct:** the replay's heat model was fixed (section 5) and items 1–2 re-run with it
(`replay/oracle_oct29_plant/`). The numbers below are from that run. They match the first run (`oracle_oct29/`)
to 0.1 %; only the mirror's schedule share moves from 97.4 to 97.3 %, and in both_degraded the oracle's pick
becomes fixed onboard YOLOv8s-640. 40 of the 380 rows change, all of them fixed-onboard runs, by at most 0.0007 sAP.

## 1. How far is v4.1 from the best possible schedule? (replay, 380 runs)

Script `validation/hardware/replay_oracle.py` (uses `replay.py` unchanged). 4 scenarios × 5 seeds, 20 s phases,
per-phase netem reset, COCO detectors with forecaster v2 (the replay's detections), common random numbers.
Output `experiments/results/hardware/replay/oracle_oct29_plant/oracle_summary.json` (first run, before the
heat fix: `oracle_oct29/`).

| Scenario | v4.1 sAP | clairvoyant v4.1 | gain | best fixed config | v4.1 − best fixed | v4.1 / per-phase schedule oracle | v4.1 / per-seed oracle |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mission | 0.0577 | 0.0577 | +0.0000 ± 0.0011 | Jetson s640q90 0.0479 | +0.0098 ± 0.0055 | 98.2 % | 96.5 % |
| mission_mirror | 0.0631 | 0.0633 | +0.0002 ± 0.0010 | laptop m640q90 0.0597 | +0.0034 ± 0.0024 | 97.3 % | 95.5 % |
| random | 0.0491 | 0.0503 | +0.0012 ± 0.0030 | Jetson s640q50 0.0399 | +0.0092 ± 0.0080 | 88.2 % | 77.5 % |
| static_good | 0.0755 | 0.0755 | +0.0000 ± 0.0021 | laptop m640q90 0.0702 | +0.0053 ± 0.0117 | 99.8 % | 96.1 % |

(± = Student-t 95 % half-width over the 5 paired seeds.)

- **Clairvoyant** = v4.1 that knows the exact goodput its next transfer on each path will get. **Perfect link
  prediction adds nothing to sAP** in any scenario (all gains inside the interval). It only shortens the longest
  stale stretch (0.39 → 0.07 s) and raises the fresh share slightly (99.4 → 99.6 %). So, under the fault types we
  emulate (rate caps, full outages, real goodput stretches), a better link predictor (radio-aware, conformal) would
  not raise accuracy.
- **Per-phase oracle** = with hindsight, the best of {v4.1, all 17 fixed configurations} in each phase. It is
  optimistic: phase changes are free, and the choice is made on the same data it is scored on (the per-seed
  version takes the maximum of noisy values). v4.1 reaches **97–100 %** of the schedule oracle in the mission,
  mirror and static scenarios. In the random scenario (4 s phases, impairment changing every phase) it reaches
  88 % (77 % of the per-seed bound, which is inflated most by noise in 4 s phases). That is where headroom is.
- **Where the oracle beats v4.1**: in total blackout it prefers fixed onboard YOLOv8n-320; with both links
  degraded fixed onboard YOLOv8s-640; in the mission's ground blackout a fixed Jetson configuration; in the
  mirror's edge-impaired phases a fixed laptop configuration. These gaps are small; v4.1 beats the best single fixed configuration in every scenario
  (significant in mission, mission_mirror and random; not in static_good).
- None of these is a proven optimum (the exact per-frame optimum is intractable). They bound what better
  prediction or better per-phase configuration could add.

## 2. Are the deadline probabilities calibrated? (replay, 44,524 offloaded frames of v4.1)

| Predicted p_on (300 ms) | frames | mean predicted | observed on time |
| --- | --- | --- | --- |
| 0.5–0.6 | 211 | 0.574 | 0.744 |
| 0.6–0.7 | 554 | 0.652 | 0.861 |
| 0.7–0.8 | 1,216 | 0.762 | 0.933 |
| 0.8–0.9 | 5,696 | 0.863 | 0.978 |
| 0.9–1.0 | 36,840 | 0.969 | 0.991 |
| all | 44,524 | 0.944 | 0.985 |

Expected calibration error 0.042 (p_on) and 0.041 (p_late, 1000 ms). **The Gaussian estimate is pessimistic, never
over-confident**: frames arrive on time more often than predicted, in every bin with more than 7 frames. Combined
with item 1, the pessimism costs no accuracy. This is the replay's link model; the hardware check needs the new
per-frame logging (item 4).

## 3. Worst-phase sAP and staleness of every hardware campaign (existing scores)

Script `scripts/report_worstphase_oct29.py` reads the per-run caches of `report_rescore.py`. Outputs
`experiments/results/hardware/worst_phase_oct29.{json,md}` (VisDrone detectors) and `_coco` (COCO).

- **Worst-phase sAP does not separate the policies**: 0 of 169 paired comparisons (VisDrone) and 0 of 169 (COCO)
  are significant after Holm. The policy first by worst phase often differs from the one first by mean (21 of 29
  campaign scenarios with VisDrone, 19 of 29 with COCO), but those are point estimates, none significant.
- The reason: the worst phase is set by the video content shown in it (e.g. `good3` in static_good, where every
  link is unimpaired; `both_degraded` in the mission), the same clip for every policy.
- **Staleness does separate them.** Same-day table, mission: v4.1 holds a result older than 300 ms for 1.4 % of
  frames (longest stale stretch 1.05 s); v5 for 16.0 % (2.83 s); v5.1 for 1.3 %. This is the freshness price at
  work and is already the brief's freshness result, now on the standard staleness measures.
- Recommended for the paper: report the miss rate and the longest stale stretch next to mean sAP. Report worst-phase
  sAP once, with the finding that it is content-dominated.

## 4. Per-frame prediction logging for the next hardware campaign

`validation/hardware/adaptive2.py`: every frame sent to a path now records
`pred = {p_on, p_late, r_mbps, s_mbps, L_ms}`, the controller's own prediction at decision time (new function
`path_pred`, same formulas and estimates as `path_value`, no side effects). Decisions are unchanged. Checked:
`path_pred` p_on equals `path_value` p_on in 140 mock cases (both paths, all variants, 5 link states, with and
without a coordinator share); all 118 tests pass. Not yet run on a board.

## 5. Found while doing this: the replay's heat model after the 28 Oct thermal fix

The replay was re-validated against the 240-run main campaign with the current constants
(`replay/validate_main_oct29/replay_check.json`):

| Agreement with hardware | before 28 Oct | now |
| --- | --- | --- |
| sAP (Pearson) | 0.948 | 0.943 |
| Pi power (Pearson) | 0.990 | 0.990 |
| paired verdicts vs v5 | 9 of 11 | 8 of 11 |
| time at ≥ 80 °C (Pearson) | 0.962 | 0.532 |

The new fit (37.26 + 11.31 °C/W, from the levels below 80 °C only) is right for the steady temperatures it
replaced. But it predicts lower temperatures at high power, so the replay now almost never reaches 80 °C: 0–2 % of the
time for every policy, against 5–22 % on hardware for the v4/v5 family and 60–72 % for the onboard-heavy baselines
(conf_trigger, jsq, reward_offload). The replay therefore also understates how much throttling slows those
baselines' onboard inference; their verdicts (worse than v5) still agree with hardware.

**Fixed (29 Oct).** `replay.py` now keeps two models, as on the hardware: the board's temperature follows a fit
over every unthrottled 6-min level, including the 83.8 °C one (`replay.load_all` -> `thermal_plant`,
T = 34.43 + 12.73 P, computed from `thermal_steady_pi.json`), while v5's heat price keeps using the controller's
own fit (`thermal_steady`, below 80 °C). At 4–5 W the board fit is 2–5 °C warmer than the controller's fit, but
it is the one that reproduces the time in the hot range. Re-validated against the same 240 runs
(`replay/validate_main_oct29_plant/replay_check.json`): sAP r 0.947, Pi power 0.990, time at ≥ 80 °C **0.962**,
verdicts 9 of 11. These are the same values as before 28 Oct. The replay still understates the *size* of the
baselines' heat (replay / hardware: conf_trigger 5 / 60 %, jsq 9 / 69 %, reward_offload 8 / 72 %), because it
gives them 0.4–0.7 W less power than measured. Replay heat results are therefore comparisons, not absolute
values. The pre-fix `replay.py` is archived in `_superseded/report_before_laptop_oct29/`.

## What this means for the plan

- A better link predictor is **not** worth building for the current fault types: perfect prediction adds nothing.
  Prediction work only pays if real interference behaves differently from what we emulate (bursty, both paths at
  once). The interference/joint-failure test therefore remains the one novelty item, and the replay cannot answer
  it (its two paths draw goodput independently).
- "v4.1 reaches 97–100 % of a hindsight per-phase oracle and gains nothing from a clairvoyant link" is a strong,
  new claim for the paper (replay-based, labelled as such).
- The replay's thermal fit is fixed (section 5); its heat results are usable as comparisons.
