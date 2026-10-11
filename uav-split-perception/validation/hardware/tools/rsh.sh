#!/bin/bash
# rsh.sh pi|nano "command" - run a command on a board (key auth if installed, else passwords from env PI_PW / NANO_PW)
D=$(cd "$(dirname "$0")" && pwd)
case $1 in pi) H=dubey@192.168.0.248; P=$PI_PW;; nano) H=nano@192.168.0.188; P=$NANO_PW;; *) echo "pi|nano"; exit 2;; esac
shift
SSHPW="$P" SSH_ASKPASS=$D/askpass.sh SSH_ASKPASS_REQUIRE=force DISPLAY=:0 setsid -w ssh -o StrictHostKeyChecking=yes \
  -o ConnectTimeout=15 -o PreferredAuthentications=publickey,password -o ServerAliveInterval=30 $H "$@" < /dev/null
