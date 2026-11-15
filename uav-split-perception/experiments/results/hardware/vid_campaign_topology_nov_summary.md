# vid_campaign_topology_nov: strategies on the AegisSwarm mesh, VisDrone weights, standard sAP with live forecaster v2

| scenario | strategy | n | sAP | sAP + fc | mAP | P(AoI ≤ 300 ms) | 95th-pct AoI (ms) | deadline-met /s | median latency (ms) | Pi W | Pi °C | throttled | Jetson W | processed at |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| multihop | v41 | 5 | 0.0470 | **0.1355 ± 0.0028** | 0.224 | 0.996 | 233 | 11.4 | 111 | 2.80 | 64.7 | 0.00 | 5.68 | jetson 73 %, laptop 22 %, onboard 5 % |
| multihop | hier | 5 | 0.0514 | **0.1497 ± 0.0017** | 0.227 | 1.000 | 200 | 13.7 | 106 | 2.81 | 64.8 | 0.00 | 6.47 | jetson 95 %, onboard 5 %, laptop 0 % |
| static_good | v41 | 5 | 0.1103 | **0.2010 ± 0.0013** | 0.240 | 1.000 | 107 | 26.2 | 50 | 2.81 | 64.0 | 0.00 | 5.03 | laptop 78 %, jetson 21 %, onboard 1 % |
| static_good | hier | 5 | 0.0514 | **0.1495 ± 0.0016** | 0.227 | 0.999 | 207 | 13.6 | 106 | 2.82 | 64.6 | 0.00 | 6.46 | jetson 95 %, onboard 5 %, laptop 0 % |
| ALL | v41 | 10 | 0.0787 | **0.1682 ± 0.0247** | 0.232 | 0.998 | 170 | 18.8 | 80 | 2.81 | 64.3 | 0.00 | 5.35 | laptop 59 %, jetson 38 %, onboard 2 % |

## Paired differences (same scenario and repetition)
| comparison | scope | metric | pairs | Δ ± 95 % CI | first ahead | p |
|---|---|---|---|---|---|---|
| hier-v41 | multihop | sAP_fc | 5 | +0.0142 ± 0.0013 | 5/5 | 0.062 |
| hier-v41 | multihop | sAP | 5 | +0.0044 ± 0.0005 | 5/5 | 0.062 |
| hier-v41 | multihop | p_aoi300 | 5 | +0.0035 ± 0.0029 | 5/5 | 0.062 |
| hier-v41 | multihop | deadline_met_fps | 5 | +2.3042 ± 0.0994 | 5/5 | 0.062 |
| hier-v41 | multihop | pi_w | 5 | +0.0119 ± 0.0208 | 4/5 | 0.188 |
| hier-v41 | multihop | pi_temp_c | 5 | +0.1100 ± 0.3647 | 4/5 | 0.562 |
| hier-v41 | multihop | jetson_w | 5 | +0.7900 ± 0.0080 | 5/5 | 0.062 |
| hier-v41 | static_good | sAP_fc | 5 | -0.0515 ± 0.0024 | 0/5 | 0.062 |
| hier-v41 | static_good | sAP | 5 | -0.0589 ± 0.0016 | 0/5 | 0.062 |
| hier-v41 | static_good | p_aoi300 | 5 | -0.0012 ± 0.0023 | 0/5 | 0.125 |
| hier-v41 | static_good | deadline_met_fps | 5 | -12.6133 ± 0.1833 | 0/5 | 0.062 |
| hier-v41 | static_good | pi_w | 5 | +0.0047 ± 0.0229 | 2/5 | 0.875 |
| hier-v41 | static_good | pi_temp_c | 5 | +0.6282 ± 0.8458 | 4/5 | 0.188 |
| hier-v41 | static_good | jetson_w | 5 | +1.4321 ± 0.1318 | 5/5 | 0.062 |
| hier-v41 | ALL | sAP_fc | 10 | -0.0186 ± 0.0248 | 5/10 | 0.121 |
| hier-v41 | ALL | sAP | 10 | -0.0273 ± 0.0238 | 5/10 | 0.062 |
| hier-v41 | ALL | p_aoi300 | 10 | +0.0012 ± 0.0023 | 5/10 | 0.289 |
| hier-v41 | ALL | deadline_met_fps | 10 | -5.1546 ± 5.6195 | 5/10 | 0.062 |
| hier-v41 | ALL | pi_w | 10 | +0.0083 ± 0.0122 | 6/10 | 0.191 |
| hier-v41 | ALL | pi_temp_c | 10 | +0.3691 ± 0.4034 | 8/10 | 0.080 |
| hier-v41 | ALL | jetson_w | 10 | +1.1110 ± 0.2471 | 10/10 | 0.002 |
