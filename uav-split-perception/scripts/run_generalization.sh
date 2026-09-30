#!/usr/bin/env bash
# Runs the whole generalization study. Every step is resumable: re-running the script skips
# finished downloads, finished survey rows (model_summary.csv) and cached validation results.
#   scripts/run_generalization.sh download   # weights + VisDrone (resumable curl)
#   scripts/run_generalization.sh gpu        # surveys and accuracy studies
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python}
REL=https://github.com/ultralytics/assets/releases/download
ACC_MODELS="yolo11n yolo11s yolo11m yolov9s yolov10s"
MORE_MODELS="yolov9t yolov9m yolov10n yolov10m yolo11l yolo11x yolov8x"

fetch() {  # fetch <url> <dest>: resumable, verified against the server's size
  local url=$1 dest=$2 size
  size=$(curl -sSLI "$url" | grep -i '^content-length' | tail -1 | tr -dc 0-9)
  if [ -z "$size" ]; then  # no Content-Length: cannot verify, so download once
    [ -s "$dest" ] || curl -sSL --retry 20 --retry-delay 5 -o "$dest" "$url"
    return
  fi
  until [ -f "$dest" ] && [ "$(stat -c %s "$dest")" = "$size" ]; do
    curl -sSL -C - --retry 20 --retry-delay 5 -o "$dest" "$url" || sleep 5
  done
}

download() {
  mkdir -p weights datasets/visdrone
  fetch $REL/v0.0.0/VisDrone2019-DET-val.zip datasets/visdrone/VisDrone2019-DET-val.zip
  for m in $ACC_MODELS $MORE_MODELS; do fetch $REL/v8.4.0/$m.pt weights/$m.pt; done
  echo "downloads complete"
}

step() {  # step <python -m args>: repeat in <=30 min pieces (every step resumes from its cache) until it succeeds
  local i
  for i in $(seq 20); do timeout 1800 $PY -m "$@" && return 0; done
  return 1
}

have_all() { for m in "$@"; do [ -f "weights/$m.pt" ] || [ -f "$m.pt" ] || return 1; done; }

gpu() {
  step evaluation.gen_accuracy --study bits
  until have_all $ACC_MODELS; do sleep 60; done
  step evaluation.gen_model_survey --models yolov5nu yolov5su yolov5mu yolov8n yolov8s yolov8m yolov8l $ACC_MODELS
  step evaluation.gen_accuracy --study models
  step evaluation.gen_accuracy --study resolution
  until [ -f datasets/visdrone_val.yaml ]; do
    if [ -d datasets/visdrone/VisDrone2019-DET-val/annotations ] || $PY -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).testzip()" \
         datasets/visdrone/VisDrone2019-DET-val.zip 2>/dev/null; then
      $PY -c "import sys; sys.path.insert(0, 'scripts'); from prepare_datasets import prepare_visdrone_val as p; p()"
    else sleep 60; fi
  done
  step evaluation.gen_accuracy --study aerial
  step evaluation.gen_model_survey --sizes 320 480 960 1280 --models yolov8n yolov8s yolov8m yolo11s
  step evaluation.gen_model_survey --sizes 640 1280 --images visdrone --models yolov8n yolov8s yolov8m yolo11s
  until have_all $MORE_MODELS; do sleep 60; done
  step evaluation.gen_model_survey --models $MORE_MODELS
  echo "gpu pipeline complete"
}

"$@"
