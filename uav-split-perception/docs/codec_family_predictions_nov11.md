# Stronger image families for the break-even rule: predictions (paper 1, P1-1 video and P1-3 learned image codecs)

Written 11 Nov 2026, ~22:00 IST. Status when written: the video job (evaluation/video_codecs.py) had produced its JPEG
rows and 17 of its 30 video rows, none analysed; two JPEG rows were seen in a log tail (Q15: 12.95 KB at 0.133 mAP,
Q25: 17.8 KB at 0.160). No break-even number with either family had been computed. The learned image codecs
(evaluation/learned_image_codecs.py) had not run.

Video (VisDrone-VID val, 2558 scored frames; x264/x265 low delay, NVENC; JPEG at 18 qualities and the codes on the
same frames):
V1. At equal accuracy, low-delay x264/x265 need 40-80 % fewer bytes per frame than per-frame JPEG (median over the
    JPEG qualities each reaches); x265 medium saves the most, x264 ultrafast the least.
V2. With video in the image family, B_be of the codes falls: the matching video setting is smaller than the matching
    JPEG. On the Jetson by at least 30 % for the smallest jointly trained code. On the Pi, with host times scaled as
    the rule scales every host time, x264 ultrafast is admitted (its encode fits within the code's frame time) and
    x265 medium is not.
V3. No winning cell lies at or above B_be with any family (a consistency check: Proposition prop:be-family is a
    theorem of the model).
V4. With encoding free onboard (a dedicated encoder; the most favourable case for the image side), B_be falls further,
    and the codes' winning cells shrink to the lowest goodputs or vanish on the Jetson.

Learned image codecs (CompressAI bmshj2018-hyperprior, mbt2018-mean, cheng2020-anchor; VisDrone-DET val, the JPEG
rows' frames and method):
L1. At equal accuracy they need 30-60 % fewer bytes than JPEG (median over the JPEG qualities they reach).
L2. Their analysis transforms cost 20-150 % of the YOLOv8s's MACs at 640 x 640. On the Pi their onboard time then
    exceeds the codes' frame time for most qualities, so they are excluded there and B_be on the Pi barely moves; on
    the Jetson they lower B_be, as video does.
L3. No winning cell at or above B_be (consistency check).

Deviation (12 Nov 2026, ~02:00 IST, before any analysis): cheng2020-anchor was run at quality 1 only. Its serial
context model takes 3.0 s to encode and 4.6 s to decode one frame on this laptop's GPU (median over the 548 frames),
10-15 times the 300 ms deadline, so no quality of it can be an image option on any device; qualities 2-6 would have
taken about 6 h. bmshj2018-hyperprior and mbt2018-mean ran at all 8 qualities.

Results, learned image codecs (12 Nov 2026, ~02:05 IST; 17 settings: bmshj2018-hyperprior and mbt2018-mean at
qualities 1-8, cheng2020-anchor at quality 1):
L1. Right. At equal accuracy they need a median 52 % fewer bytes than JPEG (predicted 30-60 %).
L2. Direction right, size wrong. Their analysis transforms cost 108-458 % of the YOLOv8s's MACs at 640 x 640 (predicted
    20-150 %): more than the whole detector. On the Pi and the Jetson no learned-codec setting fits within the codes'
    frame time, so with them alone the smallest jointly trained code has no qualifying image option; with JPEG and them
    together its B_be is unchanged (1.17 Mbit/s on the Pi, 5.83 on the Jetson, matched by JPEG Q35). They qualify only
    on the fastest boards of the sweep, where they take 170 of the codes' 1030 winning cells (860 left).
L3. Right. No winning cell at or above B_be with any family (0 exceptions in all three cases).
