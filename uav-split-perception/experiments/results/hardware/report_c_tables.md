# Task C: standard-metric rescoring of every VisDrone-VID campaign

sAP = streaming AP, standard 'newest' holding rule unless marked 'quality'. 'masked' = VisDrone ignored regions masked (official protocol). +fc = with the campaign's forecaster (v2 offline for the Part 12/14 campaigns, v2 computed live on the Pi from the 80-run campaign on). Sizes: COCO area ranges in the 640-px frame (91 % of the objects are small, 9 % medium, 7 objects large -> not reported). Freshness: age of the held result at each camera frame (30 fps); stale = older than 300 ms. Compare numbers within one campaign only.

## vid_campaign_wifi - Part 12 (108 runs, shared Wi-Fi)
forecaster: v2; reference(s): A_full; 108 runs

### All scenarios pooled (mean over runs)

| policy | n | sAP quality+fc (reported) | **sAP standard+fc** | sAP std+fc, masked | sAP50 masked+fc | small | medium | sAP std (no fc) | fresh AP masked | age p95 (ms) | age max (ms) | longest stale (s) | fresh share |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fixed_laptop_m640q90 | 12 | 0.0452 | **0.0462** | 0.0470 | 0.1063 | 0.0277 | 0.1391 | 0.0194 | 0.1157 | 12556 | 16461 | 45.8 | 0.530 |
| A_full_aer | 12 | 0.0443 | **0.0452** | 0.0458 | 0.1127 | 0.0305 | 0.1361 | 0.0204 | 0.0768 | 344 | 442 | 0.1 | 0.886 |
| abr_laptop | 12 | 0.0439 | **0.0442** | 0.0448 | 0.1055 | 0.0299 | 0.1343 | 0.0208 | 0.0764 | 12067 | 15983 | 15.9 | 0.808 |
| A_stream | 12 | 0.0421 | **0.0430** | 0.0435 | 0.1075 | 0.0288 | 0.1308 | 0.0189 | 0.0738 | 358 | 511 | 0.2 | 0.861 |
| A_full | 12 | 0.0423 | **0.0427** | 0.0433 | 0.1062 | 0.0291 | 0.1341 | 0.0231 | 0.0647 | 292 | 519 | 0.2 | 0.916 |
| static_multi | 12 | 0.0408 | **0.0393** | 0.0396 | 0.0989 | 0.0269 | 0.1300 | 0.0221 | 0.0565 | 183 | 283 | 0.0 | 1.000 |
| rule_fallback | 12 | 0.0382 | **0.0386** | 0.0390 | 0.0996 | 0.0259 | 0.1209 | 0.0162 | 0.0841 | 919 | 2975 | 17.0 | 0.639 |
| fixed_jetson_s640q90 | 12 | 0.0333 | **0.0343** | 0.0347 | 0.0906 | 0.0236 | 0.1032 | 0.0135 | 0.0923 | 10731 | 14497 | 45.9 | 0.500 |
| fixed_onboard_n320 | 12 | 0.0182 | **0.0182** | 0.0184 | 0.0498 | 0.0088 | 0.0790 | 0.0071 | 0.0282 | 194 | 1419 | 1.0 | 0.992 |

### Per scenario: standard sAP with forecaster (masked), mean ± 95 % CI

| policy | mission | mission_mirror | random | static_good |
|---|---|---|---|---|
| A_full | 0.0395 ± 0.0033 | 0.0346 ± 0.0413 | 0.0377 ± 0.0065 | 0.0613 ± 0.0108 |
| A_full_aer | 0.0412 ± 0.0043 | 0.0459 ± 0.0148 | 0.0421 ± 0.0065 | 0.0541 ± 0.0414 |
| A_stream | 0.0384 ± 0.0085 | 0.0503 ± 0.0080 | 0.0370 ± 0.0128 | 0.0482 ± 0.0614 |
| abr_laptop | 0.0260 ± 0.0060 | 0.0478 ± 0.0166 | 0.0363 ± 0.0019 | 0.0690 ± 0.0233 |
| fixed_jetson_s640q90 | 0.0383 ± 0.0034 | 0.0189 ± 0.0011 | 0.0257 ± 0.0232 | 0.0560 ± 0.0117 |
| fixed_laptop_m640q90 | 0.0224 ± 0.0024 | 0.0489 ± 0.0062 | 0.0355 ± 0.0154 | 0.0812 ± 0.0073 |
| fixed_onboard_n320 | 0.0188 ± 0.0008 | 0.0185 ± 0.0027 | 0.0183 ± 0.0021 | 0.0181 ± 0.0008 |
| rule_fallback | 0.0254 ± 0.0014 | 0.0381 ± 0.0039 | 0.0281 ± 0.0120 | 0.0642 ± 0.0079 |
| static_multi | 0.0341 ± 0.0084 | 0.0394 ± 0.0034 | 0.0318 ± 0.0093 | 0.0533 ± 0.0068 |

### mission: standard sAP with forecaster per phase

| policy | good | ground_congested | ground_blackout | both_degraded | total_blackout | recovered_low_battery |
|---|---|---|---|---|---|---|
| A_full | 0.0858 | 0.0823 | 0.0317 | 0.0036 | 0.0118 | 0.0373 |
| A_full_aer | 0.0929 | 0.0874 | 0.0343 | 0.0038 | 0.0113 | 0.0257 |
| A_stream | 0.0809 | 0.0813 | 0.0326 | 0.0066 | 0.0116 | 0.0244 |
| abr_laptop | 0.0978 | 0.0534 | 0.0003 | 0.0011 | 0.0000 | 0.0327 |
| fixed_jetson_s640q90 | 0.0875 | 0.0928 | 0.0423 | 0.0088 | 0.0001 | 0.0166 |
| fixed_laptop_m640q90 | 0.0872 | 0.0473 | 0.0003 | 0.0071 | 0.0002 | 0.0493 |
| fixed_onboard_n320 | 0.0319 | 0.0318 | 0.0087 | 0.0060 | 0.0202 | 0.0268 |
| rule_fallback | 0.0731 | 0.0346 | 0.0381 | 0.0092 | 0.0201 | 0.0128 |
| static_multi | 0.0718 | 0.0592 | 0.0305 | 0.0058 | 0.0200 | 0.0256 |

### mission_mirror: standard sAP with forecaster per phase

| policy | good | edge_congested | edge_blackout | both_degraded | total_blackout | recovered_low_battery |
|---|---|---|---|---|---|---|
| A_full | 0.0682 | 0.0702 | 0.0316 | 0.0034 | 0.0112 | 0.0375 |
| A_full_aer | 0.0836 | 0.0988 | 0.0451 | 0.0045 | 0.0119 | 0.0322 |
| A_stream | 0.0871 | 0.1033 | 0.0558 | 0.0057 | 0.0115 | 0.0304 |
| abr_laptop | 0.0875 | 0.0988 | 0.0575 | 0.0071 | 0.0002 | 0.0318 |
| fixed_jetson_s640q90 | 0.0826 | 0.0389 | 0.0003 | 0.0068 | 0.0001 | 0.0229 |
| fixed_laptop_m640q90 | 0.0904 | 0.1105 | 0.0600 | 0.0091 | 0.0002 | 0.0379 |
| fixed_onboard_n320 | 0.0317 | 0.0308 | 0.0083 | 0.0059 | 0.0199 | 0.0272 |
| rule_fallback | 0.0815 | 0.0865 | 0.0400 | 0.0080 | 0.0186 | 0.0134 |
| static_multi | 0.0754 | 0.0792 | 0.0331 | 0.0056 | 0.0190 | 0.0228 |

### Paired: A_full minus policy (all scenarios x repetitions)

| policy | metric | pairs | mean diff ± 95 % CI | wins | p (exact perm.) | p (Holm) |
|---|---|---|---|---|---|---|
| fixed_onboard_n320 | sAP_fc | 12 | +0.0245 ± 0.0082 | 11/12 | 0.0010 | 0.0078 |
| fixed_jetson_s640q90 | sAP_fc | 12 | +0.0084 ± 0.0062 | 10/12 | 0.0063 | 0.0444 |
| rule_fallback | sAP_fc | 12 | +0.0041 ± 0.0073 | 9/12 | 0.2363 | 1.0000 |
| static_multi | sAP_fc | 12 | +0.0034 ± 0.0056 | 11/12 | 0.2139 | 1.0000 |
| A_stream | sAP_fc | 12 | -0.0003 ± 0.0095 | 5/12 | 0.9302 | 1.0000 |
| abr_laptop | sAP_fc | 12 | -0.0015 ± 0.0084 | 7/12 | 0.7207 | 1.0000 |
| A_full_aer | sAP_fc | 12 | -0.0025 ± 0.0082 | 2/12 | 0.5381 | 1.0000 |
| fixed_laptop_m640q90 | sAP_fc | 12 | -0.0035 ± 0.0110 | 4/12 | 0.5024 | 1.0000 |
| fixed_onboard_n320 | sAP_masked_fc | 12 | +0.0248 ± 0.0084 | 11/12 | 0.0010 | 0.0078 |
| fixed_jetson_s640q90 | sAP_masked_fc | 12 | +0.0085 ± 0.0063 | 10/12 | 0.0068 | 0.0479 |
| rule_fallback | sAP_masked_fc | 12 | +0.0043 ± 0.0074 | 9/12 | 0.2227 | 1.0000 |
| static_multi | sAP_masked_fc | 12 | +0.0036 ± 0.0057 | 11/12 | 0.1899 | 1.0000 |
| A_stream | sAP_masked_fc | 12 | -0.0002 ± 0.0097 | 5/12 | 0.9468 | 1.0000 |
| abr_laptop | sAP_masked_fc | 12 | -0.0015 ± 0.0085 | 7/12 | 0.7251 | 1.0000 |
| A_full_aer | sAP_masked_fc | 12 | -0.0026 ± 0.0083 | 3/12 | 0.5400 | 1.0000 |
| fixed_laptop_m640q90 | sAP_masked_fc | 12 | -0.0037 ± 0.0111 | 4/12 | 0.4819 | 1.0000 |
| fixed_onboard_n320 | sAP | 12 | +0.0160 ± 0.0054 | 11/12 | 0.0010 | 0.0078 |
| fixed_jetson_s640q90 | sAP | 12 | +0.0096 ± 0.0038 | 11/12 | 0.0010 | 0.0078 |
| rule_fallback | sAP | 12 | +0.0069 ± 0.0043 | 10/12 | 0.0107 | 0.0645 |
| A_stream | sAP | 12 | +0.0042 ± 0.0055 | 10/12 | 0.1250 | 0.6250 |
| fixed_laptop_m640q90 | sAP | 12 | +0.0037 ± 0.0052 | 9/12 | 0.1504 | 0.6250 |
| A_full_aer | sAP | 12 | +0.0027 ± 0.0050 | 10/12 | 0.3032 | 0.7427 |
| abr_laptop | sAP | 12 | +0.0023 ± 0.0042 | 10/12 | 0.2476 | 0.7427 |
| static_multi | sAP | 12 | +0.0010 ± 0.0034 | 8/12 | 0.5640 | 0.7427 |
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
| A_stream | 12 | 0.0520 | **0.0527** | 0.0534 | 0.1257 | 0.0360 | 0.1525 | 0.0255 | 0.0819 | 347 | 472 | 0.2 | 0.880 |
| A_stream_fc | 12 | 0.0492 | **0.0466** | 0.0473 | 0.1109 | 0.0298 | 0.1444 | 0.0249 | 0.0778 | 217 | 364 | 0.1 | 0.998 |
| A_full | 12 | 0.0471 | **0.0461** | 0.0467 | 0.1117 | 0.0313 | 0.1397 | 0.0239 | 0.0695 | 317 | 472 | 0.2 | 0.897 |

### Per scenario: standard sAP with forecaster (masked), mean ± 95 % CI

| policy | mission | mission_mirror | random | static_good |
|---|---|---|---|---|
| A_full | 0.0343 ± 0.0148 | 0.0359 ± 0.0504 | 0.0391 ± 0.0126 | 0.0777 ± 0.0071 |
| A_stream | 0.0389 ± 0.0075 | 0.0494 ± 0.0242 | 0.0428 ± 0.0146 | 0.0826 ± 0.0040 |
| A_stream_fc | 0.0339 ± 0.0320 | 0.0496 ± 0.0096 | 0.0335 ± 0.0191 | 0.0722 ± 0.0195 |

### mission: standard sAP with forecaster per phase

| policy | good | ground_congested | ground_blackout | both_degraded | total_blackout | recovered_low_battery |
|---|---|---|---|---|---|---|
| A_full | 0.0752 | 0.0692 | 0.0240 | 0.0026 | 0.0115 | 0.0356 |
| A_stream | 0.0925 | 0.0725 | 0.0388 | 0.0063 | 0.0106 | 0.0254 |
| A_stream_fc | 0.0762 | 0.0601 | 0.0272 | 0.0051 | 0.0180 | 0.0223 |

### mission_mirror: standard sAP with forecaster per phase

| policy | good | edge_congested | edge_blackout | both_degraded | total_blackout | recovered_low_battery |
|---|---|---|---|---|---|---|
| A_full | 0.0736 | 0.0635 | 0.0437 | 0.0043 | 0.0111 | 0.0325 |
| A_stream | 0.0909 | 0.1063 | 0.0480 | 0.0054 | 0.0111 | 0.0302 |
| A_stream_fc | 0.0882 | 0.0976 | 0.0562 | 0.0050 | 0.0179 | 0.0219 |

### Paired: A_full minus policy (all scenarios x repetitions)

| policy | metric | pairs | mean diff ± 95 % CI | wins | p (exact perm.) | p (Holm) |
|---|---|---|---|---|---|---|
| A_stream_fc | sAP_fc | 12 | -0.0005 ± 0.0085 | 7/12 | 0.9238 | 0.9238 |
| A_stream | sAP_fc | 12 | -0.0066 ± 0.0045 | 1/12 | 0.0024 | 0.0049 |
| A_stream_fc | sAP_masked_fc | 12 | -0.0006 ± 0.0087 | 7/12 | 0.9077 | 0.9077 |
| A_stream | sAP_masked_fc | 12 | -0.0067 ± 0.0045 | 1/12 | 0.0020 | 0.0039 |
| A_stream_fc | sAP | 12 | -0.0009 ± 0.0049 | 6/12 | 0.7256 | 0.7256 |
| A_stream | sAP | 12 | -0.0016 ± 0.0029 | 6/12 | 0.2646 | 0.5293 |
| A_stream_fc | sAP_quality_fc | 12 | -0.0020 ± 0.0085 | 6/12 | 0.6631 | 0.6631 |
| A_stream | sAP_quality_fc | 12 | -0.0048 ± 0.0050 | 4/12 | 0.0483 | 0.0967 |

## vid_campaign_wifi_fc2 - Part 14 (80-run campaign, live forecaster v2)
forecaster: v2live; reference(s): A_full, A_stream_fc2; 80 runs

### All scenarios pooled (mean over runs)

| policy | n | sAP quality+fc (reported) | **sAP standard+fc** | sAP std+fc, masked | sAP50 masked+fc | small | medium | sAP std (no fc) | fresh AP masked | age p95 (ms) | age max (ms) | longest stale (s) | fresh share |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_stream_fc2 | 20 | 0.0508 | **0.0505** | 0.0513 | 0.1185 | 0.0337 | 0.1519 | 0.0273 | 0.0812 | 205 | 457 | 0.1 | 0.998 |
| A_stream_fc | 20 | 0.0472 | **0.0469** | 0.0475 | 0.1113 | 0.0307 | 0.1435 | 0.0251 | 0.0784 | 212 | 482 | 0.2 | 0.998 |
| A_full | 20 | 0.0463 | **0.0467** | 0.0473 | 0.1130 | 0.0322 | 0.1388 | 0.0246 | 0.0723 | 338 | 610 | 0.3 | 0.872 |
| fixed_laptop_m640q90 | 20 | 0.0409 | **0.0421** | 0.0428 | 0.0962 | 0.0257 | 0.1294 | 0.0210 | 0.1224 | 18898 | 22985 | 54.8 | 0.440 |

### Per scenario: standard sAP with forecaster (masked), mean ± 95 % CI

| policy | mission | mission_mirror | random | static_good |
|---|---|---|---|---|
| A_full | 0.0359 ± 0.0089 | 0.0483 ± 0.0145 | 0.0345 ± 0.0135 | 0.0706 ± 0.0355 |
| A_stream_fc | 0.0428 ± 0.0053 | 0.0506 ± 0.0141 | 0.0348 ± 0.0084 | 0.0620 ± 0.0453 |
| A_stream_fc2 | 0.0435 ± 0.0070 | 0.0547 ± 0.0080 | 0.0296 ± 0.0121 | 0.0773 ± 0.0319 |
| fixed_laptop_m640q90 | 0.0211 ± 0.0062 | 0.0518 ± 0.0044 | 0.0283 ± 0.0168 | 0.0699 ± 0.0482 |

### mission: standard sAP with forecaster per phase

| policy | good | ground_congested | ground_blackout | both_degraded | total_blackout | recovered_low_battery |
|---|---|---|---|---|---|---|
| A_full | 0.0779 | 0.0747 | 0.0298 | 0.0028 | 0.0098 | 0.0336 |
| A_stream_fc | 0.0868 | 0.0864 | 0.0316 | 0.0051 | 0.0189 | 0.0236 |
| A_stream_fc2 | 0.0914 | 0.0858 | 0.0335 | 0.0051 | 0.0184 | 0.0212 |
| fixed_laptop_m640q90 | 0.0967 | 0.0426 | 0.0001 | 0.0071 | 0.0003 | 0.0468 |

### mission_mirror: standard sAP with forecaster per phase

| policy | good | edge_congested | edge_blackout | both_degraded | total_blackout | recovered_low_battery |
|---|---|---|---|---|---|---|
| A_full | 0.0899 | 0.0974 | 0.0532 | 0.0042 | 0.0096 | 0.0384 |
| A_stream_fc | 0.0850 | 0.0900 | 0.0653 | 0.0053 | 0.0178 | 0.0202 |
| A_stream_fc2 | 0.0912 | 0.1120 | 0.0569 | 0.0051 | 0.0181 | 0.0201 |
| fixed_laptop_m640q90 | 0.1003 | 0.1166 | 0.0622 | 0.0090 | 0.0002 | 0.0375 |

### Paired: A_full minus policy (all scenarios x repetitions)

| policy | metric | pairs | mean diff ± 95 % CI | wins | p (exact perm.) | p (Holm) |
|---|---|---|---|---|---|---|
| fixed_laptop_m640q90 | sAP_fc | 20 | +0.0046 ± 0.0057 | 14/20 | 0.1074 | 0.3222 |
| A_stream_fc | sAP_fc | 20 | -0.0002 ± 0.0079 | 7/20 | 0.9829 | 0.9829 |
| A_stream_fc2 | sAP_fc | 20 | -0.0038 ± 0.0039 | 6/20 | 0.0554 | 0.2215 |
| fixed_laptop_m640q90 | sAP_masked_fc | 20 | +0.0045 ± 0.0057 | 14/20 | 0.1132 | 0.3395 |
| A_stream_fc | sAP_masked_fc | 20 | -0.0002 ± 0.0080 | 7/20 | 0.9764 | 0.9764 |
| A_stream_fc2 | sAP_masked_fc | 20 | -0.0039 ± 0.0039 | 6/20 | 0.0501 | 0.2004 |
| fixed_laptop_m640q90 | sAP | 20 | +0.0036 ± 0.0033 | 15/20 | 0.0319 | 0.0956 |
| A_stream_fc | sAP | 20 | -0.0005 ± 0.0051 | 7/20 | 0.8953 | 0.8953 |
| A_stream_fc2 | sAP | 20 | -0.0027 ± 0.0023 | 3/20 | 0.0238 | 0.0951 |
| fixed_laptop_m640q90 | sAP_quality_fc | 20 | +0.0054 ± 0.0058 | 15/20 | 0.0684 | 0.2052 |
| A_stream_fc | sAP_quality_fc | 20 | -0.0009 ± 0.0081 | 6/20 | 0.9108 | 0.9108 |
| A_stream_fc2 | sAP_quality_fc | 20 | -0.0045 ± 0.0038 | 7/20 | 0.0208 | 0.0834 |

### Paired: A_stream_fc2 minus policy (all scenarios x repetitions)

| policy | metric | pairs | mean diff ± 95 % CI | wins | p (exact perm.) | p (Holm) |
|---|---|---|---|---|---|---|
| fixed_laptop_m640q90 | sAP_fc | 20 | +0.0084 ± 0.0054 | 15/20 | 0.0040 | 0.0201 |
| A_full | sAP_fc | 20 | +0.0038 ± 0.0039 | 14/20 | 0.0554 | 0.2215 |
| A_stream_fc | sAP_fc | 20 | +0.0036 ± 0.0069 | 11/20 | 0.3340 | 0.6680 |
| fixed_laptop_m640q90 | sAP_masked_fc | 20 | +0.0085 ± 0.0054 | 15/20 | 0.0040 | 0.0199 |
| A_full | sAP_masked_fc | 20 | +0.0039 ± 0.0039 | 14/20 | 0.0501 | 0.2004 |
| A_stream_fc | sAP_masked_fc | 20 | +0.0037 ± 0.0071 | 11/20 | 0.3357 | 0.6714 |
| fixed_laptop_m640q90 | sAP | 20 | +0.0063 ± 0.0025 | 18/20 | 0.0000 | 0.0002 |
| A_full | sAP | 20 | +0.0027 ± 0.0023 | 17/20 | 0.0238 | 0.0951 |
| A_stream_fc | sAP | 20 | +0.0021 ± 0.0042 | 10/20 | 0.3599 | 0.7199 |
| fixed_laptop_m640q90 | sAP_quality_fc | 20 | +0.0099 ± 0.0053 | 18/20 | 0.0005 | 0.0023 |
| A_full | sAP_quality_fc | 20 | +0.0045 ± 0.0038 | 13/20 | 0.0208 | 0.0834 |
| A_stream_fc | sAP_quality_fc | 20 | +0.0037 ± 0.0070 | 12/20 | 0.3477 | 0.6954 |

## vid_campaign_energy - G9 (energy campaign)
forecaster: v2live; reference(s): A_stream_fc2; 100 runs

### All scenarios pooled (mean over runs)

| policy | n | sAP quality+fc (reported) | **sAP standard+fc** | sAP std+fc, masked | sAP50 masked+fc | small | medium | sAP std (no fc) | fresh AP masked | age p95 (ms) | age max (ms) | longest stale (s) | fresh share |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_eco_tight | 20 | 0.0543 | **0.0547** | 0.0554 | 0.1299 | 0.0358 | 0.1598 | 0.0249 | 0.0914 | 398 | 1010 | 3.1 | 0.890 |
| A_eco | 20 | 0.0525 | **0.0523** | 0.0531 | 0.1248 | 0.0340 | 0.1544 | 0.0239 | 0.0891 | 398 | 993 | 2.6 | 0.885 |
| fixed_laptop_m640q90 | 20 | 0.0463 | **0.0474** | 0.0481 | 0.1088 | 0.0291 | 0.1436 | 0.0218 | 0.1144 | 11604 | 15168 | 46.7 | 0.520 |
| A_full | 20 | 0.0465 | **0.0469** | 0.0476 | 0.1142 | 0.0328 | 0.1438 | 0.0266 | 0.0703 | 332 | 527 | 0.2 | 0.902 |
| A_stream_fc2 | 20 | 0.0470 | **0.0458** | 0.0464 | 0.1086 | 0.0293 | 0.1400 | 0.0238 | 0.0791 | 238 | 438 | 0.2 | 0.997 |

### Per scenario: standard sAP with forecaster (masked), mean ± 95 % CI

| policy | mission | mission_mirror | random | static_good |
|---|---|---|---|---|
| A_eco | 0.0406 ± 0.0064 | 0.0518 ± 0.0105 | 0.0434 ± 0.0089 | 0.0765 ± 0.0143 |
| A_eco_tight | 0.0461 ± 0.0056 | 0.0563 ± 0.0083 | 0.0421 ± 0.0031 | 0.0771 ± 0.0136 |
| A_full | 0.0367 ± 0.0060 | 0.0480 ± 0.0124 | 0.0400 ± 0.0057 | 0.0656 ± 0.0192 |
| A_stream_fc2 | 0.0331 ± 0.0097 | 0.0542 ± 0.0112 | 0.0290 ± 0.0073 | 0.0694 ± 0.0229 |
| fixed_laptop_m640q90 | 0.0226 ± 0.0010 | 0.0525 ± 0.0023 | 0.0342 ± 0.0034 | 0.0829 ± 0.0055 |

### mission: standard sAP with forecaster per phase

| policy | good | ground_congested | ground_blackout | both_degraded | total_blackout | recovered_low_battery |
|---|---|---|---|---|---|---|
| A_eco | 0.0878 | 0.0709 | 0.0416 | 0.0080 | 0.0185 | 0.0237 |
| A_eco_tight | 0.0939 | 0.0847 | 0.0439 | 0.0099 | 0.0201 | 0.0288 |
| A_full | 0.0925 | 0.0789 | 0.0229 | 0.0033 | 0.0088 | 0.0352 |
| A_stream_fc2 | 0.0755 | 0.0571 | 0.0279 | 0.0046 | 0.0172 | 0.0203 |
| fixed_laptop_m640q90 | 0.0989 | 0.0481 | 0.0004 | 0.0072 | 0.0002 | 0.0484 |

### mission_mirror: standard sAP with forecaster per phase

| policy | good | edge_congested | edge_blackout | both_degraded | total_blackout | recovered_low_battery |
|---|---|---|---|---|---|---|
| A_eco | 0.0914 | 0.1015 | 0.0542 | 0.0078 | 0.0185 | 0.0287 |
| A_eco_tight | 0.0891 | 0.1087 | 0.0651 | 0.0104 | 0.0197 | 0.0310 |
| A_full | 0.0847 | 0.1022 | 0.0531 | 0.0044 | 0.0091 | 0.0355 |
| A_stream_fc2 | 0.0927 | 0.1105 | 0.0626 | 0.0045 | 0.0163 | 0.0179 |
| fixed_laptop_m640q90 | 0.0977 | 0.1178 | 0.0690 | 0.0088 | 0.0001 | 0.0383 |

### Paired: A_stream_fc2 minus policy (all scenarios x repetitions)

| policy | metric | pairs | mean diff ± 95 % CI | wins | p (exact perm.) | p (Holm) |
|---|---|---|---|---|---|---|
| A_full | sAP_fc | 20 | -0.0012 ± 0.0044 | 11/20 | 0.5729 | 1.0000 |
| fixed_laptop_m640q90 | sAP_fc | 20 | -0.0016 ± 0.0059 | 11/20 | 0.5795 | 1.0000 |
| A_eco | sAP_fc | 20 | -0.0066 ± 0.0053 | 4/20 | 0.0187 | 0.0560 |
| A_eco_tight | sAP_fc | 20 | -0.0089 ± 0.0038 | 3/20 | 0.0001 | 0.0005 |
| A_full | sAP_masked_fc | 20 | -0.0011 ± 0.0044 | 11/20 | 0.5926 | 1.0000 |
| fixed_laptop_m640q90 | sAP_masked_fc | 20 | -0.0016 ± 0.0061 | 11/20 | 0.5779 | 1.0000 |
| A_eco | sAP_masked_fc | 20 | -0.0066 ± 0.0054 | 4/20 | 0.0192 | 0.0577 |
| A_eco_tight | sAP_masked_fc | 20 | -0.0090 ± 0.0038 | 3/20 | 0.0001 | 0.0005 |
| fixed_laptop_m640q90 | sAP | 20 | +0.0020 ± 0.0028 | 15/20 | 0.1468 | 0.4403 |
| A_eco | sAP | 20 | -0.0001 ± 0.0031 | 9/20 | 0.9443 | 0.9443 |
| A_eco_tight | sAP | 20 | -0.0011 ± 0.0021 | 5/20 | 0.2765 | 0.5530 |
| A_full | sAP | 20 | -0.0028 ± 0.0023 | 6/20 | 0.0224 | 0.0897 |
| fixed_laptop_m640q90 | sAP_quality_fc | 20 | +0.0007 ± 0.0059 | 12/20 | 0.8190 | 1.0000 |
| A_full | sAP_quality_fc | 20 | +0.0005 ± 0.0039 | 12/20 | 0.8051 | 1.0000 |
| A_eco | sAP_quality_fc | 20 | -0.0055 ± 0.0046 | 5/20 | 0.0222 | 0.0665 |
| A_eco_tight | sAP_quality_fc | 20 | -0.0074 ± 0.0030 | 3/20 | 0.0001 | 0.0002 |

## vid_campaign_v42 - G11 (live power on both boards)
forecaster: v2live; reference(s): A_eco_tight; 120 runs

### All scenarios pooled (mean over runs)

| policy | n | sAP quality+fc (reported) | **sAP standard+fc** | sAP std+fc, masked | sAP50 masked+fc | small | medium | sAP std (no fc) | fresh AP masked | age p95 (ms) | age max (ms) | longest stale (s) | fresh share |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_eco41 | 20 | 0.0566 | **0.0569** | 0.0576 | 0.1345 | 0.0380 | 0.1645 | 0.0274 | 0.0873 | 228 | 785 | 0.7 | 0.985 |
| A_eco42 | 20 | 0.0551 | **0.0550** | 0.0558 | 0.1314 | 0.0369 | 0.1596 | 0.0256 | 0.0912 | 1714 | 3480 | 3.4 | 0.881 |
| A_eco_tight | 20 | 0.0541 | **0.0549** | 0.0557 | 0.1304 | 0.0362 | 0.1621 | 0.0251 | 0.0925 | 400 | 1185 | 2.3 | 0.892 |
| A_eco42d | 20 | 0.0536 | **0.0535** | 0.0542 | 0.1270 | 0.0354 | 0.1572 | 0.0252 | 0.0887 | 438 | 1032 | 2.4 | 0.888 |
| A_stream_fc2 | 20 | 0.0485 | **0.0466** | 0.0473 | 0.1110 | 0.0302 | 0.1434 | 0.0242 | 0.0802 | 225 | 423 | 0.1 | 0.997 |
| fixed_laptop_m640q90 | 20 | 0.0450 | **0.0463** | 0.0470 | 0.1068 | 0.0281 | 0.1410 | 0.0210 | 0.1171 | 11651 | 15380 | 46.8 | 0.512 |

### Per scenario: standard sAP with forecaster (masked), mean ± 95 % CI

| policy | mission | mission_mirror | random | static_good |
|---|---|---|---|---|
| A_eco41 | 0.0473 ± 0.0056 | 0.0613 ± 0.0027 | 0.0432 ± 0.0088 | 0.0788 ± 0.0115 |
| A_eco42 | 0.0429 ± 0.0021 | 0.0608 ± 0.0027 | 0.0423 ± 0.0104 | 0.0773 ± 0.0131 |
| A_eco42d | 0.0473 ± 0.0058 | 0.0517 ± 0.0188 | 0.0415 ± 0.0089 | 0.0764 ± 0.0150 |
| A_eco_tight | 0.0472 ± 0.0035 | 0.0600 ± 0.0033 | 0.0467 ± 0.0078 | 0.0688 ± 0.0152 |
| A_stream_fc2 | 0.0403 ± 0.0072 | 0.0507 ± 0.0105 | 0.0330 ± 0.0114 | 0.0653 ± 0.0114 |
| fixed_laptop_m640q90 | 0.0223 ± 0.0013 | 0.0529 ± 0.0015 | 0.0347 ± 0.0063 | 0.0779 ± 0.0178 |

### mission: standard sAP with forecaster per phase

| policy | good | ground_congested | ground_blackout | both_degraded | total_blackout | recovered_low_battery |
|---|---|---|---|---|---|---|
| A_eco41 | 0.0960 | 0.0877 | 0.0418 | 0.0054 | 0.0204 | 0.0324 |
| A_eco42 | 0.0986 | 0.0812 | 0.0203 | 0.0069 | 0.0215 | 0.0473 |
| A_eco42d | 0.0968 | 0.0885 | 0.0429 | 0.0083 | 0.0204 | 0.0262 |
| A_eco_tight | 0.0936 | 0.0879 | 0.0444 | 0.0097 | 0.0205 | 0.0271 |
| A_stream_fc2 | 0.0915 | 0.0790 | 0.0309 | 0.0044 | 0.0171 | 0.0196 |
| fixed_laptop_m640q90 | 0.1003 | 0.0474 | 0.0002 | 0.0074 | 0.0003 | 0.0460 |

### mission_mirror: standard sAP with forecaster per phase

| policy | good | edge_congested | edge_blackout | both_degraded | total_blackout | recovered_low_battery |
|---|---|---|---|---|---|---|
| A_eco41 | 0.0977 | 0.1166 | 0.0679 | 0.0055 | 0.0205 | 0.0378 |
| A_eco42 | 0.0978 | 0.1164 | 0.0688 | 0.0101 | 0.0210 | 0.0305 |
| A_eco42d | 0.0847 | 0.1000 | 0.0559 | 0.0078 | 0.0206 | 0.0284 |
| A_eco_tight | 0.0977 | 0.1171 | 0.0642 | 0.0105 | 0.0213 | 0.0269 |
| A_stream_fc2 | 0.0805 | 0.1039 | 0.0561 | 0.0046 | 0.0170 | 0.0189 |
| fixed_laptop_m640q90 | 0.1024 | 0.1166 | 0.0671 | 0.0089 | 0.0001 | 0.0389 |

### Paired: A_eco_tight minus policy (all scenarios x repetitions)

| policy | metric | pairs | mean diff ± 95 % CI | wins | p (exact perm.) | p (Holm) |
|---|---|---|---|---|---|---|
| fixed_laptop_m640q90 | sAP_fc | 20 | +0.0087 ± 0.0061 | 15/20 | 0.0089 | 0.0355 |
| A_stream_fc2 | sAP_fc | 20 | +0.0083 ± 0.0042 | 19/20 | 0.0007 | 0.0033 |
| A_eco42d | sAP_fc | 20 | +0.0015 ± 0.0054 | 14/20 | 0.5510 | 1.0000 |
| A_eco42 | sAP_fc | 20 | -0.0001 ± 0.0042 | 10/20 | 0.9884 | 1.0000 |
| A_eco41 | sAP_fc | 20 | -0.0019 ± 0.0040 | 8/20 | 0.4102 | 1.0000 |
| fixed_laptop_m640q90 | sAP_masked_fc | 20 | +0.0087 ± 0.0062 | 15/20 | 0.0093 | 0.0370 |
| A_stream_fc2 | sAP_masked_fc | 20 | +0.0083 ± 0.0042 | 19/20 | 0.0007 | 0.0036 |
| A_eco42d | sAP_masked_fc | 20 | +0.0015 ± 0.0055 | 13/20 | 0.5591 | 1.0000 |
| A_eco42 | sAP_masked_fc | 20 | -0.0001 ± 0.0043 | 11/20 | 0.9742 | 1.0000 |
| A_eco41 | sAP_masked_fc | 20 | -0.0020 ± 0.0041 | 8/20 | 0.4148 | 1.0000 |
| fixed_laptop_m640q90 | sAP | 20 | +0.0042 ± 0.0029 | 14/20 | 0.0073 | 0.0367 |
| A_stream_fc2 | sAP | 20 | +0.0009 ± 0.0024 | 16/20 | 0.4610 | 1.0000 |
| A_eco42d | sAP | 20 | -0.0000 ± 0.0035 | 14/20 | 0.9789 | 1.0000 |
| A_eco42 | sAP | 20 | -0.0004 ± 0.0031 | 12/20 | 0.8871 | 1.0000 |
| A_eco41 | sAP | 20 | -0.0023 ± 0.0028 | 5/20 | 0.0178 | 0.0713 |
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
| v5 | 20 | 0.0519 | **0.0517** | 0.0524 | 0.1250 | 0.0339 | 0.1512 | 0.0219 | 0.0885 | 533 | 1768 | 2.1 | 0.890 |
| v5_exp | 20 | 0.0517 | **0.0517** | 0.0524 | 0.1246 | 0.0338 | 0.1529 | 0.0229 | 0.0884 | 579 | 1817 | 2.3 | 0.874 |
| v5_lin | 20 | 0.0523 | **0.0516** | 0.0523 | 0.1248 | 0.0337 | 0.1524 | 0.0222 | 0.0866 | 609 | 1977 | 2.0 | 0.927 |
| leaf | 20 | 0.0515 | **0.0516** | 0.0522 | 0.1244 | 0.0335 | 0.1530 | 0.0212 | 0.0894 | 405 | 1205 | 2.3 | 0.897 |
| v42 | 20 | 0.0501 | **0.0499** | 0.0506 | 0.1207 | 0.0324 | 0.1497 | 0.0214 | 0.0885 | 550 | 1695 | 2.7 | 0.861 |
| v5_nofc | 20 | 0.0459 | **0.0459** | 0.0465 | 0.1105 | 0.0305 | 0.1385 | 0.0216 | 0.0810 | 2296 | 5317 | 5.0 | 0.833 |
| v5_flat | 20 | 0.0465 | **0.0456** | 0.0462 | 0.1107 | 0.0290 | 0.1323 | 0.0186 | 0.1008 | 978 | 1977 | 20.2 | 0.636 |
| fixed_laptop_m640q90 | 20 | 0.0443 | **0.0453** | 0.0460 | 0.1050 | 0.0273 | 0.1385 | 0.0195 | 0.1185 | 11743 | 15417 | 45.6 | 0.512 |
| aoi_thr | 20 | 0.0407 | **0.0407** | 0.0412 | 0.1080 | 0.0276 | 0.1250 | 0.0150 | 0.0859 | 605 | 1755 | 14.7 | 0.710 |
| jsq | 20 | 0.0373 | **0.0350** | 0.0354 | 0.0896 | 0.0228 | 0.1173 | 0.0178 | 0.0638 | 212 | 357 | 0.1 | 0.999 |
| conf_trigger | 20 | 0.0305 | **0.0296** | 0.0301 | 0.0781 | 0.0183 | 0.1040 | 0.0149 | 0.0554 | 217 | 1475 | 0.9 | 0.992 |
| reward_offload | 20 | 0.0241 | **0.0253** | 0.0256 | 0.0647 | 0.0149 | 0.0957 | 0.0110 | 0.0542 | 222 | 1503 | 0.9 | 0.992 |

### Per scenario: standard sAP with forecaster (masked), mean ± 95 % CI

| policy | mission | mission_mirror | random | static_good |
|---|---|---|---|---|
| aoi_thr | 0.0374 ± 0.0060 | 0.0389 ± 0.0019 | 0.0356 ± 0.0098 | 0.0528 ± 0.0025 |
| conf_trigger | 0.0270 ± 0.0034 | 0.0315 ± 0.0026 | 0.0220 ± 0.0053 | 0.0397 ± 0.0057 |
| fixed_laptop_m640q90 | 0.0232 ± 0.0015 | 0.0498 ± 0.0040 | 0.0342 ± 0.0055 | 0.0768 ± 0.0139 |
| jsq | 0.0310 ± 0.0074 | 0.0389 ± 0.0026 | 0.0232 ± 0.0076 | 0.0484 ± 0.0132 |
| leaf | 0.0444 ± 0.0034 | 0.0563 ± 0.0031 | 0.0423 ± 0.0111 | 0.0659 ± 0.0112 |
| reward_offload | 0.0237 ± 0.0021 | 0.0270 ± 0.0037 | 0.0190 ± 0.0020 | 0.0329 ± 0.0061 |
| v42 | 0.0437 ± 0.0024 | 0.0556 ± 0.0036 | 0.0373 ± 0.0151 | 0.0658 ± 0.0196 |
| v5 | 0.0425 ± 0.0027 | 0.0565 ± 0.0018 | 0.0413 ± 0.0100 | 0.0694 ± 0.0085 |
| v5_exp | 0.0401 ± 0.0092 | 0.0573 ± 0.0033 | 0.0414 ± 0.0083 | 0.0708 ± 0.0186 |
| v5_flat | 0.0323 ± 0.0114 | 0.0446 ± 0.0027 | 0.0409 ± 0.0106 | 0.0670 ± 0.0164 |
| v5_lin | 0.0419 ± 0.0064 | 0.0573 ± 0.0016 | 0.0426 ± 0.0066 | 0.0675 ± 0.0080 |
| v5_nofc | 0.0281 ± 0.0035 | 0.0519 ± 0.0040 | 0.0384 ± 0.0086 | 0.0675 ± 0.0152 |

### mission: standard sAP with forecaster per phase

| policy | good | ground_congested | ground_blackout | both_degraded | total_blackout | recovered_low_battery |
|---|---|---|---|---|---|---|
| aoi_thr | 0.0699 | 0.0717 | 0.0355 | 0.0089 | 0.0159 | 0.0256 |
| conf_trigger | 0.0708 | 0.0454 | 0.0196 | 0.0051 | 0.0187 | 0.0219 |
| fixed_laptop_m640q90 | 0.0997 | 0.0481 | 0.0002 | 0.0070 | 0.0001 | 0.0488 |
| jsq | 0.0704 | 0.0573 | 0.0230 | 0.0050 | 0.0186 | 0.0230 |
| leaf | 0.0882 | 0.0837 | 0.0392 | 0.0112 | 0.0213 | 0.0249 |
| reward_offload | 0.0558 | 0.0427 | 0.0150 | 0.0051 | 0.0189 | 0.0233 |
| v42 | 0.0920 | 0.0784 | 0.0323 | 0.0066 | 0.0216 | 0.0452 |
| v5 | 0.0896 | 0.0820 | 0.0276 | 0.0067 | 0.0212 | 0.0399 |
| v5_exp | 0.0859 | 0.0730 | 0.0239 | 0.0065 | 0.0218 | 0.0434 |
| v5_flat | 0.0766 | 0.0723 | 0.0325 | 0.0074 | 0.0029 | 0.0438 |
| v5_lin | 0.0868 | 0.0780 | 0.0288 | 0.0064 | 0.0216 | 0.0438 |
| v5_nofc | 0.0879 | 0.0730 | 0.0029 | 0.0020 | 0.0133 | 0.0237 |

### mission_mirror: standard sAP with forecaster per phase

| policy | good | edge_congested | edge_blackout | both_degraded | total_blackout | recovered_low_battery |
|---|---|---|---|---|---|---|
| aoi_thr | 0.0702 | 0.0760 | 0.0403 | 0.0087 | 0.0159 | 0.0259 |
| conf_trigger | 0.0740 | 0.0510 | 0.0347 | 0.0048 | 0.0176 | 0.0210 |
| fixed_laptop_m640q90 | 0.0970 | 0.1109 | 0.0639 | 0.0090 | 0.0001 | 0.0370 |
| jsq | 0.0746 | 0.0828 | 0.0317 | 0.0050 | 0.0181 | 0.0220 |
| leaf | 0.0907 | 0.1089 | 0.0623 | 0.0105 | 0.0209 | 0.0340 |
| reward_offload | 0.0567 | 0.0508 | 0.0216 | 0.0051 | 0.0181 | 0.0227 |
| v42 | 0.0883 | 0.1091 | 0.0618 | 0.0088 | 0.0219 | 0.0277 |
| v5 | 0.0895 | 0.1117 | 0.0633 | 0.0080 | 0.0217 | 0.0277 |
| v5_exp | 0.0910 | 0.1100 | 0.0647 | 0.0100 | 0.0218 | 0.0328 |
| v5_flat | 0.0864 | 0.1060 | 0.0641 | 0.0073 | 0.0028 | 0.0257 |
| v5_lin | 0.0934 | 0.1112 | 0.0620 | 0.0101 | 0.0214 | 0.0299 |
| v5_nofc | 0.0903 | 0.1092 | 0.0617 | 0.0061 | 0.0136 | 0.0253 |

### Paired: v5 minus policy (all scenarios x repetitions)

| policy | metric | pairs | mean diff ± 95 % CI | wins | p (exact perm.) | p (Holm) |
|---|---|---|---|---|---|---|
| reward_offload | sAP_fc | 20 | +0.0265 ± 0.0037 | 20/20 | 0.0000 | 0.0000 |
| conf_trigger | sAP_fc | 20 | +0.0221 ± 0.0028 | 20/20 | 0.0000 | 0.0000 |
| jsq | sAP_fc | 20 | +0.0168 ± 0.0027 | 20/20 | 0.0000 | 0.0000 |
| aoi_thr | sAP_fc | 20 | +0.0110 ± 0.0032 | 20/20 | 0.0000 | 0.0000 |
| fixed_laptop_m640q90 | sAP_fc | 20 | +0.0065 ± 0.0055 | 16/20 | 0.0263 | 0.1313 |
| v5_flat | sAP_fc | 20 | +0.0061 ± 0.0034 | 16/20 | 0.0012 | 0.0083 |
| v5_nofc | sAP_fc | 20 | +0.0058 ± 0.0039 | 14/20 | 0.0041 | 0.0245 |
| v42 | sAP_fc | 20 | +0.0018 ± 0.0026 | 12/20 | 0.1732 | 0.6927 |
| leaf | sAP_fc | 20 | +0.0001 ± 0.0016 | 9/20 | 0.8426 | 1.0000 |
| v5_lin | sAP_fc | 20 | +0.0001 ± 0.0013 | 10/20 | 0.8548 | 1.0000 |
| v5_exp | sAP_fc | 20 | +0.0000 ± 0.0027 | 8/20 | 0.9777 | 1.0000 |
| reward_offload | sAP_masked_fc | 20 | +0.0268 ± 0.0037 | 20/20 | 0.0000 | 0.0000 |
| conf_trigger | sAP_masked_fc | 20 | +0.0224 ± 0.0029 | 20/20 | 0.0000 | 0.0000 |
| jsq | sAP_masked_fc | 20 | +0.0170 ± 0.0028 | 20/20 | 0.0000 | 0.0000 |
| aoi_thr | sAP_masked_fc | 20 | +0.0112 ± 0.0032 | 20/20 | 0.0000 | 0.0000 |
| fixed_laptop_m640q90 | sAP_masked_fc | 20 | +0.0064 ± 0.0056 | 16/20 | 0.0286 | 0.1432 |
| v5_flat | sAP_masked_fc | 20 | +0.0062 ± 0.0034 | 16/20 | 0.0012 | 0.0084 |
| v5_nofc | sAP_masked_fc | 20 | +0.0060 ± 0.0039 | 14/20 | 0.0039 | 0.0237 |
| v42 | sAP_masked_fc | 20 | +0.0018 ± 0.0026 | 12/20 | 0.1793 | 0.7172 |
| leaf | sAP_masked_fc | 20 | +0.0002 ± 0.0016 | 9/20 | 0.7964 | 1.0000 |
| v5_lin | sAP_masked_fc | 20 | +0.0001 ± 0.0013 | 10/20 | 0.8984 | 1.0000 |
| v5_exp | sAP_masked_fc | 20 | -0.0000 ± 0.0027 | 8/20 | 0.9964 | 1.0000 |
| reward_offload | sAP | 20 | +0.0110 ± 0.0020 | 20/20 | 0.0000 | 0.0000 |
| conf_trigger | sAP | 20 | +0.0070 ± 0.0015 | 20/20 | 0.0000 | 0.0000 |
| aoi_thr | sAP | 20 | +0.0069 ± 0.0020 | 20/20 | 0.0000 | 0.0000 |
| jsq | sAP | 20 | +0.0041 ± 0.0014 | 18/20 | 0.0000 | 0.0002 |
| v5_flat | sAP | 20 | +0.0033 ± 0.0022 | 14/20 | 0.0056 | 0.0390 |
| fixed_laptop_m640q90 | sAP | 20 | +0.0024 ± 0.0032 | 15/20 | 0.1293 | 0.7761 |
| leaf | sAP | 20 | +0.0007 ± 0.0010 | 12/20 | 0.1625 | 0.8124 |
| v42 | sAP | 20 | +0.0005 ± 0.0011 | 13/20 | 0.3511 | 1.0000 |
| v5_nofc | sAP | 20 | +0.0003 ± 0.0023 | 10/20 | 0.7910 | 1.0000 |
| v5_lin | sAP | 20 | -0.0003 ± 0.0010 | 8/20 | 0.5661 | 1.0000 |
| v5_exp | sAP | 20 | -0.0010 ± 0.0016 | 5/20 | 0.2438 | 0.9753 |
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
| v41 | 20 | 0.0596 | **0.0600** | 0.0608 | 0.1396 | 0.0407 | 0.1714 | 0.0313 | 0.0896 | 222 | 670 | 0.6 | 0.988 |
| v51 | 20 | 0.0590 | **0.0596** | 0.0605 | 0.1393 | 0.0408 | 0.1716 | 0.0314 | 0.0881 | 230 | 550 | 0.3 | 0.989 |
| v5 | 20 | 0.0593 | **0.0592** | 0.0601 | 0.1383 | 0.0400 | 0.1712 | 0.0300 | 0.0936 | 373 | 1167 | 2.6 | 0.885 |
| onboard_n320 | 20 | 0.0169 | **0.0169** | 0.0171 | 0.0472 | 0.0079 | 0.0743 | 0.0065 | 0.0283 | 230 | 1490 | 0.9 | 0.992 |

### Per scenario: standard sAP with forecaster (masked), mean ± 95 % CI

| policy | mission | mission_mirror | random | static_good |
|---|---|---|---|---|
| onboard_n320 | 0.0172 ± 0.0007 | 0.0167 ± 0.0003 | 0.0171 ± 0.0008 | 0.0175 ± 0.0007 |
| v41 | 0.0482 ± 0.0019 | 0.0628 ± 0.0017 | 0.0441 ± 0.0097 | 0.0883 ± 0.0016 |
| v5 | 0.0449 ± 0.0046 | 0.0631 ± 0.0021 | 0.0451 ± 0.0060 | 0.0873 ± 0.0029 |
| v51 | 0.0480 ± 0.0013 | 0.0630 ± 0.0005 | 0.0434 ± 0.0087 | 0.0875 ± 0.0015 |

### mission: standard sAP with forecaster per phase

| policy | good | ground_congested | ground_blackout | both_degraded | total_blackout | recovered_low_battery |
|---|---|---|---|---|---|---|
| onboard_n320 | 0.0311 | 0.0297 | 0.0076 | 0.0052 | 0.0178 | 0.0234 |
| v41 | 0.1021 | 0.0877 | 0.0466 | 0.0058 | 0.0203 | 0.0242 |
| v5 | 0.1014 | 0.0849 | 0.0349 | 0.0066 | 0.0205 | 0.0297 |
| v51 | 0.0998 | 0.0934 | 0.0340 | 0.0037 | 0.0203 | 0.0373 |

### mission_mirror: standard sAP with forecaster per phase

| policy | good | edge_congested | edge_blackout | both_degraded | total_blackout | recovered_low_battery |
|---|---|---|---|---|---|---|
| onboard_n320 | 0.0305 | 0.0290 | 0.0074 | 0.0049 | 0.0172 | 0.0225 |
| v41 | 0.1011 | 0.1208 | 0.0696 | 0.0055 | 0.0203 | 0.0371 |
| v5 | 0.1024 | 0.1210 | 0.0705 | 0.0102 | 0.0205 | 0.0330 |
| v51 | 0.1025 | 0.1200 | 0.0700 | 0.0060 | 0.0204 | 0.0325 |

### Paired: v41 minus policy (all scenarios x repetitions)

| policy | metric | pairs | mean diff ± 95 % CI | wins | p (exact perm.) | p (Holm) |
|---|---|---|---|---|---|---|
| onboard_n320 | sAP_fc | 20 | +0.0431 ± 0.0083 | 20/20 | 0.0000 | 0.0000 |
| v5 | sAP_fc | 20 | +0.0008 ± 0.0017 | 9/20 | 0.3450 | 1.0000 |
| v51 | sAP_fc | 20 | +0.0004 ± 0.0010 | 8/20 | 0.5081 | 1.0000 |
| onboard_n320 | sAP_masked_fc | 20 | +0.0437 ± 0.0085 | 20/20 | 0.0000 | 0.0000 |
| v5 | sAP_masked_fc | 20 | +0.0007 ± 0.0017 | 9/20 | 0.3916 | 1.0000 |
| v51 | sAP_masked_fc | 20 | +0.0004 ± 0.0010 | 9/20 | 0.5454 | 1.0000 |
| onboard_n320 | sAP | 20 | +0.0248 ± 0.0053 | 20/20 | 0.0000 | 0.0000 |
| v5 | sAP | 20 | +0.0013 ± 0.0011 | 12/20 | 0.0298 | 0.0596 |
| v51 | sAP | 20 | -0.0001 ± 0.0005 | 7/20 | 0.5804 | 0.5804 |
| onboard_n320 | sAP_quality_fc | 20 | +0.0428 ± 0.0085 | 20/20 | 0.0000 | 0.0000 |
| v51 | sAP_quality_fc | 20 | +0.0006 ± 0.0012 | 10/20 | 0.3317 | 0.9952 |
| v5 | sAP_quality_fc | 20 | +0.0003 ± 0.0018 | 10/20 | 0.7160 | 1.0000 |

### Paired: v5 minus policy (all scenarios x repetitions)

| policy | metric | pairs | mean diff ± 95 % CI | wins | p (exact perm.) | p (Holm) |
|---|---|---|---|---|---|---|
| onboard_n320 | sAP_fc | 20 | +0.0423 ± 0.0083 | 20/20 | 0.0000 | 0.0000 |
| v51 | sAP_fc | 20 | -0.0004 ± 0.0016 | 13/20 | 0.5908 | 1.0000 |
| v41 | sAP_fc | 20 | -0.0008 ± 0.0017 | 11/20 | 0.3450 | 1.0000 |
| onboard_n320 | sAP_masked_fc | 20 | +0.0430 ± 0.0084 | 20/20 | 0.0000 | 0.0000 |
| v51 | sAP_masked_fc | 20 | -0.0004 ± 0.0016 | 13/20 | 0.6307 | 1.0000 |
| v41 | sAP_masked_fc | 20 | -0.0007 ± 0.0017 | 11/20 | 0.3916 | 1.0000 |
| onboard_n320 | sAP | 20 | +0.0235 ± 0.0057 | 20/20 | 0.0000 | 0.0000 |
| v41 | sAP | 20 | -0.0013 ± 0.0011 | 8/20 | 0.0298 | 0.0596 |
| v51 | sAP | 20 | -0.0014 ± 0.0012 | 8/20 | 0.0196 | 0.0589 |
| onboard_n320 | sAP_quality_fc | 20 | +0.0424 ± 0.0084 | 20/20 | 0.0000 | 0.0000 |
| v51 | sAP_quality_fc | 20 | +0.0003 ± 0.0017 | 12/20 | 0.6970 | 1.0000 |
| v41 | sAP_quality_fc | 20 | -0.0003 ± 0.0018 | 10/20 | 0.7160 | 1.0000 |

## vid_campaign_long - G13 (24-minute missions)
forecaster: v2live; reference(s): v41, v5; 12 runs

### All scenarios pooled (mean over runs)

| policy | n | sAP quality+fc (reported) | **sAP standard+fc** | sAP std+fc, masked | sAP50 masked+fc | small | medium | sAP std (no fc) | fresh AP masked | age p95 (ms) | age max (ms) | longest stale (s) | fresh share |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v41 | 2 | 0.0433 | **0.0438** | 0.0443 | 0.1059 | 0.0301 | 0.1391 | 0.0187 | 0.0765 | 283 | 1150 | 1.2 | 0.981 |
| v42 | 2 | 0.0373 | **0.0390** | 0.0394 | 0.0951 | 0.0259 | 0.1303 | 0.0177 | 0.0709 | 367 | 5233 | 5.0 | 0.912 |
| v5 | 2 | 0.0317 | **0.0345** | 0.0349 | 0.0852 | 0.0222 | 0.1188 | 0.0148 | 0.0698 | 600 | 6083 | 5.8 | 0.873 |
| v51 | 2 | 0.0317 | **0.0330** | 0.0334 | 0.0828 | 0.0214 | 0.1111 | 0.0140 | 0.0676 | 317 | 1333 | 1.1 | 0.944 |
| stream_fc2 | 2 | 0.0264 | **0.0280** | 0.0283 | 0.0690 | 0.0175 | 0.0997 | 0.0124 | 0.0638 | 283 | 533 | 0.2 | 0.991 |
| fixed_laptop_m640q90 | 2 | 0.0191 | **0.0191** | 0.0194 | 0.0435 | 0.0105 | 0.0631 | 0.0065 | 0.1059 | 205217 | 241267 | 280.6 | 0.187 |

### Per scenario: standard sAP with forecaster (masked), mean ± 95 % CI

| policy | mission |
|---|---|
| fixed_laptop_m640q90 | 0.0194 ± 0.0079 |
| stream_fc2 | 0.0283 ± 0.1279 |
| v41 | 0.0443 ± 0.0069 |
| v42 | 0.0394 ± 0.0108 |
| v5 | 0.0349 ± 0.0232 |
| v51 | 0.0334 ± 0.0286 |

### mission: standard sAP with forecaster per phase

| policy | good | ground_congested | ground_blackout | both_degraded | total_blackout | recovered_low_battery |
|---|---|---|---|---|---|---|
| fixed_laptop_m640q90 | 0.0868 | 0.0263 | 0.0003 | 0.0166 | 0.0001 | 0.0165 |
| stream_fc2 | 0.0552 | 0.0335 | 0.0364 | 0.0114 | 0.0132 | 0.0112 |
| v41 | 0.0816 | 0.0546 | 0.0602 | 0.0259 | 0.0124 | 0.0243 |
| v42 | 0.0846 | 0.0456 | 0.0442 | 0.0249 | 0.0133 | 0.0252 |
| v5 | 0.0805 | 0.0417 | 0.0319 | 0.0241 | 0.0137 | 0.0169 |
| v51 | 0.0824 | 0.0318 | 0.0281 | 0.0205 | 0.0126 | 0.0232 |

### Paired: v41 minus policy (all scenarios x repetitions)

| policy | metric | pairs | mean diff ± 95 % CI | wins | p (exact perm.) | p (Holm) |
|---|---|---|---|---|---|---|
| fixed_laptop_m640q90 | sAP_fc | 2 | +0.0247 ± 0.0042 | 2/2 | 0.5000 | 1.0000 |
| stream_fc2 | sAP_fc | 2 | +0.0159 ± 0.1337 | 2/2 | 0.5000 | 1.0000 |
| v51 | sAP_fc | 2 | +0.0108 ± 0.0358 | 2/2 | 0.5000 | 1.0000 |
| v5 | sAP_fc | 2 | +0.0093 ± 0.0306 | 2/2 | 0.5000 | 1.0000 |
| v42 | sAP_fc | 2 | +0.0049 ± 0.0028 | 2/2 | 0.5000 | 1.0000 |
| fixed_laptop_m640q90 | sAP_masked_fc | 2 | +0.0249 ± 0.0010 | 2/2 | 0.5000 | 1.0000 |
| stream_fc2 | sAP_masked_fc | 2 | +0.0160 ± 0.1348 | 2/2 | 0.5000 | 1.0000 |
| v51 | sAP_masked_fc | 2 | +0.0109 ± 0.0355 | 2/2 | 0.5000 | 1.0000 |
| v5 | sAP_masked_fc | 2 | +0.0094 ± 0.0300 | 2/2 | 0.5000 | 1.0000 |
| v42 | sAP_masked_fc | 2 | +0.0049 ± 0.0040 | 2/2 | 0.5000 | 1.0000 |
| fixed_laptop_m640q90 | sAP | 2 | +0.0122 ± 0.0046 | 2/2 | 0.5000 | 1.0000 |
| stream_fc2 | sAP | 2 | +0.0063 ± 0.0777 | 2/2 | 0.5000 | 1.0000 |
| v51 | sAP | 2 | +0.0047 ± 0.0274 | 2/2 | 0.5000 | 1.0000 |
| v5 | sAP | 2 | +0.0039 ± 0.0293 | 2/2 | 0.5000 | 1.0000 |
| v42 | sAP | 2 | +0.0010 ± 0.0052 | 2/2 | 0.5000 | 1.0000 |
| fixed_laptop_m640q90 | sAP_quality_fc | 2 | +0.0243 ± 0.0047 | 2/2 | 0.5000 | 1.0000 |
| stream_fc2 | sAP_quality_fc | 2 | +0.0169 ± 0.1186 | 2/2 | 0.5000 | 1.0000 |
| v5 | sAP_quality_fc | 2 | +0.0116 ± 0.0220 | 2/2 | 0.5000 | 1.0000 |
| v51 | sAP_quality_fc | 2 | +0.0116 ± 0.0362 | 2/2 | 0.5000 | 1.0000 |
| v42 | sAP_quality_fc | 2 | +0.0060 ± 0.0051 | 2/2 | 0.5000 | 1.0000 |

### Paired: v5 minus policy (all scenarios x repetitions)

| policy | metric | pairs | mean diff ± 95 % CI | wins | p (exact perm.) | p (Holm) |
|---|---|---|---|---|---|---|
| fixed_laptop_m640q90 | sAP_fc | 2 | +0.0154 ± 0.0348 | 2/2 | 0.5000 | 1.0000 |
| stream_fc2 | sAP_fc | 2 | +0.0065 ± 0.1031 | 1/2 | 1.0000 | 1.0000 |
| v51 | sAP_fc | 2 | +0.0015 ± 0.0052 | 2/2 | 0.5000 | 1.0000 |
| v42 | sAP_fc | 2 | -0.0045 ± 0.0334 | 0/2 | 0.5000 | 1.0000 |
| v41 | sAP_fc | 2 | -0.0093 ± 0.0306 | 0/2 | 0.5000 | 1.0000 |
| fixed_laptop_m640q90 | sAP_masked_fc | 2 | +0.0155 ± 0.0311 | 2/2 | 0.5000 | 1.0000 |
| stream_fc2 | sAP_masked_fc | 2 | +0.0066 ± 0.1048 | 1/2 | 1.0000 | 1.0000 |
| v51 | sAP_masked_fc | 2 | +0.0015 ± 0.0055 | 2/2 | 0.5000 | 1.0000 |
| v42 | sAP_masked_fc | 2 | -0.0045 ± 0.0340 | 0/2 | 0.5000 | 1.0000 |
| v41 | sAP_masked_fc | 2 | -0.0094 ± 0.0300 | 0/2 | 0.5000 | 1.0000 |
| fixed_laptop_m640q90 | sAP | 2 | +0.0083 ± 0.0247 | 2/2 | 0.5000 | 1.0000 |
| stream_fc2 | sAP | 2 | +0.0024 ± 0.0484 | 1/2 | 1.0000 | 1.0000 |
| v51 | sAP | 2 | +0.0008 ± 0.0019 | 2/2 | 0.5000 | 1.0000 |
| v42 | sAP | 2 | -0.0029 ± 0.0242 | 0/2 | 0.5000 | 1.0000 |
| v41 | sAP | 2 | -0.0039 ± 0.0293 | 0/2 | 0.5000 | 1.0000 |
| fixed_laptop_m640q90 | sAP_quality_fc | 2 | +0.0126 ± 0.0267 | 2/2 | 0.5000 | 1.0000 |
| stream_fc2 | sAP_quality_fc | 2 | +0.0053 ± 0.0967 | 1/2 | 1.0000 | 1.0000 |
| v51 | sAP_quality_fc | 2 | -0.0000 ± 0.0142 | 1/2 | 1.0000 | 1.0000 |
| v42 | sAP_quality_fc | 2 | -0.0056 ± 0.0271 | 0/2 | 0.5000 | 1.0000 |
| v41 | sAP_quality_fc | 2 | -0.0116 ± 0.0220 | 0/2 | 0.5000 | 1.0000 |
