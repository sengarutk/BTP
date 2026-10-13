# Campaign A (plan part A) — work log, 12 Oct 2026

## Hardware campaigns
- `vid_campaign_long/`: 24-minute runs (6 phases × 4 min, scenario mission), v5.1 / v5 / v4.1 / v4.2 /
  v3+fc2 / fixed laptop × 2 repetitions, live power on both boards. Started 19:03.
- `vid_campaign_table/`: same-day comparison table, v5 / v5.1 / v4.1 / onboard-only × 4 scenarios × 5
  repetitions (20-s phases). Queued after the long runs.

## Faults found by the long runs (none affects an earlier 20-s campaign; each checked)
1. **Worker gave up during long outages** (adaptive.py worker): it stopped reconnecting after 60 failed
   attempts (~70 s); a 4-minute blackout phase therefore ended the laptop worker and the run. The first three
   long runs were invalid (set aside in `_superseded/long_worker_giveup/`). Fix: give up only after
   `--give-up-s` (1800 s) without a connection, clock restarted when a connection ends. Earlier campaigns:
   longest single-path blackout 40 s (computed from scenario_phases for every seed), below 70 s.
2. **Dual-price windup** (adaptive2.py): during a forced onboard period (blackout exemption, onboard unpriced)
   the energy price μ kept integrating an unattainable budget, reaching 41 in a 90-s blackout, and then priced
   out offloading after the links returned (drone stuck on onboard YOLOv8n). Fix (anti-windup): μ frozen while
   the exemption is active; μ and μ_edge capped at `--mu-max` 5; λ_F capped at `--lam-f-max` 2. Verified on
   hardware with 90-s phases: both links used again after the blackout. In 20-s runs the windup was bounded
   (≈ 6 at most).
3. **Result file copied before complete** (adaptive2.py): the JSON was written several times (and the
   _dets/_livefc files after the first write); the campaign copies the run as soon as the JSON exists. Long
   runs write ~10 MB and a truncated copy was fetched. Fix: the JSON is written once, last, atomically
   (temporary file + rename), after all other files. Earlier campaigns: every run file, detections and
   live-forecast file loaded completely during scoring.
4. **Wi-Fi power saving re-enabled on the Jetson** (network manager reconnect). Fix: arun.sh switches it off
   on both boards before every run.

## Fault in the network emulation, present in every campaign (found 12 Oct, 22:00)
`adaptive.tc_phase` applies each phase with `tc qdisc change ... netem <phase args>`. Checked on the Pi with
a dummy interface: netem then **resets loss but keeps the previous rate limit** when the new phase sets none.
So a phase described as unimpaired after a rate-limited phase was still rate-limited:
- mission: the final "recovered" phase kept laptop 2 Mbit/s and Jetson 1.5 Mbit/s (from "both degraded");
  "ground blackout" kept the 3 Mbit/s limit (irrelevant under 100 % loss);
- mission_mirror: the final phase kept laptop 1.5 / Jetson 2 Mbit/s;
- random: an "unimpaired" state kept the last rate limit;
- static_good: never limited — correct.

Consequences:
- **All policy comparisons remain valid**: every policy in a campaign ran the same scenario and seed, so the
  same (true) sequence of conditions. Only the scenario descriptions were wrong.
- **Retracted finding**: "after a blackout the real link stays slow (latency 389 ms, the simulator does not
  capture it)". Those phases were rate-limited. Re-running the simulator check with the true conditions
  (`sim_vs_real.py --stop-and-wait --netem-persist`): r = 0.947 and mean error 1.57 results/s over **all 528
  phases** (before: 0.906 excluding the "post-blackout" phases, 0.80 including them). The simulator matches
  the hardware with no exception.
- The replay tool now models the persistence (validation re-run).
- Tonight's two campaigns keep the same emulation so that they stay comparable with every earlier campaign.
  For new scenarios (mesh), tc_phase will set every phase's full state (to be changed after these campaigns).

## Laptop results
- Decay for other detectors (decay_context.py, DECAY_MODEL): YOLOv8n / s / m keep 38–39 % / 11–14 % at
  100 / 267 ms without forecasting and 81–82 % / 51–54 % with forecaster v2, although their fresh AP differs
  1.7×; with alignment the fast-camera penalty disappears for every detector. One curve per forecaster serves
  any of these detectors.
- Replay tool (replay.py) built and validated against the 240-run main campaign; first validation (before the
  two fixes below): accuracy r = 0.96, Pi power r = 0.99, but paired verdicts against v5 agree only 5/11.
  Fixed: (a) policy-dependent random streams seeded with Python's hash() (randomised per process) → common
  random numbers per seed; (b) the netem persistence above. A wrong heating time constant (14.5 s from a
  transient) was replaced by the measured 148.8 s (clean heating steps fit 137–146 s).
