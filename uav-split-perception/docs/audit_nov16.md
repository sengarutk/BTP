# Independent audit of the board numbers, 16 Nov 2026

`scripts/audit_nov16.py`: own code, raw result files only (not `scripts/report_mesh_nov16.py`).

## A. Runs re-scored from their frame logs (no cache) against the cached scores

| run | metric | re-scored | cached | |
| --- | --- | --- | --- | --- |
| vid_campaign_final_nov/multihop__accumo__r4 | sAP | 0.055748 | 0.055748 | ok |
| vid_campaign_final_nov/multihop__accumo__r4 | sAP_fc | 0.150432 | 0.150432 | ok |
| vid_campaign_final_nov/multihop__accumo__r4 | pi_w | 2.284369 | 2.284369 | ok |
| vid_campaign_final_nov/multihop__accumo__r4 | deadline_met_fps | 10.762500 | 10.762500 | ok |
| vid_campaign_fix_nov/multihop__v41fix24__r1 | sAP | 0.054960 | 0.054960 | ok |
| vid_campaign_fix_nov/multihop__v41fix24__r1 | sAP_fc | 0.149155 | 0.149155 | ok |
| vid_campaign_fix_nov/multihop__v41fix24__r1 | pi_w | 2.407938 | 2.407938 | ok |
| vid_campaign_fix_nov/multihop__v41fix24__r1 | deadline_met_fps | 12.283333 | 12.283333 | ok |
| vid_campaign_heat_nov/mission__v41cap__r3 | sAP | 0.056504 | 0.056504 | ok |
| vid_campaign_heat_nov/mission__v41cap__r3 | sAP_fc | 0.128487 | 0.128487 | ok |
| vid_campaign_heat_nov/mission__v41cap__r3 | pi_w | 3.069888 | 3.069888 | ok |
| vid_campaign_heat_nov/mission__v41cap__r3 | deadline_met_fps | 15.634028 | 15.634028 | ok |
| vid_campaign_two_cap/static_good__v41j2__r1_c2 | sAP | 0.059084 | 0.059084 | ok |
| vid_campaign_two_cap/static_good__v41j2__r1_c2 | sAP_fc | 0.144100 | 0.144100 | ok |
| vid_campaign_two_cap/static_good__v41j2__r1_c2 | pi_w | 2.869477 | 2.869477 | ok |
| vid_campaign_two_cap/static_good__v41j2__r1_c2 | deadline_met_fps | 18.212500 | 18.212500 | ok |
| vid_campaign_topology_nov/static_good__hier__r4 | sAP | 0.052723 | 0.052723 | ok |
| vid_campaign_topology_nov/static_good__hier__r4 | sAP_fc | 0.149748 | 0.149748 | ok |
| vid_campaign_topology_nov/static_good__hier__r4 | pi_w | 2.820424 | 2.820424 | ok |
| vid_campaign_topology_nov/static_good__hier__r4 | deadline_met_fps | 13.716667 | 13.716667 | ok |
| vid_campaign_budget_nov/mesh_mission__v41final__r2 | sAP | 0.088767 | 0.088767 | ok |
| vid_campaign_budget_nov/mesh_mission__v41final__r2 | sAP_fc | 0.181212 | 0.181212 | ok |
| vid_campaign_budget_nov/mesh_mission__v41final__r2 | pi_w | 2.814981 | 2.814981 | ok |
| vid_campaign_budget_nov/mesh_mission__v41final__r2 | deadline_met_fps | 20.433333 | 20.433333 | ok |

## B. Macros recomputed

| quantity | recomputed | macro | |
| --- | --- | --- | --- |
| v4.1 hot time min % | 16.0215 | 16 | ok |
| v4.1 hot time max % | 25.5533 | 26 | ok |
| v4.1 throttled samples min | 42 | 42 | ok |
| capped hold hot max % | 0.749144 | 0.7 | ok |
| capped hold peak max | 81.5 | 81.5 | ok |
| guard 76.5 peak min | 79.3 | 79.3 | ok |
| guard 76.5 peak max | 80.4 | 80.4 | ok |
| guard 76.5 hot max % | 0.0151907 | 0.02 | ok |
| final peak | 79.3 | 79.3 | ok |
| overshoot min | 2.4 | 2.4 | ok |
| overshoot max (delta_fast) | 3.9 | 3.9 | ok |
| guarded runs | 8 | 8 | ok |
| 24-min sAP v41 | 0.128084 | 0.1281 | ok |
| 24-min sAP v41cap | 0.126665 | 0.1267 | ok |
| 24-min sAP v41guard765 | 0.122776 | 0.1228 | ok |
| 24-min sAP v41final | 0.12469 | 0.1247 | ok |
| final - v41, mesh_mission | 0.000575707 | +0.0006 | ok |
|   CI | 0.00320902 | 0.0032 | ok |
|   ahead of 5 | 3 | 3 | ok |
| final - accumo, mesh_mission | 0.00668557 | +0.0067 | ok |
|   CI | 0.00190789 | 0.0019 | ok |
|   ahead of 5 | 5 | 5 | ok |
| final - leaf, mesh_mission | 0.00121554 | +0.0012 | ok |
|   CI | 0.00437756 | 0.0044 | ok |
|   ahead of 5 | 3 | 3 | ok |
| final sAP mesh_mission | 0.185672 | 0.1857 | ok |
| final W mesh_mission | 2.80712 | 2.81 | ok |
| accumo sAP mesh_mission | 0.178986 | 0.1790 | ok |
| accumo W mesh_mission | 2.45408 | 2.45 | ok |
| leaf sAP mesh_mission | 0.184456 | 0.1845 | ok |
| leaf W mesh_mission | 2.40834 | 2.41 | ok |
| budget 2.4-2.8 W, mesh_mission | -0.314725 | -0.31 | ok |
| budget 2.4-2.8 sAP, mesh_mission | -0.000427036 | -0.0004 | ok |
| late-path skip, mesh_mission | -0.00312459 | -0.0031 | ok |
|   CI | 0.0158821 | 0.0159 | ok |
|   ahead of 5 | 3 | 3 | ok |
|   p (own t) | 0.6140025485442248 | — | no macro |
| final - v41, multihop | -0.00322904 | -0.0032 | ok |
|   CI | 0.00321317 | 0.0032 | ok |
|   ahead of 5 | 0 | 0 | ok |
| final - accumo, multihop | -0.0161823 | -0.0162 | ok |
|   CI | 0.00338812 | 0.0034 | ok |
|   ahead of 5 | 0 | 0 | ok |
| final - leaf, multihop | -0.00423893 | -0.0042 | ok |
|   CI | 0.00284805 | 0.0028 | ok |
|   ahead of 5 | 0 | 0 | ok |
| final sAP multihop | 0.133904 | 0.1339 | ok |
| final W multihop | 2.82747 | 2.83 | ok |
| accumo sAP multihop | 0.150086 | 0.1501 | ok |
| accumo W multihop | 2.24686 | 2.25 | ok |
| leaf sAP multihop | 0.138143 | 0.1381 | ok |
| leaf W multihop | 2.20477 | 2.20 | ok |
| budget 2.4-2.8 W, multihop | -0.376495 | -0.38 | ok |
| budget 2.4-2.8 sAP, multihop | -0.00146535 | -0.0015 | ok |
| late-path skip, multihop | 0.0150843 | +0.0151 | ok |
|   CI | 0.0134478 | 0.0134 | ok |
|   ahead of 5 | 5 | 5 | ok |
|   p (own t) | 0.0357393820728871 | — | no macro |
| laptop share, final multihop % | 21.1902 | 21 | ok |
| laptop median ms, final multihop | 337.105 | 337 | ok |
| laptop share before skip % | 24.0386 | 24.0 | ok |
| laptop share after skip % | 5.35648 | 5.4 | ok |
| laptop ms after skip | 109.498 | 109 | ok |
| jetson ms before skip | 108.031 | 108 | ok |
| jetson ms after skip | 90.4652 | 90 | ok |
| two cameras v41j1 static_good | 0.181311 | 0.1813 | ok |
| two cameras v41j2 static_good | 0.143646 | 0.1436 | ok |
| per-camera cap static_good | 0.00614531 | +0.0061 | ok |
| two cameras v41j1 mesh_mission | 0.166684 | 0.1667 | ok |
| two cameras v41j2 mesh_mission | 0.129416 | 0.1294 | ok |
| per-camera cap mesh_mission | -0.00181414 | -0.0018 | ok |
| v4.1 rule, 8 streams, min /s | 2.88333 | 2.9 | ok |
| v4.1 rule, 8 streams, max /s | 3.7 | 3.7 | ok |
| pull, 8 streams, min /s | 19.9167 | 19.9 | ok |
| pull, 8 streams, max /s | 21.6 | 21.6 | ok |
| calibration ECE | 0.0549773 | 0.055 | ok |
| calibration frames | 1.48249e+06 | 1,482,492 | ok |
| calibration low bin observed % | 64.105 | 64 | ok |
| T10: best option at every goodput is a JPEG | True | yes | ok |
| T10 largest code on-time /s | 5 | 5.0 | ok |
| headline code B_be, JPEG, measured | 1.72498 | 1.72 | ok |
| headline code B_be, JPEG+video, measured | 0.265975 | 0.27 | ok |
| winning cells with video, measured | 0 | 0 | ok |
| exceptions, all families | 0 | 0 | ok |
| rule's Pi host scale | 63.4906 | 63.5 | ok |
| x264 ultrafast CRF 23 ms | 2.993 | 3.0 | ok |
| x265 medium CRF 23 ms | 66.887 | 67 | ok |

**0 mismatches.**
