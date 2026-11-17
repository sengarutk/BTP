# vid_campaign_fps_nov: strategies on the AegisSwarm mesh, VisDrone weights, standard sAP with live forecaster v2

| scenario | strategy | n | sAP | sAP + fc | mAP | P(AoI ≤ 300 ms) | 95th-pct AoI (ms) | deadline-met /s | median latency (ms) | Pi W | Pi °C | throttled | Jetson W | processed at |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| static_good | v41_f15 | 3 | — | — | — | — | — | 14.9 | 54 | 2.13 | 57.0 | 0.00 | 4.35 | laptop 95 %, jetson 5 %, onboard 0 % |
| static_good | v41_f30 | 3 | 0.1071 | **0.1966 ± 0.0180** | 0.239 | 0.996 | 133 | 25.6 | 50 | 2.86 | 63.6 | 0.00 | 4.97 | laptop 78 %, jetson 20 %, onboard 2 % |
| static_good | v41_f60 | 3 | — | — | — | — | — | 31.0 | 61 | 3.18 | 66.7 | 0.00 | 5.73 | laptop 68 %, jetson 32 %, onboard 0 % |
| static_good | v41ea_f30 | 3 | 0.1053 | **0.1959 ± 0.0230** | 0.238 | 0.994 | 144 | 28.3 | 55 | 2.84 | 64.2 | 0.00 | 5.24 | laptop 75 %, jetson 24 %, onboard 1 % |
| ALL | v41_f15 | 3 | — | — | — | — | — | 14.9 | 54 | 2.13 | 57.0 | 0.00 | 4.35 | laptop 95 %, jetson 5 %, onboard 0 % |
| ALL | v41_f30 | 3 | 0.1071 | **0.1966 ± 0.0180** | 0.239 | 0.996 | 133 | 25.6 | 50 | 2.86 | 63.6 | 0.00 | 4.97 | laptop 78 %, jetson 20 %, onboard 2 % |
| ALL | v41_f60 | 3 | — | — | — | — | — | 31.0 | 61 | 3.18 | 66.7 | 0.00 | 5.73 | laptop 68 %, jetson 32 %, onboard 0 % |
| ALL | v41ea_f30 | 3 | 0.1053 | **0.1959 ± 0.0230** | 0.238 | 0.994 | 144 | 28.3 | 55 | 2.84 | 64.2 | 0.00 | 5.24 | laptop 75 %, jetson 24 %, onboard 1 % |

## Paired differences (same scenario and repetition)
| comparison | scope | metric | pairs | Δ ± 95 % CI | first ahead | p |
|---|---|---|---|---|---|---|
