#!/bin/bash
# arun_mesh.sh LABEL STRATEGY SCENARIO PHASE_S SEED OUTDIR  - one run on the AegisSwarm mesh (23-24 Oct 2026)
#   camera pi-relayyy (mesh_hosts.sh: 10.1.0.11 since 14 Nov, 10.1.0.12 before): adaptive2.py; netem on bat0 (IP is visible only there); VisDrone weights; live forecaster
#   STRATEGY (all with the motion forecaster):
#     v41      Pi energy price + freshness price (controller v4.1)          heat     heat price + freshness price
#     v41e     v41 + Jetson energy price                                      heate    heat + Jetson energy + freshness
#     v41e12   v41 + Jetson energy price with a 1.2 W budget (mesh campaign 3, 25 Oct: the 0.5 W budget was unreachable)
#     noprice  stream objective, no prices                                    fixlap   fixed Pi -> laptop, YOLOv8m q90
#     aoithr   freshness-threshold offloading (literature)                    hier     hierarchical chain: camera v41
#              objective over onboard + Jetson only; the Jetson runs edge_node.py and decides local vs forward
#     accumo   AccuMO-style 30-frame model-predictive planner (mpc_planner.py, brief 19.10-19.11): content-conditioned
#              decay (camera-motion tertile from the live forecaster), no energy or heat price
#     leaf     LEAF-style fixed energy weight mu = 2.0 (as campaign_main.sh's leaf: v3+fc2 objective, no dual ascent)
#     freshonly  v41 without the energy price (freshness price kept): the energy test (campaign_energy_nov.sh)
#     v41b36   v41 with a 3.6 W budget (the 80 C budget of paper 2's Proposition 1): the energy test
#   SCENARIO static_good | mesh_mission | multihop | multihop_loss2 | multihop_loss5 (multihop*: the direct camera <-> pi-sender radio link is blocked by a
#     temporary nftables rule on both boards, so batman-adv relays through the Jetson; removed at every cleanup. Since
#     14 Nov the mesh has five boards: the camera's links to pi-receiver and Nano2 are blocked too, so the relay is
#     still Nano1, as in every earlier multihop run)
# Optional env EGO_W=160: the live forecaster's camera-motion step at that tracking width (env EGO_W_SMALL -> egomotion.W_SMALL; the
#   cheaper step of 19.9); unset = 320 px, as in every run before 29 Oct 2026.
# Needs mesh_tunnel.sh running. Passwords: env PI2_PW PI3_PW NANO_PW N2_PW.
D=$(cd "$(dirname "$0")" && pwd); HW=$(cd "$D/.." && pwd)
L=$1; ST=$2; SC=$3; PS=$4; SEED=$5; R=$6; mkdir -p $R; R=$(cd $R && pwd)
TOT=$((PS*6+60)); PY=/home/sengar/btp_env/bin/python; JPY=/home/nano/hwbench_env/bin/python
S="printf '%s\n' \"\$PW\" | sudo -S -p ''"
. $D/mesh_hosts.sh; GND_MAC=$SENDER_MAC   # board map and radio MACs (CAM_MAC, JET_MAC, ... unchanged since 23 Oct)
COMMON="--scenario $SC --phase-s $PS --seed $SEED --vid visdrone_vid_640 --conf 0.01 --live-forecast forecast_tuning_v2.json --power-log --energy-constants energy_constants.json --weight-suffix _visdrone --acc variant_accuracy_visdrone_ft.json --onboard-variants s320,s640 --wlan bat0"
DEC="--decay staleness_decay_forecast_v2.json --objective stream"
EDGE="--edge-energy-aware --edge-power-budget 0.5"
HEAT="--thermal-aware --thermal-target-c 75 --thermal-guard-c 84"
case $ST in
  v41)     POL=A_full; X="$DEC --energy-aware --power-budget 2.8 --fresh-target 0.95";;
  v41e)    POL=A_full; X="$DEC --energy-aware --power-budget 2.8 --fresh-target 0.95 $EDGE";;
  v41e12)  POL=A_full; X="$DEC --energy-aware --power-budget 2.8 --fresh-target 0.95 --edge-energy-aware --edge-power-budget 1.2";;
  heat)    POL=A_full; X="$DEC $HEAT --fresh-target 0.95";;
  heate)   POL=A_full; X="$DEC $HEAT --fresh-target 0.95 $EDGE";;
  noprice) POL=A_full; X="$DEC";;
  fixlap)  POL=fixed:laptop:m640q90; X="";;
  aoithr)  POL=aoi_thr; X="";;
  hier)    POL=A_full; X="$DEC --energy-aware --power-budget 2.8 --fresh-target 0.95";;
  accumo)  POL=accumo; X="$DEC --mpc-context decay_context_train.json";;
  leaf)    POL=A_full; X="$DEC --energy-aware --mu-fixed 2.0";;
  freshonly) POL=A_full; X="$DEC --fresh-target 0.95";;                     # energy test: v41 without the energy price
  v41b36)  POL=A_full; X="$DEC --energy-aware --power-budget 3.6 --fresh-target 0.95";;  # energy test: the 80 C budget
  *) echo "unknown strategy $ST"; exit 2;;
esac
[ $ST = hier ] && PATHS=jetson || PATHS=laptop,jetson
# NFT_ON PW "MAC [MAC...]" [DEV]: drop radio frames from those MACs on that board (DEV default wlan0; Nanos wlP1p1s0)
NFT_ON() { local r="" m; for m in $2; do r="$r $S nft add rule netdev aegis_mh in ether saddr $m drop;"; done
  echo "PW='$1'; $S nft add table netdev aegis_mh; $S nft add chain netdev aegis_mh in '{ type filter hook ingress device ${3:-wlan0} priority 0; }';$r"; }
NFT_OFF() { echo "PW='$1'; $S nft delete table netdev aegis_mh 2>/dev/null; true"; }
cleanup() {
  $D/mesh_ssh.sh camera "PW='$PI2_PW'; P=\$(pgrep -f '^$PY -W ignore [a]daptive2.py'); [ -n \"\$P\" ] && $S kill \$P; P=\$(pgrep -f '[l]inklog.sh'); [ -n \"\$P\" ] && kill \$P; sleep 1; $S /usr/sbin/tc qdisc del dev bat0 root 2>/dev/null; true"
  $D/mesh_ssh.sh jetson "PW='$NANO_PW'; P=\$(pgrep -f '[e]dge_node.py'); [ -n \"\$P\" ] && $S kill \$P; P=\$(pgrep -f '^python -W ignore [a]daptive.py worker'); [ -n \"\$P\" ] && kill \$P; sleep 1; $S /usr/sbin/tc qdisc del dev bat0 root 2>/dev/null; true"
  $D/mesh_ssh.sh camera "$(NFT_OFF "$PI2_PW")"; $D/mesh_ssh.sh sender "$(NFT_OFF "$PI3_PW")"
  $D/mesh_ssh.sh camera2 "$(NFT_OFF "$PI2_PW")" 2>/dev/null; $D/mesh_ssh.sh jetson2 "$(NFT_OFF "$N2_PW")" 2>/dev/null
  for P in $(ps -eo pid,args | awk '/^ *[0-9]+ python -W ignore adaptive.py worker --camera 127.0.0.1:4810[14]/ {print $1}'); do kill $P; done
}
watch_cam() {   # no "workers connected" from the camera within 120 s: end the run early (no result) instead of waiting
  for i in $(seq 24); do sleep 5; $D/mesh_ssh.sh camera "grep -q 'workers connected' ~/hwbench/results/a2_$L.log" 2>/dev/null && return; done
  echo "camera never connected its workers: run abandoned"
  for P in $(ps -eo pid,args | awk '/^ *[0-9]+ python -W ignore adaptive.py worker --camera 127.0.0.1:4810[14]/ {print $1}'); do kill $P; done
  $D/mesh_ssh.sh camera "PW='$PI2_PW'; P=\$(pgrep -f '^$PY -W ignore [a]daptive2.py'); [ -n \"\$P\" ] && $S kill \$P; true"
}
fetch() {       # copy with up to 6 attempts (a mesh/jump-host blip can last a minute)
  for k in 1 2 3 4 5 6; do $D/mesh_scp.sh $1 REMOTE:hwbench/results/$2 $R/ 2>/dev/null && return 0; sleep 10; done
  echo "copy failed: $2"; return 1
}
# the laptop's own link to pi-sender (Windows -> cable) drops packets at times (24 Oct): a 1 s ping log runs beside the
# campaign; start only after 60 s with at most 1 lost ping, and discard a run with >5 % lost or a >= 5 s outage
PINGLOG=$(cd $HW/../../experiments/results/hardware && pwd)/vid_campaign_mesh2_laptop_ping.txt
link_ok() { [ -f $PINGLOG ] || return 0; [ $(tail -60 $PINGLOG | grep -c 'no answer') -le 1 ]; }
if ! link_ok; then
  echo "laptop link to pi-sender degraded: waiting"
  for i in $(seq 180); do sleep 10; link_ok && break; done
  link_ok || { echo "laptop link still degraded after 30 min: run abandoned"; echo "NO RESULT for $L"; exit 1; }
  echo "laptop link clean again after $((i*10)) s"
fi
T_RUN0=$(date +%s.%N)
cleanup
if [[ $SC == multihop* ]]; then     # block the direct camera <-> ground-radio link; wait until batman-adv routes via the Jetson
  $D/mesh_ssh.sh camera "$(NFT_ON "$PI2_PW" "$GND_MAC $CAM2_MAC $JET2_MAC")"; $D/mesh_ssh.sh sender "$(NFT_ON "$PI3_PW" $CAM_MAC)"
  $D/mesh_ssh.sh camera2 "$(NFT_ON "$PI2_PW" $CAM_MAC)"; $D/mesh_ssh.sh jetson2 "$(NFT_ON "$N2_PW" $CAM_MAC wlP1p1s0)"
  ok=0
  for i in $(seq 30); do
    sleep 5
    nh=$($D/mesh_ssh.sh camera "PW='$PI2_PW'; $S /usr/sbin/batctl o -H 2>/dev/null | awk '\$1==\"*\" && \$2==\"$GND_MAC\" {for(i=3;i<=NF;i++) if(\$i ~ /^([0-9a-f][0-9a-f]:){5}[0-9a-f][0-9a-f]\$/) {print \$i; exit}}'" 2>/dev/null)
    [ "$nh" = "$JET_MAC" ] && { ok=1; break; }
  done
  echo "multihop route camera -> ground radio: next hop ${nh:-none} after $((i*5)) s"
  [ $ok = 1 ] || { echo "multihop route not established: run abandoned"; cleanup; echo "NO RESULT for $L"; exit 1; }
fi
if [[ $SC != multihop* ]]; then    # after a multihop run batman-adv keeps the relayed route for a while: wait for the direct one
  ok=0
  for i in $(seq 36); do
    nh=$($D/mesh_ssh.sh camera "PW='$PI2_PW'; $S /usr/sbin/batctl o -H 2>/dev/null | awk '\$1==\"*\" && \$2==\"$GND_MAC\" {for(i=3;i<=NF;i++) if(\$i ~ /^([0-9a-f][0-9a-f]:){5}[0-9a-f][0-9a-f]\$/) {print \$i; exit}}'" 2>/dev/null)
    [ "$nh" = "$GND_MAC" ] && { ok=1; break; }
    sleep 5
  done
  [ $ok = 1 ] || { echo "direct route camera -> ground radio not restored (next hop ${nh:-none}): run abandoned"; cleanup; echo "NO RESULT for $L"; exit 1; }
  [ $i -gt 1 ] && echo "direct route restored after $(((i-1)*5)) s"
fi
$D/mesh_ssh.sh jetson "PW='$NANO_PW'; $S jetson_clocks" 2>/dev/null
$D/mesh_ssh.sh camera "cd ~/hwbench; rm -f results/a2_$L.* results/link_$L.txt; PW='$PI2_PW'; $S ${EGO_W:+env EGO_W_SMALL=$EGO_W} nohup $PY -W ignore adaptive2.py --policy '$POL' $COMMON $X --paths $PATHS --out results/a2_$L.json > results/a2_$L.log 2>&1 & echo cam_up"
$D/mesh_ssh.sh camera "cd ~/hwbench; PW='$PI2_PW' nohup bash linklog.sh results/link_$L.txt > /dev/null 2>&1 & echo linklog_up"
sleep 20
if [ $ST = hier ]; then
  for k in 1 2 3; do
    $D/mesh_ssh.sh jetson "cd ~/hwbench; PW='$NANO_PW'; $S nohup $JPY -W ignore edge_node.py --camera $CAM_IP:48102 --listen 48104 --wlan bat0 --log results/edge_$L.json > results/edge_$L.log 2>&1 & echo edge_up"
    st=""; for c in 1 2 3; do sleep $((c==1 ? 8 : 3))
      st=$($D/mesh_ssh.sh jetson "pgrep -f '[e]dge_node.py --camera' >/dev/null && echo RUN || echo NONE" 2>/dev/null)
      [ -n "$st" ] && break; done
    [ "$st" = NONE ] || break
    echo "edge node not running, retry $k"
  done
  watch_cam &
  (cd $HW; source /home/sengar/BTP/venv/bin/activate; timeout $((TOT+300)) python -W ignore adaptive.py worker --camera 127.0.0.1:48104 --device cuda --half --weights ../../weights/yolov8s_visdrone.pt,../../weights/yolov8m_visdrone.pt --label ground --give-up-s 900 > $R/a2w_${L}_ground.log 2>&1) &
else
  for k in 1 2 3; do
    $D/mesh_ssh.sh jetson "cd ~/hwbench; nohup bash -c 'source ~/hwbench_env/bin/activate; python -W ignore adaptive.py worker --camera $CAM_IP:48102 --device cuda --half --weights yolov8s_visdrone.pt --label jetson --report-power jetson' > results/a2w_$L.log 2>&1 & echo jet_up"
    # relaunch only when the check itself got through and found no worker (a failed ssh is not "not running":
    # a second worker would take the camera connection from the first)
    st=""; for c in 1 2 3; do sleep 3
      st=$($D/mesh_ssh.sh jetson "pgrep -f '^python -W ignore [a]daptive.py worker' >/dev/null && echo RUN || echo NONE" 2>/dev/null)
      [ -n "$st" ] && break; done
    [ "$st" = NONE ] || break
    echo "jetson worker not running, retry $k"
  done
  watch_cam &
  (cd $HW; source /home/sengar/BTP/venv/bin/activate; timeout $((TOT+300)) python -W ignore adaptive.py worker --camera 127.0.0.1:48101 --device cuda --half --weights ../../weights/yolov8s_visdrone.pt,../../weights/yolov8m_visdrone.pt --label laptop > $R/a2w_${L}_laptop.log 2>&1) &
fi
# the laptop worker runs in the background: through the SSH tunnel its reconnect after the camera's end always
# "succeeds" locally, so it may never exit by itself; the run ends when the camera's result file is there
sleep $((PS*6+30))
# wait for the camera's result file (it is written ~40 s after the run, when the metrics are computed)
for i in $(seq 120); do $D/mesh_ssh.sh camera "test -f ~/hwbench/results/a2_$L.json" 2>/dev/null && break
  $D/mesh_ssh.sh camera "pgrep -f '^$PY -W ignore [a]daptive2.py' >/dev/null" 2>/dev/null || { sleep 5; $D/mesh_ssh.sh camera "test -f ~/hwbench/results/a2_$L.json" 2>/dev/null; break; }
  sleep 5; done
sleep 3
for f in a2_$L.json a2_${L}_dets.npz a2_${L}_livefc.npz a2_$L.log link_$L.txt; do fetch camera $f; done
[ $ST = hier ] && for f in edge_$L.json edge_$L.log; do fetch jetson $f; done
cleanup
if [ -f $R/a2_$L.json ] && [ -f $PINGLOG ]; then
  q=$(awk -F'[][]' -v a=$T_RUN0 -v b=$(date +%s.%N) '$2>=a && $2<=b {n++; if ($0 ~ /no answer/) {l++; r++; if (r>m) m=r} else r=0} END {printf "%d %d %d", n, l, m}' $PINGLOG)
  set -- $q
  if [ $1 -gt 0 ] && { [ $2 -gt $(($1/20)) ] || [ $3 -ge 5 ]; }; then
    A=$R/../_superseded/vid_campaign_mesh2_laptop_link_outage; mkdir -p $A
    mv $R/*_$L.* $R/*_${L}_* $A/ 2>/dev/null
    echo "$L: laptop link lost $2 of $1 pings during the run (longest outage $3 s) - discarded, re-run in pass 2" >> $A/WHY.txt
    echo "laptop link degraded during the run ($2/$1 pings lost, longest $3 s): run discarded"
  fi
fi
[ -f $R/a2_$L.json ] && tail -1 $R/a2_$L.log || echo "NO RESULT for $L"
