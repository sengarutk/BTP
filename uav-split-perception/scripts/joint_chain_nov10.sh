#!/bin/bash
# Phase 2 (hardening plan): train and score the jointly trained bottleneck for 4 configurations, one after another.
# Resumable: a configuration whose eval file exists is skipped. Run under scripts/guarded_run.py (memory watchdog).
cd "$(dirname "$0")/.." || exit 1
PY=/home/sengar/BTP/venv/bin/python
for cfg in "4 4 2" "4 16 2" "4 32 1" "2 8 2"; do
  set -- $cfg; tag="k$1_c$2_w128$([ $3 = 1 ] && echo _s1)_d2"
  [ -f experiments/results/joint_bottleneck/eval_joint_$tag.json ] && { echo "skip $tag"; continue; }
  echo "=== $(date +%T) train $tag"
  [ -f weights/joint_bottleneck/$tag.pt ] || $PY -m evaluation.joint_bottleneck train --cut $1 --channels $2 --stride $3 --epochs 30 --workers 1 || exit 1
  echo "=== $(date +%T) eval $tag"
  $PY -m evaluation.joint_bottleneck eval --cut $1 --channels $2 --stride $3 || exit 1
done
echo "=== $(date +%T) JOINT_CHAIN_DONE"
