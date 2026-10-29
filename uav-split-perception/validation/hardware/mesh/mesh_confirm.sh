#!/bin/bash
# mesh_confirm.sh (root) - the board is reachable over the mesh: cancel its fallback and restart timers
systemctl stop mesh-fallback.timer mesh-reboot.timer 2>/dev/null
touch /run/mesh_ok
echo "$(date +%T) confirmed: timers $(systemctl list-timers --all --no-legend 'mesh-*' | wc -l) left"
