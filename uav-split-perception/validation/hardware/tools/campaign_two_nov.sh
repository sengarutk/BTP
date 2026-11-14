#!/bin/bash
# campaign_two_nov.sh - plan T6 / D1 (14 Nov 2026): two sense drones (pi-relayyy, pi-receiver) with one edge drone
#   (v41j1: laptop + Nano1) or two (v41j2: laptop + Nano1 + Nano2, Nano2 also offering YOLOv8m), static_good and
#   mesh_mission (where Nano1's link is degraded or cut in some phases), 40-s phases, x 3 reps = 12 runs, ~7 min each.
#   Frame destinations, both Pis' power and temperature and both Jetsons' power are logged in every run.
#   Predictions: docs/mesh_predictions_nov14.md. Results: vid_campaign_two_nov/.
# First: push_code_mesh.sh with TARGETS="camera camera2 jetson jetson2", mesh_tunnel.sh AND mesh_tunnel2.sh, the
# keep-awake ping. Passwords: env PI2_PW PI3_PW NANO_PW N2_PW.
D=$(cd "$(dirname "$0")" && pwd); H=$(cd $D/../../.. && pwd)/experiments/results/hardware
R=$H/vid_campaign_two_nov; PS=40; mkdir -p $R
for c in camera camera2; do
  $D/mesh_ssh.sh $c "grep -q jetson2-m ~/hwbench/adaptive2.py" 2>/dev/null || { echo "$c has an adaptive2.py without --jetson2-m: push first"; exit 1; }
done
jobs() {
  for rep in 1 2 3; do
    python3 -c "
import random
c=[(s,m) for s in ('static_good','mesh_mission') for m in ('v41j1','v41j2')]
random.Random($rep*5003).shuffle(c)
print('\n'.join(f'$rep {s} {m}' for s,m in c))"
  done
}
for pass in 1 2; do
  jobs | while read rep sc m; do
    L=${sc}__${m}__r$rep
    [ -f $R/a2_${L}_c1.json ] && [ -f $R/a2_${L}_c2.json ] && continue
    until $D/mesh_ssh.sh camera true 2>/dev/null && $D/mesh_ssh.sh camera2 true 2>/dev/null && $D/mesh_ssh.sh jetson true 2>/dev/null \
          && $D/mesh_ssh.sh jetson2 true 2>/dev/null && ss -ltn | grep -q 127.0.0.1:48111; do
      echo "$(date +%T) mesh or tunnels unreachable, waiting"; sleep 60; done
    echo "=== $(date +%T) pass $pass $L  (done: $(ls $R/a2_*__r?_c2.json 2>/dev/null | wc -l))"
    $D/arun_two.sh $L $m $sc $PS $rep $R 2>&1 | grep -E '^c[12] \{|NO RESULT|abandoned|copy failed' | cut -c1-240
  done
done
echo "CAMPAIGN_TWO_NOV_DONE ($(ls $R/a2_*__r?_c2.json 2>/dev/null | wc -l) runs)"
