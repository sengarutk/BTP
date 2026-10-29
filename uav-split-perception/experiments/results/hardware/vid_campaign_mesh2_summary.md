# vid_campaign_mesh2: strategies on the AegisSwarm mesh, VisDrone weights, standard sAP with live forecaster v2

| scenario | strategy | n | sAP | sAP + fc | mAP | P(AoI ≤ 300 ms) | 95th-pct AoI (ms) | deadline-met /s | median latency (ms) | Pi W | Pi °C | throttled | Jetson W | processed at |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mesh_mission | v41 | 3 | 0.0947 | **0.1855 ± 0.0036** | 0.239 | 1.000 | 167 | 21.1 | 52 | 2.84 | 70.2 | 0.00 |  | laptop 65 %, jetson 34 %, onboard 1 % |
| mesh_mission | v41e | 3 | 0.1000 | **0.1802 ± 0.0021** | 0.225 | 0.999 | 133 | 23.7 | 49 | 2.83 | 69.6 | 0.00 |  | laptop 60 %, jetson 39 %, onboard 1 % |
| mesh_mission | heat | 3 | 0.0957 | **0.1866 ± 0.0062** | 0.238 | 1.000 | 167 | 21.6 | 53 | 3.22 | 74.8 | 0.00 |  | laptop 64 %, jetson 33 %, onboard 3 % |
| mesh_mission | heate | 3 | 0.1000 | **0.1798 ± 0.0061** | 0.224 | 0.998 | 133 | 24.1 | 50 | 3.28 | 74.3 | 0.00 |  | laptop 59 %, jetson 38 %, onboard 4 % |
| mesh_mission | noprice | 3 | 0.0916 | **0.1824 ± 0.0022** | 0.229 | 1.000 | 167 | 23.0 | 59 | 4.24 | 83.6 | 0.43 |  | laptop 58 %, jetson 31 %, onboard 11 % |
| mesh_mission | fixlap | 3 | 0.0576 | **0.1051 ± 0.0089** | 0.249 | 0.640 | 28557 | 14.6 | 37 | 2.23 | 64.9 | 0.00 |  | laptop 100 % |
| mesh_mission | aoithr | 3 | 0.0558 | **0.1384 ± 0.0020** | 0.230 | 1.000 | 233 | 9.2 | 73 | 2.17 | 67.4 | 0.00 |  | laptop 61 %, jetson 39 % |
| multihop | v41 | 3 | 0.0480 | **0.1373 ± 0.0076** | 0.224 | 0.999 | 233 | 11.4 | 108 | 2.81 | 68.2 | 0.00 |  | jetson 75 %, laptop 21 %, onboard 5 % |
| multihop | v41e | 3 | 0.0459 | **0.1004 ± 0.0043** | 0.166 | 0.986 | 211 | 17.0 | 76 | 2.86 | 69.6 | 0.00 |  | jetson 67 %, laptop 29 %, onboard 4 % |
| multihop | heat | 3 | 0.0487 | **0.1374 ± 0.0035** | 0.220 | 0.998 | 233 | 11.9 | 111 | 3.30 | 74.2 | 0.00 |  | jetson 71 %, laptop 21 %, onboard 8 % |
| multihop | heate | 3 | 0.0445 | **0.0987 ± 0.0105** | 0.165 | 0.987 | 211 | 17.4 | 77 | 3.26 | 75.0 | 0.00 |  | jetson 65 %, laptop 28 %, onboard 6 % |
| multihop | noprice | 3 | 0.0466 | **0.1369 ± 0.0057** | 0.213 | 0.997 | 242 | 13.3 | 124 | 4.40 | 84.2 | 0.60 |  | jetson 63 %, onboard 22 %, laptop 15 % |
| multihop | fixlap | 3 | 0.0165 | **0.0672 ± 0.0060** | 0.244 | 0.125 | 633 | 1.9 | 309 | 1.98 | 62.0 | 0.00 |  | laptop 100 % |
| multihop | aoithr | 3 | 0.0411 | **0.1220 ± 0.0032** | 0.231 | 0.988 | 267 | 7.4 | 109 | 2.15 | 63.9 | 0.00 |  | jetson 77 %, laptop 23 % |
| multihop | hier | 3 | 0.0519 | **0.1506 ± 0.0024** | 0.228 | 1.000 | 200 | 13.5 | 105 | 2.82 | 69.6 | 0.00 |  | jetson 96 %, onboard 4 %, laptop 0 % |
| static_good | v41 | 3 | 0.1174 | **0.2057 ± 0.0090** | 0.240 | 1.000 | 100 | 26.6 | 45 | 2.83 | 70.2 | 0.00 |  | laptop 81 %, jetson 18 %, onboard 0 % |
| static_good | v41e | 3 | 0.1194 | **0.2010 ± 0.0028** | 0.234 | 1.000 | 100 | 28.1 | 48 | 2.82 | 69.6 | 0.00 |  | laptop 76 %, jetson 23 %, onboard 1 % |
| static_good | heat | 3 | 0.1159 | **0.2038 ± 0.0043** | 0.238 | 1.000 | 100 | 27.1 | 46 | 3.34 | 74.0 | 0.00 |  | laptop 79 %, jetson 18 %, onboard 3 % |
| static_good | heate | 3 | 0.1186 | **0.2001 ± 0.0045** | 0.232 | 1.000 | 100 | 28.5 | 48 | 3.30 | 74.2 | 0.00 |  | laptop 74 %, jetson 24 %, onboard 2 % |
| static_good | noprice | 3 | 0.1127 | **0.2028 ± 0.0068** | 0.234 | 1.000 | 100 | 28.2 | 50 | 4.24 | 82.3 | 0.13 |  | laptop 74 %, jetson 19 %, onboard 7 % |
| static_good | fixlap | 3 | 0.1251 | **0.2100 ± 0.0054** | 0.243 | 1.000 | 100 | 23.2 | 36 | 2.44 | 65.2 | 0.00 |  | laptop 100 % |
| static_good | aoithr | 3 | 0.0613 | **0.1475 ± 0.0035** | 0.230 | 1.000 | 233 | 10.1 | 69 | 2.15 | 65.3 | 0.00 |  | laptop 83 %, jetson 17 % |
| ALL | v41 | 9 | 0.0867 | **0.1762 ± 0.0235** | 0.234 | 0.999 | 167 | 19.7 | 68 | 2.83 | 69.5 | 0.00 |  | laptop 63 %, jetson 36 %, onboard 2 % |
| ALL | v41e | 9 | 0.0884 | **0.1605 ± 0.0354** | 0.208 | 0.995 | 148 | 22.9 | 58 | 2.83 | 69.6 | 0.00 |  | laptop 58 %, jetson 40 %, onboard 2 % |
| ALL | heat | 9 | 0.0867 | **0.1759 ± 0.0230** | 0.232 | 0.999 | 167 | 20.2 | 70 | 3.29 | 74.3 | 0.00 |  | laptop 61 %, jetson 35 %, onboard 4 % |
| ALL | heate | 9 | 0.0877 | **0.1595 ± 0.0358** | 0.207 | 0.995 | 148 | 23.3 | 58 | 3.28 | 74.5 | 0.00 |  | laptop 57 %, jetson 39 %, onboard 4 % |
| ALL | noprice | 9 | 0.0836 | **0.1740 ± 0.0225** | 0.225 | 0.999 | 170 | 21.5 | 78 | 4.29 | 83.4 | 0.39 |  | laptop 55 %, jetson 33 %, onboard 12 % |
| ALL | fixlap | 9 | 0.0664 | **0.1274 ± 0.0494** | 0.245 | 0.588 | 9764 | 13.2 | 127 | 2.22 | 64.0 | 0.00 |  | laptop 100 % |
| ALL | aoithr | 9 | 0.0527 | **0.1360 ± 0.0087** | 0.230 | 0.996 | 245 | 8.9 | 84 | 2.16 | 65.5 | 0.00 |  | laptop 57 %, jetson 43 % |

## Paired differences (same scenario and repetition)
| comparison | scope | metric | pairs | Δ ± 95 % CI | first ahead | p |
|---|---|---|---|---|---|---|
| v41e-v41 | mesh_mission | sAP_fc | 3 | -0.0053 ± 0.0050 | 0/3 | 0.250 |
| v41e-v41 | mesh_mission | sAP | 3 | +0.0052 ± 0.0042 | 3/3 | 0.250 |
| v41e-v41 | mesh_mission | p_aoi300 | 3 | -0.0011 ± 0.0057 | 1/3 | 0.750 |
| v41e-v41 | mesh_mission | deadline_met_fps | 3 | +2.5611 ± 1.0786 | 3/3 | 0.250 |
| v41e-v41 | mesh_mission | pi_w | 3 | -0.0142 ± 0.0074 | 0/3 | 0.250 |
| v41e-v41 | mesh_mission | pi_temp_c | 3 | -0.5992 ± 2.0752 | 1/3 | 0.500 |
| v41e-v41 | multihop | sAP_fc | 3 | -0.0369 ± 0.0105 | 0/3 | 0.250 |
| v41e-v41 | multihop | sAP | 3 | -0.0021 ± 0.0066 | 1/3 | 0.500 |
| v41e-v41 | multihop | p_aoi300 | 3 | -0.0129 ± 0.0100 | 0/3 | 0.250 |
| v41e-v41 | multihop | deadline_met_fps | 3 | +5.6000 ± 0.9626 | 3/3 | 0.250 |
| v41e-v41 | multihop | pi_w | 3 | +0.0437 ± 0.0286 | 3/3 | 0.250 |
| v41e-v41 | multihop | pi_temp_c | 3 | +1.4150 ± 3.9372 | 3/3 | 0.250 |
| v41e-v41 | static_good | sAP_fc | 3 | -0.0047 ± 0.0062 | 0/3 | 0.250 |
| v41e-v41 | static_good | sAP | 3 | +0.0020 ± 0.0039 | 3/3 | 0.250 |
| v41e-v41 | static_good | p_aoi300 | 3 | +0.0000 ± 0.0002 | 1/3 | 1.000 |
| v41e-v41 | static_good | deadline_met_fps | 3 | +1.4208 ± 0.3000 | 3/3 | 0.250 |
| v41e-v41 | static_good | pi_w | 3 | -0.0100 ± 0.0469 | 1/3 | 0.500 |
| v41e-v41 | static_good | pi_temp_c | 3 | -0.6105 ± 7.1602 | 2/3 | 1.000 |
| v41e-v41 | ALL | sAP_fc | 9 | -0.0156 ± 0.0125 | 0/9 | 0.004 |
| v41e-v41 | ALL | sAP | 9 | +0.0017 ± 0.0028 | 7/9 | 0.184 |
| v41e-v41 | ALL | p_aoi300 | 9 | -0.0047 ± 0.0051 | 2/9 | 0.109 |
| v41e-v41 | ALL | deadline_met_fps | 9 | +3.1940 ± 1.4586 | 9/9 | 0.004 |
| v41e-v41 | ALL | pi_w | 9 | +0.0065 ± 0.0232 | 4/9 | 0.539 |
| v41e-v41 | ALL | pi_temp_c | 9 | +0.0685 ± 1.5212 | 6/9 | 0.910 |
| heat-v41 | mesh_mission | sAP_fc | 3 | +0.0011 ± 0.0051 | 2/3 | 0.500 |
| heat-v41 | mesh_mission | sAP | 3 | +0.0010 ± 0.0081 | 2/3 | 0.750 |
| heat-v41 | mesh_mission | p_aoi300 | 3 | -0.0000 ± 0.0014 | 1/3 | 1.000 |
| heat-v41 | mesh_mission | deadline_met_fps | 3 | +0.4542 ± 0.9262 | 3/3 | 0.250 |
| heat-v41 | mesh_mission | pi_w | 3 | +0.3826 ± 0.2000 | 3/3 | 0.250 |
| heat-v41 | mesh_mission | pi_temp_c | 3 | +4.5897 ± 5.3137 | 3/3 | 0.250 |
| heat-v41 | multihop | sAP_fc | 3 | +0.0001 ± 0.0075 | 2/3 | 1.000 |
| heat-v41 | multihop | sAP | 3 | +0.0007 ± 0.0033 | 2/3 | 0.500 |
| heat-v41 | multihop | p_aoi300 | 3 | -0.0007 ± 0.0035 | 1/3 | 0.500 |
| heat-v41 | multihop | deadline_met_fps | 3 | +0.5167 ± 0.1241 | 3/3 | 0.250 |
| heat-v41 | multihop | pi_w | 3 | +0.4838 ± 0.3174 | 3/3 | 0.250 |
| heat-v41 | multihop | pi_temp_c | 3 | +6.0192 ± 2.2148 | 3/3 | 0.250 |
| heat-v41 | static_good | sAP_fc | 3 | -0.0019 ± 0.0089 | 1/3 | 0.500 |
| heat-v41 | static_good | sAP | 3 | -0.0015 ± 0.0124 | 1/3 | 0.750 |
| heat-v41 | static_good | p_aoi300 | 3 | +0.0003 ± 0.0014 | 1/3 | 1.000 |
| heat-v41 | static_good | deadline_met_fps | 3 | +0.4764 ± 0.1302 | 3/3 | 0.250 |
| heat-v41 | static_good | pi_w | 3 | +0.5068 ± 0.1772 | 3/3 | 0.250 |
| heat-v41 | static_good | pi_temp_c | 3 | +3.7743 ± 3.1244 | 3/3 | 0.250 |
| heat-v41 | ALL | sAP_fc | 9 | -0.0002 ± 0.0022 | 5/9 | 0.805 |
| heat-v41 | ALL | sAP | 9 | +0.0001 ± 0.0025 | 5/9 | 0.969 |
| heat-v41 | ALL | p_aoi300 | 9 | -0.0001 ± 0.0007 | 3/9 | 0.719 |
| heat-v41 | ALL | deadline_met_fps | 9 | +0.4824 ± 0.1478 | 9/9 | 0.004 |
| heat-v41 | ALL | pi_w | 9 | +0.4577 ± 0.0780 | 9/9 | 0.004 |
| heat-v41 | ALL | pi_temp_c | 9 | +4.7944 ± 1.2673 | 9/9 | 0.004 |
| heate-v41 | mesh_mission | sAP_fc | 3 | -0.0057 ± 0.0067 | 0/3 | 0.250 |
| heate-v41 | mesh_mission | sAP | 3 | +0.0052 ± 0.0059 | 3/3 | 0.250 |
| heate-v41 | mesh_mission | p_aoi300 | 3 | -0.0020 ± 0.0098 | 1/3 | 1.000 |
| heate-v41 | mesh_mission | deadline_met_fps | 3 | +2.9833 ± 1.2856 | 3/3 | 0.250 |
| heate-v41 | mesh_mission | pi_w | 3 | +0.4377 ± 0.1703 | 3/3 | 0.250 |
| heate-v41 | mesh_mission | pi_temp_c | 3 | +4.1373 ± 2.8415 | 3/3 | 0.250 |
| heate-v41 | multihop | sAP_fc | 3 | -0.0386 ± 0.0065 | 0/3 | 0.250 |
| heate-v41 | multihop | sAP | 3 | -0.0035 ± 0.0043 | 0/3 | 0.250 |
| heate-v41 | multihop | p_aoi300 | 3 | -0.0114 ± 0.0126 | 0/3 | 0.250 |
| heate-v41 | multihop | deadline_met_fps | 3 | +5.9861 ± 1.5972 | 3/3 | 0.250 |
| heate-v41 | multihop | pi_w | 3 | +0.4515 ± 0.1548 | 3/3 | 0.250 |
| heate-v41 | multihop | pi_temp_c | 3 | +6.7845 ± 5.8348 | 3/3 | 0.250 |
| heate-v41 | static_good | sAP_fc | 3 | -0.0056 ± 0.0057 | 0/3 | 0.250 |
| heate-v41 | static_good | sAP | 3 | +0.0012 ± 0.0059 | 2/3 | 0.750 |
| heate-v41 | static_good | p_aoi300 | 3 | +0.0003 ± 0.0014 | 1/3 | 1.000 |
| heate-v41 | static_good | deadline_met_fps | 3 | +1.8819 ± 0.5582 | 3/3 | 0.250 |
| heate-v41 | static_good | pi_w | 3 | +0.4661 ± 0.3320 | 3/3 | 0.250 |
| heate-v41 | static_good | pi_temp_c | 3 | +3.9664 ± 1.9017 | 3/3 | 0.250 |
| heate-v41 | ALL | sAP_fc | 9 | -0.0166 ± 0.0128 | 0/9 | 0.004 |
| heate-v41 | ALL | sAP | 9 | +0.0010 ± 0.0033 | 5/9 | 0.500 |
| heate-v41 | ALL | p_aoi300 | 9 | -0.0044 ± 0.0048 | 2/9 | 0.125 |
| heate-v41 | ALL | deadline_met_fps | 9 | +3.6171 ± 1.4543 | 9/9 | 0.004 |
| heate-v41 | ALL | pi_w | 9 | +0.4517 ± 0.0634 | 9/9 | 0.004 |
| heate-v41 | ALL | pi_temp_c | 9 | +4.9627 ± 1.4866 | 9/9 | 0.004 |
| noprice-v41 | mesh_mission | sAP_fc | 3 | -0.0032 ± 0.0051 | 0/3 | 0.250 |
| noprice-v41 | mesh_mission | sAP | 3 | -0.0031 ± 0.0052 | 0/3 | 0.250 |
| noprice-v41 | mesh_mission | p_aoi300 | 3 | +0.0002 ± 0.0008 | 1/3 | 1.000 |
| noprice-v41 | mesh_mission | deadline_met_fps | 3 | +1.9278 ± 1.1321 | 3/3 | 0.250 |
| noprice-v41 | mesh_mission | pi_w | 3 | +1.4025 ± 0.2479 | 3/3 | 0.250 |
| noprice-v41 | mesh_mission | pi_temp_c | 3 | +13.3917 ± 4.0388 | 3/3 | 0.250 |
| noprice-v41 | multihop | sAP_fc | 3 | -0.0004 ± 0.0062 | 1/3 | 0.750 |
| noprice-v41 | multihop | sAP | 3 | -0.0014 ± 0.0001 | 0/3 | 0.250 |
| noprice-v41 | multihop | p_aoi300 | 3 | -0.0016 ± 0.0049 | 0/3 | 0.250 |
| noprice-v41 | multihop | deadline_met_fps | 3 | +1.9236 ± 0.2570 | 3/3 | 0.250 |
| noprice-v41 | multihop | pi_w | 3 | +1.5850 ± 0.2827 | 3/3 | 0.250 |
| noprice-v41 | multihop | pi_temp_c | 3 | +16.0180 ± 4.4948 | 3/3 | 0.250 |
| noprice-v41 | static_good | sAP_fc | 3 | -0.0029 ± 0.0023 | 0/3 | 0.250 |
| noprice-v41 | static_good | sAP | 3 | -0.0047 ± 0.0033 | 0/3 | 0.250 |
| noprice-v41 | static_good | p_aoi300 | 3 | +0.0003 ± 0.0014 | 1/3 | 1.000 |
| noprice-v41 | static_good | deadline_met_fps | 3 | +1.5333 ± 0.1254 | 3/3 | 0.250 |
| noprice-v41 | static_good | pi_w | 3 | +1.4105 ± 0.1806 | 3/3 | 0.250 |
| noprice-v41 | static_good | pi_temp_c | 3 | +12.0488 ± 3.5103 | 3/3 | 0.250 |
| noprice-v41 | ALL | sAP_fc | 9 | -0.0021 ± 0.0016 | 1/9 | 0.027 |
| noprice-v41 | ALL | sAP | 9 | -0.0031 ± 0.0015 | 0/9 | 0.004 |
| noprice-v41 | ALL | p_aoi300 | 9 | -0.0004 ± 0.0011 | 2/9 | 0.625 |
| noprice-v41 | ALL | deadline_met_fps | 9 | +1.7949 ± 0.2358 | 9/9 | 0.004 |
| noprice-v41 | ALL | pi_w | 9 | +1.4660 ± 0.0944 | 9/9 | 0.004 |
| noprice-v41 | ALL | pi_temp_c | 9 | +13.8195 ± 1.7283 | 9/9 | 0.004 |
| fixlap-v41 | mesh_mission | sAP_fc | 3 | -0.0804 ± 0.0125 | 0/3 | 0.250 |
| fixlap-v41 | mesh_mission | sAP | 3 | -0.0371 ± 0.0127 | 0/3 | 0.250 |
| fixlap-v41 | mesh_mission | p_aoi300 | 3 | -0.3597 ± 0.0153 | 0/3 | 0.250 |
| fixlap-v41 | mesh_mission | deadline_met_fps | 3 | -6.5417 ± 1.3391 | 0/3 | 0.250 |
| fixlap-v41 | mesh_mission | pi_w | 3 | -0.6065 ± 0.1287 | 0/3 | 0.250 |
| fixlap-v41 | mesh_mission | pi_temp_c | 3 | -5.3069 ± 1.1294 | 0/3 | 0.250 |
| fixlap-v41 | multihop | sAP_fc | 3 | -0.0701 ± 0.0030 | 0/3 | 0.250 |
| fixlap-v41 | multihop | sAP | 3 | -0.0315 ± 0.0006 | 0/3 | 0.250 |
| fixlap-v41 | multihop | p_aoi300 | 3 | -0.8738 ± 0.0420 | 0/3 | 0.250 |
| fixlap-v41 | multihop | deadline_met_fps | 3 | -9.5097 ± 0.0570 | 0/3 | 0.250 |
| fixlap-v41 | multihop | pi_w | 3 | -0.8330 ± 0.0789 | 0/3 | 0.250 |
| fixlap-v41 | multihop | pi_temp_c | 3 | -6.2029 ± 5.7338 | 0/3 | 0.250 |
| fixlap-v41 | static_good | sAP_fc | 3 | +0.0043 ± 0.0125 | 3/3 | 0.250 |
| fixlap-v41 | static_good | sAP | 3 | +0.0077 ± 0.0106 | 3/3 | 0.250 |
| fixlap-v41 | static_good | p_aoi300 | 3 | +0.0001 ± 0.0006 | 1/3 | 1.000 |
| fixlap-v41 | static_good | deadline_met_fps | 3 | -3.4764 ± 0.0880 | 0/3 | 0.250 |
| fixlap-v41 | static_good | pi_w | 3 | -0.3917 ± 0.1629 | 0/3 | 0.250 |
| fixlap-v41 | static_good | pi_temp_c | 3 | -5.0679 ± 8.4855 | 0/3 | 0.250 |
| fixlap-v41 | ALL | sAP_fc | 9 | -0.0487 ± 0.0310 | 3/9 | 0.031 |
| fixlap-v41 | ALL | sAP | 9 | -0.0203 ± 0.0165 | 3/9 | 0.031 |
| fixlap-v41 | ALL | p_aoi300 | 9 | -0.4111 ± 0.2930 | 1/9 | 0.031 |
| fixlap-v41 | ALL | deadline_met_fps | 9 | -6.5093 ± 2.0225 | 0/9 | 0.004 |
| fixlap-v41 | ALL | pi_w | 9 | -0.6104 ± 0.1511 | 0/9 | 0.004 |
| fixlap-v41 | ALL | pi_temp_c | 9 | -5.5259 ± 1.6469 | 0/9 | 0.004 |
| aoithr-v41 | mesh_mission | sAP_fc | 3 | -0.0471 ± 0.0042 | 0/3 | 0.250 |
| aoithr-v41 | mesh_mission | sAP | 3 | -0.0389 ± 0.0025 | 0/3 | 0.250 |
| aoithr-v41 | mesh_mission | p_aoi300 | 3 | -0.0000 ± 0.0011 | 1/3 | 1.000 |
| aoithr-v41 | mesh_mission | deadline_met_fps | 3 | -11.9444 ± 0.8839 | 0/3 | 0.250 |
| aoithr-v41 | mesh_mission | pi_w | 3 | -0.6692 ± 0.0876 | 0/3 | 0.250 |
| aoithr-v41 | mesh_mission | pi_temp_c | 3 | -2.7796 ± 2.0141 | 0/3 | 0.250 |
| aoithr-v41 | multihop | sAP_fc | 3 | -0.0153 ± 0.0061 | 0/3 | 0.250 |
| aoithr-v41 | multihop | sAP | 3 | -0.0069 ± 0.0009 | 0/3 | 0.250 |
| aoithr-v41 | multihop | p_aoi300 | 3 | -0.0105 ± 0.0064 | 0/3 | 0.250 |
| aoithr-v41 | multihop | deadline_met_fps | 3 | -3.9597 ± 0.2416 | 0/3 | 0.250 |
| aoithr-v41 | multihop | pi_w | 3 | -0.6624 ± 0.0266 | 0/3 | 0.250 |
| aoithr-v41 | multihop | pi_temp_c | 3 | -4.2659 ± 4.6327 | 0/3 | 0.250 |
| aoithr-v41 | static_good | sAP_fc | 3 | -0.0582 ± 0.0125 | 0/3 | 0.250 |
| aoithr-v41 | static_good | sAP | 3 | -0.0561 ± 0.0138 | 0/3 | 0.250 |
| aoithr-v41 | static_good | p_aoi300 | 3 | +0.0003 ± 0.0014 | 1/3 | 1.000 |
| aoithr-v41 | static_good | deadline_met_fps | 3 | -16.5056 ± 0.5145 | 0/3 | 0.250 |
| aoithr-v41 | static_good | pi_w | 3 | -0.6822 ± 0.0264 | 0/3 | 0.250 |
| aoithr-v41 | static_good | pi_temp_c | 3 | -4.9547 ± 2.4627 | 0/3 | 0.250 |
| aoithr-v41 | ALL | sAP_fc | 9 | -0.0402 ± 0.0150 | 0/9 | 0.004 |
| aoithr-v41 | ALL | sAP | 9 | -0.0340 ± 0.0168 | 0/9 | 0.004 |
| aoithr-v41 | ALL | p_aoi300 | 9 | -0.0034 ± 0.0042 | 2/9 | 0.188 |
| aoithr-v41 | ALL | deadline_met_fps | 9 | -10.8032 ± 4.2378 | 0/9 | 0.004 |
| aoithr-v41 | ALL | pi_w | 9 | -0.6713 ± 0.0162 | 0/9 | 0.004 |
| aoithr-v41 | ALL | pi_temp_c | 9 | -4.0001 ± 1.1441 | 0/9 | 0.004 |
| hier-v41 | multihop | sAP_fc | 3 | +0.0133 ± 0.0057 | 3/3 | 0.250 |
| hier-v41 | multihop | sAP | 3 | +0.0039 ± 0.0008 | 3/3 | 0.250 |
| hier-v41 | multihop | p_aoi300 | 3 | +0.0011 ± 0.0014 | 3/3 | 0.250 |
| hier-v41 | multihop | deadline_met_fps | 3 | +2.1333 ± 0.3702 | 3/3 | 0.250 |
| hier-v41 | multihop | pi_w | 3 | +0.0071 ± 0.0289 | 2/3 | 0.500 |
| hier-v41 | multihop | pi_temp_c | 3 | +1.4244 ± 2.8433 | 3/3 | 0.250 |
| hier-v41 | ALL | sAP_fc | 3 | +0.0133 ± 0.0057 | 3/3 | 0.250 |
| hier-v41 | ALL | sAP | 3 | +0.0039 ± 0.0008 | 3/3 | 0.250 |
| hier-v41 | ALL | p_aoi300 | 3 | +0.0011 ± 0.0014 | 3/3 | 0.250 |
| hier-v41 | ALL | deadline_met_fps | 3 | +2.1333 ± 0.3702 | 3/3 | 0.250 |
| hier-v41 | ALL | pi_w | 3 | +0.0071 ± 0.0289 | 2/3 | 0.500 |
| hier-v41 | ALL | pi_temp_c | 3 | +1.4244 ± 2.8433 | 3/3 | 0.250 |
| heate-heat | mesh_mission | sAP_fc | 3 | -0.0068 ± 0.0115 | 0/3 | 0.250 |
| heate-heat | mesh_mission | sAP | 3 | +0.0043 ± 0.0135 | 2/3 | 0.500 |
| heate-heat | mesh_mission | p_aoi300 | 3 | -0.0020 ± 0.0098 | 1/3 | 1.000 |
| heate-heat | mesh_mission | deadline_met_fps | 3 | +2.5292 ± 1.6695 | 3/3 | 0.250 |
| heate-heat | mesh_mission | pi_w | 3 | +0.0551 ± 0.3567 | 2/3 | 0.750 |
| heate-heat | mesh_mission | pi_temp_c | 3 | -0.4524 ± 2.7019 | 1/3 | 0.750 |
| heate-heat | multihop | sAP_fc | 3 | -0.0387 ± 0.0079 | 0/3 | 0.250 |
| heate-heat | multihop | sAP | 3 | -0.0042 ± 0.0021 | 0/3 | 0.250 |
| heate-heat | multihop | p_aoi300 | 3 | -0.0107 ± 0.0104 | 0/3 | 0.250 |
| heate-heat | multihop | deadline_met_fps | 3 | +5.4694 ± 1.6243 | 3/3 | 0.250 |
| heate-heat | multihop | pi_w | 3 | -0.0323 ± 0.4610 | 2/3 | 1.000 |
| heate-heat | multihop | pi_temp_c | 3 | +0.7653 ± 4.4691 | 2/3 | 0.750 |
| heate-heat | static_good | sAP_fc | 3 | -0.0037 ± 0.0071 | 0/3 | 0.250 |
| heate-heat | static_good | sAP | 3 | +0.0027 ± 0.0112 | 2/3 | 0.500 |
| heate-heat | static_good | p_aoi300 | 3 | +0.0000 ± 0.0000 | 0/3 | 1.000 |
| heate-heat | static_good | deadline_met_fps | 3 | +1.4056 ± 0.6658 | 3/3 | 0.250 |
| heate-heat | static_good | pi_w | 3 | -0.0407 ± 0.4137 | 1/3 | 0.750 |
| heate-heat | static_good | pi_temp_c | 3 | +0.1921 ± 2.6444 | 2/3 | 0.750 |
| heate-heat | ALL | sAP_fc | 9 | -0.0164 ± 0.0131 | 0/9 | 0.004 |
| heate-heat | ALL | sAP | 9 | +0.0009 ± 0.0041 | 4/9 | 0.602 |
| heate-heat | ALL | p_aoi300 | 9 | -0.0042 ± 0.0044 | 1/9 | 0.125 |
| heate-heat | ALL | deadline_met_fps | 9 | +3.1347 ± 1.4489 | 9/9 | 0.004 |
| heate-heat | ALL | pi_w | 9 | -0.0060 ± 0.1163 | 5/9 | 0.922 |
| heate-heat | ALL | pi_temp_c | 9 | +0.1683 ± 0.9945 | 5/9 | 0.707 |

## mesh_mission phases (sAP + fc)
| strategy | good | ground_congested | camera_out_of_range | edge_uplink_cut | edge_link_slow | recovered |
|---|---|---|---|---|---|---|
| v41 | 0.268 | 0.086 | 0.176 | 0.177 | 0.185 | 0.235 |
| v41e | 0.267 | 0.097 | 0.136 | 0.164 | 0.187 | 0.229 |
| heat | 0.268 | 0.083 | 0.174 | 0.182 | 0.190 | 0.234 |
| heate | 0.264 | 0.100 | 0.141 | 0.164 | 0.185 | 0.229 |
| noprice | 0.265 | 0.082 | 0.172 | 0.179 | 0.179 | 0.236 |
| fixlap | 0.271 | 0.034 | 0.000 | 0.126 | 0.194 | 0.238 |
| aoithr | 0.203 | 0.065 | 0.143 | 0.142 | 0.119 | 0.179 |
