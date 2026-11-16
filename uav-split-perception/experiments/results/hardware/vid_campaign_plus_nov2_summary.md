# vid_campaign_plus_nov2: strategies on the AegisSwarm mesh, VisDrone weights, standard sAP with live forecaster v2

| scenario | strategy | n | sAP | sAP + fc | mAP | P(AoI ≤ 300 ms) | 95th-pct AoI (ms) | deadline-met /s | median latency (ms) | Pi W | Pi °C | throttled | Jetson W | processed at |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mission | v41 | 3 | 0.0595 | **0.1312 ± 0.0162** | 0.217 | 0.906 | 367 | 15.8 | 73 | 3.32 | 72.3 | 0.05 | 5.38 | laptop 49 %, jetson 42 %, onboard 9 % |
| mission | v41plus | 3 | 0.0610 | **0.1342 ± 0.0061** | 0.229 | 0.890 | 500 | 15.7 | 78 | 3.39 | 71.8 | 0.00 | 5.35 | laptop 50 %, jetson 40 %, onboard 10 % |
| random | v41 | 3 | 0.0434 | **0.1088 ± 0.0584** | 0.198 | 0.940 | 333 | 15.3 | 87 | 3.08 | 69.5 | 0.01 | 5.23 | laptop 52 %, jetson 42 %, onboard 7 % |
| random | v41plus | 3 | 0.0454 | **0.1133 ± 0.0598** | 0.204 | 0.947 | 324 | 15.7 | 90 | 3.38 | 74.2 | 0.00 | 5.21 | laptop 49 %, jetson 41 %, onboard 10 % |
| ALL | v41 | 6 | 0.0515 | **0.1200 ± 0.0207** | 0.208 | 0.923 | 350 | 15.5 | 80 | 3.20 | 70.9 | 0.03 | 5.31 | laptop 50 %, jetson 42 %, onboard 8 % |
| ALL | v41plus | 6 | 0.0532 | **0.1238 ± 0.0201** | 0.216 | 0.919 | 412 | 15.7 | 84 | 3.38 | 73.0 | 0.00 | 5.28 | laptop 50 %, jetson 40 %, onboard 10 % |

## Paired differences (same scenario and repetition)
| comparison | scope | metric | pairs | Δ ± 95 % CI | first ahead | p |
|---|---|---|---|---|---|---|
| v41plus-v41 | mission | sAP_fc | 2 | -0.0012 ± 0.0496 | 1/2 | 1.000 |
| v41plus-v41 | mission | sAP | 2 | +0.0007 ± 0.0341 | 1/2 | 1.000 |
| v41plus-v41 | mission | p_aoi300 | 2 | -0.0352 ± 0.0263 | 0/2 | 0.500 |
| v41plus-v41 | mission | deadline_met_fps | 2 | -0.0250 ± 5.5606 | 1/2 | 1.000 |
| v41plus-v41 | mission | pi_w | 2 | +0.0323 ± 0.5564 | 1/2 | 1.000 |
| v41plus-v41 | mission | pi_temp_c | 2 | +1.0577 ± 2.3158 | 2/2 | 0.500 |
| v41plus-v41 | mission | jetson_w | 2 | -0.0352 ± 0.3669 | 0/2 | 0.500 |
| v41plus-v41 | random | sAP_fc | 3 | +0.0045 ± 0.0089 | 3/3 | 0.250 |
| v41plus-v41 | random | sAP | 3 | +0.0020 ± 0.0036 | 3/3 | 0.250 |
| v41plus-v41 | random | p_aoi300 | 3 | +0.0064 ± 0.0077 | 3/3 | 0.250 |
| v41plus-v41 | random | deadline_met_fps | 3 | +0.3403 ± 1.9640 | 1/3 | 1.000 |
| v41plus-v41 | random | pi_w | 3 | +0.3030 ± 0.6206 | 3/3 | 0.250 |
| v41plus-v41 | random | pi_temp_c | 3 | +4.7754 ± 6.2658 | 3/3 | 0.250 |
| v41plus-v41 | random | jetson_w | 3 | -0.0185 ± 0.0747 | 0/3 | 0.250 |
| v41plus-v41 | ALL | sAP_fc | 5 | +0.0022 ± 0.0061 | 4/5 | 0.312 |
| v41plus-v41 | ALL | sAP | 5 | +0.0015 ± 0.0028 | 4/5 | 0.188 |
| v41plus-v41 | ALL | p_aoi300 | 5 | -0.0102 ± 0.0286 | 3/5 | 0.500 |
| v41plus-v41 | ALL | deadline_met_fps | 5 | +0.1942 ± 0.8328 | 2/5 | 0.750 |
| v41plus-v41 | ALL | pi_w | 5 | +0.1947 ± 0.2894 | 4/5 | 0.125 |
| v41plus-v41 | ALL | pi_temp_c | 5 | +3.2883 ± 3.3701 | 5/5 | 0.062 |
| v41plus-v41 | ALL | jetson_w | 5 | -0.0252 ± 0.0384 | 0/5 | 0.062 |
