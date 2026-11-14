#!/bin/bash
# mesh_ssh.sh sender|camera|camera2|jetson|jetson2 "cmd" - run a command on a mesh node. The laptop reaches the mesh
# only through pi-sender (ground radio, cable 10.230.3.10). Board map: mesh_hosts.sh (verified 14 Nov 2026).
D=$(cd "$(dirname "$0")" && pwd)
. $D/mesh_hosts.sh
mesh_target "$1" || exit 2
shift
SSH_ASKPASS=$D/mesh_askpass.sh SSH_ASKPASS_REQUIRE=force DISPLAY=:0 setsid -w ssh -o StrictHostKeyChecking=yes \
  -o ConnectTimeout=15 -o PreferredAuthentications=publickey,password -o ServerAliveInterval=30 $J $H "$@" < /dev/null
