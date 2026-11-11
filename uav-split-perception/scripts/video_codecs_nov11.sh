#!/bin/bash
# Paper 1, P1-1: video codecs as the image family (evaluation/video_codecs.py), after the replay queue (memory).
set -uo pipefail
cd "$(dirname "$0")/.."
P=/home/sengar/BTP/venv/bin/python
while pgrep -f '[a]fter_adapt_nov11' > /dev/null; do sleep 60; done
$P -m evaluation.video_codecs raw || exit 1
$P -m evaluation.video_codecs jpeg || exit 1
$P -m evaluation.video_codecs video || exit 1
$P -m evaluation.video_codecs codes || exit 1
echo "=== $(date -u +%T) VIDEO_CODECS_DONE"
