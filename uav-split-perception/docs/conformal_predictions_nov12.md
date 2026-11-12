# A distribution-free deadline probability (paper 2, roadmap L8): predictions before the runs (12 Nov 2026)

Why. v4.1's chance of meeting the 300 ms deadline assumes Gaussian goodput around its estimate. Recent work gives edge
inference distribution-free deadline guarantees with conformal prediction (Kalør & Ohtsuki 2025; Binucci et al. 2025).
Can the controller use one, and does it change anything?

Method (validation/hardware/replay.py switch, policy v41_conf; driver validation/hardware/replay_conformal.py).
- Each path keeps the last 200 ratios rho = (goodput estimate when the transfer started) / (goodput achieved), from
  completed transfers of more than 20 KB.
- The chance of arriving within a budget X is the share of these ratios with rho <= r / R(X), where r is the current
  estimate and R(X) the rate the frame needs, counted as k / (n + 1), the conservative conformal rank.
- With fewer than 20 ratios the Gaussian is used. Everything else is v4.1.
- Runs: v4.1 and v41_conf in the replay, 4 scenarios (mission, mission_mirror, random, static_good) x 10 seeds,
  20-s phases, paired on the same link draws.
- Measured: calibration of p_on (reliability bins, expected calibration error), the miss rate of frames sent with
  p_on >= 0.95, streaming AP, freshness and Pi power.

Predictions:
1. The Gaussian p_on is cautious (the replay's earlier check: 94.4 % predicted, 98.5 % observed, ECE 0.042). The
   conformal p_on is closer to calibrated: ECE at most 0.03.
2. Among frames sent with p_on >= 0.95, the observed miss rate is at most 5 % with the conformal estimate, as its
   construction implies for exchangeable errors.
3. Because the conformal estimate is less cautious, v41_conf sends slightly larger frames or uses the slower path more
   often. Streaming AP changes by less than the replay's resolution (|diff| < 0.003); freshness changes by at most 2
   points.
4. Conclusion expected: the guarantee can be had at no accuracy cost, but it does not raise accuracy, consistent with
   the oracle finding that better link prediction adds nothing.
