# Joint bottleneck, run 1 (10 Nov 2026) — superseded

Kept for the record; not used by any paper. `optimizer=auto` in Ultralytics ignored `lr0=0.002` and fine-tuned with
AdamW at lr 8.3e-4. On the selection set (last 471 DET-train images, which the detector was itself trained on) the
mAP fell after epoch 1 for k4_c16, k4_c32_s1 and k2_c8, and early stopping (patience 10) kept epoch 1; k4_c4 trained
30 epochs and was still improving. Run 2 (`--run r2`): AdamW lr0 1e-3 set explicitly (chosen by a 4-rate pilot on k4_c16, 3e-5 to 1e-3, a quarter of the data: `train_joint_k4_c16_w128_d2_pilot_*.json`), cosine decay, no early stopping,
selection on 288 VID-val frames neither model ever saw, with the distilled start as a candidate.
Weights: weights/joint_bottleneck/_superseded/run1_nov10/. Training runs: experiments/joint_bottleneck_runs/joint_*_d2/.
