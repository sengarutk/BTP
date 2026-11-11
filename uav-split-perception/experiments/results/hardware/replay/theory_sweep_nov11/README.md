# Paper 2: step size, budget, room temperature and the blackout hold in the validated replay (11 Nov 2026)

`validation/hardware/replay_theory_sweep.py` (runners `scripts/theory_sweep_*_nov11.sh`), replay with
`--onboard-power power` (the setting validated in `../validate_main_oct30_power_t85`). Predictions, written and
committed before each group of runs, and what happened: `docs/theory_sweep_predictions_nov11.md`.

- `rows/`: one row per run (policy, scenario, seed), with Theorem 1's terms (`price`).
- `theory_sweep_summary.json`: means per policy and scenario, paired differences against v4.1 (`analyze`).
- `runs/` (2.6 GB, the per-frame run files and detections) is kept on the laptop only, not in git; every row can be
  regenerated with the runner scripts (common random numbers, deterministic seeds).

Caveats (in paper 2): every sAP difference here is smaller than the replay's known bias (+0.0053 sAP towards running
less onboard); the replay's thermal plant is Proposition 1's own model; its hot-share level differs from the
hardware's by 16 points on average (r 0.98 between policies); room temperature was never logged on the boards, so
the ambient runs are an extrapolation.
