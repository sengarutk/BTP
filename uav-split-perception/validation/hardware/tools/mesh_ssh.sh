#!/bin/bash
# mesh_ssh.sh sender|camera|jetson "cmd" - run a command on a mesh node. The laptop reaches the mesh only through
# pi-sender (ground radio, cable 10.230.3.10); camera = pi-relayyy 10.1.0.12, jetson = 10.1.0.13 (mesh of 23 Oct).
D=$(cd "$(dirname "$0")" && pwd)
case $1 in sender) H=dubey@10.230.3.10; J=;; camera) H=sengar@10.1.0.12; J="-J dubey@10.230.3.10";;
  jetson) H=nano@10.1.0.13; J="-J dubey@10.230.3.10";; *) echo "sender|camera|jetson"; exit 2;; esac
shift
SSH_ASKPASS=$D/mesh_askpass.sh SSH_ASKPASS_REQUIRE=force DISPLAY=:0 setsid -w ssh -o StrictHostKeyChecking=yes \
  -o ConnectTimeout=15 -o PreferredAuthentications=publickey,password -o ServerAliveInterval=30 $J $H "$@" < /dev/null
