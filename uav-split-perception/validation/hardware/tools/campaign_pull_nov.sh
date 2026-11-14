#!/bin/bash
# campaign_pull_nov.sh - plan S6 / E3-E4 (14 Nov 2026): many camera streams on one Jetson, v4.1's sending rule against
#   pull one ahead (pull_bench.py). Server: Nano1 (YOLOv8s FP16). Streams: half on pi-relayyy, half on Nano2 (two radios
#   on the shared channel; an odd count puts the extra stream on pi-relayyy). 1, 2, 4, 6, 8 streams x v41 / pull1 x 2 reps
#   = 20 runs of 60 s (~2 min each with start-up), order shuffled. Nothing else may use the boards meanwhile.
#   Predictions: docs/mesh_predictions_nov14.md (S6). Results: pull_nov/<label>_<host>.jsonl.
# First: push pull_bench.py to camera, jetson, jetson2. Passwords: env PI2_PW PI3_PW NANO_PW N2_PW.
D=$(cd "$(dirname "$0")" && pwd); H=$(cd $D/../../.. && pwd)/experiments/results/hardware; . $D/mesh_hosts.sh
R=$H/pull_nov; mkdir -p $R
PY_PI=/home/sengar/btp_env/bin/python; PY_N2=/home/nano2/hwbench_env/bin/python; PY_N1=/home/nano/hwbench_env/bin/python
for t in camera jetson jetson2; do $D/mesh_ssh.sh $t "test -f ~/hwbench/pull_bench.py" 2>/dev/null || { echo "pull_bench.py missing on $t: push first"; exit 1; }; done
stop_server() { $D/mesh_ssh.sh jetson "P=\$(pgrep -f '[p]ull_bench.py serve'); [ -n \"\$P\" ] && kill \$P; true" 2>/dev/null; }
for rep in 1 2; do
  for c in $(python3 -c "import random;p=[f'{m}:{n}' for m in ('v41','pull1') for n in (1,2,4,6,8)];random.Random($rep*911).shuffle(p);print(' '.join(p))"); do
    m=${c%%:*}; n=${c##*:}; L=${m}_s${n}_r$rep
    grep -qs on_time_total $R/${L}_camera.jsonl && continue   # done (a failed run leaves no total line: re-run)
    stop_server
    $D/mesh_ssh.sh jetson "cd ~/hwbench; nohup $PY_N1 -W ignore pull_bench.py serve --mode $m --listen 48200 > results/pull_serve_$L.log 2>&1 < /dev/null &" 2>/dev/null
    for i in $(seq 30); do sleep 2; $D/mesh_ssh.sh jetson "grep -q serving ~/hwbench/results/pull_serve_$L.log" 2>/dev/null && break; done
    n1=$(( (n + 1) / 2 )); n2=$(( n / 2 ))
    echo "=== $(date +%T) $L: $n1 streams on pi-relayyy, $n2 on Nano2"
    $D/mesh_ssh.sh camera "cd ~/hwbench; $PY_PI -W ignore pull_bench.py run --to $JET_IP:48200 --mode $m --streams $n1 --seconds 60 --label $L" > $R/${L}_camera.jsonl 2>/dev/null &
    P1=$!
    if [ $n2 -gt 0 ]; then
      $D/mesh_ssh.sh jetson2 "cd ~/hwbench; $PY_N2 -W ignore pull_bench.py run --to $JET_IP:48200 --mode $m --streams $n2 --seconds 60 --label $L" > $R/${L}_nano2.jsonl 2>/dev/null &
      P2=$!; wait $P2
    fi
    wait $P1
    stop_server
    python3 - $R $L <<'EOF'
import glob, json, sys
rows = [json.loads(l) for f in glob.glob(f"{sys.argv[1]}/{sys.argv[2]}_*.jsonl") for l in open(f) if '"stream"' in l]
if rows:
    print(f"{sys.argv[2]}: {len(rows)} streams, on time {sum(r['on_time_fps'] for r in rows):.1f}/s in total, "
          f"worst {min(r['on_time_fps'] for r in rows):.1f}, p50 {sorted(r['lat_p50_ms'] or 9e9 for r in rows)[len(rows)//2]:.0f} ms")
else:
    print(f"{sys.argv[2]}: NO RESULT")
EOF
  done
done
echo "CAMPAIGN_PULL_NOV_DONE"
