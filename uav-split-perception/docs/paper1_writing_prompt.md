# Task: finish Paper 1 of the AEGIS-UAV project, ready for arXiv and journal submission

You are taking over a research paper whose experiments and near-complete manuscript already exist in a Git
repository. You have no memory of that work. Everything you need is in the repository, and this prompt tells you
where. **Read before you write, and trust only the files**, not anything you may remember about this project.

## Mission

Turn `uav-split-perception/paper/main.tex` into a **submission-ready, arXiv-ready paper** that a strict reviewer
cannot fault on correctness. Every number must trace to a result file, every citation must be verified, every claim
must stay inside its evidence, and the writing must be clear, tight and consistent. Then prepare the arXiv package.

**Definition of done:**
1. The paper builds from a clean checkout, with zero undefined macros, citations or references, zero warnings and
   zero overfull boxes.
2. Every page has been rendered and inspected.
3. Every claim has been audited against its source.
4. The abstract and introduction have been tightened.
5. The known issues below are fixed.
6. A self-contained arXiv folder compiles with `pdflatex` alone.
7. You have handed the user a change log and a list of open decisions.

---

## 1. Rules that override everything else

1. **No typed measurements.**
   - Every measured number in the text is a LaTeX macro (for example `\MinSplitKiB`, `\HwJpegOnTime`).
   - The macros are defined in `paper/generated_tables/*metrics.tex`, which scripts write from result files.
   - `docs/claims_to_evidence.md` maps every macro to its value and source file.
   - A new number goes into the generator script that owns that section (section 4A). Then regenerate, and add it to
     `docs/claims_to_evidence.md`.
   - Only design constants (300 ms deadline, 30 frames/s, 640 px input) and structural facts (22 layer boundaries)
     may be written out.
2. **Never edit a result file** under `experiments/results/`. They are the evidence. If one looks wrong, stop and
   report the file and your reason.
3. **Never invent or guess a citation.**
   - Verify every new reference by DOI against CrossRef or DataCite, or against arxiv.org for preprints, before adding
     it.
   - If you cannot verify one, leave it out and say so.
   - The current 38 entries were verified on 30 Oct 2026.
4. **Keep each claim inside its evidence** (section 6). The paper's value is a precise, honest, bounded negative
   result. Never strengthen a claim beyond the data.
5. **Keep Paper 1's scope** (section 3). A second paper (`uav-split-perception/paper2/`) covers other results; use
   none of its material or numbers.
6. **Authors are not final.**
   - Do not write, keep or invent any author name, affiliation, email or acknowledgement.
   - Replace the current author block (`\author{...}`, its `\thanks{...}` and the `\markboth` running heads) with a
     clearly marked placeholder, for example `\author{Author names withheld (to be supplied)}`.
   - Ask the user for the final author list, order, affiliations and funding/acknowledgement text before the arXiv
     upload.
7. **Build after every change:** `cd uav-split-perception/paper && bash build_paper.sh`. It runs
   `validate_manuscript.py` (citations, figures, macros, labels, environments) and then pdflatex/bibtex, and fails on
   anything undefined. Check `grep -c Overfull main.log`.
8. **Look at the result, not just the source.** Render pages with
   `gs -q -dNOPAUSE -dBATCH -sDEVICE=png16m -r90 -sOutputFile=p%02d.png main.pdf` and inspect every figure, table and
   page break.
9. **No commit or push without the user's say-so.** When pushing:
   - never add `.claude/settings.local.json` or `*:Zone.Identifier` files;
   - keep each push under GitHub's 2 GiB pack limit.

---

## 2. Getting the repository

The repository is `git@github.com:sengarutk/BTP.git`, branch `main`; the paper project is the subfolder
`uav-split-perception/`. The full repository is about 7.3 GB, so take only what the paper needs:

```bash
git clone --filter=blob:none --sparse git@github.com:sengarutk/BTP.git
cd BTP
git sparse-checkout set \
  uav-split-perception/paper uav-split-perception/docs uav-split-perception/evaluation \
  uav-split-perception/simulation uav-split-perception/core uav-split-perception/protocol \
  uav-split-perception/quantization uav-split-perception/deployment uav-split-perception/configs \
  uav-split-perception/scripts uav-split-perception/tests uav-split-perception/utils \
  uav-split-perception/validation \
  uav-split-perception/experiments/results/generalization \
  uav-split-perception/experiments/results/validation \
  uav-split-perception/experiments/results/visdrone_ft_split \
  uav-split-perception/experiments/results/learned_bottleneck \
  uav-split-perception/experiments/results/hardware/raw
```

Cone-mode sparse checkout also brings the files directly inside every parent folder. That covers the top-level
result CSV/JSONs in `experiments/results/`, the hardware summaries in `experiments/results/hardware/`
(`placements_summary.json`, `live_summary.csv`, `sim_vs_real_stopwait_persist.json`) and the reports at the
repository root.

**Building needs only LaTeX:** `texlive-latex-extra`, `texlive-publishers` (IEEEtran), `texlive-science`,
`texlive-pictures` (TikZ) and `bibtex`. The generated macros, tables and figure PDFs are committed.

**Regenerating numbers or figures needs Python 3.12** with `uav-split-perception/requirements.txt`, and for some
steps the datasets, which are not in Git (`make data`).

---

## 3. The paper: question, answer, scope

**Title (current):** *"When Does Split Computing Pay Off for UAV Object Detection? A Measured and Trace-Driven
Study with YOLOv8"*. It's 14 pages in IEEEtran journal format, with 593 generated number macros, 38 references,
12 figures (11 PDFs and one TikZ diagram), 10 tables and 5 propositions.

**Question:** for an off-the-shelf YOLOv8s on a UAV, does *split computing* beat onboard inference or offloading a
compressed image? Split computing runs the first layers onboard and sends the intermediate activations to a server.

**Answer (a bounded negative result):**
- Post-hoc quantized splitting is essentially lossless in accuracy, and often beats onboard inference on a slow
  computer.
- But it is never bandwidth-competitive with a good JPEG: its payloads are 2.0–11.5× a JPEG frame.
- So image offload wins in every system-level setting, in simulation, in theory (a closed-form dominance bound),
  across 19 detectors, and on real hardware.
- A small *learned* bottleneck does beat JPEG on bits. On a slow drone computer it still loses end to end, except at
  the lowest goodputs, because it needs far more onboard work.

**In scope:**
- the toolkit;
- accuracy and rate;
- the system model, the simulator and its validation;
- the adaptive offloading policy, as part of the system study;
- swarms and relaying;
- energy and endurance;
- generalization;
- the hardware check;
- the learned bottleneck.

**Out of scope:** the adaptive streaming controller with energy, heat and freshness prices, the streaming-AP and mesh
campaigns, the thermal results and the published-planner comparison. These belong to the second paper. At most one
sentence may refer to "companion work".

---

## 4. Read everything below before writing (in this order)

### A. The manuscript and how its numbers are made (`uav-split-perception/paper/`)

| File | What it is | Generated by |
| --- | --- | --- |
| `main.tex` | the paper (read it end to end) | — |
| `generated_tables/autogen_metrics.tex` | accuracy, rate, timing, system, swarm, energy, policy numbers | `evaluation/make_tables.py` |
| `generated_tables/gen_metrics.tex` | detectors, bit widths, resolutions, aerial, Monte Carlo | `evaluation/make_generalization.py` |
| `generated_tables/val_metrics.tex` | ns-3, INET, Simu5G and emulation checks | `evaluation/make_validation.py` |
| `generated_tables/hw_metrics.tex`, `table_hardware.tex` | the Hardware Check | `evaluation/make_hardware.py` |
| `generated_tables/lb_metrics.tex` | the learned bottleneck | `evaluation/make_learned.py` |
| `generated_tables/table_*.tex` | the 10 tables | the scripts above |
| `figures/*.pdf` | 11 figures | `evaluation/make_figures.py`; `learned_bottleneck.pdf` by `evaluation/learned_bottleneck.py figure` |
| `references.bib` | 38 verified entries | — (`references_verified.bib` belongs to paper 2) |
| `validate_manuscript.py`, `build_paper.sh` | checks and build | `make tables`, `make figures`, `make paper`, `make reproduce` |

### B. The evidence trail (`uav-split-perception/docs/`)

- `claims_to_evidence.md`: every macro → value → source file.
- `claims_generalization.md`, `claims_validation.md`, `assumptions_and_validation.md`: what the generalization and
  validation claims rest on, and the model's assumptions.
- `hardware_results.md`: the testbed, the 1,150 placements and the live runs.
- `laptop_additions_2026-10-30_part5.md`: the learned bottleneck (design, checks, approximations).
- `novelty_and_related_work.md`: the positioning.
- `audit_2026-10-28.md`: the full project audit and its corrections.

### C. The code the paper describes (read enough to describe it exactly and check the method)

| Code | Role |
| --- | --- |
| `core/dynamic_submodels.py` | exact splitting of the DAG detector; which tensors cross each cut |
| `quantization/quantizer.py`, `quantization/nbit.py` | INT8/UINT8/FP16 and n-bit quantization |
| `protocol/packet.py` | wire format (CRC32, optional HMAC-SHA256, zstd) |
| `deployment/jetson/cuda_quant/kernel.cu`, `bindings.cpp` | CUDA INT8 quantizer, bit-identical to the Python reference |
| `evaluation/evaluate_mAP.py`, `evaluation/detection_eval.py` | accuracy protocol, paired bootstrap |
| `evaluation/benchmark_codecs.py`, `evaluation/benchmark_split_pareto.py` | codec and split payloads, timings |
| `simulation/system_model.py`, `simulation/stream_sim.py`, `simulation/analytic.py` | system model, simulator, adaptive policy, closed-form model |
| `validation/` | ns-3, OMNeT++/INET/Simu5G and loopback-emulation checks |
| `validation/hardware/placement.py`, `validation/hardware/sim_vs_real.py` | hardware placements; simulator against hardware |
| `evaluation/learned_bottleneck.py`, `evaluation/learned_bottleneck_system.py` | learned bottleneck: training, evaluation, system model |
| `scripts/verify_math_proofs.py` | checks the paper's equations and constants against the code (SymPy); **run it** |

### D. Background only (do not copy text from these)

- `AEGIS-UAV Results Brief.md` (repository root): the project log. Parts 2–8, 19.6 (R4) and 19.12 concern this
  paper.
- `Hardware Testing.pdf`: the original hardware proposal. Its "mothership" design (split at layer 4 → Jetson) is the
  "Pi k4 INT8 → Jetson" row of the live table: 2.7 frames/s, never on time.

---

## 5. The paper section by section, with its key numbers

The current values are in brackets so you can cross-check them. In the text, always use the macro.

**Abstract.** About 350 words: too long. Cut it to about 200–250 words and keep every headline result: lossless
INT8; the payload gap; JPEG wins every setting; the closed-form bound; generalization; the hardware check; the
learned bottleneck.

**I. Introduction.**
- Motivation, and three requirements for a fair evaluation:
  - held-out accuracy with the real quantization applied;
  - a properly compressed image baseline;
  - a joint link + onboard + deadline model.
- Seven contribution bullets (toolkit, accuracy, rate, system evaluation, generalization, hardware check, learned
  bottleneck).
- The central negative finding.

**II. Related work.**
- Split computing: Neurosurgeon, DADS, JALAD, Edgent, SPINN, the Matsubara survey.
- Feature compression: Choi & Bajić, BottleNet/BottleNet++, supervised compression, SC2.
- UAV links and computation.

**III. Toolkit.**
- Fig. `fig:arch` (TikZ): onboard vs split vs image offload.
- Exact DAG splitting: bit-identical output at all 22 cuts.
- Boundary quantization: Proposition `prop:int8`.
- Wire format and server.
- CUDA quantizer.

**IV. Measurement and system model.**
- Accuracy protocol: COCO val2017, quantizing exactly the crossing tensors per image, paired bootstrap.
- Rate and timing.
- Onboard speed `t_full` as a parameter: 40, 90, 180 and 360 ms.
- Traces; the simulator.
- Validation, Table `tab:validation`:
  - against ns-3, r = `\ValStreamR` [0.98] over `\ValStreamSettings` [44] settings, with the best strategy agreeing
    in `\ValStreamBestAgrees` [8 of 8];
  - the loopback emulation is within `\ValEmuMaxDiff` [0.9] frames/s;
  - Simu5G limitation stated.
- Adaptive policy: EWMA τ = `\PolicyTauMs` [200 ms], hysteresis `\PolicyHysteresisPct` [5 %].

**V. Accuracy and rate.**
- Tables `tab:splits` (per cut: tensors, onboard compute, payload, ΔmAP), `tab:quant` (wire precision at k4),
  `tab:codecs` (image baselines, mAP 44.4) and `tab:timing` (`\TimingImages` [200] frames, laptop RTX 4050).
- Figs `fig:payload` and `fig:rate`.
- INT8 changes mAP@[.5:.95] by at most `\MaxAbsDeltaINT` [0.04] points; percentile clipping hurts.
- The smallest split, `\MinSplitKiB` [310.7] KiB at `\MinSplitCut` [k4], is `\RatioMinSplitOverJPEGQNinetyFive`
  [2.4]× a Q95 JPEG.

**VI. System level.**
- Figs `fig:latbw`, `fig:single`, `fig:timeline`, `fig:hw` and `fig:swarm`; Tables `tab:system` and `tab:params`.
- JPEG is the best fixed strategy in all `\NumCells` [16] settings.
- Splitting beats onboard in `\SplitBeatsOnboardCells` [10].
- Relaying rarely helps: quote its counts from the macros.

**VII. Generalization.**
- Propositions `prop:dominance`, `prop:breakeven`, `prop:swarm` and `prop:energy`.
- Table `tab:gen-models` and Fig. `fig:gen-models`:
  - `\GenNModels` [19] detectors from `\GenNFamilies` [5] YOLO families;
  - the smallest split is `\GenRatioMin`–`\GenRatioMax` [2.0–11.5]× a Q90 JPEG;
  - input sizes `\GenResSizeSmall`–`\GenResSizeLarge` [320–1280] px.
- Fig. `fig:gen-bits`: 2–8-bit formats lose accuracy faster than JPEG.
- Monte Carlo over `\GenNScenarios` + `\GenNSwarmScenarios` [1,000 + 300] systems (Table `tab:gen-space`, Fig.
  `fig:gen-regimes`):
  - the image is at least as good as the best split in `\GenCodecBeatsSplitPct` [96.6 %] of `\GenFeasible` [977]
    feasible single-UAV scenarios;
  - a split wins by at most `\GenMaxSplitGainPct` [0.47 %];
  - the bound is attained (`\GenBoundRatioMax` [1.000]);
  - the adaptive policy is below fixed JPEG in `\GenAdaptiveBelowJpegN` [112] of `\GenAdaptiveScenariosN` [1,300],
    by at most `\GenAdaptiveVsJpegWorstPct` [7] %.

**VIII. Hardware check.**
- **Testbed:** a fanless Raspberry Pi 5 as the UAV (YOLOv8s `\HwPiFullMs` [758] ms when throttled), a Jetson Orin
  Nano edge node (`\HwJetsonFullMs` [22.7] ms, FP16), a laptop RTX 4050 ground server, Wi-Fi.
- **Placements:** all `\HwNPlacements` [1,150] evaluated; live runs in Table `tab:hardware` (`\HwLiveRuns` [29]):
  - Q90 JPEG → laptop: `\HwJpegOnTime` [14.7] on-time results/s, median `\HwJpegLatMs` [107] ms;
  - best split (k1 INT8 → laptop): `\HwKOneFps` [7.0] frames/s, `\HwKOneOnTime` [2.5] on time;
  - k4: `\HwKFourOnTime` [0.0] on time;
  - the Pi alone: `\HwPiSoloFps` [1.6] frames/s.
- **Aerial accuracy** with a VisDrone-trained YOLOv8s (mAP `\HwVdFullMap` [0.267]):
  - all `\HwVdSplitN` [16] INT8/FP16 splits are within `\HwVdSplitMaxAbsDelta` [0.0004], and every interval contains
    0;
  - Q90 JPEG loses `\HwVdJpegNinetyPct` [4.0] % and Q50 `\HwVdJpegFiftyPct` [24.0] %;
  - so a split can beat a Q90 image by at most `\HwVdBoundPct` [4.3] %.
- **Simulator vs hardware:** `\HwSimRuns` [44] runs, `\HwSimPhases` [528] phases, r = `\HwSimR` [0.947], mean
  absolute error `\HwSimMae` [1.6] results/s.

**IX. Learned bottleneck** (Fig. `fig:learned`).
- **Setup:**
  - a two-convolution encoder after k2 or k4 of the frozen VisDrone YOLOv8s, with per-image 8-bit quantization +
    zstd-1, and a decoder;
  - distilled from the detector's own neck outputs (layers 15, 18, 21) on `\LbTrainImages` [6,000] DET-train
    images, with `\LbHoldImages` [471] held out, no labels, `\LbEpochs` [20] epochs;
  - tested on `\LbValImages` [548] DET-val images;
  - `\LbConfigs` [10] configurations, with every payload measured on the same frames as JPEG q10–q95 and the post-hoc
    splits.
- **Fewer bytes than JPEG for the same mAP:**
  - k4: `\LbKFourSavingMin`–`\LbKFourSavingMax` [24–76] %, for example `\LbKFourExBytes` [3.6] kB at
    `\LbKFourExMap` [0.142] against `\LbKFourExJpegBytes` [14.9] kB;
  - k2: `\LbKTwoSavingMin`–`\LbKTwoSavingMax` [23–44] %.
- **Ceiling:** the best code is `\LbMaxMap` [0.253] at `\LbMaxBytes` [104.9] kB, against the unsplit `\LbBaseMap`
  [0.267] and Q90's `\LbJpegNinetyMap` [0.256] at `\LbJpegNinetyBytes` [77.8] kB. Resolution matters more than
  channels.
- **System:**
  - at t_full = `\LbFastMs` [40] ms the learned code wins up to `\LbFastGoodput` [17.3] Mbit/s;
  - at `\LbSlowMs` [360] ms, up to `\LbSlowGoodput` [3.5] Mbit/s;
  - on the measured Pi (`\LbPiMs` [758] ms) only below `\LbPiGoodput` [0.6] Mbit/s, where no option delivers more
    than `\LbPiUtilMax` [2.7] accuracy-weighted on-time results/s.

**X. Discussion and limitations.**
- What the results mean.
- Limitations (i)–(vi): onboard speed as a parameter with one measured board; synthetic traces with validated links;
  zero-shot aerial imagery in the generalization study; single-frame H.264; independent swarm policies; latency to
  the server.
- Reproducibility: `make reproduce`.

**XI. Conclusion.**

---

## 6. The exact limits of each claim (the text must respect these)

- **"Splitting never beats JPEG" applies only to post-hoc quantized splits** (INT8/FP16/n-bit, with zstd) of
  unmodified detectors. Compressors trained *together with* the detector can beat image coding at equal rate, as the
  literature reports. Our frozen-detector bottleneck already beats JPEG on bits.
- **The learned bottleneck keeps the detector frozen** and does not reach the unsplit accuracy. A jointly trained
  bottleneck is untested; say so, as future work.
- **Hardware:** one onboard computer (a Pi 5 that encodes JPEG on its CPU and has no neural accelerator), one Wi-Fi
  network, boards on a table, no flight.
- **The 1,150 placements come from measured component timings,** and the model is optimistic: 0.8–2.0× the live
  rate for two-device placements (`docs/hardware_results.md`). Only the important placements were run live.
- **r = 0.947** holds once the controller's one-frame-in-flight rule and the network conditions actually applied
  are modelled (`docs/claims_validation.md`).
- **The generalization study uses COCO-trained detectors on VisDrone zero-shot;** the hardware check and the learned
  bottleneck use the VisDrone-trained YOLOv8s.

---

## 7. Known issues (fix them; find more)

1. **Abstract:** "a Q95 JPEG frame that loses only −0.21 [−0.30, −0.10] points" is a double negative. Use a positive
   macro ("loses only 0.21 points") or "changes mAP by …".
2. **The author block and running heads** carry author and institution details. Replace them with a placeholder
   (rule 6), and make the running head neutral, for example the short title only.
3. **The introduction's seven bullets** are too many. Consider merging "hardware check" and "learned bottleneck".
4. **Proposition references:** `prop:int8` is numbered first, so `prop:dominance` renders as Proposition 2. Every
   reference must use `\ref`, never a typed number.
5. **Terminology:** use "image offload" vs "JPEG offload", "goodput", "on-time" and `t_{full}` consistently
   throughout.
6. **Figure legibility at column width:** check `learned_bottleneck.pdf` (labels near 27 kB and 53 kB are tight) and
   `gen_regimes.pdf`.
7. **Related work:** consider FrankenSplit (Furutanpey et al., 2024) and Matsubara et al. (2021), "Neural
   Compression and Filtering for Edge-assisted Real-time Object Detection". Verified DOIs for both are in
   `paper/references_verified.bib`; copy them across only if you cite them.
8. **`uav-split-perception/README.md`** says 106 tests; there are 129, and it doesn't mention the hardware check or
   the learned bottleneck. Update it if the paper links to the repository.

---

## 8. Writing standards

- **Precise, plain and direct.** One idea per sentence, active voice, no hype ("significantly", "novel", "superior")
  unless a statistic supports it.
- **Define every term at first use,** and use it the same way throughout.
- **Report intervals with their method** (95 % paired bootstrap; Student-t), and units every time.
- **Make every figure and table self-contained,** and cite each one in the text before it appears. Captions say what
  is plotted and on what data.
- **Keep the negative result central and exact;** avoid absolutes ("never", "always") unless the macro-backed result
  is literally total, and then say over what.
- **Narrative:** question → toolkit → accuracy → rate → system → why (closed form) → generalization → hardware →
  learned bottleneck → meaning.

---

## 9. How to work

1. **Set up:** sparse-clone, build, render every page, run `python scripts/verify_math_proofs.py` and
   `python paper/validate_manuscript.py`.
2. **Read** all of section 4. Write yourself a map of each claim → macro → source file.
3. **Audit, then stop and report.**
   - Check every sentence against its evidence and the limits in section 6.
   - Check each macro's sign, units and reference (for example "× Q95" vs "× Q90").
   - Check every figure and table reference and caption.
   - Check the equations against `simulation/system_model.py`.
   - **Give the user the full list of findings and your revision plan, and wait for approval before large rewrites.**
4. **Revise:** fix the issues, tighten the abstract and introduction, and apply the writing standards. Rebuild and
   re-render after each section.
5. **References:** verify every new one. Keep BibTeX fields consistent and ASCII-only (LaTeX-escaped).
6. **arXiv package:**
   - a clean folder with `main.tex`, the generated `main.bbl` (arXiv does not run bibtex reliably), `generated_tables/`
     and `figures/`;
   - confirm it compiles from scratch with `pdflatex` alone;
   - propose the metadata: title, plain-text abstract with the numbers written out, primary category **cs.NI** with
     cross-lists **cs.CV**, **cs.LG** and **cs.RO**, a comments field ("N pages, 12 figures, 10 tables; code and data:
     <repository URL>"), and a licence.
7. **Hand back:** a change log, the build status, the arXiv folder, and the open decisions.

---

## 10. Decisions to ask the user for (do not guess)

- The final author list, order, affiliations, emails and acknowledgements.
- The target: arXiv only first, or arXiv plus a named venue (and its page limit and template). Natural fits: a
  journal such as IEEE Access, Computer Networks or Ad Hoc Networks, or a drone-systems workshop such as DroNet. Top
  venues would ask for a jointly trained bottleneck and a flight test.
- The 14-page journal format only, or a shorter conference version too.
- The arXiv licence (for example CC BY 4.0), and whether the repository URL appears in the paper.
- Whether to run the optional experiment that would most strengthen the paper: a bottleneck trained together with
  the detector, starting from `evaluation/learned_bottleneck.py` (laptop GPU, 1–2 days, unattended).
- Whether to commit and push.
