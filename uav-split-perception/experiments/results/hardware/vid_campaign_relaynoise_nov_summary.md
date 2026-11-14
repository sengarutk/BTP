# vid_campaign_relaynoise_nov: strategies on the AegisSwarm mesh, VisDrone weights, standard sAP with live forecaster v2

| scenario | strategy | n | sAP | sAP + fc | mAP | P(AoI ≤ 300 ms) | 95th-pct AoI (ms) | deadline-met /s | median latency (ms) | Pi W | Pi °C | throttled | Jetson W | processed at |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| multihop_loss2 | v41 | 2 | 0.0298 | **0.0996 ± 0.0575** | 0.204 | 0.910 | 350 | 10.4 | 159 | 2.93 | 62.1 | 0.00 | 5.34 | jetson 67 %, laptop 24 %, onboard 9 % |
| multihop_loss2 | fixlap | 2 | 0.0122 | **0.0436 ± 0.0228** | 0.248 | 0.025 | 1000 | 0.4 | 389 | 1.84 | 48.9 | 0.00 |  | laptop 100 % |
| multihop_loss2 | hier | 2 | 0.0358 | **0.1177 ± 0.0076** | 0.224 | 0.947 | 333 | 10.6 | 134 | 2.92 | 59.3 | 0.00 | 5.86 | jetson 90 %, onboard 10 %, laptop 0 % |
| multihop_loss5 | v41 | 2 | 0.0269 | **0.0842 ± 0.0062** | 0.185 | 0.892 | 383 | 10.5 | 144 | 2.91 | 62.5 | 0.00 | 5.34 | jetson 68 %, laptop 23 %, onboard 9 % |
| multihop_loss5 | fixlap | 2 | 0.0085 | **0.0243 ± 0.0364** | 0.248 | 0.003 | 1683 | 0.0 | 550 | 1.83 | 51.1 | 0.00 |  | laptop 100 % |
| multihop_loss5 | hier | 2 | 0.0232 | **0.0814 ± 0.0790** | 0.187 | 0.858 | 433 | 9.0 | 145 | 2.92 | 59.7 | 0.00 | 5.39 | jetson 79 %, onboard 12 %, laptop 10 % |
| ALL | v41 | 4 | 0.0284 | **0.0919 ± 0.0153** | 0.194 | 0.901 | 367 | 10.4 | 151 | 2.92 | 62.3 | 0.00 | 5.34 | jetson 68 %, laptop 23 %, onboard 9 % |
| ALL | fixlap | 4 | 0.0103 | **0.0339 ± 0.0182** | 0.248 | 0.014 | 1342 | 0.2 | 469 | 1.84 | 50.0 | 0.00 |  | laptop 100 % |

## Paired differences (same scenario and repetition)
| comparison | scope | metric | pairs | Δ ± 95 % CI | first ahead | p |
|---|---|---|---|---|---|---|
| fixlap-v41 | multihop_loss2 | sAP_fc | 2 | -0.0560 ± 0.0803 | 0/2 | 0.500 |
| fixlap-v41 | multihop_loss2 | sAP | 2 | -0.0176 ± 0.0108 | 0/2 | 0.500 |
| fixlap-v41 | multihop_loss2 | p_aoi300 | 2 | -0.8844 ± 0.2220 | 0/2 | 0.500 |
| fixlap-v41 | multihop_loss2 | deadline_met_fps | 2 | -10.0062 ± 4.4750 | 0/2 | 0.500 |
| fixlap-v41 | multihop_loss2 | pi_w | 2 | -1.0892 ± 0.0913 | 0/2 | 0.500 |
| fixlap-v41 | multihop_loss2 | pi_temp_c | 2 | -13.2323 ± 16.1128 | 0/2 | 0.500 |
| fixlap-v41 | multihop_loss5 | sAP_fc | 2 | -0.0599 ± 0.0302 | 0/2 | 0.500 |
| fixlap-v41 | multihop_loss5 | sAP | 2 | -0.0184 ± 0.0030 | 0/2 | 0.500 |
| fixlap-v41 | multihop_loss5 | p_aoi300 | 2 | -0.8892 ± 0.2149 | 0/2 | 0.500 |
| fixlap-v41 | multihop_loss5 | deadline_met_fps | 2 | -10.4250 ± 10.8565 | 0/2 | 0.500 |
| fixlap-v41 | multihop_loss5 | pi_w | 2 | -1.0786 ± 0.2183 | 0/2 | 0.500 |
| fixlap-v41 | multihop_loss5 | pi_temp_c | 2 | -11.4594 ± 17.1268 | 0/2 | 0.500 |
| fixlap-v41 | ALL | sAP_fc | 4 | -0.0579 ± 0.0095 | 0/4 | 0.125 |
| fixlap-v41 | ALL | sAP | 4 | -0.0180 ± 0.0013 | 0/4 | 0.125 |
| fixlap-v41 | ALL | p_aoi300 | 4 | -0.8868 ± 0.0319 | 0/4 | 0.125 |
| fixlap-v41 | ALL | deadline_met_fps | 4 | -10.2156 ± 1.2595 | 0/4 | 0.125 |
| fixlap-v41 | ALL | pi_w | 4 | -1.0839 ± 0.0261 | 0/4 | 0.125 |
| fixlap-v41 | ALL | pi_temp_c | 4 | -12.3459 ± 2.9014 | 0/4 | 0.125 |
| hier-v41 | multihop_loss2 | sAP_fc | 2 | +0.0181 ± 0.0651 | 2/2 | 0.500 |
| hier-v41 | multihop_loss2 | sAP | 2 | +0.0060 ± 0.0154 | 2/2 | 0.500 |
| hier-v41 | multihop_loss2 | p_aoi300 | 2 | +0.0373 ± 0.3137 | 2/2 | 0.500 |
| hier-v41 | multihop_loss2 | deadline_met_fps | 2 | +0.1708 ± 5.4547 | 1/2 | 1.000 |
| hier-v41 | multihop_loss2 | pi_w | 2 | -0.0142 ± 0.0513 | 0/2 | 0.500 |
| hier-v41 | multihop_loss2 | pi_temp_c | 2 | -2.8003 ± 2.0257 | 0/2 | 0.500 |
| hier-v41 | multihop_loss2 | jetson_w | 2 | +0.5225 ± 0.8930 | 2/2 | 0.500 |
| hier-v41 | multihop_loss5 | sAP_fc | 2 | -0.0028 ± 0.0729 | 1/2 | 1.000 |
| hier-v41 | multihop_loss5 | sAP | 2 | -0.0037 ± 0.0251 | 0/2 | 0.500 |
| hier-v41 | multihop_loss5 | p_aoi300 | 2 | -0.0340 ± 0.1335 | 0/2 | 0.500 |
| hier-v41 | multihop_loss5 | deadline_met_fps | 2 | -1.4333 ± 11.4390 | 0/2 | 0.500 |
| hier-v41 | multihop_loss5 | pi_w | 2 | +0.0120 ± 0.1590 | 1/2 | 1.000 |
| hier-v41 | multihop_loss5 | pi_temp_c | 2 | -2.8105 ± 17.1422 | 0/2 | 0.500 |
| hier-v41 | multihop_loss5 | jetson_w | 2 | +0.0514 ± 0.5875 | 2/2 | 0.500 |
| hier-v41 | ALL | sAP_fc | 4 | +0.0076 ± 0.0216 | 3/4 | 0.375 |
| hier-v41 | ALL | sAP | 4 | +0.0011 ± 0.0094 | 2/4 | 0.875 |
| hier-v41 | ALL | p_aoi300 | 4 | +0.0017 ± 0.0742 | 2/4 | 1.000 |
| hier-v41 | ALL | deadline_met_fps | 4 | -0.6312 ± 1.9607 | 1/4 | 0.500 |
| hier-v41 | ALL | pi_w | 4 | -0.0011 ± 0.0295 | 1/4 | 0.875 |
| hier-v41 | ALL | pi_temp_c | 4 | -2.8054 ± 1.7632 | 0/4 | 0.125 |
| hier-v41 | ALL | jetson_w | 4 | +0.2870 ± 0.4461 | 4/4 | 0.125 |
