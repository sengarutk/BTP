#!/usr/bin/env bash
# Runs jobs.txt at most 6 at a time (each replay process peaks at about 0.76 GB; 21 at once exhausted the laptop's
# 11.8 GB on 29 Oct 2026 and it restarted). Single-threaded numpy.
cd /home/sengar/BTP/uav-split-perception
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
Q=experiments/results/hardware/replay/queue_oct29
xargs -P 6 -I{} bash -c '{}' < $Q/jobs.txt
echo "queue done $(date +%H:%M)" >> $Q/queue.log
