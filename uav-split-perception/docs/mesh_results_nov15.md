# Mesh board sessions 14-15 Nov 2026: every verdict in one place

Source of each line: `docs/board_session_predictions_nov.md` (P*) and `docs/mesh_predictions_nov14.md` (T*, S*, G, C),
written before the runs; the measured values are in those files. Testbed: `docs/mesh_session_nov14.md`.
Boards: camera pi-relayyy (and pi-receiver in T6/S6), Nano1 (and Nano2 in T6/S6), pi-sender as the ground radio.

| Test | Claim it bears on | Verdict | What it means for the papers |
|---|---|---|---|
| P1.1-P1.2 planner | a greedy priced choice ties a 30-frame planner | held, held | the replay's small planner lead is within its bias; v4.1 needs no planner |
| P2.1 | Theorem 1 (power ≤ budget + stated terms) | held (2.80-2.87 W; 3.57-3.59 W) | theorem confirmed on new runs; update by update in T4.5 |
| P2.2 | budget → mean temperature (one fit) | **did not hold** (7-11 °C below the fit) | needs a per-board intercept (pi-relayyy 29.72 + 11.66 P) |
| P2.3 | the price prevents throttling | partly (v4.1 never throttles; unpriced 4.7 W, 80-83 °C, throttles 0-7 %) | mechanism shown; "sizeable throttling" overstated for this board |
| P2.4 | the energy price costs no accuracy | held (−0.004 / −0.009) | headline kept |
| P3.1-P3.3 noisy relay | order hier ≥ v41 > fixed under relay loss | partly / **not as written** / partly | order holds at 2 %, ties at 5 %; v41 keeps 90-93.5 % within the deadline, not > 95 % |
| T9.1-T9.4 | the topology decides where the decision belongs | **all held** (5/5 each) | the brief's two-campaign limitation is removed |
| T7.1 | 15 fps: camera-bound | held | — |
| T7.2 | 60 fps changes nothing | **did not hold** (+21 %) | v4.1 leaves the radio idle between 30-fps ticks: new finding |
| T7.3 | encode ahead helps | mostly (+10 %, latency +5-6 ms) | cheap improvement for v4.1 |
| S6.1-S6.4 (Nano2 as host) | v4.1's rule collapses with many streams, pull does not | partly, held, not (1.44×), partly | superseded by the fair re-run |
| S6.1-S6.6 (two camera Pis) | the same on real camera Pis | held, held, **held (6-7×)**, partly, **fairness not held**, held | pull one ahead: 20-22 on-time/s at 8 streams vs v4.1's 2.9-3.7; no fairness claim |
| T8.1-T8.4 | v4.1+ (first design) | not, not, held, not (v41) / held (v4.1+) | the capped hold removes the hold's heat at no accuracy cost; first room budget and YOLO11n-640 failed |
| T4.1 | the hold heats the board on long missions | held (18.7 % ≥ 80 °C) | reproduces the original Pi's result on a mesh board |
| T4.2 | the capped hold removes it | partly (0.5 %, never throttled; peaks 80.4-81.5) | paper 2's main heat result |
| T4.3 | Theorem 3 (b): guard peak ≤ 79.9 °C | **did not hold** | a fast thermal mode overshoots 1.6-3.5 °C; corrected bound guard + 3.5 °C holds on every run |
| T4.4 | no accuracy cost | held (−0.0014 / −0.0017) | — |
| T4.5 | Theorem 1 holds update by update | **held** (15/15 heat runs, 121/121 new runs, 0 unexplained steps) | theorem confirmed on every mesh run; avg power ≤ budget + 0.52 W, inside the bound |
| T6.1, T6.4, T6.5 | two camera drones share the channel; no heat chain; Nano2 uses YOLOv8m | held | — |
| T6.2 | a second edge drone helps | **did not hold** (−21 % sAP) | on one shared channel more paths in flight make every result later: channel awareness needed |
| T6.3 | v41j2 moves frames to Nano2 when Nano1 degrades | partly | the shift happens, the overall loss remains |
| T8R.1 | per-board room budget holds its power and its temperature target | partly (budget 3.29-3.36 W every run; 2nd-half 72-77 °C, > 72 in 5/6) | the budget is not a temperature target under bursty load; keep the fixed 2.8 W budget as the headline |
| T8R.2 | v4.1+ on the mission: ≤ 3 % at ≥ 80 °C, no throttling | partly (never throttled vs v41's 9-11 samples; 0.9-6.8 % vs v41's 20-22 %) | the capped hold cuts the hot time 3-23× at a higher budget |
| T8R.3 | v4.1+ costs no accuracy | held (sAP +0.0022; mission 0.1342 vs 0.1312, random 0.1133 vs 0.1088) | 3 reps (4th cut) |
| T8R.4 | YOLO11n-480 replaces s320 onboard | held (192 ms; 78-83 % of onboard frames, 96-100 % in the blackout) | onboard accuracy upgrade works; 95th-pct AoI on the mission 367 → 500 ms |
| G.1 | guard 76.5 °C keeps the peak ≤ 80.0 °C | **did not hold** (79.3 / 80.4 / 79.8 °C; ≥ 80 °C 0.02 % in r2; never throttled) | δ_fast is 3.9 °C, not 3.5: Theorem 3 (b) with the measured δ_fast, no fixed-guard claim |
| G.2 | the 76.5 °C guard costs no accuracy | held (sAP 0.1228 vs 0.1263; freshness 0.841 vs 0.854) | the lower guard is free |
| C.1-C.3 | a per-camera cap on paths in flight recovers T6's loss | **none held** (sAP +0.002; −2.5 deadline-met/s; paths 5-19 ms faster) | per-camera rule cannot see the other camera; swarm-wide coordination (as S6's pull) is the open fix |
| F.1 | final controller ties v4.1 (5 reps) | held (+0.0006 / −0.0032) | the final configuration costs nothing on mesh scenarios |
| F.2 | final ties AccuMO and LEAF | **did not hold**: AccuMO +0.016 in multihop (5/5), final +0.007 on the mission (5/5); LEAF +0.004 multihop | P1.1 was underpowered; "greedy ties planner" withdrawn for multihop |
| F.3 | AccuMO/LEAF use ≥ 0.25 W less | held (0.36-0.60 W less, 10/10) | v4.1 fills its budget; state it |
| F.4 | Theorem 1 and no throttling for the final | held (10/10; 536/536 runs) | — |
| FH.1-FH.2 | the final controller on the 24-min blackout mission | held, held (peak 79.3 °C ×3, never throttled; sAP 0.1247) | the final configuration keeps G's heat result and adds a little accuracy |
| D.1-D.4 | DVFS as a third knob (1.8 GHz option, priced) | held, **not**, held, held | used for ~60 % of onboard work, but the budget price spends the saving on more onboard work: no power, heat or accuracy change |
| B.1-B.4 | a 2.4 W budget instead of 2.8 W | **all held** (−0.31 / −0.38 W, −3 °C, sAP −0.0004 / −0.0015; DVFS still neutral) | the power gap to AccuMO/LEAF closes: the final controller's budget is 2.4 W |
| T11.1-T11.5 | video encode on the Pi vs paper 1's scaled times | held, not, not, held, not | the Pi encodes video only ~2× slower than the laptop; the rule's scaling overstates it, so paper 1's Pi video break-even is an upper bound (conservative) |
| T11 follow-up | paper 1's Pi break-even with measured onboard times | B_be falls (headline code 1.88 → 1.72 JPEG, 1.06 → 0.27 video); 0 winning cells with video | model and live sweep (T10) now agree: no split wins on a Pi 5 |
| FX.1-FX.4 | the F.2 fix (`--late-path-skip 0.5`) | partly (+0.015 multihop, 5/5; laptop share 5.4 %), not narrowly (−0.003 mission, n.s.), held, held | closes the planner's multihop lead; adopted in the final controller with the backup caveat |
| TB.1-TB.2 | the SSH tunnel's cost on the laptop path | held, held (+2.3 ms per 1 KB RTT, +4 ms per frame, −20 % peak goodput) | a small measured artefact; A8's bridge re-run not needed |
| Y.1-Y.2 | YOLO11s split codes timed on the Pi (paper 1's second detector) | not (times within 2 % of the rule), held (0 wins) | the network times were right; JPEG encode overstated: Pi B_be falls 12-14 % (0.68-1.53 Mbit/s) |
| T10.1-T10.4 | paper 1: break-even goodput of the learned codes, predicted from board benches | **held, held, partly (3/4), held** | no break-even on a Pi 5 camera (rate-limited link); with a shared-radio (token-bucket) link the 4 KB code wins at 0.5 Mbit/s: the advantage depends on how the link is slow |

## Fixes found and made during the sessions (all before the runs that test them)

- Multihop relay kept on Nano1 with five boards (`arun_mesh.sh`).
- Health check: fail on under-voltage only; optional boards; profiling reported.
- `pull_bench.py`: server-clock turn order (mixed board clocks starved one host).
- YOLO11n priced at its measured 0.96 J (it was free: 0 J by default).
- Room-following budget: per-board fit, steady-only updates (the replay's derivative estimator failed on the Pi).
- Onboard variants timed at start-up (one cold inference had locked YOLO11n-480 out).
- Theorem 3: fast-mode term; guard 76.5 °C under test.
- Channel-aware sending (`--max-paths-busy`), from T6 (tested: did not help).

## Runs lost and re-run

- Energy test run 4 (laptop battery shutdown 14 Nov 22:35).
- 3 T6 runs on laptop battery (weaker ground GPU).
- 1 T8 re-test run before the onboard-timing fix.

All archived with the reason in `experiments/results/hardware/_superseded/`.
