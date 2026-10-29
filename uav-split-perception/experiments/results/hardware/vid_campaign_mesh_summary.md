# Mesh campaign: v4.1 (direct) vs hierarchical chain, VisDrone weights, standard sAP with live forecaster v2

| scenario | method | n | sAP | sAP + fc | mAP | P(AoI ≤ 300 ms) | 95th-pct AoI (ms) | median latency (ms) | Pi W | Pi °C | throttled | processed at |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mesh_mission | v41 | 3 | 0.0937 | **0.1859 ± 0.0065** | 0.238 | 1.000 | 167 | 54 | 2.81 | 64.9 | 0.00 | laptop 64 %, jetson 34 %, onboard 2 % |
| mesh_mission | hier | 3 | 0.0477 | **0.1413 ± 0.0011** | 0.226 | 0.985 | 233 | 108 | 2.83 | 65.1 | 0.00 | jetson 94 %, onboard 6 % |
| static_good | v41 | 3 | 0.1098 | **0.2008 ± 0.0037** | 0.239 | 1.000 | 100 | 50 | 2.82 | 63.7 | 0.00 | laptop 77 %, jetson 22 %, onboard 1 % |
| static_good | hier | 3 | 0.0524 | **0.1511 ± 0.0018** | 0.226 | 0.999 | 200 | 104 | 2.80 | 63.6 | 0.00 | jetson 95 %, onboard 5 % |
| ALL | v41 | 6 | 0.1017 | **0.1933 ± 0.0088** | 0.239 | 1.000 | 133 | 52 | 2.81 | 64.3 | 0.00 | laptop 71 %, jetson 27 %, onboard 1 % |
| ALL | hier | 6 | 0.0500 | **0.1462 ± 0.0057** | 0.226 | 0.992 | 217 | 106 | 2.81 | 64.4 | 0.00 | jetson 94 %, onboard 6 % |

## Paired: v4.1 minus hierarchical chain
| scope | metric | pairs | Δ ± 95 % CI | v4.1 ahead | p |
|---|---|---|---|---|---|
| mesh_mission | sAP_fc | 3 | +0.0446 ± 0.0070 | 3/3 | 0.250 |
| mesh_mission | sAP | 3 | +0.0460 ± 0.0051 | 3/3 | 0.250 |
| mesh_mission | p_aoi300 | 3 | +0.0145 ± 0.0065 | 3/3 | 0.250 |
| mesh_mission | pi_w | 3 | -0.0148 ± 0.0512 | 1/3 | 0.500 |
| static_good | sAP_fc | 3 | +0.0497 ± 0.0028 | 3/3 | 0.250 |
| static_good | sAP | 3 | +0.0574 ± 0.0014 | 3/3 | 0.250 |
| static_good | p_aoi300 | 3 | +0.0005 ± 0.0013 | 3/3 | 0.250 |
| static_good | pi_w | 3 | +0.0164 ± 0.0497 | 2/3 | 0.500 |
| ALL | sAP_fc | 6 | +0.0471 ± 0.0035 | 6/6 | 0.031 |
| ALL | sAP | 6 | +0.0517 ± 0.0067 | 6/6 | 0.031 |
| ALL | p_aoi300 | 6 | +0.0075 ± 0.0082 | 6/6 | 0.031 |
| ALL | pi_w | 6 | +0.0008 ± 0.0262 | 3/6 | 0.969 |

## mesh_mission phases (sAP + fc)
| method | good | ground_congested | camera_out_of_range | edge_uplink_cut | edge_link_slow | recovered |
|---|---|---|---|---|---|---|
| v41 | 0.267 | 0.082 | 0.175 | 0.184 | 0.185 | 0.234 |
| hier | 0.207 | 0.078 | 0.164 | 0.156 | 0.069 | 0.187 |
