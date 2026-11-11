# Detector fine-tuned on JPEG (11 Nov 2026) — the fair counterpart of the jointly trained splits

`evaluation/jpeg_tuned_detector.py`, chain `scripts/jpeg_tuned_chain_nov11.sh` (under `scripts/guarded_run.py`).
The jointly trained codes (`../joint_bottleneck/`) train every server-side layer of a split for 30 epochs, while the
JPEG path used the untuned detector. For an image every layer is server-side, so this trains every layer on
JPEG-decoded images with the same recipe: VisDrone YOLOv8s, layer 0 wrapped by a JPEG encode → decode (OpenCV, as
the hook that measured the paper's JPEG rows), AdamW lr0 1e-3, cosine to 0.1 × lr0, 30 epochs, batch 8, Ultralytics'
augmentation, epoch chosen on the same 288 VisDrone-VID val frames (JPEG'd the same way), the untuned detector a
candidate. Evaluation on the 548 VisDrone-DET val frames at each of 18 qualities; the payload is checked to equal
the untuned row's (it does, at every quality) and each quality is paired-bootstrapped against the untuned detector.

Runs
- `jpegtuned_qmix_r1`: each training image at a quality drawn from 10, 15, …, 95 (one detector for every setting).
  Selection mAP 0.197 at the start, best 0.236 at epoch 16 → trained (90 min).
- `jpegtuned_q35_r1`: every image at Q35 (the most generous case at one quality). Start 0.177, best 0.225 at epoch
  18 → trained (96 min).

| Quality | 10 | 20 | 35 | 50 | 65 | 70 | 75 | 80 | 85 | 95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| untuned | 0.099 | 0.160 | 0.188 | 0.203 | 0.220 | 0.225 | 0.231 | 0.240 | 0.247 | 0.264 |
| tuned (mix) | 0.169 | 0.199 | 0.217 | 0.224 | 0.231 | 0.233 | 0.234 | 0.237 | 0.239 | 0.242 |
| gain | +0.070 | +0.039 | +0.029 | +0.021 | +0.011 | +0.008 | +0.004 n.s. | −0.003 n.s. | −0.009 | −0.021 |

(mAP@[.5:.95]; every quality is in `eval_jpegtuned_qmix_r1_q*.json`; significant = paired 95 % interval excludes 0.)
The dedicated Q35 detector reaches 0.220 against 0.217 for the mixed one, +0.003 [−0.001, +0.007], not significant
(`paired_dedicated_vs_mix_q35.json`, `jpeg_tuned_detector.py compare --q 35`).

Use in the break-even rule (`evaluation/break_even_rule.py`, `break_even.json` → `jpeg_tuned`): the fair baseline is
`jpegtuned_qmix_r1_best_of_both`, at each quality the better of the tuned and the untuned detector (the server knows
the quality it receives). The tuned detector alone (`jpegtuned_qmix_r1`) is weaker at high quality, which leaves the
largest codes with no qualifying JPEG setting; it is stored for completeness only. Simulator check against the same
baseline: `../break_even/sim_check_tuned.json` (`evaluation/break_even_sim.py --tuned jpegtuned_qmix_r1`).

Weights (`weights/jpeg_tuned/*.pt`) and run directories (`experiments/jpeg_tuned_runs/`) are not in git; the smoke
run `jpegtuned_qmix_smoke_f0.02` (2 % of the data, 1 epoch) only checked that the pipeline runs.
