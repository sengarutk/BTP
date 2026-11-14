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
  Clarification, 11 Nov 2026, before the session, after an independent audit of paper 2. The testable part is that every
  logged update is one the coded rule allows: a plain step, clipped at zero, raised by the thermal guard, held, or at
  the cap. `paper2/theory_check.py` now classifies each update from the logged values, and on the 376 earlier runs it
  found 0 exceptions in 66,655 updates. The 2.94 / 3.74 W figures assume that no update is held or capped in
  static_good. If some are, the run's own hold and cap terms are added to the limit, and that is reported.
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

## Testbed changes since these predictions were written (14 Nov 2026, before any run of this session)

Recorded before the first run; the predictions above are unchanged. Full log: `docs/mesh_session_nov14.md`.
- **Five boards instead of three.** pi-receiver (a second camera Pi) and Nano2 (Jetson Orin Nano Super) joined the
  mesh. During these three campaigns they run nothing; their only traffic is batman-adv's own messages. Every board
  hears every other directly (batman-adv neighbour tables, 14 Nov).
- **New addresses, same boards.** Camera pi-relayyy is now 10.1.0.11 (was .12), Nano1 10.1.0.14 (was .13), pi-sender
  10.1.0.12 (was .11). The radios (MACs) are unchanged, so the route checks name the same boards. All scripts read the
  map from `tools/mesh_hosts.sh`.
- **Multihop relay kept on Nano1.** With five boards, blocking only the camera ↔ pi-sender link would let batman-adv
  relay through pi-receiver or Nano2 (better link quality than Nano1). `arun_mesh.sh` now also blocks the camera's
  links to those two (temporary nftables rules on four boards, removed at every cleanup). Tested 14 Nov: route via
  Nano1 after 5 s, 20/20 pings at 10.6 ms mean over two hops; direct route back at once after removal; no rule left.
- **Code pushed** (`push_code_mesh.sh`, md5 of every file equal to the repository on all four drones). The boards'
  previous copies are in `~/hwbench/_prev_20261114/`.
- **energy_constants.json.** The boards had the 8 Oct version (Pi thermal fit 34.43 + 12.73 P), the one every earlier
  heat-priced run used; the repository's has the 28 Oct fit (37.26 + 11.31 P). The repository's was pushed. It
  changes only the heat price's forecast, which no strategy of these campaigns uses. P2.2 is about the board's real
  temperature and keeps its stated fit.
- **Wi-Fi power save** reads "on" on the camera Pis, as during mesh campaigns 1-3 (`arun_mesh.sh` never changed it).
  Switching it off on pi-receiver changed nothing in a ping test (mean RTT 5.6 vs 5.6 ms), so in this ad-hoc mode it
  has no effect; it was left as found.
- **Clocks.** The mesh has no time source: pi-sender is 25 min behind the laptop, Nano1 36 s ahead, the others within
  0.4 s. Every latency is measured on one board's clock, so no measurement is affected; the offsets are logged by
  `tools/mesh_health.sh` and not changed.

## After the session

Add one line per prediction: held / did not hold, the measured value, and the result file. A prediction that did
not hold is reported as such in the papers.

### Results: energy test (`vid_campaign_energy_nov/`, 12 runs, 14-15 Nov 2026, pi-relayyy)

- **P2.1 held.** v41 2.87 / 2.80 / 2.81 / 2.80 W (limit 2.94); v41b36 3.58 / 3.59 / 3.59 / 3.57 W (limit 3.74).
  The update-by-update check (`paper2/theory_check.py`) is to be run on these runs.
- **P2.2 did not hold.** Second-half mean temperature: v41 63.3 / 63.8 / 61.4 / 60.9 °C against 69.7-71.6 °C from
  34.43 + 12.73 P (second-half power); v41b36 73.3 / 72.1 / 71.8 / 68.7 °C against 80.2-80.4 °C. Every run is 7-11 °C
  below, outside ±3 °C. Between the two budgets the measured rise (~9 °C) is close to the fit's (~10 °C): the
  intercept, not the slope, differs. The fit is the original Pi's (Oct, Wi-Fi testbed, daytime); this is
  pi-relayyy at night (22:10-00:15). pi-receiver's own levels (14 Nov) were also ~8-10 °C below the fit. So the
  proposition needs a per-board (and room) intercept; as stated with the fixed fit, it failed.
- **P2.3 partly held.** freshonly 4.66 / 4.76 / 4.59 / 4.83 W (predicted about 4.2); second-half mean 83.3 / 81.9 /
  79.2 / 81.2 °C (above 80 °C in 3 of 4); throttled 7 / 2 / 0 / 2 % of the time (firmware flag), not a "sizeable
  share" (the unpriced reference had 13 %); v41 never throttled (0 % in all 4 runs; peaks 67.8-72.2 °C).
- **P2.4** pending the sAP scoring.
- Run 4 (`static_good__freshonly__r2`) was lost when the laptop shut down on a critical battery at 22:35 (archived
  with the reason in `_superseded/vid_campaign_energy_nov_wsl_down/`) and re-run at 23:07.
