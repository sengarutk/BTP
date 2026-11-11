#!/bin/bash
# Paper 1, P1-4: the second detector (YOLO11s). After the video-codec follow-up (GPU, memory); one GPU job at a time.
# Resumable: finished rows are skipped.
set -uo pipefail
cd "$(dirname "$0")/.."
P=/home/sengar/BTP/venv/bin/python
L="$P -m evaluation.learned_bottleneck --detector yolo11s"
D=experiments/results/second_detector/yolo11s/learned_bottleneck
mkdir -p $D/logs
while pgrep -f '[v]ideo_codecs_after_nov11.sh' > /dev/null; do sleep 60; done
# host timings first, on an idle GPU (the replay shards use the CPU only)
[ -f experiments/results/second_detector/yolo11s/profile.json ] || $P -m evaluation.second_detector profile \
  > $D/logs/profile.log 2>&1 || echo "PROFILE FAILED"
for q in 10 15 20 25 30 35 40 45 50 55 60 65 70 75 80 85 90 95; do
  [ -f $D/jpeg_q$q.json ] || $L jpeg --q $q > $D/logs/jpeg_q$q.log 2>&1 || echo "JPEG FAILED $q"
done
[ -f $D/posthoc_k4_int8_zstd.json ] || $L posthoc --cuts 2 4 > $D/logs/posthoc.log 2>&1 || echo "POSTHOC FAILED"
for ch in 4 8 16 32; do
  t=k4_c${ch}_w128_d2
  [ -f $D/eval_$t.json ] && continue
  echo "$(date -u +%T) train $t"
  $L train --cut 4 --channels $ch --width 128 --stride 2 --dec-layers 2 --epochs 20 > $D/logs/train_$t.log 2>&1 \
    || { echo "TRAIN FAILED $t"; continue; }
  $L eval --cut 4 --channels $ch --width 128 --stride 2 --dec-layers 2 > $D/logs/eval_$t.log 2>&1 || echo "EVAL FAILED $t"
done
$P -m evaluation.second_detector analyse > $D/logs/analyse.log 2>&1 || echo "ANALYSE FAILED"
echo "=== $(date -u +%T) SECOND_DETECTOR_DONE"
