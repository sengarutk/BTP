# Second detector (paper 1, roadmap P1-4): predictions before the runs (11 Nov 2026, ~21:45 IST)

Detector: the VisDrone YOLO11s (weights/yolo11s_visdrone.pt, same 8 COCO-mapped classes as the YOLOv8s). Cut k4 (the
C3k2 output at stride 8, 256 channels at 80 x 80; layers 0-3 are not reused later, so it is the only tensor that
crosses). Bottlenecks: the main family's architecture (width 128, 2 decoder layers, stride 2, 20 epochs, head
distillation on the inputs of the Detect head, layers 16, 19, 22), at 4, 8, 16 and 32 channels. JPEG at the 18
qualities of the rule, post-hoc INT8 + zstd at k2 and k4, all on the 548 VisDrone-DET val frames
(evaluation/learned_bottleneck.py --detector yolo11s; results under experiments/results/second_detector/yolo11s/).
Timings: per-layer host GPU profile of both detectors (evaluation/second_detector.py profile); device times scaled
from the YOLOv8s measurements by the host ratio unless measured.

1. Post-hoc INT8 splits at k2 and k4 need more bits than a Q95 JPEG (as for all 6 detectors of the survey).
2. The learned codes are 3-15 KiB, as for the YOLOv8s (the code size is set by the channel count and the 40 x 40
   grid, not by the detector), with accuracy 0.10-0.24 mAP; the cut has twice the channels, so the encoder costs more.
3. No winning cell lies at or above its B_be (0 exceptions): Proposition prop:be-family is a theorem of the model, so
   this is a consistency check of the pipeline, not a test.
4. The substantive prediction: the codes win only on slow boards and below a few Mbit/s, as for the YOLOv8s. On the Pi,
   B_be of the best code is within a factor 2 of the YOLOv8s value (0.8-1.6 Mbit/s for the frozen codes); on the
   Jetson none of the frozen codes wins above 10 Mbit/s.

## Results (12 Nov 2026, 03:52 IST; evaluation/second_detector.py analyse, experiments/results/second_detector/yolo11s/)

Full YOLO11s: 0.269 mAP@[.5:.95] on the 548 frames. Host GPU time 1.42x the YOLOv8s; on the Pi the matched onboard
campaigns give 1.01x (the device times use 1.01 on the Pi, 1.42 elsewhere). The k4 prefix plus encoder is 31 % of the
YOLO11s MACs (YOLOv8s: 21 %).

1. **Held.** Post-hoc INT8 + zstd at k4 is 425 KiB per frame, 4.0x a Q95 JPEG (k2: 924 KiB). Neither is more accurate
   than the full model at fewer bits, so neither has a B_be.
2. **Held in substance; the stated size range was wrong.** The codes are 3.3-25.9 KiB (c4-c32) with 0.139-0.204 mAP.
   The YOLOv8s codes at the same channel counts are 3.5-26.2 KiB (0.142-0.227), so the size is indeed set by the
   channel count and the grid, not by the detector. My "3-15 KiB" was a misreading of the YOLOv8s range (c32 is 26 KiB
   there too). The encoder costs more: 31 % of the MACs against 21 %.
3. **Held.** 220 winning cells, all below their B_be, 0 exceptions.
4. **Held, with one difference.** On the Pi, B_be is 0.78 (c4) to 1.77 Mbit/s (c32); the YOLOv8s value is 0.81, within
   a factor 2. On the Jetson, B_be is 4.06-9.12 Mbit/s and no code wins above 7.17 Mbit/s (below 10, as predicted).
   The difference: on the Pi, no YOLO11s code wins at any goodput (the YOLOv8s codes win up to 0.60 Mbit/s). The
   onboard layers take 250 ms there, which leaves 12 ms of the 300 ms deadline after the 20 ms one-way delay and the
   ~18 ms server time, so a code is on time only above ~2.3 Mbit/s, where JPEG is better. The heavier prefix of
   YOLO11s at the stride-8 cut removes the Pi's window. B_be still bounds every win (it is an upper bound, not a
   prediction that a win exists).

Note on reproducibility: analyse first re-timed the codes' quantise + zstd and decoder steps on every run, which moved
the win count by 3 cells between runs (223 vs 220). The timings are now measured once and kept in code_timings.json;
two re-runs give identical sd_metrics.tex (220 wins).
