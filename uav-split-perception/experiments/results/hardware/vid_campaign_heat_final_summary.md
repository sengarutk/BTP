# vid_campaign_heat_final: strategies on the AegisSwarm mesh, VisDrone weights, standard sAP with live forecaster v2

| scenario | strategy | n | sAP | sAP + fc | mAP | P(AoI ≤ 300 ms) | 95th-pct AoI (ms) | deadline-met /s | median latency (ms) | Pi W | Pi °C | throttled | Jetson W | processed at |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mission | v41final | 3 | 0.0541 | **0.1247 ± 0.0031** | 0.221 | 0.852 | 622 | 15.5 | 71 | 3.00 | 70.0 | 0.00 | 5.40 | laptop 54 %, jetson 42 %, onboard 4 % |
| ALL | v41final | 3 | 0.0541 | **0.1247 ± 0.0031** | 0.221 | 0.852 | 622 | 15.5 | 71 | 3.00 | 70.0 | 0.00 | 5.40 | laptop 54 %, jetson 42 %, onboard 4 % |

## Paired differences (same scenario and repetition)
| comparison | scope | metric | pairs | Δ ± 95 % CI | first ahead | p |
|---|---|---|---|---|---|---|
