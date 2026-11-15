# vid_campaign_heat_nov2: strategies on the AegisSwarm mesh, VisDrone weights, standard sAP with live forecaster v2

| scenario | strategy | n | sAP | sAP + fc | mAP | P(AoI ≤ 300 ms) | 95th-pct AoI (ms) | deadline-met /s | median latency (ms) | Pi W | Pi °C | throttled | Jetson W | processed at |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mission | v41guard765 | 3 | 0.0518 | **0.1228 ± 0.0024** | 0.221 | 0.841 | 700 | 14.9 | 76 | 2.99 | 69.5 | 0.00 | 5.38 | laptop 53 %, jetson 43 %, onboard 4 % |
| ALL | v41guard765 | 3 | 0.0518 | **0.1228 ± 0.0024** | 0.221 | 0.841 | 700 | 14.9 | 76 | 2.99 | 69.5 | 0.00 | 5.38 | laptop 53 %, jetson 43 %, onboard 4 % |

## Paired differences (same scenario and repetition)
| comparison | scope | metric | pairs | Δ ± 95 % CI | first ahead | p |
|---|---|---|---|---|---|---|
