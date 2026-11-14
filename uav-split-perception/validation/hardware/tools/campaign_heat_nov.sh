#!/bin/bash
# campaign_heat_nov.sh - plan T4 (14 Nov 2026): the capped hold and the hard guard on 24-minute missions with blackouts.
#   Scenario "mission" (the one of the Wi-Fi 24-minute runs that were hot 19-27 % of the time, vid_campaign_long; it has
#   a 4-minute total blackout, which mesh_mission does not), 240-s phases. v41 against v41cap (hold only below 78 C) and
#   v41guard (v41cap + no onboard inference starts at >= 78 C, paper 2 Theorem 3) x 5 reps = 15 runs, ~27 min each.
#   Every run starts only when the camera Pi is below 55 C (pre-cool), so all start from the same temperature.
#   Predictions: docs/mesh_predictions_nov14.md (committed before the first run). Results: vid_campaign_heat_nov/.
# First: push_code_mesh.sh (adaptive2.py of 14 Nov or later), mesh_tunnel.sh, the keep-awake ping.
# Passwords: env PI2_PW PI3_PW NANO_PW N2_PW.
D=$(cd "$(dirname "$0")" && pwd); H=$(cd $D/../../.. && pwd)/experiments/results/hardware
R=$H/vid_campaign_heat_nov; PS=240; COOL=${COOL:-55}; mkdir -p $R
$D/mesh_ssh.sh camera "grep -q hold-max-c ~/hwbench/adaptive2.py" 2>/dev/null || { echo "camera has an adaptive2.py without --hold-max-c: push first"; exit 1; }
jobs() {
  for rep in 1 2 3 4 5; do
    for m in $(python3 -c "import random;p=['v41','v41cap','v41guard'];random.Random($rep*4241).shuffle(p);print(' '.join(p))"); do echo "$rep mission $m"; done
  done
}
for pass in 1 2; do
  jobs | while read rep sc m; do
    L=${sc}__${m}__r$rep
    [ -f $R/a2_$L.json ] && continue
    until $D/mesh_ssh.sh camera true 2>/dev/null && $D/mesh_ssh.sh jetson true 2>/dev/null && ss -ltn | grep -q 127.0.0.1:48104; do
      echo "$(date +%T) mesh or tunnel unreachable, waiting"; sleep 60; done
    for i in $(seq 90); do       # pre-cool: at most 30 min
      T=$($D/mesh_ssh.sh camera "vcgencmd measure_temp | tr -dc 0-9." 2>/dev/null)
      [ -n "$T" ] && python3 -c "import sys; sys.exit(float('$T') >= $COOL)" && break
      sleep 20
    done
    echo "=== $(date +%T) pass $pass $L  start temperature ${T} C  (done: $(ls $R/a2_*__r?.json 2>/dev/null | wc -l))"
    echo "$L $T" >> $R/start_temps.txt
    $D/arun_mesh.sh $L $m $sc $PS $rep $R 2>&1 | grep -E '^\{|NO RESULT|abandoned|retry|copy failed|laptop link' | cut -c1-220
  done
done
echo "CAMPAIGN_HEAT_NOV_DONE ($(ls $R/a2_*__r?.json 2>/dev/null | wc -l) runs)"
