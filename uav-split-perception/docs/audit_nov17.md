# Independent audit of the laptop-strengthening numbers, 17 Nov 2026

`scripts/audit_nov17.py`: own code from the raw result files (score caches, frame logs, sweep files); compared with paper 2's `generated/metrics.tex` and paper 1's `generated_tables/board_metrics.tex`.

| quantity | recomputed | macro | |
| --- | --- | --- | --- |
| equivalence no prices: 90 % CI low | -0.00346674 | -0.0035 | ok |
| equivalence no prices: 90 % CI high | -0.000818165 | -0.0008 | ok |
| equivalence no prices: pairs | 9 | 9 | ok |
| equivalence no prices: shown | True | yes | ok |
| equivalence heat price: 90 % CI low | -0.0020222 | -0.0020 | ok |
| equivalence heat price: 90 % CI high | 0.00154446 | +0.0015 | ok |
| equivalence heat price: pairs | 9 | 9 | ok |
| equivalence heat price: shown | True | yes | ok |
| equivalence final vs v4.1: 90 % CI low | -0.00315673 | -0.0032 | ok |
| equivalence final vs v4.1: 90 % CI high | 0.000503397 | +0.0005 | ok |
| equivalence final vs v4.1: pairs | 10 | 10 | ok |
| equivalence final vs v4.1: shown | True | yes | ok |
| equivalence final vs v4.1, multihop: 90 % CI low | -0.00569679 | -0.0057 | ok |
| equivalence final vs v4.1, multihop: 90 % CI high | -0.000761281 | -0.0008 | ok |
| equivalence final vs v4.1, multihop: pairs | 5 | 5 | ok |
| equivalence final vs v4.1, multihop: shown | False | no | ok |
| equivalence capped hold: 90 % CI low | -0.00532562 | -0.0053 | ok |
| equivalence capped hold: 90 % CI high | 0.00248838 | +0.0025 | ok |
| equivalence capped hold: pairs | 5 | 5 | ok |
| equivalence capped hold: shown | False | no | ok |
| equivalence capped hold + guard: 90 % CI low | -0.00414663 | -0.0041 | ok |
| equivalence capped hold + guard: 90 % CI high | 0.000651721 | +0.0007 | ok |
| equivalence capped hold + guard: pairs | 5 | 5 | ok |
| equivalence capped hold + guard: shown | True | yes | ok |
| equivalence budget 2.4 vs 2.8: 90 % CI low | -0.00279151 | -0.0028 | ok |
| equivalence budget 2.4 vs 2.8: 90 % CI high | 0.000899129 | +0.0009 | ok |
| equivalence budget 2.4 vs 2.8: pairs | 6 | 6 | ok |
| equivalence budget 2.4 vs 2.8: shown | True | yes | ok |
| held-out frames | 387075 | 387,075 | ok |
| held-out ECE, logged p_on | 0.0569248 | 0.057 | ok |
| held-out ECE, isotonic (one map) | 0.0055498 | 0.006 | ok |
| held-out ECE, per-path isotonic, jetson | 0.00404169 | 0.004 | ok |
| jetson: frames predicted late, on time % | 94.227 | 94 | ok |
| held-out ECE, per-path isotonic, laptop | 0.00680963 | 0.007 | ok |
| laptop: frames predicted late, on time % | 49.3531 | 49 | ok |
| T10 model: median |error| % (cells >= 1/s) | 7.80091 | 8 | ok |
| T10 model: cells | 30 | 30 | ok |
| Jetson camera: codes' onboard ms, min | 6.57397 | 6.6 | ok |
| Jetson camera: codes' onboard ms, max | 9.53818 | 9.5 | ok |
| Auto-Split advantage vs raw image (1.0 / 0.08) | 12.5 | 12.5 | ok |
| Auto-Split advantage vs JPEG q60 (0.15 / 0.08) | 1.875 | 1.9 | ok |
| 30 fps measured sAP_fc (3 runs) | 0.196553 | 0.197 | ok |

**0 mismatches** in 42 checks.
