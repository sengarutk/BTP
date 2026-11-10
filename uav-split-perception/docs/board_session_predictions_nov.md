# Predictions for the board session (written 10 Nov 2026, before any of these runs)

Hardening plan, Phase 5. These predictions are fixed in the repository (see this file's commit date) before the
half-day board session, so the session can confirm or refute them. Every number below comes from an existing result
file, named in brackets. After the session, each prediction gets a "held / did not hold" line with the measured value;
nothing above that line is edited.

Run order for the session (about 5 h): setup and health check (1 h), then the three campaigns below.
`push_code_mesh.sh` must copy the new `adaptive2.py` (scenarios `multihop_loss2`, `multihop_loss5`) to the camera Pi
first, and `arun_mesh.sh` has the new strategies `freshonly` and `v41b36`.

## 1. Planner campaign: v4.1 vs the AccuMO-style planner vs the LEAF-style fixed weight

`REPS=2 tools/campaign_mesh4.sh`: static_good, mesh_mission and multihop × 3 strategies × 2 reps = 18 runs.

Replay prediction (planner minus v4.1, streaming AP with forecaster) [paper2/generated/metrics.tex, from
replay/accumo_oct29 and heldout_power_oct30]: +0.0018 ± 0.0019 on the mission, +0.0044 ± 0.0019 under random faults
(+0.0045 on held-out seeds), +0.0014 ± 0.0008 over 24 minutes; the LEAF-style weight +0.0022 to +0.0053. The replay
favours policies that run less onboard by +0.0053 [ReplayLeafBias].

- **P1.1** On the boards the planner and v4.1 differ by less than 0.01 sAP in every scenario, and no difference is
  significant with 2 repetitions (Holm-corrected permutation tests).
- **P1.2** The planner's and the LEAF weight's small replay lead (≤ 0.0053) does not appear as a consistent lead on
  hardware, because it is within the replay's known bias.

## 2. Energy test: the energy price on and off, paths fixed

`tools/campaign_energy_nov.sh`: static_good, 6-minute runs, v41 (2.8 W budget), freshonly (no energy price),
v41b36 (3.6 W budget) × 4 reps = 12 runs.

Theory [paper2 Theorem 1 and Proposition 1; theory_check/theory_check.json, plant fit 34.43 + 12.73 P °C]:
with no blackout (held term 0) and 360 price updates, the price term is at most 5/(0.1 × 360) = 0.14 W.
Reference runs [vid_campaign_mesh2_summary.json, static_good]: v41 2.83 W, 70.2 °C, never throttled, sAP 0.2057;
no prices at all 4.24 W, 82.3 °C, throttled 13 % of the time, sAP 0.2028.

- **P2.1 (Theorem 1)** Every v41 run averages at most 2.94 W (2.8 + 0.14), and every v41b36 run at most 3.74 W.
  The bound holds on every logged update sequence (it is an identity plus a sign argument).
- **P2.2 (Proposition 1)** Second-half mean temperature within ±3 °C of 34.4 + 12.7 × (mean power): about 70–71 °C
  for v41, about 80 °C for v41b36 (at most 82 °C).
- **P2.3 (mechanism)** freshonly runs like the unpriced controller: about 4.2 W, a mean above 80 °C and throttling
  in a sizeable share of the run, while v41 never throttles. Above the throttle limit the linear model does not apply
  (the firmware holds the board near 85 °C), so P2.2 is not claimed for freshonly.
- **P2.4 (accuracy)** The three strategies' streaming AP differ by less than 0.01: the energy price costs no accuracy.

## 3. Noisy relay

`tools/campaign_relaynoise_nov.sh`: multihop route with 2 % or 5 % loss and 5 ± 5 ms delay on both hops; v41, the
hierarchical chain (hier) and fixed laptop offloading × 2 reps = 12 runs.

Correction, 11 Nov 2026, before any run of this campaign (found in the laptop dry run): the camera's netem cannot act
on the Jetson's batman-adv forwarding, so in the first version the relayed laptop path of v41 and fixed offloading
got the noise of one hop while the hierarchical chain's forwarded frames got two. The laptop path now carries the
two-hop equivalent (loss 1 − (1 − x)², i.e. 3.96 % and 9.75 %, delay 10 ms with 7 ms jitter); the Jetson path and the
edge node's uplink carry one hop each (`adaptive2.py`, scenarios `multihop_loss2/5`). The predictions below are
unchanged.

Reference, noise-free multihop [vid_campaign_mesh2_summary.json]: hier 0.1506, v41 0.1373, fixed laptop 0.0672 sAP
(only 12.5 % of its results on time). Simulator sweep [experiments/results/relay_noise/summary.json, written on the
same day]: see that file for how relay loss changes the relayed frames' on-time share and the strategy order.

- **P3.1** The order stays hier ≥ v41 > fixed laptop at both loss levels.
- **P3.2** Fixed laptop offloading falls further below its noise-free 12.5 % on-time share; v4.1 and hier keep more
  than 95 % of their results within the deadline by moving work to the Jetson or onboard.
- **P3.3** Every strategy loses streaming AP against the noise-free multihop runs, more at 5 % than at 2 %; the
  adaptive strategies lose less than fixed offloading in absolute terms.

## After the session

Add one line per prediction: held / did not hold, the measured value, and the result file. A prediction that did
not hold is reported as such in the papers.
