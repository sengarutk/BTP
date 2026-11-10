Your audit is approved. Go ahead with the revision, following the instructions below exactly. I checked your most
important findings against the data on my side and they are correct:
- the 44 simulator-vs-hardware runs are fixed single-path offloading (`fixed:laptop:m640q90` in 384 of the 528
  phases, `fixed:jetson:s640q90` in 144), not an adaptive controller;
- the Pi's 758 ms is outside the 40–360 ms sweep;
- §IV-C contradicts §VIII;
- on VisDrone frames the post-hoc k4 split is about 264 kB against about 78 kB for Q90 JPEG (about 3.4×);
- 2 of the 8 k4 learned codes use more bytes than JPEG.

Fix all 25 issues. Keep every rule from the first prompt.

---

## Part 1: My decisions on your questions

1. **Authors:** not final. Use the placeholder `\author{Author names withheld (to be supplied)}`, remove the
   `\thanks{...}` footnote, and make both running heads the short title only. Write no name, affiliation, email or
   acknowledgement anywhere.
2. **Target:** arXiv first, in the current IEEEtran journal format. No conference version for now.
3. **Licence:** [CC BY 4.0 — the user may change this before upload]. Put it only in the arXiv metadata you prepare,
   not in the paper.
4. **Repository URL:** [include it — the user may change this]. Add one sentence to the Reproducibility paragraph:
   "Code, data-preparation scripts and result files: <URL>". Use `\url{}` and leave the URL as a clearly marked
   placeholder `REPO-URL` for me to fill in.
5. **mAP units:** yes, report mAP in points (×100) everywhere, including §VIII, §IX and Fig. 12. Do it in the
   generators (`make_hardware.py`, `make_learned.py`, the figure code), never by hand.
6. **Jointly trained bottleneck:** no, not now. Keep it as stated future work.
7. **Units:** use **Mbit/s** everywhere (text, tables, figure axes). For payloads use **KiB** everywhere
   (1 KiB = 1024 bytes), as the core tables already do. Convert the kB values of §VIII and §IX in their generators.
8. **Git:** create a branch `paper1-arxiv` from `main` and commit after each phase below, with a clear message. Do not
   touch `main`. Push the branch only at the very end, after I say yes.

---

## Part 2: Order of work

Work in these phases, in order. At the end of every phase:
- rebuild (`bash paper/build_paper.sh`);
- run `python scripts/verify_math_proofs.py`;
- render the changed pages and look at them;
- commit to `paper1-arxiv`;
- send me a short status: what changed, the build result, the proof-check result, the page count.

### Phase 1: Generators (scripts that write macros and figures)

Change only the scripts. Never edit a `generated_tables/*.tex` file or a result file by hand. Then regenerate, and
update `docs/claims_to_evidence.md` for every new or changed macro (macro, value, source file, how it is computed).

1. **`evaluation/make_hardware.py`:**
   - **Proposition comment:** fix it so it names the offload-dominance proposition by its label (`prop:dominance`),
     not a number. Then the proof checker should pass 40/40.
   - **Simulator-check run counts:** add a macro for the number of runs of each strategy, read from
     `sim_vs_real_stopwait_persist.json` (`HwSimRunsLaptop`, `HwSimRunsJetson`), and macros for the two strategies'
     phase counts if you use them.
   - **Measured VisDrone ratio:** add `HwVdSplitOverJpeg` = (post-hoc k4 INT8+zstd payload) ÷ (Q90 JPEG payload), both
     measured on the same VisDrone DET val frames. Read `experiments/results/learned_bottleneck/posthoc_k4_int8_zstd.json`
     and `jpeg_q90.json`, field `payload_bytes_mean`. Expect about 3.4.
   - **Units:** produce the mAP values in points and the payloads in KiB.
2. **`evaluation/make_learned.py`:**
   - **Win/loss counts:** add the number of k4 codes that save bytes, the total k4 codes, and the same for k2. Expect
     6 of 8 at k4 and 2 of 2 at k2. Add the losing codes' saving (negative) and payload, so the text can name them.
   - **Units:** mAP in points, payloads in KiB.
3. **Typed numbers (rule 1).** Make a macro, in the generator that owns that section, for each of:
   - "≈0.2–0.3 points" (both places);
   - "about 0.2 points" (introduction);
   - "50 COCO frames";
   - "548 VisDrone images";
   - "1.2 M / 1.4 M elements".

   Each must come from the result file it describes. If one is a design constant rather than a measurement, say which
   and leave it typed.
4. **Positive-sign loss macros** for the two double negatives:
   - the Q95 JPEG loss in the abstract: "loses only 0.21 points";
   - §VIII's Q90 JPEG loss: "loses 1.08 points".

   Keep the signed macros for tables.
5. **Relaying:**
   - Make the maximum relay gain macro print enough decimals to show its true value (about 0.04, not 0.0).
   - Check it against Table I's 0.05; if the two come from different runs, say which is which in the text.
6. **Figures:**
   - **`evaluation/make_figures.py`, Fig. 3:** fix the table reference inside the figure. Better, remove table numbers
     from inside figures entirely: write "see the codec table" in the caption with `\ref` instead.
   - **Axis labels:** "Mbit/s" on every axis.
   - **Fig. 11:** move the legend off the data (outside the axes, or to an empty corner).
   - **Fig. 12** (`evaluation/learned_bottleneck.py`, `cmd_figure`): fix the label collisions. Offset the labels per
     family, or use a small table of labels instead of on-plot text. Switch to mAP in points and KiB.
   - Regenerate all figures and look at each one at column width.

### Phase 2: Factual corrections in `main.tex` (section A of your audit)

- **A1, §VIII simulator check:** describe the runs exactly. "We rebuilt `\HwSimRuns` real runs of fixed single-path
  offloading (JPEG Q90 to the laptop with YOLOv8m in `\HwSimRunsLaptop` runs, or to the Jetson with YOLOv8s in
  `\HwSimRunsJetson`), under scripted link impairments (`\HwSimPhases` phases)…". Keep the condition that the
  camera's one-frame-in-flight (stop-and-wait) rule and the impairments actually applied are modelled.
- **A2, the Pi's speed:** "slower than the slowest onboard setting of the system sweep, but inside the Monte Carlo
  range". Use the existing macros for the sweep and the Monte Carlo range if they exist; if not, add them.
- **A3, §IV-C:** rewrite so it no longer says there are no measurements. Something like: "In the system study the
  onboard speed is a parameter; Section VIII measures one onboard computer."
- **A4, the aerial dominance argument:**
  - Use the measured `\HwVdSplitOverJpeg` (same frames, VisDrone-trained detector), not the COCO-survey minimum.
  - State all three conditions of the dominance proposition and show each holds: fewer bits, less onboard time, and
    less onboard-plus-server time. Use numbers already in the paper's macros (timing table, hardware timings).
  - If any condition cannot be shown from existing macros, add the macro from its result file.
- **A5, learned-bottleneck savings:** "`\LbKFourWinN` of the `\LbKFourN` k4 codes and both k2 codes need X–Y % fewer
  bytes than JPEG for the same mAP; the other two k4 codes need more." In `summary.json` (width 128, two decoder
  layers) the two losing codes are k4 with 64 channels at stride 2 (about 53.8 kB, −16 %) and k4 with 32 channels at
  stride 1 (about 104.9 kB, −43 %). Name them in the text, with their payloads as macros.
- **A6, limitation (iii):** correct it. Smaller models have *smaller* split-to-JPEG ratios (for example YOLO11n about
  2.0× against about 3.5× for YOLOv8s at 640 px; the existing macros are `\GenRatioMin` with `\GenRatioMinModel`), so the payload
  argument is weakest for small models; onboard work still favours the image in every row. Use macros for any number
  you quote.
- **A7, reproducibility:** say exactly what `make reproduce` regenerates. In the Makefile it runs
  `clean-cache data test results generalization paper` and does **not** run `validate` or `validate-omnetpp`; the
  Makefile's header comment ("all of the above") is wrong, so fix that comment too. Then list what needs separate
  steps, with the script names:
  - the hardware runs;
  - the VisDrone fine-tuning;
  - the learned bottleneck (`evaluation/learned_bottleneck.py`);
  - the ns-3/OMNeT++ validation (`make validate`, `make validate-omnetpp`).
- **A8, Fig. 3:** done in Phase 1; check the result.
- **A9, the indicator symbol:** replace `\mathbb{1}` with `\mathbf{1}` everywhere (§IV-G, §VII-A, the proposition).

### Phase 3: Claims beyond their evidence (section B of your audit)

- **B1:** "Relayed frames of the adaptive policy (any codec) are usually on time (`\RelayAdaptiveAllOnTime` of
  `\RelayAdaptiveAllTotal`, i.e. 463 of 540)". Do not call them JPEG frames.
- **B2:** use the corrected relay-gain macro from Phase 1.
- **B3:** "would avoid" → "could reduce" (or remove the sentence).
- **B4:** "JPEG is not disproportionately harmful" → restrict it to Q95 with the zero-shot detectors, and add that
  with the VisDrone-trained detector Q90 loses `\HwVdJpegNinetyPct` % (§VIII).
- **B5:** say that the `\HwNPlacements` placements are *model estimates from measured component timings*, and that
  only the important placements were run live. Add the model's accuracy, as recorded in `docs/hardware_results.md`
  §5: for two-device chains it predicts the live frame rate within about 30 % and ranks the placements in the same
  order; for three-device chains it is too optimistic, because both Wi-Fi hops share one channel. Take the 30 % from
  its result file as a macro; if no file holds it, write "roughly" and cite the section.
- **B6:** state the VisDrone class mapping exactly as the code applies it (`scripts/prepare_datasets.py`,
  `VISDRONE_TO_COCO`):
  - pedestrian and people → person; car and van → car; bicycle → bicycle; motor → motorcycle; truck → truck;
    bus → bus;
  - dropped: ignored regions, "others", tricycle and awning-tricycle (no COCO counterpart).

  The current text omits "others".

### Phase 4: Layout, consistency, author block

1. **Tables VII and VIII:** make them readable. Use `table*` (full page width) without `\resizebox`, or split each
   into two smaller tables. No table font below 7 pt.
2. **Units:** Mbit/s and KiB everywhere, as decided above.
3. **Terminology:**
   - "Fig." for every figure reference, through one command;
   - "YOLOv5u" vs "YOLOv5n": use the exact model names in the table, and explain "u" once if needed;
   - "image offload" for the strategy and "JPEG" for the codec, used consistently.
4. **mAP** in points everywhere, as decided.
5. **Author block and running heads:** as decided in Part 1.
6. **Underfull boxes:** fix the 11 where easy (rewording); don't distort the text to remove them.

### Phase 5: Abstract and introduction

1. **Abstract:** 220–250 words, keeping every headline result:
   - lossless INT8;
   - the payload gap;
   - image offload wins every setting;
   - the closed-form bound;
   - generalization (19 detectors);
   - the hardware check;
   - the learned bottleneck with its exact limits (it beats JPEG on bits for most codes, but on the measured Pi it
     wins end to end only at the lowest goodputs).

   Numbers via macros only.
2. **Introduction:** six contribution bullets, with the hardware check and the learned bottleneck merged into one.
   Keep the central negative result stated precisely: post-hoc quantized splits of unmodified detectors.
3. **Read the whole paper once more,** start to finish, for flow and consistency after all the edits.

### Phase 6: References

1. **Krishnamoorthi:** make the arXiv ID print (arXiv:1806.08342; verify it on arxiv.org).
2. **SC2 (TMLR):** add its OpenReview URL, after verifying it.
3. **Related work:** add FrankenSplit (Furutanpey et al., 2024) and Matsubara et al. (2021), "Neural Compression and
   Filtering for Edge-assisted Real-time Object Detection". Copy their verified entries from
   `paper/references_verified.bib` (keys `Furutanpey_2024`, `Matsubara_2021`), rename the keys to the paper's style,
   and cite both in the feature-compression paragraph: one sentence on what each does.
4. **Re-verify** every reference you add or change, by DOI or arXiv. Keep all fields ASCII.

### Phase 7: Final checks and packaging

1. **Checks:**
   - `bash paper/build_paper.sh`: no undefined anything, 0 overfull boxes;
   - `verify_math_proofs.py`: 40/40;
   - `pytest -q tests`: report the exact count and update the README's test count to it;
   - render all pages and look at every one.
2. **`uav-split-perception/README.md`:** fix the test count, and add one line each for the hardware check and the
   learned bottleneck.
3. **arXiv folder** `paper/arxiv/` (git-ignored, or a zip next to it):
   - contents: `main.tex`, `main.bbl`, `generated_tables/`, `figures/`, nothing else needed;
   - compile it from a fresh copy with `pdflatex` only, twice, and confirm the PDF matches;
   - remove comments that hold private notes;
   - no absolute paths.
4. **arXiv metadata** in `paper/arxiv/metadata.md`:
   - the title;
   - a plain-text abstract with the numbers written out (no LaTeX);
   - primary category cs.NI, cross-lists cs.CV, cs.LG, cs.RO;
   - the comments field: "N pages, 12 figures, 10 tables; code and data: REPO-URL";
   - the licence: CC BY 4.0, placeholder for me to confirm.
5. **Change log** in `paper/CHANGELOG_paper1.md`: every change, grouped by phase, with the reason and the
   macro/source behind each corrected number.
6. **Report to me:** the final page count, the build and check results, and any issue you could not resolve, with
   the reason. Then wait for my go-ahead to push the `paper1-arxiv` branch.

---

## Part 3: Rules that still apply

- Never edit a result file under `experiments/results/`. Never type a measured number. Never add an unverified
  citation.
- If a fix needs a result file that is not in your sparse checkout, add only that folder with
  `git sparse-checkout add <path>` and tell me which.
- If any fix turns out to change a conclusion, rather than its wording, stop and tell me before writing it.
- Keep Paper 1's scope: none of paper 2's controller or mesh material.
