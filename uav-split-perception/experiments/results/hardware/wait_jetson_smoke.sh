#!/bin/bash
cd /home/sengar/BTP/uav-split-perception; T=validation/hardware/tools
until ping -c1 -W3 192.168.0.188 >/dev/null 2>&1 && $T/rsh.sh nano true 2>/dev/null; do sleep 30; done
echo "jetson back $(date +%T)"; $T/rsh.sh nano 'uptime -s'
$T/rcp.sh nano validation/hardware/adaptive.py validation/hardware/hwbench.py REMOTE:hwbench/
$T/arun.sh estfix A_full static_good 10 1 experiments/results/hardware/smoke --vid visdrone_vid_640 --conf 0.01 --acc variant_accuracy_visdrone.json --decay staleness_decay.json --objective stream
python3 -c "
import json
r=json.load(open('experiments/results/hardware/smoke/a2_estfix.json'))
for k,v in r['per_phase'].items(): print(k, round(v['availability'],2), sorted(v['dispatch'].items(), key=lambda x:-x[1])[:4])"
echo SMOKE_DONE
