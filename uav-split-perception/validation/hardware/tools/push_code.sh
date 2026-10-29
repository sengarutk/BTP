#!/bin/bash
# Push the live-run code and config to both boards (~/hwbench is a flat copy: code + JSONs together).
# Only the files the boards execute are copied; results/ on the boards is never touched. Run after
# editing adaptive*.py / power_logger.py / thermal_steady.py / energy_profile.py / the decay-accuracy-
# forecast JSONs. The JSONs live in experiments/results/hardware in the repo (energy_constants.json in
# experiments/results/hardware/energy). Passwords: env PI_PW / NANO_PW (/ PI2_PW / PI3_PW).
# TARGETS="pi2 nano" (default "pi nano"): the boards to update.
D=$(cd "$(dirname "$0")" && pwd); HW=$(cd "$D/.." && pwd); RES=$(cd "$HW/../../experiments/results/hardware" && pwd)
CODE="adaptive.py adaptive2.py energy_profile.py power_logger.py hwbench.py egomotion.py forecast.py relay.py pipeline_node.py
      thermal_steady.py"
CONF="staleness_decay.json staleness_decay_forecast_v2.json forecast_tuning_v2.json
      variant_accuracy_visdrone.json variant_accuracy_visdrone_ft.json"
for f in $CODE; do
  [ -f $HW/$f ] || { echo "missing code $f"; exit 1; }
  for t in ${TARGETS:-pi nano}; do $D/rcp.sh $t $HW/$f REMOTE:hwbench/ || exit 1; done
done
for f in $CONF energy/energy_constants.json; do
  [ -f $RES/$f ] || { echo "missing config $f"; exit 1; }
  b=$(basename $f)
  for t in ${TARGETS:-pi nano}; do $D/rcp.sh $t $RES/$f REMOTE:hwbench/$b || exit 1; done
done
echo PUSH_DONE
