#!/bin/bash
# campaign_topology_nov.sh - plan T9 (14 Nov 2026): the topology reversal of the Results Brief (Part 20, section 7) in ONE
#   campaign. Direct ground link (static_good) and forced multihop (multihop: relay through Nano1), v4.1 against the
#   hierarchical chain (hier) x 5 reps = 20 runs, ~6 min each, order shuffled within each repetition so the two
#   topologies alternate in time. Predictions: docs/mesh_predictions_nov14.md. Results: vid_campaign_topology_nov/.
# First: mesh_tunnel.sh, the keep-awake ping. Passwords: env PI2_PW PI3_PW NANO_PW N2_PW.
D=$(cd "$(dirname "$0")" && pwd); H=$(cd $D/../../.. && pwd)/experiments/results/hardware
R=$H/vid_campaign_topology_nov; PS=40; mkdir -p $R
jobs() {
  for rep in 1 2 3 4 5; do
    python3 -c "
import random
c=[(s,m) for s in ('static_good','multihop') for m in ('v41','hier')]
random.Random($rep*6007).shuffle(c)
print('\n'.join(f'$rep {s} {m}' for s,m in c))"
  done
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
echo "CAMPAIGN_TOPOLOGY_NOV_DONE ($(ls $R/a2_*__r?.json 2>/dev/null | wc -l) runs)"
