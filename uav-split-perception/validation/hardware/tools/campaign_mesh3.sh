#!/bin/bash
# campaign_mesh3.sh - mesh campaign 3 (25 Oct 2026): the Jetson energy price with a realistic budget. v41 against
#   v41e12 (v41 + Jetson energy price, budget 1.2 W of extra Jetson power, between its unpriced draw in the normal
#   (1.0 W) and mission (1.4 W) scenarios; the 0.5 W of campaign 2 was never reachable) x static_good, mesh_mission,
#   multihop x 3 reps = 18 runs, order shuffled, resumable, two passes. Camera code logs the Jetson's power in every
#   strategy (edge_w_log), so the energy saved is measured, not modelled. Results: vid_campaign_mesh3/.
# Needs mesh_tunnel.sh and the keep-awake ping. Passwords: env PI2_PW PI3_PW NANO_PW.
D=$(cd "$(dirname "$0")" && pwd); H=$(cd $D/../../.. && pwd)/experiments/results/hardware
R=$H/vid_campaign_mesh3; PS=40; mkdir -p $R
jobs() {
  for rep in 1 2 3; do for sc in static_good mesh_mission multihop; do
    for m in $(python3 -c "import random;p=['v41','v41e12'];random.Random($rep*1000+len('$sc')).shuffle(p);print(' '.join(p))"); do echo "$rep $sc $m"; done
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
echo "CAMPAIGN_MESH3_DONE ($(ls $R/a2_*__r?.json 2>/dev/null | wc -l) runs)"
