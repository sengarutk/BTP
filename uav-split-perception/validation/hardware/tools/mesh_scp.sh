#!/bin/bash
# mesh_scp.sh sender|camera|camera2|jetson|jetson2 SRC DST  (REMOTE: marks the remote side, as rcp.sh)
# Board map: mesh_hosts.sh (verified 14 Nov 2026); sender is the ground radio, over the cable.
D=$(cd "$(dirname "$0")" && pwd)
. $D/mesh_hosts.sh
mesh_target "$1" || exit 2
S=${2/REMOTE:/$H:}; T=${3/REMOTE:/$H:}
SSH_ASKPASS=$D/mesh_askpass.sh SSH_ASKPASS_REQUIRE=force DISPLAY=:0 setsid -w scp -q -o StrictHostKeyChecking=yes \
  -o ConnectTimeout=15 $J "$S" "$T" < /dev/null
