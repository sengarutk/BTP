#!/bin/bash
# Phase G energy campaign: controller v4.2 (both drones priced) vs v4.1 / v4 / v3+forecaster-v2 / fixed
# JPEG offload, every run with live power logging on BOTH boards (JLOG=1 Jetson power_logger +
# --power-log on the Pi camera) and the Jetson worker reporting board power per response
# (--report-power jetson, wired in arun.sh). Results: experiments/results/hardware/vid_campaign_v42/
# (a NEW directory: the 7 Oct 100-run campaign lives in vid_campaign_energy/ and must stay untouched;
# v4/v3+fc2/fixed are re-run here fresh so every policy is compared with live logging on both boards).
# Resumable; skips runs whose result already exists. Passwords: env PI_PW / NANO_PW.
# Policies:
#   A_eco42      v4.2: camera budget 2.8 W (as v4/v4.1, directly comparable) + edge drone priced with
#                --edge-energy-aware --edge-power-budget 0.5 (W above the Jetson's idle; v4-style runs
#                averaged ~0.86 W extra, so this budget binds and tests that mu_edge tracks it). A 0 budget
#                is degenerate: extra power is never negative, so mu_edge could only rise and the edge
#                path would be priced out for good after its first use.
#   A_eco42d     v4.2 with BOTH budgets DERIVED from battery + flight power for a 28-min mission:
#                camera mini_249g 60*17.3/28 - 33.5 = 3.57 W, edge edge_1.5kg 60*88.8/28 - 153.6 = 36.7 W
#                (non-binding: at realistic battery numbers the edge drone's serving energy is <1 % of
#                its flight power, so this measures whether edge pricing matters at all)
#   A_eco41      v4.1 (freshness target), A_eco_tight v4, A_stream_fc2 v3+forecaster-v2,
#   fixed_laptop_m640q90   the JPEG-offload reference of the 100-run campaign
D=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$D/../../.." && pwd)
R=${OUTDIR:-$REPO/experiments/results/hardware/vid_campaign_v42}; mkdir -p $R
REPS=${REPS:-5}
export JLOG=1 POWERLOG=1        # live power log of the Jetson (power_logger) and the Pi camera, every run
LIVEFC=${LIVEFC:-forecast_tuning_v2.json}
COMMON="--vid visdrone_vid_640 --conf 0.01 --live-forecast $LIVEFC --power-log --energy-constants energy_constants.json"
AER="--acc variant_accuracy_visdrone.json"
DECF2="--decay staleness_decay_forecast_v2.json --objective stream"   # decay with the camera-aligned forecaster v2
declare -A ARGS=(
  [A_eco42]="A_full|$COMMON $AER $DECF2 --energy-aware --power-budget 2.8 --edge-energy-aware --edge-power-budget ${EDGE_BUDGET:-0.5}"
  [A_eco42d]="A_full|$COMMON $AER $DECF2 --energy-aware --mission-min 28 --camera-drone-class mini_249g --edge-drone-class edge_1.5kg --edge-energy-aware"
  [A_eco41]="A_full|$COMMON $AER $DECF2 --energy-aware --power-budget 2.8 --fresh-target ${FRESH:-0.95}"
  [A_eco_tight]="A_full|$COMMON $AER $DECF2 --energy-aware --power-budget 2.8"
  [A_stream_fc2]="A_full|$COMMON $AER $DECF2"
  [fixed_laptop_m640q90]="fixed:laptop:m640q90|$COMMON $AER"
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
echo CAMPAIGN_ENERGY_DONE
