#!/bin/bash
# arun_onboard_mesh.sh BOARD LABEL VARIANT PHASE_S SEED OUTDIR [PRE_COOL_C]  - one onboard-only run on a Pi of the
# AegisSwarm mesh (25 Oct 2026; YOLO11 onboard, the same design as the YOLOv8 runs of Part 17 / campaign_main.sh):
#   static_good, one model alone on the Pi (--policy fixed:onboard:VARIANT), no live forecaster (scored offline),
#   --paths laptop with a CPU-only placeholder worker (it answers probes only; the laptop GPU stays free for training)
#   BOARD camera = pi-relayyy (pi2, through the SSH tunnel localhost:48101) | sender = pi-sender (pi3, over the cable)
#   PRE_COOL_C: wait (up to 20 min) until the Pi is below this temperature before the run starts
# Passwords: env PI2_PW PI3_PW. Needs mesh_tunnel.sh for BOARD=camera.
D=$(cd "$(dirname "$0")" && pwd); HW=$(cd "$D/.." && pwd)
B=$1; L=$2; VAR=$3; PS=$4; SEED=$5; R=$6; COOL=$7; mkdir -p $R; R=$(cd $R && pwd)
case $B in camera) PW=$PI2_PW; PY=/home/sengar/btp_env/bin/python; EP=127.0.0.1:48101;;
  sender) PW=$PI3_PW; PY=/home/dubey/btp_env/bin/python; EP=10.230.3.10:48101;; *) echo "camera|sender"; exit 2;; esac
TOT=$((PS*6+60)); S="printf '%s\n' \"\$PW\" | sudo -S -p ''"
kill_cam() { $D/mesh_ssh.sh $B "PW='$PW'; P=\$(pgrep -f '^$PY -W ignore [a]daptive2.py'); [ -n \"\$P\" ] && $S kill \$P; sleep 1; $S /usr/sbin/tc qdisc del dev bat0 root 2>/dev/null; true"; }
kill_worker() { for P in $(ps -eo pid,args | awk -v ep="--camera $EP" '/^ *[0-9]+ python -W ignore adaptive.py worker/ && index($0, ep) {print $1}'); do kill $P; done; }
kill_cam; kill_worker
if [ -n "$COOL" ]; then
  for i in $(seq 80); do
    T=$($D/mesh_ssh.sh $B "vcgencmd measure_temp" 2>/dev/null | grep -oE '[0-9]+\.[0-9]+')
    [ -n "$T" ] && awk -v t="$T" -v c="$COOL" 'BEGIN{exit !(t < c)}' && break
    sleep 15
  done
  echo "pre-cool: Pi at ${T} C (target < $COOL C)"
fi
$D/mesh_ssh.sh $B "PW='$PW'; $S iw dev wlan0 set power_save off 2>/dev/null; cd ~/hwbench; rm -f results/a2_$L.*; $S nohup $PY -W ignore adaptive2.py --policy 'fixed:onboard:$VAR' --scenario static_good --phase-s $PS --seed $SEED --vid visdrone_vid_640 --conf 0.01 --power-log --energy-constants energy_constants.json --acc variant_accuracy_visdrone_ft11.json --onboard-variants $VAR --paths laptop --wlan bat0 --out results/a2_$L.json > results/a2_$L.log 2>&1 & echo cam_up"
sleep 20
(cd $HW; source /home/sengar/BTP/venv/bin/activate; timeout $((TOT+300)) python -W ignore adaptive.py worker --camera $EP --device cpu --weights ../../weights/yolov8n_visdrone.pt --label laptop > $R/a2w_${L}_laptop.log 2>&1) &
sleep $((PS*6+30))
for i in $(seq 120); do $D/mesh_ssh.sh $B "test -f ~/hwbench/results/a2_$L.json" 2>/dev/null && break
  $D/mesh_ssh.sh $B "pgrep -f '^$PY -W ignore [a]daptive2.py' >/dev/null" 2>/dev/null || { sleep 5; break; }
  sleep 5; done
sleep 3
for f in a2_$L.json a2_${L}_dets.npz a2_$L.log; do
  for k in 1 2 3 4 5 6; do $D/mesh_scp.sh $B REMOTE:hwbench/results/$f $R/ 2>/dev/null && break; sleep 10; done
done
kill_cam; kill_worker
[ -f $R/a2_$L.json ] && tail -1 $R/a2_$L.log || echo "NO RESULT for $L"
