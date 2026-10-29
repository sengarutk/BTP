# Task C: standard-metric rescoring of every VisDrone-VID campaign

sAP = streaming AP, standard 'newest' holding rule unless marked 'quality'. 'masked' = VisDrone ignored regions masked (official protocol). +fc = with the campaign's forecaster (v2 offline for the Part 12/14 campaigns, v2 computed live on the Pi from the 80-run campaign on). Sizes: COCO area ranges in the 640-px frame (91 % of the objects are small, 9 % medium, 7 objects large -> not reported). Freshness: age of the held result at each camera frame (30 fps); stale = older than 300 ms. Compare numbers within one campaign only.

## vid_campaign_wifi - Part 12 (108 runs, shared Wi-Fi)
forecaster: v2; reference(s): A_full; 108 runs

### All scenarios pooled (mean over runs)

| policy | n | sAP quality+fc (reported) | **sAP standard+fc** | sAP std+fc, masked | sAP50 masked+fc | small | medium | sAP std (no fc) | fresh AP masked | age p95 (ms) | age max (ms) | longest stale (s) | fresh share |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_full_aer | 12 | 0.0443 | **0.1127** | 0.1139 | 0.2673 | 0.0975 | 0.2393 | 0.0472 | 0.2028 | 344 | 442 | 0.1 | 0.886 |
| A_stream | 12 | 0.0421 | **0.1047** | 0.1058 | 0.2512 | 0.0907 | 0.2270 | 0.0420 | 0.1945 | 358 | 511 | 0.2 | 0.861 |
| A_full | 12 | 0.0423 | **0.1030** | 0.1040 | 0.2436 | 0.0864 | 0.2320 | 0.0513 | 0.1715 | 292 | 519 | 0.2 | 0.916 |
| rule_fallback | 12 | 0.0382 | **0.0999** | 0.1007 | 0.2380 | 0.0767 | 0.2501 | 0.0396 | 0.2305 | 919 | 2975 | 17.0 | 0.639 |
| static_multi | 12 | 0.0408 | **0.0935** | 0.0944 | 0.2338 | 0.0688 | 0.2518 | 0.0471 | 0.1462 | 183 | 283 | 0.0 | 1.000 |
| fixed_laptop_m640q90 | 12 | 0.0452 | **0.0902** | 0.0913 | 0.2108 | 0.0714 | 0.2115 | 0.0379 | 0.2668 | 12556 | 16461 | 45.8 | 0.530 |
| abr_laptop | 12 | 0.0439 | **0.0887** | 0.0898 | 0.2133 | 0.0722 | 0.2236 | 0.0407 | 0.1824 | 12067 | 15983 | 15.9 | 0.808 |
| fixed_jetson_s640q90 | 12 | 0.0333 | **0.0804** | 0.0812 | 0.1965 | 0.0641 | 0.2153 | 0.0293 | 0.2544 | 10731 | 14497 | 45.9 | 0.500 |
| fixed_onboard_n320 | 12 | 0.0182 | **0.0594** | 0.0597 | 0.1527 | 0.0433 | 0.1502 | 0.0246 | 0.1137 | 194 | 1419 | 1.0 | 0.992 |

### Per scenario: standard sAP with forecaster (masked), mean ± 95 % CI

| policy | mission | mission_mirror | random | static_good |
|---|---|---|---|---|
| A_full | 0.0926 ± 0.0075 | 0.0868 ± 0.0910 | 0.0907 ± 0.0322 | 0.1460 ± 0.0289 |
| A_full_aer | 0.1067 ± 0.0137 | 0.1138 ± 0.0182 | 0.1006 ± 0.0161 | 0.1343 ± 0.1082 |
| A_stream | 0.0998 ± 0.0211 | 0.1197 ± 0.0142 | 0.0882 ± 0.0244 | 0.1155 ± 0.1463 |
| abr_laptop | 0.0437 ± 0.0108 | 0.0829 ± 0.0381 | 0.0776 ± 0.0365 | 0.1551 ± 0.0462 |
| fixed_jetson_s640q90 | 0.0843 ± 0.0415 | 0.0341 ± 0.0023 | 0.0620 ± 0.0547 | 0.1445 ± 0.0231 |
| fixed_laptop_m640q90 | 0.0381 ± 0.0063 | 0.0839 ± 0.0070 | 0.0696 ± 0.0762 | 0.1737 ± 0.0288 |
| fixed_onboard_n320 | 0.0610 ± 0.0069 | 0.0602 ± 0.0092 | 0.0601 ± 0.0073 | 0.0578 ± 0.0036 |
| rule_fallback | 0.0641 ± 0.0033 | 0.1028 ± 0.0095 | 0.0689 ± 0.0359 | 0.1669 ± 0.0137 |
| static_multi | 0.0848 ± 0.0162 | 0.0933 ± 0.0088 | 0.0757 ± 0.0260 | 0.1236 ± 0.0191 |

### mission: standard sAP with forecaster per phase

| policy | good | ground_congested | ground_blackout | both_degraded | total_blackout | recovered_low_battery |
|---|---|---|---|---|---|---|
| A_full | 0.1508 | 0.1442 | 0.0817 | 0.0216 | 0.0559 | 0.0805 |
| A_full_aer | 0.1762 | 0.2152 | 0.0895 | 0.0177 | 0.0526 | 0.0472 |
| A_stream | 0.1490 | 0.2055 | 0.0836 | 0.0210 | 0.0517 | 0.0477 |
| abr_laptop | 0.1758 | 0.1209 | 0.0003 | 0.0260 | 0.0025 | 0.0579 |
| fixed_jetson_s640q90 | 0.1762 | 0.2281 | 0.0976 | 0.0123 | 0.0004 | 0.0914 |
| fixed_laptop_m640q90 | 0.1771 | 0.1400 | 0.0004 | 0.0095 | 0.0007 | 0.1231 |
| fixed_onboard_n320 | 0.0693 | 0.0754 | 0.0368 | 0.0316 | 0.0917 | 0.0632 |
| rule_fallback | 0.1553 | 0.1158 | 0.0891 | 0.0123 | 0.0382 | 0.0738 |
| static_multi | 0.1427 | 0.1139 | 0.0802 | 0.0228 | 0.0925 | 0.0634 |

### mission_mirror: standard sAP with forecaster per phase

| policy | good | edge_congested | edge_blackout | both_degraded | total_blackout | recovered_low_battery |
|---|---|---|---|---|---|---|
| A_full | 0.1152 | 0.1602 | 0.0760 | 0.0203 | 0.0532 | 0.0709 |
| A_full_aer | 0.1559 | 0.2344 | 0.0870 | 0.0245 | 0.0542 | 0.0734 |
| A_stream | 0.1633 | 0.2381 | 0.1040 | 0.0254 | 0.0552 | 0.0649 |
| abr_laptop | 0.1717 | 0.2159 | 0.1035 | 0.0240 | 0.0018 | 0.0523 |
| fixed_jetson_s640q90 | 0.1732 | 0.1151 | 0.0006 | 0.0099 | 0.0011 | 0.1150 |
| fixed_laptop_m640q90 | 0.1832 | 0.2542 | 0.1064 | 0.0123 | 0.0005 | 0.1068 |
| fixed_onboard_n320 | 0.0678 | 0.0731 | 0.0356 | 0.0312 | 0.0927 | 0.0628 |
| rule_fallback | 0.1692 | 0.2208 | 0.0918 | 0.0112 | 0.0468 | 0.0761 |
| static_multi | 0.1425 | 0.1391 | 0.0862 | 0.0214 | 0.0868 | 0.0555 |

### Paired: A_full minus policy (all scenarios x repetitions)

| policy | metric | pairs | mean diff ± 95 % CI | wins | p (exact perm.) | p (Holm) |
|---|---|---|---|---|---|---|
| fixed_onboard_n320 | sAP_fc | 12 | +0.0436 ± 0.0197 | 11/12 | 0.0010 | 0.0078 |
| fixed_jetson_s640q90 | sAP_fc | 12 | +0.0226 ± 0.0169 | 10/12 | 0.0049 | 0.0342 |
| abr_laptop | sAP_fc | 12 | +0.0142 ± 0.0185 | 8/12 | 0.1206 | 0.6030 |
| fixed_laptop_m640q90 | sAP_fc | 12 | +0.0127 ± 0.0244 | 7/12 | 0.2690 | 1.0000 |
| static_multi | sAP_fc | 12 | +0.0095 ± 0.0116 | 11/12 | 0.0986 | 0.5918 |
| rule_fallback | sAP_fc | 12 | +0.0031 ± 0.0180 | 7/12 | 0.7134 | 1.0000 |
| A_stream | sAP_fc | 12 | -0.0017 ± 0.0231 | 5/12 | 0.8218 | 1.0000 |
| A_full_aer | sAP_fc | 12 | -0.0097 ± 0.0192 | 2/12 | 0.3462 | 1.0000 |
| fixed_onboard_n320 | sAP_masked_fc | 12 | +0.0443 ± 0.0199 | 11/12 | 0.0010 | 0.0078 |
| fixed_jetson_s640q90 | sAP_masked_fc | 12 | +0.0228 ± 0.0172 | 10/12 | 0.0049 | 0.0342 |
| abr_laptop | sAP_masked_fc | 12 | +0.0142 ± 0.0187 | 8/12 | 0.1255 | 0.6274 |
| fixed_laptop_m640q90 | sAP_masked_fc | 12 | +0.0127 ± 0.0247 | 7/12 | 0.2744 | 1.0000 |
| static_multi | sAP_masked_fc | 12 | +0.0097 ± 0.0118 | 11/12 | 0.0981 | 0.5889 |
| rule_fallback | sAP_masked_fc | 12 | +0.0033 ± 0.0183 | 7/12 | 0.6997 | 1.0000 |
| A_stream | sAP_masked_fc | 12 | -0.0018 ± 0.0234 | 5/12 | 0.8203 | 1.0000 |
| A_full_aer | sAP_masked_fc | 12 | -0.0098 ± 0.0194 | 2/12 | 0.3481 | 1.0000 |
| fixed_onboard_n320 | sAP | 12 | +0.0267 ± 0.0152 | 11/12 | 0.0010 | 0.0078 |
| fixed_jetson_s640q90 | sAP | 12 | +0.0220 ± 0.0084 | 10/12 | 0.0020 | 0.0137 |
| fixed_laptop_m640q90 | sAP | 12 | +0.0134 ± 0.0104 | 10/12 | 0.0215 | 0.1289 |
| rule_fallback | sAP | 12 | +0.0117 ± 0.0092 | 10/12 | 0.0254 | 0.1289 |
| abr_laptop | sAP | 12 | +0.0106 ± 0.0084 | 11/12 | 0.0229 | 0.1289 |
| A_stream | sAP | 12 | +0.0093 ± 0.0146 | 10/12 | 0.1934 | 0.5801 |
| static_multi | sAP | 12 | +0.0042 ± 0.0082 | 9/12 | 0.2842 | 0.5801 |
| A_full_aer | sAP | 12 | +0.0042 ± 0.0133 | 7/12 | 0.5308 | 0.5801 |
| fixed_onboard_n320 | sAP_quality_fc | 12 | +0.0242 ± 0.0087 | 11/12 | 0.0010 | 0.0078 |
| fixed_jetson_s640q90 | sAP_quality_fc | 12 | +0.0091 ± 0.0068 | 11/12 | 0.0044 | 0.0308 |
| rule_fallback | sAP_quality_fc | 12 | +0.0041 ± 0.0074 | 9/12 | 0.2437 | 1.0000 |
| static_multi | sAP_quality_fc | 12 | +0.0016 ± 0.0058 | 8/12 | 0.5962 | 1.0000 |
| A_stream | sAP_quality_fc | 12 | +0.0003 ± 0.0097 | 5/12 | 0.9336 | 1.0000 |
| abr_laptop | sAP_quality_fc | 12 | -0.0015 ± 0.0085 | 7/12 | 0.7197 | 1.0000 |
| A_full_aer | sAP_quality_fc | 12 | -0.0019 ± 0.0084 | 6/12 | 0.6309 | 1.0000 |
| fixed_laptop_m640q90 | sAP_quality_fc | 12 | -0.0028 ± 0.0115 | 4/12 | 0.5830 | 1.0000 |

## vid_campaign_wifi_fc - Part 14 (forecaster v1 campaign)
forecaster: v2; reference(s): A_full; 36 runs

### All scenarios pooled (mean over runs)

| policy | n | sAP quality+fc (reported) | **sAP standard+fc** | sAP std+fc, masked | sAP50 masked+fc | small | medium | sAP std (no fc) | fresh AP masked | age p95 (ms) | age max (ms) | longest stale (s) | fresh share |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_stream | 12 | 0.0520 | **0.1227** | 0.1240 | 0.2869 | 0.1060 | 0.2608 | 0.0552 | 0.2055 | 347 | 472 | 0.2 | 0.880 |
| A_stream_fc | 12 | 0.0492 | **0.1155** | 0.1167 | 0.2708 | 0.0909 | 0.2625 | 0.0590 | 0.1966 | 217 | 364 | 0.1 | 0.998 |
| A_full | 12 | 0.0471 | **0.1084** | 0.1095 | 0.2532 | 0.0926 | 0.2366 | 0.0527 | 0.1766 | 317 | 472 | 0.2 | 0.897 |

### Per scenario: standard sAP with forecaster (masked), mean ± 95 % CI

| policy | mission | mission_mirror | random | static_good |
|---|---|---|---|---|
| A_full | 0.0813 ± 0.0366 | 0.0833 ± 0.1064 | 0.0919 ± 0.0356 | 0.1813 ± 0.0090 |
| A_stream | 0.0972 ± 0.0097 | 0.1141 ± 0.0559 | 0.0981 ± 0.0334 | 0.1866 ± 0.0201 |
| A_stream_fc | 0.0906 ± 0.0601 | 0.1172 ± 0.0174 | 0.0839 ± 0.0327 | 0.1751 ± 0.0302 |

### mission: standard sAP with forecaster per phase

| policy | good | ground_congested | ground_blackout | both_degraded | total_blackout | recovered_low_battery |
|---|---|---|---|---|---|---|
| A_full | 0.1428 | 0.1303 | 0.0658 | 0.0227 | 0.0535 | 0.0751 |
| A_stream | 0.1784 | 0.1831 | 0.0978 | 0.0200 | 0.0492 | 0.0512 |
| A_stream_fc | 0.1511 | 0.1503 | 0.0699 | 0.0246 | 0.0848 | 0.0558 |

### mission_mirror: standard sAP with forecaster per phase

| policy | good | edge_congested | edge_blackout | both_degraded | total_blackout | recovered_low_battery |
|---|---|---|---|---|---|---|
| A_full | 0.1316 | 0.1387 | 0.0845 | 0.0163 | 0.0510 | 0.0616 |
| A_stream | 0.1731 | 0.2371 | 0.0955 | 0.0223 | 0.0488 | 0.0603 |
| A_stream_fc | 0.1688 | 0.2262 | 0.1026 | 0.0183 | 0.0814 | 0.0553 |

### Paired: A_full minus policy (all scenarios x repetitions)

| policy | metric | pairs | mean diff ± 95 % CI | wins | p (exact perm.) | p (Holm) |
|---|---|---|---|---|---|---|
| A_stream_fc | sAP_fc | 12 | -0.0070 ± 0.0173 | 7/12 | 0.4497 | 0.4497 |
| A_stream | sAP_fc | 12 | -0.0142 ± 0.0106 | 2/12 | 0.0054 | 0.0107 |
| A_stream_fc | sAP_masked_fc | 12 | -0.0073 ± 0.0176 | 7/12 | 0.4453 | 0.4453 |
| A_stream | sAP_masked_fc | 12 | -0.0146 ± 0.0108 | 2/12 | 0.0049 | 0.0098 |
| A_stream | sAP | 12 | -0.0025 ± 0.0072 | 6/12 | 0.4644 | 0.4902 |
| A_stream_fc | sAP | 12 | -0.0063 ± 0.0108 | 6/12 | 0.2451 | 0.4902 |
| A_stream_fc | sAP_quality_fc | 12 | -0.0020 ± 0.0085 | 6/12 | 0.6631 | 0.6631 |
| A_stream | sAP_quality_fc | 12 | -0.0048 ± 0.0050 | 4/12 | 0.0483 | 0.0967 |

## vid_campaign_wifi_fc2 - Part 14 (80-run campaign, live forecaster v2)
forecaster: v2live; reference(s): A_full, A_stream_fc2; 80 runs

### All scenarios pooled (mean over runs)

| policy | n | sAP quality+fc (reported) | **sAP standard+fc** | sAP std+fc, masked | sAP50 masked+fc | small | medium | sAP std (no fc) | fresh AP masked | age p95 (ms) | age max (ms) | longest stale (s) | fresh share |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_stream_fc2 | 20 | 0.0508 | **0.1241** | 0.1256 | 0.2884 | 0.0990 | 0.2832 | 0.0646 | 0.2034 | 205 | 457 | 0.1 | 0.998 |
| A_stream_fc | 20 | 0.0472 | **0.1155** | 0.1168 | 0.2707 | 0.0921 | 0.2635 | 0.0592 | 0.1960 | 212 | 482 | 0.2 | 0.998 |
| A_full | 20 | 0.0463 | **0.1088** | 0.1099 | 0.2552 | 0.0926 | 0.2333 | 0.0530 | 0.1819 | 338 | 610 | 0.3 | 0.872 |
| fixed_laptop_m640q90 | 20 | 0.0409 | **0.0859** | 0.0870 | 0.1953 | 0.0690 | 0.2003 | 0.0428 | 0.2672 | 18898 | 22985 | 54.8 | 0.440 |

### Per scenario: standard sAP with forecaster (masked), mean ± 95 % CI

| policy | mission | mission_mirror | random | static_good |
|---|---|---|---|---|
| A_full | 0.0826 ± 0.0168 | 0.1119 ± 0.0342 | 0.0821 ± 0.0251 | 0.1630 ± 0.0749 |
| A_stream_fc | 0.1132 ± 0.0122 | 0.1179 ± 0.0307 | 0.0892 ± 0.0195 | 0.1470 ± 0.0976 |
| A_stream_fc2 | 0.1129 ± 0.0122 | 0.1309 ± 0.0121 | 0.0802 ± 0.0269 | 0.1783 ± 0.0727 |
| fixed_laptop_m640q90 | 0.0391 ± 0.0014 | 0.0949 ± 0.0212 | 0.0547 ± 0.0395 | 0.1590 ± 0.1098 |

### mission: standard sAP with forecaster per phase

| policy | good | ground_congested | ground_blackout | both_degraded | total_blackout | recovered_low_battery |
|---|---|---|---|---|---|---|
| A_full | 0.1480 | 0.1326 | 0.0816 | 0.0202 | 0.0473 | 0.0701 |
| A_stream_fc | 0.1704 | 0.2126 | 0.0813 | 0.0232 | 0.0872 | 0.0563 |
| A_stream_fc2 | 0.1759 | 0.2079 | 0.0839 | 0.0232 | 0.0831 | 0.0524 |
| fixed_laptop_m640q90 | 0.1925 | 0.1294 | 0.0005 | 0.0098 | 0.0007 | 0.1231 |

### mission_mirror: standard sAP with forecaster per phase

| policy | good | edge_congested | edge_blackout | both_degraded | total_blackout | recovered_low_battery |
|---|---|---|---|---|---|---|
| A_full | 0.1740 | 0.2168 | 0.1015 | 0.0235 | 0.0488 | 0.0738 |
| A_stream_fc | 0.1763 | 0.2067 | 0.1167 | 0.0194 | 0.0793 | 0.0518 |
| A_stream_fc2 | 0.1829 | 0.2590 | 0.1055 | 0.0203 | 0.0826 | 0.0506 |
| fixed_laptop_m640q90 | 0.1909 | 0.2676 | 0.1124 | 0.0121 | 0.0004 | 0.1103 |

### Paired: A_full minus policy (all scenarios x repetitions)

| policy | metric | pairs | mean diff ± 95 % CI | wins | p (exact perm.) | p (Holm) |
|---|---|---|---|---|---|---|
| fixed_laptop_m640q90 | sAP_fc | 20 | +0.0228 ± 0.0127 | 15/20 | 0.0022 | 0.0053 |
| A_stream_fc | sAP_fc | 20 | -0.0067 ± 0.0179 | 5/20 | 0.5154 | 0.5154 |
| A_stream_fc2 | sAP_fc | 20 | -0.0154 ± 0.0088 | 3/20 | 0.0018 | 0.0053 |
| fixed_laptop_m640q90 | sAP_masked_fc | 20 | +0.0230 ± 0.0128 | 15/20 | 0.0023 | 0.0050 |
| A_stream_fc | sAP_masked_fc | 20 | -0.0069 ± 0.0181 | 5/20 | 0.5060 | 0.5060 |
| A_stream_fc2 | sAP_masked_fc | 20 | -0.0157 ± 0.0089 | 3/20 | 0.0017 | 0.0050 |
| fixed_laptop_m640q90 | sAP | 20 | +0.0102 ± 0.0063 | 17/20 | 0.0044 | 0.0089 |
| A_stream_fc | sAP | 20 | -0.0062 ± 0.0119 | 3/20 | 0.3233 | 0.3233 |
| A_stream_fc2 | sAP | 20 | -0.0116 ± 0.0056 | 2/20 | 0.0006 | 0.0018 |
| fixed_laptop_m640q90 | sAP_quality_fc | 20 | +0.0054 ± 0.0058 | 15/20 | 0.0684 | 0.1368 |
| A_stream_fc | sAP_quality_fc | 20 | -0.0009 ± 0.0081 | 6/20 | 0.9108 | 0.9108 |
| A_stream_fc2 | sAP_quality_fc | 20 | -0.0045 ± 0.0038 | 7/20 | 0.0208 | 0.0625 |

### Paired: A_stream_fc2 minus policy (all scenarios x repetitions)

| policy | metric | pairs | mean diff ± 95 % CI | wins | p (exact perm.) | p (Holm) |
|---|---|---|---|---|---|---|
| fixed_laptop_m640q90 | sAP_fc | 20 | +0.0382 ± 0.0137 | 19/20 | 0.0000 | 0.0001 |
| A_full | sAP_fc | 20 | +0.0154 ± 0.0088 | 17/20 | 0.0018 | 0.0035 |
| A_stream_fc | sAP_fc | 20 | +0.0086 ± 0.0150 | 10/20 | 0.2675 | 0.2675 |
| fixed_laptop_m640q90 | sAP_masked_fc | 20 | +0.0386 ± 0.0139 | 19/20 | 0.0000 | 0.0001 |
| A_full | sAP_masked_fc | 20 | +0.0157 ± 0.0089 | 17/20 | 0.0017 | 0.0034 |
| A_stream_fc | sAP_masked_fc | 20 | +0.0087 ± 0.0152 | 10/20 | 0.2670 | 0.2670 |
| fixed_laptop_m640q90 | sAP | 20 | +0.0218 ± 0.0061 | 19/20 | 0.0000 | 0.0000 |
| A_full | sAP | 20 | +0.0116 ± 0.0056 | 18/20 | 0.0006 | 0.0012 |
| A_stream_fc | sAP | 20 | +0.0054 ± 0.0096 | 11/20 | 0.2955 | 0.2955 |
| fixed_laptop_m640q90 | sAP_quality_fc | 20 | +0.0099 ± 0.0053 | 18/20 | 0.0005 | 0.0014 |
| A_full | sAP_quality_fc | 20 | +0.0045 ± 0.0038 | 13/20 | 0.0208 | 0.0417 |
| A_stream_fc | sAP_quality_fc | 20 | +0.0037 ± 0.0070 | 12/20 | 0.3477 | 0.3477 |

## vid_campaign_energy - G9 (energy campaign)
forecaster: v2live; reference(s): A_stream_fc2; 100 runs

### All scenarios pooled (mean over runs)

| policy | n | sAP quality+fc (reported) | **sAP standard+fc** | sAP std+fc, masked | sAP50 masked+fc | small | medium | sAP std (no fc) | fresh AP masked | age p95 (ms) | age max (ms) | longest stale (s) | fresh share |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_eco_tight | 20 | 0.0543 | **0.1304** | 0.1318 | 0.3046 | 0.1053 | 0.2892 | 0.0583 | 0.2214 | 398 | 1010 | 3.1 | 0.890 |
| A_eco | 20 | 0.0525 | **0.1241** | 0.1254 | 0.2910 | 0.0999 | 0.2753 | 0.0556 | 0.2181 | 398 | 993 | 2.6 | 0.885 |
| A_full | 20 | 0.0465 | **0.1121** | 0.1133 | 0.2622 | 0.0936 | 0.2525 | 0.0588 | 0.1789 | 332 | 527 | 0.2 | 0.902 |
| A_stream_fc2 | 20 | 0.0470 | **0.1114** | 0.1126 | 0.2619 | 0.0876 | 0.2588 | 0.0563 | 0.1982 | 238 | 438 | 0.2 | 0.997 |
| fixed_laptop_m640q90 | 20 | 0.0463 | **0.0957** | 0.0968 | 0.2197 | 0.0771 | 0.2226 | 0.0442 | 0.2628 | 11604 | 15168 | 46.7 | 0.520 |

### Per scenario: standard sAP with forecaster (masked), mean ± 95 % CI

| policy | mission | mission_mirror | random | static_good |
|---|---|---|---|---|
| A_eco | 0.1033 ± 0.0153 | 0.1176 ± 0.0264 | 0.1042 ± 0.0176 | 0.1764 ± 0.0358 |
| A_eco_tight | 0.1154 ± 0.0155 | 0.1266 ± 0.0245 | 0.1057 ± 0.0119 | 0.1795 ± 0.0251 |
| A_full | 0.0843 ± 0.0132 | 0.1111 ± 0.0307 | 0.0951 ± 0.0138 | 0.1628 ± 0.0353 |
| A_stream_fc2 | 0.0856 ± 0.0223 | 0.1258 ± 0.0227 | 0.0773 ± 0.0133 | 0.1619 ± 0.0512 |
| fixed_laptop_m640q90 | 0.0401 ± 0.0021 | 0.0919 ± 0.0026 | 0.0715 ± 0.0256 | 0.1837 ± 0.0159 |

### mission: standard sAP with forecaster per phase

| policy | good | ground_congested | ground_blackout | both_degraded | total_blackout | recovered_low_battery |
|---|---|---|---|---|---|---|
| A_eco | 0.1727 | 0.1785 | 0.1016 | 0.0227 | 0.0802 | 0.0634 |
| A_eco_tight | 0.1861 | 0.2180 | 0.1039 | 0.0196 | 0.0797 | 0.0722 |
| A_full | 0.1715 | 0.1401 | 0.0625 | 0.0262 | 0.0459 | 0.0697 |
| A_stream_fc2 | 0.1537 | 0.1450 | 0.0717 | 0.0208 | 0.0748 | 0.0497 |
| fixed_laptop_m640q90 | 0.1950 | 0.1397 | 0.0005 | 0.0096 | 0.0006 | 0.1265 |

### mission_mirror: standard sAP with forecaster per phase

| policy | good | edge_congested | edge_blackout | both_degraded | total_blackout | recovered_low_battery |
|---|---|---|---|---|---|---|
| A_eco | 0.1762 | 0.2356 | 0.0967 | 0.0169 | 0.0694 | 0.0712 |
| A_eco_tight | 0.1737 | 0.2478 | 0.1162 | 0.0226 | 0.0750 | 0.0765 |
| A_full | 0.1569 | 0.2212 | 0.1029 | 0.0205 | 0.0450 | 0.0704 |
| A_stream_fc2 | 0.1784 | 0.2500 | 0.1122 | 0.0158 | 0.0738 | 0.0477 |
| fixed_laptop_m640q90 | 0.1943 | 0.2706 | 0.1226 | 0.0121 | 0.0005 | 0.1103 |

### Paired: A_stream_fc2 minus policy (all scenarios x repetitions)

| policy | metric | pairs | mean diff ± 95 % CI | wins | p (exact perm.) | p (Holm) |
|---|---|---|---|---|---|---|
| fixed_laptop_m640q90 | sAP_fc | 20 | +0.0158 ± 0.0163 | 13/20 | 0.0583 | 0.1165 |
| A_full | sAP_fc | 20 | -0.0006 ± 0.0090 | 10/20 | 0.8859 | 0.8859 |
| A_eco | sAP_fc | 20 | -0.0127 ± 0.0117 | 5/20 | 0.0360 | 0.1081 |
| A_eco_tight | sAP_fc | 20 | -0.0189 ± 0.0095 | 3/20 | 0.0005 | 0.0021 |
| fixed_laptop_m640q90 | sAP_masked_fc | 20 | +0.0159 ± 0.0165 | 13/20 | 0.0594 | 0.1188 |
| A_full | sAP_masked_fc | 20 | -0.0007 ± 0.0091 | 10/20 | 0.8823 | 0.8823 |
| A_eco | sAP_masked_fc | 20 | -0.0127 ± 0.0119 | 5/20 | 0.0381 | 0.1143 |
| A_eco_tight | sAP_masked_fc | 20 | -0.0192 ± 0.0097 | 3/20 | 0.0005 | 0.0020 |
| fixed_laptop_m640q90 | sAP | 20 | +0.0121 ± 0.0076 | 16/20 | 0.0044 | 0.0178 |
| A_eco | sAP | 20 | +0.0008 ± 0.0064 | 9/20 | 0.8112 | 1.0000 |
| A_eco_tight | sAP | 20 | -0.0020 ± 0.0048 | 7/20 | 0.3962 | 1.0000 |
| A_full | sAP | 20 | -0.0024 ± 0.0065 | 11/20 | 0.4481 | 1.0000 |
| fixed_laptop_m640q90 | sAP_quality_fc | 20 | +0.0007 ± 0.0059 | 12/20 | 0.8190 | 1.0000 |
| A_full | sAP_quality_fc | 20 | +0.0005 ± 0.0039 | 12/20 | 0.8051 | 1.0000 |
| A_eco | sAP_quality_fc | 20 | -0.0055 ± 0.0046 | 5/20 | 0.0222 | 0.0665 |
| A_eco_tight | sAP_quality_fc | 20 | -0.0074 ± 0.0030 | 3/20 | 0.0001 | 0.0002 |

## vid_campaign_v42 - G11 (live power on both boards)
forecaster: v2live; reference(s): A_eco_tight; 120 runs

### All scenarios pooled (mean over runs)

| policy | n | sAP quality+fc (reported) | **sAP standard+fc** | sAP std+fc, masked | sAP50 masked+fc | small | medium | sAP std (no fc) | fresh AP masked | age p95 (ms) | age max (ms) | longest stale (s) | fresh share |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_eco41 | 20 | 0.0566 | **0.1351** | 0.1366 | 0.3147 | 0.1094 | 0.2976 | 0.0627 | 0.2138 | 228 | 785 | 0.7 | 0.985 |
| A_eco_tight | 20 | 0.0541 | **0.1297** | 0.1311 | 0.3039 | 0.1060 | 0.2884 | 0.0579 | 0.2256 | 400 | 1185 | 2.3 | 0.892 |
| A_eco42 | 20 | 0.0551 | **0.1284** | 0.1299 | 0.3003 | 0.1060 | 0.2806 | 0.0593 | 0.2230 | 1714 | 3480 | 3.4 | 0.881 |
| A_eco42d | 20 | 0.0536 | **0.1268** | 0.1282 | 0.2969 | 0.1032 | 0.2820 | 0.0580 | 0.2162 | 438 | 1032 | 2.4 | 0.888 |
| A_stream_fc2 | 20 | 0.0485 | **0.1132** | 0.1145 | 0.2679 | 0.0899 | 0.2641 | 0.0565 | 0.2005 | 225 | 423 | 0.1 | 0.997 |
| fixed_laptop_m640q90 | 20 | 0.0450 | **0.0928** | 0.0939 | 0.2144 | 0.0744 | 0.2157 | 0.0425 | 0.2614 | 11651 | 15380 | 46.8 | 0.512 |

### Per scenario: standard sAP with forecaster (masked), mean ± 95 % CI

| policy | mission | mission_mirror | random | static_good |
|---|---|---|---|---|
| A_eco41 | 0.1169 ± 0.0210 | 0.1409 ± 0.0037 | 0.1055 ± 0.0231 | 0.1830 ± 0.0266 |
| A_eco42 | 0.1052 ± 0.0061 | 0.1348 ± 0.0077 | 0.1014 ± 0.0250 | 0.1781 ± 0.0309 |
| A_eco42d | 0.1193 ± 0.0143 | 0.1187 ± 0.0384 | 0.0965 ± 0.0202 | 0.1784 ± 0.0343 |
| A_eco_tight | 0.1215 ± 0.0069 | 0.1323 ± 0.0083 | 0.1106 ± 0.0184 | 0.1602 ± 0.0378 |
| A_stream_fc2 | 0.1030 ± 0.0187 | 0.1202 ± 0.0207 | 0.0859 ± 0.0215 | 0.1489 ± 0.0287 |
| fixed_laptop_m640q90 | 0.0396 ± 0.0010 | 0.0979 ± 0.0145 | 0.0710 ± 0.0281 | 0.1671 ± 0.0475 |

### mission: standard sAP with forecaster per phase

| policy | good | ground_congested | ground_blackout | both_degraded | total_blackout | recovered_low_battery |
|---|---|---|---|---|---|---|
| A_eco41 | 0.1859 | 0.2215 | 0.0980 | 0.0257 | 0.0824 | 0.0695 |
| A_eco42 | 0.1873 | 0.2073 | 0.0630 | 0.0207 | 0.0725 | 0.1200 |
| A_eco42d | 0.1848 | 0.2206 | 0.0997 | 0.0274 | 0.0877 | 0.0616 |
| A_eco_tight | 0.1824 | 0.2233 | 0.1052 | 0.0307 | 0.0921 | 0.0626 |
| A_stream_fc2 | 0.1745 | 0.1948 | 0.0757 | 0.0172 | 0.0777 | 0.0494 |
| fixed_laptop_m640q90 | 0.1919 | 0.1370 | 0.0005 | 0.0102 | 0.0008 | 0.1268 |

### mission_mirror: standard sAP with forecaster per phase

| policy | good | edge_congested | edge_blackout | both_degraded | total_blackout | recovered_low_battery |
|---|---|---|---|---|---|---|
| A_eco41 | 0.1889 | 0.2693 | 0.1193 | 0.0319 | 0.0900 | 0.0725 |
| A_eco42 | 0.1875 | 0.2694 | 0.1213 | 0.0196 | 0.0767 | 0.0706 |
| A_eco42d | 0.1687 | 0.2373 | 0.1007 | 0.0190 | 0.0756 | 0.0689 |
| A_eco_tight | 0.1861 | 0.2690 | 0.1133 | 0.0218 | 0.0765 | 0.0694 |
| A_stream_fc2 | 0.1546 | 0.2397 | 0.1011 | 0.0181 | 0.0778 | 0.0502 |
| fixed_laptop_m640q90 | 0.1978 | 0.2706 | 0.1209 | 0.0122 | 0.0004 | 0.1124 |

### Paired: A_eco_tight minus policy (all scenarios x repetitions)

| policy | metric | pairs | mean diff ± 95 % CI | wins | p (exact perm.) | p (Holm) |
|---|---|---|---|---|---|---|
| fixed_laptop_m640q90 | sAP_fc | 20 | +0.0369 ± 0.0158 | 16/20 | 0.0002 | 0.0009 |
| A_stream_fc2 | sAP_fc | 20 | +0.0165 ± 0.0099 | 17/20 | 0.0028 | 0.0113 |
| A_eco42d | sAP_fc | 20 | +0.0029 ± 0.0123 | 12/20 | 0.6254 | 1.0000 |
| A_eco42 | sAP_fc | 20 | +0.0013 ± 0.0103 | 11/20 | 0.8828 | 1.0000 |
| A_eco41 | sAP_fc | 20 | -0.0054 ± 0.0101 | 9/20 | 0.3196 | 0.9587 |
| fixed_laptop_m640q90 | sAP_masked_fc | 20 | +0.0372 ± 0.0160 | 16/20 | 0.0002 | 0.0009 |
| A_stream_fc2 | sAP_masked_fc | 20 | +0.0167 ± 0.0100 | 18/20 | 0.0030 | 0.0120 |
| A_eco42d | sAP_masked_fc | 20 | +0.0029 ± 0.0125 | 12/20 | 0.6304 | 1.0000 |
| A_eco42 | sAP_masked_fc | 20 | +0.0013 ± 0.0105 | 11/20 | 0.8879 | 1.0000 |
| A_eco41 | sAP_masked_fc | 20 | -0.0054 ± 0.0102 | 9/20 | 0.3234 | 0.9702 |
| fixed_laptop_m640q90 | sAP | 20 | +0.0153 ± 0.0074 | 16/20 | 0.0006 | 0.0028 |
| A_stream_fc2 | sAP | 20 | +0.0014 ± 0.0057 | 14/20 | 0.6318 | 1.0000 |
| A_eco42d | sAP | 20 | -0.0002 ± 0.0081 | 10/20 | 0.9755 | 1.0000 |
| A_eco42 | sAP | 20 | -0.0014 ± 0.0070 | 8/20 | 0.8696 | 1.0000 |
| A_eco41 | sAP | 20 | -0.0048 ± 0.0070 | 8/20 | 0.1372 | 0.5487 |
| fixed_laptop_m640q90 | sAP_quality_fc | 20 | +0.0091 ± 0.0061 | 15/20 | 0.0065 | 0.0262 |
| A_stream_fc2 | sAP_quality_fc | 20 | +0.0056 ± 0.0037 | 18/20 | 0.0050 | 0.0250 |
| A_eco42d | sAP_quality_fc | 20 | +0.0005 ± 0.0053 | 11/20 | 0.8132 | 1.0000 |
| A_eco42 | sAP_quality_fc | 20 | -0.0009 ± 0.0042 | 10/20 | 0.7928 | 1.0000 |
| A_eco41 | sAP_quality_fc | 20 | -0.0025 ± 0.0041 | 7/20 | 0.2075 | 0.6225 |

## vid_campaign_main - G12 (main campaign, 240 runs)
forecaster: v2live; reference(s): v5; 240 runs

### All scenarios pooled (mean over runs)

| policy | n | sAP quality+fc (reported) | **sAP standard+fc** | sAP std+fc, masked | sAP50 masked+fc | small | medium | sAP std (no fc) | fresh AP masked | age p95 (ms) | age max (ms) | longest stale (s) | fresh share |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v5_lin | 20 | 0.0523 | **0.1232** | 0.1244 | 0.2911 | 0.0995 | 0.2718 | 0.0525 | 0.2155 | 609 | 1977 | 2.0 | 0.927 |
| v5 | 20 | 0.0519 | **0.1229** | 0.1242 | 0.2900 | 0.1003 | 0.2702 | 0.0522 | 0.2173 | 533 | 1768 | 2.1 | 0.890 |
| leaf | 20 | 0.0515 | **0.1222** | 0.1235 | 0.2910 | 0.0993 | 0.2709 | 0.0506 | 0.2195 | 405 | 1205 | 2.3 | 0.897 |
| v5_exp | 20 | 0.0517 | **0.1213** | 0.1227 | 0.2862 | 0.0990 | 0.2707 | 0.0536 | 0.2155 | 579 | 1817 | 2.3 | 0.874 |
| v42 | 20 | 0.0501 | **0.1180** | 0.1193 | 0.2809 | 0.0971 | 0.2628 | 0.0499 | 0.2166 | 550 | 1695 | 2.7 | 0.861 |
| v5_nofc | 20 | 0.0459 | **0.1070** | 0.1082 | 0.2531 | 0.0891 | 0.2343 | 0.0488 | 0.2012 | 2296 | 5317 | 5.0 | 0.833 |
| v5_flat | 20 | 0.0465 | **0.1044** | 0.1055 | 0.2475 | 0.0856 | 0.2295 | 0.0412 | 0.2422 | 978 | 1977 | 20.2 | 0.636 |
| aoi_thr | 20 | 0.0407 | **0.1025** | 0.1034 | 0.2514 | 0.0837 | 0.2489 | 0.0356 | 0.2299 | 605 | 1755 | 14.7 | 0.710 |
| jsq | 20 | 0.0373 | **0.0967** | 0.0977 | 0.2362 | 0.0736 | 0.2453 | 0.0458 | 0.1817 | 212 | 357 | 0.1 | 0.999 |
| fixed_laptop_m640q90 | 20 | 0.0443 | **0.0943** | 0.0954 | 0.2176 | 0.0755 | 0.2161 | 0.0410 | 0.2601 | 11743 | 15417 | 45.6 | 0.512 |
| conf_trigger | 20 | 0.0305 | **0.0859** | 0.0867 | 0.2080 | 0.0635 | 0.2023 | 0.0423 | 0.1645 | 217 | 1475 | 0.9 | 0.992 |
| reward_offload | 20 | 0.0241 | **0.0732** | 0.0739 | 0.1824 | 0.0549 | 0.1920 | 0.0308 | 0.1581 | 222 | 1503 | 0.9 | 0.992 |

### Per scenario: standard sAP with forecaster (masked), mean ± 95 % CI

| policy | mission | mission_mirror | random | static_good |
|---|---|---|---|---|
| aoi_thr | 0.0955 ± 0.0130 | 0.0974 ± 0.0013 | 0.0829 ± 0.0237 | 0.1379 ± 0.0076 |
| conf_trigger | 0.0770 ± 0.0091 | 0.0887 ± 0.0084 | 0.0661 ± 0.0108 | 0.1151 ± 0.0151 |
| fixed_laptop_m640q90 | 0.0454 ± 0.0091 | 0.0920 ± 0.0182 | 0.0704 ± 0.0258 | 0.1737 ± 0.0273 |
| jsq | 0.0849 ± 0.0160 | 0.1057 ± 0.0079 | 0.0696 ± 0.0170 | 0.1308 ± 0.0349 |
| leaf | 0.1133 ± 0.0126 | 0.1252 ± 0.0037 | 0.1037 ± 0.0211 | 0.1519 ± 0.0313 |
| reward_offload | 0.0671 ± 0.0042 | 0.0761 ± 0.0102 | 0.0596 ± 0.0039 | 0.0929 ± 0.0164 |
| v42 | 0.1071 ± 0.0070 | 0.1246 ± 0.0069 | 0.0904 ± 0.0307 | 0.1553 ± 0.0421 |
| v5 | 0.1073 ± 0.0116 | 0.1271 ± 0.0056 | 0.1014 ± 0.0212 | 0.1609 ± 0.0149 |
| v5_exp | 0.0994 ± 0.0219 | 0.1277 ± 0.0039 | 0.1037 ± 0.0135 | 0.1599 ± 0.0487 |
| v5_flat | 0.0755 ± 0.0238 | 0.0989 ± 0.0052 | 0.0916 ± 0.0226 | 0.1558 ± 0.0410 |
| v5_lin | 0.1031 ± 0.0150 | 0.1311 ± 0.0075 | 0.1034 ± 0.0150 | 0.1602 ± 0.0202 |
| v5_nofc | 0.0664 ± 0.0145 | 0.1195 ± 0.0114 | 0.0900 ± 0.0293 | 0.1567 ± 0.0239 |

### mission: standard sAP with forecaster per phase

| policy | good | ground_congested | ground_blackout | both_degraded | total_blackout | recovered_low_battery |
|---|---|---|---|---|---|---|
| aoi_thr | 0.1501 | 0.1868 | 0.0831 | 0.0121 | 0.0444 | 0.1189 |
| conf_trigger | 0.1402 | 0.1295 | 0.0513 | 0.0286 | 0.0843 | 0.0550 |
| fixed_laptop_m640q90 | 0.1895 | 0.1387 | 0.0007 | 0.0100 | 0.0003 | 0.1310 |
| jsq | 0.1338 | 0.1396 | 0.0594 | 0.0239 | 0.0848 | 0.0563 |
| leaf | 0.1719 | 0.2124 | 0.0928 | 0.0278 | 0.0869 | 0.0613 |
| reward_offload | 0.0977 | 0.0906 | 0.0481 | 0.0259 | 0.0886 | 0.0568 |
| v42 | 0.1759 | 0.2006 | 0.0832 | 0.0219 | 0.0678 | 0.1113 |
| v5 | 0.1691 | 0.2075 | 0.0763 | 0.0201 | 0.0818 | 0.0858 |
| v5_exp | 0.1675 | 0.1904 | 0.0685 | 0.0221 | 0.0722 | 0.1063 |
| v5_flat | 0.1550 | 0.1899 | 0.0822 | 0.0101 | 0.0094 | 0.1132 |
| v5_lin | 0.1607 | 0.1971 | 0.0789 | 0.0228 | 0.0727 | 0.0976 |
| v5_nofc | 0.1603 | 0.1721 | 0.0082 | 0.0325 | 0.0511 | 0.0338 |

### mission_mirror: standard sAP with forecaster per phase

| policy | good | edge_congested | edge_blackout | both_degraded | total_blackout | recovered_low_battery |
|---|---|---|---|---|---|---|
| aoi_thr | 0.1494 | 0.1954 | 0.0950 | 0.0127 | 0.0383 | 0.1204 |
| conf_trigger | 0.1436 | 0.1530 | 0.0847 | 0.0206 | 0.0811 | 0.0529 |
| fixed_laptop_m640q90 | 0.1877 | 0.2584 | 0.1122 | 0.0119 | 0.0004 | 0.1120 |
| jsq | 0.1408 | 0.2019 | 0.0765 | 0.0227 | 0.0836 | 0.0538 |
| leaf | 0.1737 | 0.2553 | 0.1111 | 0.0215 | 0.0637 | 0.0835 |
| reward_offload | 0.1012 | 0.1101 | 0.0644 | 0.0241 | 0.0871 | 0.0542 |
| v42 | 0.1696 | 0.2567 | 0.1111 | 0.0147 | 0.0690 | 0.0737 |
| v5 | 0.1714 | 0.2596 | 0.1120 | 0.0162 | 0.0766 | 0.0762 |
| v5_exp | 0.1731 | 0.2575 | 0.1153 | 0.0186 | 0.0736 | 0.0832 |
| v5_flat | 0.1657 | 0.2474 | 0.1132 | 0.0113 | 0.0107 | 0.1198 |
| v5_lin | 0.1802 | 0.2579 | 0.1113 | 0.0322 | 0.0804 | 0.0709 |
| v5_nofc | 0.1713 | 0.2530 | 0.1113 | 0.0318 | 0.0473 | 0.0360 |

### Paired: v5 minus policy (all scenarios x repetitions)

| policy | metric | pairs | mean diff ± 95 % CI | wins | p (exact perm.) | p (Holm) |
|---|---|---|---|---|---|---|
| reward_offload | sAP_fc | 20 | +0.0497 ± 0.0068 | 20/20 | 0.0000 | 0.0000 |
| conf_trigger | sAP_fc | 20 | +0.0370 ± 0.0042 | 20/20 | 0.0000 | 0.0000 |
| fixed_laptop_m640q90 | sAP_fc | 20 | +0.0286 ± 0.0150 | 16/20 | 0.0014 | 0.0081 |
| jsq | sAP_fc | 20 | +0.0262 ± 0.0064 | 19/20 | 0.0000 | 0.0000 |
| aoi_thr | sAP_fc | 20 | +0.0204 ± 0.0040 | 20/20 | 0.0000 | 0.0000 |
| v5_flat | sAP_fc | 20 | +0.0185 ± 0.0077 | 17/20 | 0.0002 | 0.0011 |
| v5_nofc | sAP_fc | 20 | +0.0159 ± 0.0093 | 14/20 | 0.0021 | 0.0104 |
| v42 | sAP_fc | 20 | +0.0049 ± 0.0063 | 12/20 | 0.1255 | 0.5021 |
| v5_exp | sAP_fc | 20 | +0.0016 ± 0.0069 | 12/20 | 0.6739 | 1.0000 |
| leaf | sAP_fc | 20 | +0.0007 ± 0.0042 | 9/20 | 0.7897 | 1.0000 |
| v5_lin | sAP_fc | 20 | -0.0003 ± 0.0031 | 9/20 | 0.8651 | 1.0000 |
| reward_offload | sAP_masked_fc | 20 | +0.0502 ± 0.0068 | 20/20 | 0.0000 | 0.0000 |
| conf_trigger | sAP_masked_fc | 20 | +0.0375 ± 0.0042 | 20/20 | 0.0000 | 0.0000 |
| fixed_laptop_m640q90 | sAP_masked_fc | 20 | +0.0288 ± 0.0152 | 16/20 | 0.0014 | 0.0083 |
| jsq | sAP_masked_fc | 20 | +0.0264 ± 0.0065 | 19/20 | 0.0000 | 0.0000 |
| aoi_thr | sAP_masked_fc | 20 | +0.0208 ± 0.0041 | 20/20 | 0.0000 | 0.0000 |
| v5_flat | sAP_masked_fc | 20 | +0.0187 ± 0.0078 | 17/20 | 0.0002 | 0.0011 |
| v5_nofc | sAP_masked_fc | 20 | +0.0160 ± 0.0094 | 14/20 | 0.0022 | 0.0110 |
| v42 | sAP_masked_fc | 20 | +0.0048 ± 0.0063 | 12/20 | 0.1354 | 0.5416 |
| v5_exp | sAP_masked_fc | 20 | +0.0015 ± 0.0070 | 11/20 | 0.6903 | 1.0000 |
| leaf | sAP_masked_fc | 20 | +0.0007 ± 0.0042 | 9/20 | 0.8164 | 1.0000 |
| v5_lin | sAP_masked_fc | 20 | -0.0003 ± 0.0032 | 9/20 | 0.8616 | 1.0000 |
| reward_offload | sAP | 20 | +0.0214 ± 0.0041 | 20/20 | 0.0000 | 0.0000 |
| aoi_thr | sAP | 20 | +0.0166 ± 0.0039 | 20/20 | 0.0000 | 0.0000 |
| fixed_laptop_m640q90 | sAP | 20 | +0.0112 ± 0.0082 | 16/20 | 0.0118 | 0.0706 |
| v5_flat | sAP | 20 | +0.0110 ± 0.0046 | 17/20 | 0.0002 | 0.0020 |
| conf_trigger | sAP | 20 | +0.0099 ± 0.0025 | 19/20 | 0.0000 | 0.0000 |
| jsq | sAP | 20 | +0.0064 ± 0.0033 | 17/20 | 0.0010 | 0.0071 |
| v5_nofc | sAP | 20 | +0.0035 ± 0.0050 | 12/20 | 0.1589 | 0.6925 |
| v42 | sAP | 20 | +0.0024 ± 0.0032 | 13/20 | 0.1385 | 0.6925 |
| leaf | sAP | 20 | +0.0017 ± 0.0027 | 13/20 | 0.2179 | 0.6925 |
| v5_lin | sAP | 20 | -0.0003 ± 0.0018 | 9/20 | 0.7260 | 0.9052 |
| v5_exp | sAP | 20 | -0.0013 ± 0.0035 | 7/20 | 0.4526 | 0.9052 |
| reward_offload | sAP_quality_fc | 20 | +0.0278 ± 0.0035 | 20/20 | 0.0000 | 0.0000 |
| conf_trigger | sAP_quality_fc | 20 | +0.0214 ± 0.0027 | 20/20 | 0.0000 | 0.0000 |
| jsq | sAP_quality_fc | 20 | +0.0146 ± 0.0025 | 20/20 | 0.0000 | 0.0000 |
| aoi_thr | sAP_quality_fc | 20 | +0.0112 ± 0.0032 | 20/20 | 0.0000 | 0.0000 |
| fixed_laptop_m640q90 | sAP_quality_fc | 20 | +0.0076 ± 0.0057 | 16/20 | 0.0131 | 0.0655 |
| v5_nofc | sAP_quality_fc | 20 | +0.0059 ± 0.0042 | 14/20 | 0.0073 | 0.0437 |
| v5_flat | sAP_quality_fc | 20 | +0.0054 ± 0.0034 | 16/20 | 0.0028 | 0.0199 |
| v42 | sAP_quality_fc | 20 | +0.0018 ± 0.0024 | 11/20 | 0.1398 | 0.5594 |
| leaf | sAP_quality_fc | 20 | +0.0004 ± 0.0016 | 9/20 | 0.5924 | 1.0000 |
| v5_exp | sAP_quality_fc | 20 | +0.0002 ± 0.0026 | 8/20 | 0.8591 | 1.0000 |
| v5_lin | sAP_quality_fc | 20 | -0.0005 ± 0.0015 | 8/20 | 0.5170 | 1.0000 |

## vid_campaign_table - G13 (same-day table)
forecaster: v2live; reference(s): v41, v5; 80 runs

### All scenarios pooled (mean over runs)

| policy | n | sAP quality+fc (reported) | **sAP standard+fc** | sAP std+fc, masked | sAP50 masked+fc | small | medium | sAP std (no fc) | fresh AP masked | age p95 (ms) | age max (ms) | longest stale (s) | fresh share |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v41 | 20 | 0.0596 | **0.1437** | 0.1454 | 0.3288 | 0.1162 | 0.3133 | 0.0724 | 0.2176 | 222 | 670 | 0.6 | 0.988 |
| v51 | 20 | 0.0590 | **0.1424** | 0.1442 | 0.3274 | 0.1160 | 0.3133 | 0.0727 | 0.2160 | 230 | 550 | 0.3 | 0.989 |
| v5 | 20 | 0.0593 | **0.1373** | 0.1389 | 0.3177 | 0.1129 | 0.3015 | 0.0678 | 0.2247 | 373 | 1167 | 2.6 | 0.885 |
| onboard_n320 | 20 | 0.0169 | **0.0558** | 0.0562 | 0.1448 | 0.0422 | 0.1397 | 0.0218 | 0.1147 | 230 | 1490 | 0.9 | 0.992 |

### Per scenario: standard sAP with forecaster (masked), mean ± 95 % CI

| policy | mission | mission_mirror | random | static_good |
|---|---|---|---|---|
| onboard_n320 | 0.0570 ± 0.0018 | 0.0545 ± 0.0013 | 0.0561 ± 0.0029 | 0.0572 ± 0.0025 |
| v41 | 0.1234 ± 0.0063 | 0.1446 ± 0.0021 | 0.1095 ± 0.0259 | 0.2040 ± 0.0007 |
| v5 | 0.1121 ± 0.0154 | 0.1404 ± 0.0059 | 0.1077 ± 0.0118 | 0.1955 ± 0.0217 |
| v51 | 0.1257 ± 0.0036 | 0.1440 ± 0.0019 | 0.1059 ± 0.0174 | 0.2010 ± 0.0023 |

### mission: standard sAP with forecaster per phase

| policy | good | ground_congested | ground_blackout | both_degraded | total_blackout | recovered_low_battery |
|---|---|---|---|---|---|---|
| onboard_n320 | 0.0673 | 0.0690 | 0.0332 | 0.0253 | 0.0845 | 0.0562 |
| v41 | 0.1951 | 0.2214 | 0.1113 | 0.0281 | 0.0918 | 0.0600 |
| v5 | 0.1934 | 0.2148 | 0.0966 | 0.0255 | 0.0623 | 0.0936 |
| v51 | 0.1921 | 0.2310 | 0.0978 | 0.0190 | 0.0846 | 0.0798 |

### mission_mirror: standard sAP with forecaster per phase

| policy | good | edge_congested | edge_blackout | both_degraded | total_blackout | recovered_low_battery |
|---|---|---|---|---|---|---|
| onboard_n320 | 0.0661 | 0.0674 | 0.0331 | 0.0276 | 0.0791 | 0.0574 |
| v41 | 0.1956 | 0.2778 | 0.1234 | 0.0324 | 0.0912 | 0.0744 |
| v5 | 0.1970 | 0.2771 | 0.1256 | 0.0231 | 0.0777 | 0.0808 |
| v51 | 0.1964 | 0.2762 | 0.1249 | 0.0278 | 0.0925 | 0.0693 |

### Paired: v41 minus policy (all scenarios x repetitions)

| policy | metric | pairs | mean diff ± 95 % CI | wins | p (exact perm.) | p (Holm) |
|---|---|---|---|---|---|---|
| onboard_n320 | sAP_fc | 20 | +0.0878 ± 0.0177 | 20/20 | 0.0000 | 0.0000 |
| v5 | sAP_fc | 20 | +0.0064 ± 0.0065 | 14/20 | 0.0538 | 0.1076 |
| v51 | sAP_fc | 20 | +0.0012 ± 0.0025 | 11/20 | 0.3125 | 0.3125 |
| onboard_n320 | sAP_masked_fc | 20 | +0.0892 ± 0.0178 | 20/20 | 0.0000 | 0.0000 |
| v5 | sAP_masked_fc | 20 | +0.0065 ± 0.0066 | 14/20 | 0.0531 | 0.1063 |
| v51 | sAP_masked_fc | 20 | +0.0012 ± 0.0025 | 11/20 | 0.3308 | 0.3308 |
| onboard_n320 | sAP | 20 | +0.0506 ± 0.0123 | 20/20 | 0.0000 | 0.0000 |
| v5 | sAP | 20 | +0.0047 ± 0.0038 | 13/20 | 0.0105 | 0.0210 |
| v51 | sAP | 20 | -0.0002 ± 0.0012 | 8/20 | 0.7086 | 0.7086 |
| onboard_n320 | sAP_quality_fc | 20 | +0.0428 ± 0.0085 | 20/20 | 0.0000 | 0.0000 |
| v51 | sAP_quality_fc | 20 | +0.0006 ± 0.0012 | 10/20 | 0.3317 | 0.6635 |
| v5 | sAP_quality_fc | 20 | +0.0003 ± 0.0018 | 10/20 | 0.7160 | 0.7160 |

### Paired: v5 minus policy (all scenarios x repetitions)

| policy | metric | pairs | mean diff ± 95 % CI | wins | p (exact perm.) | p (Holm) |
|---|---|---|---|---|---|---|
| onboard_n320 | sAP_fc | 20 | +0.0815 ± 0.0172 | 20/20 | 0.0000 | 0.0000 |
| v51 | sAP_fc | 20 | -0.0051 ± 0.0058 | 5/20 | 0.0774 | 0.1076 |
| v41 | sAP_fc | 20 | -0.0064 ± 0.0065 | 6/20 | 0.0538 | 0.1076 |
| onboard_n320 | sAP_masked_fc | 20 | +0.0827 ± 0.0174 | 20/20 | 0.0000 | 0.0000 |
| v51 | sAP_masked_fc | 20 | -0.0052 ± 0.0058 | 5/20 | 0.0742 | 0.1063 |
| v41 | sAP_masked_fc | 20 | -0.0065 ± 0.0066 | 6/20 | 0.0531 | 0.1063 |
| onboard_n320 | sAP | 20 | +0.0460 ± 0.0130 | 20/20 | 0.0000 | 0.0000 |
| v41 | sAP | 20 | -0.0047 ± 0.0038 | 7/20 | 0.0105 | 0.0137 |
| v51 | sAP | 20 | -0.0049 ± 0.0036 | 5/20 | 0.0068 | 0.0137 |
| onboard_n320 | sAP_quality_fc | 20 | +0.0424 ± 0.0084 | 20/20 | 0.0000 | 0.0000 |
| v51 | sAP_quality_fc | 20 | +0.0003 ± 0.0017 | 12/20 | 0.6970 | 1.0000 |
| v41 | sAP_quality_fc | 20 | -0.0003 ± 0.0018 | 10/20 | 0.7160 | 1.0000 |

## vid_campaign_long - G13 (24-minute missions)
forecaster: v2live; reference(s): v41, v5; 12 runs

### All scenarios pooled (mean over runs)

| policy | n | sAP quality+fc (reported) | **sAP standard+fc** | sAP std+fc, masked | sAP50 masked+fc | small | medium | sAP std (no fc) | fresh AP masked | age p95 (ms) | age max (ms) | longest stale (s) | fresh share |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v41 | 2 | 0.0433 | **0.1094** | 0.1105 | 0.2569 | 0.0852 | 0.2587 | 0.0442 | 0.2019 | 283 | 1150 | 1.2 | 0.981 |
| v42 | 2 | 0.0373 | **0.1024** | 0.1033 | 0.2369 | 0.0795 | 0.2427 | 0.0449 | 0.1978 | 367 | 5233 | 5.0 | 0.912 |
| v5 | 2 | 0.0317 | **0.0907** | 0.0914 | 0.2142 | 0.0696 | 0.2163 | 0.0373 | 0.1954 | 600 | 6083 | 5.8 | 0.873 |
| v51 | 2 | 0.0317 | **0.0878** | 0.0885 | 0.2076 | 0.0683 | 0.2015 | 0.0361 | 0.1869 | 317 | 1333 | 1.1 | 0.944 |
| stream_fc2 | 2 | 0.0264 | **0.0764** | 0.0770 | 0.1859 | 0.0569 | 0.1917 | 0.0308 | 0.1794 | 283 | 533 | 0.2 | 0.991 |
| fixed_laptop_m640q90 | 2 | 0.0191 | **0.0414** | 0.0416 | 0.0956 | 0.0345 | 0.0873 | 0.0148 | 0.2414 | 205217 | 241267 | 280.6 | 0.187 |

### Per scenario: standard sAP with forecaster (masked), mean ± 95 % CI

| policy | mission |
|---|---|
| fixed_laptop_m640q90 | 0.0416 ± 0.0032 |
| stream_fc2 | 0.0770 ± 0.2776 |
| v41 | 0.1105 ± 0.0093 |
| v42 | 0.1033 ± 0.0536 |
| v5 | 0.0914 ± 0.0594 |
| v51 | 0.0885 ± 0.0617 |

### mission: standard sAP with forecaster per phase

| policy | good | ground_congested | ground_blackout | both_degraded | total_blackout | recovered_low_battery |
|---|---|---|---|---|---|---|
| fixed_laptop_m640q90 | 0.1963 | 0.0568 | 0.0005 | 0.0377 | 0.0008 | 0.0384 |
| stream_fc2 | 0.1347 | 0.0924 | 0.0976 | 0.0438 | 0.0447 | 0.0417 |
| v41 | 0.1919 | 0.1389 | 0.1588 | 0.0632 | 0.0415 | 0.0633 |
| v42 | 0.1985 | 0.1352 | 0.1268 | 0.0624 | 0.0451 | 0.0619 |
| v5 | 0.1881 | 0.1185 | 0.0977 | 0.0588 | 0.0457 | 0.0490 |
| v51 | 0.1924 | 0.0945 | 0.0829 | 0.0588 | 0.0417 | 0.0622 |

### Paired: v41 minus policy (all scenarios x repetitions)

| policy | metric | pairs | mean diff ± 95 % CI | wins | p (exact perm.) | p (Holm) |
|---|---|---|---|---|---|---|
| fixed_laptop_m640q90 | sAP_fc | 2 | +0.0681 ± 0.0141 | 2/2 | 0.5000 | 1.0000 |
| stream_fc2 | sAP_fc | 2 | +0.0330 ± 0.2829 | 2/2 | 0.5000 | 1.0000 |
| v51 | sAP_fc | 2 | +0.0217 ± 0.0706 | 2/2 | 0.5000 | 1.0000 |
| v5 | sAP_fc | 2 | +0.0187 ± 0.0679 | 2/2 | 0.5000 | 1.0000 |
| v42 | sAP_fc | 2 | +0.0070 ± 0.0433 | 2/2 | 0.5000 | 1.0000 |
| fixed_laptop_m640q90 | sAP_masked_fc | 2 | +0.0689 ± 0.0126 | 2/2 | 0.5000 | 1.0000 |
| stream_fc2 | sAP_masked_fc | 2 | +0.0334 ± 0.2870 | 2/2 | 0.5000 | 1.0000 |
| v51 | sAP_masked_fc | 2 | +0.0220 ± 0.0710 | 2/2 | 0.5000 | 1.0000 |
| v5 | sAP_masked_fc | 2 | +0.0190 ± 0.0688 | 2/2 | 0.5000 | 1.0000 |
| v42 | sAP_masked_fc | 2 | +0.0072 ± 0.0443 | 2/2 | 0.5000 | 1.0000 |
| fixed_laptop_m640q90 | sAP | 2 | +0.0293 ± 0.0233 | 2/2 | 0.5000 | 1.0000 |
| stream_fc2 | sAP | 2 | +0.0134 ± 0.1643 | 2/2 | 0.5000 | 1.0000 |
| v51 | sAP | 2 | +0.0080 ± 0.0609 | 2/2 | 0.5000 | 1.0000 |
| v5 | sAP | 2 | +0.0068 ± 0.0668 | 2/2 | 0.5000 | 1.0000 |
| v42 | sAP | 2 | -0.0007 ± 0.0028 | 0/2 | 0.5000 | 1.0000 |
| fixed_laptop_m640q90 | sAP_quality_fc | 2 | +0.0243 ± 0.0047 | 2/2 | 0.5000 | 1.0000 |
| stream_fc2 | sAP_quality_fc | 2 | +0.0169 ± 0.1186 | 2/2 | 0.5000 | 1.0000 |
| v5 | sAP_quality_fc | 2 | +0.0116 ± 0.0220 | 2/2 | 0.5000 | 1.0000 |
| v51 | sAP_quality_fc | 2 | +0.0116 ± 0.0362 | 2/2 | 0.5000 | 1.0000 |
| v42 | sAP_quality_fc | 2 | +0.0060 ± 0.0051 | 2/2 | 0.5000 | 1.0000 |

### Paired: v5 minus policy (all scenarios x repetitions)

| policy | metric | pairs | mean diff ± 95 % CI | wins | p (exact perm.) | p (Holm) |
|---|---|---|---|---|---|---|
| fixed_laptop_m640q90 | sAP_fc | 2 | +0.0493 ± 0.0538 | 2/2 | 0.5000 | 1.0000 |
| stream_fc2 | sAP_fc | 2 | +0.0143 ± 0.2149 | 1/2 | 1.0000 | 1.0000 |
| v51 | sAP_fc | 2 | +0.0029 ± 0.0026 | 2/2 | 0.5000 | 1.0000 |
| v42 | sAP_fc | 2 | -0.0117 ± 0.1112 | 0/2 | 0.5000 | 1.0000 |
| v41 | sAP_fc | 2 | -0.0187 ± 0.0679 | 0/2 | 0.5000 | 1.0000 |
| fixed_laptop_m640q90 | sAP_masked_fc | 2 | +0.0498 ± 0.0562 | 2/2 | 0.5000 | 1.0000 |
| stream_fc2 | sAP_masked_fc | 2 | +0.0144 ± 0.2182 | 1/2 | 1.0000 | 1.0000 |
| v51 | sAP_masked_fc | 2 | +0.0029 ± 0.0022 | 2/2 | 0.5000 | 1.0000 |
| v42 | sAP_masked_fc | 2 | -0.0119 ± 0.1130 | 0/2 | 0.5000 | 1.0000 |
| v41 | sAP_masked_fc | 2 | -0.0190 ± 0.0688 | 0/2 | 0.5000 | 1.0000 |
| fixed_laptop_m640q90 | sAP | 2 | +0.0225 ± 0.0435 | 2/2 | 0.5000 | 1.0000 |
| stream_fc2 | sAP | 2 | +0.0066 ± 0.0974 | 1/2 | 1.0000 | 1.0000 |
| v51 | sAP | 2 | +0.0012 ± 0.0059 | 2/2 | 0.5000 | 1.0000 |
| v41 | sAP | 2 | -0.0068 ± 0.0668 | 0/2 | 0.5000 | 1.0000 |
| v42 | sAP | 2 | -0.0075 ± 0.0696 | 0/2 | 0.5000 | 1.0000 |
| fixed_laptop_m640q90 | sAP_quality_fc | 2 | +0.0126 ± 0.0267 | 2/2 | 0.5000 | 1.0000 |
| stream_fc2 | sAP_quality_fc | 2 | +0.0053 ± 0.0967 | 1/2 | 1.0000 | 1.0000 |
| v51 | sAP_quality_fc | 2 | -0.0000 ± 0.0142 | 1/2 | 1.0000 | 1.0000 |
| v42 | sAP_quality_fc | 2 | -0.0056 ± 0.0271 | 0/2 | 0.5000 | 1.0000 |
| v41 | sAP_quality_fc | 2 | -0.0116 ± 0.0220 | 0/2 | 0.5000 | 1.0000 |
