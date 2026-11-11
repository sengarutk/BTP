# Region-of-interest JPEG with server feedback (paper 1, roadmap P1-9): predictions before the runs (12 Nov 2026, ~04:45 IST)

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
