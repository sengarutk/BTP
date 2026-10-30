# Laptop-only additions, part 5 (30 Oct 2026): a learned feature-compression baseline, and the second paper

Continues `laptop_additions_2026-10-30_part4.md`. Brief section 19.12 (built by `scripts/report_part5_oct30.py`; the
text below is the same section, followed by details that are not in the brief).

Write-up `docs/laptop_additions_2026-10-30_part5.md`. Part 20 (section 1) left one test open: a learned, trained compressor for the features. Code `evaluation/learned_bottleneck.py` (training, evaluation, the JPEG and post-hoc measurements, figure) and `evaluation/learned_bottleneck_system.py` (the system model); results `experiments/results/learned_bottleneck/`; weights `weights/learned_bottleneck/`.

- **Design** (BottleFit / supervised compression, here with the detector frozen): a small encoder (two convolutions) after layer 2 or 4 of the VisDrone YOLOv8s outputs a few channels at half or full resolution, quantised per image to 8 bits and coded with zstd-1 (the toolkit's coder); a decoder restores the layer's output and the rest of the detector is unchanged. Only the encoder and decoder are trained, by distilling the detector's own neck outputs (layers 15, 18, 21) and the cut tensor: 6,000 VisDrone2019-DET training images, 471 held out for monitoring, no labels, 20 epochs. DET val (548 images) is the test set.
- **Like for like.** Every payload is measured on the same DET val frames: the learned codes, JPEG at q10–q95 and the post-hoc INT8 + zstd splits (through the toolkit's quantiser and wire format). The VisDrone tables of R3 (`visdrone_ft_split/`) keep the COCO-measured payloads by design, so they were not used for sizes; on VisDrone frames JPEG q50 is 30.4 kB, not 37.4. The validator's warm-up pass on a dummy frame is excluded from every average.

| Payload | kB per frame | mAP@[.5:.95] | JPEG mAP at the same size | JPEG kB for the same mAP | bytes saved against JPEG |
| --- | --- | --- | --- | --- | --- |
| learned, k2, 8 channels | 27.1 | 0.233 | 0.196 | 48.6 | **44 %** |
| learned, k2, 16 channels | 54.2 | 0.251 | 0.239 | 70.4 | **23 %** |
| learned, k4, 4 channels | 3.6 | 0.142 | — | 14.9 | **76 %** |
| learned, k4, 8 channels | 7.0 | 0.181 | — | 22.2 | **69 %** |
| learned, k4, 16 channels | 13.7 | 0.206 | 0.131 | 31.8 | **57 %** |
| learned, k4, 8 channels, full resolution | 26.8 | 0.240 | 0.195 | 55.7 | **52 %** |
| learned, k4, 32 channels | 26.9 | 0.227 | 0.195 | 43.4 | **38 %** |
| learned, k4, 16 channels, full resolution | 52.7 | 0.251 | 0.237 | 69.6 | **24 %** |
| learned, k4, 64 channels | 53.8 | 0.231 | 0.238 | 46.3 | −16 % |
| learned, k4, 32 channels, full resolution | 104.9 | 0.253 | 0.263 | 73.3 | −43 % |
| JPEG q10 | 11.0 | 0.099 |  |  |  |
| JPEG q20 | 16.9 | 0.160 |  |  |  |
| JPEG q35 | 24.3 | 0.188 |  |  |  |
| JPEG q50 | 30.4 | 0.203 |  |  |  |
| JPEG q75 | 46.2 | 0.231 |  |  |  |
| JPEG q90 | 77.8 | 0.256 |  |  |  |
| JPEG q95 | 109.1 | 0.264 |  |  |  |
| post-hoc k2 int8 zstd | 539.3 | 0.267 |  |  |  |
| post-hoc k4 int8 zstd | 263.6 | 0.267 |  |  |  |

- **A learned code beats the image on bits.** It needs 23–76 % fewer bytes than JPEG for the same accuracy, which no post-hoc split does (k4 INT8 + zstd is 264 kB on these frames). Resolution matters more than channels: at about the same size, the k4 code at full resolution with 8 channels reached 0.240 (26.8 kB), the half-resolution one with 32 channels 0.227 (26.9 kB). Not every code wins: k4, 64 channels (53.8 kB, 0.231 against JPEG's 0.238 at that size) and k4, 32 channels, full resolution (104.9 kB, 0.253 against JPEG's 0.263 at that size) lose to JPEG; accuracy saturates near 0.25.
- **It does not reach the unsplit accuracy.** The best code reached 0.253 at 104.9 kB; JPEG q90 reaches 0.256 at 77.8 kB and the unsplit model 0.267. A likely limit is the small decoder with the detector frozen; training the detector with the bottleneck (as supervised compression does) may go further.

**Does it change the system result?** Each option scored with the paper's own model, exactly as its adaptive policy scores it (expected accuracy-weighted on-time results per second; `learned_bottleneck_system.py`), over 31 goodputs from 0.25 to 50 Mbit/s and the paper's onboard speeds plus the measured Pi:

| Onboard speed (YOLOv8s per frame) | goodputs where a learned code beats the best image option | up to | largest gain where the image delivers at least 0.5 accuracy-weighted on-time results/s | learned codes that win |
| --- | --- | --- | --- | --- |
| 40 ms | 25 of 31 | 17.3 Mbit/s | +409 % | k2_c16_w128_d2, k4_c16_w128_d2, k4_c4_w128_d2, k4_c8_w128_d2, k4_c8_w128_s1_d2 |
| 90 ms | 25 of 31 | 17.3 Mbit/s | +437 % | k2_c16_w128_d2, k4_c16_w128_d2, k4_c4_w128_d2, k4_c8_w128_d2, k4_c8_w128_s1_d2 |
| 180 ms | 22 of 31 | 17.3 Mbit/s | +504 % | k2_c16_w128_d2, k2_c8_w128_d2, k4_c16_w128_d2, k4_c4_w128_d2, k4_c8_w128_d2, k4_c8_w128_s1_d2 |
| 360 ms | 13 of 31 | 3.5 Mbit/s | +756 % | k2_c8_w128_d2, k4_c16_w128_d2, k4_c4_w128_d2, k4_c8_w128_d2 |
| 758 ms (the Pi 5, measured) | 6 of 31 | 0.6 Mbit/s | +127 % | k4_c4_w128_d2 |

- **Only with fast onboard compute and a slow link.** The image needs more bits now, so Proposition 1 no longer applies, but it still needs far less onboard work. With YOLOv8s at 40 ms per frame a learned code wins up to 17.3 Mbit/s; on the measured Pi (758 ms) only up to 0.6 Mbit/s, where no option delivers more than 2.7 accuracy-weighted on-time results per second; above that the image wins, because layers 0..k and the encoder cost more onboard time than the smaller payload saves.
- **Verdict for the paper.** "Send the image" stays the answer for the drone computers measured here, except at the lowest goodputs; it is no longer a statement about bits alone. The paper now says so (`paper/main.tex`, section "A Learned Bottleneck", every number generated by `evaluation/make_learned.py`).

**The second paper, first draft.** `paper2/` (`bash build.sh`), framed around the thesis agreed for it: on a fanless drone computer heat is a hidden accuracy cost, and pricing measured power removes it at no accuracy cost (throttling alone costs onboard streaming AP 37–59 % against an emulated full clock). It covers the priced controller — energy pricing on Wi-Fi and the mesh, the objective matched to the forecaster, decision placement by topology, the literature schedulers and the AccuMO-style planner, the hindsight oracle and calibration (replay), the two-camera swarm, the whole-system energy view and the negative results, then a reviewer-style pass (Wi-Fi campaigns' COCO detectors stated, relative effect sizes, sign and wording fixes); 5 pages, a testbed figure, the decay figure and a results table, every number generated from the result files (`paper2/make_metrics.py`, sources in `paper2/generated/metrics_sources.md`), every new citation verified via doi.org. What it still needs is listed in `paper2/README.md`; chiefly the planner's board campaign.


## Details not in the brief

### Training runs (`experiments/results/learned_bottleneck/train_*.json`, laptop RTX 4050)

| Configuration | Epochs | Held-out neck loss (last epoch; MSE / teacher variance) | Minutes |
| --- | --- | --- | --- |
| k2, 16 channels, width 128, stride 2, 2 decoder layers | 20 | 0.112 | 37 |
| k2, 8 channels, width 128, stride 2, 2 decoder layers | 20 | 0.231 | 36 |
| k4, 16 channels, width 128, stride 1, 2 decoder layers | 20 | 0.131 | 27 |
| k4, 4 channels, width 128, stride 2, 2 decoder layers | 20 | 0.677 | 26 |
| k4, 64 channels, width 128, stride 2, 2 decoder layers | 20 | 0.176 | 25 |
| k4, 8 channels, width 128, stride 2, 2 decoder layers | 20 | 0.474 | 26 |
| k4, 32 channels, width 128, stride 1, 2 decoder layers | 20 | 0.090 | 27 |
| k4, 8 channels, width 64, stride 2, 1 decoder layers | 12 | 0.607 | 13 |
| k4, 32 channels, width 128, stride 2, 2 decoder layers | 20 | 0.206 | 29 |
| k4, 16 channels, width 128, stride 2, 2 decoder layers | 20 | 0.302 | 25 |
| k4, 8 channels, width 128, stride 1, 2 decoder layers | 20 | 0.218 | 26 |

The first configuration (k4, 8 channels, width 64, 1 decoder layer, 12 epochs) was a pilot; the family reported in the
brief and the paper is width 128, 2 decoder layers, 20 epochs (`learned_bottleneck.py`, `ARCH`). Batch 8, AdamW
(learning rate 2e-3, one-cycle), mixed precision, horizontal flips, seed 0.

### Checks

- The replica of the detector's forward pass used for training (`run_detector`) equals the real model's neck outputs
  bit for bit (checked on a 640 x 384 input).
- Every evaluation reproduces the unsplit baseline (0.26706) and the JPEG accuracies of the VisDrone codec table
  (q50–q95 identical to the last digit); the post-hoc measurement hook leaves the detector unchanged.
- The validator's warm-up pass on a dummy 640 x 640 frame (549 hook calls for 548 images) is dropped from every size
  average; the measurements made before the fix are archived in `_superseded/learned_bottleneck_warmup_oct30/`.
- Encoder MACs are counted with thop on a 640 x 640 input; layers 0..k use the topology file of the post-hoc rows, so
  learned and post-hoc rows share one basis (`learned_bottleneck_system.py`).
- Tests: `tests/test_learned_bottleneck.py`.

### Approximations in the system model

- JPEG q10–q35 have no row in the VisDrone timing table; they take q50's encode and server times.
- The learned codes' server time is the post-hoc split's server time at the same cut plus the decoder measured on the
  laptop GPU; onboard non-DNN work is quantisation + zstd measured on the laptop, scaled like every other option.
