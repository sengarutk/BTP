#!/bin/bash
# dryrun_board_session.sh - laptop-only dry run of the half-day board session (hardening plan Phase 5; 11 Nov 2026).
#   Runs the three campaigns (energy, noisy relay, REPS=2 planner) against stand-ins: mesh_ssh.sh always succeeds, a
#   local listener takes the tunnel port 48104, and arun_mesh.sh keeps its real strategy table but only records the
#   camera command and writes an empty result. Then every distinct command is parsed by adaptive2.py's own argument
#   parser and its scenario is expanded. Touches no board, no network rule and no result file of the repository.
#   usage: validation/hardware/tools/dryrun_board_session.sh [WORKDIR]   -> prints run counts and "failures 0"
set -e
REPO=$(cd "$(dirname "$0")/../../.." && pwd); S=${1:-$(mktemp -d)}; T=$S/validation/hardware/tools
rm -rf "$S/validation" "$S/experiments"; mkdir -p $T $S/experiments/results/hardware
cp $REPO/validation/hardware/tools/campaign_{energy_nov,relaynoise_nov,mesh4}.sh $T/
printf '#!/bin/bash\nexit 0\n' > $T/mesh_ssh.sh
{ sed -n '1,/^esac$/p' $REPO/validation/hardware/tools/arun_mesh.sh; cat <<'EOS'
[ $ST = hier ] && PATHS=jetson || PATHS=laptop,jetson
echo "CMD $L :: --policy $POL $COMMON $X --paths $PATHS" >> $(dirname $R)/commands.txt
echo '{}' > $R/a2_$L.json; echo '{"fake": true}'
EOS
} > $T/arun_mesh.sh; chmod +x $T/*.sh
python3 -c "import socket,time;s=socket.socket();s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('127.0.0.1',48104));s.listen();time.sleep(300)" & LP=$!
trap "kill $LP 2>/dev/null" EXIT; sleep 1
bash $T/campaign_energy_nov.sh | tail -1; bash $T/campaign_relaynoise_nov.sh | tail -1; REPS=2 bash $T/campaign_mesh4.sh | tail -1
cd $REPO/validation/hardware && ${PY:-/home/sengar/BTP/venv/bin/python} tools/dryrun_parse_check.py $S/experiments/results/hardware/commands.txt
