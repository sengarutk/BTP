#!/bin/bash
# Start joint training run 2 only after the relay-noise sweep has finished (11 Nov 2026: the two together pushed
# Windows' available memory below the watchdog floor at the training's start-up).
cd "$(dirname "$0")/.." || exit 1
L=experiments/joint_bottleneck_runs/logs
while pgrep -f '[r]elay_noise_sweep' >/dev/null; do sleep 30; done
echo "$(date +%T) sweep finished, starting run 2" >> $L/chain2_launcher.log
exec /home/sengar/BTP/venv/bin/python scripts/guarded_run.py --log $L/chain2_guard.log --wsl-floor-mb 1500 --win-floor-mb 200 -- bash scripts/joint_chain_nov11.sh > $L/chain2.log 2>&1
