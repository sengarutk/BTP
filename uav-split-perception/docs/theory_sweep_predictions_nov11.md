# Paper 2: step-size and budget sweeps in the validated replay. Predictions written before any run (11 Nov 2026)

Script: `validation/hardware/replay_theory_sweep.py` (v4.1 with one setting changed, common random numbers, the
validated replay with `--onboard-power power`, the setting of `replay/validate_main_oct30_power_t85`). The replay
now logs Theorem 1's terms per run (`replay.py`, logging only; benchmark check bit-exact).

What is and is not a test here
- Theorem 1 is an identity of the update rule, so "the bound holds in every run" only checks the logging.
- The replay's thermal plant is the same first-order fit as Proposition 1 (T = 34.43 + 12.73 P, tau 149 s), so the
  mean temperature against a + b P is circular. Not reported as evidence.
- What is a test: (i) how the excess power and the accuracy move with the step size, where Theorem 2's assumptions
  are broken (Markov links, per-frame choices, hold and cap, freshness term); (ii) whether the budget chosen from the
  throttle limit (B <= 3.6 W) is near the budget with the best streaming AP once throttling (the replay's measured
  slow-down, x 2400/1568 at 85 C) and heat transients act.

Sweeps
- step size eta (mu_step): 0.02, 0.05, 0.1 (v4.1), 0.2, 0.5, 1.0; budget 2.8 W. Short missions (6 phases x 20 s,
  seeds 1-10), random faults (seeds 1-10), 24-min missions (6 x 240 s, seeds 1-5).
- budget B: 2.4, 2.8 (v4.1), 3.2, 3.6, 4.0, 4.5 W; eta 0.1. 24-min missions, seeds 1-5 (heat needs tau-long runs).

Predictions
1. Theorem 1's inequality holds in every run (sanity check of the logging).
2. The price term mu_N / (eta N) falls with eta, roughly as 1/eta, until the price reaches its cap (5); on 2-min
   runs with eta <= 0.05 the price cannot reach its working level, so the mean power exceeds the budget most there.
3. The excess power over the budget falls with eta (Theorem 1's trade) on every scenario.
4. Streaming AP: Theorem 2's gap term (eta/2) mean (P - B)^2, computed from the logged power, grows with eta; the
   measured sAP is flat (within the paired interval of v4.1) for eta from 0.05 to 0.2 (the Oct 29 sweep found that
   for 0.05 and 0.2) and lower at eta = 1.0. If sAP does not fall at large eta, the idealised O(eta) gap is not
   visible in this system and we say so.
5. Budget: the share of time at or above 80 C is about 0 for B <= 3.2 W and rises above 3.6 W; sAP rises with B
   while the board stays cool and stops rising (or falls) once it throttles, so the best budget is within one step of
   3.6 W. If sAP keeps rising up to 4.5 W, the rule only protects temperature and not accuracy, and we say so.

Addendum (11 Nov 2026, ~12:30 IST, before the ambient runs): hotter room
Ambient was never logged on the boards, so this is an extrapolation of the model, labelled as such. Assumption: a
hotter room shifts the plant's intercept a by the same amount (the board's rise above the room is set by its power),
so the 80-C budget falls by 1/b = 0.079 W per degree: 3.6 W in the lab, 3.2 W at +5 C, 2.8 W at +10 C. The campaign
offsets of the hardware fit (1.6 C between the 24-min Wi-Fi and mesh runs, 0.13 W of budget) show the size of
day-to-day shifts already seen. Runs: th_amb5_b3.6, th_amb5_b3.2, th_amb10_b3.6, th_amb10_b2.8 (24-min missions,
seeds 1-5), compared with th_b3.6 (lab).
6. Keeping the lab's 3.6 W on a hotter room raises the share of time at or above 80 C clearly above the lab's
   (largest at +10 C, where the board reaches its 85-C throttle limit for part of the run); the corrected budget
   brings it back to about the lab's level. Streaming AP at the corrected budget is no more than slightly below the
   kept budget's; if keeping 3.6 W gives clearly higher sAP despite the heat, the rule protects temperature only, and
   we say so.

Addendum 2 (11 Nov 2026, ~14:25 IST, after the step-size and budget runs, before these runs): the blackout hold
The 24-min missions spend 18-21 % of the time at or above 80 C at every budget from 2.4 to 4.5 W, and the hold term
(0.16-0.50 W) is the largest term of Theorem 1 there. Hypothesis: the heat comes from the hold (in a blackout
onboard inference is not priced), not from the budget. Diagnostic runs th_nohold_b2.8 and th_nohold_b3.6 (24-min
missions, seeds 1-5): the hold switched off, so onboard inference is priced in blackouts too (replay.py no_exempt;
not a proposed controller: without the hold nothing is shown during a blackout except what the price allows).
7. Without the hold, the share of time at or above 80 C falls well below 18 % at 2.8 W, the excess power falls to
   about the price and cap terms, and sAP falls (the hold is there to show results in blackouts). If the hot share
   stays near 18 %, the heat has another cause and we say so.

Results so far (step size, budget, ambient, no hold) are in theory_sweep_summary.json; predictions 4, 5 and 6 failed
(sAP does not fall at large eta; hot time is 18-21 % at every budget; the corrected budget does not reduce the hot
time in a hotter room), prediction 7 held for heat (18 % -> 0 %) and excess, not for sAP (no significant change).

Addendum 3 (11 Nov 2026, ~15:15 IST, before these runs): a hold capped at the guard temperature
The hold is allowed while the board is below 85 C. Proposed change: allow it only below 78 C, the thermal guard's own
threshold (replay.py hold_max_c). Runs th_hold78 (lab) and th_hold78_amb10 (room +10 C), 24-min missions, seeds 1-5,
against v41 and th_amb10_b2.8.
8. The hot time falls far below v4.1's 18 % in the lab and below th_amb10_b2.8's 58 % at +10 C, while the hold
   still covers most blackout time below 78 C; sAP within the paired interval of v4.1 (lab) and of th_amb10_b2.8.
   If the hot time does not fall much, the guard's own heating is the cause and we say so.

Result of addendum 3 (11 Nov 2026, ~16:00 IST): prediction 8 held in the lab (hot time 18 % -> 0 %, excess 0.52 ->
0.22 W, sAP +0.0000 +- 0.0001) and failed at +10 C (57 %: the price is at its cap in 29 % of the updates, cap term
0.75 W). The replay's hot-share level differs from the hardware's by 16 points on average (r 0.98 between
policies), so all shares are comparisons between settings. Paper 2: Section "Guarantees", "The settings, swept in
the replay".

Addendum 4 (11 Nov 2026, ~20:00 IST, before these runs): the price cap at +10 C, and a self-calibrating budget
Both with the hold capped at 78 C. (a) th_hold78_amb10_cap{10,20,50}: the price cap raised from 5. (b) th_adapt_amb{0,5,10}:
the budget follows an online estimate of the room's offset, a_hat = T + tau dT/dt - b P (the controller's own fit,
b = 11.31 C/W, tau = 149 s, smoothed over 120 s), B = (68.9 C - a_hat) / b clipped to [2.2, 4.5] W; 68.9 C is what
the controller's fit gives at 2.8 W, so in the lab B stays near 2.8 W. Compared with th_hold78 (lab), th_hold78_amb5
and th_hold78_amb10. 24-min missions, seeds 1-5.
9. A higher cap lowers the hot time at +10 C (the cap term was 0.75 W at cap 5), by more at higher caps, with sAP within
   the replay's bias of th_hold78_amb10.
10. The adaptive budget stays within 0.2 W of 2.8 W in the lab (th_adapt_amb0 ~ th_hold78 in hot time and sAP), and
    at +5 and +10 C lowers the budget (to ~2.4 and ~2.0 W, clipped at 2.2) and the hot time below th_hold78_amb5 and
    th_hold78_amb10. If the board's floor power (idle + forecaster + radio, ~2.4 W) already exceeds the budget at +10 C,
    the hot time stays high and we say so: no budget can then help, only less onboard work or cooling.

Results of addendum 4 (11 Nov 2026, 20:50 IST). 9: partly right. A higher cap lowers the hot time at +10 C (57 % -> 42 %,
sAP 0.045 vs 0.046), but caps 10, 20 and 50 give identical runs: the price never passes 7.0, so any cap above 7 is
the same. The cost is freshness (98.7 % -> 89.4 %). 42 % is still hot because the 2.8 W budget itself is too high at
+10 C: the plant (34.4 C + 12.73 C/W x P + 10 C) crosses 80 C at 2.81 W. 10: in the lab right (budget 2.65 W, hot 0 %,
sAP 0.047 vs 0.046). At +5 and +10 C the budget falls as predicted (final estimates 2.43 and 2.10 W; the estimated
offset is 41.5 and 45.2 C against 42.3 and 47.3 C, i.e. 2 C low at +10 C, where the temperature sits at the 85 C
limit and dT/dt reads zero), but the hot time barely moves (22.5 % vs 24.5 % at +5 C, 52.5 % vs 56.7 % at +10 C)
because the price is at its cap of 5 in 73-74 % of the updates: the budget cannot be enforced. Both failures point to
the same pair of changes, tested next.

Addendum 5 (11 Nov 2026, 21:00 IST, before these runs): a raised cap with the adaptive budget, and the hard guard
Replay plant (from the replay's own fit): steady temperature 34.4 C + ambient + 12.73 C/W x P. With no onboard
inference the Pi draws its floor, idle 1.89 + forecaster 0.29 + radio ~0.2-0.3 W, about 2.45 W -> 65.6 C + ambient.
(a) th_adapt_amb{5,10}_cap50: adaptive budget as in addendum 4, price cap 50.
(b) th_guard_amb{0,5,10,15}: the hold capped at 78 C and the hard guard: no onboard inference while T >= 78 C
    (guard_hard_c 78). Baseline th_hold78_amb15 (no hard guard).
Theorem 3 (to be written in paper 2): if the floor's steady temperature is below the guard temperature, the guard
keeps T <= 78 C plus the rise during one inference already started; the ambient margin is 78 - 65.6 = 12.4 C.
11. th_guard: temp_max <= 78.5 C and hot share 0 % at +0, +5 and +10 C; at +15 C the floor alone reaches ~80.6 C, so
    temp_max is 80-81.5 C and the hot share is large (most of the mission after warm-up, > 50 %), but no run reaches
    the 85 C limit. th_hold78_amb15: hot share above th_hold78_amb10's 57 %, temp_max 85 C.
    sAP within 0.003 of th_hold78_amb{0,5,10} (onboard share is ~6 %); freshness lower than without the guard at
    +5 and +10 C (the guard removes onboard inference during outages), by an amount we report.
12. th_adapt_cap50: at +5 C the budget (~2.4 W) is met within 0.15 W and the hot share falls below th_adapt_amb5's
    22.5 % to near 0 (< 5 %); at +10 C the budget (~2.1 W) is below the floor, so power settles near the floor
    (2.5-2.7 W), the temperature near 76-79 C and the hot share far below 52.5 % (< 15 %); freshness below
    th_adapt_amb10's 97.9 %, as in the cap runs.
(c) th_floor_amb{0,5,10,15} (added 11 Nov, ~22:00 IST, before the runs): the fixed offload policy (laptop, m640 Q90,
    no onboard inference) at each room temperature: the floor temperature theta_f of Theorem 3 measured directly.
    The hardware's 24-min offload-only runs average 2.26 W and 62.7-63.6 C, the controller's fit gives 62.8 C.
13. th_floor: mean temperature 34.4 + 12.73 x P + ambient with P = 2.2-2.5 W, i.e. 62-67 C in the lab, and the
    maximum within 5 C above the mean; at +15 C the mean exceeds 78 C, which is why th_guard_amb15 cannot hold the
    guard (Theorem 3: the temperature is never below the floor's).

Addendum 6 (11 Nov 2026, ~22:30 IST, before training): a constrained deep-RL baseline (validation/hardware/rl_baseline.py)
PPO-Lagrangian, trained on 2-min replay episodes with seeds 1001+ (600 episodes: 300 iterations x 2 workers), the
multiplier on the measured mean power against v4.1's 2.8 W; greedy policy evaluated on the 24-min mission (seeds 1-5)
and the 2-min mission and random scenarios (seeds 1-10), against v4.1 on the same seeds.
14. Its mean power ends within 0.3 W of 2.8 W on the 24-min mission (the multiplier enforces the budget on average).
15. It does not beat v4.1's streaming AP by more than the replay's accuracy bias on any of the three scenarios, and is
    below it by more than that on at least one. A learned policy with this much training is a baseline, not a
    contender; if it does beat v4.1, we report that.
Addendum 6, attempt 2 (11 Nov, ~23:00 IST): the first training run charged the radio energy of the transfer only;
in the replay the radio stays on until the acknowledgement, so the cost was too low (fixed, cost now within 3 % of the
billed power). The second run ended at 2.3 W, but the multiplier had wound up to 88 while the policy was still
learning, and the argmax policy always skipped (availability 0). Attempt 3, before its run: the multiplier capped at
20 (about twice the price at which one s640 inference stops paying for the ticks its result is shown), its step 0.1,
600 iterations; the stochastic policy is evaluated, as trained. Predictions 14 and 15 stand. Attempt 2 is archived
(experiments/results/hardware/replay/rl_baseline/_superseded/attempt2/).
Results of addendum 6, attempt 3 (11 Nov 2026, ~22:35 IST; checkpoint of iteration 571, multiplier 18.5; stochastic
policy; paired with v4.1 on the same seeds, mean difference +- 95 % interval):
  24-min mission (5 seeds): sAP 0.036 vs 0.046 (-0.010 +- 0.001), power 2.43 vs 3.41 W, fresh 77.7 %, hot 0 %
  2-min mission (10 seeds): sAP 0.042 vs 0.054 (-0.012 +- 0.003), power 2.42 vs 3.48 W
  2-min random (10 seeds):  sAP 0.047 vs 0.050 (-0.004 +- 0.003), power 2.47 vs 3.16 W
14: missed narrowly. The policy keeps the budget but undershoots it: 2.43 W, 0.37 W below 2.8 W (predicted within 0.3).
15: right. It does not beat v4.1 anywhere and is below it by more than the replay's bias (0.003) in all three
    scenarios. Caveat for the paper: v4.1 spends about 1 W more than the RL policy (its hold and cap let it exceed the
    budget, Theorem 1), so part of the gap is power v4.1 is allowed to spend; the comparison is at the same nominal
    budget, not at equal power.
