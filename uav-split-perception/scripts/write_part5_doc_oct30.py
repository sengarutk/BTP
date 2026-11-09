#!/usr/bin/env python3
"""Writes docs/laptop_additions_2026-10-30_part5.md (the 19.12 section text of report_part5_oct30.py, then details that
are not in the brief). Run after report_part5_oct30.py. The learned-bottleneck section of docs/claims_to_evidence.md is
written by evaluation/make_learned.py itself (evaluation/ledger.py), not here."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import report_part5_oct30 as B  # noqa: E402
from report_parts_oct22 import html_to_md  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LB = ROOT / "experiments" / "results" / "learned_bottleneck"


def main():
    body = html_to_md(B.section()).split("\n", 1)[1]
    rows = sorted((json.load(open(f)) for f in LB.glob("train_*.json")), key=lambda r: r["cut"])
    tr = "\n".join(f"| k{r['cut']}, {r['channels']} channels, width {r.get('width', 64)}, stride {r.get('stride', 2)}, "
                   f"{r.get('dec_layers', 1)} decoder layers | {r['epochs']} | {r['epochs_log'][-1]['holdout_neck_loss']:.3f} | "
                   f"{r['epochs_log'][-1]['minutes']:.0f} |" for r in rows)
    doc = f"""# Laptop-only additions, part 5 (30 Oct 2026): a learned feature-compression baseline, and the second paper

Continues `laptop_additions_2026-10-30_part4.md`. Brief section 19.12 (built by `scripts/report_part5_oct30.py`; the
text below is the same section, followed by details that are not in the brief).
{body}
## Details not in the brief

### Training runs (`experiments/results/learned_bottleneck/train_*.json`, laptop RTX 4050)

| Configuration | Epochs | Held-out neck loss (last epoch; MSE / teacher variance) | Minutes |
| --- | --- | --- | --- |
{tr}

The first configuration (k4, 8 channels, width 64, 1 decoder layer, 12 epochs) was a pilot; the family reported in the
brief and the paper is width 128, 2 decoder layers, 20 epochs (`learned_bottleneck.py`, `ARCH`). Batch 8, AdamW
(learning rate 2e-3, one-cycle), mixed precision, horizontal flips, seed 0.

### Checks

- The replica of the detector's forward pass used for training (`run_detector`) equals the real model's neck outputs
  bit for bit (checked on a 640 x 384 input).
- Every evaluation reproduces the unsplit baseline (0.26706) and the JPEG accuracies of the VisDrone codec table
  (q50–q95 identical to the last digit); the post-hoc measurement hook leaves the detector unchanged.
- The validator's warm-up pass on a dummy 640 x 640 frame (549 hook calls for 548 images) is dropped from every size
  average; the measurements made before the fix are archived in `_superseded/learned_bottleneck_warmup_oct30/`.
- Encoder MACs are counted with thop on a 640 x 640 input; layers 0..k use the topology file of the post-hoc rows, so
  learned and post-hoc rows share one basis (`learned_bottleneck_system.py`).
- Tests: `tests/test_learned_bottleneck.py`.

### Approximations in the system model

- JPEG q10–q35 have no row in the VisDrone timing table; they take q50's encode and server times.
- The learned codes' server time is the post-hoc split's server time at the same cut plus the decoder measured on the
  laptop GPU; onboard non-DNN work is quantisation + zstd measured on the laptop, scaled like every other option.
"""
    (ROOT / "docs" / "laptop_additions_2026-10-30_part5.md").write_text(doc)
    print("docs/laptop_additions_2026-10-30_part5.md written (the ledger section comes from evaluation/make_learned.py)")


if __name__ == "__main__":
    main()
