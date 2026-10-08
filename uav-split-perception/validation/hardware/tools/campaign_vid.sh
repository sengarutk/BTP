#!/bin/bash
# Task-level campaign on VisDrone-VID val: every (scenario, policy) x REPS, policy order shuffled per repetition.
# Results: experiments/results/hardware/vid_campaign/. Skips runs whose result already exists (resumable).
D=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$D/../../.." && pwd)
R=${OUTDIR:-$REPO/experiments/results/hardware/vid_campaign}; mkdir -p $R
REPS=${REPS:-5}
COMMON="--vid visdrone_vid_640 --conf 0.01${LIVEFC:+ --live-forecast $LIVEFC}"   # LIVEFC=forecast_tuning_v2.json: live forecaster on the Pi
COMMON="$COMMON${POWERLOG:+ --power-log --energy-constants energy_constants.json}"   # POWERLOG=1: measured energy per run
AER="--acc variant_accuracy_visdrone.json"
DEC="--decay staleness_decay.json --objective stream"
DECF="--decay staleness_decay_forecast.json --objective stream"   # decay with motion forecasting (forecast.py)
DECF2="--decay staleness_decay_forecast_v2.json --objective stream"   # decay with the camera-aligned forecaster v2
declare -A ARGS=(
  [A_stream]="A_full|$COMMON $AER $DEC"
  [A_stream_fc]="A_full|$COMMON $AER $DECF"
  [A_stream_fc2]="A_full|$COMMON $AER $DECF2"
  [A_eco]="A_full|$COMMON $AER $DECF2 --energy-aware --power-budget ${BUDGET:-3.5}"         # controller v4
  [A_eco_tight]="A_full|$COMMON $AER $DECF2 --energy-aware --power-budget ${BUDGET_TIGHT:-2.8}"
  [A_eco41]="A_full|$COMMON $AER $DECF2 --energy-aware --power-budget ${BUDGET_TIGHT:-2.8} --fresh-target ${FRESH:-0.95}"   # v4.1
  [A_full_aer]="A_full|$COMMON $AER"
  [A_full]="A_full|$COMMON"
  [static_multi]="static_multi|$COMMON $AER"
  [abr_laptop]="abr:laptop|$COMMON $AER $DEC"
  [rule_fallback]="rule_fallback|$COMMON $AER"
  [fixed_laptop_m640q90]="fixed:laptop:m640q90|$COMMON $AER"
  [fixed_jetson_s640q90]="fixed:jetson:s640q90|$COMMON $AER"
  [fixed_onboard_n320]="fixed:onboard:n320|$COMMON $AER"
)
NAMES="${ONLY:-${!ARGS[@]}}"   # ONLY="a b c": run a subset of the policies
for rep in $(seq 1 $REPS); do
  for sc in ${SCENARIOS:-mission mission_mirror random static_good}; do
    order=$(python3 -c "import random;p='$NAMES'.split();p.sort();random.Random($rep*1000+len('$sc')).shuffle(p);print(' '.join(p))")
    for name in $order; do
      L=${sc}__${name}__r$rep
      [ -f $R/a2_$L.json ] && continue
      IFS='|' read -r POL EXTRA <<< "${ARGS[$name]}"
      # pause while either board is unreachable (a network outage must not burn through runs)
      until ping -c1 -W2 192.168.0.248 >/dev/null 2>&1 && ping -c1 -W2 192.168.0.188 >/dev/null 2>&1 \
            && $D/rsh.sh pi true 2>/dev/null && $D/rsh.sh nano true 2>/dev/null; do
        echo "$(date +%T) boards unreachable, waiting"; sleep 60; done
      # recover any result left on the Pi by an earlier connection drop, then log a heartbeat
      for f in $($D/rsh.sh pi "cd ~/hwbench/results; ls a2_*__r*.json 2>/dev/null" 2>/dev/null); do
        [ -f $R/$f ] || { $D/rcp.sh pi REMOTE:hwbench/results/$f $R/ 2>/dev/null && $D/rcp.sh pi REMOTE:hwbench/results/${f%.json}_dets.npz $R/ 2>/dev/null && { $D/rcp.sh pi REMOTE:hwbench/results/${f%.json}_livefc.npz $R/ 2>/dev/null; true; } && echo "$(date +%T) recovered $f"; }
      done
      echo "$(date +%T) heartbeat: $(ls $R/a2_*__r*.json 2>/dev/null | grep -vc dets) results; ping pi $(ping -c1 -W2 192.168.0.248 | grep -oE 'time=[0-9.]+' ) jetson $(ping -c1 -W2 192.168.0.188 | grep -oE 'time=[0-9.]+')"
      echo "=== $(date +%T) $L"
      $D/arun.sh $L "$POL" $sc ${PHASE_S:-20} $rep $R $EXTRA | grep -E '^\{' | cut -c1-200
    done
  done
done
echo CAMPAIGN_VID_DONE
