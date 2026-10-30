#!/usr/bin/env bash
# 30 Oct 2026: the corrected power model with the board held at its 85 C throttle limit; the validation against the 240
# hardware runs and the 12 held-out 24-min runs again. At most 6 jobs at once (0.76 GB each), single-threaded numpy.
cd /home/sengar/BTP/uav-split-perception
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
Q=experiments/results/hardware/replay/queue_oct30_t85
echo "queue start $(date +%H:%M)" >> $Q/queue.log
xargs -P 6 -I{} bash -c '{}' < $Q/jobs.txt
echo "queue done $(date +%H:%M)" >> $Q/queue.log
