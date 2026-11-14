#!/bin/bash
# arun_two.sh LABEL STRATEGY SCENARIO PHASE_S SEED OUTDIR - one run with TWO sense drones and up to TWO edge drones
#   (plan T6 / D1; 14 Nov 2026). Cameras: camera (pi-relayyy) and camera2 (pi-receiver), each running adaptive2.py with
#   the same scenario and seed, started together. Edge drones: Nano1 serves both cameras on its jetson path (one worker
#   per camera, sharing its GPU); with j2 strategies Nano2 serves both on the jetson2 path. The laptop serves each camera
#   through its own tunnel (camera: mesh_tunnel.sh 48101; camera2: mesh_tunnel2.sh 48111).
#   STRATEGY
#     v41j1   v4.1 (energy + freshness price), paths laptop + Nano1 (the single-edge system of every earlier campaign)
#     v41j2   v4.1, paths laptop + Nano1 + Nano2, Nano2 also offering YOLOv8m (--jetson2-m)
#   Every frame's destination is in each camera's run JSON (frames[].server); both Jetsons' power (--report-power) and
#   both Pis' power, temperature and clock are logged. Results: a2_<LABEL>_c1.* (camera), a2_<LABEL>_c2.* (camera2).
# Needs mesh_tunnel.sh and mesh_tunnel2.sh running and the adaptive2.py of 14 Nov or later on both cameras.
# Passwords: env PI2_PW PI3_PW NANO_PW N2_PW.
D=$(cd "$(dirname "$0")" && pwd); HW=$(cd "$D/.." && pwd); . $D/mesh_hosts.sh
L=$1; ST=$2; SC=$3; PS=$4; SEED=$5; R=$6; mkdir -p $R; R=$(cd $R && pwd)
TOT=$((PS*6+60)); PY=/home/sengar/btp_env/bin/python
S="printf '%s\n' \"\$PW\" | sudo -S -p ''"
COMMON="--scenario $SC --phase-s $PS --seed $SEED --vid visdrone_vid_640 --conf 0.01 --live-forecast forecast_tuning_v2.json --power-log --energy-constants energy_constants.json --weight-suffix _visdrone --acc variant_accuracy_visdrone_ft.json --onboard-variants s320,s640 --wlan bat0"
X="--decay staleness_decay_forecast_v2.json --objective stream --energy-aware --power-budget 2.8 --fresh-target 0.95"
case $ST in
  v41j1) PATHS=laptop,jetson; J2=0;;
  v41j2) PATHS=laptop,jetson,jetson2; J2=1; X="$X --jetson2-m";;
  *) echo "unknown strategy $ST"; exit 2;;
esac
CAMS="camera:$CAM_IP:48101:c1 camera2:$CAM2_IP:48111:c2"
cleanup() {
  for c in camera camera2; do
    $D/mesh_ssh.sh $c "PW='$PI2_PW'; P=\$(pgrep -f '^$PY -W ignore [a]daptive2.py'); [ -n \"\$P\" ] && $S kill \$P; sleep 1; $S /usr/sbin/tc qdisc del dev bat0 root 2>/dev/null; true"
  done
  $D/mesh_ssh.sh jetson "P=\$(pgrep -f '^python -W ignore [a]daptive.py worker'); [ -n \"\$P\" ] && kill \$P; true"
  $D/mesh_ssh.sh jetson2 "P=\$(pgrep -f '^python -W ignore [a]daptive.py worker'); [ -n \"\$P\" ] && kill \$P; true"
  for P in $(ps -eo pid,args | awk '/^ *[0-9]+ python -W ignore adaptive.py worker --camera 127.0.0.1:481(01|11) .*--label two_/ {print $1}'); do kill $P; done
}
fetch() {
  for k in 1 2 3 4 5 6; do $D/mesh_scp.sh $1 REMOTE:hwbench/results/$2 $R/ 2>/dev/null && return 0; sleep 10; done
  echo "copy failed: $1 $2"; return 1
}
for p in 48101 48111; do ss -ltn | grep -q "127.0.0.1:$p" || { echo "tunnel port $p not listening: run abandoned"; echo "NO RESULT for $L"; exit 1; }; done
cleanup
$D/mesh_ssh.sh jetson "PW='$NANO_PW'; $S jetson_clocks" 2>/dev/null
[ $J2 = 1 ] && $D/mesh_ssh.sh jetson2 "PW='$N2_PW'; $S jetson_clocks" 2>/dev/null
for spec in $CAMS; do IFS=: read c ip lp tag <<< "$spec"
  $D/mesh_ssh.sh $c "cd ~/hwbench; rm -f results/a2_${L}_$tag.*; PW='$PI2_PW'; $S nohup $PY -W ignore adaptive2.py --policy A_full $COMMON $X --paths $PATHS --out results/a2_${L}_$tag.json > results/a2_${L}_$tag.log 2>&1 < /dev/null & echo ${tag}_up"
done
sleep 20
for spec in $CAMS; do IFS=: read c ip lp tag <<< "$spec"
  $D/mesh_ssh.sh jetson "cd ~/hwbench; nohup bash -c 'source ~/hwbench_env/bin/activate; python -W ignore adaptive.py worker --camera $ip:48102 --device cuda --half --weights yolov8s_visdrone.pt --label jetson_$tag --report-power jetson' > results/a2w_${L}_$tag.log 2>&1 < /dev/null & echo j1_$tag"
  [ $J2 = 1 ] && $D/mesh_ssh.sh jetson2 "cd ~/hwbench; nohup bash -c 'source ~/hwbench_env/bin/activate; python -W ignore adaptive.py worker --camera $ip:48105 --device cuda --half --weights yolov8s_visdrone.pt,yolov8m_visdrone.pt --label jetson2_$tag --report-power jetson' > results/a2w_${L}_$tag.log 2>&1 < /dev/null & echo j2_$tag"
  (cd $HW; source /home/sengar/BTP/venv/bin/activate; timeout $((TOT+300)) python -W ignore adaptive.py worker --camera 127.0.0.1:$lp --device cuda --half --weights ../../weights/yolov8s_visdrone.pt,../../weights/yolov8m_visdrone.pt --label two_laptop_$tag > $R/a2w_${L}_${tag}_laptop.log 2>&1) &
done
ok=1
for spec in $CAMS; do IFS=: read c ip lp tag <<< "$spec"
  for i in $(seq 24); do sleep 5; $D/mesh_ssh.sh $c "grep -q 'workers connected' ~/hwbench/results/a2_${L}_$tag.log" 2>/dev/null && break; done
  $D/mesh_ssh.sh $c "grep -q 'workers connected' ~/hwbench/results/a2_${L}_$tag.log" 2>/dev/null || { echo "$c never connected its workers: run abandoned"; ok=0; }
done
if [ $ok = 0 ]; then cleanup; echo "NO RESULT for $L"; exit 1; fi
sleep $((PS*6+30))
for spec in $CAMS; do IFS=: read c ip lp tag <<< "$spec"
  for i in $(seq 120); do $D/mesh_ssh.sh $c "test -f ~/hwbench/results/a2_${L}_$tag.json" 2>/dev/null && break; sleep 5; done
done
sleep 3
for spec in $CAMS; do IFS=: read c ip lp tag <<< "$spec"
  for f in a2_${L}_$tag.json a2_${L}_${tag}_dets.npz a2_${L}_${tag}_livefc.npz a2_${L}_$tag.log; do fetch $c $f; done
  fetch jetson a2w_${L}_$tag.log && mv $R/a2w_${L}_$tag.log $R/a2w_${L}_${tag}_j1.log
  [ $J2 = 1 ] && fetch jetson2 a2w_${L}_$tag.log && mv $R/a2w_${L}_$tag.log $R/a2w_${L}_${tag}_j2.log
done
cleanup
for tag in c1 c2; do [ -f $R/a2_${L}_$tag.json ] && echo "$tag $(tail -1 $R/a2_${L}_$tag.log)" || echo "NO RESULT for ${L}_$tag"; done
