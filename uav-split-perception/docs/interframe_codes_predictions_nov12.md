# Inter-frame coding of the split codes (paper 1, roadmap P1-10): predictions before the runs (12 Nov 2026, ~04:25 IST)

Why. With low-delay video as the image family (P1-1), the image side uses the previous frame and the split codes did
not. The fair comparison is video against video: the codes are also coded against the previous frame.

Method (evaluation/interframe_codes.py). On the 2,558 scored frames of the 7 VisDrone-VID validation sequences
(the frames of P1-1), for the frozen learned codes (k4, width 128, 2 decoder layers, 4-64 channels) and the jointly
trained codes. The uint8 code of every frame is recorded in the validator's own run, keyed by file, and reordered
into sequence order. Each frame is coded losslessly, as the smallest of three, plus a 1-byte mode flag:
- intra: zstd level 1 (the P1-1 coding);
- residual: zstd of the byte-wise difference from the previous frame's code (mod 256);
- reference: zstd with the previous frame's code as its dictionary.
Every 60th coded frame is intra, matching the video encoders' keyint 60. The one unscored frame in ten is not coded,
so every tenth reference is two frames back; this is conservative for the split. Each mode is decoded and checked
bit-exact. Lossless coding leaves the accuracy exactly that of the intra code. The added CPU time per frame
(measured, median) is added to the code's onboard processing time. The stream is assumed error-free, like the video
options.

Analysis: video_codecs.py analyse --inter, the P1-1 analysis with the codes' payloads replaced by the inter-coded ones.
Outputs go to analysis_inter.json and video_inter_metrics.tex (prefix Vi).

Predictions:
1. Extraction check: the recorded intra sizes reproduce the P1-1 payload means exactly, and the run's mAP equals the
   P1-1 row's.
2. Inter coding saves 5-30 % of the code bytes. The savings are limited for two reasons: the per-frame min-max
   quantiser shifts the code values between frames, and the drone camera moves, while each code cell covers 16 pixels.
   The saving is smaller than video's saving over JPEG (46-91 %).
3. B_be does not change. It depends on the image family, the code's accuracy and its onboard time, not on the code's
   bytes; the added coding time is well under 1 ms. The winning cells grow only below B_be: from 204 to at most 260
   with video and JPEG together. There are 0 exceptions.
4. Conclusion: video against video does not reverse P1-1. The joint code's B_be on the Jetson stays near 1.5 Mbit/s.
