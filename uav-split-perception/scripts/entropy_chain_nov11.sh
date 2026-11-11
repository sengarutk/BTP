#!/bin/bash
# Entropy-coded bottlenecks (evaluation/entropy_bottleneck.py): train and evaluate 5 rate weights, after the replay
# sweeps (CPU and memory). Resumable: a trained weight is skipped if its train json exists, an eval if its eval json.
set -uo pipefail
cd "$(dirname "$0")/.."
P=/home/sengar/BTP/venv/bin/python
R=experiments/results/entropy_bottleneck
while pgrep -f '[r]eplay_theory_sweep|[t]heory_sweep_ambient_nov11' > /dev/null; do sleep 60; done
for lam in 0.03 0.1 0.01 0.3 0.003; do
  [ -f $R/train_ec_k4_c32_l${lam}.json ] || { echo "=== $(date -u +%T) train $lam"; $P -m evaluation.entropy_bottleneck train --lam $lam || exit 1; }
  [ -f $R/eval_ec_k4_c32_l${lam}.json ] || { echo "=== $(date -u +%T) eval $lam"; $P -m evaluation.entropy_bottleneck eval --lam $lam || exit 1; }
done
echo "=== $(date -u +%T) ENTROPY_CHAIN_DONE"
