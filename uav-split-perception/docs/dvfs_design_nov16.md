# DVFS as a third knob (plan Phase 5, D5): measured profile and controller design (16 Nov 2026)

## Measured profile (`experiments/results/hardware/energy/dvfs_profile_pi-receiver_20261116.json`)

`validation/hardware/dvfs_profile.py` on pi-receiver (Pi 5, same model as the camera pi-relayyy), 16 Nov 2026
01:14-01:45 IST: frequency pinned (cpufreq min = max), each state 15 s, every inference state started below 55 °C, two
passes (second in reverse order), cpufreq restored to ondemand 1.5-2.4 GHz afterwards (checked). Mean of the passes; J
per inference = (P − P_idle at that clock) × time.

| clock | idle W | s320 ms | s320 W | s320 J | n480y11 ms | n480y11 W | n480y11 J |
|---|---|---|---|---|---|---|---|
| 1.5 GHz | 1.79 | 207 | 4.36 | 0.531 | 195 | 4.43 | 0.515 |
| 1.8 GHz | 1.84 | 182 | 4.17 | **0.425** | 173 | 3.95 | **0.366** |
| 2.1 GHz | 1.93 | 167 | 5.08 | 0.527 | 161 | 4.52 | 0.416 |
| 2.4 GHz | 2.06 | 154 | 5.86 | 0.586 | 151 | 5.37 | 0.499 |

Repeatability: latency within 1 % between passes at every clock; power within 0.1-0.6 W (largest at 1.5 GHz).

Findings:
1. **1.8 GHz is the energy minimum** for both models: −27 % J per inference against 2.4 GHz, −1.4 to −1.7 W while
   inferring, +22 to +28 ms latency (both still far inside the 300 ms deadline).
2. **The curve is U-shaped:** 1.5 GHz costs more energy than 1.8 GHz (longer inference, power barely lower), so the
   choice is not "always slower".
3. **Isolated bench vs in-run time:** YOLO11n-480 takes 151 ms here at 2.4 GHz and 190-192 ms inside a running
   controller (camera Pi, start-up timing): the controller's own threads (forecaster, encoder, sender) take ~25 %
   (s320: 154 vs 176 ms, 14 %). The controller must use in-run times per clock, measured at start-up as it already
   does at 2.4 GHz, not the bench values.
4. Encoding a 640 q90 JPEG at 30 fps adds only 0.04-0.07 W at any clock: the offload path barely cares about the clock.

## Controller design (v41dvfs)

The onboard options become (variant, clock) pairs with clock ∈ {1.8, 2.4} GHz (1.5 and 2.1 are dominated: higher J
than 1.8 at longer or equal time). The value formula is unchanged (`onboard_value`), with the pair's own measured time
t(v, f) and energy E(v, f):

    V_onboard(v, f) = (A_v / A_ref) · H(t(v,f), T) − μ · E(v, f) + λ_F · 1[t ≤ D] · 1[AoI + t ≥ D]

so the existing prices decide the clock: when μ is high (over budget or ≥ 78 °C) the cheaper 1.8 GHz option wins
unless its extra latency costs more holding value than the energy saved; in the blackout hold (onboard unpriced) 2.4 GHz
wins on latency, and when hot (hold capped) 1.8 GHz wins on price. No new price, no new theorem term: Theorem 1 is
unchanged because E(v, f) is just another measured option energy.

Mechanism: before an onboard inference starts, the controller writes scaling_max_freq = f (min stays at 1.5 GHz,
governor ondemand; adaptive2.py already runs as root); after it, back to 2.4 GHz. The other threads run at f during
the inference, which the in-run start-up timing per (v, f) includes. Start-up timing: 6 runs per pair, as now.

Board test (after Phase 4, predictions committed first): v41final vs v41final + DVFS on the 24-min mission (heat) and on
mesh_mission/random (40-s phases), paired reps; expected effect: lower Pi power and temperature in blackout-heavy
phases at the same sAP.

## Implementation and board test of the mechanism (16 Nov 2026, adaptive2.py `--onboard-clocks`, `--dvfs-profile`)

`validation/hardware/tests/test_dvfs_onboard.py` on pi-receiver (as root): default clock 2400 MHz read at start; start-up
timing s320 152 ms, s320@1800 180 ms (both timed under the same conditions); the twin shares its variant's model object;
during s320 inferences the cap read 2400, during s320@1800 1800; after them 2400; a SIGTERM in the middle of a capped
inference exits 143 with the cap restored to 2400. Not yet run in a campaign: the arun_mesh strategy and cleanup line
(`cpuinfo_max_freq > scaling_max_freq` on the camera) are added before the DVFS campaign, after Phase 4.
