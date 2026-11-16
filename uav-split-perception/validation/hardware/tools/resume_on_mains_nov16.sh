#!/bin/bash
# resume_on_mains_nov16.sh (16 Nov 2026): after the 04:40 charger drop. Waits until the laptop has been on mains for 2 min,
# then relaunches the Phase 4 session (board_session_nov16a2: final_nov resumes its 5 missing runs, then heat_nov, the
# 3 x 24-min runs of v41final) and the DVFS waiter following it (chain_after_nov16a.sh WAIT_SESSION=board_session_nov16a2).
# Both are started from Windows (survive chat restarts). Needs PI2_PW PI3_PW NANO_PW N2_PW in the environment.
H=~/BTP/uav-split-perception/experiments/results/hardware; T=~/BTP/uav-split-perception/validation/hardware/tools
ok=0
while [ $ok -lt 4 ]; do        # 4 consecutive checks 30 s apart on mains
  s=$(cd /mnt/c && timeout 30 /mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile -Command "(Get-CimInstance Win32_Battery).BatteryStatus" 2>/dev/null | tr -d '\r')
  [ "$s" = 2 ] && ok=$((ok+1)) || ok=0
  sleep 30
done
echo "$(TZ=Asia/Kolkata date +%T) on mains for 2 min: resuming"
launch() {   # $1 WSLENV list, $2 command. WSLENV must be exported HERE too, or the variables never leave WSL
  export WSLENV=$1                # (16 Nov 06:04: without it the session started with its defaults and no passwords)
  cd /mnt/c && /mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile -Command "\$env:WSLENV='$1'; Start-Process -WindowStyle Hidden wsl.exe -ArgumentList '-d Ubuntu --exec /bin/bash -c \"$2\"'"
}
export CAMPAIGNS='final_nov heat_nov' SESSION=board_session_nov16a2 HEAT_OUT=vid_campaign_heat_final HEAT_STRATS=v41final HEAT_REPS=3
launch PI2_PW:PI3_PW:NANO_PW:N2_PW:CAMPAIGNS:SESSION:HEAT_OUT:HEAT_STRATS:HEAT_REPS "$T/session_nov14.sh"
sleep 60; tail -3 $H/board_session_nov16a2/session.log
export WAIT_SESSION=board_session_nov16a2
mkdir -p $H/board_session_nov16a2
launch PI2_PW:PI3_PW:NANO_PW:N2_PW:WAIT_SESSION "$T/chain_after_nov16a.sh > $H/board_session_nov16a2/chain_after.log 2>&1"
sleep 5; echo "waiter: $(ps -eo pid,args | awk '$2=="/bin/bash" && $3 ~ /chain_after_nov16a\.sh$/ {print $1}')"
