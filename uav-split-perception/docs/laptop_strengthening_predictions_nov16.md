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
