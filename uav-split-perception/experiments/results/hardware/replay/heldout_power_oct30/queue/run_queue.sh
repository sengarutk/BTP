#!/usr/bin/env bash
# Held-out check (30 Oct 2026), corrected onboard power model, seeds 11-20 (none used before): at most 6 jobs at once
# (each replay process peaks at about 0.76 GB; the laptop has 11.8 GB). Single-threaded numpy.
cd /home/sengar/BTP/uav-split-perception
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
Q=experiments/results/hardware/replay/heldout_power_oct30/queue
echo "queue start $(date +%H:%M)" >> $Q/queue.log
xargs -P 6 -I{} bash -c '{}' < $Q/jobs.txt
echo "queue done $(date +%H:%M)" >> $Q/queue.log
