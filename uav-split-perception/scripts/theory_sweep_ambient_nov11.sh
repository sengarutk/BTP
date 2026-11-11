#!/bin/bash
# Ambient runs of the theory sweep (after scripts/theory_sweep_nov11.sh): 24-min missions, seeds 1-5, one shard
# per seed; then the analysis of the whole directory. Resumable.
set -uo pipefail
cd "$(dirname "$0")/../validation/hardware"
P=/home/sengar/BTP/venv/bin/python
OUT=../../experiments/results/hardware/replay/theory_sweep_nov11
LOG=$OUT/logs
while pgrep -f '[t]heory_sweep_nov11.sh' > /dev/null; do sleep 30; done
for s in 1 2 3 4 5; do
  $P replay_theory_sweep.py run --scenario mission --phase-s 240 --seeds $s-$s \
    --only th_amb5_b3.2 th_amb5_b3.6 th_amb10_b2.8 th_amb10_b3.6 --out $OUT > $LOG/amb_s$s.log 2>&1 &
done
fail=0
for j in $(jobs -p); do wait $j || fail=1; done
$P replay_theory_sweep.py analyze $OUT > $LOG/analyze.log 2>&1 || fail=1
echo "=== $(date -u +%T) THEORY_SWEEP_AMBIENT_DONE fail=$fail"
exit $fail
