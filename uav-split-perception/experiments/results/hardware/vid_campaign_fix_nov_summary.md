# vid_campaign_fix_nov: strategies on the AegisSwarm mesh, VisDrone weights, standard sAP with live forecaster v2

| scenario | strategy | n | sAP | sAP + fc | mAP | P(AoI ≤ 300 ms) | 95th-pct AoI (ms) | deadline-met /s | median latency (ms) | Pi W | Pi °C | throttled | Jetson W | processed at |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mesh_mission | v41final24 | 5 | 0.0755 | **0.1645 ± 0.0382** | 0.233 | 0.969 | 233 | 18.0 | 76 | 2.54 | 60.9 | 0.00 | 5.29 | laptop 60 %, jetson 39 %, onboard 1 % |
| mesh_mission | v41fix24 | 5 | 0.0734 | **0.1614 ± 0.0286** | 0.235 | 0.959 | 287 | 17.8 | 70 | 2.56 | 61.0 | 0.00 | 5.34 | laptop 63 %, jetson 36 %, onboard 1 % |
| multihop | v41final24 | 5 | 0.0403 | **0.1245 ± 0.0120** | 0.220 | 0.955 | 300 | 10.6 | 125 | 2.50 | 61.7 | 0.00 | 5.55 | jetson 72 %, laptop 24 %, onboard 4 % |
| multihop | v41fix24 | 5 | 0.0495 | **0.1396 ± 0.0150** | 0.227 | 0.956 | 293 | 10.9 | 94 | 2.45 | 61.0 | 0.00 | 5.78 | jetson 91 %, laptop 5 %, onboard 3 % |
| ALL | v41final24 | 10 | 0.0579 | **0.1445 ± 0.0215** | 0.227 | 0.962 | 267 | 14.3 | 101 | 2.52 | 61.3 | 0.00 | 5.42 | jetson 52 %, laptop 46 %, onboard 2 % |
| ALL | v41fix24 | 10 | 0.0615 | **0.1505 ± 0.0148** | 0.231 | 0.958 | 290 | 14.3 | 82 | 2.50 | 61.0 | 0.00 | 5.56 | jetson 57 %, laptop 41 %, onboard 2 % |

## Paired differences (same scenario and repetition)
| comparison | scope | metric | pairs | Δ ± 95 % CI | first ahead | p |
|---|---|---|---|---|---|---|

## mesh_mission phases (sAP + fc)
| strategy | good | ground_congested | camera_out_of_range | edge_uplink_cut | edge_link_slow | recovered |
|---|---|---|---|---|---|---|
| v41final24 | 0.238 | 0.074 | 0.158 | 0.159 | 0.168 | 0.210 |
| v41fix24 | 0.245 | 0.066 | 0.141 | 0.143 | 0.171 | 0.220 |
