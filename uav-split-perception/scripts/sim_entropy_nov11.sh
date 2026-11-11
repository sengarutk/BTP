#!/bin/bash
# Simulator check of the break-even rule with the entropy-coded codes, against untuned and tuned JPEG.
set -uo pipefail
cd "$(dirname "$0")/.."
P=/home/sengar/BTP/venv/bin/python
$P -m evaluation.break_even_sim --entropy --workers 4 || exit 1
$P -m evaluation.break_even_sim --entropy --tuned jpegtuned_qmix_r1 --workers 4 || exit 1
echo "=== $(date -u +%T) SIM_ENTROPY_DONE"
