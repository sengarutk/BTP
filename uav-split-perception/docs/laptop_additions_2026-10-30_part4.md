# Laptop-only additions, part 4 (29–30 Oct 2026): v4.1's settings, the replay's power model, a held-out check, the planner on the board

Continues `laptop_additions_2026-10-29_part3.md`. Brief section 19.11 (built by `scripts/report_part4_oct30.py`; the
text below is the same section, followed by details that are not in the brief).

Write-up `docs/laptop_additions_2026-10-30_part4.md`; nothing earlier was changed or re-scored (every new setting of the replay is a switch whose default reproduces the stored results exactly; checked on stored runs of v5, v4.1 and the planner, identical to the last digit).

**1. How sensitive is v4.1 to its own settings?** One setting at a time moved away from what the board runs, the others held, on the same seeds and link draws as v4.1 (`validation/hardware/replay_sweep.py`, `replay/sweep_oct29/`, 295 runs; seeds 1–10, the 24-min mission seeds 1–3; old power model, as 19.8–19.10). Bold: the 95 % interval excludes zero; positive = better than v4.1.

| Setting | Value | mission, n 10: sAP − v4.1 (Pi W) | random links, n 10: sAP − v4.1 (Pi W) | 24-min mission, n 3: sAP − v4.1 (Pi W) |
| --- | --- | --- | --- | --- |
| energy target (`--power-budget`, v4.1: 2.8 W) | 2.4 W | **+0.0015 ± 0.0005** (−0.10 W) | **+0.0016 ± 0.0011** (−0.16 W) | +0.0006 ± 0.0014 (−0.09 W) |
| energy target (`--power-budget`, v4.1: 2.8 W) | 2.6 W | **+0.0011 ± 0.0005** (−0.06 W) | **+0.0018 ± 0.0009** (−0.11 W) | — |
| energy target (`--power-budget`, v4.1: 2.8 W) | 3 W | **−0.0009 ± 0.0006** (+0.07 W) | **−0.0009 ± 0.0004** (+0.13 W) | — |
| energy target (`--power-budget`, v4.1: 2.8 W) | 3.2 W | **−0.0019 ± 0.0011** (+0.16 W) | **−0.0028 ± 0.0008** (+0.27 W) | **−0.0024 ± 0.0005** (+0.23 W) |
| freshness target (`--fresh-target`, v4.1: 0.95) | 0.85 | +0.0003 ± 0.0008 (−0.08 W) | **+0.0015 ± 0.0014** (−0.07 W) | +0.0009 ± 0.0012 (−0.05 W) |
| freshness target (`--fresh-target`, v4.1: 0.95) | 0.9 | −0.0001 ± 0.0004 (−0.03 W) | +0.0013 ± 0.0014 (−0.03 W) | — |
| freshness target (`--fresh-target`, v4.1: 0.95) | 0.99 | +0.0001 ± 0.0006 (+0.01 W) | −0.0010 ± 0.0011 (+0.05 W) | +0.0007 ± 0.0009 (+0.02 W) |
| energy price step (`--eta`, v4.1: 0.1) | 0.05 | **−0.0012 ± 0.0008** (+0.05 W) | **−0.0007 ± 0.0007** (+0.07 W) | — |
| energy price step (`--eta`, v4.1: 0.1) | 0.2 | **+0.0007 ± 0.0004** (−0.03 W) | **+0.0012 ± 0.0005** (−0.07 W) | — |
| freshness price step (`--eta-f`, v4.1: 2.0) | 1 | +0.0000 ± 0.0004 (+0.00 W) | +0.0001 ± 0.0005 (−0.01 W) | — |
| freshness price step (`--eta-f`, v4.1: 2.0) | 4 | −0.0001 ± 0.0004 (+0.00 W) | **+0.0005 ± 0.0005** (−0.01 W) | — |
| freshness price cap (`--lam-f-max`, v4.1: 2.0) | 1 | +0.0001 ± 0.0003 (−0.01 W) | +0.0002 ± 0.0004 (−0.02 W) | — |
| freshness price cap (`--lam-f-max`, v4.1: 2.0) | 4 | +0.0000 ± 0.0004 (−0.00 W) | +0.0001 ± 0.0005 (−0.01 W) | — |

- **v4.1 is flat in its update speeds and freshness cap** (at most 0.0012 sAP from v4.1), and nearly flat in its freshness target (−0.0010 to +0.0015). Nothing in the result depends on hand-tuning these.
- **The energy target is the one that matters.** A tighter target (2.4–2.6 W) scores +0.0011 to +0.0018 on the short scenarios, a looser one (3.0–3.2 W) −0.0028 to −0.0009; over the 24-min mission 3.2 W costs −0.0024 ± 0.0005 and 2.4 W ties (+0.0006 ± 0.0014). The direction is the replay's known bias (it favours less onboard work), so this is a hint, not a reason to change 2.8 W; it was checked on fresh seeds below.

**2. The replay's onboard power, corrected.** The replay spread the bench energy of one onboard inference over the inference time, so a slower inference (CPU contention, throttling) drew *less* power; on the Pi the power during inference stays the same when it slows (4.8 W cool, 4.7 W throttled, Part 6), so the energy grows. Corrected as a switch (`replay.py --onboard-power power`: the bench power held for the whole inference), with the board held at its 85 °C throttle limit (the firmware does that; with full power kept, the linear thermal fit would let the simulated board reach 98 °C in the 24-min mission, which the real board never does). Re-validated against the same 240 hardware runs (`replay/validate_main_oct30_power_t85/`, same scenarios, seeds and netem setting as `validate_main_oct29_plant`):

| Replay against the 240 hardware runs | old model: r / mean abs. diff. | corrected model: r / mean abs. diff. |
| --- | --- | --- |
| sAP | 0.947 / 0.004 | 0.957 / 0.003 |
| Pi power (W) | 0.990 / 0.213 | 0.989 / 0.106 |
| time ≥ 80 °C | 0.962 / 0.201 | 0.978 / 0.163 |
| share of time with a fresh result | 0.926 / 0.055 | 0.927 / 0.053 |
| paired verdicts against v5 that agree with hardware | 9 of 11 | 9 of 11 |
| LEAF − v5 sAP (hardware −0.0004) | +0.0050 | +0.0049 |
| Pi power of the 3 onboard-heavy baselines (replay / hardware) | 4.13 W / 4.80 W, 4.07 W / 4.71 W, 4.23 W / 4.66 W | 4.55 W / 4.80 W, 4.47 W / 4.71 W, 4.74 W / 4.66 W |
| their time ≥ 80 °C (replay / hardware) | 9 % / 69 %, 5 % / 60 %, 8 % / 72 % | 22 % / 69 %, 19 % / 60 %, 26 % / 72 % |

- **The power and heat errors shrink**, but the replay still under-states the onboard-heavy baselines' heat, and **its LEAF bias is unchanged** (+0.0049 against a hardware tie). So the bias is not in the power model; the likely cause is CPU contention on the Pi (onboard inference slowing the camera loop, encoding and forecasting), which the replay does not model. Comparisons of policies that differ in onboard use by a few per cent remain beyond the replay.

**3. Held-out check on fresh seeds, corrected model.** Seeds 11–20 (never used before), v4.1 against the AccuMO-style planner, the LEAF-style weight and v4.1 with a 2.4 or 2.6 W target (`replay/heldout_power_oct30/`, 100 runs, peak 76 °C, so the 85 °C hold never acts there; the 24-min mission seeds 11–13 in `replay/heldout_power_oct30_t85/`, 12 runs).

| Scenario | v4.1 sAP + fc | AccuMO-style planner − v4.1 | LEAF-style weight − v4.1 | v4.1 at 2.4 W − v4.1 | v4.1 at 2.6 W − v4.1 |
| --- | --- | --- | --- | --- | --- |
| mission (seeds 11–20) | 0.0529 | +0.0009 ± 0.0015 | **+0.0017 ± 0.0010** | **+0.0004 ± 0.0003** | +0.0003 ± 0.0003 |
| random links (seeds 11–20) | 0.0456 | **+0.0045 ± 0.0026** | **+0.0047 ± 0.0022** | +0.0013 ± 0.0018 | **+0.0016 ± 0.0009** |
| 24-min mission (seeds 11–13) | 0.0469 | +0.0011 ± 0.0023 | **+0.0018 ± 0.0006** | +0.0001 ± 0.0007 | — |

- **The ranking of 19.10 holds on fresh seeds and with the corrected power model:** the planner and LEAF tie or lead v4.1 (random links **+0.0045 ± 0.0026** and **+0.0047 ± 0.0022**; mission +0.0009 ± 0.0015 and **+0.0017 ± 0.0010**), by less than the replay's LEAF bias. The board campaign below decides it.
- **The tighter energy target gains little** (**+0.0004 ± 0.0003** and +0.0013 ± 0.0018 at 2.4 W; 24-min mission +0.0001 ± 0.0007): well inside the replay's error and in the direction of its bias. **2.8 W stays.**

**4. The AccuMO-style planner on the board.** `adaptive2.py --policy accumo` (with `--mpc-horizon`, and `--mpc-context` for the camera-motion-conditioned decay from the live forecaster). The search is one shared module, `validation/hardware/mpc_planner.py`.

- **Same decisions as the replay's planner:** `tests/test_mpc_planner.py` runs both on the same replay state every frame of two replayed missions (with and without the energy price) and requires identical choices.
- **Runs end to end:** a loopback run on the laptop (camera and GPU worker on 127.0.0.1, the network shaping replaced by a no-op, the laptop's network untouched) completed all 540 frames; the planner took 1.87 ms per frame (95th percentile 2.26 ms) and used the camera-motion curve in 536 of 540 frames (`planner_smoke_oct30.json`; a functional check, not a measurement).
- **Planner time:** 0.64 ms median, 0.97 ms 95th percentile per frame on the laptop, single-threaded, over 2950 sampled states (`bench_planner.py`, `planner_bench_laptop_oct30.json`), against a 33 ms frame budget. The same script runs on the Pi without workers.

**5. The next board session, ready to run.**

- `tools/push_code_mesh.sh`: the code and configuration to the camera and the Jetson over the mesh (with an import check on the camera); `tools/push_code.sh` updated for Wi-Fi.
- `tools/campaign_mesh4.sh`: v4.1, the planner (`accumo`) and the LEAF-style weight (`leaf`, as in the 240-run campaign) × good links, mesh mission, multihop × 5 repetitions = 45 runs, shuffled, resumable; it first times the planner on the camera Pi. About 6 h.
- `tools/campaign_ego160.sh`: the 160 px camera-motion step (19.9) timed on the Pi (`egomotion_bench.py`), then v4.1 at 320 and 160 px × 2 scenarios × 3 repetitions = 12 runs (`EGO_W=160`; the default stays 320). About 1.5 h.
- `validation/hardware/calib_hw.py`: the calibration check of 19.8 on real runs (the controller's logged deadline probabilities against measured latencies, the same bins as the replay); tested on the loopback run and on campaign 3 (runs from before the logging are skipped).

**6. The paper.** `paper/main.tex` has a new section "Hardware Check" (all 1,150 placements; live runs: a Q90 JPEG to the laptop 14.7 on-time results/s against 2.5 for the best split; INT8/FP16 splits within 0.0004 mAP with the VisDrone YOLOv8s while Q90 JPEG loses 4.0 %, so a split can beat it by at most 4.3 %; the simulator against 44 real runs, r = 0.947), plus updates to the abstract, contributions and limitations. Every number is generated from the result files (`evaluation/make_hardware.py`, traced in `docs/claims_to_evidence.md`). Checked: the simulator code against the paper's policy equations (they match); every cited DOI against CrossRef/DataCite (one fix: the YOLOv5 v7.0 entry is from 2022, not 2020).


## Details not in the brief

### Code changes (all switches default to the earlier behaviour)

- `replay.py`: `--onboard-power energy|power` (module `ONB_POWER`, default `energy`); with `power` the board is also held
  at `energy_constants.json` `pi.thermal.throttle_c` (85 °C). The dual-update gains are read from the policy
  (`mu_step`, `fresh_step`, `fresh_cap`; defaults 0.1, 2.0, 2.0, as hard-coded before).
- `replay_accumo.py`, `replay_sweep.py`: `--onboard-power`, written into every row (`onboard_power`).
- `adaptive2.py`: `--policy accumo`, `--mpc-horizon` (30), `--mpc-context FILE`; the run JSON gains `mpc` (planner time
  per frame, tertile counts). Every other policy is unchanged.
- `egomotion.py`: `W_SMALL` from the environment variable `EGO_W_SMALL` (default 320).
- New: `mpc_planner.py`, `bench_planner.py`, `egomotion_bench.py`, `calib_hw.py`, `replay_sweep.py`,
  `tools/push_code_mesh.sh`, `tools/campaign_mesh4.sh`, `tools/campaign_ego160.sh`; `tools/arun_mesh.sh` gains the
  strategies `accumo` and `leaf` and the optional `EGO_W`; `tools/push_code.sh` copies the new files.
- Tests: `tests/test_mpc_planner.py` (the board planner against the replay planner, every frame), `tests/test_board_tools.py`.
- Paper: `evaluation/make_hardware.py` (`make tables`), `paper/generated_tables/hw_metrics.tex`, `table_hardware.tex`.

### Reproduction checks

- Default switches against stored rows: `validate_main_oct29_plant` v5 mission seed 1 (needs `--netem legacy`, as the
  240 hardware runs it is checked against are from before the 13 Oct netem fix), `accumo_oct29` accumo and v4.1 mission
  seed 1: identical sAP and power.
- The 85 °C hold: none of the 240 validation runs changes its sAP (only 24 of them passed 85 °C, by at most 3.8 °C). In
  the 24-min mission it changes sAP by 0 to +0.0003 (v4.1 +0.0001, LEAF +0.0003, the planner and 2.4 W 0; the board cools from 85 °C instead of up to 98 °C, so less
  time above 80 °C slows onboard inference); the verdicts are the same as without it
  (`replay/heldout_power_oct30/` 24-min rows, kept for comparison).

### Incidents (no result lost or corrupted)

- 29 Oct about 19:40 and 21:00 IST the laptop restarted twice. Cause: 21 replay processes at once, each peaking at
  0.76 GB (measured), on an 11.8 GB machine (the project's memory note of 25 Oct already warned against more than 3 heavy
  workers). Every row file was checked afterwards (all parse); the interrupted runs were re-run. Since then at most 6
  replay processes run at once, single-threaded, from a queue (`replay/queue_oct29/`, `queue_oct30_t85/`,
  `heldout_power_oct30/queue/`).
- A first launch of the power-model validation used `--netem reset` (wrong for the 240 hardware runs); it was killed by
  the restart and is archived unused in `replay/validate_main_oct29_power/_aborted_reset_netem_oct29/`.
- `replay/validate_main_oct29_power/` (power model without the 85 °C hold) is kept for comparison; the brief uses
  `validate_main_oct30_power_t85/`.

### Files

- Results: `replay/sweep_oct29/`, `replay/validate_main_oct29_power/`, `replay/validate_main_oct30_power_t85/`,
  `replay/heldout_power_oct30/`, `replay/heldout_power_oct30_t85/`, `planner_bench_laptop_oct30.json`,
  `planner_smoke_oct30.json` (and the overloaded first run, `planner_smoke_oct29.json`, `planner_bench_laptop_oct29.json`).
- Archives: `_superseded/replay_before_power_oct29/` (replay, sweep, accumo, egomotion, push and run scripts before the
  switches), `_superseded/paper_before_hw_oct29/` (paper, bib, Makefiles), `_superseded/report_before_part4_oct30/`
  (brief and Novelty Brief before 19.11).
