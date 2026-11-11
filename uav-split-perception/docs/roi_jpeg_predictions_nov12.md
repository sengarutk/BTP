# Region-of-interest JPEG with server feedback (paper 1, roadmap P1-9): predictions before the runs (12 Nov 2026, 04:01 IST, committed ef879ea9)

Method: evaluation/roi_jpeg.py (see its docstring). On the VisDrone-VID validation frames, in a closed loop:
- The server's YOLOv8s detections of frame t-2 (conf 0.25), grown by 16 px and snapped to the 16-px MCU grid, form
  the region mask.
- Two JPEGs are sent: the whole frame at q_b in {10, 20, 30}, and the region at q_r in {50, 70, 90}, with mid-grey
  outside it.
- The server rebuilds the mask from its own boxes, so no side information is sent.
- Scoring is on the 2,558 scored frames, as for P1-1.

The ROI options join the image family in the P1-1 analysis: JPEG + ROI, and JPEG + ROI + video. Timings are measured
single-thread on this laptop and scaled like every host time.

Predictions:
1. The region covers 20-50 % of the frame on average. VisDrone-VID frames are crowded (cars, people), and the 16-px
   margin plus the MCU snapping make small boxes large.
2. At equal accuracy, ROI JPEG needs 10-40 % fewer bytes than plain JPEG at the mid-to-high qualities (Q50-Q90). It
   gains little at low accuracy, where the background quality already sets the accuracy.
   - With a 2-frame lag, objects that enter the frame, or move more than the margin, fall in the background layer.
     This caps the accuracy below that of plain JPEG at q_r.
   - ROI saves less than video does (46-91 %).
3. Encode time is about 1.5-2 times that of one JPEG (two encodes). On the Pi this is still far below the codes'
   onboard time, so the ROI options are available on every device.
4. B_be of the joint c4 code against JPEG + ROI falls on both boards, but by less than with video. With all three
   families together, B_be is at most the video value (adding options can only lower it). There are 0 exceptions, and
   the winning cells with JPEG + ROI fall below the JPEG-only 1,118.

## Results (12 Nov 2026, 04:30 IST; experiments/results/roi_jpeg/, video_codecs.py analyse)

Nine settings: 21.9-47.5 KB per frame, 0.178-0.229 mAP@[.5:.95] (plain JPEG: 10.1-98.0 KB, 0.104-0.244).

1. **Held.** The region covers 29-31 % of the frame (mean 30 %).
2. **Failed.** At equal accuracy, ROI JPEG needs about as many bytes as plain JPEG: the median saving is 0 %, ranging
   from -13 % to +12 %, across the JPEG accuracies that the ROI grid reaches (Q35-Q80). There is no clear gain at
   Q50-Q90; the best is 12 % at Q55. Above Q80 accuracy, no ROI setting reaches plain JPEG at all (best 0.229, against
   0.235 at Q85).
   - Why: with 30 % of the frame in the region, the background layer at q_b 10 already costs 10.1 KB, about half of
     the total.
   - The objects the 2-frame-old feedback misses are small, and they fall in the q_b layer.
   - ROI saves far less than video does (46-91 %).
   - Method note: the first computed median (-8 %) also counted the JPEG accuracies below the ROI grid's lowest point
     (Q10-Q30), where the envelope charges ROI for bytes it need not send. The macro now uses only the range the grid
     covers; both numbers are recorded here.
3. **Failed in size, not in effect.** The camera side takes 2.9-3.1 ms per frame, 6.2 times one JPEG encode (0.49 ms),
   not 1.5-2 times. Two encodes would be about 1 ms; the rest is the Python/NumPy mask and compositing, unoptimised.
   It is still far below the codes' onboard time, so the ROI options remain available on every device.
4. **Held.**
   - **JPEG + ROI:** the joint c4 code's B_be falls from 9.84 to 8.99 Mbit/s on the Jetson, where the matched setting
     becomes ROI q_b 10 / q_r 90. It stays at 1.88 on the Pi, where the matched setting is still plain Q75. Both
     changes are much smaller than with video (1.51 and 1.06).
   - **Winning cells:** 1,118 fall to 1,106 with JPEG + ROI.
   - **All three families:** exactly the video + JPEG values (B_be 1.51 / 1.06, 204 winning cells; free encoding 64),
     so ROI adds nothing once video is available.
   - **Exceptions:** 0 everywhere.

Conclusion: on these frames a feedback-driven ROI JPEG is not a stronger image family than JPEG. The image-side
argument of the paper rests on video (P1-1), not on ROI coding. A learned per-macroblock quality model (AccMPEG) was
not tried.
