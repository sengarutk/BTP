# An FCM-style feature-coding baseline with HEVC (paper 1, roadmap L5): predictions before the runs (12 Nov 2026)

Why. MPEG's Feature Coding for Machines (FCM) codes the features at the split with a standard video codec, VVC in its
test model FCTM. A reviewer can ask how the split does with such a codec. FCM's reference software is hosted for MPEG
members. Building an open VVC encoder (VVenC) needs the user's permission for external code, not yet given. This uses
HEVC (x265 through ffmpeg, already installed), the generation before VVC, and is labelled as HEVC.

Method (evaluation/feature_hevc.py), on the 548 VisDrone-DET val frames with the VisDrone YOLOv8s, mAP@[.5:.95]:
- (a) Post-hoc cut k4 (no feature reduction, as FCM without its NN reduction). The 128-channel tensor is quantised
  per image with min-max to 10 bits and tiled 16 x 8 into one monochrome picture. It is coded with x265 intra
  (each frame independent; preset medium; QP 22, 27, 32, 37, 42, 47), decoded, untiled, dequantised, and the
  detector continues.
- (b) The same coding applied to the frozen learned codes (k4, 4-32 channels, 40 x 40): a learned reduction followed
  by a standard codec, FCTM's structure.
- Payload: the HEVC bitstream plus 8 bytes for min and max. Timing: x265's encode time on this CPU, single thread,
  scaled like every host time (an estimate for the Pi). B_be from break_even_rule.analyse, as for every code.

Predictions:
1. (a) At QP 22-27 the accuracy is within 0.01 of the full model. The payload is 30-150 KiB: below the 310 KiB of
   INT8 + zstd, but above a Q90 JPEG (76 KiB) at QP 22. At QP 37-47 it is under 20 KiB with accuracy at most 0.20.
2. (a) Its onboard time (the 21 % prefix plus encoding a 1280 x 640 picture) is at least that of the INT8 split. On the
   Pi it does not win above 1 Mbit/s, and on the Jetson not above 10 Mbit/s.
3. (b) HEVC makes the learned codes 20-60 % smaller than zstd at the same accuracy; B_be is unchanged (Corollary 1),
   and wins are added only below it.
4. 0 exceptions to the rule in every case.
