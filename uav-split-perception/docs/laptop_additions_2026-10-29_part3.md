# Laptop-only additions, part 3 (29 Oct 2026): a published scheduler in the replay

Continues `laptop_additions_2026-10-29_part2.md`. Nothing existing was re-scored or overwritten; every output is new.
Brief section 19.10 (built by `scripts/report_accumo_oct29.py`).

## Why

The closest published scheduler is AccuMO (Kong, Xu, Meng, Hu; MobiCom 2023; `docs/novelty_check_phase0.md`). It
predicts how the accuracy of the last result falls with its age, depending on content (camera angular velocity, its
K1), and plans offloading by model-predictive control over a 30-frame horizon to maximise predicted accuracy. It prices
neither energy nor heat. Part 16.1 of the brief argues that a greedy per-frame choice with slow prices is enough; this
tests that argument, and gives the paper a published baseline instead of only our own fixed policies.

## Method

Script `validation/hardware/replay_accumo.py` (subclasses the replay of `replay_oracle.py`; `replay.py` unchanged).
Output `experiments/results/hardware/replay/accumo_oct29/` (`rows/`, `runs/`, `accumo_summary.json`, logs).

- **Accuracy model:** the measured decay with forecaster v2 for the camera-motion tertile of the current frame
  (`decay_context_train.json`, tertile cuts fixed on train; ego speed from the val camera-motion chain with
  `decay_context.ego_speed`, which the Pi can compute live).
- **Plans:** one setting, or none, per server for the next 30 frames: laptop 8 + 1, Jetson 6 + 1, onboard 3 + 1 =
  252 plans.
  - A server repeats its setting whenever it is free (a path: once the transfer is acknowledged; onboard: after the
    inference, current throttling included).
  - Results arrive after the expected latency: encode + transfer at the live goodput estimate + server time + round
    trips. Settings whose transfer would stall the link are excluded.
  - Results already in flight count in every plan, re-predicted each frame with the live estimator (its in-flight
    stall check); a result on a link that dropped is counted as lost.
- **Objective:** the mean over the horizon of A(shown)/A_ref × ρ(age of shown), where "shown" is the newest capture
  that has arrived by that frame (what the display holds).
- **Action:** receding horizon. Each frame the best plan is recomputed, and of its servers that are idle now, the one
  whose removal would cost the plan most is started. The harness sends at most one frame per tick, as on the Pi.
- **Variants:**
  - `accumo`: as above;
  - `accumo_global`: the global forecaster-v2 curve (what v4.1 uses), which separates the content conditioning;
  - `accumo_energy`: `accumo` minus v4.1's camera energy price (same 2.8 W target, dual update and blackout
    exemption), which separates planning from pricing.
- **Unavoidable differences from AccuMO:** one task (detection), not several; the decay is measured per ego-motion
  tertile, not predicted by a learned model; goodput is the live EWMA estimate all our controllers use.
- **Planner time:** median 1.4 ms per frame on the laptop beside other jobs (95th percentile 3.0 ms). Not yet
  measured on the Pi.
- **Runs:** all on the same seeds and link draws (common random numbers), with netem reset per phase.
  - 15 seeds for the mission and random scenarios, 5 for the mirror mission and good links, 7 for a 24-minute
    mission (6 × 4 min).
  - Comparators: v4.1, v5, v4, v3 + fc2 (`stream_fc2`), the LEAF-style fixed weight, shortest queue, freshness
    threshold, confidence trigger, offloading reward and fixed laptop m640q90.
  - In total, 422 runs.
- **Check:** the 20 stored v4.1 runs of 19.8 (`oracle_oct29_plant`) are reproduced exactly (largest sAP difference 0).

## Results (sAP with forecaster; difference to v4.1, paired, Student-t 95 %; positive = better than v4.1)

| Scenario | v4.1 | AccuMO-style | one global curve | + energy price | LEAF-style weight | v4 |
| --- | --- | --- | --- | --- | --- | --- |
| mission (n 15) | 0.0525 | +0.0018 ± 0.0019 | +0.0018 ± 0.0019 | +0.0018 ± 0.0019 | **+0.0022 ± 0.0009** | +0.0001 ± 0.0008 |
| mirror mission (n 5) | 0.0631 | +0.0014 ± 0.0022 | +0.0016 ± 0.0019 | +0.0014 ± 0.0022 | +0.0022 ± 0.0024 | — |
| random links (n 15) | 0.0470 | **+0.0044 ± 0.0019** | **+0.0045 ± 0.0022** | **+0.0044 ± 0.0019** | **+0.0053 ± 0.0014** | **+0.0020 ± 0.0014** |
| good links (n 5) | 0.0755 | −0.0001 ± 0.0051 | −0.0008 ± 0.0054 | −0.0001 ± 0.0051 | +0.0009 ± 0.0017 | — |
| 24-min mission (n 7) | 0.0469 | **+0.0014 ± 0.0008** | — | **+0.0014 ± 0.0008** | **+0.0022 ± 0.0005** | — |

The AccuMO-style planner sends 0–6 % of frames onboard against v4.1's 3–11 %, and holds a result younger than 300 ms
87–97 % of the time against 99–100 %. In the 24-minute mission it is ≥ 80 °C 11 % of the time against 16 %.

- **In the replay, v4.1 does not beat the AccuMO-style planner.** They tie on the mission, the mirror mission and good
  links. The planner is ahead on random links (+0.0044, 15 of 15 seeds) and over the 24-minute mission (+0.0014,
  6 of 7).
- **The gain is not from planning.** The LEAF-style fixed-weight greedy controller is ahead of v4.1 by as much or more
  in every scenario, and v4 (v4.1 without the freshness price) is ahead on random links.
  - Content conditioning adds nothing: the global curve gives the same result.
  - v4.1's energy price changes nothing in the planner: its power is already at or below the 2.8 W target.
  - A likely mechanism: an onboard result is newer, so on screen it replaces a better offloaded result still on its
    way. The planner sees that cost; v4.1's freshness price pushes towards onboard results. One example (mission,
    seed 1): at the total blackout the planner waits about 1 s for results sent just before both links died, then
    switches to onboard.
- **These differences are within the replay's known error for this kind of comparison.** The replay's validation
  against the 240-run main campaign (19.8, `validate_main_oct29_plant/replay_check.json`) put LEAF +0.0050 sAP ahead of
  v5 where the hardware measured a tie (−0.0004). On hardware, v4.1 − v4 was +0.0025 ± 0.0041 (G11), and LEAF tied
  v5 (G12). The replay favours policies that run less onboard, so it cannot rank the planner against v4.1.
- **Against the other literature baselines the planner behaves like v4.1.** Shortest queue, freshness threshold,
  confidence trigger and offloading reward are 0.007–0.029 sAP behind both.

## What this changes

- **The paper must not claim that v4.1 beats AccuMO-style planning.** The supported claim is narrower: on this system,
  a greedy priced choice does as well as a 30-frame model-predictive planner, within the replay's error, at a fraction
  of the computation.
- **Board test:** run the planner against v4.1 and the LEAF-style weight on hardware. It needs:
  - the planner ported into `adaptive2.py`;
  - its time per frame measured on the Pi 5;
  - 5 paired repetitions per scenario.
- **The replay's bias:** it favours light onboard use (above), and it gives onboard-heavy policies 0.4–0.7 W less
  power than measured (19.8). Both are worth correcting before the replay is used to rank policies that differ by
  less than about 0.005 sAP.
