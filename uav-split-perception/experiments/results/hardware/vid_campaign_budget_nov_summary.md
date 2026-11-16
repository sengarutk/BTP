# vid_campaign_budget_nov: strategies on the AegisSwarm mesh, VisDrone weights, standard sAP with live forecaster v2

| scenario | strategy | n | sAP | sAP + fc | mAP | P(AoI ≤ 300 ms) | 95th-pct AoI (ms) | deadline-met /s | median latency (ms) | Pi W | Pi °C | throttled | Jetson W | processed at |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mesh_mission | v41final | 3 | 0.0898 | **0.1819 ± 0.0020** | 0.238 | 0.999 | 167 | 20.6 | 57 | 2.81 | 65.3 | 0.00 | 5.34 | laptop 62 %, jetson 35 %, onboard 3 % |
| mesh_mission | v41final24 | 3 | 0.0894 | **0.1815 ± 0.0060** | 0.241 | 0.999 | 167 | 20.2 | 55 | 2.50 | 61.9 | 0.00 | 5.34 | laptop 63 %, jetson 36 %, onboard 1 % |
| mesh_mission | v41dvfs24 | 3 | 0.0904 | **0.1839 ± 0.0034** | 0.240 | 0.999 | 167 | 20.6 | 56 | 2.52 | 63.5 | 0.00 | 5.34 | laptop 64 %, jetson 36 %, onboard 1 % |
| multihop | v41final | 3 | 0.0471 | **0.1359 ± 0.0034** | 0.225 | 0.996 | 233 | 11.2 | 113 | 2.79 | 64.9 | 0.00 | 5.66 | jetson 73 %, laptop 21 %, onboard 6 % |
| multihop | v41final24 | 3 | 0.0464 | **0.1344 ± 0.0046** | 0.224 | 0.994 | 233 | 10.9 | 109 | 2.42 | 62.0 | 0.00 | 5.66 | jetson 75 %, laptop 23 %, onboard 2 % |
| multihop | v41dvfs24 | 3 | 0.0455 | **0.1325 ± 0.0089** | 0.223 | 0.996 | 233 | 11.2 | 109 | 2.44 | 62.6 | 0.00 | 5.66 | jetson 73 %, laptop 23 %, onboard 3 % |
| ALL | v41final | 6 | 0.0685 | **0.1589 ± 0.0265** | 0.231 | 0.997 | 200 | 15.9 | 85 | 2.80 | 65.1 | 0.00 | 5.50 | jetson 50 %, laptop 47 %, onboard 4 % |
| ALL | v41final24 | 6 | 0.0679 | **0.1579 ± 0.0271** | 0.232 | 0.997 | 200 | 15.6 | 82 | 2.46 | 62.0 | 0.00 | 5.50 | jetson 51 %, laptop 48 %, onboard 1 % |
| ALL | v41dvfs24 | 6 | 0.0680 | **0.1582 ± 0.0296** | 0.232 | 0.997 | 200 | 15.9 | 83 | 2.48 | 63.0 | 0.00 | 5.50 | jetson 50 %, laptop 48 %, onboard 2 % |

## Paired differences (same scenario and repetition)
| comparison | scope | metric | pairs | Δ ± 95 % CI | first ahead | p |
|---|---|---|---|---|---|---|

## mesh_mission phases (sAP + fc)
| strategy | good | ground_congested | camera_out_of_range | edge_uplink_cut | edge_link_slow | recovered |
|---|---|---|---|---|---|---|
| v41final | 0.262 | 0.082 | 0.172 | 0.177 | 0.182 | 0.233 |
| v41final24 | 0.263 | 0.083 | 0.171 | 0.177 | 0.181 | 0.233 |
| v41dvfs24 | 0.263 | 0.086 | 0.173 | 0.182 | 0.183 | 0.232 |
