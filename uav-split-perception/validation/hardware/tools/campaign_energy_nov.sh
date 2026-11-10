#!/bin/bash
# campaign_energy_nov.sh - the energy test of the hardening plan (Phase 6; prepared 10 Nov 2026). Isolates the energy
#   price and checks paper 2's Theorem 1 and Proposition 1 on the board: v41 (energy + freshness price, 2.8 W budget)
#   against freshonly (the same controller without the energy price) and v41b36 (a 3.6 W budget, the 80 C budget of
#   Proposition 1), with both paths up throughout (static_good) and 60-s phases (6-min runs, long enough for the board
#   temperature, tau about 150 s). 3 strategies x 4 reps = 12 runs, order shuffled, resumable, two passes.
#   Predictions written before the session: docs/board_session_predictions_nov.md. Results: vid_campaign_energy_nov/.
# First: push_code_mesh.sh (adaptive2.py), mesh_tunnel.sh, the keep-awake ping. Passwords: env PI2_PW PI3_PW NANO_PW.
D=$(cd "$(dirname "$0")" && pwd); H=$(cd $D/../../.. && pwd)/experiments/results/hardware
R=$H/vid_campaign_energy_nov; PS=60; mkdir -p $R
jobs() {
  for rep in 1 2 3 4; do
    for m in $(python3 -c "import random;p=['v41','freshonly','v41b36'];random.Random($rep*7919).shuffle(p);print(' '.join(p))"); do echo "$rep static_good $m"; done
  done
}
for pass in 1 2; do
  jobs | while read rep sc m; do
    L=${sc}__${m}__r$rep
    [ -f $R/a2_$L.json ] && continue
    until $D/mesh_ssh.sh camera true 2>/dev/null && $D/mesh_ssh.sh jetson true 2>/dev/null && ss -ltn | grep -q 127.0.0.1:48104; do
      echo "$(date +%T) mesh or tunnel unreachable, waiting"; sleep 60; done
    echo "=== $(date +%T) pass $pass $L  (done: $(ls $R/a2_*__r?.json 2>/dev/null | wc -l))"
    $D/arun_mesh.sh $L $m $sc $PS $rep $R 2>&1 | grep -E '^\{|NO RESULT|abandoned|retry|copy failed|laptop link' | cut -c1-220
  done
done
echo "CAMPAIGN_ENERGY_NOV_DONE ($(ls $R/a2_*__r?.json 2>/dev/null | wc -l) runs)"
