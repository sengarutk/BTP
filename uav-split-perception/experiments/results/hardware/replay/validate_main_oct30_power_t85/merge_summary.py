#!/usr/bin/env python3
"""Merge the per-group replay summaries (legacy_<scenario>_g<k>/replay_summary_20s.json) into replay_summary_20s.json,
the input of validation/hardware/replay_check.py. Fails if any of the 240 runs is missing or duplicated."""
import json
from pathlib import Path

D = Path(__file__).resolve().parent
rows = [r for f in sorted(D.glob("legacy_*_g*/replay_summary_20s.json")) for r in json.load(open(f))]
keys = [(r["policy"], r["scenario"], r["seed"]) for r in rows]
assert len(keys) == len(set(keys)) == 240, (len(keys), len(set(keys)))
json.dump(rows, open(D / "replay_summary_20s.json", "w"), indent=1)
print("merged", len(rows))
