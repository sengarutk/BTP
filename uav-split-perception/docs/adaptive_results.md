# Adaptive multi-server perception scheduling: live hardware results

Hardware:
- Camera UAV: Raspberry Pi 5.
- Edge: Jetson Orin Nano (FP16, 15 W, clocks locked).
- Ground: laptop RTX 4050 (FP16).
- Network: all three on one home Wi-Fi access point.

Controller: `validation/hardware/adaptive2.py`; worker: `validation/hardware/adaptive.py worker`.
Raw runs: `experiments/results/hardware/adaptive2/`. Summary: `adaptive2_summary.csv`, produced by
`validation/hardware/summarize_adaptive2.py`.

## Setup

**Three servers.** Each holds at most one frame at a time:
- the Pi's own CPU, running YOLOv8n@320, YOLOv8s@320 or YOLOv8s@640;
- a Wi-Fi path to the laptop, which runs YOLOv8s on JPEG q90/q50 at 640, 480 or 320, or YOLOv8m@640 at
  q90/q50;
- a Wi-Fi path to the Jetson, which runs YOLOv8s on the same JPEG variants.

**Measured inputs.** Every variant's accuracy is its measured COCO val2017 mAP@[.5:.95] on 5,000 images
(`variant_accuracy.json`). Device times and payload sizes come from the per-device measurements, and the
controller updates them online.

**Controller.** For each camera frame (30 fps), the newest frame goes to the idle server, and the
variant, that adds the most accuracy-weighted on-time results per second. The estimate is
(mAP / mAP of YOLOv8s@640) × P(on time | Gaussian goodput estimate) / busy time.

**Impairments.** Applied with `tc netem` on the Pi's Wi-Fi, to the data ports only, per path:
- rate limits of 6, 3, 2 and 1.5 Mbit/s;
- 100 % loss (blackout).

**Protocol.**
- Four scenarios: `mission` (ground link fails first), `mission_mirror` (Jetson link fails first),
  `random` (each path follows a Markov chain over five states, 4 s steps, same seed for every policy
  in a repetition) and `static_good` (no impairment).
- Each run is 120 s.
- 2 repetitions, with the policy order shuffled per repetition.
- 300 ms deadline.

**Policies.**

| Policy | Description |
|---|---|
| `A_full` | All servers in parallel, with per-frame variant adaptation |
| `A_paths` | The two Wi-Fi paths with adaptation; onboard only as a fallback |
| `A_single` | One server at a time, with adaptation |
| `static_multi` | All servers in parallel with fixed variants (laptop s640q50, Jetson s640q50, onboard n320); no adaptation |
| `fixed:<server>:<variant>` | One server and one variant throughout |
| Phase oracle | The best fixed policy in every phase, chosen with hindsight; an upper bound for any single-server, single-variant policy |

**Harness problems found during the campaign, fixed, and the affected runs rerun.**
- Leftover worker processes from earlier runs reconnected to new runs. Those 27 runs were discarded.
- A sender thread could die on a closed socket. The 10 flagged runs were rerun.
- The stall rule now requires that no bytes have been acknowledged for 1.5 s, independent of payload
  size.

## Results (median of 2 repetitions)

Accuracy-weighted on-time results per second (on-time results per second in brackets):

| Scenario | A_full | static_multi | A_paths | A_single | Best fixed | Phase oracle (fixed) |
|---|---|---|---|---|---|---|
| mission | **18.8** (22.4) | 16.9 (21.2) | 16.4 (18.2) | 13.8 (15.7) | 11.6 (16.3), jetson s320q50 | 15.2 (19.6) |
| mission_mirror | **20.5** (22.4) | 17.0 (21.3) | 18.5 (19.1) | 16.0 (16.3) | 13.2 (14.3), laptop s640q50 | 16.7 (19.7) |
| random | **20.0** (25.1) | 18.1 (22.5) | 18.2 (21.7) | 14.9 (18.0) | 12.6 (17.6), laptop s320q50 | 17.2 (22.2) |
| static_good | **30.2** (29.4) | 24.6 (29.5) | 19.7 (19.5) | 20.2 (18.9) | 25.4 (22.9), laptop m640q90 | 25.4 (28.6) |

Paired by repetition, A_full has the highest accuracy-weighted rate in all 8 (scenario, repetition)
pairs, against static_multi and against every fixed policy. On the plain on-time count it is at least
level with static_multi in 7 of 8 pairs; in `static_good`, repetition 1, it scored 29.2 against 29.5.

Other metrics:
- **Availability** (share of time the newest result is at most 300 ms old): 0.999 for A_full in every
  scenario. Fixed remote policies score 0.18-0.83 in the impaired scenarios, because they deliver
  nothing during blackouts. In total blackout, A_full keeps delivering about 10 on-time results/s with
  YOLOv8n@320 on the Pi (about 84 ms per frame).
- **Pi perception power** (compute + radio, measured powers):

  | Scenario | A_full | static_multi |
  |---|---|---|
  | mission | 1.9 W | 3.1 W |
  | mission_mirror | 2.4 W | 3.1 W |
  | random | 3.1 W | 3.1 W |
  | static_good | 0.7 W | 2.4 W |

- **Age of information:** A_full is within 0.84-1.28× of the best fixed policy. It is not the best
  on this metric: in `static_good`, small-payload fixed policies give fresher results (72-75 ms
  against 92 ms), because A_full prefers the slower but more accurate YOLOv8m.

## What the gains come from (ablation)

| Mechanism | Effect, from the table above |
|---|---|
| Variant adaptation on one server (A_single vs best fixed) | +18-21 % in the impaired scenarios; -20 % in `static_good` (repetition 1 was hit by poor Wi-Fi; repetition 2 was level, 25.4 vs 25.6) |
| Using both paths (A_paths vs A_single) | +16-22 % in the impaired scenarios, where the paths fail at different times |
| Onboard engine in parallel (A_full vs A_paths) | +10-15 % in the impaired scenarios, and availability of 0.999 |
| Adaptation on top of parallelism (A_full vs static_multi) | +10-23 % accuracy-weighted at a similar on-time count, with up to 3.4× lower Pi power |

Most of the increase in the raw on-time count comes from parallel servers: static_multi is close to
A_full on that count. Adaptation then lifts accuracy and lowers power: it uses YOLOv8m when the ground
link allows, smaller frames when links degrade, and the onboard engine only when it helps.

## Limitations

- Only 2 repetitions. Shared Wi-Fi varied strongly between runs; for example, A_paths in `static_good`
  scored 10.7 and 28.2. A publication needs at least 5 repetitions and confidence intervals.
- One site, router-mediated Wi-Fi, impairments injected on the Pi's uplink only, and 20 s phases.
- The accuracy-weighted rate uses dataset mAP as the value of each result. It is not task accuracy on
  the live stream, which has no labels.
- The "phase oracle" covers fixed single-server policies only. A_full exceeds it because it uses
  several servers at once, so the oracle is not an upper bound for multi-server policies.
