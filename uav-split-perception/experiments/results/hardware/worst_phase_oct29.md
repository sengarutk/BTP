# Worst-phase streaming AP and staleness (VisDrone detectors, headline forecaster)


## vid_campaign_wifi: Part 12 (108 runs, shared Wi-Fi)


**mission**

| Policy | n | sAP | worst-phase sAP | most often worst | miss > 300 ms | longest stale (s) | age p95 (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A_full | 3 | 0.0915 ± 0.0074 | 0.0216 ± 0.0129 | both_degraded | 9.9 % | 0.16 ± 0.05 | 356 |
| A_full_aer | 3 | 0.1055 ± 0.0132 | 0.0177 ± 0.0148 | both_degraded | 20.2 % | 0.18 ± 0.05 | 400 |
| A_stream | 3 | 0.0987 ± 0.0208 | 0.0210 ± 0.0065 | both_degraded | 19.0 % | 0.21 ± 0.05 | 400 |
| abr_laptop | 3 | 0.0429 ± 0.0105 | 0.0003 ± 0.0004 | ground_blackout | 36.2 % | 20.41 ± 0.05 | 17700 |
| fixed_jetson_s640q90 | 3 | 0.0831 ± 0.0415 | 0.0004 ± 0.0010 | total_blackout | 51.0 % | 59.72 ± 0.05 | 15579 |
| fixed_laptop_m640q90 | 3 | 0.0377 ± 0.0062 | 0.0003 ± 0.0006 | ground_blackout | 80.7 % | 84.66 ± 3.92 | 18500 |
| fixed_onboard_n320 | 3 | 0.0605 ± 0.0068 | 0.0316 ± 0.0085 | both_degraded | 0.8 % | 0.99 ± 0.05 | 189 |
| rule_fallback | 3 | 0.0638 ± 0.0031 | 0.0123 ± 0.0007 | both_degraded | 50.5 % | 22.93 ± 0.08 | 1133 |
| static_multi | 3 | 0.0841 ± 0.0162 | 0.0228 ± 0.0067 | both_degraded | 0.0 % | 0.01 ± 0.05 | 189 |

First by mean sAP: A_full_aer; first by worst-phase sAP: fixed_onboard_n320 (different).


**mission_mirror**

| Policy | n | sAP | worst-phase sAP | most often worst | miss > 300 ms | longest stale (s) | age p95 (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A_full | 3 | 0.0859 ± 0.0896 | 0.0203 ± 0.0202 | both_degraded | 19.2 % | 0.49 ± 1.39 | 389 |
| A_full_aer | 3 | 0.1125 ± 0.0179 | 0.0245 ± 0.0038 | both_degraded | 14.0 % | 0.18 ± 0.10 | 389 |
| A_stream | 3 | 0.1183 ± 0.0138 | 0.0254 ± 0.0139 | both_degraded | 14.3 % | 0.18 ± 0.05 | 389 |
| abr_laptop | 3 | 0.0817 ± 0.0374 | 0.0018 ± 0.0008 | total_blackout | 19.8 % | 20.50 ± 0.00 | 14802 |
| fixed_jetson_s640q90 | 3 | 0.0336 ± 0.0025 | 0.0006 ± 0.0007 | edge_blackout | 77.8 % | 75.99 ± 0.19 | 18300 |
| fixed_laptop_m640q90 | 3 | 0.0824 ± 0.0069 | 0.0005 ± 0.0002 | total_blackout | 50.9 % | 60.92 ± 5.11 | 15557 |
| fixed_onboard_n320 | 3 | 0.0599 ± 0.0092 | 0.0295 ± 0.0128 | both_degraded | 0.8 % | 1.00 ± 0.08 | 200 |
| rule_fallback | 3 | 0.1017 ± 0.0094 | 0.0112 ± 0.0018 | both_degraded | 37.7 % | 23.12 ± 0.13 | 1278 |
| static_multi | 3 | 0.0922 ± 0.0090 | 0.0214 ± 0.0171 | both_degraded | 0.0 % | 0.00 ± 0.00 | 222 |

First by mean sAP: A_stream; first by worst-phase sAP: fixed_onboard_n320 (different).


**random**

| Policy | n | sAP | worst-phase sAP | most often worst | miss > 300 ms | longest stale (s) | age p95 (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A_full | 3 | 0.0900 ± 0.0320 | 0.0145 ± 0.0126 | r18_L1J3 | 3.1 % | 0.09 ± 0.21 | 244 |
| A_full_aer | 3 | 0.0996 ± 0.0158 | 0.0068 ± 0.0127 | r18_L1J3 | 8.5 % | 0.17 ± 0.08 | 344 |
| A_stream | 3 | 0.0873 ± 0.0243 | 0.0088 ± 0.0148 | r18_L1J3 | 8.2 % | 0.18 ± 0.05 | 322 |
| abr_laptop | 3 | 0.0769 ± 0.0370 | 0.0000 ± 0.0000 | r26_L4J0 | 18.8 % | 21.24 ± 39.68 | 15546 |
| fixed_jetson_s640q90 | 3 | 0.0617 ± 0.0542 | 0.0000 ± 0.0000 | r19_L1J3 | 64.9 % | 45.92 ± 73.10 | 8667 |
| fixed_laptop_m640q90 | 3 | 0.0690 ± 0.0763 | 0.0000 ± 0.0000 | r26_L4J0 | 55.1 % | 36.29 ± 34.47 | 15946 |
| fixed_onboard_n320 | 3 | 0.0597 ± 0.0070 | 0.0148 ± 0.0030 | r18_L1J3 | 0.8 % | 0.99 ± 0.10 | 189 |
| rule_fallback | 3 | 0.0685 ± 0.0358 | 0.0010 ± 0.0032 | r18_L1J3 | 54.9 % | 21.28 ± 24.13 | 1044 |
| static_multi | 3 | 0.0750 ± 0.0261 | 0.0129 ± 0.0085 | r18_L1J3 | 0.0 % | 0.00 ± 0.00 | 189 |

First by mean sAP: A_full_aer; first by worst-phase sAP: fixed_onboard_n320 (different).


**static_good**

| Policy | n | sAP | worst-phase sAP | most often worst | miss > 300 ms | longest stale (s) | age p95 (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A_full | 3 | 0.1445 ± 0.0291 | 0.0691 ± 0.0861 | good3 | 1.3 % | 0.14 ± 0.42 | 178 |
| A_full_aer | 3 | 0.1331 ± 0.1070 | 0.0618 ± 0.0831 | good3 | 2.8 % | 0.06 ± 0.24 | 244 |
| A_stream | 3 | 0.1144 ± 0.1448 | 0.0462 ± 0.0777 | good3 | 14.0 % | 0.30 ± 0.44 | 322 |
| abr_laptop | 3 | 0.1534 ± 0.0452 | 0.0654 ± 0.0156 | good3 | 2.1 % | 1.62 ± 3.59 | 222 |
| fixed_jetson_s640q90 | 3 | 0.1432 ± 0.0232 | 0.0545 ± 0.0217 | good3 | 6.4 % | 2.13 ± 2.79 | 378 |
| fixed_laptop_m640q90 | 3 | 0.1718 ± 0.0287 | 0.0495 ± 0.0222 | good3 | 1.4 % | 1.21 ± 4.78 | 222 |
| fixed_onboard_n320 | 3 | 0.0574 ± 0.0034 | 0.0281 ± 0.0085 | good3 | 0.8 % | 0.99 ± 0.05 | 200 |
| rule_fallback | 3 | 0.1654 ± 0.0131 | 0.0713 ± 0.0427 | good3 | 1.5 % | 0.61 ± 1.99 | 222 |
| static_multi | 3 | 0.1225 ± 0.0191 | 0.0720 ± 0.0233 | good3 | 0.0 % | 0.01 ± 0.05 | 133 |

First by mean sAP: fixed_laptop_m640q90; first by worst-phase sAP: static_multi (different).

Paired worst-phase sAP against A_full: 32 unique comparisons, 0 significant after Holm.


## vid_campaign_wifi_fc: Part 14 (forecaster v1 campaign)


**mission**

| Policy | n | sAP | worst-phase sAP | most often worst | miss > 300 ms | longest stale (s) | age p95 (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A_full | 3 | 0.0805 ± 0.0356 | 0.0227 ± 0.0164 | both_degraded | 14.1 % | 0.27 ± 0.36 | 400 |
| A_stream | 3 | 0.0962 ± 0.0094 | 0.0200 ± 0.0018 | both_degraded | 21.1 % | 0.21 ± 0.05 | 422 |
| A_stream_fc | 3 | 0.0898 ± 0.0594 | 0.0246 ± 0.0029 | both_degraded | 0.1 % | 0.03 ± 0.14 | 233 |

First by mean sAP: A_stream; first by worst-phase sAP: A_stream_fc (different).


**mission_mirror**

| Policy | n | sAP | worst-phase sAP | most often worst | miss > 300 ms | longest stale (s) | age p95 (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A_full | 3 | 0.0825 ± 0.1046 | 0.0163 ± 0.0067 | both_degraded | 20.7 % | 0.30 ± 0.50 | 411 |
| A_stream | 3 | 0.1126 ± 0.0548 | 0.0223 ± 0.0040 | both_degraded | 15.8 % | 0.20 ± 0.00 | 411 |
| A_stream_fc | 3 | 0.1158 ± 0.0172 | 0.0183 ± 0.0057 | both_degraded | 0.0 % | 0.02 ± 0.05 | 233 |

First by mean sAP: A_stream_fc; first by worst-phase sAP: A_stream (different).


**random**

| Policy | n | sAP | worst-phase sAP | most often worst | miss > 300 ms | longest stale (s) | age p95 (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A_full | 3 | 0.0911 ± 0.0351 | 0.0095 ± 0.0043 | r18_L2J4 | 6.3 % | 0.19 ± 0.05 | 322 |
| A_stream | 3 | 0.0972 ± 0.0334 | 0.0078 ± 0.0123 | r18_L2J4 | 10.6 % | 0.20 ± 0.00 | 378 |
| A_stream_fc | 3 | 0.0831 ± 0.0323 | 0.0118 ± 0.0027 | r18_L2J4 | 0.0 % | 0.01 ± 0.05 | 233 |

First by mean sAP: A_stream; first by worst-phase sAP: A_stream_fc (different).


**static_good**

| Policy | n | sAP | worst-phase sAP | most often worst | miss > 300 ms | longest stale (s) | age p95 (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A_full | 3 | 0.1795 ± 0.0087 | 0.0920 ± 0.0269 | good3 | 0.1 % | 0.02 ± 0.10 | 133 |
| A_stream | 3 | 0.1845 ± 0.0199 | 0.0653 ± 0.0746 | good3 | 0.6 % | 0.11 ± 0.29 | 178 |
| A_stream_fc | 3 | 0.1732 ± 0.0302 | 0.0741 ± 0.0236 | good3 | 0.7 % | 0.16 ± 0.67 | 167 |

First by mean sAP: A_stream; first by worst-phase sAP: A_full (different).

Paired worst-phase sAP against A_full: 8 unique comparisons, 0 significant after Holm.


## vid_campaign_wifi_fc2: Part 14 (80-run campaign, live forecaster v2)


**mission**

| Policy | n | sAP | worst-phase sAP | most often worst | miss > 300 ms | longest stale (s) | age p95 (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A_full | 5 | 0.0818 ± 0.0165 | 0.0202 ± 0.0078 | both_degraded | 16.8 % | 0.24 ± 0.07 | 427 |
| A_stream_fc | 5 | 0.1118 ± 0.0119 | 0.0232 ± 0.0086 | both_degraded | 0.2 % | 0.27 ± 0.56 | 220 |
| A_stream_fc2 | 5 | 0.1114 ± 0.0121 | 0.0232 ± 0.0096 | both_degraded | 0.1 % | 0.07 ± 0.14 | 227 |
| fixed_laptop_m640q90 | 5 | 0.0387 ± 0.0014 | 0.0005 ± 0.0005 | ground_blackout | 81.5 % | 87.01 ± 4.45 | 19014 |

First by mean sAP: A_stream_fc; first by worst-phase sAP: A_stream_fc.


**mission_mirror**

| Policy | n | sAP | worst-phase sAP | most often worst | miss > 300 ms | longest stale (s) | age p95 (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A_full | 5 | 0.1106 ± 0.0336 | 0.0235 ± 0.0055 | both_degraded | 14.9 % | 0.34 ± 0.34 | 420 |
| A_stream_fc | 5 | 0.1164 ± 0.0300 | 0.0194 ± 0.0031 | both_degraded | 0.2 % | 0.09 ± 0.15 | 233 |
| A_stream_fc2 | 5 | 0.1292 ± 0.0117 | 0.0203 ± 0.0067 | both_degraded | 0.0 % | 0.01 ± 0.02 | 233 |
| fixed_laptop_m640q90 | 5 | 0.0933 ± 0.0211 | 0.0004 ± 0.0003 | total_blackout | 51.7 % | 59.71 ± 0.02 | 15615 |

First by mean sAP: A_stream_fc2; first by worst-phase sAP: A_full (different).


**random**

| Policy | n | sAP | worst-phase sAP | most often worst | miss > 300 ms | longest stale (s) | age p95 (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A_full | 5 | 0.0814 ± 0.0248 | 0.0078 ± 0.0054 | r18_L1J3 | 12.3 % | 0.37 ± 0.49 | 347 |
| A_stream_fc | 5 | 0.0883 ± 0.0190 | 0.0101 ± 0.0015 | r18_L1J3 | 0.1 % | 0.05 ± 0.07 | 233 |
| A_stream_fc2 | 5 | 0.0795 ± 0.0264 | 0.0102 ± 0.0024 | r19_L1J3 | 0.3 % | 0.27 ± 0.56 | 233 |
| fixed_laptop_m640q90 | 5 | 0.0543 ± 0.0394 | 0.0000 ± 0.0000 | r13_L0J2 | 69.0 % | 54.77 ± 31.09 | 25088 |

First by mean sAP: A_stream_fc; first by worst-phase sAP: A_stream_fc2 (different).


**static_good**

| Policy | n | sAP | worst-phase sAP | most often worst | miss > 300 ms | longest stale (s) | age p95 (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A_full | 5 | 0.1614 ± 0.0739 | 0.0821 ± 0.0476 | good3 | 7.1 % | 0.25 ± 0.57 | 160 |
| A_stream_fc | 5 | 0.1455 ± 0.0964 | 0.0711 ± 0.0502 | good3 | 0.3 % | 0.28 ± 0.54 | 160 |
| A_stream_fc2 | 5 | 0.1764 ± 0.0719 | 0.0852 ± 0.0411 | good3 | 0.3 % | 0.21 ± 0.57 | 127 |
| fixed_laptop_m640q90 | 5 | 0.1574 ± 0.1087 | 0.0684 ± 0.0554 | good3 | 21.9 % | 17.77 ± 46.49 | 15874 |

First by mean sAP: A_stream_fc2; first by worst-phase sAP: A_stream_fc2.

Paired worst-phase sAP against A_full, A_stream_fc2: 20 unique comparisons, 0 significant after Holm.


## vid_campaign_energy: G9 (energy campaign)


**mission**

| Policy | n | sAP | worst-phase sAP | most often worst | miss > 300 ms | longest stale (s) | age p95 (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A_eco | 5 | 0.1023 ± 0.0151 | 0.0227 ± 0.0102 | both_degraded | 13.4 % | 4.67 ± 1.77 | 511 |
| A_eco_tight | 5 | 0.1141 ± 0.0152 | 0.0196 ± 0.0093 | both_degraded | 14.1 % | 5.32 ± 3.75 | 505 |
| A_full | 5 | 0.0833 ± 0.0131 | 0.0262 ± 0.0031 | both_degraded | 15.8 % | 0.27 ± 0.00 | 447 |
| A_stream_fc2 | 5 | 0.0848 ± 0.0219 | 0.0208 ± 0.0042 | both_degraded | 0.2 % | 0.19 ± 0.47 | 247 |
| fixed_laptop_m640q90 | 5 | 0.0397 ± 0.0021 | 0.0005 ± 0.0002 | ground_blackout | 79.9 % | 84.06 ± 3.55 | 18428 |

First by mean sAP: A_eco_tight; first by worst-phase sAP: A_full (different).


**mission_mirror**

| Policy | n | sAP | worst-phase sAP | most often worst | miss > 300 ms | longest stale (s) | age p95 (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A_eco | 5 | 0.1162 ± 0.0259 | 0.0169 ± 0.0058 | both_degraded | 16.5 % | 2.57 ± 1.26 | 467 |
| A_eco_tight | 5 | 0.1249 ± 0.0241 | 0.0226 ± 0.0045 | both_degraded | 10.8 % | 2.09 ± 2.34 | 427 |
| A_full | 5 | 0.1097 ± 0.0301 | 0.0205 ± 0.0023 | both_degraded | 15.9 % | 0.39 ± 0.38 | 447 |
| A_stream_fc2 | 5 | 0.1242 ± 0.0222 | 0.0158 ± 0.0024 | both_degraded | 0.3 % | 0.05 ± 0.02 | 267 |
| fixed_laptop_m640q90 | 5 | 0.0902 ± 0.0025 | 0.0005 ± 0.0001 | total_blackout | 50.7 % | 59.71 ± 0.02 | 15595 |

First by mean sAP: A_eco_tight; first by worst-phase sAP: A_eco_tight.


**random**

| Policy | n | sAP | worst-phase sAP | most often worst | miss > 300 ms | longest stale (s) | age p95 (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A_eco | 5 | 0.1033 ± 0.0175 | 0.0087 ± 0.0057 | r19_L1J3 | 13.6 % | 2.57 ± 3.38 | 413 |
| A_eco_tight | 5 | 0.1047 ± 0.0116 | 0.0079 ± 0.0071 | r18_L1J3 | 16.8 % | 3.69 ± 4.92 | 447 |
| A_full | 5 | 0.0942 ± 0.0136 | 0.0101 ± 0.0067 | r18_L1J3 | 7.0 % | 0.20 ± 0.08 | 313 |
| A_stream_fc2 | 5 | 0.0766 ± 0.0133 | 0.0100 ± 0.0024 | r18_L1J3 | 0.2 % | 0.08 ± 0.16 | 253 |
| fixed_laptop_m640q90 | 5 | 0.0710 ± 0.0257 | 0.0000 ± 0.0000 | r26_L4J0 | 59.4 % | 42.17 ± 17.21 | 12175 |

First by mean sAP: A_eco_tight; first by worst-phase sAP: A_full (different).


**static_good**

| Policy | n | sAP | worst-phase sAP | most often worst | miss > 300 ms | longest stale (s) | age p95 (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A_eco | 5 | 0.1747 ± 0.0354 | 0.0751 ± 0.0309 | good3 | 2.5 % | 0.59 ± 0.71 | 200 |
| A_eco_tight | 5 | 0.1777 ± 0.0246 | 0.0724 ± 0.0323 | good3 | 2.4 % | 1.27 ± 1.55 | 213 |
| A_full | 5 | 0.1611 ± 0.0347 | 0.0747 ± 0.0343 | good3 | 0.5 % | 0.08 ± 0.14 | 120 |
| A_stream_fc2 | 5 | 0.1602 ± 0.0506 | 0.0587 ± 0.0432 | good3 | 0.4 % | 0.29 ± 0.77 | 187 |
| fixed_laptop_m640q90 | 5 | 0.1818 ± 0.0159 | 0.0720 ± 0.0209 | good3 | 1.8 % | 0.85 ± 1.37 | 220 |

First by mean sAP: fixed_laptop_m640q90; first by worst-phase sAP: A_eco (different).

Paired worst-phase sAP against A_stream_fc2: 16 unique comparisons, 0 significant after Holm.


## vid_campaign_v42: G11 (live power on both boards)


**mission**

| Policy | n | sAP | worst-phase sAP | most often worst | miss > 300 ms | longest stale (s) | age p95 (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A_eco41 | 5 | 0.1155 ± 0.0208 | 0.0257 ± 0.0136 | both_degraded | 2.1 % | 1.34 ± 0.43 | 233 |
| A_eco42 | 5 | 0.1040 ± 0.0061 | 0.0207 ± 0.0114 | both_degraded | 19.7 % | 11.07 ± 5.72 | 5871 |
| A_eco42d | 5 | 0.1178 ± 0.0140 | 0.0274 ± 0.0081 | both_degraded | 9.5 % | 3.12 ± 1.83 | 473 |
| A_eco_tight | 5 | 0.1200 ± 0.0068 | 0.0307 ± 0.0101 | both_degraded | 11.9 % | 4.17 ± 3.22 | 493 |
| A_stream_fc2 | 5 | 0.1018 ± 0.0184 | 0.0172 ± 0.0017 | both_degraded | 0.2 % | 0.09 ± 0.15 | 233 |
| fixed_laptop_m640q90 | 5 | 0.0391 ± 0.0010 | 0.0005 ± 0.0003 | ground_blackout | 79.9 % | 82.88 ± 4.83 | 18414 |

First by mean sAP: A_eco_tight; first by worst-phase sAP: A_eco_tight.


**mission_mirror**

| Policy | n | sAP | worst-phase sAP | most often worst | miss > 300 ms | longest stale (s) | age p95 (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A_eco41 | 5 | 0.1390 ± 0.0036 | 0.0319 ± 0.0086 | both_degraded | 1.3 % | 0.61 ± 0.12 | 227 |
| A_eco42 | 5 | 0.1329 ± 0.0076 | 0.0196 ± 0.0085 | both_degraded | 7.0 % | 0.73 ± 0.35 | 347 |
| A_eco42d | 5 | 0.1171 ± 0.0378 | 0.0190 ± 0.0069 | both_degraded | 15.2 % | 2.94 ± 0.94 | 493 |
| A_eco_tight | 5 | 0.1304 ± 0.0081 | 0.0218 ± 0.0035 | both_degraded | 8.4 % | 0.83 ± 0.56 | 347 |
| A_stream_fc2 | 5 | 0.1186 ± 0.0202 | 0.0181 ± 0.0051 | both_degraded | 0.2 % | 0.11 ± 0.18 | 240 |
| fixed_laptop_m640q90 | 5 | 0.0963 ± 0.0145 | 0.0004 ± 0.0003 | total_blackout | 50.2 % | 60.18 ± 1.31 | 15588 |

First by mean sAP: A_eco41; first by worst-phase sAP: A_eco41.


**random**

| Policy | n | sAP | worst-phase sAP | most often worst | miss > 300 ms | longest stale (s) | age p95 (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A_eco41 | 5 | 0.1046 ± 0.0230 | 0.0109 ± 0.0049 | r18_L1J3 | 1.9 % | 0.51 ± 0.69 | 267 |
| A_eco42 | 5 | 0.1005 ± 0.0248 | 0.0059 ± 0.0048 | r18_L1J3 | 19.8 % | 1.32 ± 0.75 | 447 |
| A_eco42d | 5 | 0.0956 ± 0.0201 | 0.0065 ± 0.0065 | r18_L1J3 | 17.3 % | 2.53 ± 3.15 | 453 |
| A_eco_tight | 5 | 0.1097 ± 0.0183 | 0.0055 ± 0.0053 | r18_L1J3 | 16.5 % | 2.16 ± 1.49 | 420 |
| A_stream_fc2 | 5 | 0.0850 ± 0.0211 | 0.0094 ± 0.0020 | r18_L1J3 | 0.1 % | 0.03 ± 0.07 | 233 |
| fixed_laptop_m640q90 | 5 | 0.0705 ± 0.0282 | 0.0000 ± 0.0000 | r26_L4J0 | 58.6 % | 42.70 ± 17.10 | 12148 |

First by mean sAP: A_eco_tight; first by worst-phase sAP: A_eco41 (different).


**static_good**

| Policy | n | sAP | worst-phase sAP | most often worst | miss > 300 ms | longest stale (s) | age p95 (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A_eco41 | 5 | 0.1812 ± 0.0262 | 0.0779 ± 0.0307 | good3 | 0.4 % | 0.16 ± 0.29 | 187 |
| A_eco42 | 5 | 0.1763 ± 0.0304 | 0.0801 ± 0.0296 | good3 | 1.2 % | 0.35 ± 0.32 | 193 |
| A_eco42d | 5 | 0.1766 ± 0.0338 | 0.0791 ± 0.0306 | good3 | 2.7 % | 0.82 ± 2.16 | 333 |
| A_eco_tight | 5 | 0.1587 ± 0.0372 | 0.0624 ± 0.0301 | good3 | 6.4 % | 2.06 ± 2.18 | 340 |
| A_stream_fc2 | 5 | 0.1473 ± 0.0286 | 0.0561 ± 0.0317 | good3 | 0.6 % | 0.30 ± 0.63 | 193 |
| fixed_laptop_m640q90 | 5 | 0.1654 ± 0.0469 | 0.0517 ± 0.0278 | good3 | 6.6 % | 1.48 ± 3.17 | 453 |

First by mean sAP: A_eco41; first by worst-phase sAP: A_eco42 (different).

Paired worst-phase sAP against A_eco_tight: 20 unique comparisons, 0 significant after Holm.


## vid_campaign_main: G12 (main campaign, 240 runs)


**mission**

| Policy | n | sAP | worst-phase sAP | most often worst | miss > 300 ms | longest stale (s) | age p95 (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| aoi_thr | 5 | 0.0946 ± 0.0128 | 0.0121 ± 0.0004 | both_degraded | 38.4 % | 21.51 ± 0.83 | 687 |
| conf_trigger | 5 | 0.0763 ± 0.0090 | 0.0286 ± 0.0099 | both_degraded | 0.7 % | 0.89 ± 0.04 | 220 |
| fixed_laptop_m640q90 | 5 | 0.0450 ± 0.0092 | 0.0003 ± 0.0004 | total_blackout | 79.5 % | 80.99 ± 4.94 | 18601 |
| jsq | 5 | 0.0839 ± 0.0158 | 0.0239 ± 0.0117 | both_degraded | 0.1 % | 0.05 ± 0.11 | 220 |
| leaf | 5 | 0.1119 ± 0.0123 | 0.0278 ± 0.0107 | both_degraded | 12.2 % | 4.80 ± 1.68 | 500 |
| reward_offload | 5 | 0.0664 ± 0.0041 | 0.0259 ± 0.0100 | both_degraded | 0.8 % | 0.94 ± 0.05 | 220 |
| v42 | 5 | 0.1057 ± 0.0067 | 0.0219 ± 0.0100 | both_degraded | 14.2 % | 3.12 ± 1.42 | 747 |
| v5 | 5 | 0.1061 ± 0.0114 | 0.0201 ± 0.0085 | both_degraded | 13.3 % | 4.42 ± 2.82 | 1038 |
| v5_exp | 5 | 0.0982 ± 0.0215 | 0.0221 ± 0.0083 | both_degraded | 16.5 % | 3.64 ± 1.70 | 1097 |
| v5_flat | 5 | 0.0747 ± 0.0234 | 0.0088 ± 0.0006 | total_blackout | 52.2 % | 39.06 ± 2.14 | 1480 |
| v5_lin | 5 | 0.1020 ± 0.0147 | 0.0228 ± 0.0064 | both_degraded | 13.6 % | 4.77 ± 3.68 | 1437 |
| v5_nofc | 5 | 0.0658 ± 0.0144 | 0.0082 ± 0.0036 | ground_blackout | 32.4 % | 9.84 ± 2.99 | 5613 |

First by mean sAP: leaf; first by worst-phase sAP: conf_trigger (different).


**mission_mirror**

| Policy | n | sAP | worst-phase sAP | most often worst | miss > 300 ms | longest stale (s) | age p95 (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| aoi_thr | 5 | 0.0965 ± 0.0012 | 0.0127 ± 0.0012 | both_degraded | 34.8 % | 22.19 ± 0.33 | 707 |
| conf_trigger | 5 | 0.0879 ± 0.0083 | 0.0206 ± 0.0034 | both_degraded | 0.8 % | 0.94 ± 0.05 | 233 |
| fixed_laptop_m640q90 | 5 | 0.0905 ± 0.0181 | 0.0004 ± 0.0003 | total_blackout | 50.5 % | 59.72 ± 0.02 | 15762 |
| jsq | 5 | 0.1044 ± 0.0080 | 0.0227 ± 0.0077 | both_degraded | 0.0 % | 0.05 ± 0.09 | 227 |
| leaf | 5 | 0.1235 ± 0.0036 | 0.0215 ± 0.0070 | both_degraded | 10.0 % | 1.39 ± 0.48 | 380 |
| reward_offload | 5 | 0.0752 ± 0.0100 | 0.0241 ± 0.0038 | both_degraded | 0.8 % | 0.95 ± 0.02 | 227 |
| v42 | 5 | 0.1229 ± 0.0067 | 0.0147 ± 0.0033 | both_degraded | 13.0 % | 3.61 ± 3.65 | 453 |
| v5 | 5 | 0.1254 ± 0.0055 | 0.0162 ± 0.0020 | both_degraded | 10.7 % | 1.79 ± 1.99 | 407 |
| v5_exp | 5 | 0.1261 ± 0.0037 | 0.0186 ± 0.0032 | both_degraded | 9.7 % | 1.40 ± 1.95 | 400 |
| v5_flat | 5 | 0.0976 ± 0.0052 | 0.0104 ± 0.0013 | total_blackout | 45.6 % | 30.88 ± 4.06 | 1347 |
| v5_lin | 5 | 0.1295 ± 0.0074 | 0.0322 ± 0.0044 | both_degraded | 4.8 % | 0.83 ± 0.75 | 313 |
| v5_nofc | 5 | 0.1178 ± 0.0109 | 0.0315 ± 0.0079 | recovered_low_battery | 18.6 % | 4.23 ± 0.62 | 505 |

First by mean sAP: v5_lin; first by worst-phase sAP: v5_lin.


**random**

| Policy | n | sAP | worst-phase sAP | most often worst | miss > 300 ms | longest stale (s) | age p95 (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| aoi_thr | 5 | 0.0822 ± 0.0235 | 0.0017 ± 0.0048 | r18_L1J3 | 39.0 % | 14.85 ± 13.36 | 727 |
| conf_trigger | 5 | 0.0654 ± 0.0107 | 0.0114 ± 0.0021 | r18_L1J3 | 0.8 % | 0.91 ± 0.05 | 233 |
| fixed_laptop_m640q90 | 5 | 0.0699 ± 0.0259 | 0.0001 ± 0.0002 | r26_L4J0 | 59.6 % | 40.91 ± 16.57 | 12308 |
| jsq | 5 | 0.0689 ± 0.0167 | 0.0113 ± 0.0021 | r18_L1J3 | 0.1 % | 0.10 ± 0.28 | 227 |
| leaf | 5 | 0.1028 ± 0.0211 | 0.0097 ± 0.0077 | r18_L1J3 | 13.2 % | 1.96 ± 1.58 | 427 |
| reward_offload | 5 | 0.0590 ± 0.0037 | 0.0129 ± 0.0007 | r18_L1J3 | 0.8 % | 0.95 ± 0.05 | 233 |
| v42 | 5 | 0.0896 ± 0.0304 | 0.0047 ± 0.0043 | r18_L1J3 | 22.3 % | 2.88 ± 3.70 | 657 |
| v5 | 5 | 0.1006 ± 0.0210 | 0.0091 ± 0.0057 | r18_L1J3 | 17.6 % | 1.95 ± 1.54 | 420 |
| v5_exp | 5 | 0.1029 ± 0.0134 | 0.0102 ± 0.0072 | r18_L1J3 | 17.8 % | 3.38 ± 3.97 | 447 |
| v5_flat | 5 | 0.0908 ± 0.0225 | 0.0025 ± 0.0057 | r19_L1J3 | 39.5 % | 9.83 ± 7.87 | 713 |
| v5_lin | 5 | 0.1024 ± 0.0150 | 0.0074 ± 0.0036 | r19_L1J3 | 6.6 % | 0.81 ± 0.66 | 340 |
| v5_nofc | 5 | 0.0892 ± 0.0292 | 0.0069 ± 0.0079 | r26_L4J0 | 13.5 % | 5.12 ± 8.33 | 2715 |

First by mean sAP: v5_exp; first by worst-phase sAP: reward_offload (different).


**static_good**

| Policy | n | sAP | worst-phase sAP | most often worst | miss > 300 ms | longest stale (s) | age p95 (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| aoi_thr | 5 | 0.1368 ± 0.0075 | 0.0485 ± 0.0107 | good3 | 4.0 % | 0.38 ± 0.19 | 300 |
| conf_trigger | 5 | 0.1141 ± 0.0151 | 0.0577 ± 0.0187 | good2 | 0.8 % | 0.92 ± 0.04 | 180 |
| fixed_laptop_m640q90 | 5 | 0.1719 ± 0.0268 | 0.0786 ± 0.0167 | good3 | 5.4 % | 0.95 ± 1.02 | 300 |
| jsq | 5 | 0.1295 ± 0.0345 | 0.0557 ± 0.0173 | good2 | 0.0 % | 0.02 ± 0.04 | 173 |
| leaf | 5 | 0.1504 ± 0.0309 | 0.0689 ± 0.0305 | good3 | 5.9 % | 1.02 ± 1.53 | 313 |
| reward_offload | 5 | 0.0920 ± 0.0163 | 0.0425 ± 0.0156 | good3 | 0.8 % | 0.95 ± 0.08 | 207 |
| v42 | 5 | 0.1538 ± 0.0414 | 0.0734 ± 0.0239 | good3 | 6.1 % | 1.02 ± 2.05 | 343 |
| v5 | 5 | 0.1594 ± 0.0146 | 0.0829 ± 0.0135 | good3 | 2.4 % | 0.31 ± 0.15 | 267 |
| v5_exp | 5 | 0.1581 ± 0.0482 | 0.0735 ± 0.0404 | good3 | 6.5 % | 0.80 ± 1.55 | 371 |
| v5_flat | 5 | 0.1544 ± 0.0406 | 0.0565 ± 0.0362 | good3 | 8.2 % | 1.11 ± 2.42 | 373 |
| v5_lin | 5 | 0.1588 ± 0.0198 | 0.0771 ± 0.0277 | good3 | 3.9 % | 1.46 ± 2.93 | 347 |
| v5_nofc | 5 | 0.1551 ± 0.0234 | 0.0790 ± 0.0244 | good3 | 2.4 % | 0.96 ± 2.16 | 353 |

First by mean sAP: fixed_laptop_m640q90; first by worst-phase sAP: v5 (different).

Paired worst-phase sAP against v5: 44 unique comparisons, 0 significant after Holm.


## vid_campaign_table: G13 (same-day table)


**mission**

| Policy | n | sAP | worst-phase sAP | most often worst | miss > 300 ms | longest stale (s) | age p95 (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| onboard_n320 | 5 | 0.0566 ± 0.0018 | 0.0253 ± 0.0027 | both_degraded | 0.8 % | 0.93 ± 0.05 | 233 |
| v41 | 5 | 0.1219 ± 0.0062 | 0.0281 ± 0.0074 | both_degraded | 1.4 % | 1.05 ± 0.65 | 247 |
| v5 | 5 | 0.1109 ± 0.0152 | 0.0255 ± 0.0045 | both_degraded | 16.0 % | 2.83 ± 1.14 | 473 |
| v51 | 5 | 0.1240 ± 0.0037 | 0.0190 ± 0.0030 | both_degraded | 1.3 % | 0.25 ± 0.02 | 267 |

First by mean sAP: v51; first by worst-phase sAP: v41 (different).


**mission_mirror**

| Policy | n | sAP | worst-phase sAP | most often worst | miss > 300 ms | longest stale (s) | age p95 (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| onboard_n320 | 5 | 0.0542 ± 0.0013 | 0.0276 ± 0.0024 | both_degraded | 0.8 % | 0.91 ± 0.03 | 233 |
| v41 | 5 | 0.1425 ± 0.0021 | 0.0324 ± 0.0102 | both_degraded | 1.6 % | 0.82 ± 0.42 | 247 |
| v5 | 5 | 0.1383 ± 0.0059 | 0.0231 ± 0.0109 | both_degraded | 15.0 % | 3.36 ± 3.39 | 487 |
| v51 | 5 | 0.1419 ± 0.0019 | 0.0278 ± 0.0109 | both_degraded | 1.5 % | 0.58 ± 0.11 | 253 |

First by mean sAP: v41; first by worst-phase sAP: v41.


**random**

| Policy | n | sAP | worst-phase sAP | most often worst | miss > 300 ms | longest stale (s) | age p95 (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| onboard_n320 | 5 | 0.0558 ± 0.0028 | 0.0127 ± 0.0011 | r18_L1J3 | 0.8 % | 0.93 ± 0.03 | 227 |
| v41 | 5 | 0.1085 ± 0.0256 | 0.0091 ± 0.0056 | r18_L1J3 | 1.5 % | 0.35 ± 0.37 | 273 |
| v5 | 5 | 0.1067 ± 0.0116 | 0.0091 ± 0.0037 | r18_L1J3 | 14.6 % | 4.09 ± 6.96 | 407 |
| v51 | 5 | 0.1049 ± 0.0174 | 0.0080 ± 0.0023 | r18_L1J3 | 1.5 % | 0.46 ± 0.54 | 280 |

First by mean sAP: v41; first by worst-phase sAP: onboard_n320 (different).


**static_good**

| Policy | n | sAP | worst-phase sAP | most often worst | miss > 300 ms | longest stale (s) | age p95 (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| onboard_n320 | 5 | 0.0568 ± 0.0025 | 0.0277 ± 0.0047 | good3 | 0.8 % | 0.93 ± 0.03 | 227 |
| v41 | 5 | 0.2019 ± 0.0007 | 0.0986 ± 0.0045 | good3 | 0.2 % | 0.18 ± 0.48 | 120 |
| v5 | 5 | 0.1933 ± 0.0216 | 0.0814 ± 0.0367 | good3 | 0.4 % | 0.19 ± 0.51 | 127 |
| v51 | 5 | 0.1989 ± 0.0022 | 0.0898 ± 0.0137 | good3 | 0.0 % | 0.00 ± 0.00 | 120 |

First by mean sAP: v41; first by worst-phase sAP: v41.

Paired worst-phase sAP against v41, v5: 20 unique comparisons, 0 significant after Holm.


## vid_campaign_long: G13 (24-minute missions)


**mission**

| Policy | n | sAP | worst-phase sAP | most often worst | miss > 300 ms | longest stale (s) | age p95 (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| fixed_laptop_m640q90 | 2 | 0.0414 ± 0.0043 | 0.0003 ± 0.0030 | total_blackout | 81.3 % | 280.55 ± 2.33 | 205217 |
| stream_fc2 | 2 | 0.0764 ± 0.2730 | 0.0417 ± 0.0188 | recovered_low_battery | 0.9 % | 0.25 ± 1.06 | 283 |
| v41 | 2 | 0.1094 ± 0.0099 | 0.0415 ± 0.0337 | total_blackout | 1.9 % | 1.20 ± 7.20 | 283 |
| v42 | 2 | 0.1024 ± 0.0531 | 0.0451 ± 0.0096 | total_blackout | 8.8 % | 4.98 ± 23.09 | 367 |
| v5 | 2 | 0.0907 ± 0.0581 | 0.0457 ± 0.0133 | total_blackout | 12.7 % | 5.78 ± 0.21 | 600 |
| v51 | 2 | 0.0878 ± 0.0607 | 0.0417 ± 0.0125 | total_blackout | 5.6 % | 1.07 ± 5.51 | 317 |

First by mean sAP: v41; first by worst-phase sAP: v5 (different).

Paired worst-phase sAP against v41, v5: 9 unique comparisons, 0 significant after Holm.

