#!/usr/bin/env bash
# Builds paper/main_conf.pdf (the conference version). Fails if validation or LaTeX fails.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
PYTHON="${PYTHON:-python3}"
"$PYTHON" validate_manuscript.py main_conf.tex
rm -f main_conf.aux main_conf.bbl
pdflatex -interaction=nonstopmode -halt-on-error main_conf.tex >/dev/null
bibtex main_conf >/dev/null
pdflatex -interaction=nonstopmode -halt-on-error main_conf.tex >/dev/null
pdflatex -interaction=nonstopmode -halt-on-error main_conf.tex >/dev/null
if grep -E "undefined|Citation .* undefined|multiply defined" main_conf.log; then
    echo "ERROR: unresolved references in main_conf.log" >&2
    exit 1
fi
echo "Built paper/main_conf.pdf ($(grep -o 'Output written on main_conf.pdf ([0-9]* pages' main_conf.log | grep -o '[0-9]* pages'))"
