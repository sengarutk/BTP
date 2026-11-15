# vid_campaign_two_nov: strategies on the AegisSwarm mesh, VisDrone weights, standard sAP with live forecaster v2

| scenario | strategy | n | sAP | sAP + fc | mAP | P(AoI ≤ 300 ms) | 95th-pct AoI (ms) | deadline-met /s | median latency (ms) | Pi W | Pi °C | throttled | Jetson W | processed at |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mesh_mission | v41j1 | 6 | 0.0729 | **0.1667 ± 0.0032** | 0.237 | 0.994 | 233 | 17.1 | 80 | 2.83 | 68.0 | 0.00 | 6.12 | laptop 63 %, jetson 34 %, onboard 2 % |
| mesh_mission | v41j2 | 6 | 0.0498 | **0.1294 ± 0.0075** | 0.219 | 0.972 | 300 | 17.0 | 132 | 2.90 | 66.7 | 0.00 | 5.73 | laptop 38 %, jetson2 31 %, jetson 28 %, onboard 3 % |
| static_good | v41j1 | 6 | 0.0862 | **0.1813 ± 0.0040** | 0.240 | 0.998 | 183 | 20.0 | 70 | 2.82 | 66.3 | 0.00 | 5.73 | laptop 74 %, jetson 24 %, onboard 1 % |
| static_good | v41j2 | 6 | 0.0586 | **0.1436 ± 0.0067** | 0.226 | 0.975 | 272 | 17.7 | 124 | 2.92 | 69.4 | 0.00 | 5.63 | laptop 47 %, jetson2 26 %, jetson 25 %, onboard 2 % |
| ALL | v41j1 | 12 | 0.0796 | **0.1740 ± 0.0053** | 0.238 | 0.996 | 208 | 18.5 | 75 | 2.82 | 67.2 | 0.00 | 5.92 | laptop 69 %, jetson 29 %, onboard 2 % |
| ALL | v41j2 | 12 | 0.0542 | **0.1365 ± 0.0062** | 0.223 | 0.973 | 286 | 17.4 | 128 | 2.91 | 68.1 | 0.00 | 5.68 | laptop 43 %, jetson2 29 %, jetson 27 %, onboard 2 % |

## Paired differences (same scenario and repetition)
| comparison | scope | metric | pairs | Δ ± 95 % CI | first ahead | p |
|---|---|---|---|---|---|---|

## mesh_mission phases (sAP + fc)
| strategy | good | ground_congested | camera_out_of_range | edge_uplink_cut | edge_link_slow | recovered |
|---|---|---|---|---|---|---|
| v41j1 | 0.253 | 0.061 | 0.147 | 0.156 | 0.181 | 0.219 |
| v41j2 | 0.209 | 0.041 | 0.120 | 0.119 | 0.134 | 0.185 |
