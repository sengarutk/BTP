#!/bin/bash
# campaign_dvfs_nov.sh - plan Phase 5 (16 Nov 2026): the CPU clock as a third knob. v41dvfs (v41final + 1.8 GHz twins of
#   the onboard variants, priced at the measured energy ratio, docs/dvfs_design_nov16.md) against v41final, paired:
#     heat:  scenario mission (4-min total blackout), 240-s phases (24 min), 3 reps, start below 55 C
#     short: scenario mission, 40-s phases, 5 reps, start below 60 C
#   (mesh_mission / multihop not run: onboard serves 2-5 % of frames there, so the clock cannot matter.)
#   First pushes adaptive2.py (with --onboard-clocks) to the camera and copies the measured profile as dvfs_profile.json,
#   and checks both. After every run the camera's clock cap is checked and restored to the hardware maximum.
#   Predictions: docs/mesh_predictions_nov14.md (Phase 5, committed before the first run). Results: vid_campaign_dvfs_heat/,
#   vid_campaign_dvfs_short/.  Passwords: env PI2_PW PI3_PW NANO_PW N2_PW.
D=$(cd "$(dirname "$0")" && pwd); H=$(cd $D/../../.. && pwd)/experiments/results/hardware
S="printf '%s\n' \"\$PW\" | sudo -S -p ''"
TARGETS=camera $D/push_code_mesh.sh 2>&1 | grep -E "MD5_OK|MD5_MISMATCH|rror" || { echo "push failed"; exit 1; }
$D/mesh_scp.sh camera $H/energy/dvfs_profile_pi-receiver_20261116.json REMOTE:hwbench/dvfs_profile.json || { echo "profile copy failed"; exit 1; }
$D/mesh_ssh.sh camera "grep -q onboard-clocks ~/hwbench/adaptive2.py && python3 -c \"import json;json.load(open('/home/sengar/hwbench/dvfs_profile.json'))['summary']['1800']['s320']\"" 2>/dev/null \
  || { echo "camera lacks --onboard-clocks or the profile: abandoned"; exit 1; }
restore_clock() {
  $D/mesh_ssh.sh camera "PW='$PI2_PW'; c=/sys/devices/system/cpu/cpu0/cpufreq; m=\$(cat \$c/cpuinfo_max_freq); [ \"\$(cat \$c/scaling_max_freq)\" = \"\$m\" ] && echo clock_ok || { echo \$m | $S tee \$c/scaling_max_freq > /dev/null; echo clock_RESTORED; }" 2>/dev/null
}
run_set() {   # $1 out dir, $2 phase s, $3 reps, $4 cool C, $5 seed base
  local R=$H/$1 PS=$2 REPS=$3 COOL=$4 SB=$5; mkdir -p $R
  for pass in 1 2; do
    for rep in $(seq $REPS); do
      for m in $(python3 -c "import random;p=['v41final','v41dvfs'];random.Random($rep*$SB).shuffle(p);print(' '.join(p))"); do
        L=mission__${m}__r$rep
        [ -f $R/a2_$L.json ] && continue
        until $D/mesh_ssh.sh camera true 2>/dev/null && $D/mesh_ssh.sh jetson true 2>/dev/null && ss -ltn | grep -q 127.0.0.1:48104; do
          echo "$(date +%T) mesh or tunnel unreachable, waiting"; sleep 60; done
        for i in $(seq 90); do
          T=$($D/mesh_ssh.sh camera "vcgencmd measure_temp | tr -dc 0-9." 2>/dev/null)
          [ -n "$T" ] && python3 -c "import sys; sys.exit(float('$T') >= $COOL)" && break
          sleep 20
        done
        echo "=== $(date +%T) $1 pass $pass $L  start ${T} C  (done: $(ls $R/a2_*__r?.json 2>/dev/null | wc -l))"
        echo "$L $T" >> $R/start_temps.txt
        $D/arun_mesh.sh $L $m mission $PS $rep $R 2>&1 | grep -E '^\{|NO RESULT|abandoned|retry|copy failed|laptop link' | cut -c1-220
        echo "  $(restore_clock)"
      done
    done
  done
}
run_set vid_campaign_dvfs_heat 240 3 55 6131
run_set vid_campaign_dvfs_short 40 5 60 6133
echo "CAMPAIGN_DVFS_NOV_DONE ($(ls $H/vid_campaign_dvfs_heat/a2_*__r?.json 2>/dev/null | wc -l) heat, $(ls $H/vid_campaign_dvfs_short/a2_*__r?.json 2>/dev/null | wc -l) short)"
