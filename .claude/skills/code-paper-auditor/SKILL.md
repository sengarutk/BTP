---
name: code-paper-auditor
description: Verify that code implementation strictly matches paper methodology and metrics.
---
# Code vs Paper Audit Protocol
1. Scan `src/` or script files and compare them against Section 3 (Methodology) in `paper.tex`.
2. Check that variable names, hyperparameters (learning rate, batch size, threshold values), and equations in the LaTeX file match the actual Python implementation.
3. Run `pytest` locally to confirm code executes end-to-end without errors.