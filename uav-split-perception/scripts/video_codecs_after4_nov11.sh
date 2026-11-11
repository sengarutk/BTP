#!/bin/bash
# Video follow-up, last part: the JPEG-tuned detector on the same frames (checkpoint loading fixed) and the analysis.
set -uo pipefail
cd "$(dirname "$0")/.."
P=/home/sengar/BTP/venv/bin/python
$P -m evaluation.video_codecs jpeg_tuned || exit 1
$P -m evaluation.video_codecs analyse || exit 1
echo "=== $(date -u +%T) VIDEO_AFTER_DONE"
