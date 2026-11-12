# Removing the replay's bias (paper 2, roadmap L7): diagnosis and predictions before the runs (12 Nov 2026)

## The problem

The trace replay is validated against the 240-run main campaign (validate_main_oct30_power_t85). It ranks policies
well (r = 0.957), but some policies come out too high:

| Policy | Replay − hardware sAP |
|---|---|
| reward_offload | +0.0078 |
| conf_trigger | +0.0075 |
| jsq | +0.0065 |
| LEAF | +0.0059 |
| v5 | +0.0006 |
| fixed laptop | −0.0012 |

LEAF's error is the one that matters: the replay puts it +0.0049 ahead of v5, where the hardware measured a tie. This
error is why the AccuMO-style planner and the LEAF-style weight cannot be ranked against v4.1.

## Diagnosis (from the logs, before any change)

1. **Pi CPU contention.** The overestimate tracks the share of time the Pi runs onboard inference (correlation 0.81
   over the 12 policies). Offloads dispatched while onboard inference runs take a median 6-14 ms longer (mean 8-25 ms)
   in the Wi-Fi campaigns, and 1-6 ms on the mesh. This is confounded: onboard is chosen when the links look worse. It
   explains the three literature baselines (onboard busy 73-83 % of the time), not LEAF (20 %, like v5).
2. **The Jetson path is over-used in the replay.** In static_good, where neither policy goes onboard, the replay sends
   10.3 Jetson frames/s for LEAF against 6.1 on the boards (+70 %), and 8.6 against 5.3 for v5 (+60 %).
   - LEAF has no Jetson energy price (v5 and v4.2 have one), so it leans on the Jetson most and gains most.
   - The replay draws the two paths' goodputs independently. On the boards both paths share the Pi's one radio, so a
     frame sent while the other path is transmitting gets only part of the airtime.

## Two switches (default off: every stored replay result reproduces exactly)

- `--contention-ms D`: an offload dispatched while onboard inference runs starts D ms later.
- `--shared-radio`: a transfer that starts while the other path is transmitting gets half the drawn goodput.

## Procedure

Policies are split into two halves, each with v5 as the paired reference:
- Fit: v5, v42, v5_exp, conf_trigger, jsq, aoi_thr.
- Held out: v5_lin, v5_flat, v5_nofc, leaf, reward_offload, fixed_laptop_m640q90 (v5 also run).

1. The fit half is replayed for D in {0, 10, 20, 40} ms, each with and without the shared radio (8 settings).
2. The setting with the smallest mean |replay − hardware| sAP on the fit half is chosen.
3. Only that setting is replayed on the held-out half; it is judged there.

## Predictions

1. The shared radio reduces the Jetson over-use in static_good from +60-70 % to within 25 %.
2. The chosen setting includes the shared radio and D of 10-20 ms.
3. On the held-out half, the mean |replay − hardware| sAP falls by at least 30 %. LEAF's lead over v5 in the replay
   falls from +0.0049 to at most +0.0025 (the hardware has it at −0.0004).
4. The correlation of policy means stays at least 0.95.

If prediction 3 fails, the replay keeps its stated bias and the planner comparison stays unresolved; we say so.
