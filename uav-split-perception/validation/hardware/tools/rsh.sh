#!/bin/bash
# rsh.sh pi|nano "command" - run a command on a board (key auth if installed, else passwords from env PI_PW / NANO_PW)
D=$(cd "$(dirname "$0")" && pwd)
case $1 in pi) H=dubey@192.168.0.248; P=$PI_PW;; pi2) H=sengar@${PI2_HOST:-192.168.0.129}; P=$PI2_PW;; pi3) H=dubey@${PI3_HOST:-192.168.0.247}; P=$PI3_PW;; nano) H=nano@${NANO_IP:-192.168.0.188}; P=$NANO_PW;; *) echo "pi|pi2|pi3|nano"; exit 2;; esac
shift
SSHPW="$P" SSH_ASKPASS=$D/askpass.sh SSH_ASKPASS_REQUIRE=force DISPLAY=:0 setsid -w ssh -o StrictHostKeyChecking=yes \
  -o ConnectTimeout=15 -o PreferredAuthentications=publickey,password -o ServerAliveInterval=30 $H "$@" < /dev/null
