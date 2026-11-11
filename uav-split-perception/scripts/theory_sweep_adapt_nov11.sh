#!/bin/bash
# Addendum 4 (price cap at +10 C, self-calibrating budget): 24-min missions, seeds 1-5, one shard per seed.
set -uo pipefail
cd "$(dirname "$0")/../validation/hardware"
P=/home/sengar/BTP/venv/bin/python
OUT=../../experiments/results/hardware/replay/theory_sweep_nov11
LOG=$OUT/logs
POLS="th_hold78_amb5 th_hold78_amb10_cap10 th_hold78_amb10_cap20 th_hold78_amb10_cap50 th_adapt_amb0 th_adapt_amb5 th_adapt_amb10"
# 3 shards at a time (11 Nov: 5 shards beside other jobs took Windows below the guard's 200 MB floor); resumable
fail=0
printf "%s\n" 1 2 3 4 5 | xargs -P 3 -I{} sh -c "$P replay_theory_sweep.py run --scenario mission --phase-s 240 --seeds {}-{} --only $POLS --out $OUT > $LOG/adapt_s{}.log 2>&1" || fail=1
$P replay_theory_sweep.py analyze $OUT > $LOG/analyze.log 2>&1 || fail=1
echo "=== $(date -u +%T) THEORY_SWEEP_ADAPT_DONE fail=$fail"
exit $fail
