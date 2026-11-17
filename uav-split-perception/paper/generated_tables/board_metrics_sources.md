# paper 1 board numbers and their sources

| Macro | Value | Source |
| --- | --- | --- |
| `\BpRates` | 0.5, 0.75, 1, 2, 4, 8 | experiments/results/hardware/t10 (scripts/report_mesh_nov16.py): goodputs swept (Mbit/s) |
| `\BpBestAllJpeg` | yes | experiments/results/hardware/t10 (scripts/report_mesh_nov16.py): a JPEG option is best at every goodput |
| `\BpCodeFpsMax` | 5.0 | experiments/results/hardware/t10 (scripts/report_mesh_nov16.py): largest on-time rate of any code (results/s) |
| `\BpJpegFpsFour` | 15.8 | experiments/results/hardware/t10 (scripts/report_mesh_nov16.py): jpeg_q20 on-time results/s at 4 Mbit/s |
| `\BpJpegFpsEight` | 24.1 | experiments/results/hardware/t10 (scripts/report_mesh_nov16.py): jpeg_q20 on-time results/s at 8 Mbit/s |
| `\BpOnbKfourCfour` | 227 | experiments/results/hardware/t10 (scripts/report_mesh_nov16.py): t10_prediction.json options.k4_c4_w128_d2.onboard_ms (cold bench) |
| `\BpOnbKtwoCeight` | 174 | experiments/results/hardware/t10 (scripts/report_mesh_nov16.py): t10_prediction.json options.k2_c8_w128_d2.onboard_ms (cold bench) |
| `\BpJpegOnb` | 2.3 | experiments/results/hardware/t10 (scripts/report_mesh_nov16.py): jpeg_q20 onboard ms |
| `\BpHtbCode` | 4.2 | experiments/results/hardware/t10 (scripts/report_mesh_nov16.py): token bucket, 0.5 Mbit/s, k4_c4 on-time/s |
| `\BpHtbJpeg` | 0.8 | experiments/results/hardware/t10 (scripts/report_mesh_nov16.py): token bucket, 0.5 Mbit/s, jpeg_q20 on-time/s |
| `\BpXuf` | 3.0 | t11: x264 ultrafast CRF 23 ms/frame on the Pi |
| `\BpXmed` | 67 | t11: x265 medium CRF 23 ms/frame on the Pi |
| `\BpRatioMin` | 1.55 | t11: Pi/laptop encode time, min over settings |
| `\BpRatioMax` | 3.08 | t11: ... max |
| `\BpScale` | 63.5 | analysis_pi_measured.json: the rule's host-time scale on the Pi |
| `\BpJpegRatio` | 4.5 | analysis_pi_measured.json: JPEG encode, Pi/laptop, median of the measured qualities |
| `\BpHeadJpegRule` | 1.88 | analysis_pi_measured.json: joint_k4_c4, jpeg, rule |
| `\BpHeadJpegMeas` | 1.72 | ... measured Pi times |
| `\BpHeadVideoRule` | 1.06 | analysis_pi_measured.json: joint_k4_c4, both, rule |
| `\BpHeadVideoMeas` | 0.27 | ... measured Pi times |
| `\BpWinsVideoMeas` | 0 | analysis_pi_measured.json: winning cells, measured, JPEG + video |
| `\BpWinsJpegMeas` | 11 | ... JPEG only |
| `\BpExc` | 0 | ... exceptions, all families |
| `\BpCodeMsMin` | 174 | t10_bench_camera2.json: measured Pi onboard ms of the codes, min |
| `\BpCodeMsMax` | 228 | ... max |
| `\BpYelevenDev` | 1 | break_even_pi_measured.json: YOLO11s codes, |measured/rule - 1| max (%) |
| `\BpYelevenBeMin` | 0.68 | break_even_pi_measured.json: YOLO11s B_be measured, min |
| `\BpYelevenBeMax` | 1.53 | ... max |
| `\BpYelevenWins` | 0 | ... winning cells |
| `\BpModelErrPct` | 8 | t10_model_check.json: median |pred - meas| / meas, cells >= 1/s (%) |
| `\BpModelCells` | 30 | t10_model_check.json: measured cells |
| `\BpModelCellsBig` | 18 | ... cells with >= 1 on-time result/s |
| `\BpModelR` | 0.98 | t10_model_check.json: Pearson r predicted vs measured on-time rate |
| `\BpModelBestMatch` | 5 | t10_model_check.json: goodputs where the predicted best option was the measured best |
| `\BpModelRates` | 6 | ... goodputs |
| `\BpJetCodeMsMin` | 6.6 | t10_bench_jetson2.json: codes' onboard ms on the Jetson, min |
| `\BpJetCodeMsMax` | 9.5 | ... max |
| `\BpJetJpegRatio` | 7.5 | analysis_jetson_measured.json: JPEG encode Jetson/laptop |
| `\BpJetHeadJpeg` | 9.84 | analysis_jetson_measured.json: joint_k4_c4 B_be, JPEG, measured Jetson times |
| `\BpJetHeadJpegRule` | 9.84 | ... the rule's scaled Jetson times |
| `\BpJetHeadVideoHi` | 4.40 | ... JPEG + video, video at the JPEG ratio (upper end) |
| `\BpJetHeadVideoLo` | 1.51 | ... JPEG + video, video at the Pi's lowest video/JPEG ratio |
| `\BpJetHeadVideoRule` | 1.51 | ... JPEG + video, the rule's scaled times |
| `\BpJetWinsJpeg` | 218 | analysis_jetson_measured.json: winning cells, JPEG |
| `\BpJetWinsVideoMin` | 39 | ... winning cells with video, min over the video-cost versions |
| `\BpJetWinsVideoMax` | 75 | ... max |
| `\BpJetExc` | 0 | ... exceptions, every family and version |
| `\BpLitPapers` | 5 | literature/published_splits.json: papers re-read |
| `\BpLitNotMatched` | 5 | ... papers without an accuracy-matched image baseline |
| `\BpLitAutoRaw` | 12.5 | published_splits.json autosplit: latency advantage vs raw image (Table 8 / 7) |
| `\BpLitAutoMatched` | 1.9 | ... vs accuracy-matched JPEG q60 (Table 7) |
