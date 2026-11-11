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
