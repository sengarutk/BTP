# vid_campaign_heat_nov: strategies on the AegisSwarm mesh, VisDrone weights, standard sAP with live forecaster v2

| scenario | strategy | n | sAP | sAP + fc | mAP | P(AoI ≤ 300 ms) | 95th-pct AoI (ms) | deadline-met /s | median latency (ms) | Pi W | Pi °C | throttled | Jetson W | processed at |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mission | v41 | 5 | 0.0552 | **0.1281 ± 0.0046** | 0.219 | 0.854 | 460 | 15.7 | 73 | 3.18 | 70.3 | 0.06 | 5.35 | laptop 54 %, jetson 40 %, onboard 6 % |
| mission | v41cap | 5 | 0.0550 | **0.1267 ± 0.0017** | 0.221 | 0.854 | 567 | 15.4 | 72 | 3.06 | 68.1 | 0.00 | 5.38 | laptop 54 %, jetson 42 %, onboard 4 % |
| mission | v41guard | 5 | 0.0549 | **0.1263 ± 0.0018** | 0.221 | 0.854 | 573 | 15.3 | 72 | 3.06 | 68.3 | 0.00 | 5.37 | laptop 54 %, jetson 42 %, onboard 4 % |
| ALL | v41 | 5 | 0.0552 | **0.1281 ± 0.0046** | 0.219 | 0.854 | 460 | 15.7 | 73 | 3.18 | 70.3 | 0.06 | 5.35 | laptop 54 %, jetson 40 %, onboard 6 % |
| ALL | v41cap | 5 | 0.0550 | **0.1267 ± 0.0017** | 0.221 | 0.854 | 567 | 15.4 | 72 | 3.06 | 68.1 | 0.00 | 5.38 | laptop 54 %, jetson 42 %, onboard 4 % |
| ALL | v41guard | 5 | 0.0549 | **0.1263 ± 0.0018** | 0.221 | 0.854 | 573 | 15.3 | 72 | 3.06 | 68.3 | 0.00 | 5.37 | laptop 54 %, jetson 42 %, onboard 4 % |

## Paired differences (same scenario and repetition)
| comparison | scope | metric | pairs | Δ ± 95 % CI | first ahead | p |
|---|---|---|---|---|---|---|
| v41cap-v41 | mission | sAP_fc | 5 | -0.0014 ± 0.0051 | 2/5 | 0.625 |
| v41cap-v41 | mission | sAP | 5 | -0.0002 ± 0.0031 | 2/5 | 0.875 |
| v41cap-v41 | mission | p_aoi300 | 5 | -0.0003 ± 0.0212 | 2/5 | 1.000 |
| v41cap-v41 | mission | deadline_met_fps | 5 | -0.3361 ± 0.4039 | 0/5 | 0.062 |
| v41cap-v41 | mission | pi_w | 5 | -0.1124 ± 0.0807 | 0/5 | 0.062 |
| v41cap-v41 | mission | pi_temp_c | 5 | -2.1584 ± 1.6575 | 0/5 | 0.062 |
| v41cap-v41 | mission | jetson_w | 5 | +0.0277 ± 0.0650 | 3/5 | 0.375 |
| v41cap-v41 | ALL | sAP_fc | 5 | -0.0014 ± 0.0051 | 2/5 | 0.625 |
| v41cap-v41 | ALL | sAP | 5 | -0.0002 ± 0.0031 | 2/5 | 0.875 |
| v41cap-v41 | ALL | p_aoi300 | 5 | -0.0003 ± 0.0212 | 2/5 | 1.000 |
| v41cap-v41 | ALL | deadline_met_fps | 5 | -0.3361 ± 0.4039 | 0/5 | 0.062 |
| v41cap-v41 | ALL | pi_w | 5 | -0.1124 ± 0.0807 | 0/5 | 0.062 |
| v41cap-v41 | ALL | pi_temp_c | 5 | -2.1584 ± 1.6575 | 0/5 | 0.062 |
| v41cap-v41 | ALL | jetson_w | 5 | +0.0277 ± 0.0650 | 3/5 | 0.375 |
| v41guard-v41 | mission | sAP_fc | 5 | -0.0017 ± 0.0031 | 1/5 | 0.188 |
| v41guard-v41 | mission | sAP | 5 | -0.0004 ± 0.0015 | 1/5 | 0.562 |
| v41guard-v41 | mission | p_aoi300 | 5 | -0.0001 ± 0.0188 | 1/5 | 1.000 |
| v41guard-v41 | mission | deadline_met_fps | 5 | -0.3554 ± 0.1578 | 0/5 | 0.062 |
| v41guard-v41 | mission | pi_w | 5 | -0.1173 ± 0.0796 | 0/5 | 0.062 |
| v41guard-v41 | mission | pi_temp_c | 5 | -1.9680 ± 1.4905 | 0/5 | 0.062 |
| v41guard-v41 | mission | jetson_w | 5 | +0.0179 ± 0.0478 | 3/5 | 0.375 |
| v41guard-v41 | ALL | sAP_fc | 5 | -0.0017 ± 0.0031 | 1/5 | 0.188 |
| v41guard-v41 | ALL | sAP | 5 | -0.0004 ± 0.0015 | 1/5 | 0.562 |
| v41guard-v41 | ALL | p_aoi300 | 5 | -0.0001 ± 0.0188 | 1/5 | 1.000 |
| v41guard-v41 | ALL | deadline_met_fps | 5 | -0.3554 ± 0.1578 | 0/5 | 0.062 |
| v41guard-v41 | ALL | pi_w | 5 | -0.1173 ± 0.0796 | 0/5 | 0.062 |
| v41guard-v41 | ALL | pi_temp_c | 5 | -1.9680 ± 1.4905 | 0/5 | 0.062 |
| v41guard-v41 | ALL | jetson_w | 5 | +0.0179 ± 0.0478 | 3/5 | 0.375 |
