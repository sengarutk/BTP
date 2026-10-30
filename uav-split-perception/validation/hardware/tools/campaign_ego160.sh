#!/bin/bash
# campaign_ego160.sh - the cheaper camera-motion step on the camera Pi (prepared 29 Oct 2026; brief 19.9): first the
#   step itself is timed on the Pi at 320 and 160 px (egomotion_bench.py) -> ego_step_pi_160.json; then v41 with the
#   live forecaster at 320 px (as before) and at 160 px (EGO_W=160), static_good and mesh_mission x 3 reps = 12 runs,
#   order shuffled, resumable. Compare onboard_ms, the forecaster's own timings (_livefc) and sAP between widths.
#   Results: vid_campaign_ego160/.
# First: push_code_mesh.sh, mesh_tunnel.sh, the keep-awake ping. Passwords: env PI2_PW PI3_PW NANO_PW.
D=$(cd "$(dirname "$0")" && pwd); H=$(cd $D/../../.. && pwd)/experiments/results/hardware
R=$H/vid_campaign_ego160; PS=40; mkdir -p $R
if [ ! -f $R/ego_step_pi_160.json ]; then
  $D/mesh_ssh.sh camera "cd ~/hwbench && /home/sengar/btp_env/bin/python egomotion_bench.py visdrone_vid_640 --widths 320 160 --frames 300 --reps 3 --out results/ego_step_pi_160.json > /dev/null && cat results/ego_step_pi_160.json" > $R/ego_step_pi_160.json \
    || { echo "step timing failed (run push_code_mesh.sh first?)"; rm -f $R/ego_step_pi_160.json; exit 1; }
  echo "step on the Pi: $(python3 -c "import json;d=json.load(open('$R/ego_step_pi_160.json'))['widths'];print({w:round(v['ms_per_frame_median'],2) for w,v in d.items()},'ms/frame')")"
fi
jobs() {
  for rep in 1 2 3; do for sc in static_good mesh_mission; do
    for w in $(python3 -c "import random;p=['320','160'];random.Random($rep*100+len('$sc')).shuffle(p);print(' '.join(p))"); do echo "$rep $sc $w"; done
  done; done
}
for pass in 1 2; do
  jobs | while read rep sc w; do
    L=${sc}__v41w${w}__r$rep
    [ -f $R/a2_$L.json ] && continue
    until $D/mesh_ssh.sh camera true 2>/dev/null && $D/mesh_ssh.sh jetson true 2>/dev/null && ss -ltn | grep -q 127.0.0.1:48104; do
      echo "$(date +%T) mesh or tunnel unreachable, waiting"; sleep 60; done
    echo "=== $(date +%T) pass $pass $L"
    if [ $w = 160 ]; then E=160; else E=; fi
    EGO_W=$E $D/arun_mesh.sh $L v41 $sc $PS $rep $R 2>&1 | grep -E '^\{|NO RESULT|abandoned|retry|direct route|copy failed|laptop link' | cut -c1-220
  done
done
echo "CAMPAIGN_EGO160_DONE ($(ls $R/a2_*__r?.json 2>/dev/null | wc -l) runs)"
