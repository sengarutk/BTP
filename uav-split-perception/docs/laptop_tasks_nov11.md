# Laptop work from the roadmap (docs/novelty_roadmap_nov11.md), started 11 Nov 2026

Status: [x] done and pushed, [~] running or in progress, [ ] to do. Board items are listed in the roadmap.

## Paper 2
- [x] P2-4  scope the heat-removal claim (abstract, thesis, section title, conclusion)
- [x] P2-8  why a few watts matter (MAVBench), P2-11 AoI and heat-at-the-edge related work (Crossref-verified)
- [x] P2-6  self-calibrating budget (online intercept estimate) + price-cap sweep at +10 C, replay (addendum 4;
            follow-up with both, addendum 5: hot 0 % at +5 and +10 C)
- [x] P2-1  theorem (Theorem 3; hardware constants; replay check 20/20): peak temperature and time above the throttle temperature under guard + capped hold; checked on
            every logged run and in the replay
- [x] P2-7  constrained DRL baseline (PPO-Lagrangian) in the replay (attempt 3; below v4.1 on all three scenarios)

## Paper 1
- [x] P1-2  corollary: B_be is independent of the code's payload, so no coder (even at the rate-distortion limit) raises it
- [x] P1-11 bootstrap intervals on B_be
- [x] P1-12 a channel-adaptive split obeys the bound slot by slot (Corollary cor:switch)
- [x] P1-1  video codecs (x264/x265 low delay) as the image family on VisDrone-VID val; same frames for JPEG and codes
- [x] P1-4  second detector YOLO11s (033c7239): codes 3.3-25.9 KiB; B_be 0.78-1.77 Mbit/s Pi (no win: 250 ms prefix vs 300 ms deadline), 4.06-9.12 Jetson; 220 wins, 0 exceptions. Entropy codes not trained for it
- [x] P1-3  learned image codecs as the image family (rate, accuracy, encode time)
- [x] P1-6  energy version of the break-even rule (measured Pi energy constants)
- [x] P1-10 inter-frame coding of the split codes (39ff4b85): lossless, 26-32 % fewer bytes; B_be unchanged; wins 204 -> 260; 0 exceptions
- [x] P1-9  ROI JPEG with server feedback (af554d3b): median 0 % saving at equal accuracy; Jetson B_be 9.84 -> 8.99; nothing added once video is available
- [x] P1-8  MPEG FCM: not run. The reference software (FCTM) is on git.mpeg.expert, believed to need an MPEG member login, and uses VTM. Handle by discussion + citation (arXiv 2512.10209, 2509.20777)

## Afterwards
- [ ] rewrite both papers around the results; fresh-context audit
