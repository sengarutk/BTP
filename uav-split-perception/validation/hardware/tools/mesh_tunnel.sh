#!/bin/bash
# mesh_tunnel.sh: the laptop's way into the mesh without changing it - SSH port forwards through pi-sender:
#   localhost:48101 -> camera 10.1.0.12:48101 (v4.1's direct laptop path; the laptop worker connects here)
#   localhost:48104 -> jetson 10.1.0.13:48104 (the hierarchical edge node's ground link)
# Traffic still crosses the mesh to pi-sender and then the cable. Runs until killed; restarts itself if dropped.
D=$(cd "$(dirname "$0")" && pwd)
while true; do
  SSH_ASKPASS=$D/mesh_askpass.sh SSH_ASKPASS_REQUIRE=force DISPLAY=:0 setsid -w ssh -N -o StrictHostKeyChecking=yes \
    -o ServerAliveInterval=10 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes \
    -L 48101:10.1.0.12:48101 -L 48104:10.1.0.13:48104 dubey@10.230.3.10 < /dev/null
  sleep 3
done
