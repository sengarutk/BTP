# Every controller's equations against the code and the logs (12 Nov 2026)

Two checks for each controller:
1. Do the equations written in the Results Brief (Part 16) and in paper 2 ("Controller") match the code that ran?
2. Do the logged price updates follow the stated rules? (`paper2/theory_check.py` for mu;
   `paper2/price_rules_check.py` for lambda_F, lambda_T and mu_e.)

| Controller | Equation (Part 16 / paper 2) | Code | Matches | Logged updates checked |
|---|---|---|---|---|
| v1 (Part 9) | U = fps·q·A/A_ref − lambda(SoC)·E·fps; q = p_on + 0.25·max(0, p_late − p_on); lambda = 0.01·(1 + (0.15/SoC)²); late window 1.5 s | `adaptive.py` `utility()` (lines 333-358), defaults `--lambda0 0.01 --late-ms 1500 --late-value 0.25` | yes | no price updates |
| v2 (rate objective) | value = (A_v/A_ref)·q / T_busy; T_busy = max(t_tx + rtt, one frame), onboard rounded up to frames; late window 1 s | `adaptive2.py` `path_value` / `onboard_value`, `objective == "rate"` branch | yes | no price updates |
| v3 (+ forecasting) | value = (A_v/A_ref)·H(L, T)·p_late; H = mean of rho at L + f·T, f = 0, 1/4, ..., 1; T = T_busy / n_active; onboard factor p_late = 1 | `objective == "stream"` branch, `hold_quality` | yes | no price updates |
| v4 | value_v3 − mu·E_cam; mu ← clip(mu + 0.1(P̄ − B), 0, 5); guard mu ≥ 1 at ≥ 78 °C; hold when no path has p_on > 0.2 and the board is below 85 °C, and for 1 s after | `cam_price`, `power_logger` (lines 640-690), exemption (lines 994-999) | yes | mu: 66,655 updates, 376 runs, 0 unexplained |
| v4.1 | + lambda_F·p_on·[AoI + L ≥ D]; lambda_F ← clip(lambda_F + 2(0.95 − F̂_5s), 0, 2) | lines 452-453, 474-475, 937-947 | yes | lambda_F: 53,758 updates, 158 runs, 0 unexplained (8 runs before the cap ran uncapped) |
| v4.2 | − mu_e·E_edge; mu_e ← clip(mu_e + 0.1(P_extra − B_e), 0, 5) | lines 450-451, 674-682 | yes | mu_e: 43,355 updates, 239 runs, 0 unexplained (28 runs before the cap ran uncapped) |
| v5, variants, v5.1 | camera joules priced at mu + lambda_T; lambda_T ← clip(lambda_T + 0.01(θ̂ − 75), 0, 2); θ̂ = θ + (θ_ss − θ)(1 − e^(−60/τ)) | `cam_price`, lines 665-670 | yes | lambda_T: 34,929 updates, 170 runs, 0 unexplained |
| Heat price (mesh) | lambda_T alone: no energy price, no hold, no guard | `--thermal-aware` without `--energy-aware` | yes | in the lambda_T count |
| LEAF-style | mu fixed (`--mu-fixed`) | line 655 | yes | constant by design |

Energy constants (`experiments/results/hardware/energy/energy_constants.json`):
- Pi onboard inference: 0.324 / 0.741 / 2.229 J (n320 / s320 / s640).
- Pi radio power: 0.211 + 0.016·r W.
- JPEG encode: 0.005-0.007 J.
- Jetson idle: 4.08 W.

These equal the values quoted in Part 16 and in paper 2.

Not covered by these checks:
- Per-frame decisions. Their inputs (goodput estimate, predicted latency) were not logged in the hardware campaigns, so
  the decisions cannot be recomputed from the logs. The `pred` logging added on 29 Oct makes this possible from the
  next board session.
- The inputs of lambda_T (θ̂) and mu_e (P_extra). Each update follows its rule given its logged input; the inputs
  themselves were not re-derived.
- Whether the board-side copy of energy_constants.json equals the repository's (needs the boards; md5 to be compared
  at the next session).

## Mathematical verification (13 Nov 2026)

Beyond "the code matches the paper": each formula's derivation, units and signs were checked, each proof was
re-derived line by line, and each statement was tested on random cases (`paper2/theorem_random_checks.py`, seed
20261113, results in `experiments/results/hardware/theory_check/random_checks.json`). Each test was also run with one
assumption broken (negative control), to show that it can fail.

| Item | Derivation / proof | Units and signs | Random test | Negative control |
|---|---|---|---|---|
| p_on, p_late (Gaussian deadline probability) | P(g >= R_need) = Phi((r - R_need)/sigma) for g ~ N(r, sigma²); R_need = 8b / (1000 (X - t_enc - t_rem - rtt)) Mbit/s | bits / (ms·10³) = Mbit/s; argument dimensionless | (calibration in the replay: ECE 0.042, cautious) | - |
| Value V (stream) | expected held accuracy: A/A_ref × 5-point mean of rho over [L, L+T] × p_late; a modelled objective, not a theorem | dimensionless; mu·E: (1/J)·J; lambda_F·p_on dimensionless | - | - |
| Rate value (v1, v2) | accuracy-weighted on-time results per second; energy term J × 1/s = W, times a price per J | value per second throughout | - | - |
| E_cam(path) | encode J + radio power (a + b r) W × airtime 8b/(10⁶ r) s | J | - | - |
| mu update (energy price) | projected dual ascent on E[P] <= B: rises when P̄ > B | correct sign | (Theorem 1) | - |
| lambda_F update | multiplier of F >= 0.95: rises when F̂ < 0.95 | correct sign | - | - |
| mu_e, lambda_T updates | multipliers of the Jetson budget and of θ̂ <= 75 °C | correct signs | - | - |
| θ̂ (60-s prediction) | exact solution of the first-order model for constant input | °C | - | - |
| Theorem 1 | telescoping sum of the update; s_t >= 0 for plain, clipped and guard-raised steps, so only held/capped steps can loosen it | W | 20,000 random sequences: 0 violations | without the hold/cap term: 2,130 of 3,000 fail |
| Theorem 2 | drift-plus-penalty with L = mu²/2: ΔL <= eta mu (P - B) + eta² (P - B)²/2; greedy >= best stationary policy | value units | 100 random i.i.d. problems, U* exact by duality: 0 violations | - |
| Proposition (budget, temperature) | integrate θ' = (a + bP - θ)/τ over the window | °C | 2,000 profiles: error <= 1.4·10⁻¹² °C | - |
| Theorem 3 (a) | superposition, θ_i >= 0 | °C | 3,000 cases: 0 violations | - |
| Theorem 3 (b) | bounds (i) and (ii) re-derived; their crossing x* = (H - θ_f)/(H - θ_lo) gives the stated bound (algebraic identity checked) | °C | 3,000 cases: 0 violations, closest 0.28 °C below the bound | without the guard: 425 of 600 fail, by up to 16 °C |
| Theorem 3 constants | δ_i = 11.31·3.1·(1 - e^(-0.76/149)) = 0.18; δ_n = 8.5·5/24.3 = 1.75; bound 79.93 °C; room margin 14.5 °C; converse 10.8 °C | - | - | - |
| Paper 1 proposition (break-even goodput) | proof re-derived (frame rate and on-time probability of the qualifying image setting) | Mbit/s | 20,000 random options: 0 violations | image less accurate than required: 1,853 of 5,000 fail |

What remains a model, not a mathematical fact (stated as such in the papers):
- The deadline probability assumes Gaussian goodput: calibrated in the replay; on hardware from the next session.
- V is the controller's chosen objective: an estimate of held accuracy, not a proved optimum. Its 5-point average,
  T = T_busy / n_active, and the freshness bonus are approximations.
- Theorem 2 is idealised; the hardware breaks six of its assumptions (listed in paper 2).
- The Proposition and Theorem 3 rest on the first-order thermal model: mean temperature checked within 1.6 °C on 16
  long runs; the guard's peak is checked only in the replay.
