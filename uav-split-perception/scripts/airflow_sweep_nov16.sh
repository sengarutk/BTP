#!/usr/bin/env bash
# Item 6 (16-17 Nov 2026): the airflow sweep in the validated replay. Resumable (finished rows are skipped).
# Relaunched 17 Nov after the laptop restarted: 3 shards (one per seed 1-3, memory), k = 1.0-0.6 (0.5 dropped:
# documented in docs/laptop_strengthening_predictions_nov16.md), 24-min mission then the 2-min mission.
cd "$(dirname "$0")/../validation/hardware"
PY=/home/sengar/BTP/venv/bin/python
L=../../experiments/results/hardware/replay/airflow_nov16/logs
POLS=$(for k in 1 0.9 0.8 0.7 0.6; do for b in v41 hold guard noprice; do printf "af%s_%s " $k $b; done; done)
for s in 1 2 3; do
  ( $PY replay_airflow.py run --scenario mission --phase-s 240 --seeds $s-$s --only $POLS >> $L/m240_s$s.log 2>&1
    $PY replay_airflow.py run --scenario mission --phase-s 20 --seeds $s-$s --only $POLS >> $L/m20_s$s.log 2>&1 ) &
done
wait
echo ALL_DONE
