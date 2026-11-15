# vid_campaign_two_cap: strategies on the AegisSwarm mesh, VisDrone weights, standard sAP with live forecaster v2

| scenario | strategy | n | sAP | sAP + fc | mAP | P(AoI ≤ 300 ms) | 95th-pct AoI (ms) | deadline-met /s | median latency (ms) | Pi W | Pi °C | throttled | Jetson W | processed at |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mesh_mission | v41j2 | 4 | 0.0488 | **0.1262 ± 0.0462** | 0.214 | 0.960 | 308 | 17.5 | 134 | 2.90 | 63.2 | 0.00 | 5.61 | laptop 36 %, jetson2 33 %, jetson 28 %, onboard 3 % |
| mesh_mission | v41j2cap | 4 | 0.0462 | **0.1244 ± 0.0172** | 0.223 | 0.948 | 317 | 14.5 | 125 | 2.89 | 62.3 | 0.00 | 5.67 | jetson2 36 %, laptop 32 %, jetson 27 %, onboard 5 % |
| static_good | v41j2 | 4 | 0.0560 | **0.1348 ± 0.0590** | 0.215 | 0.938 | 317 | 18.3 | 123 | 2.88 | 62.7 | 0.00 | 5.52 | laptop 46 %, jetson2 27 %, jetson 24 %, onboard 3 % |
| static_good | v41j2cap | 4 | 0.0594 | **0.1409 ± 0.0562** | 0.228 | 0.964 | 275 | 16.4 | 109 | 2.89 | 63.5 | 0.00 | 5.25 | laptop 48 %, jetson2 29 %, jetson 20 %, onboard 4 % |
| ALL | v41j2 | 8 | 0.0524 | **0.1305 ± 0.0260** | 0.215 | 0.949 | 312 | 17.9 | 128 | 2.89 | 63.0 | 0.00 | 5.56 | laptop 41 %, jetson2 30 %, jetson 26 %, onboard 3 % |
| ALL | v41j2cap | 8 | 0.0528 | **0.1326 ± 0.0215** | 0.225 | 0.956 | 296 | 15.4 | 117 | 2.89 | 62.9 | 0.00 | 5.46 | laptop 41 %, jetson2 32 %, jetson 23 %, onboard 4 % |

## Paired differences (same scenario and repetition)
| comparison | scope | metric | pairs | Δ ± 95 % CI | first ahead | p |
|---|---|---|---|---|---|---|

## mesh_mission phases (sAP + fc)
| strategy | good | ground_congested | camera_out_of_range | edge_uplink_cut | edge_link_slow | recovered |
|---|---|---|---|---|---|---|
| v41j2 | 0.201 | 0.046 | 0.121 | 0.114 | 0.132 | 0.169 |
| v41j2cap | 0.183 | 0.045 | 0.118 | 0.103 | 0.143 | 0.177 |
