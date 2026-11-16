# Deadline-probability calibration on the hardware (plan B4; 16 Nov 2026)

`validation/hardware/calib_hw.py` over the 16 November-session mesh campaigns (mesh4, energy_nov, relaynoise_nov,
topology_nov, fps_nov, heat_nov, heat_nov2, plus_nov2, two_nov, two_cap, final_nov, heat_final, dvfs_heat, dvfs_short,
budget_nov, fix_nov): 241 runs, 1,482,492 offloaded frames, each with the controller's logged prediction at send time
and the measured latency. Output: `experiments/results/hardware/calibration/calib_hw_nov16.json`. Same bins, ECE and
Brier score as the replay check (Results Brief 19.8).

p_on (chance of meeting the 300 ms deadline) against arrival within 300 ms:

| predicted | frames | mean predicted | observed |
|---|---|---|---|
| 0.0-0.1 | 66,650 | 0.003 | 0.641 |
| 0.1-0.2 | 2,646 | 0.148 | 0.866 |
| 0.2-0.3 | 2,240 | 0.249 | 0.877 |
| 0.3-0.4 | 1,870 | 0.349 | 0.856 |
| 0.4-0.5 | 1,937 | 0.451 | 0.811 |
| 0.5-0.6 | 3,289 | 0.555 | 0.782 |
| 0.6-0.7 | 5,226 | 0.652 | 0.817 |
| 0.7-0.8 | 15,221 | 0.760 | 0.880 |
| 0.8-0.9 | 102,249 | 0.867 | 0.958 |
| 0.9-1.0 | 1,281,164 | 0.975 | 0.992 |
| all | 1,482,492 | | ECE 0.055, Brier 0.045 |

p_late (within 1 s): ECE 0.022, Brier 0.006; observed ≥ predicted in every bin.

Findings:
1. **Never over-confident on the hardware**, as in the replay: in every bin the observed on-time rate is at least the
   predicted one. Errors are on the safe side.
2. **Strongly pessimistic at the low end**: frames predicted at ~0 % arrived on time 64 % of the time (bins 0.1-0.5:
   81-88 %). The Gaussian on the goodput estimate puts too much mass on the slow tail when the estimate is low or noisy.
3. **The F.2 fix acts on this estimate.** Paths it skips (p_on < 0.5) would often have delivered, which fits FX.2's
   small mission-side cost (2 of 5 pairs, lower availability). With the fix on, multihop calibration improves from
   ECE 0.095 (v41final24) to 0.017 (v41fix24), because frames are no longer sent where the estimate is worst.
4. For paper 2: the deadline model is safe but conservative; a calibrated estimate (e.g. isotonic recalibration of
   p_on from the logged pairs) would sharpen both the value and the skip. Stated as a direction, not tested.
