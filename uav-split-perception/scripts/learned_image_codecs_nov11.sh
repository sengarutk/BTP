#!/bin/bash
# Paper 1, P1-3: learned image codecs as the image family. After the second-detector job (GPU timings need an idle
# GPU) and the checkpoint download. Runs in the isolated venv_lic. Resumable.
set -uo pipefail
cd "$(dirname "$0")/.."
P=/home/sengar/BTP/venv_lic/bin/python
while pgrep -f '[s]econd_detector_nov11.sh' > /dev/null; do sleep 60; done
until [ "$(ls $HOME/.cache/torch/hub/checkpoints | grep -c 'pth.tar$')" -ge 22 ]; do sleep 60; done
mkdir -p experiments/results/learned_image_codecs/logs
$P -m evaluation.learned_image_codecs eval > experiments/results/learned_image_codecs/logs/eval.log 2>&1 || { echo "EVAL FAILED"; exit 1; }
$P -m evaluation.learned_image_codecs analyse > experiments/results/learned_image_codecs/logs/analyse.log 2>&1 || { echo "ANALYSE FAILED"; exit 1; }
echo "=== $(date -u +%T) LIC_DONE"
