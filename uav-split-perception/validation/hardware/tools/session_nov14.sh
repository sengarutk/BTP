#!/bin/bash
# session_nov14.sh - the prepared board session (plan items B1-B3; 14 Nov 2026): the laptop infrastructure, then
#   REPS=2 campaign_mesh4.sh (planner), campaign_energy_nov.sh (energy), campaign_relaynoise_nov.sh (noisy relay),
#   with the read-only health check before and after each. Each campaign is resumable (it skips finished runs), so
#   this script can simply be started again after an interruption. Stops (SESSION_STOPPED) if a health check fails.
# Start it outside any interactive session's process tree, e.g. from Windows:
#   wsl.exe -d Ubuntu --exec bash -c 'export PI2_PW=... PI3_PW=... NANO_PW=... N2_PW=...; exec tools/session_nov14.sh'
# Logs: experiments/results/hardware/board_session_nov14/. Passwords: env only.
D=$(cd "$(dirname "$0")" && pwd); H=$(cd $D/../../.. && pwd)/experiments/results/hardware
LOG=$H/board_session_nov14; mkdir -p $LOG
PINGLOG=$H/vid_campaign_mesh2_laptop_ping.txt
say() { echo "$(TZ=Asia/Kolkata date '+%d %b %H:%M:%S') $*" >> $LOG/session.log; }
infra() {   # tunnel, keep-awake ping (laptop Ethernet energy saving), 1-s ping log; each started only if not running
  pgrep -f "[m]esh_tunnel.sh" > /dev/null || { setsid nohup $D/mesh_tunnel.sh >> $LOG/tunnel.log 2>&1 < /dev/null & say "tunnel started"; }
  pgrep -f "[p]ing -i 0.05 10.230.3.10" > /dev/null || { setsid nohup ping -i 0.05 10.230.3.10 > /dev/null 2>&1 < /dev/null & say "keep-awake ping started"; }
  pgrep -f "[p]ing -D -O -i 1 10.230.3.10" > /dev/null || { setsid nohup ping -D -O -i 1 10.230.3.10 >> $PINGLOG 2>&1 < /dev/null & say "ping log started"; }
  for i in $(seq 30); do [ $(ss -ltn | grep -cE '127.0.0.1:4810[14]') = 2 ] && return 0; sleep 2; done
  say "tunnel ports not listening"; return 1
}
health() {
  $D/mesh_health.sh > $LOG/health_$1.txt 2>&1
  say "health $1: $(tail -1 $LOG/health_$1.txt)"
  grep -q HEALTH_OK $LOG/health_$1.txt || { cat $LOG/health_$1.txt >> $LOG/session.log; say SESSION_STOPPED; exit 1; }
}
say "session start (pid $$)"
infra || { say SESSION_STOPPED; exit 1; }
health start
for c in mesh4 energy_nov relaynoise_nov; do
  infra
  say "campaign $c start"
  if [ $c = mesh4 ]; then REPS=2 $D/campaign_mesh4.sh >> $LOG/campaign_$c.log 2>&1; else $D/campaign_$c.sh >> $LOG/campaign_$c.log 2>&1; fi
  say "campaign $c end: $(tail -1 $LOG/campaign_$c.log)"
  health after_$c
done
say SESSION_DONE
