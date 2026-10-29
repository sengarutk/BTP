# Controller scoring functions, exactly as implemented (checked line by line, 12 Oct 2026)

Code: v1 `validation/hardware/adaptive.py` (`utility`), v2–v5 `validation/hardware/adaptive2.py`
(`path_value`, `onboard_value`, `power_logger`, dispatch loop), swarm `coordinator.py`.
Every term below has its units; the two sides of every subtraction have the same units.

## Common quantities

| Symbol | Meaning | Unit |
| --- | --- | --- |
| D | deadline, 300 | ms |
| L_late | late window: 1500 (v1), 1000 (v2+) | ms |
| w_late | value of a late result relative to an on-time one, 0.25 | – |
| Δ | camera frame period, 1000/30 = 33.3 | ms |
| b | JPEG size of the variant (EWMA of real frames) | byte |
| r, σ | path goodput estimate and its standard deviation (EWMA; lowered while a frame is stuck) | Mbit/s |
| t_enc, t_rem, rtt | encode time on the Pi, server inference time, round trip (all learned online) | ms |
| t_tx = 8b / (1000 r) | transfer time | ms |
| A_v | measured accuracy of variant v (COCO or VisDrone table) | mAP |
| A_ref | accuracy of YOLOv8s-640 in the same table | mAP |
| Φ | standard normal CDF | – |

Probability of meeting a time budget X (ms) on a path, with uncertain goodput:

  P(X) = Φ( ( r − 8b / (1000 (X − t_enc − t_rem − rtt)) ) / σ ),   0 if X − t_enc − t_rem − rtt ≤ 0

The required rate 8b / (1000 · ms) is in Mbit/s, so the argument of Φ is dimensionless.
p_on = P(D), p_late = P(L_late). Onboard: p_on = 1[t_onb ≤ D], p_late = 1[t_onb ≤ L_late].
Quality of service: q = p_on + w_late · max(0, p_late − p_on)   (–)

## v1 — one action at a time (adaptive.py)

  U(a) = f(a) · q(a) · A_a / A_ref − λ(SoC) · E(a) · f(a)

| Term | Definition | Unit |
| --- | --- | --- |
| f(a) | onboard: 1000 / (⌈t_onb/Δ⌉ Δ); offload: min(30, 1000/(⌈t_enc/Δ⌉Δ), 1000/(t_tx + rtt), 1000/t_rem) | 1/s |
| first term | accuracy-weighted on-time results per second | 1/s |
| E(a) | onboard: 2.7 W · t_onb; offload: 2.7 W · t_enc + 0.31 W · t_tx (times in s) | J per frame |
| E · f | power drawn by the action | W |
| λ(SoC) | λ₀ (1 + (0.15/SoC)²), λ₀ = 0.01; SoC from the scripted mission phase | 1/J |
| second term | λ · W | 1/s |

Switch to the best action only if U_best > U_current + 10 % · |U_current| and 1 s since the last switch
(immediately if the current action's path is down or its U ≤ 0).

## v2 — all servers in parallel, rate objective (`--objective rate`)

Every camera tick, each idle server s proposes v*(s) = argmax_v value(s, v); the frame goes to the idle
server with the largest value, if it is > 0.

  value(s, v) = (A_v / A_ref) · q(s, v) / T_busy(s, v)                                [1/s]

  T_busy = max(t_tx + rtt, Δ) for a path;  ⌈t_onb/Δ⌉ Δ onboard   (in s in the division)

## v3 — streaming objective (`--objective stream --decay FILE`)

The value of a result is the expected accuracy it provides while the drone holds it:

  value(path s, v) = (A_v / A_ref) · H(L, T) · p_late                                 [–]
  value(onboard, v) = (A_v / A_ref) · H(t_onb, T)                                      [–]

  L = t_enc + t_tx + t_rem + rtt  (path) or t_onb (onboard)    latency of the result      [ms]
  T = T_busy / n_active                                       how long it will be held   [ms]
  n_active = number of servers whose best variant has p_on > 0.2 (at least 1)
  H(L, T) = ⅕ Σ_{f ∈ {0, ¼, ½, ¾, 1}} ρ(L + f·T)              mean staleness factor while held [–]
  ρ(age) = measured share of fresh AP kept at that age (linear interpolation of the decay file):
           v3: no forecasting (staleness_decay.json); v3 + fc: forecaster v1 (staleness_decay_forecast.json);
           v3 + fc2: forecaster v2 (staleness_decay_forecast_v2.json)
  Ablation `--decay-shape`: flat ρ = 1; linear ρ = max(0, 1 − age/(2D)); exp ρ = 0.5^(age/D).

## v4 — camera-drone energy price (`--energy-aware --power-budget B`)

  value_v4 = value_v3 − μ · E_cam(s, v)                                               [–]

  E_cam(onboard, v) = J_inf(v): measured 0.324 / 0.741 / 2.229 J for n320 / s320 / s640      [J]
  E_cam(path, v) = J_enc(v) + (0.211 + 0.016 · r) W · 8b / (10⁶ r) s                          [J]
  μ ← max(0, μ + η (P̄ − B)) once per second, P̄ = mean measured Pi power over the last 1 s,
      η = 0.1;  μ ≥ 1 while the measured temperature ≥ 78 °C (thermal guard)                  [1/J]
  Blackout exemption: if no path has p_on > 0.2 (and T < 85 °C), onboard is not priced.

## v4.1 — freshness price (`--fresh-target F*`)

  value_v4.1 = value_v4 + λ_F · p_on · 1[AoI + L ≥ D]                                 [–]

  AoI = age of the newest result received (now − its capture time)                         [ms]
  F̂ = share of camera ticks in the last 5 s with AoI ≤ D
  λ_F ← max(0, λ_F + η_F (F* − F̂)) once per second, F* = 0.95, η_F = 2                    [–]
  (onboard: the same bonus with p_on = 1[t_onb ≤ D])

## v4.2 — edge-drone energy price (`--edge-energy-aware --edge-power-budget B_e`)

  value_v4.2(jetson, v) = value_v4(.1)(jetson, v) − μ_e · E_edge(v)                    [–]

  E_edge(v) = J_Jetson(v) (measured 0.040–0.371 J per inference) + 0.211 W · 8b / (10⁶ r) s   [J]
  μ_e ← max(0, μ_e + η_e (P_extra − B_e)) once per second, η_e = 0.1, B_e > 0 (0.5 W used)     [1/J]
  P_extra = live Jetson board power (1-s mean, reported in every reply) − 4.079 W idle;
            if no report within 2 s: modelled served energy over the last 5 s / 5 s            [W]
  Budgets from a mission time M (`--mission-min`): B = 60 · Wh / M − P_flight (≥ 0).

## v5 — predictive heat price (`--thermal-aware`)

The camera price becomes μ + λ_T:

  value_v5 = value_v3 − (μ + λ_T) · E_cam(s, v) − μ_e · E_edge(v) [+ v4.1 term if enabled]  [–]

  T_ss = 34.43 °C + 12.73 °C/W · P̄₁₀   (measured steady-state fit; P̄₁₀ = mean measured power, last 10 s)
  T̂ = T + (T_ss − T)(1 − e^(−h/τ)),  h = 60 s, τ = 148.8 s (measured)                     [°C]
  λ_T ← min(2, max(0, λ_T + η_T (T̂ − 75 °C))) once per second, η_T = 0.01                [1/J]
  Hard guard raised to 84 °C in the campaign.

## Rate objective with prices (implemented, not used in any campaign)

  value = (A_v/A_ref) · q / T_busy − (μ + λ_T) · E_cam / T_busy − μ_e · E_edge / T_busy       [1/s]

E / T_busy is a power, so price × power has the units of value per second.

## Swarm coordinator (`coordinator.py --mode admission`)

Every 1 s window each camera i reports: other_i = Σ over its non-laptop servers of max(0, best value),
and its laptop-path value at a share of the link, lap_i(k) = max_v value(laptop, v) with r = r_full/k
(r_full = its best goodput over the last 10 s; no prices in these what-if values). The coordinator admits

  k* = argmax_{k ∈ 0..n} Σ_i [ other_i + (k/n) · max(0, lap_i(k)) ]   (ties: larger k)

cameras to the laptop path, rotating which ones (or by modelled state of charge with `--energy-pref`).

## Corrections made during this check (12 Oct 2026)

1. The rate objective divided by the COCO accuracy constant (0.444) instead of the reference of the
   loaded table. All options were scaled by the same factor, so no decision of a past run changes;
   now both objectives use A_ref from the same table.
2. With prices on, the rate objective priced offloading but not onboard inference. Fixed (onboard
   penalty = price × J_inf / T_busy). No campaign used rate + prices.
3. The coordinator valued every k ≥ 2 cameras sharing the laptop link at half the link (exact only for
   k = 2). Cameras now report lap_i(k) at r_full/k for k = 1–8. The two-camera campaign (k ≤ 2) is unchanged.
4. The v1 docstring still described an older "+ eps" term; the code uses q with w_late = 0.25.
