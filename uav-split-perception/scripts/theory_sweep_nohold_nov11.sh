#!/bin/bash
# Diagnostic runs (predictions addendum 2): the blackout hold off, 24-min missions, seeds 1-5. b2.8 runs now in one
# process (6 heavy processes with the ambient runs); b3.6 after the ambient runs, one shard per seed. Then analysis.
set -uo pipefail
cd "$(dirname "$0")/../validation/hardware"
P=/home/sengar/BTP/venv/bin/python
OUT=../../experiments/results/hardware/replay/theory_sweep_nov11
LOG=$OUT/logs
$P replay_theory_sweep.py run --scenario mission --phase-s 240 --seeds 1-5 --only th_nohold_b2.8 --out $OUT > $LOG/nohold_b2.8.log 2>&1 &
first=$!
while pgrep -f '[t]heory_sweep_ambient_nov11' > /dev/null; do sleep 20; done
for s in 1 2 3 4; do
  $P replay_theory_sweep.py run --scenario mission --phase-s 240 --seeds $s-$s --only th_nohold_b3.6 --out $OUT > $LOG/nohold_b3.6_s$s.log 2>&1 &
done
fail=0
for j in $(jobs -p); do wait $j || fail=1; done
$P replay_theory_sweep.py run --scenario mission --phase-s 240 --seeds 5-5 --only th_nohold_b3.6 --out $OUT > $LOG/nohold_b3.6_s5.log 2>&1 || fail=1
$P replay_theory_sweep.py analyze $OUT > $LOG/analyze.log 2>&1 || fail=1
echo "=== $(date -u +%T) THEORY_SWEEP_NOHOLD_DONE fail=$fail"
exit $fail
