#!/bin/bash
# Heat run (Phase G): hold every Pi 5 thermal load level for LEVEL_S seconds (default 1440 s = 24 min)
# and log power / SoC temperature / ARM clock at 10 Hz (thermal_steady.py on the Pi). The steady value
# per level is the mean over its last 60 s. Result fetched to experiments/results/hardware/energy/
# thermal_steady_pi_24min.json (the Pi-side file is thermal_steady_pi.json and gets rewritten level by
# level, so it is fetched only after the run finishes). Must NOT run while a campaign is using the Pi.
# Passwords: env PI_PW.
D=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$D/../../.." && pwd)
R=$REPO/experiments/results/hardware/energy; mkdir -p $R
LEVEL_S=${LEVEL_S:-1440}
PY=/home/dubey/btp_env/bin/python
until ping -c1 -W2 192.168.0.248 >/dev/null 2>&1 && $D/rsh.sh pi true 2>/dev/null; do
  echo "$(date +%T) pi unreachable, waiting"; sleep 60; done
$D/rsh.sh pi "cd ~/hwbench; rm -f results/thermal_steady_pi.json; nohup $PY -W ignore thermal_steady.py --level-s $LEVEL_S > results/heat_run.log 2>&1 & echo heat_up"
echo "$(date +%T) heat run started: levels held ${LEVEL_S}s each (idle, forecaster, encode, n320 at duty 0.15/0.3/0.5/1.0)"
while :; do
  sleep 60
  until ping -c1 -W2 192.168.0.248 >/dev/null 2>&1; do echo "$(date +%T) pi unreachable, waiting"; sleep 60; done
  if ! $D/rsh.sh pi "pgrep -f 'thermal_[s]teady.py' >/dev/null" 2>/dev/null; then
    break
  fi
  echo "$(date +%T) heat run still running ($($D/rsh.sh pi "cd ~/hwbench/results && python3 -c \"import json; print(len(json.load(open('thermal_steady_pi.json'))['levels']))\" 2>/dev/null || echo 0" 2>/dev/null) levels done)"
done
$D/rsh.sh pi "tail -5 ~/hwbench/results/heat_run.log"
$D/rcp.sh pi REMOTE:hwbench/results/thermal_steady_pi.json $R/thermal_steady_pi_24min.json && echo HEAT_RUN_DONE
