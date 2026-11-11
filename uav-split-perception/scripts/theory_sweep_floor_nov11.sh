#!/bin/bash
# Addendum 5 (c): the floor temperature (offload only) at each room temperature, after the guard sweep. 24-min
# missions, seeds 1-5, 3 shards (memory). Resumable.
set -uo pipefail
cd "$(dirname "$0")/../validation/hardware"
P=/home/sengar/BTP/venv/bin/python
OUT=../../experiments/results/hardware/replay/theory_sweep_nov11
LOG=$OUT/logs
while pgrep -f '[t]heory_sweep_guard_nov11.sh' > /dev/null; do sleep 60; done
POLS="th_floor_amb0 th_floor_amb5 th_floor_amb10 th_floor_amb15"
fail=0
printf "%s\n" 1 2 3 4 5 | xargs -P 3 -I{} sh -c "$P replay_theory_sweep.py run --scenario mission --phase-s 240 --seeds {}-{} --only $POLS --out $OUT > $LOG/floor_s{}.log 2>&1" || fail=1
echo "=== $(date -u +%T) THEORY_SWEEP_FLOOR_DONE fail=$fail"
exit $fail
