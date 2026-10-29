#!/bin/bash
# mesh_scp.sh camera|jetson|sender SRC DST  (REMOTE: marks the remote side, as rcp.sh)
D=$(cd "$(dirname "$0")" && pwd)
case $1 in camera) H=sengar@10.1.0.12; J="-J dubey@10.230.3.10";; jetson) H=nano@10.1.0.13; J="-J dubey@10.230.3.10";;
  sender) H=dubey@10.230.3.10; J=;; *) exit 2;; esac   # sender: the ground radio, over the cable
S=${2/REMOTE:/$H:}; T=${3/REMOTE:/$H:}
SSH_ASKPASS=$D/mesh_askpass.sh SSH_ASKPASS_REQUIRE=force DISPLAY=:0 setsid -w scp -q -o StrictHostKeyChecking=yes \
  -o ConnectTimeout=15 $J "$S" "$T" < /dev/null
