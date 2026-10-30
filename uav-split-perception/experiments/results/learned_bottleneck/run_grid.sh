#!/usr/bin/env bash
# The learned-bottleneck rate curve (30 Oct 2026): one GPU job at a time (train 20 epochs, then evaluate on
# VisDrone2019-DET val). Resumable: a configuration with an eval_*.json is skipped.
cd /home/sengar/BTP/uav-split-perception
D=experiments/results/learned_bottleneck
P=/home/sengar/BTP/venv/bin/python
while read cut ch w s d; do
  t=k${cut}_c${ch}; [ $w != 64 ] && t=${t}_w$w; [ $s != 2 ] && t=${t}_s$s; [ $d != 1 ] && t=${t}_d$d
  [ -f $D/eval_$t.json ] && continue
  echo "$(date +%H:%M) train $t" >> $D/grid.log
  $P -m evaluation.learned_bottleneck train --cut $cut --channels $ch --width $w --stride $s --dec-layers $d --epochs 20 \
    > $D/logs/train_$t.log 2>&1 || { echo "$(date +%H:%M) TRAIN FAILED $t" >> $D/grid.log; continue; }
  $P -m evaluation.learned_bottleneck eval --cut $cut --channels $ch --width $w --stride $s --dec-layers $d \
    > $D/logs/eval_$t.log 2>&1 || { echo "$(date +%H:%M) EVAL FAILED $t" >> $D/grid.log; continue; }
  echo "$(date +%H:%M) done $t: $(tail -1 $D/logs/eval_$t.log | cut -c1-200)" >> $D/grid.log
done <<'CFG'
4 16 128 2 2
4 32 128 2 2
4 64 128 2 2
4 16 128 1 2
2 16 128 2 2
2 8 128 2 2
CFG
echo "$(date +%H:%M) GRID DONE" >> $D/grid.log
