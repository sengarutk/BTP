# Reference results of the open benchmark

Generated on 11 Nov 2026 by `python -m benchmark.aegis_bench score benchmark/example_policy.py --seeds 1-5`
(`experiments/results/benchmark_scores/score_report.json`). The table gives the mean over seeds 1–5, with 20-s phases.

- **Streaming AP** is scored with forecaster v2, as in the papers.
- **Clairvoyant v4.1** and **best fixed** come from the stored oracle (`replay/oracle_oct29_plant`). Best fixed is the best of the 17 fixed configurations, chosen per seed with hindsight.

| Scenario | Example policy | v4.1 | Clairvoyant v4.1 | Best fixed (hindsight) | Pi power, example / v4.1 (W) |
| --- | --- | --- | --- | --- | --- |
| mission | 0.0287 | 0.0577 | 0.0577 | 0.0481 | 3.21 / 3.31 |
| random | 0.0303 | 0.0491 | 0.0503 | 0.0436 | 2.99 / 3.16 |

A new controller is worth reporting when it beats v4.1 on the same seeds. Use the paired difference per seed, since the runs share their link draws.
