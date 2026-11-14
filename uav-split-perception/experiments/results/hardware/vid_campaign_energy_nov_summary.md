# vid_campaign_energy_nov: strategies on the AegisSwarm mesh, VisDrone weights, standard sAP with live forecaster v2

| scenario | strategy | n | sAP | sAP + fc | mAP | P(AoI ≤ 300 ms) | 95th-pct AoI (ms) | deadline-met /s | median latency (ms) | Pi W | Pi °C | throttled | Jetson W | processed at |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| static_good | v41 | 4 | 0.1054 | **0.1922 ± 0.0111** | 0.232 | 0.997 | 125 | 25.8 | 52 | 2.82 | 61.9 | 0.00 | 4.96 | laptop 79 %, jetson 20 %, onboard 1 % |
| static_good | freshonly | 4 | 0.0984 | **0.1880 ± 0.0083** | 0.227 | 1.000 | 133 | 27.0 | 59 | 4.71 | 79.4 | 0.03 | 5.08 | laptop 70 %, jetson 22 %, onboard 8 % |
| static_good | v41b36 | 4 | 0.0961 | **0.1837 ± 0.0285** | 0.228 | 0.999 | 150 | 25.7 | 59 | 3.58 | 70.3 | 0.00 | 5.02 | laptop 73 %, jetson 22 %, onboard 5 % |
| ALL | v41 | 4 | 0.1054 | **0.1922 ± 0.0111** | 0.232 | 0.997 | 125 | 25.8 | 52 | 2.82 | 61.9 | 0.00 | 4.96 | laptop 79 %, jetson 20 %, onboard 1 % |
| ALL | freshonly | 4 | 0.0984 | **0.1880 ± 0.0083** | 0.227 | 1.000 | 133 | 27.0 | 59 | 4.71 | 79.4 | 0.03 | 5.08 | laptop 70 %, jetson 22 %, onboard 8 % |
| ALL | v41b36 | 4 | 0.0961 | **0.1837 ± 0.0285** | 0.228 | 0.999 | 150 | 25.7 | 59 | 3.58 | 70.3 | 0.00 | 5.02 | laptop 73 %, jetson 22 %, onboard 5 % |

## Paired differences (same scenario and repetition)
| comparison | scope | metric | pairs | Δ ± 95 % CI | first ahead | p |
|---|---|---|---|---|---|---|
| freshonly-v41 | static_good | sAP_fc | 4 | -0.0041 ± 0.0063 | 0/4 | 0.125 |
| freshonly-v41 | static_good | sAP | 4 | -0.0070 ± 0.0091 | 0/4 | 0.125 |
| freshonly-v41 | static_good | p_aoi300 | 4 | +0.0032 ± 0.0105 | 1/4 | 1.000 |
| freshonly-v41 | static_good | deadline_met_fps | 4 | +1.2312 ± 0.9787 | 4/4 | 0.125 |
| freshonly-v41 | static_good | pi_w | 4 | +1.8892 ± 0.1990 | 4/4 | 0.125 |
| freshonly-v41 | static_good | pi_temp_c | 4 | +17.4544 ± 3.8711 | 4/4 | 0.125 |
| freshonly-v41 | static_good | jetson_w | 4 | +0.1122 ± 0.1100 | 4/4 | 0.125 |
| freshonly-v41 | ALL | sAP_fc | 4 | -0.0041 ± 0.0063 | 0/4 | 0.125 |
| freshonly-v41 | ALL | sAP | 4 | -0.0070 ± 0.0091 | 0/4 | 0.125 |
| freshonly-v41 | ALL | p_aoi300 | 4 | +0.0032 ± 0.0105 | 1/4 | 1.000 |
| freshonly-v41 | ALL | deadline_met_fps | 4 | +1.2312 ± 0.9787 | 4/4 | 0.125 |
| freshonly-v41 | ALL | pi_w | 4 | +1.8892 ± 0.1990 | 4/4 | 0.125 |
| freshonly-v41 | ALL | pi_temp_c | 4 | +17.4544 ± 3.8711 | 4/4 | 0.125 |
| freshonly-v41 | ALL | jetson_w | 4 | +0.1122 ± 0.1100 | 4/4 | 0.125 |
| v41b36-v41 | static_good | sAP_fc | 4 | -0.0085 ± 0.0177 | 0/4 | 0.125 |
| v41b36-v41 | static_good | sAP | 4 | -0.0093 ± 0.0153 | 0/4 | 0.125 |
| v41b36-v41 | static_good | p_aoi300 | 4 | +0.0027 ± 0.0086 | 1/4 | 1.000 |
| v41b36-v41 | static_good | deadline_met_fps | 4 | -0.1326 ± 2.8631 | 3/4 | 1.000 |
| v41b36-v41 | static_good | pi_w | 4 | +0.7598 ± 0.0623 | 4/4 | 0.125 |
| v41b36-v41 | static_good | pi_temp_c | 4 | +8.3427 ± 4.3080 | 4/4 | 0.125 |
| v41b36-v41 | static_good | jetson_w | 4 | +0.0581 ± 0.1082 | 4/4 | 0.125 |
| v41b36-v41 | ALL | sAP_fc | 4 | -0.0085 ± 0.0177 | 0/4 | 0.125 |
| v41b36-v41 | ALL | sAP | 4 | -0.0093 ± 0.0153 | 0/4 | 0.125 |
| v41b36-v41 | ALL | p_aoi300 | 4 | +0.0027 ± 0.0086 | 1/4 | 1.000 |
| v41b36-v41 | ALL | deadline_met_fps | 4 | -0.1326 ± 2.8631 | 3/4 | 1.000 |
| v41b36-v41 | ALL | pi_w | 4 | +0.7598 ± 0.0623 | 4/4 | 0.125 |
| v41b36-v41 | ALL | pi_temp_c | 4 | +8.3427 ± 4.3080 | 4/4 | 0.125 |
| v41b36-v41 | ALL | jetson_w | 4 | +0.0581 ± 0.1082 | 4/4 | 0.125 |
