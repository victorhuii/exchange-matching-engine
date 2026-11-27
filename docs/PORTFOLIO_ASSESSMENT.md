# Portfolio priorities: quant development and research infrastructure

Engineering review, November 27, 2026. These are project-selection judgments, not a hiring guarantee or a claim that any project is unimprovable.

## What to lead with

| Project | Useful evidence | Best next investment |
| --- | --- | --- |
| Exchange Matching Engine | Original C++ matching, independent reference, durable acknowledgments, recovery, repeatable workload measurements | Bounded randomized failure testing, retained-history memory, recovery scaling |
| MarketLab | Original causal research/execution pipeline and explicit fill assumptions | Real sourced data, frozen protocols, uncertainty and selection-bias controls |
| Disclosure Radar | Data provenance, conservative source handling, delayed-disclosure semantics | A genuinely verified official-source environment; additional sourced coverage |
| Echo Canvas Lab | Original geometry, workers, audio graph lifecycle, revision coordination | Actual cross-browser listening and geometry validation if targeting DSP/media roles |
| Sentinel Workbench | An attributed contribution to an existing security scanner | Maintainer feedback and usability evidence; keep ownership claims precise |
| CrossBeam Review | An attributed local document/evidence workflow with human gates | Independently labeled extraction fixtures and qualified-domain review |

For a quant-focused resume, the original engine and reproducible research work are stronger leads than additional forked dashboards. The forks should be presented as extensions: show the exact new contribution and preserve the original author's credit.

The assessment is consistent with the emphasis on experiment design, dataset generation, time series, feature engineering, and model building in [Jane Street's quantitative research description](https://www.janestreet.com/join-jane-street/position/6302325002/), and data curation/assimilation in [Citadel Securities' research-engineering description](https://www.citadelsecurities.com/careers/details/senior-research-engineer-data/). Requirements vary by role; portfolio evidence complements interview preparation and relevant experience.

## New projects with distinct value

1. **Walk-forward research lab:** a real-data, protocol-first study with train/validation/holdout separation, delayed decisions, transaction-cost accounting, block-bootstrap uncertainty, and explicit multiple-search limitations. Publish methodology and negative findings as carefully as positive ones.
2. **Portfolio risk engine:** covariance estimation, historical VaR/expected shortfall, risk contributions, stress scenarios, and backtesting of risk forecasts with analytic/reference checks.
3. **Market-data replay engine:** sequence integrity, gap detection, deterministic order-book reconstruction, replay checkpoints, bounded parsing, fuzz/regression cases, and transparent throughput measurements.

These form a coherent research-to-risk-to-execution story. An additional introductory indicator dashboard or plain Black–Scholes calculator would add less distinct evidence unless it includes a substantial numerical, validation, or systems contribution.

## Stop rules for polishing

Stop a release when its authorized core workflow works, its key invariants are checked, results are reproducible, attribution/limitations are clear, and no material correctness failure remains. Reopen it for a reproduced bug, new data, or a concrete evaluation gap. More features, more tests that mirror implementation, and larger claimed numbers do not automatically improve resume value.
