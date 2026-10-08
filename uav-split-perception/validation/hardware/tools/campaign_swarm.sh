#!/bin/bash
# Two-camera swarm campaign on VisDrone-VID val (the Pi and the Jetson as camera drones, the laptop as the shared
# ground station). Settings x scenarios x REPS, order shuffled per repetition, resumable, outage guard, heartbeat.
#   pi_alone     the Pi camera alone (arun.sh): the reference for what sharing costs
#   duo_none     both cameras, controller v2 (aerial accuracy), coordinator in logging-only mode
#   duo_coord    both cameras, controller v2 (aerial accuracy), coordinator admitting cameras to the laptop path
#   duo_fixed    both cameras, fixed JPEG q90 to the laptop's YOLOv8m (no adaptation, no coordination)
# Every camera runs the live forecaster (forecast_tuning_v2.json). Results: experiments/results/hardware/swarm_duo/.
D=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$D/../../.." && pwd)
R=${OUTDIR:-$REPO/experiments/results/hardware/swarm_duo}; mkdir -p $R
REPS=${REPS:-3}
COMMON="--vid visdrone_vid_640 --conf 0.01 --live-forecast forecast_tuning_v2.json --acc variant_accuracy_visdrone.json"
SETTINGS="pi_alone duo_none duo_coord duo_fixed"
for rep in $(seq 1 $REPS); do
  for sc in static_good mission; do
    order=$(python3 -c "import random;p='$SETTINGS'.split();random.Random($rep*1000+len('$sc')).shuffle(p);print(' '.join(p))")
    for st in $order; do
      L=${sc}__${st}__r$rep
      done_f=$R/a2_${L}__pi.json; [ $st = pi_alone ] && done_f=$R/a2_$L.json
      [ -f $done_f ] && continue
      until ping -c1 -W2 192.168.0.248 >/dev/null 2>&1 && ping -c1 -W2 192.168.0.188 >/dev/null 2>&1 \
            && $D/rsh.sh pi true 2>/dev/null && $D/rsh.sh nano true 2>/dev/null; do
        echo "$(date +%T) boards unreachable, waiting"; sleep 60; done
      echo "$(date +%T) heartbeat: $(ls $R/a2_*__r*.json $R/a2_*__r*__pi.json 2>/dev/null | sort -u | grep -vc dets) runs; ping pi $(ping -c1 -W2 192.168.0.248 | grep -oE 'time=[0-9.]+') jetson $(ping -c1 -W2 192.168.0.188 | grep -oE 'time=[0-9.]+')"
      echo "=== $(date +%T) $L"
      case $st in
        pi_alone)  $D/arun.sh $L A_full $sc 20 $rep $R $COMMON | grep -E '^\{' | cut -c1-200 ;;
        duo_none)  $D/arun2.sh $L none A_full $sc 20 $rep $R $COMMON | grep -E '^\{' | cut -c1-200 ;;
        duo_coord) $D/arun2.sh $L admission A_full $sc 20 $rep $R $COMMON | grep -E '^\{' | cut -c1-200 ;;
        duo_fixed) $D/arun2.sh $L none fixed:laptop:m640q90 $sc 20 $rep $R $COMMON | grep -E '^\{' | cut -c1-200 ;;
      esac
    done
  done
done
echo CAMPAIGN_SWARM_DONE
