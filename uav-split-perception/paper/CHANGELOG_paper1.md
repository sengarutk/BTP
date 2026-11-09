# Paper 1 change log: audit fixes and arXiv preparation (branch `paper1-arxiv`, Nov 2026)

Every number in the paper is a macro written by a generator in `evaluation/`; each macro, its value, its source
file and how it is computed is in `docs/claims_to_evidence.md` (hardware and learned-bottleneck sections) and the
`docs/claims_*.md` ledgers. No result file under `experiments/results/` was changed.

Final state: 15 pages, 0 undefined references or citations, 0 overfull boxes, 0 LaTeX warnings, 9 underfull boxes
(see "Open items"); `scripts/verify_math_proofs.py` 40/40; 40 references, all cited, ASCII-only.

## Phase 1: generators (commit e02d700)

| Change | Reason | Macro (value) / source |
| --- | --- | --- |
| `evaluation/ledger.py`: each generator owns a section of `docs/claims_to_evidence.md` | `make_tables.py` overwrote the whole ledger and deleted the hand-added hardware and learned sections | `docs/claims_to_evidence.md` now has a "How computed" column |
| Positive JPEG-loss macros | Double negatives ("loses only -0.21 points") | `\JPEGLossQNinetyFive` (0.21), `\JPEGLossQNinety` (0.33), also Q50/Q75; `codec_baselines.csv` |
| Live-set sizes as macros | Typed "1.2 M / 1.4 M" | `\LiveElemsKFiveM` (1.2), `\LiveElemsKSevenM` (1.4, asserted equal for k7-k18); `yolov8s_graph_topology.json` |
| Relay gain with two decimals | Printed as "0.0" | `\RelayMaxGain` (0.05, equal to Table I's paper-model value); `system_swarm.csv` |
| Sweep and Monte Carlo onboard-speed bounds | Needed by the Sec. VIII correction | `\SweepTfullMinMs`/`MaxMs` (40/360; `system_model.py`), `\GenTfullMinMs`/`MaxMs` (10/1000; checked against `scenarios.csv`) |
| VisDrone image count | Typed "548" | `\GenAerialValImages` (548); `generalization/accuracy.csv` |
| Hardware macros in points and KiB; simulator-check runs per strategy | Units; Sec. VIII described the runs wrongly | `\HwSimRunsLaptop` (32), `\HwSimRunsJetson` (12), phases 384/144; `sim_vs_real_stopwait_persist.json` |
| Measured VisDrone payload ratio and the three dominance conditions | The aerial argument used the COCO-survey minimum (2.0) and only two of three conditions | `\HwVdSplitOverJpeg` (3.4 = 263,641 / 77,770 B), `\HwVdSplitKiB` (257.5), `\HwVdJpegNinetyKiB` (75.9); `\HwPiJpegEncMs` (4.0), `\HwPiSplitOnboardMinMs` (76, cut k0), `\HwPiImgTotalMs` (13.8), `\HwPiSplitTotalMinMs` (92); `learned_bottleneck/*.json`, `hardware/raw/pi5_cpu_4t_sustained.json`, `laptop_gpu_fp16.json` |
| Placement model against live runs | Needed by B5 | `\HwModelRatioMin`/`Max` (0.8/2.0, 9 one-/two-device placements), `\HwModelRatioThreeMax` (4.2, 3 chains), `\HwModelImageAboveSplit` (every); `hardware/placements.csv`, `live_summary.csv` |
| Positive VisDrone JPEG losses | Double negative in Sec. VIII | `\HwVdJpegNinetyLoss` (1.08 points), `\HwVdJpegFiftyLoss` (6.40) |
| Learned-bottleneck macros in points and KiB; winners and losers | A5; units | `\LbKFourWinN` (6 of 8), `\LbKTwoWinN` (2 of 2), `\LbKFourLoseOne*` (64 ch, half res., 52.5 KiB, +16 %), `\LbKFourLoseTwo*` (32 ch, full res., 102.4 KiB, +43 %); `learned_bottleneck/summary.json` |
| Proposition comment in `make_hardware.py` names `prop:dominance` | The proof checker failed (comment said "Proposition 1") | -- |
| Figures: Mbit/s on every axis; no table number inside Fig. 3 (caption points to the codec table); Fig. 11 legend above the data; Fig. 12 in points and KiB with non-overlapping labels | Layout audit | `make_figures.py`, `make_generalization.py`, `learned_bottleneck.py figure` |

## Phase 2: factual corrections (commit 4d5b330)

| ID | Change | Evidence |
| --- | --- | --- |
| A1 | Sec. VIII: the simulator check rebuilt 44 live runs of fixed single-path image offload (JPEG Q90 to the laptop with YOLOv8m, 32 runs; to the Jetson with YOLOv8s, 12 runs), not an adaptive controller | `sim_vs_real_stopwait_persist.json` policies |
| A2 | The Pi (758 ms) is slower than the sweep's slowest setting (360 ms) but inside the Monte Carlo range (10-1000 ms); it was called "the slow end of the sweep" | `\HwPiFullMs`, `\SweepTfullMaxMs`, `\GenTfullMin/MaxMs` |
| A3 | Sec. IV-C no longer says there are no onboard measurements | -- |
| A4 | Aerial dominance stated with all three conditions and measured values on the same frames and devices | Phase 1 macros |
| A5 | Learned bottleneck: 6 of 8 k4 codes and 2 of 2 k2 codes save bytes; the two losing k4 codes named | `summary.json` |
| A6 | Limitation (iii): the payload argument is weakest for small models (YOLO11n 2.0x vs YOLOv8s 3.5x); onboard work favours the image in all 43 survey rows | `\GenRatioMin`, `\GenResRatioSixForty`, new `\GenOnboardFavoursImageRows` (43; `model_summary.csv`) |
| A7 | Reproducibility paragraph and Makefile header say exactly what `make reproduce` runs and what needs separate steps; repository-URL placeholder `REPO-URL` | `Makefile` |
| A8 | Fig. 3 table reference (phase 1) | -- |
| A9 | Indicator written `\mathbf{1}` (amssymb's `\mathbb{1}` rendered a wrong glyph); the checker's guard pattern follows | `scripts/verify_math_proofs.py` |

## Phase 3: claims inside their evidence (commit b4d718f)

| ID | Change |
| --- | --- |
| B1 | Relayed frames of the adaptive policy may use any codec (463 of 540); no longer "relayed JPEG frames" |
| B2 | "raised it by at most 0.05 frames/s" (was "never by more than 0.0") |
| B3 | "a coordinated scheduler would avoid this" -> "could reduce this" |
| B4 | The aerial JPEG statement is limited to Q95 with the zero-shot detectors; the VisDrone-trained detector's 4.0 % loss at Q90 is cited |
| B5 | The 1,150 placements are model estimates from measured component timings; only important placements ran live; model 0.8-2.0x the live frame rate (one/two devices), same image-above-split ordering, up to 4.2x too optimistic for three-device chains. `docs/hardware_results.md` says "within about 30 %", which the result files do not support |
| B6 | VisDrone class mapping stated exactly as `scripts/prepare_datasets.py` applies it (others, tricycle, awning-tricycle and ignored regions dropped) |
| -- | Typed numbers replaced: 0.2-0.3 points (twice), "about 0.2 points", 1.2 M / 1.4 M, 548 (twice). "50 survey frames" stays typed: a design constant (`gen_model_survey.py --n-images` default), not recorded in any result file |

## Phase 4: layout, units, terminology, author block (commit 44ccb87)

- No `\resizebox`; no table font below 7 pt. Tables VII and VIII full width (8 pt); Tables I, III, IX at 7 pt with two-line headers from the generators; Tables IV, V at 8 pt; Table X at 7 pt.
- Mbit/s in all prose and figure axes (four "Mbps" in the text); KiB for every payload.
- `\figref` for all 12 figure references (`validate_manuscript.py` accepts it); "image offload" for the strategy and "JPEG" for the codec, in text, Table VI and the figure legends; exact YOLOv5nu/su/mu names, the "u" explained once.
- Author block and running heads: placeholder "Author names withheld (to be supplied)" and the short title; no names, affiliations, emails or acknowledgements remain.
- Underfull boxes reduced (breakable `\path` in Reproducibility; reworded validation intro).

## Phase 5: abstract and introduction (commit 8b58c70)

- Abstract 337 -> 249 words (numbers expanded), every headline result kept, the learned bottleneck with its exact limits.
- Six contribution bullets (hardware check and learned bottleneck merged); the central finding stated for post-hoc quantized splits of unmodified detectors.
- "goodput" where the text meant goodput (two places); `\BoundRatioMax` printed as 1.0000, as in Table III.

## Phase 6: references (commit 50deb9b)

- `krishnamoorthi2018quantizing`: arXiv:1806.08342 now prints (checked on arxiv.org).
- `matsubara2023sc2`: OpenReview URL `https://openreview.net/forum?id=p28wv4G65d` (TMLR acceptance record, checked through the OpenReview API).
- New, re-checked against CrossRef and cited in the feature-compression paragraph: `matsubara2021neural` (ICPR 2021, 10.1109/ICPR48806.2021.9412388) and `furutanpey2024frankensplit` (IEEE TMC 23(12):10770-10786, 10.1109/TMC.2024.3381952).

## Phase 7: final checks and packaging

- Conclusion: the dominance sentence states all three conditions, the ratio is against a Q90 JPEG, the generality claim is limited to what was tested, and "for most of the codes we trained".
- `uav-split-perception/README.md`: test count, hardware check and learned bottleneck, what `make reproduce` covers.
- `paper/make_arxiv.py` builds `paper/arxiv/` and `paper/arxiv.zip` (git-ignored): main.tex without comments, main.bbl, the 15 generated tables and 11 figure PDFs it uses; refuses absolute paths; writes `arxiv/metadata.md`. A fresh copy compiles with pdflatex alone (twice) to a PDF identical page by page to the full build.
- Tests (`pytest -q tests`, Windows): 127 items, 117 passed, 7 skipped (CUDA, nvcc, C++ compiler; two modules that import `fcntl`), 3 failed for Linux-only reasons (`os.sched_getaffinity`, ZeroMQ `ipc://`). 126 tests are collected.

## Open items

- Authors, affiliations, acknowledgements and the repository URL (`REPO-URL`) are placeholders; the licence (CC BY 4.0) is in `arxiv/metadata.md` for confirmation.
- 9 underfull boxes remain: the keyword list, one introduction bullet, the Proposition 4 heading and page-break `\vbox` notices; removing them would distort the text.
- `docs/hardware_results.md` still says the placement model is "within about 30 %"; the paper now uses the values computed from the result files (0.8-2.0x).
