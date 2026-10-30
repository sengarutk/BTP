#!/bin/bash
# push_code_mesh.sh - push_code.sh for the AegisSwarm mesh (29 Oct 2026): the same code and config files, copied with
# mesh_scp.sh (through pi-sender) to ~/hwbench on the camera (pi-relayyy) and the Jetson. results/ on the boards is
# never touched. Includes the AccuMO-style planner (mpc_planner.py, decay_context.py, bench_planner.py and
# decay_context_train.json) for adaptive2.py --policy accumo. Passwords: env PI2_PW PI3_PW NANO_PW.
# TARGETS="camera" (default "camera jetson"): the boards to update.
D=$(cd "$(dirname "$0")" && pwd); HW=$(cd "$D/.." && pwd); RES=$(cd "$HW/../../experiments/results/hardware" && pwd)
CODE="adaptive.py adaptive2.py energy_profile.py power_logger.py hwbench.py egomotion.py forecast.py relay.py pipeline_node.py
      thermal_steady.py edge_node.py mpc_planner.py decay_context.py bench_planner.py egomotion_bench.py"
CONF="staleness_decay.json staleness_decay_forecast_v2.json forecast_tuning_v2.json
      variant_accuracy_visdrone.json variant_accuracy_visdrone_ft.json decay_context_train.json"
for f in $CODE; do
  [ -f $HW/$f ] || { echo "missing code $f"; exit 1; }
  for t in ${TARGETS:-camera jetson}; do $D/mesh_scp.sh $t $HW/$f REMOTE:hwbench/ || { echo "copy failed: $f -> $t"; exit 1; }; done
done
for f in $CONF energy/energy_constants.json; do
  [ -f $RES/$f ] || { echo "missing config $f"; exit 1; }
  b=$(basename $f)
  for t in ${TARGETS:-camera jetson}; do $D/mesh_scp.sh $t $RES/$f REMOTE:hwbench/$b || { echo "copy failed: $f -> $t"; exit 1; }; done
done
# the copies must import on the camera (catches a missing file before a campaign starts)
[[ " ${TARGETS:-camera jetson} " == *" camera "* ]] && \
  $D/mesh_ssh.sh camera "cd ~/hwbench && /home/sengar/btp_env/bin/python -c 'import mpc_planner, decay_context; print(\"imports ok\")'"
echo PUSH_MESH_DONE
