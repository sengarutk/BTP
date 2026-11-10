#!/bin/bash
# campaign_mesh4.sh - mesh campaign 4 (prepared 29 Oct 2026): the published-scheduler test of brief 19.10-19.11 on the
#   board. v41 against the AccuMO-style planner (accumo) and the LEAF-style fixed weight (leaf), which tied v4.1 or
#   were slightly ahead in the replay, within its error. static_good, mesh_mission, multihop x 5 reps = 45 runs (REPS=2: 18),
#   order shuffled, resumable, two passes. Before the first run the planner is timed on the camera Pi
#   (bench_planner.py, no workers needed) -> planner_bench_pi_mesh4.json. Every run logs the controller's predictions
#   (calib_hw.py) and accumo's planner time per frame (the run JSON's "mpc"). Results: vid_campaign_mesh4/.
# First: push_code_mesh.sh (the planner files), mesh_tunnel.sh, the keep-awake ping. Passwords: env PI2_PW PI3_PW NANO_PW.
D=$(cd "$(dirname "$0")" && pwd); H=$(cd $D/../../.. && pwd)/experiments/results/hardware
R=$H/vid_campaign_mesh4; PS=40; mkdir -p $R
if [ ! -f $R/planner_bench_pi_mesh4.json ]; then
  $D/mesh_ssh.sh camera "cd ~/hwbench && /home/sengar/btp_env/bin/python bench_planner.py --n 3000 --decay staleness_decay_forecast_v2.json --out results/planner_bench_pi_mesh4.json > /dev/null && cat results/planner_bench_pi_mesh4.json" > $R/planner_bench_pi_mesh4.json \
    && echo "planner timed on the camera Pi: $(python3 -c "import json;d=json.load(open('$R/planner_bench_pi_mesh4.json'));print(round(d['ms_median'],2),'ms median,',round(d['ms_p95'],2),'ms p95')")" \
    || { echo "planner benchmark failed (run push_code_mesh.sh first?)"; rm -f $R/planner_bench_pi_mesh4.json; exit 1; }
fi
jobs() {
  for rep in $(seq ${REPS:-5}); do for sc in static_good mesh_mission multihop; do
    for m in $(python3 -c "import random;p=['v41','accumo','leaf'];random.Random($rep*1000+len('$sc')).shuffle(p);print(' '.join(p))"); do echo "$rep $sc $m"; done
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
echo "CAMPAIGN_MESH4_DONE ($(ls $R/a2_*__r?.json 2>/dev/null | wc -l) runs)"
