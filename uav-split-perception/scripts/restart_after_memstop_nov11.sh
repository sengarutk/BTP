#!/bin/bash
# Restart after the memory watchdog stopped the jobs (11 Nov 2026, 23:29 IST; Windows free memory < 300 MB).
# One job at a time on each resource: CPU replay (2 shards), then the GPU chain after the learned-codec job.
# Every step is resumable (finished rows are skipped).
set -uo pipefail
cd "$(dirname "$0")/.."
P=/home/sengar/BTP/venv/bin/python
( cd validation/hardware
  OUT=../../experiments/results/hardware/replay/theory_sweep_nov11
  G="th_adapt_amb5_cap50 th_adapt_amb10_cap50 th_hold78_amb15 th_guard_amb0 th_guard_amb5 th_guard_amb10 th_guard_amb15"
  F="th_floor_amb0 th_floor_amb5 th_floor_amb10 th_floor_amb15"
  printf "%s\n" 1 2 3 4 5 | xargs -P 2 -I{} sh -c "$P replay_theory_sweep.py run --scenario mission --phase-s 240 --seeds {}-{} --only $G $F --out $OUT > $OUT/logs/restart_s{}.log 2>&1"
  $P replay_theory_sweep.py analyze $OUT > $OUT/logs/analyze.log 2>&1
  echo "=== $(date -u +%T) REPLAY_RESTART_DONE" ) &
while pgrep -f '[l]earned_image_codecs_nov11.sh' > /dev/null; do sleep 60; done
bash scripts/video_codecs_after2_nov11.sh > experiments/joint_bottleneck_runs/logs/video_after3.log 2>&1 || echo "VIDEO_AFTER FAILED"
bash scripts/second_detector_nov11.sh > experiments/joint_bottleneck_runs/logs/second_det2.log 2>&1 || echo "SECOND_DET FAILED"
wait
echo "=== $(date -u +%T) RESTART_ALL_DONE"
