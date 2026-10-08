#!/bin/bash
# arun2.sh LABEL MODE POLICY SCENARIO PHASE_S SEED OUTDIR [extra camera args...]
# Two camera drones sharing the ground station:
#   Pi camera     adaptive2.py, paths laptop + jetson, CPU onboard
#   Jetson camera adaptive2.py, path laptop, GPU onboard (FP16); the Jetson also serves the Pi's frames
#   laptop        one worker per camera (one GPU, one Wi-Fi link) and the swarm coordinator (MODE admission|none)
# Both cameras run the same POLICY, SCENARIO and SEED (netem on their own interface) and stream the same video.
# Results in OUTDIR: a2_<LABEL>__pi.json, a2_<LABEL>__jetson.json (+ _dets.npz, _livefc.npz), coord_<LABEL>.json.
# Passwords: env PI_PW / NANO_PW.
D=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$D/../../.." && pwd)
L=$1; MODE=$2; POL=$3; SC=$4; PS=${5:-20}; SEED=${6:-1}; R=$7; shift 7; EXTRA="$*"
mkdir -p $R; R=$(cd $R && pwd)
PI=192.168.0.248; NANO=192.168.0.188; CP=48110
TOT=$((PS*6+60))
JPY=/home/nano/hwbench_env/bin/python
# stale processes from earlier runs: Jetson worker and camera, laptop workers and coordinator, Pi camera
$D/rsh.sh nano 'P=$(pgrep -f "^python -W ignore adaptive.py worker"); [ -n "$P" ] && kill $P; true'
$D/rsh.sh nano "P=\$(pgrep -f '^$JPY -W ignore adaptive2.py'); [ -n \"\$P\" ] && printf '%s\n' '$NANO_PW' | sudo -S -p '' kill \$P; true"
for P in $(ps -eo pid,args | awk '/^ *[0-9]+ python -W ignore (adaptive.py worker|coordinator.py)/{print $1}'); do kill $P; done
$D/rsh.sh pi "P=\$(pgrep -f '^/home/dubey/btp_env/bin/python -W ignore adaptive2.py'); [ -n \"\$P\" ] && printf '%s\n' '$PI_PW' | sudo -S -p '' kill \$P; true"
$D/rsh.sh nano "printf '%s\n' '$NANO_PW' | sudo -S -p '' jetson_clocks"
# cameras (root, for tc)
$D/rsh.sh pi "cd ~/hwbench; rm -f results/a2_${L}__pi*; printf '%s\n' '$PI_PW' | sudo -S -p '' nohup /home/dubey/btp_env/bin/python -W ignore adaptive2.py --policy '$POL' --scenario $SC --phase-s $PS --seed $SEED --coord-port $CP $EXTRA --out results/a2_${L}__pi.json > results/a2_${L}__pi.log 2>&1 & echo pi_cam_up"
$D/rsh.sh nano "cd ~/hwbench; rm -f results/a2_${L}__jetson*; printf '%s\n' '$NANO_PW' | sudo -S -p '' nohup $JPY -W ignore adaptive2.py --policy '$POL' --scenario $SC --phase-s $PS --seed $SEED --paths laptop --onboard-device cuda --wlan wlP1p1s0 --coord-port $CP $EXTRA --out results/a2_${L}__jetson.json > results/a2_${L}__jetson.log 2>&1 & echo jet_cam_up"
sleep 25
# Jetson serves the Pi's edge path
$D/rsh.sh nano "cd ~/hwbench; nohup bash -c 'source ~/hwbench_env/bin/activate; python -W ignore adaptive.py worker --camera $PI:48102 --device cuda --half --weights yolov8s.pt --label jetson' > results/a2w_${L}.log 2>&1 & echo jet_worker_up"
# laptop: worker for the Jetson camera and the coordinator in the background, worker for the Pi in the foreground
cd $REPO/validation/hardware; source /home/sengar/BTP/venv/bin/activate
timeout $((TOT+300)) python -W ignore adaptive.py worker --camera $NANO:48101 --device cuda --half --weights ../../yolov8s.pt,../../weights/yolov8m.pt --label laptop_j > $R/a2w_${L}_laptop_jetson.log 2>&1 &
timeout $((TOT+300)) python -W ignore coordinator.py --cameras $PI:$CP,$NANO:$CP --mode $MODE --duration $((TOT+60)) --out $R/coord_${L}.json > $R/coord_${L}.log 2>&1 &
timeout $((TOT+300)) python -W ignore adaptive.py worker --camera $PI:48101 --device cuda --half --weights ../../yolov8s.pt,../../weights/yolov8m.pt --label laptop > $R/a2w_${L}_laptop_pi.log 2>&1
for i in $(seq 90); do $D/rsh.sh pi "test -f ~/hwbench/results/a2_${L}__pi.json" 2>/dev/null && $D/rsh.sh nano "test -f ~/hwbench/results/a2_${L}__jetson.json" 2>/dev/null && break; sleep 5; done
sleep 3
for cam in pi nano; do
  sfx=$([ $cam = pi ] && echo pi || echo jetson)
  $D/rcp.sh $cam REMOTE:hwbench/results/a2_${L}__$sfx.json $R/ && { $D/rcp.sh $cam REMOTE:hwbench/results/a2_${L}__${sfx}_dets.npz $R/ 2>/dev/null; $D/rcp.sh $cam REMOTE:hwbench/results/a2_${L}__${sfx}_livefc.npz $R/ 2>/dev/null; $D/rsh.sh $cam "tail -1 ~/hwbench/results/a2_${L}__$sfx.log"; } || $D/rsh.sh $cam "tail -20 ~/hwbench/results/a2_${L}__$sfx.log"
done
wait
$D/rsh.sh nano 'P=$(pgrep -f "^python -W ignore adaptive.py worker"); [ -n "$P" ] && kill $P; true'
