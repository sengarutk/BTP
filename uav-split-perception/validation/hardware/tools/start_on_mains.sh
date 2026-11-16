#!/bin/bash
# start_on_mains.sh (16 Nov 2026): wait until the laptop has been on mains for 2 min (4 checks, 30 s apart), then launch
# session_nov14.sh from Windows with the variables named in $START_VARS (exported here AND passed via WSLENV: see the
# 16 Nov 06:04 lesson). Needs PI2_PW PI3_PW NANO_PW N2_PW and the START_VARS variables in the environment.
PS=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
ok=0
while [ $ok -lt 4 ]; do
  s=$(cd /mnt/c && timeout 30 $PS -NoProfile -Command "(Get-CimInstance Win32_Battery).BatteryStatus" 2>/dev/null | tr -d '\r')
  [ "$s" = 2 ] && ok=$((ok+1)) || ok=0
  sleep 30
done
echo "$(TZ=Asia/Kolkata date +%T) on mains for 2 min: launching ($START_VARS)"
export WSLENV=PI2_PW:PI3_PW:NANO_PW:N2_PW:$START_VARS
cd /mnt/c && $PS -NoProfile -Command "\$env:WSLENV='$WSLENV'; Start-Process -WindowStyle Hidden wsl.exe -ArgumentList '-d Ubuntu --exec /home/sengar/BTP/uav-split-perception/validation/hardware/tools/session_nov14.sh'"
sleep 60; tail -3 ~/BTP/uav-split-perception/experiments/results/hardware/$SESSION/session.log
