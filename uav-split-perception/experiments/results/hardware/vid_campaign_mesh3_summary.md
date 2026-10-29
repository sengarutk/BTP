# vid_campaign_mesh3: strategies on the AegisSwarm mesh, VisDrone weights, standard sAP with live forecaster v2

| scenario | strategy | n | sAP | sAP + fc | mAP | P(AoI ≤ 300 ms) | 95th-pct AoI (ms) | deadline-met /s | median latency (ms) | Pi W | Pi °C | throttled | Jetson W | processed at |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mesh_mission | v41 | 3 | 0.0914 | **0.1842 ± 0.0024** | 0.240 | 0.997 | 167 | 20.5 | 53 | 2.82 | 68.3 | 0.00 | 5.30 | laptop 66 %, jetson 33 %, onboard 1 % |
| mesh_mission | v41e12 | 3 | 0.0939 | **0.1822 ± 0.0051** | 0.233 | 0.996 | 167 | 22.1 | 51 | 2.82 | 68.8 | 0.00 | 5.30 | laptop 65 %, jetson 34 %, onboard 2 % |
| multihop | v41 | 3 | 0.0436 | **0.1287 ± 0.0072** | 0.220 | 0.992 | 256 | 10.9 | 114 | 2.82 | 68.8 | 0.00 | 5.65 | jetson 72 %, laptop 23 %, onboard 4 % |
| multihop | v41e12 | 3 | 0.0448 | **0.1237 ± 0.0081** | 0.210 | 0.991 | 244 | 11.6 | 103 | 2.82 | 69.2 | 0.00 | 5.41 | jetson 69 %, laptop 26 %, onboard 5 % |
| static_good | v41 | 3 | 0.1107 | **0.2011 ± 0.0046** | 0.241 | 1.000 | 111 | 26.1 | 49 | 2.83 | 67.2 | 0.00 | 5.03 | laptop 79 %, jetson 20 %, onboard 1 % |
| static_good | v41e12 | 3 | 0.1111 | **0.2012 ± 0.0051** | 0.240 | 1.000 | 111 | 26.1 | 49 | 2.83 | 67.5 | 0.00 | 5.05 | laptop 79 %, jetson 20 %, onboard 1 % |
| ALL | v41 | 9 | 0.0819 | **0.1713 ± 0.0253** | 0.234 | 0.996 | 178 | 19.2 | 72 | 2.82 | 68.1 | 0.00 | 5.32 | laptop 63 %, jetson 36 %, onboard 2 % |
| ALL | v41e12 | 9 | 0.0832 | **0.1690 ± 0.0270** | 0.228 | 0.996 | 174 | 19.9 | 68 | 2.82 | 68.5 | 0.00 | 5.25 | laptop 62 %, jetson 36 %, onboard 2 % |

## Paired differences (same scenario and repetition)
| comparison | scope | metric | pairs | Δ ± 95 % CI | first ahead | p |
|---|---|---|---|---|---|---|
| v41e12-v41 | mesh_mission | sAP_fc | 3 | -0.0020 ± 0.0037 | 0/3 | 0.250 |
| v41e12-v41 | mesh_mission | sAP | 3 | +0.0025 ± 0.0026 | 3/3 | 0.250 |
| v41e12-v41 | mesh_mission | p_aoi300 | 3 | -0.0005 ± 0.0021 | 1/3 | 0.500 |
| v41e12-v41 | mesh_mission | deadline_met_fps | 3 | +1.5333 ± 0.6745 | 3/3 | 0.250 |
| v41e12-v41 | mesh_mission | pi_w | 3 | +0.0054 ± 0.0310 | 2/3 | 0.500 |
| v41e12-v41 | mesh_mission | pi_temp_c | 3 | +0.5151 ± 0.2289 | 3/3 | 0.250 |
| v41e12-v41 | mesh_mission | jetson_w | 3 | -0.0006 ± 0.1034 | 2/3 | 1.000 |
| v41e12-v41 | multihop | sAP_fc | 3 | -0.0049 ± 0.0080 | 0/3 | 0.250 |
| v41e12-v41 | multihop | sAP | 3 | +0.0012 ± 0.0031 | 3/3 | 0.250 |
| v41e12-v41 | multihop | p_aoi300 | 3 | -0.0011 ± 0.0048 | 1/3 | 0.500 |
| v41e12-v41 | multihop | deadline_met_fps | 3 | +0.6764 ± 0.3107 | 3/3 | 0.250 |
| v41e12-v41 | multihop | pi_w | 3 | -0.0024 ± 0.0378 | 2/3 | 1.000 |
| v41e12-v41 | multihop | pi_temp_c | 3 | +0.4042 ± 0.4978 | 3/3 | 0.250 |
| v41e12-v41 | multihop | jetson_w | 3 | -0.2335 ± 0.0336 | 0/3 | 0.250 |
| v41e12-v41 | static_good | sAP_fc | 3 | +0.0000 ± 0.0049 | 1/3 | 1.000 |
| v41e12-v41 | static_good | sAP | 3 | +0.0004 ± 0.0051 | 2/3 | 0.750 |
| v41e12-v41 | static_good | p_aoi300 | 3 | +0.0000 ± 0.0000 | 0/3 | 1.000 |
| v41e12-v41 | static_good | deadline_met_fps | 3 | +0.0042 ± 0.3503 | 1/3 | 1.000 |
| v41e12-v41 | static_good | pi_w | 3 | -0.0044 ± 0.0714 | 1/3 | 0.750 |
| v41e12-v41 | static_good | pi_temp_c | 3 | +0.2692 ± 4.7847 | 1/3 | 1.000 |
| v41e12-v41 | static_good | jetson_w | 3 | +0.0142 ± 0.1281 | 1/3 | 1.000 |
| v41e12-v41 | ALL | sAP_fc | 9 | -0.0023 ± 0.0023 | 1/9 | 0.043 |
| v41e12-v41 | ALL | sAP | 9 | +0.0014 ± 0.0012 | 8/9 | 0.035 |
| v41e12-v41 | ALL | p_aoi300 | 9 | -0.0005 ± 0.0009 | 2/9 | 0.219 |
| v41e12-v41 | ALL | deadline_met_fps | 9 | +0.7380 ± 0.5267 | 7/9 | 0.016 |
| v41e12-v41 | ALL | pi_w | 9 | -0.0004 ± 0.0139 | 5/9 | 0.945 |
| v41e12-v41 | ALL | pi_temp_c | 9 | +0.3962 ± 0.7514 | 7/9 | 0.270 |
| v41e12-v41 | ALL | jetson_w | 9 | -0.0733 ± 0.0963 | 3/9 | 0.160 |

## mesh_mission phases (sAP + fc)
| strategy | good | ground_congested | camera_out_of_range | edge_uplink_cut | edge_link_slow | recovered |
|---|---|---|---|---|---|---|
| v41 | 0.265 | 0.084 | 0.170 | 0.180 | 0.185 | 0.234 |
| v41e12 | 0.266 | 0.085 | 0.161 | 0.176 | 0.187 | 0.234 |
