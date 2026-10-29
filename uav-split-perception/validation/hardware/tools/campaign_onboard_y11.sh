#!/bin/bash
# campaign_onboard_y11.sh BOARD "MODELS"  - YOLO11 (VisDrone weights) onboard on one Pi of the mesh, as Part 17 did
# for YOLOv8s/m/l: per model 2 short runs started hot (back to back), 2 short runs started cool, 1 long (24-min) run
# started cool. Short = 6 x 40 s, long = 6 x 240 s. Cool start: camera (pi2) < 55 C, sender (pi3) < 61 C, as in Part 17.
# Results: experiments/results/hardware/vid_campaign_onboard{,_cool,_long}_vd_y11_{pi2,pi3}/  (resumable)
# usage: PI2_PW=.. PI3_PW=.. campaign_onboard_y11.sh camera "n640y11 s640y11"
D=$(cd "$(dirname "$0")" && pwd); H=$(cd $D/../../.. && pwd)/experiments/results/hardware
B=$1; MODELS=$2
case $B in camera) P=pi2; C=55;; sender) P=pi3; C=61;; *) exit 2;; esac
run() {   # run OUTDIR LABEL VAR PS SEED [COOL]
  [ -f $1/a2_$2.json ] && return 0
  echo "=== $(date +%T) $B $2"
  $D/arun_onboard_mesh.sh $B $2 $3 $4 $5 $1 $6 2>&1 | grep -E '^\{|NO RESULT|pre-cool' | cut -c1-220
}
for v in $MODELS; do
  n=onboard_${v%640y11}640_vd_y11
  for r in 1 2; do run $H/vid_campaign_onboard_vd_y11_$P static_good__${n}__r$r $v 40 $r; done
  for r in 1 2; do run $H/vid_campaign_onboard_cool_vd_y11_$P static_good__${n}__r$r $v 40 $r $C; done
  run $H/vid_campaign_onboard_long_vd_y11_$P static_good__${n}__r1 $v 240 1 $C
done
echo "CAMPAIGN_ONBOARD_Y11_DONE $B"
