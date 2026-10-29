#!/bin/bash
# mesh_up.sh WLAN IP/PREFIX [ETH]   (run as root, detached: systemd-run --unit=mesh-up mesh_up.sh ...)
# Puts this board on the AegisSwarm test mesh: WLAN leaves the lab Wi-Fi and joins the ad-hoc (IBSS) cell
# "aegisswarm" on 2.4 GHz channel 1 (2412 MHz, away from the lab AP on channel 7), batman-adv runs on it (bat0).
# With ETH (the ground radio, pi-sender), bat0 and ETH are bridged (br0), so the laptop on the cable is on the mesh.
# Safety: unless /run/mesh_ok exists after FALLBACK_S (default 600 s), mesh_down.sh puts the board back on the lab
# Wi-Fi, so a failed mesh never leaves a board unreachable. Create /run/mesh_ok over the mesh to keep it.
set -u
WLAN=$1; IP=$2; ETH=${3:-}; FREQ=${FREQ:-2412}; CELL=${CELL:-aegisswarm}; BSSID=${BSSID:-02:ae:91:55:00:01}
D=$(cd "$(dirname "$0")" && pwd); LOG=$D/mesh_up.log          # in ~/hwbench: survives a restart
exec >> $LOG 2>&1
echo "$(date +%T) mesh_up $WLAN $IP ${ETH:-}"
rm -f /run/mesh_ok
# safety first, independent of everything below (a hung Wi-Fi command cannot block them): back to the lab Wi-Fi after
# FALLBACK_S, restart the board after REBOOT_S. mesh_confirm.sh cancels both once the board is reachable over the mesh.
if [ -z "${NO_SAFETY:-}" ]; then
  systemd-run --unit=mesh-fallback --on-active=${FALLBACK_S:-300} --timer-property=AccuracySec=1s $D/mesh_down.sh $WLAN ${ETH:-}
  systemd-run --unit=mesh-reboot --on-active=${REBOOT_S:-480} --timer-property=AccuracySec=1s /usr/bin/systemctl reboot
fi
modprobe batman-adv
nmcli dev disconnect $WLAN 2>/dev/null          # leave the lab AP first: the driver refuses a mode change while associated
nmcli dev set $WLAN managed no
sleep 2
ip link set $WLAN down
for i in 1 2 3 4 5; do iw dev $WLAN set type ibss && break; echo "set type busy, retry $i"; sleep 2; done
ip link set $WLAN mtu 1532 2>/dev/null || echo "mtu 1532 not supported (batman-adv fragments instead)"
ip link set $WLAN up
iw dev $WLAN ibss join $CELL $FREQ HT20 fixed-freq $BSSID || { echo "HT20 join failed, retrying without"; iw dev $WLAN ibss join $CELL $FREQ fixed-freq $BSSID; }
batctl if add $WLAN 2>/dev/null || batctl meshif bat0 interface add $WLAN
ip link set bat0 up
if [ -n "$ETH" ]; then
  nmcli dev set $ETH managed no
  ip addr flush dev $ETH
  ip link add br0 type bridge 2>/dev/null
  ip link set $ETH master br0
  ip link set bat0 master br0
  ip link set br0 up
  ip addr add $IP dev br0
else
  ip addr add $IP dev bat0
fi
echo "$(date +%T) up: $(iw dev $WLAN info | grep -E 'type|channel' | tr -s '\t ' ' ')"
sleep 30
echo "$(date +%T) after 30 s: $(iw dev $WLAN link | tr -s '\t\n ' ' ')"
echo "$(date +%T) stations: $(iw dev $WLAN station dump | grep -c Station); batman neighbours: $(batctl n -H 2>/dev/null | wc -l)"
