#!/bin/bash
# arun.sh LABEL POLICY SCENARIO PHASE_S SEED OUTDIR [extra camera args...]
# One live run: camera = adaptive2.py on the Pi (root, for tc), workers on the Jetson and the laptop.
# The Jetson worker reports its measured board power (INA3221) in every response header (--report-power
# jetson), so v4.2 can price edge-drone energy live; JLOG=1 additionally runs power_logger.py on it.
# Any worker or camera left from an earlier run is killed first. Passwords: env PI_PW / NANO_PW.
D=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$D/../../.." && pwd)
L=$1; POL=$2; SC=$3; PS=${4:-20}; SEED=${5:-1}; R=$6; shift 6; EXTRA="$*"
mkdir -p $R; R=$(cd $R && pwd)
NPH=6; [ "$SC" = random ] && NPH=6
TOT=$((PS*NPH+60))
$D/rsh.sh nano 'P=$(pgrep -f "^python -W ignore adaptive.py worker"); [ -n "$P" ] && kill $P; true'
# Jetson clocks locked at the 15 W-mode maximum for every run (a reboot clears jetson_clocks)
$D/rsh.sh nano "printf '%s\n' '$NANO_PW' | sudo -S -p '' jetson_clocks"
for P in $(ps -eo pid,args | awk '/^ *[0-9]+ python -W ignore adaptive.py worker/{print $1}'); do kill $P; done
$D/rsh.sh pi "P=\$(pgrep -f '^/home/dubey/btp_env/bin/python -W ignore adaptive2.py'); [ -n \"\$P\" ] && printf '%s\n' '$PI_PW' | sudo -S -p '' kill \$P; true"
$D/rsh.sh pi "cd ~/hwbench; rm -f results/a2_$L.json results/a2_${L}_dets.npz results/a2_${L}_livefc.npz; printf '%s\n' '$PI_PW' | sudo -S -p '' nohup /home/dubey/btp_env/bin/python -W ignore adaptive2.py --policy '$POL' --scenario $SC --phase-s $PS --seed $SEED $EXTRA --out results/a2_$L.json > results/a2_$L.log 2>&1 & echo cam_up"
sleep 20
# JLOG=1: live power / temperature log of the Jetson (edge drone) for the whole run
[ -n "$JLOG" ] && $D/rsh.sh nano "cd ~/hwbench; rm -f results/pw_$L.json; nohup bash -c 'source ~/hwbench_env/bin/activate; python -W ignore power_logger.py --device jetson --duration $((TOT+20)) --out results/pw_$L.json' > /dev/null 2>&1 & echo jlog_up"
$D/rsh.sh nano "cd ~/hwbench; nohup bash -c 'source ~/hwbench_env/bin/activate; python -W ignore adaptive.py worker --camera 192.168.0.248:48102 --device cuda --half --weights yolov8s.pt --label jetson --report-power jetson' > results/a2w_$L.log 2>&1 & echo jet_up"
(cd $REPO/validation/hardware; source /home/sengar/BTP/venv/bin/activate; timeout $((TOT+300)) python -W ignore adaptive.py worker --camera 192.168.0.248:48101 --device cuda --half --weights ../../yolov8s.pt,../../weights/yolov8m.pt --label laptop > $R/a2w_${L}_laptop.log 2>&1)
for i in $(seq 90); do $D/rsh.sh pi "test -f ~/hwbench/results/a2_$L.json" 2>/dev/null && break; sleep 5; done
$D/rcp.sh pi REMOTE:hwbench/results/a2_$L.json $R/ && { $D/rcp.sh pi REMOTE:hwbench/results/a2_${L}_dets.npz $R/ 2>/dev/null; $D/rcp.sh pi REMOTE:hwbench/results/a2_${L}_livefc.npz $R/ 2>/dev/null; $D/rsh.sh pi "tail -1 ~/hwbench/results/a2_$L.log"; } || $D/rsh.sh pi "tail -20 ~/hwbench/results/a2_$L.log"
$D/rsh.sh nano 'P=$(pgrep -f "^python -W ignore adaptive.py worker"); [ -n "$P" ] && kill $P; true'
if [ -n "$JLOG" ]; then   # stop the Jetson logger (it rewrites its file every 10 s) and fetch it
  $D/rsh.sh nano 'P=$(pgrep -f "^python -W ignore power_logger.py"); [ -n "$P" ] && kill $P; true'
  sleep 1; $D/rcp.sh nano REMOTE:hwbench/results/pw_$L.json $R/ 2>/dev/null
fi
