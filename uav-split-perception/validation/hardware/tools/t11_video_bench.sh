#!/bin/bash
# t11_video_bench.sh (plan T11, 16 Nov 2026): low-delay video encode time per frame on this board (run on a camera Pi,
# in ~/hwbench). The first sequence of visdrone_vid_640 (up to N frames) is decoded once to raw YUV 4:2:0, so only the
# encode is timed; one thread, -tune zerolatency, no B-frames (x264) / zerolatency (x265), CRF 18 23 28 33, presets
# ultrafast and medium, plus the Pi 5's h264_v4l2m2m. ffmpeg -benchmark reports utime/rtime; per-frame time =
# rtime / frames. Output: one JSON line per setting -> results/t11_video_<host>.jsonl
cd ~/hwbench; N=${N:-150}; OUT=results/t11_video_$(hostname)${CRFS:+_extra}.jsonl; : > $OUT
SEQ=$(python3 -c "import json;print(json.load(open('visdrone_vid_640/sequences.json'))[0][0])")
TMP=$(mktemp -d); trap 'rm -rf $TMP' EXIT
ffmpeg -hide_banner -loglevel error -start_number 1 -i visdrone_vid_640/$SEQ/%07d.jpg -frames:v $N -pix_fmt yuv420p -f rawvideo $TMP/in.yuv
SZ=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 visdrone_vid_640/$SEQ/0000001.jpg)
NF=$(( $(stat -c %s $TMP/in.yuv) / ( $(echo $SZ | cut -dx -f1) * $(echo $SZ | cut -dx -f2) * 3 / 2 ) ))
run() {   # $1 label, rest: encoder args
  local L=$1; shift
  local o=$(ffmpeg -hide_banner -benchmark -f rawvideo -pix_fmt yuv420p -s $SZ -i $TMP/in.yuv "$@" -f null - 2>&1)
  local rt=$(echo "$o" | grep -o "rtime=[0-9.]*s" | tail -1 | tr -dc 0-9.)
  local ut=$(echo "$o" | grep -o "utime=[0-9.]*s" | tail -1 | tr -dc 0-9.)
  if [ -n "$rt" ]; then echo "{\"setting\": \"$L\", \"frames\": $NF, \"size\": \"$SZ\", \"rtime_s\": $rt, \"utime_s\": $ut, \"ms_per_frame\": $(python3 -c "print(round($rt*1000/$NF,3))")}" | tee -a $OUT
  else echo "{\"setting\": \"$L\", \"error\": \"$(echo "$o" | tail -2 | tr -d '"\n' | cut -c1-160)\"}" | tee -a $OUT; fi
}
for p in ultrafast medium; do for q in ${CRFS:-18 23 28 33}; do
  # exactly evaluation/video_codecs.py encode_args (paper 1), so the Pi/laptop ratio compares like with like
  run x264_${p}_crf$q -c:v libx264 -preset $p -tune zerolatency -crf $q -x264-params bframes=0:keyint=60:intra-refresh=1:threads=1
  run x265_${p}_crf$q -c:v libx265 -preset $p -tune zerolatency -crf $q -x265-params bframes=0:keyint=60:intra-refresh=1:pools=1:frame-threads=1:log-level=error
done; done
[ -z "$CRFS" ] && run h264_v4l2m2m -c:v h264_v4l2m2m -b:v 2M
echo "T11_DONE $OUT"
