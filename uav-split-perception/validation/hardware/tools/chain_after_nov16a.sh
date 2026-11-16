#!/bin/bash
# chain_after_nov16a.sh (16 Nov 2026): waits for session nov16a (Phase 4) to end with SESSION_DONE and the laptop on mains, pushes
# the DVFS controller and profile to the camera, smoke-tests v41dvfs (5-s phases), and only if that passes launches
# session nov16b (campaign_dvfs_nov.sh). Launched from Windows so a chat restart cannot kill it.
# needs PI2_PW PI3_PW NANO_PW N2_PW in the environment (never written here)
H=~/BTP/uav-split-perception/experiments/results/hardware; T=~/BTP/uav-split-perception/validation/hardware/tools
WS=${WAIT_SESSION:-board_session_nov16a}   # the Phase 4 session to wait for (nov16a2 after the 04:40 charger drop)
SP=$H/$WS     # smoke-test output
until [ -f $H/$WS/session.log ] && grep -q "session start (pid" $H/$WS/session.log; do sleep 30; done
SPID=$(grep -o "session start (pid [0-9]*" $H/$WS/session.log | tail -1 | grep -o "[0-9]*$")
while kill -0 $SPID 2>/dev/null; do sleep 30; done
echo "$(TZ=Asia/Kolkata date +%T) session $WS ended: $(tail -1 $H/$WS/session.log)"
grep -q SESSION_DONE $H/$WS/session.log || { echo "$WS did not end with SESSION_DONE: DVFS not started"; exit 1; }
s=$(cd /mnt/c && timeout 30 /mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile -Command "(Get-CimInstance Win32_Battery).BatteryStatus" | tr -d '\r')
[ "$s" != 2 ] && { echo "laptop on battery: DVFS not started"; exit 1; }
cd $T && TARGETS=camera timeout 600 ./push_code_mesh.sh 2>&1 | grep -E "MD5|rror"
./mesh_scp.sh camera $H/energy/dvfs_profile_pi-receiver_20261116.json REMOTE:hwbench/dvfs_profile.json || { echo "profile copy failed"; exit 1; }
rm -rf $SP/smoke_dvfs; timeout 400 ./arun_mesh.sh smoke_dvfs v41dvfs mission 5 1 $SP/smoke_dvfs 2>&1 | grep -E '^\{|NO RESULT|abandoned' | cut -c1-200
python3 -c "
import json,collections,sys
d=json.load(open('$SP/smoke_dvfs/a2_smoke_dvfs.json')); dv=d.get('dvfs'); print('dvfs', dv); print('onboard', collections.Counter(f.get('variant') for f in d['frames'] if f.get('server')=='onboard'))
sys.exit(0 if dv and dv.get('default_mhz') else 1)" || { echo "SMOKE FAILED: DVFS not started"; exit 1; }
cap=$(./mesh_ssh.sh camera "cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq" | tr '\n' ' '); echo "cap after smoke: $cap"
set -- $cap; [ "$1" = "$2" ] || { echo "CLOCK NOT RESTORED after smoke: DVFS not started"; exit 1; }
export CAMPAIGNS=dvfs_nov SESSION=board_session_nov16b
export WSLENV=PI2_PW:PI3_PW:NANO_PW:N2_PW:CAMPAIGNS:SESSION
cd /mnt/c && /mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile -Command "\$env:WSLENV='$WSLENV'; Start-Process -WindowStyle Hidden wsl.exe -ArgumentList '-d Ubuntu --exec /home/sengar/BTP/uav-split-perception/validation/hardware/tools/session_nov14.sh'"
sleep 120; tail -4 $H/board_session_nov16b/session.log; tail -3 $H/board_session_nov16b/campaign_dvfs_nov.log
