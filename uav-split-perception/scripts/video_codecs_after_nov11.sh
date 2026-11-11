#!/bin/bash
# Paper 1, P1-1 follow-up: after video_codecs_nov11.sh, the jointly trained codes (codes is resumable, only the new
# rows run), the JPEG-tuned detector on the same JPEG frames, then the break-even analysis.
set -uo pipefail
cd "$(dirname "$0")/.."
P=/home/sengar/BTP/venv/bin/python
while pgrep -f '[v]ideo_codecs_nov11.sh' > /dev/null; do sleep 60; done
grep -q VIDEO_CODECS_DONE experiments/joint_bottleneck_runs/logs/video_codecs.log || { echo "video job did not finish"; exit 1; }
$P -m evaluation.video_codecs codes || exit 1
$P -m evaluation.video_codecs jpeg_tuned || exit 1
$P -m evaluation.video_codecs analyse || exit 1
echo "=== $(date -u +%T) VIDEO_AFTER_DONE"
