#!/bin/bash
# arun_b.sh LABEL POLICY SCENARIO PHASE_S SEED OUTDIR [extra camera args...]
# Task B (21 Oct 2026): arun.sh with the VisDrone fine-tuned weights on every worker and the relay path.
#   laptop worker  -> Pi:48101  yolov8s_visdrone + yolov8m_visdrone
#   Jetson worker  -> Pi:48102  yolov8s_visdrone
#   RELAY=1: relay.py on the Jetson (-> Pi:48103, listening on 48104) + a second laptop worker -> Jetson:48104
#            (the camera must then be started with --paths laptop,jetson,relay)
# The camera arguments (--weight-suffix _visdrone --acc variant_accuracy_visdrone_ft.json ...) come from the caller.
# One live run: camera = adaptive2.py on the Pi (root, for tc), workers on the Jetson and the laptop.
# The Jetson worker reports its measured board power (INA3221) in every response header (--report-power
# jetson), so v4.2 can price edge-drone energy live; JLOG=1 additionally runs power_logger.py on it.
# Any worker or camera left from an earlier run is killed first. Passwords: env PI_PW / NANO_PW.
D=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$D/../../.." && pwd)
# PI_TARGET=pi2 / pi3: second Pi 5 (sengar@192.168.0.129, PI2_PW) / third (dubey@192.168.0.247, PI3_PW); default: first (dubey@192.168.0.248, PI_PW)
if [ "${PI_TARGET:-pi}" = pi2 ]; then PIH=pi2; PI_IP=192.168.0.129; PIPY=/home/sengar/btp_env/bin/python; PIPW=$PI2_PW
elif [ "${PI_TARGET:-pi}" = pi3 ]; then PIH=pi3; PI_IP=192.168.0.247; PIPY=/home/dubey/btp_env/bin/python; PIPW=$PI3_PW
else PIH=pi; PI_IP=192.168.0.248; PIPY=/home/dubey/btp_env/bin/python; PIPW=$PI_PW; fi
# PI_ONLY=1: runs that need only the Pi (onboard models): every Jetson step is skipped, so the Jetson may be off
nano_rsh() { [ -n "$PI_ONLY" ] && return 0; $D/rsh.sh nano "$@"; }
nano_rcp() { [ -n "$PI_ONLY" ] && return 0; $D/rcp.sh nano "$@"; }
L=$1; POL=$2; SC=$3; PS=${4:-20}; SEED=${5:-1}; R=$6; shift 6; EXTRA="$*"
mkdir -p $R; R=$(cd $R && pwd)
NPH=6; [ "$SC" = random ] && NPH=6
TOT=$((PS*NPH+60))
NANO_IP=${NANO_IP:-192.168.0.188}
nano_rsh 'P=$(pgrep -f "^python -W ignore adaptive.py worker"); [ -n "$P" ] && kill $P; P=$(pgrep -f "^python -W ignore relay.py"); [ -n "$P" ] && kill $P; true'
# Jetson clocks locked at the 15 W-mode maximum for every run (a reboot clears jetson_clocks)
nano_rsh "printf '%s\n' '$NANO_PW' | sudo -S -p '' jetson_clocks"
# Wi-Fi power saving off on both boards for every run (it adds latency spikes; a reboot or a network-manager
# reconnect turns it back on - found on the Jetson on 12 Oct)
nano_rsh "printf '%s\n' '$NANO_PW' | sudo -S -p '' /usr/sbin/iw dev wlP1p1s0 set power_save off" 2>/dev/null
$D/rsh.sh $PIH "printf '%s\n' '$PIPW' | sudo -S -p '' iw dev wlan0 set power_save off" 2>/dev/null
# PRE_COOL_C=55: wait (up to 20 min) until the Pi is below this temperature, so a run starts from a cool board
# (throttling analysis: the run then shows cool -> heating -> throttled)
if [ -n "$PRE_COOL_C" ]; then
  for i in $(seq 80); do
    T=$($D/rsh.sh $PIH "vcgencmd measure_temp" 2>/dev/null | grep -oE '[0-9]+\.[0-9]+')
    [ -n "$T" ] && awk -v t="$T" -v c="$PRE_COOL_C" 'BEGIN{exit !(t < c)}' && break
    sleep 15
  done
  echo "pre-cool: Pi at ${T} C (target < $PRE_COOL_C C)"
fi
# stale laptop workers of THIS Pi only (campaigns on several Pis may run in parallel, each with its own workers)
for P in $(ps -eo pid,args | awk -v ip="--camera $PI_IP:" -v rip="--camera $NANO_IP:48104" '/^ *[0-9]+ python -W ignore adaptive.py worker/ && (index($0, ip) || index($0, rip)) {print $1}'); do kill $P; done
$D/rsh.sh $PIH "P=\$(pgrep -f '^$PIPY -W ignore adaptive2.py'); [ -n \"\$P\" ] && printf '%s\n' '$PIPW' | sudo -S -p '' kill \$P; true"
$D/rsh.sh $PIH "cd ~/hwbench; rm -f results/a2_$L.json results/a2_${L}_dets.npz results/a2_${L}_livefc.npz; printf '%s\n' '$PIPW' | sudo -S -p '' nohup $PIPY -W ignore adaptive2.py --policy '$POL' --scenario $SC --phase-s $PS --seed $SEED $EXTRA --out results/a2_$L.json > results/a2_$L.log 2>&1 & echo cam_up"
sleep 20
# JLOG=1: live power / temperature log of the Jetson (edge drone) for the whole run
[ -n "$JLOG" ] && nano_rsh "cd ~/hwbench; rm -f results/pw_$L.json; nohup bash -c 'source ~/hwbench_env/bin/activate; python -W ignore power_logger.py --device jetson --duration $((TOT+20)) --out results/pw_$L.json' > /dev/null 2>&1 & echo jlog_up"
nano_rsh "cd ~/hwbench; nohup bash -c 'source ~/hwbench_env/bin/activate; python -W ignore adaptive.py worker --camera $PI_IP:48102 --device cuda --half --weights yolov8s_visdrone.pt --label jetson --report-power jetson' > results/a2w_$L.log 2>&1 & echo jet_up"
if [ -n "$RELAY" ]; then
  nano_rsh "cd ~/hwbench; nohup bash -c 'source ~/hwbench_env/bin/activate; python -W ignore relay.py --camera $PI_IP:48103 --listen 48104' > results/relay_$L.log 2>&1 & echo relay_up"
  (cd $REPO/validation/hardware; source /home/sengar/BTP/venv/bin/activate; exec timeout $((TOT+300)) python -W ignore adaptive.py worker --camera $NANO_IP:48104 --device cuda --half --weights ../../weights/yolov8s_visdrone.pt,../../weights/yolov8m_visdrone.pt --label relay > $R/a2w_${L}_relay.log 2>&1) &
  RW=$!
fi
(cd $REPO/validation/hardware; source /home/sengar/BTP/venv/bin/activate; timeout $((TOT+300)) python -W ignore adaptive.py worker --camera $PI_IP:48101 --device cuda --half --weights ../../weights/yolov8s_visdrone.pt,../../weights/yolov8m_visdrone.pt --label laptop > $R/a2w_${L}_laptop.log 2>&1)
# the relay worker exits on the camera's bye; if it has not 20 s after the direct worker, stop it (before the relay
# fix of 22 Oct it never saw the bye and every run waited for its timeout, ~5 min)
if [ -n "$RW" ]; then for i in $(seq 20); do kill -0 $RW 2>/dev/null || break; sleep 1; done; kill $RW 2>/dev/null; fi
wait
for i in $(seq 90); do $D/rsh.sh $PIH "test -f ~/hwbench/results/a2_$L.json" 2>/dev/null && break; sleep 5; done
$D/rcp.sh $PIH REMOTE:hwbench/results/a2_$L.json $R/ && { $D/rcp.sh $PIH REMOTE:hwbench/results/a2_${L}_dets.npz $R/ 2>/dev/null; $D/rcp.sh $PIH REMOTE:hwbench/results/a2_${L}_livefc.npz $R/ 2>/dev/null; $D/rsh.sh $PIH "tail -1 ~/hwbench/results/a2_$L.log"; } || $D/rsh.sh $PIH "tail -20 ~/hwbench/results/a2_$L.log"
nano_rsh 'P=$(pgrep -f "^python -W ignore adaptive.py worker"); [ -n "$P" ] && kill $P; true'
[ -n "$RELAY" ] && { nano_rsh 'tail -1 ~/hwbench/results/relay_'$L'.log; P=$(pgrep -f "^python -W ignore relay.py"); [ -n "$P" ] && kill $P; true'; nano_rcp REMOTE:hwbench/results/relay_$L.log $R/ 2>/dev/null; }
if [ -n "$JLOG" ]; then   # stop the Jetson logger (it rewrites its file every 10 s) and fetch it
  nano_rsh 'P=$(pgrep -f "^python -W ignore power_logger.py"); [ -n "$P" ] && kill $P; true'
  sleep 1; nano_rcp REMOTE:hwbench/results/pw_$L.json $R/ 2>/dev/null
fi
