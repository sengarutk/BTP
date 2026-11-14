#!/bin/bash
# mesh_tunnel2.sh: the second camera's laptop path for two-camera runs (plan T6; 14 Nov 2026), beside mesh_tunnel.sh
# (which it does not touch): localhost:48111 -> camera2 (pi-receiver) 48101. Runs until killed; restarts if dropped.
D=$(cd "$(dirname "$0")" && pwd)
. $D/mesh_hosts.sh
while true; do
  SSH_ASKPASS=$D/mesh_askpass.sh SSH_ASKPASS_REQUIRE=force DISPLAY=:0 setsid -w ssh -N -o StrictHostKeyChecking=yes \
    -o ServerAliveInterval=10 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes \
    -L 48111:$CAM2_IP:48101 dubey@$SENDER_CABLE < /dev/null
  sleep 3
done
