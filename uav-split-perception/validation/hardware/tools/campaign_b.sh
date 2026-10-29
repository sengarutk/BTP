#!/bin/bash
# Task B campaign (21 Oct 2026): the relay path, VisDrone fine-tuned weights everywhere (camera --weight-suffix
# _visdrone, accuracy table variant_accuracy_visdrone_ft.json, workers via arun_b.sh), every run with all three paths
# connected (laptop, jetson, relay) so the four policies differ only in their decisions:
#   jet_s     fixed Pi -> Jetson, YOLOv8s-VisDrone JPEG q90 @640
#   lap_m     fixed Pi -> laptop, YOLOv8m-VisDrone JPEG q90 @640
#   relay_m   fixed Pi -> Jetson -> laptop (relay.py), YOLOv8m-VisDrone JPEG q90 @640
#   v41       controller v4.1 (stream objective, forecast-v2 decay, energy price 2.8 W, freshness target 0.95) over
#             onboard + jetson + laptop + relay, live forecaster
# Scenarios: static_good (normal), mission (stress), out_of_range (direct Pi -> laptop link cut for the whole run).
# Default: 3 reps x 3 scenarios x 4 policies = 36 runs, PHASE_S=40. Long runs: ONLY="v41 relay_m" SCENARIOS=mission
# REPS=1 PHASE_S=240 OUTDIR=<another empty dir>. Results: experiments/results/hardware/vid_campaign_b/ (resumable).
# Passwords: env PI2_PW / PI3_PW / NANO_PW. Needs push_code.sh (relay.py, VisDrone weights + table on both boards).
D=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$D/../../.." && pwd)
# PI_TARGET=pi2 / pi3: second Pi 5 (sengar@192.168.0.129, PI2_PW) / third (dubey@192.168.0.247, PI3_PW); default: first (dubey@192.168.0.248, PI_PW)
if [ "${PI_TARGET:-pi}" = pi2 ]; then PIH=pi2; PI_IP=192.168.0.129; PIPY=/home/sengar/btp_env/bin/python; PIPW=$PI2_PW
elif [ "${PI_TARGET:-pi}" = pi3 ]; then PIH=pi3; PI_IP=192.168.0.247; PIPY=/home/dubey/btp_env/bin/python; PIPW=$PI3_PW
else PIH=pi; PI_IP=192.168.0.248; PIPY=/home/dubey/btp_env/bin/python; PIPW=$PI_PW; fi
R=${OUTDIR:-$REPO/experiments/results/hardware/vid_campaign_b}; mkdir -p $R
REPS=${REPS:-3}
export JLOG=1
LIVEFC=${LIVEFC:-forecast_tuning_v2.json}
VD="--weight-suffix _visdrone --acc variant_accuracy_visdrone_ft.json --paths laptop,jetson,relay ${ONB:-}"
COMMON="--vid visdrone_vid_640 --conf 0.01 --live-forecast $LIVEFC --power-log --energy-constants energy_constants.json $VD"
DEC="--decay ${DECAY:-staleness_decay_forecast_v2.json} --objective stream"
declare -A ARGS=(
  [jet_s]="fixed:jetson:s640q90|$COMMON"
  [lap_m]="fixed:laptop:m640q90|$COMMON"
  [relay_m]="fixed:relay:m640q90|$COMMON"
  [v41]="A_full|$COMMON $DEC --energy-aware --power-budget 2.8 --fresh-target ${FRESH:-0.95}"
)
DEFAULT_NAMES="jet_s lap_m relay_m v41"
NAMES="${ONLY:-$DEFAULT_NAMES}"
# a fresh campaign first archives the Pi's loose results: the recovery step below pulls any a2_*__r*.json the
# campaign folder lacks, so leftovers from an earlier campaign with the same names must not be on the Pi
if [ "$(ls $R/a2_*__r*.json 2>/dev/null | wc -l)" = 0 ]; then
  $D/rsh.sh $PIH "cd ~/hwbench/results && mkdir -p archive_before_main && mv a2_* pw_* archive_before_main/ 2>/dev/null; true"
  echo "$(date +%T) archived the Pi's earlier results into results/archive_before_main/"
fi
for rep in $(seq 1 $REPS); do
  for sc in ${SCENARIOS:-static_good mission out_of_range}; do
    order=$(python3 -c "import random;p='$NAMES'.split();p.sort();random.Random($rep*1000+len('$sc')).shuffle(p);print(' '.join(p))")
    for name in $order; do
      L=${sc}__${name}${TAG:-}__r$rep    # TAG (e.g. _long): distinct labels for another campaign on this Pi
      [ -f $R/a2_$L.json ] && continue
      IFS='|' read -r POL EXTRA <<< "${ARGS[$name]}"
      until ping -c1 -W2 $PI_IP >/dev/null 2>&1 && $D/rsh.sh $PIH true 2>/dev/null \
            && { [ -n "$PI_ONLY" ] || { ping -c1 -W2 ${NANO_IP:-192.168.0.188} >/dev/null 2>&1 && $D/rsh.sh nano true 2>/dev/null; }; }; do
        echo "$(date +%T) boards unreachable, waiting"; sleep 60; done
      for f in $($D/rsh.sh $PIH "cd ~/hwbench/results; ls a2_*__r*.json 2>/dev/null" 2>/dev/null); do
        [ -f $R/$f ] || { $D/rcp.sh $PIH REMOTE:hwbench/results/$f $R/ 2>/dev/null && $D/rcp.sh $PIH REMOTE:hwbench/results/${f%.json}_dets.npz $R/ 2>/dev/null && { $D/rcp.sh $PIH REMOTE:hwbench/results/${f%.json}_livefc.npz $R/ 2>/dev/null; true; } && echo "$(date +%T) recovered $f"; }
      done
      echo "$(date +%T) heartbeat: $(ls $R/a2_*__r*.json 2>/dev/null | grep -vc dets) results; ping pi $(ping -c1 -W2 $PI_IP | grep -oE 'time=[0-9.]+' ) jetson $(ping -c1 -W2 ${NANO_IP:-192.168.0.188} | grep -oE 'time=[0-9.]+')"
      echo "=== $(date +%T) $L"
      RELAY=1 $D/arun_b.sh $L "$POL" $sc ${PHASE_S:-20} $rep $R $EXTRA | grep -E '^\{' | cut -c1-200
    done
  done
done
echo CAMPAIGN_B_DONE
