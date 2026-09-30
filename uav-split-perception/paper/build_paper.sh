#!/usr/bin/env bash
# Builds paper/main.pdf. Fails (non-zero exit) if validation or LaTeX fails.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
PYTHON="${PYTHON:-python3}"

"$PYTHON" validate_manuscript.py

if ! command -v pdflatex >/dev/null 2>&1 || ! command -v bibtex >/dev/null 2>&1; then
    echo "ERROR: pdflatex/bibtex not found (e.g. apt-get install texlive-latex-extra texlive-publishers)" >&2
    exit 1
fi

pdflatex -interaction=nonstopmode -halt-on-error main.tex >/dev/null
bibtex main >/dev/null
pdflatex -interaction=nonstopmode -halt-on-error main.tex >/dev/null
pdflatex -interaction=nonstopmode -halt-on-error main.tex >/dev/null

if grep -E "undefined|Citation .* undefined|multiply defined" main.log; then
    echo "ERROR: unresolved references in main.log" >&2
    exit 1
fi
echo "Built paper/main.pdf"
