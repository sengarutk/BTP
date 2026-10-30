#!/usr/bin/env bash
# Replay validation with the onboard power model "power" (29 Oct 2026): the same 12 policies, 4 scenarios and seeds 1-5
# as validate_main_oct29_plant, one process per scenario and policy group, merged afterwards (merge_summary.py).
cd /home/sengar/BTP/uav-split-perception
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
V=experiments/results/hardware/replay/validate_main_oct29_power
P=/home/sengar/BTP/venv/bin/python
G1="v5 v42 v5_nofc v5_flat"; G2="v5_lin v5_exp leaf fixed_laptop_m640q90"; G3="jsq aoi_thr conf_trigger reward_offload"
for sc in mission mission_mirror random static_good; do
  i=0
  for g in "$G1" "$G2" "$G3"; do
    i=$((i+1))
    nohup $P validation/hardware/replay.py --policy $g --scenario $sc --phase-s 20 --seeds 1-5 --netem reset \
      --onboard-power power --out $V/${sc}_g$i > $V/${sc}_g$i.log 2>&1 &
  done
done
