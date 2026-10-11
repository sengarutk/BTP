# Phase G completion — work log

Log of the Phase G follow-up work (system-level energy: pricing the edge drone, live Jetson
logging, energy-aware coordination, system-level rescoring, Part 15 correction, campaigns).
Every number below traces to a measured file or a run; nothing is estimated by hand.

## Grounding: the measured constants this work prices with (energy_constants.json, from
energy_profile_{pi,jetson}.json / thermal_steady_pi.json — all measured on the boards)

- Pi 5 (camera drone): idle 1.894 W; infer J/frame n320 0.324, s320 0.741, s640 2.229;
  encode J/frame ~0.005–0.007; radio tx 0.211 W + 0.016 W per Mbit/s; forecaster 0.294 W.
- Jetson Orin Nano (edge drone, clocks locked): idle 4.079 W; infer J/frame
  n320 0.040, s320 0.067, s480 0.110, s640 0.163, m640 0.371; radio rx 0.211 W.
- Drone classes (momentum-theory hover + published battery): mini_249g 33.5 W flight / 17.3 Wh;
  quad_1.2kg 109.9 W / 59.2 Wh usable; edge_1.5kg 153.6 W / 88.8 Wh usable.
- Verification of the user's table against energy_campaign_summary.json (100-run campaign):
  A_eco_tight sAP 0.0543 / Pi 3.33 W / edge 4.94 W; A_stream_fc2 0.0470 / 4.47 / 4.84;
  A_full 0.0465 / 4.24 / 4.93; fixed_laptop_m640q90 0.0463 / 2.65 / 0. Edge *extra* work
  (minus 4.08 W idle) ~0.86 W. All figures reproduce.

## Design decisions

1. **v4.2 (this work) = v4 + an edge-drone energy price.** New dual variable mu_edge with its
   own budget, subtracted as `- mu_edge * E_edge(s, v)` from the jetson path's value in both
   objectives. E_edge = measured Jetson J per inference for the variant + radio receive J.
2. **mu_edge ascent is on the edge drone's EXTRA power, not its whole-board power.** The
   Jetson's 4.08 W idle floor is real but must not make mu_edge diverge when the path is idle:
   the error term is max(0-measured-extra) vs the budget, so with budget 0 mu_edge rises only
   while the Jetson is actually serving and decays when it stops (clip at 0).
   **[Corrected 11 Oct — this was wrong]** with budget 0 the step is eta·(p_extra − 0) ≥ 0, so mu_edge can
   never decay: it ratchets up while the Jetson serves and stays there, pricing the Jetson out for the rest
   of the run. The budget must be > 0 (default now 1.0 W; campaign 0.5 W binding / battery-derived).
3. **Live edge power in the loop.** The Jetson worker reports its measured board power
   (INA3221 VDD_IN) in every response header (`--report-power`); the camera EWMA-s it
   (Path.edge_w). mu_edge prefers this live measurement (baseline-corrected by the measured
   idle) and falls back to the modelled served-energy rate between reports. The separate
   5 Hz power_logger (JLOG) still logs every run independently.
4. **Budgets derived from battery + flight power when asked**: budget_w =
   60 * battery_wh * usable / mission_min - flight_w (clamped >= 0); per drone class.
   Camera default class mini_249g, edge class edge_1.5kg. Hand-set values still win when given.
5. **Coordinator energy preference is a flag, not a guess**: --energy-pref low|high|off.
   `low` admits the lowest-SoC cameras first (max-min lifetime under the measured cost
   structure: offload ~0.8 W vs onboard ~2.7 W above idle), `high` the literal
   "more battery left" reading, `off` = today's round-robin. The campaign measures both.
   Cameras report modelled SoC (from measured board power + drone class) and their mu.
6. **System views in rescoring** (three, explicitly labelled, no mixing):
   (a) extra: camera W + edge extra W (infer + rx only; edge drone flies anyway);
   (b) board: + the Jetson's whole board power incl. 4.08 W idle;
   (c) dedicated: + edge flight power 153.6 W (edge drone flies only for perception).
   Plus per-drone endurance and swarm lifetime = first drone to land.
7. **Energy penalties now apply in both objectives.** v4 subtracted mu only in the stream
   objective; no campaign ever ran energy-aware with the rate objective, so extending the
   penalty to it changes no past result and makes v4.2 consistent.

## Changes

(all edits are in `validation/hardware/`; every file below was read in full before editing)

1. **adaptive.py** (worker + Path, shared by all controllers):
   - worker: new `--report-power jetson|pi` — the worker reads its own measured board power
     (Jetson: INA3221 VDD_IN via energy_profile.read_power; NaN/failure → header value null) and puts
     `board_w` in every response header.
   - Path._receiver: EWMA (0.8/0.2) of the worker-reported `board_w` into `Path.edge_w` (+ timestamp
     `edge_w_t`), so the camera always has a fresh, measured edge-drone power estimate in the loop.
2. **adaptive2.py** (controller v2/v3/v4/v4.1/**v4.2**):
   - CLI: `--edge-energy-aware`, `--edge-power-budget` (default: sentinel → derived), `--edge-eta 0.1`,
     `--mission-min`, `--camera-drone-class mini_249g`, `--edge-drone-class edge_1.5kg`;
     `--power-budget` default is now a sentinel too — derived from battery + flight power when
     `--mission-min` is given (60·Wh/min − flight W, clamped ≥ 0), else the old 3.0 W.
   - power_logger thread: alongside the camera μ ascent, a **μ_edge ascent on the edge drone's EXTRA
     power** (worker-reported board_w − measured idle 4.079 W when fresh ≤ 2 s, else the modelled
     served-energy rate over a 5 s window; both sources logged), step `--edge-eta·(p_extra − budget)`,
     clipped ≥ 0. Also models the camera drone's state of charge (measured power + drone class).
   - `e_edge(s,v)`: measured Jetson J per inference for the variant + radio-rx J — the term the
     objective prices.
   - path values: `− μ_edge·e_edge(s,v)` on the jetson path in the **stream objective** (v4 priced only
     the camera) and both μ and μ_edge in the **rate objective** (v4 priced nothing there; no past
     campaign ran energy-aware with rate, so no past result changes meaning).
   - dispatch site records each served frame's edge energy (for the modelled fallback); the
     coordinator report now carries `soc`, `mu`, `edge_w`; the run output adds `mu_edge_log`
     (t, μ_edge, p_extra, source), `edge_budget_w`, `edge_reported_w`, `soc_model_end`.
3. **coordinator.py**: `--energy-pref low|high|off`. When K < N cameras get the laptop path, `low`
   admits the lowest-SoC cameras first (max-min lifetime), `high` the highest-SoC first, `off` the
   previous round-robin (controlled baseline). soc comes from the cameras' reports; the flag is logged
   into the coordinator output.
4. **energy_model.py**: `system_views()` — the three labelled system views per run (extra / board /
   dedicated, see decision 6) as joules and mean watts; `swarm_lifetime_min()` — per-drone endurance
   and swarm lifetime (first drone to land); run_energy_v1 now also returns its edge breakdown (v1
   runs previously summed the edge drone's energy without a breakdown, which the system views need).
5. **energy_rescore.py**: every run of every campaign now also gets system_w/j_{extra,board,dedicated},
   sAP per system watt in each view, edge-drone flight time (endurance at its measured board power +
   153.6 W flight), swarm lifetime and swarm mission perception (sAP × swarm lifetime), per camera
   drone class. Summaries carry all of it with 95 % t-intervals.
6. **tools/arun.sh / arun2.sh**: the Jetson worker is launched with `--report-power jetson` (live board
   power in every response, every run); arun2's coordinator takes `EPREF=low|high|off`.
7. **tools/campaign_energy.sh** (new): the Phase G campaign — A_eco42 (v4.2, camera budget 2.8 W for
   direct comparison with v4/v4.1, edge budget 0 = dedicated edge drone), A_eco42d (v4.2 with the
   camera budget DERIVED from the mini_249g battery + flight power at a 28-min mission = 3.57 W),
   A_eco41, A_eco_tight (v4), A_stream_fc2 (v3 + forecaster v2), fixed_laptop_m640q90; 4 scenarios ×
   REPS (default 5) × 6 policies = 120 runs, shuffled per rep, resumable, outage guard; **JLOG=1 and
   POWERLOG=1 on every run** (power_logger on the Jetson + measured power log on the Pi camera).
8. **tools/heat_run.sh** (new): the 24-minute heat run — thermal_steady.py on the Pi with
   `--level-s 1440` (every load level held 24 min: idle, forecaster, JPEG encode, YOLOv8n-320 at duty
   0.15/0.3/0.5/1.0), 10 Hz power/temperature/ARM-clock logging, result fetched to
   experiments/results/hardware/energy/thermal_steady_pi_24min.json.
9. **tools/push_code.sh** (new): pushes the live-run code + config JSONs to both boards' ~/hwbench
   (never touches results/), to run once before the campaign (the Jetson was reflashed, so its
   ~/hwbench must be verified/re-created too — see Prerequisites below).

## Prerequisites before any live run (the Jetson was reflashed)

- Jetson (192.168.0.188): ~/hwbench SURVIVED the reflash (verified 2026-10-08 over SSH: adaptive.py,
  adaptive2.py, power_logger.py, energy_profile.py, the decay/accuracy/forecast JSONs, the weights
  yolov8n/s/m.pt and visdrone_vid_640 are all present), hwbench_env venv exists, jetson_clocks present
  (L4T R39 rev 2.0). STILL TO VERIFY: torch+CUDA inside hwbench_env, ultralytics import, INA3221 power
  read (the --report-power path), passwordless sudo for jetson_clocks under the harness.
- Pi (192.168.0.248): ~/hwbench intact from the earlier campaigns (verified: same flat layout, all JSONs
  present incl. energy_constants.json). push_code.sh refreshes adaptive.py/adaptive2.py and the JSONs.
- Config JSONs live in experiments/results/hardware in the repo (energy_constants.json in
  experiments/results/hardware/energy); the boards' ~/hwbench is a flat copy — push_code.sh pushes
  code from validation/hardware and the JSONs from their real repo locations.
- Passwords via env PI_PW / NANO_PW only (never written to files).

## Status / next

- Code: all 9 items above are written. Pending: py_compile syntax check of the edited Python (shell
  tool was blocked at the time of writing — will run), offline rescore of all earlier campaigns with
  the system views (~1 h CPU), Part 15 wording fix in `AEGIS-UAV Results Brief.md` from the rescored
  numbers, push_code.sh to both boards, Jetson prerequisite audit, then the campaign + heat runs.

## Rescore (9 Oct 2026, done)

- Syntax check: py_compile OK on all 7 edited Python files (WSL venv). tools/*.sh made executable.
- Jetson audit after the reflash: ~/hwbench survived (all code, JSONs, weights, video present),
  hwbench_env exists, jetson_clocks present (L4T R39 rev 2.0), torch 2.14.1+cu130 with CUDA available
  on the Orin, INA3221 read_power works live (read 5.14 W idle-ish at the terminal).
- Full offline rescore ran over ALL earlier campaigns (387 runs: v1 21, v2 88, wifi 108, wifi_fc 36,
  wifi_fc2 80, energy 100, swarm_duo 42): every run now has system_w/j_{extra,board,dedicated},
  sAP per system watt per view, per-drone flight time (camera + edge), swarm lifetime and swarm
  mission perception. Outputs: energy/energy_<campaign>.json + energy/energy_all_summary.json.
  The new vid_campaign_v42 directory shows 0 runs (campaign not started yet).
- Sanity against the user's table (100-run campaign, pooled): A_eco_tight sAP 0.0543, camera W 3.04
  model (3.33 measured — within the model's stated 0.1-0.4 W), edge W 4.94; sAP/W whole 0.0069,
  extra 0.0142; fixed_laptop extra 0.0189, whole-system (no edge drone at all: 2.65 W measured vs
  Pi+Jetson ≈ 8.3 W) ≈ 2.6-2.7x. All figures reproduce; swarm lifetime = the mini camera drone lands
  first everywhere (28-29 vs 33-34 min), so swarm mission perception tracks the camera's.
- Part 15 fix in `AEGIS-UAV Results Brief.md`: the "sAP per Pi watt" column relabelled as
  camera-drone-only with a pointer to G10; the two over-claiming bullets qualified ("most accurate /
  19-25% less Pi power" — for the camera drone, whole-swarm reverses; "nearly matches the most frugal
  strategy's accuracy per watt" — prices only the Pi); NEW G10 subsection "The whole swarm:
  system-level energy" with the three labelled views, the pooled system table, the honest
  whole-swarm statements (extra view 1.33x for fixed; board view ~equal because the 4.08 W idle
  dwarfs policy differences; the 2.6x claim framed as cross-system: fixed needs NO airborne edge
  drone, v4's accuracy depends on one), and the v4.2 summary. Part 19's v4-refinements row marked
  done-in-code with the campaign night still pending; Part 20 lists vid_campaign_v42.

## G-section audit (9 Oct 2026, second pass — measured vs estimate for BOTH boards)

Every number in Part 15 G1–G10 traced to its source file (energy_profile_{pi,jetson}.json,
thermal_steady_pi.json, energy_constants.json, campaign logs + rescored summaries). Findings:

- MEASURED and correctly cited: G1's whole table (all states both boards, 10 Hz, 20 s), G2's Pi
  steady table, G8's live-measured μ, G9's live-measured Pi power. The Jetson's thermal data
  EXISTS (profile thermal section: 5 min sustained YOLOv8m @ 640 back to back at ~10.6 W, 1 Hz log,
  52.7 → 60.3 °C peak at 262 s, clock pinned 1510 MHz by jetson_clocks, no throttling) — but G2
  described it in one unlabelled sentence and the 5-min curve was not yet fully flat.
- ESTIMATES found and now labelled in the brief (both .md and .html):
  1. G1 radio row: "≈ 0.2 W + 0.016 W per Mbit/s" is a linear fit of the Pi's measured points
     (now said); the Jetson's receive power is a SINGLE measured point at 21 Mbit/s (+0.21 W)
     applied at every link speed (now said, with the over-count direction).
  2. G3: flight powers + usable-battery fractions are the hover-model/assumed-80 % estimates,
     not measured in flight (now an explicit sentence; the Source column already said so).
  3. G5, G6: Pi power + edge-drone columns are the model reconstruction (these campaigns predate
     the power logger; live Pi power first appears in G9) — now said in both.
  4. G7: Jetson-as-camera 7.4 W / serving +1 W / board 8.5 W are model reconstruction — now said.
  5. Model-internal estimate (energy_model.py:174): the forecaster on a Jetson-as-camera is
     ¼ of the Pi's measured forecaster power (not measured on the Jetson) — affects G7's
     forecasting numbers; inline comment already marks it.
- STILL TO MEASURE (actual testing on the boards):
  1. ~~Jetson profile re-measurement post-reflash~~ **DONE (9 Oct)**: tools/profile_jetson24.sh ran the
     FULL profile with --heat-s 1440 --cool-s 300 on the reflashed Jetson (torch 2.14.1+cu130, CUDA True),
     radio states driven from the laptop. RESULT: idle and all five inference states matched the 8 Oct profile within
     0.1 W (the serve-s640-at-15-fps state differs by 0.32 W: 7.04 vs 6.72 W; radio rx +0.27 W at 27.9 Mbit/s vs +0.21 at 21) — idle 4.170 vs 4.079, n320 5.804 vs 5.714 (24.55 vs 24.77 ms), s320 6.819 vs 6.759,
     s480 8.294 vs 8.210, s640 9.714 vs 9.666 (29.11 vs 29.17 ms), m640 10.644 vs 10.646 (56.42 ms),
     tx ~4.2 W. Per-inference energies shift ≤ 2 % (s640 161 vs 163 mJ, m640 364 vs 371 mJ). The 8 Oct
     profile WAS post-reflash; NO constants regeneration needed — the G1 numbers stand, now confirmed
     by a second measurement. Fetched: energy/energy_profile_jetson_20261009.json (+ _24min.log).
     Caveat: the new run's radio tx "flat out" only reached ~4.1 Mbit/s (the laptop's WSL drainer was
     the bottleneck, not the radio) — the 8 Oct tx fit (to 8.14 Mbit/s) remains the one used.
  2. ~~Jetson steady-state thermal~~ **DONE (9 Oct, same run)**: 24-min sustained YOLOv8m @ 640 at 1 Hz —
     10.7 W throughout (10.69–10.93), temp 52.2 → steady 61.0–61.7 °C (mean 61.2) over the last minute,
     clock pinned 1510.4 MHz, NO throttling; cools to ~50 °C in 5 min. G2 updated with these measured
     numbers (both .md and .html), replacing the unlabelled one-line "peaked at 60 °C" (the 8 Oct
     5-min curve had peaked 60.3 °C and was still creeping; 24 min shows where it settles).
  3. 24-min Pi heat run (tools/heat_run.sh): **DONE (9–10 Oct, 03:04–06:16 board time)**. All 7 levels
     held 24 min each; steady (last-60-s) values from `energy/thermal_steady_pi_24min.json`: idle
     1.81 W / 64.0 °C, forecaster 2.17 W / 73.1 °C, JPEG encode 1.90 W / 54.1 °C, YOLOv8n duty
     0.15 / 0.3 / 0.5 / 1.0 = 2.62 W / 62.3 °C (2,314 MHz), 3.38 W / 71.5 °C (2,339 MHz), 3.77 W /
     81.8 °C (2,347 MHz with dips to 1,600 — throttling onset), 4.46 W / 84.4 °C (1,834 MHz —
     throttled; the board ends at 85.3 °C, right at the throttle boundary). Throttling again begins
     between the 30 % and 50 % duty levels, and the 6-min fit predicts the 50 % row to within 0.5 °C
     (82.3 predicted, 81.8 measured). The low-power rows are NOT a clean replication of the 6-min
     table: the idle level started from a board still warm after setup (67.8 °C → settles 64 °C), the
     encoder stopped part-way in the encode level (power fell to 1.65 W — a near-idle row), and the
     forecaster's temperature was still creeping at 24 min. Thermal history/ambient sensitivity
     bracketed by the two runs; every throttling conclusion holds in both. G2 updated in both brief
     files with these numbers. HARNESS BUG found and fixed: the run's completion poll used
     `pgrep -f thermal_steady.py`, which matches the poll's own SSH command line, so the poller never
     exited after the run finished and polled pointlessly ~90 min until killed (the result was fetched
     manually); fixed with the `thermal_[s]teady.py` character-class pattern in heat_run.sh.
  4. The live v4.2 campaign (JLOG+POWERLOG on every run) replaces the model-based edge power with
     measured per-run Jetson power.

## Next: live campaign

1. Passwordless campaign launch: install a WSL ed25519 key on both boards (key auth from Windows
   already works), relax rsh.sh/rcp.sh to try pubkey first with the askpass password fallback.
2. push_code.sh to both boards (refreshes adaptive.py/adaptive2.py + JSONs in ~/hwbench).
3. One short v4.2 smoke run (A_eco42, PHASE_S=20): verify the Jetson worker's board_w headers reach
   the camera (edge_reported_w, mu_edge_log in the run output) and torch inference works on the
   reflashed Jetson.
4. campaign_energy.sh in the background (6 policies x 4 scenarios x 5 reps = 120 runs, ~10 h),
   heat_run.sh AFTER it (the Pi cannot serve both at once).
5. Rescore the new campaign; G11 in the brief with the results.

## Validation review (11 Oct 2026) — mistakes found and corrected

Every Phase G claim above was re-checked against the raw files: the 24-min Pi heat run
(thermal_steady_pi_24min.json), both Jetson profiles, energy_constants.json, the rescored campaign
files, and the code (py_compile + an offline test of the corrected logic). The measured numbers
reproduce (two small over-statements fixed: see the profile note above, and the brief's "duty rows
2–6 °C apart" is 1–6 °C). Six mistakes were found in the new code/analysis and fixed:

1. **mu_edge ratchet (adaptive2.py, campaign_energy.sh).** With `--edge-power-budget 0` the dual step is
   never negative, so mu_edge only rises (offline test: 3.44 after 20 s of serving and still 3.44 at 60 s;
   with 0.5 W it relaxes to 0.44). A_eco42 would have been "v4 that stops using the Jetson after ~25 s",
   not "uses it when worth its energy". Fix: default edge budget 1.0 W (derived when --mission-min),
   warning if ≤ 0; campaign A_eco42 uses 0.5 W (binds: v4 runs averaged ~0.86 W extra) and A_eco42d
   derives both budgets from battery + flight power (edge 36.7 W: non-binding — measures whether edge
   pricing matters at realistic battery numbers).
2. **Edge power sampled at the worst moment (adaptive.py).** The worker read the INA3221 once per
   response — always just after an inference — which over-states mean power (the same bias as the old
   1 Hz Pi log). Fix: a 5 Hz background sampler, header carries the 1-s mean; one sampler per worker
   (it was re-created on every reconnect).
3. **SoC model (adaptive2.py).** It multiplied the current 1-s power by the whole elapsed time instead of
   integrating, was only updated for energy-aware policies (others always reported 1.0), and used each
   camera's own start time as origin — a 25 s start offset between cameras outweighs the whole
   perception-energy difference of a 3-min run. Fix: integrate measured board energy at 5 Hz whenever
   the power logger runs, SoC origin = first coordinator contact (common to all cameras).
4. **Coordinator starvation (coordinator.py).** With equal SoC (always, before fix 3) `sorted` is stable,
   so the first-listed camera was admitted every window and the other never. Fix: ties broken by the
   round-robin rotation (offline test: pi, jet, pi, jet, ...).
5. **Rate-objective units (adaptive2.py).** v4.2 subtracted mu·J-per-frame from a per-second value.
   Fix: penalty × frames/s (÷ busy s), i.e. a power. No campaign ran energy-aware with --objective rate.
6. **System views charged a drone that is not there (energy_model.py, energy_rescore.py).** Runs that
   never use the edge drone (fixed laptop) have edge_w = 0 in the rows, yet system_views added the
   Jetson's 4.08 W idle (board view) and 153.6 W flight (dedicated view), and the swarm lifetime included
   an edge drone. That produced the brief's claim "board view: about equal (0.0071 vs 0.0069)". Fix: no
   edge drone in any view when edge_used is False. All 387 runs rescored (log
   energy/energy_rescore_20261011.log; previous outputs archived in
   _superseded/energy_rescore_20261009/). Only no-edge runs changed. Corrected G10: fixed offloading
   0.0189 sAP/W in every view; v4 (2.8 W) 0.0183 camera / 0.0142 extra / 0.0069 board / 0.00034
   dedicated → fixed is 1.33× (extra), 2.7× (board), ~55× (dedicated). Brief .md and .html updated.

Not mistakes but noted: `verify_phase_g.py` sits at the repo root (an audit script; run from
uav-split-perception/); `docs/results_brief.html` and the published artifact are still the 8 Oct
version — the current brief is `AEGIS-UAV Results Brief.md/.html` at the repo root.
Still to do: push_code.sh to both boards, the v4.2 smoke run, then campaign_energy.sh (120 runs).
