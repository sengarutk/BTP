#!/bin/bash
# Main paper campaign (publication plan, Phase 3): controller v5 against (1) the same controller with only its
# value curve changed (the decay ablation that decides whether measured staleness matters) and (2) the
# literature baselines, all under one harness, live power on both boards (JLOG=1 + --power-log), live forecaster.
# Results: experiments/results/hardware/vid_campaign_main/. Resumable; outage guard; shuffled per rep.
# Run AFTER campaign_energy.sh has finished and push_code.sh has copied the current adaptive*.py to the boards.
# Passwords: env PI_PW / NANO_PW.
# Policies (all with the camera-motion-aligned forecaster running live; sAP scored with it):
#   v5            v4.2 (camera budget 2.8 W, edge budget 0.5 W) + predictive heat price (target 75 C, hard guard
#                 raised to 84 C so the smooth price is the active mechanism)
#   v42           v4.2 alone (the heat price ablated)
#   v5_nofc       v5 with the measured decay WITHOUT forecasting (staleness_decay.json)
#   v5_exp        v5 with a generic exponential decay (half-life = deadline)
#   v5_lin        v5 with a generic linear age-of-information decay
#   v5_flat       v5 with no staleness at all (rho = 1)
#   leaf          LEAF-style: v3+fc2 objective with a FIXED energy weight mu = 2.0 (the median price v4 settled at
#                 in the 100-run energy campaign, i.e. the best fixed weight we know) - no dual ascent, no heat price
#   conf_trigger  OffloaD-style detection-failure trigger
#   reward_offload  Qiu-style per-frame offloading reward from local detections (top 30 %)
#   aoi_thr       freshness-threshold offloading (150 ms)
#   jsq           shortest expected latency, no accuracy/energy term
#   fixed_laptop_m640q90  fixed JPEG offload to the ground GPU
# Also defined (run with ONLY=...): v51 = v5 + the v4.1 freshness price, v41, stream_fc2 (v3 + forecaster v2),
# onboard_n320 (onboard YOLOv8n-320 only). Long runs: PHASE_S=240 (6 phases x 4 min = 24 min per run).
D=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$D/../../.." && pwd)
# PI_TARGET=pi2 / pi3: second Pi 5 (sengar@192.168.0.129, PI2_PW) / third (dubey@192.168.0.247, PI3_PW); default: first (dubey@192.168.0.248, PI_PW)
if [ "${PI_TARGET:-pi}" = pi2 ]; then PIH=pi2; PI_IP=192.168.0.129; PIPY=/home/sengar/btp_env/bin/python; PIPW=$PI2_PW
elif [ "${PI_TARGET:-pi}" = pi3 ]; then PIH=pi3; PI_IP=192.168.0.247; PIPY=/home/dubey/btp_env/bin/python; PIPW=$PI3_PW
else PIH=pi; PI_IP=192.168.0.248; PIPY=/home/dubey/btp_env/bin/python; PIPW=$PI_PW; fi
R=${OUTDIR:-$REPO/experiments/results/hardware/vid_campaign_main}; mkdir -p $R
REPS=${REPS:-5}
export JLOG=1
LIVEFC=${LIVEFC:-forecast_tuning_v2.json}
COMMON="--vid visdrone_vid_640 --conf 0.01 --live-forecast $LIVEFC --power-log --energy-constants energy_constants.json --acc variant_accuracy_visdrone.json"
COMMON_NOFC="--vid visdrone_vid_640 --conf 0.01 --power-log --energy-constants energy_constants.json --acc variant_accuracy_visdrone.json"
DEC="--decay staleness_decay_forecast_v2.json --objective stream"
V42="--energy-aware --power-budget 2.8 --edge-energy-aware --edge-power-budget 0.5"
V5="$V42 --thermal-aware --thermal-target-c 75 --thermal-guard-c 84"
declare -A ARGS=(
  [v5]="A_full|$COMMON $DEC $V5"
  [v42]="A_full|$COMMON $DEC $V42"
  [v5_nofc]="A_full|$COMMON --decay staleness_decay.json --objective stream $V5"
  [v5_exp]="A_full|$COMMON $DEC --decay-shape exp $V5"
  [v5_lin]="A_full|$COMMON $DEC --decay-shape linear $V5"
  [v5_flat]="A_full|$COMMON $DEC --decay-shape flat $V5"
  [leaf]="A_full|$COMMON $DEC --energy-aware --mu-fixed 2.0"
  [conf_trigger]="conf_trigger|$COMMON"
  [reward_offload]="reward_offload|$COMMON"
  [aoi_thr]="aoi_thr|$COMMON"
  [jsq]="jsq|$COMMON"
  [fixed_laptop_m640q90]="fixed:laptop:m640q90|$COMMON"
  # added 12 Oct for the 24-minute runs and the same-day comparison table (campaign A of the plan)
  [v51]="A_full|$COMMON $DEC $V5 --fresh-target ${FRESH:-0.95}"
  [v41]="A_full|$COMMON $DEC --energy-aware --power-budget 2.8 --fresh-target ${FRESH:-0.95}"
  [stream_fc2]="A_full|$COMMON $DEC"
  [onboard_n320]="fixed:onboard:n320|$COMMON"
  # onboard-model comparison (20 Oct): one model alone on the Pi, no live forecaster (it would share the CPU);
  # scored afterwards with and without forecaster v2. Run with ONLY="onboard_s640 onboard_m640 onboard_l640".
  [onboard_s640]="fixed:onboard:s640|$COMMON_NOFC --onboard-variants s640 --paths laptop"
  [onboard_m640]="fixed:onboard:m640|$COMMON_NOFC --onboard-variants m640 --paths laptop"
  [onboard_l640]="fixed:onboard:l640|$COMMON_NOFC --onboard-variants l640 --paths laptop"
)
# Default set = the 12 policies of the 240-run main campaign; the added ones run only when named in ONLY.
DEFAULT_NAMES="v5 v42 v5_nofc v5_exp v5_lin v5_flat leaf conf_trigger reward_offload aoi_thr jsq fixed_laptop_m640q90"
NAMES="${ONLY:-$DEFAULT_NAMES}"
# a fresh campaign first archives the Pi's loose results: the recovery step below pulls any a2_*__r*.json the
# campaign folder lacks, so leftovers from an earlier campaign with the same names must not be on the Pi
if [ "$(ls $R/a2_*__r*.json 2>/dev/null | wc -l)" = 0 ]; then
  $D/rsh.sh $PIH "cd ~/hwbench/results && mkdir -p archive_before_main && mv a2_* pw_* archive_before_main/ 2>/dev/null; true"
  echo "$(date +%T) archived the Pi's earlier results into results/archive_before_main/"
fi
for rep in $(seq 1 $REPS); do
  for sc in ${SCENARIOS:-mission mission_mirror random static_good}; do
    order=$(python3 -c "import random;p='$NAMES'.split();p.sort();random.Random($rep*1000+len('$sc')).shuffle(p);print(' '.join(p))")
    for name in $order; do
      L=${sc}__${name}__r$rep
      [ -f $R/a2_$L.json ] && continue
      IFS='|' read -r POL EXTRA <<< "${ARGS[$name]}"
      until ping -c1 -W2 $PI_IP >/dev/null 2>&1 && $D/rsh.sh $PIH true 2>/dev/null \
            && { [ -n "$PI_ONLY" ] || { ping -c1 -W2 192.168.0.188 >/dev/null 2>&1 && $D/rsh.sh nano true 2>/dev/null; }; }; do
        echo "$(date +%T) boards unreachable, waiting"; sleep 60; done
      for f in $($D/rsh.sh $PIH "cd ~/hwbench/results; ls a2_*__r*.json 2>/dev/null" 2>/dev/null); do
        [ -f $R/$f ] || { $D/rcp.sh $PIH REMOTE:hwbench/results/$f $R/ 2>/dev/null && $D/rcp.sh $PIH REMOTE:hwbench/results/${f%.json}_dets.npz $R/ 2>/dev/null && { $D/rcp.sh $PIH REMOTE:hwbench/results/${f%.json}_livefc.npz $R/ 2>/dev/null; true; } && echo "$(date +%T) recovered $f"; }
      done
      echo "$(date +%T) heartbeat: $(ls $R/a2_*__r*.json 2>/dev/null | grep -vc dets) results; ping pi $(ping -c1 -W2 $PI_IP | grep -oE 'time=[0-9.]+' ) jetson $(ping -c1 -W2 192.168.0.188 | grep -oE 'time=[0-9.]+')"
      echo "=== $(date +%T) $L"
      $D/arun.sh $L "$POL" $sc ${PHASE_S:-20} $rep $R $EXTRA | grep -E '^\{' | cut -c1-200
    done
  done
done
echo CAMPAIGN_MAIN_DONE
