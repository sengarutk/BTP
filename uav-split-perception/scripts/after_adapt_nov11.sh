#!/bin/bash
# Queue: the adaptive-budget / price-cap runs, then the B_be bootstrap (one at a time, memory).
set -uo pipefail
cd "$(dirname "$0")/.."
P=/home/sengar/BTP/venv/bin/python
bash scripts/theory_sweep_adapt_nov11.sh || exit 1
$P -m evaluation.break_even_ci --n-boot 200 > experiments/joint_bottleneck_runs/logs/beci.log 2>&1 || exit 1
echo "=== $(date -u +%T) AFTER_ADAPT_DONE"
