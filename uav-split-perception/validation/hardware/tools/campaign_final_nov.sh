#!/bin/bash
# campaign_final_nov.sh - plan Phase 4 (16 Nov 2026): the FINAL controller (v41final: v4.1 + capped hold + guard 76.5 C
#   + YOLO11n-480 priced + contention 10 ms, fixed 2.8 W budget) against v4.1 and the two published-style schedulers
#   that tied it on 2 reps in mesh4 (accumo: AccuMO-style planner; leaf: LEAF-style fixed weight), mesh_mission and
#   multihop (static_good dropped: the laptop serves every frame and all four tie there, mesh4), 40-s phases, x 5 reps
#   = 40 runs, order shuffled per rep, resumable, two passes. Every run starts with the camera Pi below 60 C, so the
#   thermal rules of v41final meet the same start as everything else. Predictions: docs/mesh_predictions_nov14.md
#   (Phase 4, committed before the first run). Results: ${FINAL_OUT:-vid_campaign_final_nov}/.
# First: push_code_mesh.sh, mesh_tunnel.sh, the keep-awake ping. Passwords: env PI2_PW PI3_PW NANO_PW N2_PW.
D=$(cd "$(dirname "$0")" && pwd); H=$(cd $D/../../.. && pwd)/experiments/results/hardware
R=$H/${FINAL_OUT:-vid_campaign_final_nov}; PS=40; COOL=${COOL:-60}; mkdir -p $R
$D/mesh_ssh.sh camera "grep -q guard-hard-c ~/hwbench/adaptive2.py && grep -q contention-ms ~/hwbench/adaptive2.py && test -f ~/hwbench/yolo11n_visdrone.pt && test -f ~/hwbench/variant_accuracy_visdrone_ft11.json && test -f ~/hwbench/decay_context_train.json" 2>/dev/null \
  || { echo "camera lacks the final controller's options, YOLO11n, the _ft11 table or the planner's decay context: push first"; exit 1; }
jobs() {
  for rep in $(seq ${FINAL_REPS:-5}); do for sc in mesh_mission multihop; do
    for m in $(python3 -c "import random;p=['v41final','v41','accumo','leaf'];random.Random($rep*1009+len('$sc')).shuffle(p);print(' '.join(p))"); do echo "$rep $sc $m"; done
  done; done
}
for pass in 1 2; do
  jobs | while read rep sc m; do
    L=${sc}__${m}__r$rep
    [ -f $R/a2_$L.json ] && continue
    until $D/mesh_ssh.sh camera true 2>/dev/null && $D/mesh_ssh.sh jetson true 2>/dev/null && ss -ltn | grep -q 127.0.0.1:48104; do
      echo "$(date +%T) mesh or tunnel unreachable, waiting"; sleep 60; done
    for i in $(seq 60); do       # pre-cool: at most 20 min
      T=$($D/mesh_ssh.sh camera "vcgencmd measure_temp | tr -dc 0-9." 2>/dev/null)
      [ -n "$T" ] && python3 -c "import sys; sys.exit(float('$T') >= $COOL)" && break
      sleep 20
    done
    echo "=== $(date +%T) pass $pass $L  start ${T} C  (done: $(ls $R/a2_*__r?.json 2>/dev/null | wc -l))"
    echo "$L $T" >> $R/start_temps.txt
    $D/arun_mesh.sh $L $m $sc $PS $rep $R 2>&1 | grep -E '^\{|NO RESULT|abandoned|retry|multihop route|direct route|copy failed|laptop link' | cut -c1-220
  done
done
echo "CAMPAIGN_FINAL_NOV_DONE ($(ls $R/a2_*__r?.json 2>/dev/null | wc -l) runs)"
