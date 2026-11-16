# vid_campaign_dvfs_heat: strategies on the AegisSwarm mesh, VisDrone weights, standard sAP with live forecaster v2

| scenario | strategy | n | sAP | sAP + fc | mAP | P(AoI ≤ 300 ms) | 95th-pct AoI (ms) | deadline-met /s | median latency (ms) | Pi W | Pi °C | throttled | Jetson W | processed at |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mission | v41final | 3 | 0.0529 | **0.1238 ± 0.0038** | 0.221 | 0.844 | 589 | 15.3 | 72 | 3.05 | 69.8 | 0.00 | 5.35 | laptop 54 %, jetson 41 %, onboard 5 % |
| mission | v41dvfs | 3 | 0.0544 | **0.1260 ± 0.0016** | 0.220 | 0.857 | 578 | 15.6 | 73 | 3.04 | 69.6 | 0.00 | 5.38 | laptop 53 %, jetson 42 %, onboard 5 % |
| ALL | v41final | 3 | 0.0529 | **0.1238 ± 0.0038** | 0.221 | 0.844 | 589 | 15.3 | 72 | 3.05 | 69.8 | 0.00 | 5.35 | laptop 54 %, jetson 41 %, onboard 5 % |
| ALL | v41dvfs | 3 | 0.0544 | **0.1260 ± 0.0016** | 0.220 | 0.857 | 578 | 15.6 | 73 | 3.04 | 69.6 | 0.00 | 5.38 | laptop 53 %, jetson 42 %, onboard 5 % |

## Paired differences (same scenario and repetition)
| comparison | scope | metric | pairs | Δ ± 95 % CI | first ahead | p |
|---|---|---|---|---|---|---|
