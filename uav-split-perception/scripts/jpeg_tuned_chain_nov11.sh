#!/usr/bin/env bash
# Fair counterpart of the jointly trained split (audit of paper 1's v2 drafts, 11 Nov 2026): the detector fine-tuned on
# JPEG, mixed qualities (one detector for every setting) and fixed Q35 (the matching setting of the smallest joint code),
# then evaluated on every quality of the grid. Resumable: a finished step leaves its train/eval json.
set -uo pipefail
cd "$(dirname "$0")/.."
P=/home/sengar/BTP/venv/bin/python
R=experiments/results/jpeg_tuned
for q in mix 35; do
  [ -f $R/train_jpegtuned_q${q}_r1.json ] || { echo "=== $(date -u +%T) train q$q"; $P -m evaluation.jpeg_tuned_detector train --q $q --epochs 30 --lr0 1e-3 --workers 2 || exit 1; }
  last=$([ $q = mix ] && echo 95 || echo $q)
  [ -f $R/eval_jpegtuned_q${q}_r1_q${last}.json ] || { echo "=== $(date -u +%T) eval q$q"; $P -m evaluation.jpeg_tuned_detector eval --q $q --workers 3 || exit 1; }
done
echo "=== $(date -u +%T) JPEG_TUNED_CHAIN_DONE"
