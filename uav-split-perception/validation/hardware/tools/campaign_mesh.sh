#!/bin/bash
# campaign_mesh.sh: v4.1 (direct three-tier) against the hierarchical chain (each tier deciding) on the AegisSwarm mesh
# (23 Oct 2026). Scenarios: static_good (normal) and mesh_mission; REPS (3) repetitions, order shuffled per repetition;
# 4-minute runs (PHASE_S=40). Results: experiments/results/hardware/vid_campaign_mesh/ (resumable: done runs skipped).
# Needs mesh_tunnel.sh running. Passwords: env PI2_PW PI3_PW NANO_PW.
D=$(cd "$(dirname "$0")" && pwd); R=${OUTDIR:-$(cd $D/../../.. && pwd)/experiments/results/hardware/vid_campaign_mesh}; mkdir -p $R
for rep in $(seq 1 ${REPS:-3}); do
  for sc in ${SCENARIOS:-static_good mesh_mission}; do
    for m in $(python3 -c "import random;p=['v41','hier'];random.Random($rep*1000+len('$sc')).shuffle(p);print(' '.join(p))"); do
      L=${sc}__${m}__r$rep
      [ -f $R/a2_$L.json ] && continue
      until $D/mesh_ssh.sh camera true 2>/dev/null && $D/mesh_ssh.sh jetson true 2>/dev/null && ss -ltn | grep -q 127.0.0.1:48104; do
        echo "$(date +%T) mesh or tunnel unreachable, waiting"; sleep 60; done
      echo "=== $(date +%T) $L  (done: $(ls $R/a2_*__r?.json 2>/dev/null | wc -l))"
      $D/arun_mesh.sh $L $m $sc ${PHASE_S:-40} $rep $R 2>&1 | grep -E '^\{|NO RESULT' | cut -c1-220
    done
  done
done
echo CAMPAIGN_MESH_DONE
