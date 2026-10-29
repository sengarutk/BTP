# vid_campaign_mesh2_long: strategies on the AegisSwarm mesh, VisDrone weights, standard sAP with live forecaster v2

| scenario | strategy | n | sAP | sAP + fc | mAP | P(AoI ≤ 300 ms) | 95th-pct AoI (ms) | deadline-met /s | median latency (ms) | Pi W | Pi °C | throttled | Jetson W | processed at |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mesh_mission | v41 | 5 | 0.0875 | **0.1784 ± 0.0005** | 0.230 | 1.000 | 167 | 21.8 | 53 | 2.90 | 70.7 | 0.00 |  | laptop 67 %, jetson 33 %, onboard 1 % |
| mesh_mission | v41e | 3 | 0.0932 | **0.1675 ± 0.0022** | 0.210 | 1.000 | 100 | 25.4 | 52 | 2.93 | 73.4 | 0.00 |  | laptop 60 %, jetson 39 %, onboard 0 % |
| mesh_mission | heat | 5 | 0.0871 | **0.1776 ± 0.0019** | 0.230 | 1.000 | 167 | 21.6 | 54 | 3.24 | 74.7 | 0.00 |  | laptop 65 %, jetson 32 %, onboard 2 % |
| mesh_mission | heate | 3 | 0.0932 | **0.1700 ± 0.0030** | 0.212 | 1.000 | 100 | 25.4 | 53 | 3.16 | 75.4 | 0.00 |  | laptop 61 %, jetson 37 %, onboard 1 % |
| ALL | v41 | 5 | 0.0875 | **0.1784 ± 0.0005** | 0.230 | 1.000 | 167 | 21.8 | 53 | 2.90 | 70.7 | 0.00 |  | laptop 67 %, jetson 33 %, onboard 1 % |
| ALL | v41e | 3 | 0.0932 | **0.1675 ± 0.0022** | 0.210 | 1.000 | 100 | 25.4 | 52 | 2.93 | 73.4 | 0.00 |  | laptop 60 %, jetson 39 %, onboard 0 % |
| ALL | heat | 5 | 0.0871 | **0.1776 ± 0.0019** | 0.230 | 1.000 | 167 | 21.6 | 54 | 3.24 | 74.7 | 0.00 |  | laptop 65 %, jetson 32 %, onboard 2 % |
| ALL | heate | 3 | 0.0932 | **0.1700 ± 0.0030** | 0.212 | 1.000 | 100 | 25.4 | 53 | 3.16 | 75.4 | 0.00 |  | laptop 61 %, jetson 37 %, onboard 1 % |

## Paired differences (same scenario and repetition)
| comparison | scope | metric | pairs | Δ ± 95 % CI | first ahead | p |
|---|---|---|---|---|---|---|
| v41e-v41 | mesh_mission | sAP_fc | 3 | -0.0112 ± 0.0014 | 0/3 | 0.250 |
| v41e-v41 | mesh_mission | sAP | 3 | +0.0056 ± 0.0016 | 3/3 | 0.250 |
| v41e-v41 | mesh_mission | p_aoi300 | 3 | +0.0001 ± 0.0001 | 3/3 | 0.250 |
| v41e-v41 | mesh_mission | deadline_met_fps | 3 | +3.6046 ± 0.2337 | 3/3 | 0.250 |
| v41e-v41 | mesh_mission | pi_w | 3 | +0.0245 ± 0.0779 | 2/3 | 0.500 |
| v41e-v41 | mesh_mission | pi_temp_c | 3 | +1.6499 ± 5.3174 | 3/3 | 0.250 |
| v41e-v41 | ALL | sAP_fc | 3 | -0.0112 ± 0.0014 | 0/3 | 0.250 |
| v41e-v41 | ALL | sAP | 3 | +0.0056 ± 0.0016 | 3/3 | 0.250 |
| v41e-v41 | ALL | p_aoi300 | 3 | +0.0001 ± 0.0001 | 3/3 | 0.250 |
| v41e-v41 | ALL | deadline_met_fps | 3 | +3.6046 ± 0.2337 | 3/3 | 0.250 |
| v41e-v41 | ALL | pi_w | 3 | +0.0245 ± 0.0779 | 2/3 | 0.500 |
| v41e-v41 | ALL | pi_temp_c | 3 | +1.6499 ± 5.3174 | 3/3 | 0.250 |
| heat-v41 | mesh_mission | sAP_fc | 5 | -0.0008 ± 0.0017 | 1/5 | 0.188 |
| heat-v41 | mesh_mission | sAP | 5 | -0.0005 ± 0.0010 | 2/5 | 0.250 |
| heat-v41 | mesh_mission | p_aoi300 | 5 | +0.0000 ± 0.0004 | 2/5 | 0.875 |
| heat-v41 | mesh_mission | deadline_met_fps | 5 | -0.1250 ± 0.2473 | 2/5 | 0.375 |
| heat-v41 | mesh_mission | pi_w | 5 | +0.3367 ± 0.2032 | 5/5 | 0.062 |
| heat-v41 | mesh_mission | pi_temp_c | 5 | +3.9946 ± 1.7659 | 5/5 | 0.062 |
| heat-v41 | ALL | sAP_fc | 5 | -0.0008 ± 0.0017 | 1/5 | 0.188 |
| heat-v41 | ALL | sAP | 5 | -0.0005 ± 0.0010 | 2/5 | 0.250 |
| heat-v41 | ALL | p_aoi300 | 5 | +0.0000 ± 0.0004 | 2/5 | 0.875 |
| heat-v41 | ALL | deadline_met_fps | 5 | -0.1250 ± 0.2473 | 2/5 | 0.375 |
| heat-v41 | ALL | pi_w | 5 | +0.3367 ± 0.2032 | 5/5 | 0.062 |
| heat-v41 | ALL | pi_temp_c | 5 | +3.9946 ± 1.7659 | 5/5 | 0.062 |
| heate-v41 | mesh_mission | sAP_fc | 3 | -0.0086 ± 0.0025 | 0/3 | 0.250 |
| heate-v41 | mesh_mission | sAP | 3 | +0.0056 ± 0.0007 | 3/3 | 0.250 |
| heate-v41 | mesh_mission | p_aoi300 | 3 | +0.0001 ± 0.0001 | 3/3 | 0.250 |
| heate-v41 | mesh_mission | deadline_met_fps | 3 | +3.6646 ± 0.2210 | 3/3 | 0.250 |
| heate-v41 | mesh_mission | pi_w | 3 | +0.2544 ± 0.3155 | 3/3 | 0.250 |
| heate-v41 | mesh_mission | pi_temp_c | 3 | +3.6297 ± 3.9062 | 3/3 | 0.250 |
| heate-v41 | ALL | sAP_fc | 3 | -0.0086 ± 0.0025 | 0/3 | 0.250 |
| heate-v41 | ALL | sAP | 3 | +0.0056 ± 0.0007 | 3/3 | 0.250 |
| heate-v41 | ALL | p_aoi300 | 3 | +0.0001 ± 0.0001 | 3/3 | 0.250 |
| heate-v41 | ALL | deadline_met_fps | 3 | +3.6646 ± 0.2210 | 3/3 | 0.250 |
| heate-v41 | ALL | pi_w | 3 | +0.2544 ± 0.3155 | 3/3 | 0.250 |
| heate-v41 | ALL | pi_temp_c | 3 | +3.6297 ± 3.9062 | 3/3 | 0.250 |
| heate-heat | mesh_mission | sAP_fc | 3 | -0.0084 ± 0.0039 | 0/3 | 0.250 |
| heate-heat | mesh_mission | sAP | 3 | +0.0056 ± 0.0003 | 3/3 | 0.250 |
| heate-heat | mesh_mission | p_aoi300 | 3 | +0.0001 ± 0.0003 | 2/3 | 0.500 |
| heate-heat | mesh_mission | deadline_met_fps | 3 | +3.8095 ± 0.1972 | 3/3 | 0.250 |
| heate-heat | mesh_mission | pi_w | 3 | +0.0168 ± 0.0842 | 2/3 | 0.750 |
| heate-heat | mesh_mission | pi_temp_c | 3 | -0.0762 ± 0.7568 | 1/3 | 0.750 |
| heate-heat | ALL | sAP_fc | 3 | -0.0084 ± 0.0039 | 0/3 | 0.250 |
| heate-heat | ALL | sAP | 3 | +0.0056 ± 0.0003 | 3/3 | 0.250 |
| heate-heat | ALL | p_aoi300 | 3 | +0.0001 ± 0.0003 | 2/3 | 0.500 |
| heate-heat | ALL | deadline_met_fps | 3 | +3.8095 ± 0.1972 | 3/3 | 0.250 |
| heate-heat | ALL | pi_w | 3 | +0.0168 ± 0.0842 | 2/3 | 0.750 |
| heate-heat | ALL | pi_temp_c | 3 | -0.0762 ± 0.7568 | 1/3 | 0.750 |

## mesh_mission phases (sAP + fc)
| strategy | good | ground_congested | camera_out_of_range | edge_uplink_cut | edge_link_slow | recovered |
|---|---|---|---|---|---|---|
| v41 | 0.202 | 0.143 | 0.157 | 0.187 | 0.196 | 0.189 |
| v41e | 0.201 | 0.131 | 0.129 | 0.173 | 0.195 | 0.175 |
| heat | 0.202 | 0.143 | 0.156 | 0.187 | 0.194 | 0.188 |
| heate | 0.200 | 0.130 | 0.129 | 0.181 | 0.196 | 0.183 |
