#!/usr/bin/env bash
# Items 8b then 7b (17 Nov 2026), one process at a time (resumable).
cd "$(dirname "$0")/../validation/hardware"
PY=/home/sengar/BTP/venv/bin/python
O=../../experiments/results/hardware/replay
$PY replay_conformal.py --seeds 1-10 >> $O/conformal_nov12/run.log 2>&1
$PY replay_skip.py run --shared 0 >> $O/skip_nov16/shared0.log 2>&1
$PY replay_skip.py run --shared 1 >> $O/skip_nov16/shared1.log 2>&1
echo CHAIN_DONE >> $O/skip_nov16/shared1.log
