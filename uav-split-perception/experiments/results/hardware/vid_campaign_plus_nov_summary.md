# vid_campaign_plus_nov: strategies on the AegisSwarm mesh, VisDrone weights, standard sAP with live forecaster v2

| scenario | strategy | n | sAP | sAP + fc | mAP | P(AoI ≤ 300 ms) | 95th-pct AoI (ms) | deadline-met /s | median latency (ms) | Pi W | Pi °C | throttled | Jetson W | processed at |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mission | v41 | 4 | 0.0626 | **0.1354 ± 0.0152** | 0.220 | 0.907 | 367 | 15.6 | 71 | 3.35 | 69.8 | 0.02 | 5.41 | laptop 47 %, jetson 45 %, onboard 9 % |
| mission | v41plus | 4 | 0.0649 | **0.1357 ± 0.0021** | 0.226 | 0.896 | 408 | 15.6 | 72 | 3.10 | 68.2 | 0.00 | 5.38 | laptop 52 %, jetson 41 %, onboard 7 % |
| random | v41 | 4 | 0.0494 | **0.1185 ± 0.0413** | 0.204 | 0.956 | 300 | 15.9 | 82 | 2.95 | 66.0 | 0.00 | 5.26 | laptop 51 %, jetson 43 %, onboard 5 % |
| random | v41plus | 4 | 0.0504 | **0.1213 ± 0.0350** | 0.207 | 0.951 | 308 | 16.1 | 80 | 2.90 | 65.9 | 0.00 | 5.26 | laptop 53 %, jetson 43 %, onboard 5 % |
| ALL | v41 | 8 | 0.0560 | **0.1270 ± 0.0169** | 0.212 | 0.931 | 333 | 15.8 | 77 | 3.15 | 67.9 | 0.01 | 5.34 | laptop 49 %, jetson 44 %, onboard 7 % |
| ALL | v41plus | 8 | 0.0576 | **0.1285 ± 0.0136** | 0.216 | 0.924 | 358 | 15.9 | 76 | 3.00 | 67.0 | 0.00 | 5.32 | laptop 52 %, jetson 42 %, onboard 6 % |

## Paired differences (same scenario and repetition)
| comparison | scope | metric | pairs | Δ ± 95 % CI | first ahead | p |
|---|---|---|---|---|---|---|
| v41plus-v41 | mission | sAP_fc | 4 | +0.0003 ± 0.0165 | 2/4 | 1.000 |
| v41plus-v41 | mission | sAP | 4 | +0.0023 ± 0.0123 | 2/4 | 0.625 |
| v41plus-v41 | mission | p_aoi300 | 4 | -0.0104 ± 0.0114 | 0/4 | 0.125 |
| v41plus-v41 | mission | deadline_met_fps | 4 | +0.0240 ± 0.6450 | 2/4 | 1.000 |
| v41plus-v41 | mission | pi_w | 4 | -0.2467 ± 0.1259 | 0/4 | 0.125 |
| v41plus-v41 | mission | pi_temp_c | 4 | -1.6262 ± 0.6952 | 0/4 | 0.125 |
| v41plus-v41 | mission | jetson_w | 4 | -0.0279 ± 0.0846 | 2/4 | 0.500 |
| v41plus-v41 | random | sAP_fc | 4 | +0.0027 ± 0.0116 | 2/4 | 0.625 |
| v41plus-v41 | random | sAP | 4 | +0.0010 ± 0.0050 | 3/4 | 0.625 |
| v41plus-v41 | random | p_aoi300 | 4 | -0.0047 ± 0.0269 | 3/4 | 1.000 |
| v41plus-v41 | random | deadline_met_fps | 4 | +0.2427 ± 0.5109 | 4/4 | 0.125 |
| v41plus-v41 | random | pi_w | 4 | -0.0501 ± 0.0738 | 0/4 | 0.125 |
| v41plus-v41 | random | pi_temp_c | 4 | -0.0582 ± 1.5909 | 2/4 | 1.000 |
| v41plus-v41 | random | jetson_w | 4 | -0.0057 ± 0.0589 | 3/4 | 1.000 |
| v41plus-v41 | ALL | sAP_fc | 8 | +0.0015 ± 0.0070 | 4/8 | 0.617 |
| v41plus-v41 | ALL | sAP | 8 | +0.0016 ± 0.0046 | 5/8 | 0.414 |
| v41plus-v41 | ALL | p_aoi300 | 8 | -0.0076 ± 0.0103 | 3/8 | 0.125 |
| v41plus-v41 | ALL | deadline_met_fps | 8 | +0.1333 ± 0.2990 | 6/8 | 0.320 |
| v41plus-v41 | ALL | pi_w | 8 | -0.1484 ± 0.1010 | 0/8 | 0.008 |
| v41plus-v41 | ALL | pi_temp_c | 8 | -0.8422 ± 0.9192 | 2/8 | 0.078 |
| v41plus-v41 | ALL | jetson_w | 8 | -0.0168 ± 0.0368 | 5/8 | 0.297 |
