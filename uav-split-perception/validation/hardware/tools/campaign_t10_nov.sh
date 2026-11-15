#!/bin/bash
# campaign_t10_nov.sh - plan T10 (15 Nov 2026): the MEASURE step of paper 1's break-even goodput. pi-receiver (camera2)
#   sends each option to Nano2 (jetson2) with split_live.py, its traffic to the server port shaped by htb to the rate;
#   rates 0.5 0.75 1 2 4 8 Mbit/s x jpeg_q20 jpeg_q35 k4_c4 k4_c8 k2_c8 x 45 s, order shuffled, netem serialising each payload at the
#   rate (a rate-R link, the model's assumption; split_live.py shape()); a second repetition at 0.75-2 Mbit/s; arm htb: token bucket, burst 15 KB
#   (small payloads leave at line rate, as on a shared radio) at 0.5-1 Mbit/s for jpeg_q20 and k4_c4. Prediction committed first: docs/mesh_predictions_nov14.md (T10), experiments/results/hardware/t10/.
#   Results: t10/sweep/<rate>__<option>__r<k>|htb.json (one JSON line from split_live send). Resumable.
# Needs only camera2 and jetson2 on the mesh (no tunnel). Passwords: env PI2_PW PI3_PW NANO_PW N2_PW.
D=$(cd "$(dirname "$0")" && pwd); . $D/mesh_hosts.sh; H=$(cd $D/../../.. && pwd)/experiments/results/hardware
R=$H/${T10_OUT:-t10/sweep}; mkdir -p $R; PY=/home/sengar/btp_env/bin/python; PORT=48190; SEC=${T10_SEC:-45}; COOL=${COOL:-60}
S="printf '%s\n' \"\$PW\" | sudo -S -p ''"
for c in camera2 jetson2; do
  $D/mesh_ssh.sh $c "grep -q 'board_temp' ~/hwbench/split_live.py" 2>/dev/null || { echo "$c has a split_live.py without board_temp: push first"; exit 1; }
done
stop_server() { $D/mesh_ssh.sh jetson2 "P=\$(pgrep -f '^python -W ignore [s]plit_live.py serve'); [ -n \"\$P\" ] && kill \$P; true"; }
cleanup() {
  $D/mesh_ssh.sh camera2 "PW='$PI2_PW'; P=\$(pgrep -f '[s]plit_live.py send'); [ -n \"\$P\" ] && $S kill \$P; sleep 1; $S /usr/sbin/tc qdisc del dev bat0 root 2>/dev/null; true"
}
start_server() {
  stop_server
  $D/mesh_ssh.sh jetson2 "PW='$N2_PW'; $S jetson_clocks; cd ~/hwbench; nohup bash -c 'source ~/hwbench_env/bin/activate; python -W ignore split_live.py serve --device cuda --half --listen $PORT' > results/t10_serve.log 2>&1 < /dev/null &"
  for i in $(seq 30); do sleep 3; $D/mesh_ssh.sh jetson2 "grep -q 'serving on' ~/hwbench/results/t10_serve.log" 2>/dev/null && return 0; done
  echo "server never came up"; return 1
}
jobs() {
  for rep in 1 2 3; do       # 1, 2: netem (a rate-R link, the model's assumption); 3 = arm htb below
    python3 -c "
import random
rates = {1: [0.5, 0.75, 1, 2, 4, 8], 2: [0.75, 1, 2], 3: [0.5, 0.75, 1]}[$rep]
opts = ('jpeg_q20', 'jpeg_q35', 'k4_c4_w128_d2', 'k4_c8_w128_d2', 'k2_c8_w128_d2') if $rep < 3 else ('jpeg_q20', 'k4_c4_w128_d2')
c = [(r, o) for r in rates for o in opts]
random.Random($rep * 9173).shuffle(c)
print('\n'.join(f'$rep {r} {o}' for r, o in c))"
  done
}
trap 'cleanup; stop_server' EXIT
cleanup; start_server || exit 1
for pass in 1 2; do
  jobs | while read rep rate opt; do
    if [ $rep = 3 ]; then SH=htb; L=${rate}__${opt}__htb; else SH=netem; L=${rate}__${opt}__r$rep; fi
    [ -s $R/$L.json ] && continue
    until $D/mesh_ssh.sh camera2 true 2>/dev/null && $D/mesh_ssh.sh jetson2 "pgrep -f '[s]plit_live.py serve'" >/dev/null 2>&1; do
      echo "$(date +%T) camera2 or the server unreachable/down, restarting server"; start_server || sleep 60; done
    for i in $(seq 90); do       # pre-cool (15 Nov 2026: the camera Pi reached 83 C, soft limit active, in the first sweep)
      TC=$($D/mesh_ssh.sh camera2 "vcgencmd measure_temp | tr -dc 0-9." 2>/dev/null)
      [ -n "$TC" ] && python3 -c "import sys; sys.exit(float('$TC') >= $COOL)" && break
      sleep 20
    done
    echo "=== $(date +%T) pass $pass $L  start ${TC} C  (done: $(ls $R/*.json 2>/dev/null | wc -l))"
    out=$($D/mesh_ssh.sh camera2 "PW='$PI2_PW'; cd ~/hwbench; $S timeout $((SEC+120)) $PY -W ignore split_live.py send --to $JET2_IP:$PORT --option $opt --seconds $SEC --rate-mbit $rate --shaper $SH --dev bat0 2> results/t10_send.err | tail -1" 2>/dev/null)
    if echo "$out" | grep -q '"on_time"'; then echo "$out" > $R/$L.json; echo "$out" | cut -c1-220
    else echo "NO RESULT for $L: $(echo "$out" | tail -c 200)"; cleanup; fi
  done
done
echo "CAMPAIGN_T10_NOV_DONE ($(ls $R/*.json 2>/dev/null | wc -l) runs)"
