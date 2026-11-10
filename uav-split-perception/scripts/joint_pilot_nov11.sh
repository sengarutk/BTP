#!/bin/bash
# Run 2 pilot: learning rate for the joint fine-tune, k4_c16, a quarter of the training images, 4 epochs, no weights kept.
cd "$(dirname "$0")/.." || exit 1
PY=/home/sengar/BTP/venv/bin/python
for lr in 1e-4 3e-5 3e-4 1e-3; do   # 1e-3 was run on its own after the first three (log pilot2.log)
  echo "=== $(date +%T) pilot lr $lr"
  $PY -m evaluation.joint_bottleneck train --cut 4 --channels 16 --epochs 4 --fraction 0.25 --lr0 $lr --run pilot_lr$lr --save 0 --workers 2 || exit 1
done
echo "=== $(date +%T) PILOT_DONE"
