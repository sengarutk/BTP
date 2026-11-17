# Reproducing the results of both papers

Paths are relative to `uav-split-perception/` unless noted. Every number in both papers is a generated LaTeX macro,
computed from the committed result files. Nothing is typed by hand. The general pipeline (COCO, codecs, simulator,
ns-3/OMNeT++ checks, the open benchmark) is the `Makefile`. This file adds the steps the Makefile does not cover: the
board campaigns, the analyses run on their result files, and the two paper builds.

## 1. One command: re-derive everything from the committed results

```bash
scripts/repro_check.sh
```

The script needs no board. It runs these steps:

1. It re-scores the 17 mesh campaigns of 14–16 Nov 2026 (`validation/hardware/mesh2_summary.py --campaign …`; the per-run scores are cached in each campaign's `_eval_cache_mesh.json`).
2. It re-computes the deadline calibration and compares it with the committed file.
3. It re-checks Theorem 1 and the price rules on every logged price update.
4. It re-runs paper 1's break-even analysis with the measured Pi times.
5. It regenerates the derived numbers:
   - paper 1's board macros;
   - Results Brief 19.24–19.31;
   - the Final Report and the Novelty Brief.
6. It builds both papers.
7. It fails if any derived file differs from the committed version.

To skip steps 1–4, run `QUICK=1 scripts/repro_check.sh`.

Other checks:

| Check | Command | Time |
| --- | --- | --- |
| Unit and integration tests | `python -m pytest -q` | under 1 min |
| Open benchmark (replay, oracle, traces, theory) | `make benchmark-check` | about 70 s |
| Earlier audit checks (28 Oct) | `scripts/audit_2026-10-28/` | minutes |

## 2. Environment

### Laptop

| Item | Version |
| --- | --- |
| Operating system | WSL2 Ubuntu on Windows |
| GPU | RTX 4050 |
| Python | 3.12.3, venv `../venv` |
| Python packages | Pinned in `requirements.txt`: torch 2.13.0, torchvision 0.28.0, ultralytics 8.4.132 (pinned because model construction changes between releases), numpy 1.26.4, opencv-python 4.11.0.86, zstandard 0.25.0, matplotlib 3.11.1 |
| Learned image codecs | Separate venv `../venv_lic` with compressai 1.2.8 |
| LaTeX | TeX Live 2023: pdflatex and bibtex |
| ffmpeg | 6.1.1, for the video-codec analysis |

### Boards

| Board | Role and setup |
| --- | --- |
| Raspberry Pi 5 (×3, fanless) | One is pi-sender, the ground radio, cabled to the laptop. Two are cameras: pi-relayyy and pi-receiver. |
| Jetson Orin Nano (15 W) | Nano1, an edge drone |
| Jetson Orin Nano Super (25 W) | Nano2, an edge drone. Software: JetPack 7 (L4T R39), TensorRT 10.16, CUDA PyTorch |
| Network | An IBSS mesh on channel 6, routed by batman-adv (AegisSwarm). The laptop reaches the mesh through SSH port forwards on pi-sender. |

Board passwords are read only from environment variables (`PI2_PW`, `PI3_PW`, `NANO_PW`, `N2_PW`). They are never
stored in a file.

### Data and weights

- VisDrone2019: `scripts/prepare_datasets.py`.
- The fine-tuned detectors are in `weights/*_visdrone.pt`. Their training runs are in `experiments/finetune/`.

## 3. The board campaigns (14–16 Nov 2026)

### Before the first run of any campaign

1. Push the code to the boards with `validation/hardware/tools/push_code_mesh.sh`.
2. Open the tunnel with `mesh_tunnel.sh`.
3. Start the laptop's keep-awake ping. It writes `vid_campaign_mesh2_laptop_ping.txt`, which is used to check every run.
4. Commit the campaign's predictions to `docs/mesh_predictions_nov14.md` before the first run.

### Running a campaign

Every campaign script:

- is resumable;
- shuffles the order of strategies in each repetition;
- starts a run only once the camera Pi is below a set temperature (`COOL`, 55–60 °C);
- removes its temporary nft/tc rules after every run.

Run on mains power only. Runs made on battery are archived in `_superseded/` and re-run.

The scripts are in `validation/hardware/tools/`. The results are in `experiments/results/hardware/`.

| Campaign script | Results folder | What it tests | Results Brief |
| --- | --- | --- | --- |
| `campaign_heat_nov.sh` (re-tests with `HEAT_OUT`, `HEAT_STRATS`, `HEAT_REPS`) | `vid_campaign_heat_nov`, `_heat_nov2`, `_heat_final` | Capped hold and guard on a 24-min mission with a blackout | 19.25 |
| `campaign_final_nov.sh` | `vid_campaign_final_nov` | Final controller against v4.1, AccuMO-style and LEAF-style, 5 repetitions | 19.26 |
| `campaign_final_nov.sh` with `FINAL_OUT`, `FINAL_STRATS`, `FINAL_REPS` | `vid_campaign_budget_nov`, `vid_campaign_fix_nov` | The 2.4 W budget, and the late-path skip | 19.26 |
| `campaign_plus_nov.sh` (re-test with `PLUS_OUT`) | `vid_campaign_plus_nov`, `_plus_nov2` | v4.1+ re-test | 19.27 |
| `campaign_dvfs_nov.sh` | `vid_campaign_dvfs_heat`, `_dvfs_short` | CPU clock as a priced knob | 19.27 |
| `campaign_two_nov.sh` (follow-up with `TWO_OUT`, `TWO_STRATS`, `TWO_REPS`) | `vid_campaign_two_nov`, `_two_cap` | Two camera drones on one channel | 19.28 |
| `campaign_pull_nov.sh` (`pull_bench.py`) | `pull_nov/`, `pull_nov_fair/` | Pull-one-ahead coordinator, up to 8 streams | 19.28 |
| `campaign_topology_nov.sh`, `campaign_fps_nov.sh`, `campaign_relaynoise_nov.sh`, `campaign_energy_nov.sh` | `vid_campaign_topology_nov`, `_fps_nov`, `_relaynoise_nov`, `_energy_nov` | Topology, frame rate, noisy relay, energy price | 19.29 |
| `campaign_mesh4.sh` (`REPS=2`) | `vid_campaign_mesh4` | First planner pass | 19.26 |
| `campaign_t10_nov.sh` (`t10_predict.py` first) | `t10/` (`t10_prediction.json`, `sweep/`) | Paper 1: live break-even sweep | 19.30 |
| `t11_video_bench.sh` | `t11/` | Paper 1: video encode times on the Pi | 19.30 |
| `dvfs_profile.py` (run with sudo on the Pi) | `energy/dvfs_profile_*.json` | Clock profile | 19.27 |
| `tunnel_bench.py` | `tunnel_bench/` | Cost of the SSH tunnel | 19.31 |

The full sessions were chained by `session_nov14.sh`, `start_on_mains.sh`, `chain_after_nov16a.sh` and
`resume_on_mains_nov16.sh`. The session log is `docs/mesh_session_nov14.md`, and every verdict is in
`docs/mesh_results_nov15.md`.

## 4. From result files to numbers

### Paper 2

`paper2/build.sh` runs:

- `make_metrics.py`, which writes `generated/metrics.tex`;
- `make_figures.py`;
- LaTeX.

It fails on any undefined macro, citation or reference. `make_metrics.py` reads:

| Input | What produces it |
| --- | --- |
| Campaign summaries (`vid_campaign_*_summary.json`) | `mesh2_summary.py` |
| `theory_check/theory_check.json`, `price_rules_check.json` | `paper2/theory_check.py`, `paper2/price_rules_check.py` |
| `theory_check/guard_theorem.json` | `paper2/guard_theorem.py` |
| `calibration/calib_hw_nov16.json` | `validation/hardware/calib_hw.py` |
| The board numbers | `scripts/report_mesh_nov16.py` |

### Paper 1

`paper/build_paper.sh` runs `validate_manuscript.py`, then LaTeX. The board numbers come from
`evaluation/board_metrics_paper1.py`, which writes `paper/generated_tables/board_metrics.tex` and a table of each
number's source in `board_metrics_sources.md`. That script uses:

- `evaluation/pi_measured_break_even.py`, which writes `experiments/results/video_codecs/analysis_pi_measured.json`;
- `evaluation/pi_measured_second_detector.py`.

The rule's own tests are listed in the header of `paper/drafts/design_rule.tex`.

### The reports

All three reports take their numbers from `scripts/report_mesh_nov16.py`:

- the Results Brief, through that script directly;
- the Final Report and the Novelty Brief, through `scripts/report_final_nov16.py`.

Both builders are idempotent. Each archives the version it replaces in
`experiments/results/hardware/_superseded/report_before_*`.

## 4b. Laptop strengthening (16–17 Nov 2026, no boards)

Predictions and verdicts are in `docs/laptop_strengthening_predictions_nov16.md`. Every script reads recorded board
data or runs the validated trace replay.

| Item | Script | Output |
| --- | --- | --- |
| 5: equal accuracy as a tested equivalence (TOST) | `validation/hardware/equivalence_tost.py` | `hardware/equivalence/equivalence.json` |
| 6: airflow sensitivity (replay) | `scripts/airflow_sweep_nov16.sh`, then `replay_airflow.py analyze` | `replay/airflow_nov16/airflow_summary.json` |
| 8a: deadline probability recalibrated (held-out day) | `validation/hardware/calib_recal.py` | `calibration/calib_recal_nov16.json` |
| 8b: conformal deadline probability (replay) | `replay_conformal.py` (`scripts/conformal_then_skip_nov16.sh`), then `--analyse` | `replay/conformal_nov12/summary.json` |
| 2: published split results re-read | data file, quoted from the papers | `results/literature/published_splits.json` |
| 1a: T10 timing model against the sweep | `evaluation/t10_model_check.py` | `hardware/t10/t10_model_check.json` |
| 1b: a Jetson camera on measured times | `evaluation/jetson_measured_break_even.py` | `video_codecs/analysis_jetson_measured.json` |
| 7a: the late-path rule on held-out logs | `validation/hardware/skip_counterfactual.py` | `hardware/skip_counterfactual/skip_cf.json` |
| 7b: the late-path rule on held-out replay seeds | `replay_skip.py run --shared 0/1`, then `analyze` | `replay/skip_nov16/skip_summary.json` |
| 10: pull model against the bench | `validation/hardware/pull_model_check.py` | `overload_handling/pull_model_check.json` |
| 9: two-time-constant thermal fit | `paper2/thermal_two_mode.py` | `theory_check/thermal_two_mode.json` |
| 3: paper 1 conference version | `bash paper/build_conf.sh` | `paper/main_conf.pdf` |

The replay runs are long: about 10 min per 24-minute mission with 3 processes. Run them on mains power, with at most
4 replay processes at a time. The laptop restarted twice when it slept on battery; every runner resumes from its
finished rows.

## 5. Rules kept for every result

- Predictions are committed before the first run, and failed predictions are reported as failed.
- Strategies are compared only within one campaign, using paired repetitions.
- Results are never deleted. A run that becomes invalid is moved to `_superseded/` with the reason.
- Controller settings are tuned only on VisDrone-DET val and VID train. The test clips are never used for tuning.
