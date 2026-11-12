# The break-even rule on real measured mesh links (paper 1, roadmap L4): predictions before the run (12 Nov 2026)

Why. The fading test of the rule (break_even_sim.py) used synthetic channel profiles. A reviewer can say the rule is
only checked in our own model and simulator. Here the same simulator test runs on goodput traces measured on the real
AegisSwarm mesh.

Traces. Mesh campaign 2, scenario static_good (no injected faults): the per-transfer goodput samples of the direct
Pi -> Jetson mesh link (link_goodput_samples["jetson"]). The laptop path is not used: its samples read 45-99 Mbit/s,
above the mesh's capacity, because the ground radio's SSH port forward acknowledges data before it reaches the laptop
(a known limitation of the testbed).
- Five realisations: the static_good runs that have at least 600 Jetson samples, sorted by name; the first, last and
  three evenly spaced between.
- From each, a 60-s window starting 30 s into the run, sample-and-hold into the simulator's 10-ms slots.
- Each trace is rescaled to every goodput of the rule's grid (as for the synthetic profiles), so its shape is kept.
- Loss is 0 (the samples are goodput). One-way delay is a constant 20 ms, the rule's assumption.
- The relative spread s is that of the slot trace, which is what the fading rule uses.

Caveat. A per-transfer goodput sample also reflects transfer size and server load, not only the radio. This makes the
trace look more variable than the radio alone, which is a harsher test for the constant rule.

Predictions:
1. The spread of the real traces is 0.35-0.50, between the synthetic moderate (0.38) and vehicular (0.54) profiles;
   the per-run sample spread is 0.41-0.45.
2. The constant-goodput B_be fails on the fast devices (180 ms per inference or less) for 5-25 % of the simulated
   wins, and holds on the Pi (758 ms) and at 360 ms.
3. The fading version, with the traces' own spread, has 0 exceptions (at most 1 % of wins).
4. Model and simulator agree on who wins in 88-96 % of the cells.
