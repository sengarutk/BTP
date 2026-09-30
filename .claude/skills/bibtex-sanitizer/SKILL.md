---
name: bibtex-sanitizer
description: Audit every citation in references.bib against live CrossRef APIs.
---
# Bibliography Integrity Check
1. Query CrossRef API for every DOI in `references.bib`.
2. Flag and report any fake, unverified, or mismatched citations.
3. Replace missing DOIs with real, verified links.