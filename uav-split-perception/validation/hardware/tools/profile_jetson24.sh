#!/bin/bash
# profile_jetson24.sh [OUTFILE] — re-measure the Jetson energy profile (post-reflash) with a
# 24-minute sustained heat phase: energy_profile.py --device jetson --heat-s 1440 --cool-s 300
# (states at 20 s each, then YOLOv8m @ 640 back to back for 24 min at 1 Hz power/temp/clock log,
# then 5 min cooldown), then fetch the result. Establishes the Jetson's steady-state thermal
# numbers to the same standard as the Pi's thermal_steady test.
# The profile's radio states need a laptop peer on port 48120 over the Wi-Fi: this script drives
# them from this laptop (a pusher for radio_rx_max, then a drainer for the two transmit states),
# polling the run's log over SSH.
# Passwords: env NANO_PW only (sudo for jetson_clocks; never written to files). Key auth from the
# laptop is tried first. Must NOT run while a campaign is using the Jetson.
D=$(cd "$(dirname "$0")" && pwd)
OUT=${1:-"$D/../../../experiments/results/hardware/energy/energy_profile_jetson_20261009.json"}
H=nano@192.168.0.188
JPY=/home/nano/hwbench_env/bin/python

# 0. prerequisites: venv torch+CUDA, model, video, results dir
echo "== prereq check =="
$D/rsh.sh nano "cd ~/hwbench && $JPY -c 'import torch; print(\"torch\", torch.__version__, \"cuda\", torch.cuda.is_available())' \
  && ls energy_profile.py yolov8m.pt visdrone_vid_640/sequences.json && ls -d results" \
  || { echo "PREREQ FAILED"; exit 1; }

# 1. stale processes from earlier runs, then lock clocks (as in every campaign)
$D/rsh.sh nano "P=\$(pgrep -f 'adaptive.py worker|adaptive2.py|energy_profile.py'); [ -n \"\$P\" ] && printf '%s\n' '$NANO_PW' | sudo -S -p '' kill \$P; true"
if [ -n "$NANO_PW" ]; then
  $D/rsh.sh nano "printf '%s\n' '$NANO_PW' | sudo -S -p '' jetson_clocks" || { echo "JETSON_CLOCKS FAILED"; exit 1; }
else
  $D/rsh.sh nano "sudo -n jetson_clocks" || { echo "Set NANO_PW (sudo needed for jetson_clocks): NANO_PW=... ./profile_jetson24.sh"; exit 1; }
fi

# 2. launch the profile in the background on the Jetson
$D/rsh.sh nano "cd ~/hwbench; rm -f results/energy_profile_jetson.json results/energy_profile_jetson_24min.log; \
  nohup $JPY -W ignore energy_profile.py --device jetson --state-s 20 --heat-s 1440 --cool-s 300 \
  > results/energy_profile_jetson_24min.log 2>&1 & echo PROFILE_UP"

# 3. drive the radio states from this laptop (peer over the Wi-Fi, port 48120)
PUSH=0; DRAIN=0
for i in $(seq 600); do
  LOG=$($D/rsh.sh nano "cat ~/hwbench/results/energy_profile_jetson_24min.log" 2>/dev/null)
  case "$LOG" in
    *ENERGY_PROFILE_DONE*) break;;
  esac
  if [ "$PUSH" = 0 ] && echo "$LOG" | grep -q "radio: waiting for the laptop$"; then
    PUSH=1
    python3 -c '
import socket, time, sys
s = socket.socket(); s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
s.connect(("192.168.0.188", 48120))
chunk = 87000 * b"x"
t0 = time.time()
try:
    while time.time() - t0 < 120: s.sendall(chunk)
except OSError: pass
s.close()' &
    echo "pusher up (radio_rx_max)"
  elif [ "$DRAIN" = 0 ] && echo "$LOG" | grep -q "waiting for the laptop (transmit test)"; then
    DRAIN=1
    python3 -c '
import socket, time
s = socket.socket(); s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
s.connect(("192.168.0.188", 48120))
s.settimeout(1.0)
t0 = time.time()
try:
    while time.time() - t0 < 120:
        try: s.recv(1 << 16)
        except socket.timeout: pass
except OSError: pass
s.close()' &
    echo "drainer up (radio_tx)"
  fi
  sleep 4
done
wait
echo "== radio states driven =="

# 4. wait for the run to finish (24 min heat + 5 min cool), then fetch
for i in $(seq 200); do
  $D/rsh.sh nano "grep -q ENERGY_PROFILE_DONE ~/hwbench/results/energy_profile_jetson_24min.log" 2>/dev/null && break
  sleep 10
done
$D/rcp.sh nano REMOTE:hwbench/results/energy_profile_jetson.json "$OUT" \
  && $D/rcp.sh nano REMOTE:hwbench/results/energy_profile_jetson_24min.log \
      "${OUT%/*}/energy_profile_jetson_24min.log" \
  && echo "FETCHED: $OUT" || { echo "FETCH FAILED"; exit 1; }
$D/rsh.sh nano "tail -5 ~/hwbench/results/energy_profile_jetson_24min.log"
