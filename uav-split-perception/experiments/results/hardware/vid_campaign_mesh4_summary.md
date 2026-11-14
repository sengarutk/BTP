# vid_campaign_mesh4: strategies on the AegisSwarm mesh, VisDrone weights, standard sAP with live forecaster v2

| scenario | strategy | n | sAP | sAP + fc | mAP | P(AoI ≤ 300 ms) | 95th-pct AoI (ms) | deadline-met /s | median latency (ms) | Pi W | Pi °C | throttled | Jetson W | processed at |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mesh_mission | v41 | 2 | 0.0900 | **0.1826 ± 0.0037** | 0.237 | 0.999 | 167 | 20.5 | 56 | 2.81 | 61.4 | 0.00 | 5.29 | laptop 63 %, jetson 35 %, onboard 2 % |
| mesh_mission | accumo | 2 | 0.0847 | **0.1785 ± 0.0225** | 0.240 | 0.987 | 167 | 17.0 | 50 | 2.37 | 57.5 | 0.00 | 5.80 | laptop 71 %, jetson 29 % |
| mesh_mission | leaf | 2 | 0.0919 | **0.1836 ± 0.0118** | 0.239 | 0.997 | 167 | 20.3 | 54 | 2.37 | 57.0 | 0.00 | 5.29 | laptop 65 %, jetson 35 %, onboard 0 % |
| multihop | v41 | 2 | 0.0441 | **0.1291 ± 0.0171** | 0.218 | 0.992 | 267 | 11.5 | 111 | 2.81 | 61.0 | 0.00 | 5.62 | jetson 71 %, laptop 24 %, onboard 5 % |
| multihop | accumo | 2 | 0.0470 | **0.1384 ± 0.1394** | 0.232 | 0.928 | 383 | 9.7 | 88 | 2.23 | 55.3 | 0.00 | 5.71 | jetson 99 %, onboard 0 %, laptop 0 % |
| multihop | leaf | 2 | 0.0450 | **0.1320 ± 0.1101** | 0.224 | 0.960 | 300 | 11.0 | 114 | 2.14 | 55.1 | 0.00 | 5.60 | jetson 75 %, laptop 25 %, onboard 0 % |
| static_good | v41 | 2 | 0.1125 | **0.2019 ± 0.0077** | 0.239 | 1.000 | 100 | 26.4 | 49 | 2.81 | 59.5 | 0.00 | 4.94 | laptop 79 %, jetson 19 %, onboard 1 % |
| static_good | accumo | 2 | 0.1083 | **0.2000 ± 0.0004** | 0.240 | 1.000 | 100 | 21.2 | 42 | 2.54 | 57.3 | 0.00 | 4.09 | laptop 100 %, jetson 0 % |
| static_good | leaf | 2 | 0.1104 | **0.2004 ± 0.0471** | 0.240 | 1.000 | 117 | 25.7 | 50 | 2.49 | 57.4 | 0.00 | 5.03 | laptop 78 %, jetson 22 %, onboard 0 % |
| ALL | v41 | 6 | 0.0822 | **0.1712 ± 0.0354** | 0.232 | 0.997 | 178 | 19.5 | 72 | 2.81 | 60.6 | 0.00 | 5.28 | laptop 62 %, jetson 36 %, onboard 3 % |
| ALL | accumo | 6 | 0.0800 | **0.1723 ± 0.0302** | 0.237 | 0.972 | 217 | 16.0 | 60 | 2.38 | 56.7 | 0.00 | 5.42 | laptop 69 %, jetson 30 %, onboard 0 % |
| ALL | leaf | 6 | 0.0825 | **0.1720 ± 0.0340** | 0.234 | 0.985 | 194 | 19.0 | 73 | 2.33 | 56.5 | 0.00 | 5.30 | laptop 62 %, jetson 38 %, onboard 0 % |

## Paired differences (same scenario and repetition)
| comparison | scope | metric | pairs | Δ ± 95 % CI | first ahead | p |
|---|---|---|---|---|---|---|
| accumo-v41 | mesh_mission | sAP_fc | 2 | -0.0042 ± 0.0188 | 0/2 | 0.500 |
| accumo-v41 | mesh_mission | sAP | 2 | -0.0053 ± 0.0234 | 0/2 | 0.500 |
| accumo-v41 | mesh_mission | p_aoi300 | 2 | -0.0126 ± 0.0388 | 0/2 | 0.500 |
| accumo-v41 | mesh_mission | deadline_met_fps | 2 | -3.5312 ± 5.7989 | 0/2 | 0.500 |
| accumo-v41 | mesh_mission | pi_w | 2 | -0.4426 ± 0.1861 | 0/2 | 0.500 |
| accumo-v41 | mesh_mission | pi_temp_c | 2 | -3.9814 ± 5.6738 | 0/2 | 0.500 |
| accumo-v41 | mesh_mission | jetson_w | 2 | +0.5057 ± 0.3030 | 2/2 | 0.500 |
| accumo-v41 | multihop | sAP_fc | 2 | +0.0093 ± 0.1224 | 1/2 | 1.000 |
| accumo-v41 | multihop | sAP | 2 | +0.0029 ± 0.0867 | 1/2 | 1.000 |
| accumo-v41 | multihop | p_aoi300 | 2 | -0.0639 ± 0.8242 | 1/2 | 1.000 |
| accumo-v41 | multihop | deadline_met_fps | 2 | -1.7979 ± 12.4187 | 0/2 | 0.500 |
| accumo-v41 | multihop | pi_w | 2 | -0.5791 ± 0.2551 | 0/2 | 0.500 |
| accumo-v41 | multihop | pi_temp_c | 2 | -5.7052 ± 3.5282 | 0/2 | 0.500 |
| accumo-v41 | multihop | jetson_w | 2 | +0.0872 ± 1.4127 | 1/2 | 1.000 |
| accumo-v41 | static_good | sAP_fc | 2 | -0.0020 ± 0.0073 | 0/2 | 0.500 |
| accumo-v41 | static_good | sAP | 2 | -0.0042 ± 0.0139 | 0/2 | 0.500 |
| accumo-v41 | static_good | p_aoi300 | 2 | +0.0000 ± 0.0000 | 0/2 | 1.000 |
| accumo-v41 | static_good | deadline_met_fps | 2 | -5.1354 ± 2.1448 | 0/2 | 0.500 |
| accumo-v41 | static_good | pi_w | 2 | -0.2743 ± 0.0162 | 0/2 | 0.500 |
| accumo-v41 | static_good | pi_temp_c | 2 | -2.1832 ± 25.0298 | 0/2 | 0.500 |
| accumo-v41 | static_good | jetson_w | 1 | -0.8495 ± nan | 0/1 | 1.000 |
| accumo-v41 | ALL | sAP_fc | 6 | +0.0011 ± 0.0094 | 1/6 | 1.000 |
| accumo-v41 | ALL | sAP | 6 | -0.0022 ± 0.0063 | 1/6 | 0.406 |
| accumo-v41 | ALL | p_aoi300 | 6 | -0.0255 ± 0.0535 | 1/6 | 0.250 |
| accumo-v41 | ALL | deadline_met_fps | 6 | -3.4882 ± 1.7257 | 0/6 | 0.031 |
| accumo-v41 | ALL | pi_w | 6 | -0.4320 ± 0.1442 | 0/6 | 0.031 |
| accumo-v41 | ALL | pi_temp_c | 6 | -3.9566 ± 2.1356 | 0/6 | 0.031 |
| accumo-v41 | ALL | jetson_w | 5 | +0.0673 ± 0.6954 | 3/5 | 0.875 |
| leaf-v41 | mesh_mission | sAP_fc | 2 | +0.0010 ± 0.0155 | 1/2 | 1.000 |
| leaf-v41 | mesh_mission | sAP | 2 | +0.0019 ± 0.0010 | 2/2 | 0.500 |
| leaf-v41 | mesh_mission | p_aoi300 | 2 | -0.0028 ± 0.0283 | 0/2 | 0.500 |
| leaf-v41 | mesh_mission | deadline_met_fps | 2 | -0.1812 ± 2.5685 | 1/2 | 1.000 |
| leaf-v41 | mesh_mission | pi_w | 2 | -0.4416 ± 0.1421 | 0/2 | 0.500 |
| leaf-v41 | mesh_mission | pi_temp_c | 2 | -4.3867 ± 4.4524 | 0/2 | 0.500 |
| leaf-v41 | mesh_mission | jetson_w | 2 | -0.0047 ± 0.2335 | 1/2 | 1.000 |
| leaf-v41 | multihop | sAP_fc | 2 | +0.0028 ± 0.0931 | 1/2 | 1.000 |
| leaf-v41 | multihop | sAP | 2 | +0.0009 ± 0.0464 | 1/2 | 1.000 |
| leaf-v41 | multihop | p_aoi300 | 2 | -0.0319 ± 0.4367 | 1/2 | 1.000 |
| leaf-v41 | multihop | deadline_met_fps | 2 | -0.5250 ± 9.2677 | 1/2 | 1.000 |
| leaf-v41 | multihop | pi_w | 2 | -0.6657 ± 0.2984 | 0/2 | 0.500 |
| leaf-v41 | multihop | pi_temp_c | 2 | -5.8689 ± 8.8256 | 0/2 | 0.500 |
| leaf-v41 | multihop | jetson_w | 2 | -0.0257 ± 0.8941 | 1/2 | 1.000 |
| leaf-v41 | static_good | sAP_fc | 2 | -0.0015 ± 0.0548 | 1/2 | 1.000 |
| leaf-v41 | static_good | sAP | 2 | -0.0021 ± 0.0420 | 1/2 | 1.000 |
| leaf-v41 | static_good | p_aoi300 | 2 | +0.0000 ± 0.0000 | 0/2 | 1.000 |
| leaf-v41 | static_good | deadline_met_fps | 2 | -0.6562 ± 1.6152 | 0/2 | 0.500 |
| leaf-v41 | static_good | pi_w | 2 | -0.3203 ± 0.4524 | 0/2 | 0.500 |
| leaf-v41 | static_good | pi_temp_c | 2 | -2.1076 ± 8.6604 | 0/2 | 0.500 |
| leaf-v41 | static_good | jetson_w | 2 | +0.0900 ± 0.7018 | 2/2 | 0.500 |
| leaf-v41 | ALL | sAP_fc | 6 | +0.0008 ± 0.0061 | 3/6 | 0.812 |
| leaf-v41 | ALL | sAP | 6 | +0.0002 ± 0.0038 | 4/6 | 0.875 |
| leaf-v41 | ALL | p_aoi300 | 6 | -0.0115 ± 0.0282 | 1/6 | 0.375 |
| leaf-v41 | ALL | deadline_met_fps | 6 | -0.4542 ± 0.5587 | 2/6 | 0.125 |
| leaf-v41 | ALL | pi_w | 6 | -0.4759 ± 0.1670 | 0/6 | 0.031 |
| leaf-v41 | ALL | pi_temp_c | 6 | -4.1210 ± 1.9058 | 0/6 | 0.031 |
| leaf-v41 | ALL | jetson_w | 6 | +0.0199 ± 0.0838 | 4/6 | 0.594 |

## mesh_mission phases (sAP + fc)
| strategy | good | ground_congested | camera_out_of_range | edge_uplink_cut | edge_link_slow | recovered |
|---|---|---|---|---|---|---|
| v41 | 0.266 | 0.084 | 0.174 | 0.176 | 0.181 | 0.233 |
| accumo | 0.265 | 0.077 | 0.172 | 0.164 | 0.181 | 0.235 |
| leaf | 0.266 | 0.082 | 0.171 | 0.178 | 0.186 | 0.234 |
