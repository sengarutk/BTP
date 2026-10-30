# Laptop-only additions, part 2 (29 Oct 2026)

Continues `laptop_additions_2026-10-29.md`. Again nothing existing was re-scored or overwritten; every output is new.

## A. Joint link failures: what do they cost, and can better prediction recover it? (replay, 420 runs)

Script `validation/hardware/replay_joint.py` (subclasses the replay of `replay_oracle.py`; `replay.py` unchanged).
Output `experiments/results/hardware/replay/joint_oct29/joint_summary.json`.

**Setup.** The unimpaired static_good scenario (6 × 20 s, per-phase netem reset) plus short deep fades: during a
burst a path's goodput is capped at 0.5 Mbit/s. A transfer's time is integrated over the burst timeline, so a burst
that starts or ends mid-transfer slows only that part.
- **Bursts:** Poisson arrivals, exponential durations with mean 0.3 s or 1.5 s.
- **Correlation:** rho is the share of bursts that hit both paths: 0, 0.5 or 1.
- **Equal marginal:** the total burst rate per path is the same for every rho. Each path is faded 11–15 % of the
  time in every condition (measured), and only the overlap changes: both paths faded 1.5–2 % of the time at rho 0,
  6–8 % at 0.5, and 12–14 % at 1.
- **Common random numbers:** the bursts of a (condition, seed) are the same for every policy.
- **Size:** 10 seeds × 7 conditions (including no bursts) × 6 policies.
- **Policies:** v4.1, clairvoyant v4.1, v5, and fixed laptop m640q90 / Jetson s640q90 / onboard n320. The
  clairvoyant v4.1 knows each transfer's true time, bursts included.

**Check.** With no bursts the runs reproduce the oracle replay bit for bit (static_good, seed 1: identical sAP and
power).

| Condition (rho, mean burst) | both paths faded | v4.1 sAP | v4.1 loss vs no bursts | clairvoyant − v4.1 | v4.1 − v5 | v4.1 − fixed laptop |
| --- | --- | --- | --- | --- | --- | --- |
| no bursts | 0 % | 0.0748 | — | −0.0002 ± 0.0013 | +0.0046 ± 0.0021 | +0.0022 ± 0.0055 |
| 0, 0.3 s | 2.2 % | 0.0728 | −0.0020 ± 0.0018 | −0.0009 ± 0.0011 | +0.0048 ± 0.0027 | +0.0074 ± 0.0043 |
| 0.5, 0.3 s | 8.2 % | 0.0702 | −0.0046 ± 0.0023 | −0.0009 ± 0.0011 | +0.0057 ± 0.0035 | +0.0054 ± 0.0031 |
| 1, 0.3 s | 13.7 % | 0.0694 | −0.0054 ± 0.0019 | −0.0004 ± 0.0023 | +0.0055 ± 0.0022 | +0.0031 ± 0.0040 |
| 0, 1.5 s | 1.5 % | 0.0724 | −0.0024 ± 0.0027 | −0.0004 ± 0.0015 | +0.0054 ± 0.0017 | +0.0102 ± 0.0045 |
| 0.5, 1.5 s | 5.8 % | 0.0705 | −0.0042 ± 0.0026 | +0.0000 ± 0.0011 | +0.0058 ± 0.0028 | +0.0073 ± 0.0038 |
| 1, 1.5 s | 12.3 % | 0.0687 | −0.0061 ± 0.0031 | +0.0002 ± 0.0012 | +0.0075 ± 0.0027 | +0.0073 ± 0.0051 |

(± = Student-t 95 % half-width over 10 paired seeds.)

- **Joint fades cost more than independent fades of the same amount.** v4.1 at rho 1 minus rho 0, with each path
  faded equally often:
  - 0.3 s bursts: −0.0035 ± 0.0016, significant;
  - 1.5 s bursts: −0.0037 ± 0.0039, not significant.

  Two parallel paths hedge independent fades but cannot hedge joint ones. The fixed single-path strategies are
  indifferent to rho, as they must be.
- **Perfect link prediction still adds nothing.** The clairvoyant v4.1 is within ±0.001 of v4.1 in every
  condition, including all-joint bursts. The loss comes from there being no good path, not from mispredicting
  one. Even with perfect knowledge, the only remaining move is onboard inference. v4.1 already makes it: its
  onboard share rises from 3.4 % with no bursts to 5.2–5.5 % at rho 1, and it keeps 98.6–98.9 % of frames fresh.
- **v4.1 degrades least.** Its loss is 0.002–0.006; fixed laptop offloading loses 0.006–0.011. v4.1 beats v5 in
  every condition (significant everywhere), and beats the fixed laptop significantly in 5 of 6 burst conditions (at rho 1 with 0.3 s
  bursts it is +0.0031 ± 0.0040, a tie).

**What this means.** In this replay, a joint-failure-aware or radio-aware controller has no headroom: the
clairvoyant bound is flat. The hardware interference test is still worth running, but as a measurement: do joint
fades occur on the shared channel, and how often? That would size the correlation cost above on real links. It is
not worth running as a route to a better controller, unless the measured fades look very different from these
(for example, the fallback itself failing).

**Limits.** The bursts are synthetic, with a 0.5 Mbit/s cap and exponential lengths. The only onboard fallback is
YOLOv8n-320 (sAP 0.0185 here). The base scenario has no other impairment.

## C. A cheaper camera-motion step for the live forecaster (offline, laptop)

Script `validation/hardware/forecast_cheap.py`. Outputs `experiments/results/hardware/forecast_cheap_oct29.json`
(accuracy) and `forecast_cheap_oct29_timing.json` (timing on an idle machine; the timings in the first file were
taken beside the replay jobs and are not used).

**Why it matters.** On the Pi, the camera-motion step (`egomotion.step`) is the forecaster's main cost: median
7.46 ms per camera frame over 780 live runs, about 22 % of one core at 30 fps. Recording a result takes 1.8 ms and
moving the held boxes to the display time takes 0.28 ms (medians over the same runs). Earlier work found that the live forecaster slows onboard
inference.

**Method.** The step was varied (tracking-image width, corner budget, tracking every second frame); everything else
(forecaster v2 settings, detections) is unchanged. Accuracy is `forecast.replay`: one result every 2 frames, shown
0–600 ms late, mean AP over the lagged settings.
- **Train split** (where the forecaster was tuned) is used to choose.
- **Val split** (the live test clips) is used to report.
- **Check:** the base variant reproduces the stored camera-motion chains exactly (max difference 0.0) and the stored
  tuning result to 4 decimals.

| Variant | train: share of the forecaster's gain kept | val: share kept | step time, laptop (× base) |
| --- | --- | --- | --- |
| base (320 px, 200 corners, every frame) | 100 % | 100 % | 2.22 ms (1.00) |
| 240 px | 99 % | 100 % | 0.87 |
| **160 px** | **99 %** | **98 %** | **0.57** |
| 100 corners | 99 % | 100 % | 0.70 |
| 50 corners | 97 % | 98 % | 0.58 |
| every 2nd frame | 97 % | 88 % | 0.54 |
| 160 px, every 2nd frame | 96 % | 89 % | 0.31 |
| 240 px, 100 corners | 99 % | 100 % | 0.68 |

("Gain" = lagged AP with the forecaster minus without.)

- **Choice (on train):** the cheapest variant that keeps ≥ 99 % of the gain on train is the 160-px tracking image.
  On val it keeps 98 % (lagged AP 0.0432 vs 0.0438) at 0.57× the laptop time. If the Pi scales the same way, that
  is about 7.5 → 4.2 ms per frame, which frees about 10 % of one core. This is an estimate and needs measuring on
  the Pi.
- **Tracking every second frame is the wrong saving.** It costs 11–12 % of the gain on val: an odd frame's one-frame
  camera motion is left uncorrected.
- **Not done (needs a board):** measuring the Pi's step time and the onboard-inference speed-up with `W_SMALL = 160`
  in `egomotion.py`. That is a one-constant change, not made here because it changes what the live system runs.

## B. Decay curve and forecaster on all 56 VID train sequences

Script `validation/hardware/decay_all56.py`. Outputs: `staleness_decay_train56.json` (curves) and
`staleness_decay_train56_replay.json` (controller check). New data: `datasets/visdrone_vid_full/` (the 48 missing
train sequences, from the HuggingFace mirror `huseyincavus/visdrone2019-vid` the 8 came from; about 2 h to
download), prepared into `datasets/visdrone_vid_train56_640/` (first 400 frames per sequence, 17,663 frames), and
detections `forecast_train56_dets.npz`.

**Pipeline.** As `forecast.py decay`: COCO YOLOv8s at 640, one result every 2 frames, the frozen forecaster v2. The
48 new sequences were detected on the laptop GPU; on the CPU three processes took about 3 min per sequence beside
other work.

**Checks.**
- The 8 known sequences reproduce the stored curve exactly.
- The same 8 detected on the GPU give the same curves (largest difference 0.0006).

| Ratio to fresh accuracy, at age | 0 | 100 ms | 267 ms | 400 ms | 600 ms | 1167 ms |
| --- | --- | --- | --- | --- | --- | --- |
| stored (8 sequences), forecaster | 1.000 | 0.854 | 0.603 | 0.452 | 0.304 | 0.041 |
| all 56, forecaster | 1.000 | 0.839 | 0.580 | 0.427 | 0.277 | 0.093 |
| new 48, forecaster | 1.000 | 0.836 | 0.576 | 0.424 | 0.276 | 0.104 |
| stored (8), no forecaster | 1.000 | 0.411 | 0.070 | 0.026 | 0.014 | 0.007 |
| all 56, no forecaster | 1.000 | 0.440 | 0.136 | 0.074 | 0.043 | 0.023 |
| new 48, no forecaster | 1.000 | 0.448 | 0.150 | 0.084 | 0.049 | 0.026 |

- **The curve holds:** within 0.028 of the stored one up to 600 ms (the range of live result ages). Beyond that the
  56-sequence curve keeps more (0.093 vs 0.041 at 1.2 s).
- **The forecaster keeps most of its effect on unseen video:**
  - It adds +0.034 AP averaged over the stale ages on the 48 sequences it never saw, against +0.053 on the 8 it was
    tuned on.
  - Part of the difference is that accuracy decays more slowly on the new sequences, so less is lost.
  - At 267 ms it recovers 50 % of what is lost on the new sequences, against 57 % on the 8.
- **The controller does not depend on it:** v4.1 scheduling for the 56-sequence curve, against the stored curve, in
  the 19.8 replay (4 scenarios × 5 seeds, paired): −0.0002 ± 0.0003 sAP. The 8-sequence measurement was enough.
