Before we start the next stage of work on this laptop, I need a **read-only readiness check**. Do not change, install,
delete, commit or push anything during this check. Only look and report. If a check needs a command that would change
something (an install, a download, a checkout), do not run it; write down the command you would run instead.

## What we want to run here, and what each part needs

This is the plan for the next two weeks. All of it is laptop work except one half-day on the boards. We want to know
which parts can run on **this** laptop.

| Phase | Work | What it needs |
|---|---|---|
| 1 | Theorems for paper 2 (power budget, accuracy gap, temperature rule), checked against recorded data | CPU only; `paper2/`, `validation/hardware/adaptive2.py`, `replay*.py`, and the recorded runs in `experiments/results/hardware/` (mesh campaigns, replay summaries, energy constants) |
| 2 | Jointly trained split: fine-tune the VisDrone YOLOv8s together with the learned bottleneck (k2 and k4, 3–4 code sizes) | **NVIDIA GPU with CUDA** (the reference laptop: RTX 4050, 6 GB); `evaluation/learned_bottleneck.py`; `weights/yolov8s_visdrone.pt`; the **VisDrone2019-DET train and val images** in `datasets/visdrone/` (about 3.2 GB, not in git) |
| 3 | "When does a split pay off" rule, tested on every measured point | CPU; `experiments/results/learned_bottleneck/`, `generalization/`, `hardware/raw/`, `paper/` |
| 4 | Simulator sweep: noise and packet loss on relayed links | CPU, several cores; `simulation/` |
| 5 | Board scripts and a dry run | Writing works anywhere, but the dry run needs Linux tools (bash, `tc`/netem, ssh) |
| 6 | Half-day on the boards | **Not here.** It runs from the laptop that is connected to the AegisSwarm mesh |
| 7 | Integration, audit, report updates | Builders in `scripts/`, the report HTML files at the repository root, LaTeX for both papers |

The reference laptop where all of this has run so far:
- Linux (WSL2 Ubuntu), Python 3.12.3;
- torch 2.13.0+cu130 with CUDA, ultralytics 8.4.132, numpy 1.26.4, opencv 4.11.0;
- 16 CPU threads, 11 GB RAM visible to Linux;
- pdflatex and bibtex.

## Checks to run, in this order

1. **System.**
   - Operating system and version.
   - Is WSL2 with Ubuntu available? If so, run every following check **inside WSL as well**, and report both.
   - CPU threads, total RAM, free disk space on the drive holding the repository.
2. **GPU, needed for Phase 2.**
   - `nvidia-smi`: GPU model, memory, driver and CUDA version.
   - In the Python environment you use for this repository: `python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"`.
   - A tiny CUDA test: allocate a 1000×1000 tensor on the GPU and multiply it. This changes nothing on disk.
3. **Python environment.**
   - Python version, and the versions of torch, torchvision, ultralytics, numpy, opencv-python, zstandard, pandas,
     matplotlib, scipy and pytest.
   - Compare them with `requirements.txt` and `requirements-dev.txt`, and list what is missing or differs from the
     reference versions above.
4. **Repository state.**
   - `git status`; `git branch -a`; `git log -3 --oneline` on `main` and on `paper1-arxiv`.
   - `git fetch` only, no pull, then report how far local `main` and `paper1-arxiv` are behind `origin`.
   - Is this a sparse checkout? If so, print `git sparse-checkout list`.
5. **Files each phase needs.** For each path, report "present", "missing" or "present but empty", and its size:
   - `uav-split-perception/validation/hardware/` (`adaptive2.py`, `replay.py`, `mpc_planner.py`);
   - `uav-split-perception/simulation/`, `evaluation/`, `scripts/`, `paper/`, `paper2/`, `tests/`;
   - `uav-split-perception/weights/yolov8s_visdrone.pt` and `weights/learned_bottleneck/`;
   - `uav-split-perception/experiments/results/hardware/`: the folders `vid_campaign_mesh`, `vid_campaign_mesh2`,
     `vid_campaign_mesh3`, `vid_campaign_main`, `replay/`, `energy/`, `raw/`, plus the files `placements.csv`,
     `live_summary.csv` and `staleness_decay_forecast_v2.json`;
   - `uav-split-perception/experiments/results/learned_bottleneck/` and `experiments/results/generalization/`;
   - `uav-split-perception/datasets/visdrone/VisDrone2019-DET-train/images` and `VisDrone2019-DET-val/images`
     (count the images: train should be about 6,471 and val 548);
   - the report files at the repository root: `AEGIS-UAV Results Brief.html` and `.md`,
     `AEGIS-UAV Final Report.html`, `AEGIS-UAV Novelty Brief.html`.

   The whole `experiments/` folder is about 13 GB in git. If it is not all present, say which parts are and how much
   disk adding the rest would need. Do not add them.
6. **Quick functional tests.** These only read files, or write inside a temporary folder.
   - `pytest -q tests` from `uav-split-perception`. On the reference Linux laptop: 130 passed. On Windows, 3 tests are
     known to fail because they need Linux.
   - `python scripts/verify_math_proofs.py` after `bash paper/build_paper.sh`. The build writes only inside `paper/`.
     Expected: 15 pages, 40/40.
   - Paper 2: compile `paper2/main.tex` from its committed `generated/` files (pdflatex, bibtex, pdflatex ×2), without
     running `paper2/build.sh`, which needs the full results. Report pages and warnings.
   - Phase 2 smoke test, **only if a CUDA GPU is available and the VisDrone DET images are present**: run
     `python -m evaluation.learned_bottleneck --help` to see its sub-commands. Do not start training. Then report
     whether the script finds `weights/yolov8s_visdrone.pt` and the DET train folder at the paths it expects
     (`WEIGHTS` and `TRAIN_DIR` near the top of the file).
   - Phase 4 smoke test: `python -c "import simulation.stream_sim"` from `uav-split-perception`.
7. **Memory limit.** The reference laptop crashed twice when its memory ran out. For this machine, report:
   - how much RAM is free with your usual programs open;
   - whether WSL has a memory limit set in `%UserProfile%\.wslconfig`.

## Report

End with one table, one row per phase (1–5 and 7):

| Phase | Can run here? (yes / yes after setup / no) | What is missing | Exact commands to fix it, not run | Estimated download / disk |

Then list:
- anything that differs from the reference laptop and could change a result (other library versions, Windows instead
  of Linux, a different GPU);
- your recommendation: which phases to run here, and which to leave for the reference laptop.

Remember: this check changes nothing. I'll decide what to install or download after reading your report.
