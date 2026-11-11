#!/bin/bash
# Rerun of the video follow-up after the joint-checkpoint loading fix (video_codecs.py cmd_codes): the 4 joint codes
# (the 13 finished rows are skipped), the JPEG-tuned detector on the same frames, the analysis.
set -uo pipefail
cd "$(dirname "$0")/.."
P=/home/sengar/BTP/venv/bin/python
$P -m evaluation.video_codecs codes || exit 1
$P -m evaluation.video_codecs jpeg_tuned || exit 1
$P -m evaluation.video_codecs analyse || exit 1
echo "=== $(date -u +%T) VIDEO_AFTER_DONE"
