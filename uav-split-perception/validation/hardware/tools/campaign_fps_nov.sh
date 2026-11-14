#!/bin/bash
# campaign_fps_nov.sh - plan T7 (14 Nov 2026): camera frame rate and encode ahead (brief 19.13), one camera.
#   static_good, 40-s phases: v41 at 15, 30 and 60 frames/s, and v41ea (encode ahead) at 30 frames/s, x 3 reps = 12
#   runs, ~6 min each, order shuffled within each repetition. Predictions: docs/mesh_predictions_nov14.md.
#   Results: vid_campaign_fps_nov/ (labels static_good__v41_f15__r1 etc.).
# First: push_code_mesh.sh (adaptive2.py with --encode-ahead), mesh_tunnel.sh, the keep-awake ping.
# Passwords: env PI2_PW PI3_PW NANO_PW N2_PW.
D=$(cd "$(dirname "$0")" && pwd); H=$(cd $D/../../.. && pwd)/experiments/results/hardware
R=$H/vid_campaign_fps_nov; PS=40; mkdir -p $R
$D/mesh_ssh.sh camera "grep -q encode-ahead ~/hwbench/adaptive2.py" 2>/dev/null || { echo "camera has an adaptive2.py without --encode-ahead: push first"; exit 1; }
jobs() {
  for rep in 1 2 3; do
    for c in $(python3 -c "import random;p=['v41:15','v41:30','v41:60','v41ea:30'];random.Random($rep*3001).shuffle(p);print(' '.join(p))"); do
      echo "$rep static_good ${c%%:*} ${c##*:}"; done
  done
}
for pass in 1 2; do
  jobs | while read rep sc m fps; do
    L=${sc}__${m}_f${fps}__r$rep
    [ -f $R/a2_$L.json ] && continue
    until $D/mesh_ssh.sh camera true 2>/dev/null && $D/mesh_ssh.sh jetson true 2>/dev/null && ss -ltn | grep -q 127.0.0.1:48104; do
      echo "$(date +%T) mesh or tunnel unreachable, waiting"; sleep 60; done
    echo "=== $(date +%T) pass $pass $L  (done: $(ls $R/a2_*__r?.json 2>/dev/null | wc -l))"
    FPS=$fps $D/arun_mesh.sh $L $m $sc $PS $rep $R 2>&1 | grep -E '^\{|NO RESULT|abandoned|retry|copy failed|laptop link' | cut -c1-220
  done
done
echo "CAMPAIGN_FPS_NOV_DONE ($(ls $R/a2_*__r?.json 2>/dev/null | wc -l) runs)"
