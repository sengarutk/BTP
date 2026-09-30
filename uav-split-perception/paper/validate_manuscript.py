#!/usr/bin/env python3
"""Pre-build checks: citations, figures, generated tables, macros, labels, environments."""

import re
import sys
from collections import Counter
from pathlib import Path

PAPER = Path(__file__).resolve().parent
tex = (PAPER / "main.tex").read_text(encoding="utf-8")
bib = (PAPER / "references.bib").read_text(encoding="utf-8")
errors = []

bib_keys = set(re.findall(r"@\w+\s*\{\s*([^,\s]+)\s*,", bib))
cited = {k.strip() for g in re.findall(r"\\cite\{([^}]+)\}", tex) for k in g.split(",")}
if cited - bib_keys:
    errors.append(f"undefined citations: {sorted(cited - bib_keys)}")
if bib_keys - cited:
    print(f"note: {len(bib_keys - cited)} unused bibliography entries: {sorted(bib_keys - cited)}")

for g in re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", tex):
    if not (PAPER / "figures" / g).exists():
        errors.append(f"missing figure figures/{g} (run `make figures`)")
for t in re.findall(r"\\input\{([^}]+)\}", tex):
    if not (PAPER / t).exists():
        errors.append(f"missing input {t} (run `make tables`)")

defined = set()
for macros_file in (PAPER / "generated_tables").glob("*metrics.tex"):  # autogen_metrics.tex, gen_metrics.tex
    defined |= set(re.findall(r"\\newcommand\{\\([A-Za-z]+)\}", macros_file.read_text()))
used = set(re.findall(r"(?<!\\)\\([A-Z][A-Za-z]+)\b", tex))
builtin = {"Pr", "Big", "Bigg", "Bigl", "Bigr", "Biggl", "Biggr", "Delta", "Gamma", "Lambda", "Theta", "Omega", "Sigma", "Phi", "Psi", "Pi"}
missing = sorted(m for m in used - defined - builtin if not m.startswith("IEEE"))
if missing:
    errors.append(f"undefined number macros: {missing} (run `make tables`)")

labels = set(re.findall(r"\\label\{([^}]+)\}", tex))
refs = set(re.findall(r"\\ref\{([^}]+)\}", tex))
if refs - labels:
    errors.append(f"undefined \\ref targets: {sorted(refs - labels)}")
if Counter(re.findall(r"\\begin\{([^}]+)\}", tex)) != Counter(re.findall(r"\\end\{([^}]+)\}", tex)):
    errors.append("unbalanced \\begin/\\end environments")

if errors:
    print("Manuscript validation FAILED:\n  - " + "\n  - ".join(errors))
    sys.exit(1)
print(f"Manuscript validation passed ({len(cited)} citations, {len(used & defined)} generated macros).")
