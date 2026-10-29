#!/bin/bash
# campaign_mesh2.sh - the mesh campaign of 24 Oct 2026 (plan agreed with the user), VisDrone weights, motion forecaster in all:
#   short (default): strategies v41 v41e heat heate noprice fixlap aoithr x static_good mesh_mission multihop x 3 reps,
#                    plus hier x multihop x 3 (hier's normal/mission runs are in vid_campaign_mesh/)
#   long (MODE=long): 24-min mesh missions (PHASE_S=240): v41 heat x 5 reps, v41e heate x 3 reps
# Order shuffled per repetition; resumable (done runs skipped); a second pass at the end fills any failed run.
# Results: experiments/results/hardware/vid_campaign_mesh2/ (short) or vid_campaign_mesh2_long/ (long).
# Needs mesh_tunnel.sh running. Passwords: env PI2_PW PI3_PW NANO_PW.
D=$(cd "$(dirname "$0")" && pwd); H=$(cd $D/../../.. && pwd)/experiments/results/hardware
if [ "${MODE:-short}" = long ]; then R=$H/vid_campaign_mesh2_long; PS=240
else R=$H/vid_campaign_mesh2; PS=40; fi
mkdir -p $R
jobs() {   # prints "rep scenario strategy" lines in run order
  if [ "${MODE:-short}" = long ]; then
    for rep in 1 2 3 4 5; do
      s="v41 heat"; [ $rep -le 3 ] && s="$s v41e heate"
      for m in $(python3 -c "import random;p='$s'.split();random.Random($rep*77).shuffle(p);print(' '.join(p))"); do echo "$rep mesh_mission $m"; done
    done
  else
    for rep in 1 2 3; do for sc in static_good mesh_mission multihop; do
      s="v41 v41e heat heate noprice fixlap aoithr"; [ $sc = multihop ] && s="$s hier"
      for m in $(python3 -c "import random;p='$s'.split();random.Random($rep*1000+len('$sc')).shuffle(p);print(' '.join(p))"); do echo "$rep $sc $m"; done
    done; done
  fi
}
for pass in 1 2; do
  jobs | while read rep sc m; do
    L=${sc}__${m}__r$rep
    [ -f $R/a2_$L.json ] && continue
    until $D/mesh_ssh.sh camera true 2>/dev/null && $D/mesh_ssh.sh jetson true 2>/dev/null && ss -ltn | grep -q 127.0.0.1:48104; do
      echo "$(date +%T) mesh or tunnel unreachable, waiting"; sleep 60; done
    echo "=== $(date +%T) pass $pass $L  (done: $(ls $R/a2_*__r?.json 2>/dev/null | wc -l))"
    $D/arun_mesh.sh $L $m $sc $PS $rep $R 2>&1 | grep -E '^\{|NO RESULT|abandoned|retry|multihop route|direct route|copy failed' | cut -c1-220
  done
done
echo "CAMPAIGN_MESH2_DONE ($(ls $R/a2_*__r?.json 2>/dev/null | wc -l) runs)"
