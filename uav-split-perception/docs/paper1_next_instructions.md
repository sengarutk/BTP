Excellent work, and thank you for checking the data instead of trusting my numbers. You were right on both points:
the placement model is 0.8–2.0× (up to 4.2× for three devices), not "within about 30 %". I checked one row myself: Pi
JPEG → laptop, model 30 fps against 15.2 fps live, which is 2.0×. The relay gain is 0.05. Keep your values.

Do the steps below in order, on the `paper1-arxiv` branch. After each step: rebuild (`bash paper/build_paper.sh`),
run `python scripts/verify_math_proofs.py` (must stay 40/40) and commit. All the old rules still apply.

---

## Step 1: Git identity (repository-local only)

Use the identity of all earlier commits, for this repository only, not globally:

```
git config user.name "sengarutk"
git config user.email "cs23bt026@iitdh.ac.in"
```

Then look at the authors of your 7 commits (`git log main..paper1-arxiv --format='%h %an <%ae>'`):
- if any commit has a different or empty author, fix it with
  `git rebase main --exec "git commit --amend --no-edit --reset-author"`;
- this is safe because the branch has not been pushed;
- afterwards check that the trees are unchanged: `git diff <old-tip> HEAD` must be empty.

## Step 2: Make the placement-model accuracy a generated number

Right now 0.8–2.0× and 4.2× come from a calculation you ran by hand. Rule 1 says every number comes from a result
file, so:

1. **Script:** write `evaluation/placement_model_check.py`.
   - It reads `experiments/results/hardware/placements.csv` (model) and `live_summary.csv` (live).
   - It matches each live placement to its model row, and computes model fps ÷ live median fps.
   - It writes a new result file, `experiments/results/hardware/placement_model_check.json`, with:
     - every matched pair;
     - the min and max ratio for one- and two-device chains, and separately for three-device chains;
     - whether the model's ranking puts every image-offload placement above every split.
   - It writes a new file; it does not modify an existing result file.
2. **Matching:** print the matching table in your status, so I can check it. If a live placement has no clear model
   row, leave it out and say which.
3. **Macros:** add them to `evaluation/make_hardware.py`, read from that JSON, and use them in the Placements
   paragraph instead of typed values. Add them to `docs/claims_to_evidence.md`.
4. **`docs/hardware_results.md` §5:** correct the "within about 30 %" sentence.
   - Replace it with the computed values and a note: "corrected 9 Nov 2026; computed by
     `evaluation/placement_model_check.py`".
   - Keep the rest of the file as it is.
5. **Test:** add a small test in `tests/` that runs the script and checks the JSON has the expected keys.

## Step 3: Consistency checks across the repository

1. **Renamed macros:** list the three macros you renamed in Phase 1, with old and new names. Search the whole
   repository for the old names: `grep -rn "<old name>" --include=*.py --include=*.tex --include=*.md .`. That
   includes `paper2/`, `scripts/` and `docs/`. Update every use, or tell me where an old name is still used and why.
   - `scripts/report_part4_oct30.py` reads `hw_metrics.tex` macros by name (for example `HwSimRuns`, `HwSimR`): make
     sure each name it reads still exists.
   - `paper2/` must still build (`bash paper2/build.sh`, if LaTeX is available there).
2. **Ledger completeness:**
   - Collect every macro name defined in `paper/generated_tables/*.tex`, and every macro entry in
     `docs/claims_to_evidence.md`.
   - Report the two counts and any macro without an entry. Every macro needs one.
   - Confirm that no entry from the old ledger was lost: compare against `git show main:docs/claims_to_evidence.md`.
3. **Meaning changes:** give me a list of every sentence in `main.tex` whose *claim* changed during the revision, not
   just its wording. For each: old claim, new claim, the source file that justifies the change. I will check each one
   on my side.

## Step 4: Test count in the README

On my Linux laptop the full suite gives **129 passed** (`pytest -q tests`, today). Your Windows run collects fewer,
because two modules need `fcntl`, and 3 tests need Linux. Write the README line as:

> 129 tests (`pytest -q tests`, on Linux; some tests need Linux-only features, CUDA or a C++ compiler and are skipped
> elsewhere).

If Step 2 added a test, make it 130. I will re-run the count here before merging.

## Step 5: Repository URL

The code is at `https://github.com/sengarutk/BTP`. **Do not put it in the paper yet.**
- Keep `REPO-URL` as the placeholder.
- The repository may be private and contains far more than paper 1. I will decide between making it public and
  publishing a cleaned copy for the paper, and give you the final URL.
- Make sure `paper/make_arxiv.py` **refuses to build** while `REPO-URL` or the author placeholder is still in
  `main.tex`. It should print exactly which placeholders remain.

## Step 6: Author block

Leave the placeholder. When I send the names, affiliations and email, you will:
- fill them in, plus the acknowledgements I send, and nothing else;
- re-run `bash paper/build_paper.sh` and `python paper/make_arxiv.py`;
- re-check pages 1 and 15.

Don't invent any part of it.

## Step 7: Final checks and push

1. **Full check, one last time:**
   - build: 0 warnings, 0 overfull boxes;
   - proof checker: 40/40;
   - `pytest -q tests`: report the result;
   - render all pages and check them.
2. **Change log:** update `paper/CHANGELOG_paper1.md` with Steps 1–6.
3. **Push only the branch:** `git push -u origin paper1-arxiv`.
   - Do not merge to `main` and do not push `main`.
   - Do not commit `.claude/settings.local.json`, any `*:Zone.Identifier` file, `yolov8s.pt`, or the `paper/arxiv/`
     folder or `arxiv.zip`.
   - Check with `git status` and `git diff --stat main..paper1-arxiv` before pushing, and paste both in your report.
4. **Report to me:**
   - the commit list;
   - the check results;
   - the placement-matching table from Step 2;
   - the renamed-macro list and the meaning-change list from Step 3;
   - anything unresolved.

I will pull the branch on the other laptop, re-run everything on Linux, and merge it myself.

---

## Not for this chat

The joint-training experiment and the "when does a split pay off" rule are planned for the journal version. They run
on the other laptop (GPU and datasets), so don't start them here. The arXiv version goes out with what we have now.
