#!/bin/bash
# rcp.sh pi|nano <scp args, REMOTE: = the board> (key auth if installed, else passwords from env PI_PW / NANO_PW)
D=$(cd "$(dirname "$0")" && pwd)
case $1 in pi) H=dubey@192.168.0.248; P=$PI_PW;; nano) H=nano@192.168.0.188; P=$NANO_PW;; *) echo "pi|nano"; exit 2;; esac
shift; args=("${@//REMOTE:/$H:}")
SSHPW="$P" SSH_ASKPASS=$D/askpass.sh SSH_ASKPASS_REQUIRE=force DISPLAY=:0 setsid -w scp -q -o StrictHostKeyChecking=yes \
  -o PreferredAuthentications=publickey,password "${args[@]}" < /dev/null
