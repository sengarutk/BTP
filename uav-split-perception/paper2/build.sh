#!/usr/bin/env bash
# Builds paper2/main.pdf: numbers from the result files, then LaTeX; fails on undefined macros, citations or references.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
rm -f main.aux main.bbl   # stale files of an earlier run are read before bibtex regenerates them
/home/sengar/BTP/venv/bin/python make_metrics.py > /dev/null
/home/sengar/BTP/venv/bin/python make_figures.py > /dev/null
used=$(grep -o '\\[A-Z][A-Za-z]*{}' main.tex | sed 's/[\\{}]//g' | sort -u)
for m in $used; do grep -q "newcommand{\\\\$m}" generated/metrics.tex || { echo "undefined macro $m"; exit 1; }; done
pdflatex -interaction=nonstopmode -halt-on-error main.tex > /dev/null
bibtex main > /dev/null
pdflatex -interaction=nonstopmode -halt-on-error main.tex > /dev/null
pdflatex -interaction=nonstopmode -halt-on-error main.tex > /dev/null
if grep -E "undefined|multiply defined" main.log; then echo "unresolved references"; exit 1; fi
echo "Built paper2/main.pdf ($(grep -c 'newcommand' generated/metrics.tex) generated numbers)"
