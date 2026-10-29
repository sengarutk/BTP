#!/bin/bash
# Laptop-only work while the boards are away (23 Oct 2026). Resumable: every step skips what is already done.
#  GPU: 2. C7 detections, YOLOv8s/m settings (first)   1. YOLOv8n VisDrone fine-tuning (resume)
#       3. C7 detections, YOLOv8n settings (after 1)    4. YOLO11n/s/m VisDrone fine-tuning (80/80/60 epochs, batch 16/8/4)
#  CPU: C7 rescoring of the 776 earlier runs (report_rescore.py --visdrone), started after step 3, alongside step 4
cd /home/sengar/BTP/uav-split-perception; V=/home/sengar/BTP/venv/bin/python; L=experiments/finetune
log(){ echo "$(date '+%F %T') $*"; }
log "chain start"
# 2 (first, alone on the GPU: training used up to 5.9 of its 6.1 GB): VisDrone detections of the YOLOv8s/m settings
(cd validation/hardware && $V vd_variant_dets.py --variants s320,s640,s640q90,s640q50,s480q90,s480q50,s320q90,s320q50,m640q90,m640q50 > ../../$L/c7_dets_sm.log 2>&1)
log "C7 s/m detections done: $(ls experiments/results/hardware/vd_variant_dets/*.npz 2>/dev/null | wc -l) settings"
# 1: YOLOv8n (done or stopped by GPU faults: see experiments/finetune/yolov8n_e80/STOPPED_AT_EPOCH_77.txt)
train(){   # train MODEL EPOCHS BATCH: up to 6 attempts, each resuming from the last saved epoch after a GPU fault
  local m=$1 e=$2 b=$3 d=$L/$1_e$2 k
  for k in 1 2 3 4 5 6; do
    [ "$(tail -1 $d/results.csv 2>/dev/null | cut -d, -f1 | tr -d ' ')" = "$e" ] && [ -f weights/${m}_visdrone.pt ] && return 0
    # early stopping (no gain in 20 epochs) also ends a run: train_visdrone.py then writes the final weights line
    grep -aq "best weights -> .*/weights/${m}_visdrone.pt" $L/${m}_e$e.log 2>/dev/null && [ -f weights/${m}_visdrone.pt ] && return 0
    if [ -f $d/weights/last.pt ]; then log "$m resume (attempt $k) from epoch $(tail -1 $d/results.csv | cut -d, -f1 | tr -d ' ')"; $V scripts/train_visdrone.py $m $e --resume >> $L/${m}_e$e.log 2>&1
    else log "$m start (attempt $k)"; $V scripts/train_visdrone.py $m $e --batch $b >> $L/${m}_e$e.log 2>&1; fi
    sleep 20
  done
  if [ -f $d/weights/best.pt ]; then cp $d/weights/best.pt weights/${m}_visdrone.pt
    log "$m STOPPED at epoch $(tail -1 $d/results.csv | cut -d, -f1 | tr -d ' ') of $e after 6 attempts: best epoch so far kept"; fi
}
if [ ! -f weights/yolov8n_visdrone.pt ]; then train yolov8n 80 16; fi
# 3: YOLOv8n detections, then the C7 rescoring on the CPU (background)
(cd validation/hardware && $V vd_variant_dets.py --variants n320 > ../../$L/c7_dets_n.log 2>&1)
log "C7 detections: $(ls experiments/results/hardware/vd_variant_dets/*.npz 2>/dev/null | wc -l) settings"
(cd validation/hardware && nice -n 15 $V report_rescore.py --visdrone --workers 3 > ../../$L/c7_rescore.log 2>&1; echo "$(date '+%F %T') C7 rescoring rc $?" >> ../../$L/c7_rescore.log) &
C7=$!
# 4: YOLO11 fine-tuning
for spec in "yolo11n 80 16" "yolo11s 80 8" "yolo11m 60 4"; do
  set -- $spec; train $1 $2 $3
  log "$1 done: best mAP50-95 $($V -c "import csv;r=list(csv.DictReader(open('$L/$1_e$2/results.csv')));k=[c for c in r[0] if 'mAP50-95' in c][0];print(max(float(x[k]) for x in r))" 2>/dev/null)"
done
wait $C7
log "CHAIN_DONE"
