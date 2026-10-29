#!/bin/bash
# mesh_down.sh WLAN [ETH]   (root) - leave the test mesh and return to the lab Wi-Fi (NetworkManager reconnects
# the saved TP-Link profile). ETH (pi-sender's cable) keeps its address 10.230.3.10/20 for the laptop.
WLAN=$1; ETH=${2:-}
echo "$(date +%T) mesh_down $WLAN ${ETH:-}"
rm -f /run/mesh_ok
if [ -n "$ETH" ]; then ip link set $ETH nomaster 2>/dev/null; ip link del br0 2>/dev/null; ip addr add 10.230.3.10/20 dev $ETH 2>/dev/null; fi
batctl if del $WLAN 2>/dev/null || batctl meshif bat0 interface del $WLAN 2>/dev/null
ip link del bat0 2>/dev/null
iw dev $WLAN ibss leave 2>/dev/null
ip link set $WLAN down
iw dev $WLAN set type managed
ip link set $WLAN mtu 1500
ip link set $WLAN up
nmcli dev set $WLAN managed yes
sleep 3
nmcli dev connect $WLAN || nmcli dev wifi connect TP-Link_lab_522
echo "$(date +%T) back on: $(iw dev $WLAN link | grep SSID)"
