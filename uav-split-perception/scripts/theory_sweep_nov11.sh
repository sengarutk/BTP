#!/bin/bash
# Paper 2 step-size and budget sweeps in the validated replay (validation/hardware/replay_theory_sweep.py);
# predictions: docs/theory_sweep_predictions_nov11.md. 5 shards (one per seed) in parallel; resumable (rows that
# exist are skipped). Long missions first (all 11 policies), then the short ones (6 step sizes).
set -uo pipefail
cd "$(dirname "$0")/../validation/hardware"
P=/home/sengar/BTP/venv/bin/python
OUT=../../experiments/results/hardware/replay/theory_sweep_nov11
LOG=../../experiments/results/hardware/replay/theory_sweep_nov11/logs
mkdir -p $LOG
ETA="v41 th_eta0.02 th_eta0.05 th_eta0.2 th_eta0.5 th_eta1"
for s in 1 2 3 4 5; do
  (
    $P replay_theory_sweep.py run --scenario mission --phase-s 240 --seeds $s-$s --out $OUT > $LOG/long_s$s.log 2>&1 || exit 1
    for t in $s $((s + 5)); do
      $P replay_theory_sweep.py run --scenario mission random --phase-s 20 --seeds $t-$t --only $ETA --out $OUT \
        > $LOG/short_s$t.log 2>&1 || exit 1
    done
  ) &
done
fail=0
for j in $(jobs -p); do wait $j || fail=1; done
$P replay_theory_sweep.py analyze $OUT > $LOG/analyze.log 2>&1 || fail=1
echo "=== $(date -u +%T) THEORY_SWEEP_DONE fail=$fail"
exit $fail
