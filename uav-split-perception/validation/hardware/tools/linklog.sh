#!/bin/bash
# linklog.sh OUTFILE - batman-adv originators and neighbours every 5 s for the run's link log (sudo password from env PW)
while true; do
  echo "T $(date +%s)"
  printf '%s\n' "$PW" | sudo -S -p '' /usr/sbin/batctl o -H
  printf '%s\n' "$PW" | sudo -S -p '' /usr/sbin/batctl n -H
  sleep 5
done >> "$1" 2>&1
