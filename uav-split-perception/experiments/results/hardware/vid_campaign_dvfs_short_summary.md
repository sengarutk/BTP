# vid_campaign_dvfs_short: strategies on the AegisSwarm mesh, VisDrone weights, standard sAP with live forecaster v2

| scenario | strategy | n | sAP | sAP + fc | mAP | P(AoI ≤ 300 ms) | 95th-pct AoI (ms) | deadline-met /s | median latency (ms) | Pi W | Pi °C | throttled | Jetson W | processed at |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mission | v41final | 5 | 0.0620 | **0.1346 ± 0.0072** | 0.226 | 0.897 | 413 | 15.5 | 75 | 3.05 | 68.9 | 0.00 | 5.35 | laptop 50 %, jetson 42 %, onboard 8 % |
| mission | v41dvfs | 5 | 0.0586 | **0.1299 ± 0.0071** | 0.223 | 0.892 | 433 | 15.4 | 76 | 3.07 | 69.4 | 0.00 | 5.35 | laptop 48 %, jetson 42 %, onboard 10 % |
| ALL | v41final | 5 | 0.0620 | **0.1346 ± 0.0072** | 0.226 | 0.897 | 413 | 15.5 | 75 | 3.05 | 68.9 | 0.00 | 5.35 | laptop 50 %, jetson 42 %, onboard 8 % |
| ALL | v41dvfs | 5 | 0.0586 | **0.1299 ± 0.0071** | 0.223 | 0.892 | 433 | 15.4 | 76 | 3.07 | 69.4 | 0.00 | 5.35 | laptop 48 %, jetson 42 %, onboard 10 % |

## Paired differences (same scenario and repetition)
| comparison | scope | metric | pairs | Δ ± 95 % CI | first ahead | p |
|---|---|---|---|---|---|---|
