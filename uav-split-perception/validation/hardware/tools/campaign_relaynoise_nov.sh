#!/bin/bash
# campaign_relaynoise_nov.sh - the noisy-relay test of the hardening plan (Phase 6; prepared 10 Nov 2026): the multihop
#   route (the direct camera <-> ground link blocked, batman-adv relays through the Jetson) with 2 % or 5 % packet loss
#   and 5 +- 5 ms delay on both hops (scenarios multihop_loss2 / multihop_loss5 in adaptive2.py). v41, the hierarchical
#   chain (the Jetson decides) and fixed laptop offloading, 2 losses x 3 strategies x 2 reps = 12 runs, 40-s phases,
#   order shuffled, resumable, two passes. Compare with mesh campaign 2's noise-free multihop runs.
#   Predictions: docs/board_session_predictions_nov.md. Results: vid_campaign_relaynoise_nov/.
# First: push_code_mesh.sh (adaptive2.py), mesh_tunnel.sh, the keep-awake ping. Passwords: env PI2_PW PI3_PW NANO_PW.
D=$(cd "$(dirname "$0")" && pwd); H=$(cd $D/../../.. && pwd)/experiments/results/hardware
R=$H/vid_campaign_relaynoise_nov; PS=40; mkdir -p $R
jobs() {
  for rep in 1 2; do for sc in multihop_loss2 multihop_loss5; do
    for m in $(python3 -c "import random;p=['v41','hier','fixlap'];random.Random($rep*104729+int('$sc'[-1])).shuffle(p);print(' '.join(p))"); do echo "$rep $sc $m"; done
  done; done
}
for pass in 1 2; do
  jobs | while read rep sc m; do
    L=${sc}__${m}__r$rep
    [ -f $R/a2_$L.json ] && continue
    until $D/mesh_ssh.sh camera true 2>/dev/null && $D/mesh_ssh.sh jetson true 2>/dev/null && ss -ltn | grep -q 127.0.0.1:48104; do
      echo "$(date +%T) mesh or tunnel unreachable, waiting"; sleep 60; done
    echo "=== $(date +%T) pass $pass $L  (done: $(ls $R/a2_*__r?.json 2>/dev/null | wc -l))"
    $D/arun_mesh.sh $L $m $sc $PS $rep $R 2>&1 | grep -E '^\{|NO RESULT|abandoned|retry|multihop route|direct route|copy failed|laptop link' | cut -c1-220
  done
done
echo "CAMPAIGN_RELAYNOISE_NOV_DONE ($(ls $R/a2_*__r?.json 2>/dev/null | wc -l) runs)"
