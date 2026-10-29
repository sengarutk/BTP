# Task C: standard-metric rescoring of every VisDrone-VID campaign

sAP = streaming AP, standard 'newest' holding rule unless marked 'quality'. 'masked' = VisDrone ignored regions masked (official protocol). +fc = with the campaign's forecaster (v2 offline for the Part 12/14 campaigns, v2 computed live on the Pi from the 80-run campaign on). Sizes: COCO area ranges in the 640-px frame (91 % of the objects are small, 9 % medium, 7 objects large -> not reported). Freshness: age of the held result at each camera frame (30 fps); stale = older than 300 ms. Compare numbers within one campaign only.

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
