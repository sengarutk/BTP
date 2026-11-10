# Jointly trained bottlenecks, run 2 (11 Nov 2026) — hardening plan, Phase 2

`evaluation/joint_bottleneck.py`, chain `scripts/joint_chain_nov11.sh`: the bottleneck and the detector's server-side
layers trained together on the detection loss, starting from the code distilled on the frozen detector.
AdamW, lr0 1e-3 (4-rate pilot on k4_c16, `train_*_pilot_*.json`), cosine to 0.1 × lr0, 30 epochs, no early stopping.
The epoch is chosen on 288 VisDrone-VID val frames (`datasets/visdrone_joint_sel`) that neither model saw; the start
is a candidate. Evaluation on the 548 VisDrone-DET val frames, as for the frozen codes
(`experiments/results/learned_bottleneck/system.json`).

| Code | Payload | Frozen mAP50-95 | Joint mAP50-95 | Gain | Best epoch |
| --- | --- | --- | --- | --- | --- |
| k4_c4 | 3.4 KB | 0.142 | 0.183 | +0.041 | 25 |
| k4_c16 | 13.4 KB | 0.206 | 0.219 | +0.013 | 18 |
| k2_c8 | 26.5 KB | 0.233 | 0.238 | +0.005 | 22 |
| k4_c32_s1 | 104.8 KB | 0.253 | 0.256 | +0.002 | 23 |

The full detector scores 0.267 on the same frames. Every code chose a trained epoch over its start. The bootstrap
half-width of each estimate is up to 0.008 mAP, so the two smallest gains (+0.005, +0.002) are not claimed; the split's
server side gets extra training while the JPEG path keeps the unmodified detector, so the gains bound the split's
advantage from above.
Break-even rule with these codes: `experiments/results/break_even/` (0 exceptions in 657 winning cells);
paper text: `paper/drafts/design_rule.tex`. Run 1 (invalid) is in `_superseded/run1_nov10/`.
Weights (`weights/joint_bottleneck/*.pt`, 23 MB each) are not in git.
