#!/bin/bash
# mesh_health.sh - read-only health check of the five-board AegisSwarm mesh (14 Nov 2026; plan item A6). Changes nothing.
# For each board: hostname and bat0 address as in mesh_hosts.sh, batman-adv neighbours (expect the other 4 boards),
# no leftover temporary rule (nft table aegis_mh, a tc qdisc on bat0 other than the default), no stray experiment
# process, temperature and throttling, free disk, clock offset against the laptop. Prints one line per board and
# HEALTH_OK or HEALTH_FAIL. The boards have no time source on the mesh (14 Nov: pi-sender -25 min, Nano1 +36 s); every
# latency is measured on one board's clock, so an offset only matters when logs of two boards are aligned: it is
# printed (save this output with the campaign) and never corrected on the boards. Passwords: env PI2_PW PI3_PW NANO_PW N2_PW.
D=$(cd "$(dirname "$0")" && pwd); . $D/mesh_hosts.sh
fail=0
# HEALTH_OPTIONAL="camera2 ...": boards that may be absent (reported, not a failure; the others then expect one
# neighbour fewer per absent board). Added 14 Nov 2026 22:10 when pi-receiver dropped off the mesh during the session.
OPT=" ${HEALTH_OPTIONAL:-} "; NEXP=4
for b in $HEALTH_OPTIONAL; do NEXP=$((NEXP-1)); done
check() {   # check TARGET HOSTNAME IP PWVAR KIND
  local t=$1 hn=$2 ip=$3 pw=${!4} kind=$5 S out
  S="printf '%s\n' '$pw' | sudo -S -p ''"
  out=$($D/mesh_ssh.sh $t "
    echo host=\$(hostname)
    echo ip=\$(ip -4 -br addr show bat0 | awk '{print \$3}')
    echo neigh=\$($S /usr/sbin/batctl n -H 2>/dev/null | awk '{print \$2}' | sort -u | wc -l)
    echo nft=\$($S /usr/sbin/nft list tables 2>/dev/null | grep -c aegis_mh)
    echo tc=\$(/usr/sbin/tc qdisc show dev bat0 | grep -cvE 'noqueue|pfifo_fast|fq_codel|mq ')
    echo procs=\$(pgrep -fc '[a]daptive2.py|[e]dge_node.py|[a]daptive.py worker|[l]inklog.sh|[s]plit_live.py' )
    echo prof=\$(pgrep -fc '[h]eat_run|[t]hermal_steady.py|[e]nergy_profile.py' )
    echo disk=\$(df -BG --output=avail ~ | tail -1 | tr -dc 0-9)G
    echo clock=\$(date +%s.%N)
    if [ $kind = pi ]; then
      echo temp=\$(vcgencmd measure_temp | tr -dc '0-9.')
      echo throttled=\$(vcgencmd get_throttled | cut -d= -f2)
    else
      echo temp=\$(awk '{printf \"%.1f\", \$1/1000}' /sys/devices/virtual/thermal/thermal_zone0/temp)
      echo mode=\$($S nvpmodel -q 2>/dev/null | head -1 | sed 's/NV Power Mode: //')
    fi" 2>/dev/null)
  local now=$(date +%s.%N)
  if [ -z "$out" ]; then
    if [[ "$OPT" == *" $t "* ]]; then echo "$t: UNREACHABLE (optional: not a failure)"; else echo "$t: UNREACHABLE"; fail=1; fi
    return
  fi
  eval "$(echo "$out" | grep -E '^[a-z]+=' | sed 's/^/local /')"
  local off=$(python3 -c "print(f'{($clock)-($now):+.2f}')" 2>/dev/null)
  local bad=""
  [ "$host" = "$hn" ] || bad="$bad host($host)"
  [ "$ip" = "$3/24" ] || bad="$bad ip($ip)"
  [ "$neigh" -ge $NEXP ] || bad="$bad neighbours($neigh)"
  [ "$nft" = 0 ] || bad="$bad leftover-nft"
  [ "$tc" = 0 ] || bad="$bad leftover-tc"
  [ "$procs" = 0 ] || bad="$bad stray-processes($procs)"
  # profiling (thermal_steady, energy_profile, heat_run) loads and heats a board: not allowed on the campaign's camera
  # and Jetson; on pi-receiver / Nano2 it is reported only (14 Nov: S3 profiles there during the campaigns)
  local info=""
  if [ "$prof" != 0 ]; then case $t in camera|jetson) bad="$bad profiling-running($prof)";; *) info=" profiling-running";; esac; fi
  [ ${disk%G} -ge 3 ] || bad="$bad low-disk($disk)"
  # vcgencmd get_throttled: bit 0 / 16 = under-voltage now / since boot (a power-supply fault: FAIL); bits 1-3 and
  # 17-19 = frequency capped / throttled / soft temperature limit now / since boot: heat, which some strategies are
  # expected to cause (P2.3), so reported, not a failure (fixed 14 Nov 2026 before the first between-campaign check)
  [ $kind = pi ] && [ $(( throttled & 0x10001 )) != 0 ] && bad="$bad under-voltage($throttled)"
  local warn=""; python3 -c "import sys; sys.exit(abs($off) > 2.0)" || warn=" (clock offset: logged, not corrected)"
  echo "$t $host $ip neigh=$neigh temp=${temp}C ${throttled:+throttled=$throttled }${mode:+mode=$mode }disk=$disk clock=${off}s$warn$info${bad:+ FAIL:$bad}"
  [ -n "$bad" ] && fail=1
}
check sender  pi-sender   $SENDER_IP PI3_PW  pi
check camera  pi-relayyy  $CAM_IP    PI2_PW  pi
check camera2 pi-receiver $CAM2_IP   PI2_PW  pi
check jetson  nano        $JET_IP    NANO_PW jetson
check jetson2 nano2       $JET2_IP   N2_PW   jetson
[ $fail = 0 ] && echo HEALTH_OK || echo HEALTH_FAIL
