# Laptop work from the roadmap (docs/novelty_roadmap_nov11.md), started 11 Nov 2026

Status: [x] done and pushed, [~] running or in progress, [ ] to do. Board items are listed in the roadmap.

## Paper 2
- [x] P2-4  scope the heat-removal claim (abstract, thesis, section title, conclusion)
- [x] P2-8  why a few watts matter (MAVBench), P2-11 AoI and heat-at-the-edge related work (Crossref-verified)
- [x] P2-6  self-calibrating budget (online intercept estimate) + price-cap sweep at +10 C, replay (addendum 4;
            follow-up with both, addendum 5, running)
- [~] P2-1  theorem (Theorem 3 written, hardware constants done; replay check running): peak temperature and time above the throttle temperature under guard + capped hold; checked on
            every logged run and in the replay
- [ ] P2-7  constrained DRL baseline (PPO-Lagrangian) in the replay

## Paper 1
- [x] P1-2  corollary: B_be is independent of the code's payload, so no coder (even at the rate-distortion limit) raises it
- [x] P1-11 bootstrap intervals on B_be
- [x] P1-12 a channel-adaptive split obeys the bound slot by slot (Corollary cor:switch)
- [~] P1-1  video codecs (x264/x265 low delay) as the image family on VisDrone-VID val; same frames for JPEG and codes
- [~] P1-4  second detector (YOLO11s, VisDrone): JPEG grid, post-hoc, learned and entropy codes, break-even rule
- [ ] P1-3  learned image codecs as the image family (rate, accuracy, encode time)
- [x] P1-6  energy version of the break-even rule (measured Pi energy constants)
- [ ] P1-10 inter-frame coding of the split code (the fair video counterpart)
- [ ] P1-9  region-of-interest image encoding as the image family
- [ ] P1-8  MPEG FCM baseline (feasibility first)

## Afterwards
- [ ] rewrite both papers around the results; fresh-context audit
