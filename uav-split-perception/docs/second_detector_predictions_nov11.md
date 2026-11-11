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
