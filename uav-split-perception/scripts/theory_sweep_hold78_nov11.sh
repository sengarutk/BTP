#!/bin/bash
# Addendum 3: hold capped at 78 C, 24-min missions, seeds 1-5, two processes (beside the GPU training).
set -uo pipefail
cd "$(dirname "$0")/../validation/hardware"
P=/home/sengar/BTP/venv/bin/python
OUT=../../experiments/results/hardware/replay/theory_sweep_nov11
LOG=$OUT/logs
for pol in th_hold78 th_hold78_amb10; do
  $P replay_theory_sweep.py run --scenario mission --phase-s 240 --seeds 1-5 --only $pol --out $OUT > $LOG/$pol.log 2>&1 &
done
fail=0
for j in $(jobs -p); do wait $j || fail=1; done
$P replay_theory_sweep.py analyze $OUT > $LOG/analyze.log 2>&1 || fail=1
echo "=== $(date -u +%T) THEORY_SWEEP_HOLD78_DONE fail=$fail"
exit $fail
