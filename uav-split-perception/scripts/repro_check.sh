#!/usr/bin/env bash
# Re-derives every number of the 14-16 Nov board sessions and both papers from the committed raw results, then checks
# that nothing changed (git diff on the derived files) and that both papers build. No board is needed.
# usage: scripts/repro_check.sh            (from uav-split-perception/; PYTHON defaults to ../venv/bin/python)
#        QUICK=1 scripts/repro_check.sh    (skip the campaign re-scoring and the slow checks)
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
PY="${PYTHON:-$(cd .. && pwd)/venv/bin/python}"; [ -x "$PY" ] || PY=$(command -v python3)
export PYTHON="$PY"
H=experiments/results/hardware
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
step() { printf '\n== %s\n' "$*"; }

if [ -z "${QUICK:-}" ]; then
  step "1. re-score the 17 mesh campaigns of 14-16 Nov (cached per run in _eval_cache_mesh.json)"
  for c in mesh4 energy_nov relaynoise_nov topology_nov fps_nov heat_nov plus_nov two_nov plus_nov2 heat_nov2 two_cap \
           final_nov heat_final dvfs_heat dvfs_short budget_nov fix_nov; do
    (cd validation/hardware && "$PY" mesh2_summary.py --campaign "$c" > "$TMP/score_$c.log") || { echo "FAIL $c"; exit 1; }
  done
  step "2. deadline calibration (into a temporary file, compared with the committed one)"
  dirs=""; for c in mesh4 energy_nov relaynoise_nov topology_nov fps_nov heat_nov heat_nov2 plus_nov2 two_nov two_cap \
                    final_nov heat_final dvfs_heat dvfs_short budget_nov fix_nov; do dirs="$dirs $H/vid_campaign_$c"; done
  "$PY" validation/hardware/calib_hw.py $dirs --out "$TMP/calib.json" > /dev/null
  "$PY" - "$TMP/calib.json" "$H/calibration/calib_hw_nov16.json" <<'EOF'
import json, sys
a, b = (json.load(open(f)) for f in sys.argv[1:])
assert a == b, "calibration differs from the committed calib_hw_nov16.json"
print("calibration identical:", a["runs"], "runs")
EOF
  step "3. Theorem 1 and the price rules on every logged update"
  "$PY" paper2/theory_check.py > /dev/null
  "$PY" paper2/price_rules_check.py > /dev/null
  step "4. paper 1: break-even goodput with measured Pi times"
  "$PY" evaluation/pi_measured_break_even.py > /dev/null
  "$PY" evaluation/pi_measured_second_detector.py > /dev/null
  step "4b. laptop strengthening (17 Nov): equivalence, recalibration, skip counterfactual, models, a Jetson camera"
  "$PY" validation/hardware/equivalence_tost.py > /dev/null
  "$PY" validation/hardware/calib_recal.py > /dev/null
  "$PY" validation/hardware/skip_counterfactual.py > /dev/null
  "$PY" validation/hardware/pull_model_check.py > /dev/null
  "$PY" evaluation/t10_model_check.py > /dev/null
  "$PY" evaluation/jetson_measured_break_even.py > /dev/null
  "$PY" paper2/thermal_two_mode.py > /dev/null
  (cd validation/hardware && "$PY" replay_conformal.py --analyse > /dev/null && "$PY" replay_skip.py analyze > /dev/null \
     && "$PY" replay_airflow.py analyze > /dev/null)
fi
step "5. derived numbers: paper 1 board macros, Results Brief 19.24-19.31, Final Report and Novelty Brief (idempotent)"
"$PY" evaluation/board_metrics_paper1.py > /dev/null
"$PY" scripts/report_mesh_nov16.py > /dev/null
"$PY" scripts/report_final_nov16.py > /dev/null
step "6. both papers (every number a generated macro; the builds fail on an undefined macro, citation or reference)"
bash paper2/build.sh
bash paper/build_paper.sh
bash paper/build_conf.sh
step "7. nothing derived may have changed"
changed=$( { git status --porcelain --untracked-files=no -- . ../"AEGIS-UAV Results Brief.md" ../"AEGIS-UAV Results Brief.html" \
              ../"AEGIS-UAV Final Report.html" ../"AEGIS-UAV Novelty Brief.html";
            git status --porcelain -- experiments/results paper/generated_tables paper2/generated | grep '^??' || true; } \
          | grep -v -E '\.(pdf|aux|log|bbl|blg|out)$' || true)
if [ -n "$changed" ]; then echo "CHANGED (not reproduced bit for bit):"; echo "$changed"; exit 1; fi
echo "OK: every derived file reproduced identically"
