# Paper 2 (draft 1, 30 Oct 2026): the priced streaming-perception controller

`bash build.sh` regenerates every number (`make_metrics.py` -> `generated/metrics.tex`, sources in
`generated/metrics_sources.md`) and builds `main.pdf` (fails on an undefined number, citation or reference).

Content: the argument of Part 20 of the Results Brief — energy pricing (Wi-Fi G9/G11, mesh campaign 2, 24-min mesh
missions), the objective matched to the forecaster (Wi-Fi fc2, the 240-run G12 ablations), decision placement by
topology (mesh campaigns 1-2), the literature schedulers and the AccuMO-style planner (replay, 19.10-19.11), the
negative results (heat price, edge-drone price). Bibliography: `paper/references_verified.bib` plus A2-UAV, Glimpse and
StreamFlow verified via doi.org on 30 Oct and five entries of `paper/references.bib` (CrossRef-checked 30 Oct).

In since draft 1: a testbed figure (TikZ), the decay-curve figure (`make_figures.py`), the hindsight-oracle and clairvoyant-link results, the
calibration of the deadline probabilities (replay), the two-camera hardware swarm and the calibrated swarm simulation,
the whole-system energy view (G11, board view), and related work verified via doi.org on 30 Oct (Chameleon, AWStream,
Kalibera & Jones, Qu TNSM 2024, Xu TPDS 2021, Diniz ICUAS 2025, Jiang TMC 2023, Younis TNSM 2024, Zaki TVT 2024).

Not yet in this draft:
- the board campaign against the planner (tools/campaign_mesh4.sh), which decides the planner claim;
- the learned-bottleneck result as a related finding (in paper 1).
Design constants (300 ms deadline, 30 fps, 2.8 W budget, step sizes 0.1 and 2, freshness target 0.95) are written out:
they are the defaults of validation/hardware/adaptive2.py.
