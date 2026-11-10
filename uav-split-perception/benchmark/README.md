# AEGIS-UAV open benchmark

You can score a perception-offloading controller for a fanless drone computer against a measured three-board
testbed without having the boards. The benchmark is built from the code and data behind both papers. Nothing in it
is re-implemented.

| Part | What it is | Where |
| --- | --- | --- |
| Replay | A trace-driven replay of the testbed: a Raspberry Pi 5 camera drone, a Jetson Orin Nano edge drone and a laptop ground station (details below). | `validation/hardware/replay.py` |
| Oracle | v4.1, v4.1 with a clairvoyant link, all 17 fixed configurations, and the per-phase hindsight best. Every policy runs on the same seeds and link draws. | `validation/hardware/replay_oracle.py`, results in `experiments/results/hardware/replay/oracle_oct29_plant/` |
| Traces | Every hardware run: per-run power, temperature, prices and decisions. | `experiments/results/hardware/vid_campaign_*` |
| Theory | Paper 2's Theorem 1 bound and Proposition 1, checked on every logged price sequence. | `paper2/theory_check.py` |

The replay uses measured data throughout:

- goodput traces;
- onboard times;
- Pi power and the thermal plant;
- the real detections of every variant on every frame.

It applies the fault scenarios with netem, as on the boards, and scores results with streaming AP, exactly as the
live runs are scored.

**How well the replay matches the hardware.** It was validated against the 240-run main hardware campaign by
comparing the policy means. The Pearson correlations are:

| Measure | r |
| --- | --- |
| Streaming AP | 0.95 |
| Pi power | 0.99 |
| Availability | 0.93 |
| Time at or above 80 °C | 0.96 |

The full comparison is in `replay/validate_main_oct29_plant/replay_check.json`.

## One-command check

```bash
make benchmark-check        # or: python -m benchmark.aegis_bench check   (about 70 s)
```

It checks four things:

1. Every data file still matches `MANIFEST.json` (sha256). There are 1,518 files, about 1.06 GB.
2. The replay reproduces the stored v4.1 results bit for bit, on two scenarios.
3. The example policy runs.
4. Three stored results still hold:
   - the stored validation against the hardware;
   - paper 2's Theorem 1, recomputed from the hardware traces, identical to the stored check;
   - the tests for paper 1's break-even rule and for the planner.

## Score your own controller

A policy is one function in a Python file:

```python
def decide(rp, t):          # called every camera frame (30 fps); t in seconds; rp: the replay
    if rp.links["laptop"].idle(t) and rp.links["laptop"].est(t)[0] >= 8.0:
        return ("laptop", "m640q90")        # (server, variant)
    if rp.onb_free <= t:
        return ("onboard", "n320")
    return None                             # send nothing this frame
```

Then score it:

```bash
python -m benchmark.aegis_bench score my_policy.py --scenario mission random --seeds 1-5
```

**Servers and variants.**

| Server | Variants |
| --- | --- |
| `laptop`, `jetson` | `s640q90`, `s640q50`, `s480q90`, `s480q50`, `s320q90`, `s320q50` (YOLOv8s at a given size and JPEG quality) |
| `laptop` only | also `m640q90`, `m640q50` (YOLOv8m) |
| `onboard` | `n320`, `s320`, `s640` |

**State your policy can read.**

| Attribute | What it gives |
| --- | --- |
| `rp.links[p].est(t)` | goodput estimate and its spread, in Mbit/s |
| `rp.links[p].idle(t)` | whether link `p` is idle |
| `rp.onb_free` | when the onboard model is next free |
| `rp.onboard_ms(v)` | onboard inference time of variant `v`, in ms |
| `rp.aoi` | age of the shown result, in ms |
| `rp.temp` | board temperature, in °C |
| `rp.last_onboard_det` | the latest onboard detections |

A choice of a busy server is dropped, as on the live harness.

**What the score reports.** For each run, the report gives:

- your streaming AP, Pi power and mean temperature;
- v4.1 on the same seeds and link draws;
- the clairvoyant v4.1 and the best fixed configuration, taken from the stored oracle.

The report is written to `experiments/results/benchmark_scores/score_report.json`.

## Reference results

These cover five seeds of the `mission` and `random` scenarios, with 20-s phases. The example policy is
`benchmark/example_policy.py`: a goodput threshold rule with a heat guard. It prices nothing and forecasts nothing.

See `REFERENCE.md`, which `aegis_bench score benchmark/example_policy.py --seeds 1-5` generates.

## Scope and limits

These are the replay's own limits:

- one camera drone;
- link recovery is fixed at 1.2 s;
- the Jetson never throttles (measured: 61 °C at full load);
- no CPU contention beyond the measured times.

The oracle references bound what better prediction or a better per-phase choice could add. They are not proven
optima.

The VisDrone data falls under its own licence. Download the VID val clips with
`validation/hardware/prepare_vid.py`.
