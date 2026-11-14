#!/bin/bash
# push_code_mesh.sh - push_code.sh for the AegisSwarm mesh (29 Oct 2026): the same code and config files, copied with
# mesh_scp.sh (through pi-sender) to ~/hwbench on the camera (pi-relayyy) and the Jetson. results/ on the boards is
# never touched. Since 14 Nov also camera2 (pi-receiver) and jetson2 (Nano2); board map in mesh_hosts.sh. Includes the AccuMO-style planner (mpc_planner.py, decay_context.py, bench_planner.py and
# decay_context_train.json) for adaptive2.py --policy accumo. Passwords: env PI2_PW PI3_PW NANO_PW.
# TARGETS="camera" (default "camera jetson"; also camera2 jetson2): the boards to update. Passwords also N2_PW (Nano2).
# Ends with an md5 table of the pushed files on every target against the repository (MD5_OK / MD5_MISMATCH).
D=$(cd "$(dirname "$0")" && pwd); HW=$(cd "$D/.." && pwd); RES=$(cd "$HW/../../experiments/results/hardware" && pwd)
CODE="adaptive.py adaptive2.py energy_profile.py power_logger.py hwbench.py egomotion.py forecast.py relay.py pipeline_node.py
      thermal_steady.py edge_node.py mpc_planner.py decay_context.py bench_planner.py egomotion_bench.py
      split_live.py pull_bench.py"
CONF="staleness_decay.json staleness_decay_forecast_v2.json forecast_tuning_v2.json
      variant_accuracy_visdrone.json variant_accuracy_visdrone_ft.json variant_accuracy_visdrone_ft11.json
      decay_context_train.json"
for f in $CODE; do
  [ -f $HW/$f ] || { echo "missing code $f"; exit 1; }
  for t in ${TARGETS:-camera jetson}; do $D/mesh_scp.sh $t $HW/$f REMOTE:hwbench/ || { echo "copy failed: $f -> $t"; exit 1; }; done
done
for f in $CONF energy/energy_constants.json; do
  [ -f $RES/$f ] || { echo "missing config $f"; exit 1; }
  b=$(basename $f)
  for t in ${TARGETS:-camera jetson}; do $D/mesh_scp.sh $t $RES/$f REMOTE:hwbench/$b || { echo "copy failed: $f -> $t"; exit 1; }; done
done
# T10: the learned split codes split_live.py loads (weights/learned_bottleneck/<tag>.pt next to the code; ~2 MB each)
LB="k4_c4_w128_d2 k4_c8_w128_d2 k2_c8_w128_d2"
for t in ${TARGETS:-camera jetson}; do
  $D/mesh_ssh.sh $t "mkdir -p ~/hwbench/weights/learned_bottleneck" || { echo "mkdir failed on $t"; exit 1; }
  for c in $LB; do $D/mesh_scp.sh $t $HW/../../weights/learned_bottleneck/$c.pt REMOTE:hwbench/weights/learned_bottleneck/$c.pt \
    || { echo "copy failed: $c.pt -> $t"; exit 1; }; done
done
# the copies must import on the camera Pis (catches a missing file before a campaign starts)
for t in camera camera2; do [[ " ${TARGETS:-camera jetson} " == *" $t "* ]] && \
  $D/mesh_ssh.sh $t "cd ~/hwbench && /home/sengar/btp_env/bin/python -c 'import mpc_planner, decay_context; print(\"$t imports ok\")'"; done
# every pushed file must have the repository's md5 on every target
FILES=""; for f in $CODE; do FILES="$FILES $HW/$f"; done; for f in $CONF energy/energy_constants.json; do FILES="$FILES $RES/$f"; done
bad=0
for t in ${TARGETS:-camera jetson}; do
  names=$(for f in $FILES; do printf ' %s' "$(basename $f)"; done)
  remote=$($D/mesh_ssh.sh $t "cd ~/hwbench && md5sum$names" 2>/dev/null)
  for f in $FILES; do b=$(basename $f); m=$(md5sum < $f | cut -c1-32)
    echo "$remote" | grep -q "^$m  $b\$" || { echo "MD5_MISMATCH $t $b"; bad=1; }; done
done
[ $bad = 0 ] && echo "MD5_OK on ${TARGETS:-camera jetson}" || exit 1
echo PUSH_MESH_DONE
