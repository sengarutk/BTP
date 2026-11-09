# AEGIS-UAV: split computing vs. image offloading for UAV object detection

Code and reproducible experiments for the paper *"When Does Split Computing Pay Off for UAV Object
Detection? A Measured and Trace-Driven Study with YOLOv8"* (`paper/main.tex`).

The repository provides

- **an exact split-inference toolkit for YOLOv8** — cut after any of the 22 layer boundaries; the
  edge part returns every activation that crosses the cut, and edge→cloud output is bit-identical
  to the unsplit model;
- **a fail-closed wire format** with CRC32, optional HMAC-SHA256 authentication, and INT8 / UINT8 /
  FP16 / zstd payloads, plus ZeroMQ edge and cloud processes and a server that serves every cut from
  one copy of the weights;
- **a C++/CUDA INT8 quantizer** that is bit-identical to the Python reference;
- **the measurement and simulation code** behind every number in the paper: COCO val2017 accuracy
  with paired-bootstrap CIs, codec baselines (JPEG, WebP, libx264), per-stage timing, and a
  trace-driven single-/multi-UAV simulator;
- **a generalization study**: a closed-form model of onboard / split / offload
  (`simulation/analytic.py`) checked on 1,300 randomly drawn systems varying 24 parameters, payload
  and exactness for 19 detectors (YOLOv5u/v8/v9/v10/11), 2–8-bit wire formats, input sizes
  320–1280 px, and VisDrone aerial imagery;
- **a hardware check** (`validation/hardware/`): YOLOv8s on a Raspberry Pi 5, a Jetson Orin Nano and a
  laptop GPU, a model of every placement built from measured component timings, live pipelines, and
  the simulator rebuilt from live runs;
- **a learned bottleneck** (`evaluation/learned_bottleneck.py`, `evaluation/learned_bottleneck_system.py`):
  a small encoder and decoder trained at a cut of the frozen VisDrone-trained YOLOv8s, compared with
  JPEG and the post-hoc splits on the same frames and in the system model.

## Quick start

```bash
python3 -m venv venv && source venv/bin/activate
make setup          # pinned dependencies + editable install
make data           # COCO val2017 (~800 MB) and COCO128
make test           # pytest suite: 126 tests collected (replay and IPC tests need Linux; CUDA tests a GPU and nvcc)
make reproduce      # COCO results, generalization study, tables, figures and the PDF (GPU recommended, ~7 h)
```

`make results` regenerates the COCO accuracy, codec, timing and system-study files in `experiments/results/`; `make tables figures`
rebuilds `paper/generated_tables/` and `paper/figures/` from them; `make paper` builds the PDF.
Every number in the paper text is a macro written by a generator in `evaluation/` (`make_tables.py`,
`make_generalization.py`, `make_validation.py`, `make_hardware.py`, `make_learned.py`); the mapping from
each macro to its value and source file is in `docs/claims_to_evidence.md` and the `docs/claims_*.md` ledgers.
`make reproduce` does not run four parts, whose result files are committed: the simulator validation
(`make validate`, `make validate-omnetpp`), the hardware runs (`validation/hardware/`), the VisDrone
fine-tuning (`scripts/train_visdrone.py`) and the learned bottleneck (`evaluation/learned_bottleneck.py`).
`python scripts/verify_math_proofs.py` checks the paper's equations and stated model constants against
the code, `configs/`, and the result files (SymPy proofs, exact-rational checks, and parameter comparisons);
it exits with status 1 if any check fails.

## Generalization study

`make generalization` downloads the extra detector weights and VisDrone val, then runs, resumably:

| Script | What it measures | Output (`experiments/results/generalization/`) |
|---|---|---|
| `evaluation/gen_model_survey.py` | per detector × input size × imagery: bit-exactness at every cut, per-cut payloads, bottleneck cut, n-bit sizes, timings, codec sizes | `model_summary.csv`, `model_cuts.csv`, `codec_sizes.csv` |
| `evaluation/gen_accuracy.py` | COCO / VisDrone accuracy of n-bit splits and JPEG across bit widths, detectors, input sizes, aerial imagery | `accuracy.csv` |
| `evaluation/gen_scenarios.py` | Monte Carlo over every system variable; simulated utility of every configuration and both policies, plus closed-form predictions | `scenarios.csv`, `scenario_strategies.csv` |

`evaluation/make_generalization.py` turns them into `paper/generated_tables/gen_metrics.tex`, two tables,
three figures, and `docs/claims_generalization.md`. VisDrone labels are mapped to COCO classes by
`scripts/prepare_datasets.py` so that COCO-trained detectors can be evaluated zero-shot.

## Layout

| Path | Contents |
|---|---|
| `core/` | split submodels (`dynamic_submodels.py`), named splits + multi-cut dispatcher (`submodels.py`), graph/FLOP inspection, standalone checkpoint export |
| `quantization/` | per-tensor / per-channel INT8, affine UINT8, FP16, zstd |
| `protocol/` | wire format (`packet.py`) and ZeroMQ transport |
| `pipeline/` | edge and cloud streaming processes, runtime policy switchboard |
| `simulation/` | channel-trace generator, system model (hardware, energy, policy), slotted simulator, optional `tc netem` replay |
| `evaluation/` | accuracy (`evaluate_mAP.py`), codecs, timing/payload (`benchmark_split_pareto.py`), quantization modes, system study (`benchmark_system.py`), tables, figures |
| `deployment/jetson/` | TorchScript/ONNX/TensorRT export, CUDA quantizer |
| `demo/` | interactive split-inference demo with HUD |
| `tests/` | pytest suite |
| `traces/` | synthetic channel traces (CSV: `timestamp_ms, sinr_db, bandwidth_mbps, delay_ms, packet_loss_pct`) |
| `archive/` | superseded code and outputs, not used for any result |

## Running the live pipeline

```bash
# terminal 1: ground server
python -m pipeline.cloud_pipeline --endpoint ipc:///tmp/aegis.ipc --auth-key secret
# terminal 2: UAV side, split after layer 4, INT8, frames from COCO val2017
python -m pipeline.edge_pipeline --cut 4 --dtype int8 --endpoint ipc:///tmp/aegis.ipc --auth-key secret
```

To exercise it under a channel trace on Linux (root required):
`sudo python -m simulation.netem_controller --trace traces/trace_5g_moderate.csv --interface lo`.

## What is measured and what is modelled

- **Measured:** accuracy (COCO val2017, 5,000 images), payload sizes, codec sizes and accuracy,
  and per-stage timings on the host GPU.
- **Modelled:** onboard speed is a parameter (`t_full`, swept over 40–360 ms), power figures are
  assumptions listed in the paper, and the channel traces are synthetic (log-normal shadowing +
  Rician fading + the 3GPP TR 36.942 attenuated Shannon mapping). Measured traces in the same CSV
  format can replace them.

## Notes

- Versions are pinned in `requirements.txt`: Ultralytics changes how model configs are built between
  releases, so standalone checkpoints store activation types as well as weights.
- Ultralytics YOLOv8 is AGPL-3.0; choose a licence for this repository that is compatible with it.
