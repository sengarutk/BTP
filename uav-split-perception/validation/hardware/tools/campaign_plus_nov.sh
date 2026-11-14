#!/bin/bash
# campaign_plus_nov.sh - plan T8 / D2 (14 Nov 2026): v4.1+ (capped hold, room-following budget, contention-aware latency
#   10 ms, YOLO11n allowed onboard) against v4.1, scenarios mission (with blackouts) and random (random faults),
#   40-s phases, x 4 reps = 16 runs, ~7 min each, order shuffled. Every run starts with the camera Pi below 60 C.
#   Predictions: docs/mesh_predictions_nov14.md (T8). Results: vid_campaign_plus_nov/.
# First: push_code_mesh.sh (adaptive2.py with --budget-rule, --contention-ms; the _ft11 table), mesh_tunnel.sh, the
# keep-awake ping. Passwords: env PI2_PW PI3_PW NANO_PW N2_PW.
D=$(cd "$(dirname "$0")" && pwd); H=$(cd $D/../../.. && pwd)/experiments/results/hardware
R=$H/vid_campaign_plus_nov; PS=40; COOL=${COOL:-60}; mkdir -p $R
$D/mesh_ssh.sh camera "grep -q budget-rule ~/hwbench/adaptive2.py && test -f ~/hwbench/yolo11n_visdrone.pt && test -f ~/hwbench/variant_accuracy_visdrone_ft11.json" 2>/dev/null \
  || { echo "camera lacks adaptive2.py --budget-rule, yolo11n_visdrone.pt or the _ft11 table: push first"; exit 1; }
jobs() {
  for rep in 1 2 3 4; do
    python3 -c "
import random
c=[(s,m) for s in ('mission','random') for m in ('v41','v41plus')]
random.Random($rep*7717).shuffle(c)
print('\n'.join(f'$rep {s} {m}' for s,m in c))"
  done
}
for pass in 1 2; do
  jobs | while read rep sc m; do
    L=${sc}__${m}__r$rep
    [ -f $R/a2_$L.json ] && continue
    until $D/mesh_ssh.sh camera true 2>/dev/null && $D/mesh_ssh.sh jetson true 2>/dev/null && ss -ltn | grep -q 127.0.0.1:48104; do
      echo "$(date +%T) mesh or tunnel unreachable, waiting"; sleep 60; done
    for i in $(seq 60); do
      T=$($D/mesh_ssh.sh camera "vcgencmd measure_temp | tr -dc 0-9." 2>/dev/null)
      [ -n "$T" ] && python3 -c "import sys; sys.exit(float('$T') >= $COOL)" && break
      sleep 20
    done
    echo "=== $(date +%T) pass $pass $L  start ${T} C  (done: $(ls $R/a2_*__r?.json 2>/dev/null | wc -l))"
    $D/arun_mesh.sh $L $m $sc $PS $rep $R 2>&1 | grep -E '^\{|NO RESULT|abandoned|retry|copy failed|laptop link' | cut -c1-220
  done
done
echo "CAMPAIGN_PLUS_NOV_DONE ($(ls $R/a2_*__r?.json 2>/dev/null | wc -l) runs)"
