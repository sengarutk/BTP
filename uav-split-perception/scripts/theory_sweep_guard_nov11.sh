#!/bin/bash
# Addendum 5 (hard guard, Theorem 3; adaptive budget with a raised cap): 24-min missions, seeds 1-5, one shard per
# seed. At most 6 heavy processes: 1 shard while the video-codec job runs (5 processes), up to 3 after. Resumable.
set -uo pipefail
cd "$(dirname "$0")/../validation/hardware"
P=/home/sengar/BTP/venv/bin/python
OUT=../../experiments/results/hardware/replay/theory_sweep_nov11
LOG=$OUT/logs
POLS="th_adapt_amb5_cap50 th_adapt_amb10_cap50 th_hold78_amb15 th_guard_amb0 th_guard_amb5 th_guard_amb10 th_guard_amb15"
fail=0; pids=()
for s in 1 2 3 4 5; do
  while :; do
    n=0; for p in "${pids[@]}"; do kill -0 "$p" 2>/dev/null && n=$((n+1)); done
    lim=3; pgrep -f '[v]ideo_codecs_nov11' > /dev/null && lim=1
    [ "$n" -lt "$lim" ] && break; sleep 30
  done
  $P replay_theory_sweep.py run --scenario mission --phase-s 240 --seeds $s-$s --only $POLS --out $OUT > $LOG/guard_s$s.log 2>&1 &
  pids+=($!)
done
for p in "${pids[@]}"; do wait "$p" || fail=1; done
$P replay_theory_sweep.py analyze $OUT > $LOG/analyze.log 2>&1 || fail=1
echo "=== $(date -u +%T) THEORY_SWEEP_GUARD_DONE fail=$fail"
exit $fail
