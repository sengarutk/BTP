# vid_campaign_final_nov: strategies on the AegisSwarm mesh, VisDrone weights, standard sAP with live forecaster v2

| scenario | strategy | n | sAP | sAP + fc | mAP | P(AoI ≤ 300 ms) | 95th-pct AoI (ms) | deadline-met /s | median latency (ms) | Pi W | Pi °C | throttled | Jetson W | processed at |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mesh_mission | v41 | 5 | 0.0946 | **0.1851 ± 0.0019** | 0.238 | 1.000 | 167 | 21.2 | 52 | 2.81 | 63.9 | 0.00 | 5.31 | laptop 65 %, jetson 33 %, onboard 2 % |
| mesh_mission | accumo | 5 | 0.0861 | **0.1790 ± 0.0013** | 0.241 | 0.988 | 167 | 17.3 | 48 | 2.45 | 61.1 | 0.00 | 5.85 | laptop 72 %, jetson 28 % |
| mesh_mission | leaf | 5 | 0.0930 | **0.1845 ± 0.0028** | 0.239 | 0.997 | 167 | 20.8 | 53 | 2.41 | 58.6 | 0.00 | 5.30 | laptop 66 %, jetson 34 %, onboard 0 % |
| mesh_mission | v41final | 5 | 0.0939 | **0.1857 ± 0.0021** | 0.238 | 0.999 | 167 | 21.3 | 52 | 2.81 | 63.8 | 0.00 | 5.30 | laptop 65 %, jetson 33 %, onboard 2 % |
| multihop | v41 | 5 | 0.0481 | **0.1371 ± 0.0026** | 0.223 | 0.995 | 233 | 11.5 | 108 | 2.80 | 64.5 | 0.00 | 5.71 | jetson 73 %, laptop 21 %, onboard 5 % |
| multihop | accumo | 5 | 0.0550 | **0.1501 ± 0.0036** | 0.231 | 0.990 | 207 | 10.7 | 85 | 2.25 | 59.3 | 0.00 | 5.88 | jetson 100 %, laptop 0 %, onboard 0 % |
| multihop | leaf | 5 | 0.0474 | **0.1381 ± 0.0055** | 0.224 | 0.988 | 247 | 11.8 | 110 | 2.20 | 58.3 | 0.00 | 5.73 | jetson 76 %, laptop 24 %, onboard 0 % |
| multihop | v41final | 5 | 0.0464 | **0.1339 ± 0.0049** | 0.226 | 0.993 | 240 | 11.4 | 113 | 2.83 | 64.1 | 0.00 | 5.67 | jetson 72 %, laptop 21 %, onboard 6 % |
| ALL | v41 | 10 | 0.0713 | **0.1611 ± 0.0181** | 0.230 | 0.997 | 200 | 16.3 | 80 | 2.81 | 64.2 | 0.00 | 5.51 | jetson 48 %, laptop 48 %, onboard 3 % |
| ALL | accumo | 10 | 0.0706 | **0.1645 ± 0.0110** | 0.236 | 0.989 | 187 | 14.0 | 66 | 2.35 | 60.2 | 0.00 | 5.86 | jetson 56 %, laptop 44 %, onboard 0 % |
| ALL | leaf | 10 | 0.0702 | **0.1613 ± 0.0176** | 0.232 | 0.993 | 207 | 16.3 | 82 | 2.31 | 58.5 | 0.00 | 5.52 | jetson 50 %, laptop 50 %, onboard 0 % |
| ALL | v41final | 10 | 0.0701 | **0.1598 ± 0.0196** | 0.232 | 0.996 | 203 | 16.3 | 83 | 2.82 | 64.0 | 0.00 | 5.48 | laptop 48 %, jetson 48 %, onboard 4 % |

## Paired differences (same scenario and repetition)
| comparison | scope | metric | pairs | Δ ± 95 % CI | first ahead | p |
|---|---|---|---|---|---|---|
| accumo-v41 | mesh_mission | sAP_fc | 5 | -0.0061 ± 0.0022 | 0/5 | 0.062 |
| accumo-v41 | mesh_mission | sAP | 5 | -0.0085 ± 0.0026 | 0/5 | 0.062 |
| accumo-v41 | mesh_mission | p_aoi300 | 5 | -0.0113 ± 0.0038 | 0/5 | 0.062 |
| accumo-v41 | mesh_mission | deadline_met_fps | 5 | -3.9100 ± 0.5539 | 0/5 | 0.062 |
| accumo-v41 | mesh_mission | pi_w | 5 | -0.3575 ± 0.0387 | 0/5 | 0.062 |
| accumo-v41 | mesh_mission | pi_temp_c | 5 | -2.7224 ± 1.5069 | 0/5 | 0.062 |
| accumo-v41 | mesh_mission | jetson_w | 5 | +0.5381 ± 0.0575 | 5/5 | 0.062 |
| accumo-v41 | multihop | sAP_fc | 5 | +0.0130 ± 0.0037 | 5/5 | 0.062 |
| accumo-v41 | multihop | sAP | 5 | +0.0070 ± 0.0021 | 5/5 | 0.062 |
| accumo-v41 | multihop | p_aoi300 | 5 | -0.0054 ± 0.0079 | 1/5 | 0.125 |
| accumo-v41 | multihop | deadline_met_fps | 5 | -0.7683 ± 0.2885 | 0/5 | 0.062 |
| accumo-v41 | multihop | pi_w | 5 | -0.5579 ± 0.0418 | 0/5 | 0.062 |
| accumo-v41 | multihop | pi_temp_c | 5 | -5.1926 ± 0.8250 | 0/5 | 0.062 |
| accumo-v41 | multihop | jetson_w | 5 | +0.1678 ± 0.0390 | 5/5 | 0.062 |
| accumo-v41 | ALL | sAP_fc | 10 | +0.0034 ± 0.0074 | 5/10 | 0.311 |
| accumo-v41 | ALL | sAP | 10 | -0.0008 ± 0.0060 | 5/10 | 0.768 |
| accumo-v41 | ALL | p_aoi300 | 10 | -0.0084 ± 0.0040 | 1/10 | 0.004 |
| accumo-v41 | ALL | deadline_met_fps | 10 | -2.3392 ± 1.2073 | 0/10 | 0.002 |
| accumo-v41 | ALL | pi_w | 10 | -0.4577 ± 0.0786 | 0/10 | 0.002 |
| accumo-v41 | ALL | pi_temp_c | 10 | -3.9575 ± 1.1398 | 0/10 | 0.002 |
| accumo-v41 | ALL | jetson_w | 10 | +0.3529 ± 0.1420 | 10/10 | 0.002 |
| leaf-v41 | mesh_mission | sAP_fc | 5 | -0.0006 ± 0.0040 | 3/5 | 0.750 |
| leaf-v41 | mesh_mission | sAP | 5 | -0.0016 ± 0.0053 | 3/5 | 0.500 |
| leaf-v41 | mesh_mission | p_aoi300 | 5 | -0.0022 ± 0.0034 | 1/5 | 0.188 |
| leaf-v41 | mesh_mission | deadline_met_fps | 5 | -0.3925 ± 0.8854 | 1/5 | 0.125 |
| leaf-v41 | mesh_mission | pi_w | 5 | -0.4032 ± 0.0406 | 0/5 | 0.062 |
| leaf-v41 | mesh_mission | pi_temp_c | 5 | -5.2366 ± 4.5025 | 0/5 | 0.062 |
| leaf-v41 | mesh_mission | jetson_w | 5 | -0.0091 ± 0.0675 | 2/5 | 0.812 |
| leaf-v41 | multihop | sAP_fc | 5 | +0.0010 ± 0.0045 | 3/5 | 0.625 |
| leaf-v41 | multihop | sAP | 5 | -0.0007 ± 0.0031 | 2/5 | 0.688 |
| leaf-v41 | multihop | p_aoi300 | 5 | -0.0075 ± 0.0240 | 3/5 | 0.875 |
| leaf-v41 | multihop | deadline_met_fps | 5 | +0.3767 ± 0.5404 | 4/5 | 0.125 |
| leaf-v41 | multihop | pi_w | 5 | -0.6000 ± 0.0177 | 0/5 | 0.062 |
| leaf-v41 | multihop | pi_temp_c | 5 | -6.2291 ± 0.8779 | 0/5 | 0.062 |
| leaf-v41 | multihop | jetson_w | 5 | +0.0188 ± 0.0480 | 4/5 | 0.375 |
| leaf-v41 | ALL | sAP_fc | 10 | +0.0002 ± 0.0024 | 6/10 | 0.865 |
| leaf-v41 | ALL | sAP | 10 | -0.0012 ± 0.0024 | 5/10 | 0.314 |
| leaf-v41 | ALL | p_aoi300 | 10 | -0.0049 ± 0.0095 | 4/10 | 0.242 |
| leaf-v41 | ALL | deadline_met_fps | 10 | -0.0079 ± 0.4919 | 5/10 | 0.975 |
| leaf-v41 | ALL | pi_w | 10 | -0.5016 ± 0.0760 | 0/10 | 0.002 |
| leaf-v41 | ALL | pi_temp_c | 10 | -5.7328 ± 1.7973 | 0/10 | 0.002 |
| leaf-v41 | ALL | jetson_w | 10 | +0.0048 ± 0.0334 | 6/10 | 0.744 |
| v41final-v41 | mesh_mission | sAP_fc | 5 | +0.0006 ± 0.0032 | 3/5 | 0.625 |
| v41final-v41 | mesh_mission | sAP | 5 | -0.0007 ± 0.0034 | 2/5 | 0.625 |
| v41final-v41 | mesh_mission | p_aoi300 | 5 | -0.0002 ± 0.0008 | 1/5 | 0.500 |
| v41final-v41 | mesh_mission | deadline_met_fps | 5 | +0.0742 ± 0.5309 | 3/5 | 0.688 |
| v41final-v41 | mesh_mission | pi_w | 5 | -0.0044 ± 0.0119 | 1/5 | 0.375 |
| v41final-v41 | mesh_mission | pi_temp_c | 5 | -0.0881 ± 1.9471 | 2/5 | 0.875 |
| v41final-v41 | mesh_mission | jetson_w | 5 | -0.0079 ± 0.0515 | 3/5 | 0.750 |
| v41final-v41 | multihop | sAP_fc | 5 | -0.0032 ± 0.0032 | 0/5 | 0.062 |
| v41final-v41 | multihop | sAP | 5 | -0.0017 ± 0.0020 | 0/5 | 0.062 |
| v41final-v41 | multihop | p_aoi300 | 5 | -0.0020 ± 0.0099 | 4/5 | 1.000 |
| v41final-v41 | multihop | deadline_met_fps | 5 | -0.1033 ± 0.3649 | 2/5 | 0.438 |
| v41final-v41 | multihop | pi_w | 5 | +0.0227 ± 0.0657 | 3/5 | 0.562 |
| v41final-v41 | multihop | pi_temp_c | 5 | -0.3814 ± 0.7345 | 1/5 | 0.250 |
| v41final-v41 | multihop | jetson_w | 5 | -0.0439 ± 0.0771 | 1/5 | 0.125 |
| v41final-v41 | ALL | sAP_fc | 10 | -0.0013 ± 0.0023 | 3/10 | 0.217 |
| v41final-v41 | ALL | sAP | 10 | -0.0012 ± 0.0016 | 2/10 | 0.117 |
| v41final-v41 | ALL | p_aoi300 | 10 | -0.0011 ± 0.0039 | 5/10 | 0.930 |
| v41final-v41 | ALL | deadline_met_fps | 10 | -0.0146 ± 0.2558 | 5/10 | 0.895 |
| v41final-v41 | ALL | pi_w | 10 | +0.0091 ± 0.0276 | 4/10 | 0.742 |
| v41final-v41 | ALL | pi_temp_c | 10 | -0.2348 ± 0.8051 | 3/10 | 0.529 |
| v41final-v41 | ALL | jetson_w | 10 | -0.0259 ± 0.0380 | 4/10 | 0.145 |

## mesh_mission phases (sAP + fc)
| strategy | good | ground_congested | camera_out_of_range | edge_uplink_cut | edge_link_slow | recovered |
|---|---|---|---|---|---|---|
| v41 | 0.267 | 0.084 | 0.174 | 0.183 | 0.184 | 0.236 |
| accumo | 0.265 | 0.074 | 0.172 | 0.166 | 0.182 | 0.235 |
| leaf | 0.267 | 0.082 | 0.173 | 0.180 | 0.186 | 0.235 |
| v41final | 0.267 | 0.085 | 0.175 | 0.182 | 0.186 | 0.235 |
