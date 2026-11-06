# Task backlog

Status: T01, T02, T03, R01/R02, Milestone 1A, Milestone 1B, Milestone 1C, and Parallel Multi-Agent Cycle (Codex Tasks C1–C3 + Gemini Tasks G1–G3) COMPLETED; 128/128 unit, integration, backtesting, reconciliation, and Streamlit AppTest UI tests passing with zero live API calls.

## T01 - Reproduce and verify rules [DONE]
Run the locked quality gate and demo locally. Run the blocked rules check. Inspect official
competition evidence without bypassing access restrictions. Update STATE with environment,
exact commands, rule unknowns, and source evidence. Gate: reproducible local checks and
honest status; official-rule access may remain blocked.

## T02 - Authorized local data import [DONE]
Extend the supplied canonical CSV parser into an import command with immutable snapshot,
source permission metadata, rejection report, and idempotent manifest. Test French number
formats only in a source-specific adapter, not by silently guessing in the canonical parser.
Gate: valid/invalid/no-trade/duplicate/corrected fixtures; byte-for-byte reproducibility.

## T03 - Instrument master and real sessions [DONE]
Add dated identifiers, listing history, official market sessions and suspensions. Distinguish
holiday, no trade, missing file, stale quote, and delisted instrument. Gate: schema and
calendar fixtures; reject unsupported history rather than forward-filling it.

## R01 & R02 - BVMT Data Sources, GitHub Reuse Evaluation & 25-Model Alibaba AI Plan [DONE]
Research official BVMT/CMF data sources (`docs/BVMT_DATA_SOURCES.md`), evaluate Qlib, Backtrader,
VectorBT, and FinGPT (`docs/GITHUB_REUSE_EVALUATION.md`), design the 3-role LLM extraction and
complete 25-model Alibaba Cloud Model Studio budget/quota architecture (`docs/LLM_TRADING_INTELLIGENCE.md`,
`docs/ALIBABA_INTEGRATION_PLAN.md`, `docs/LLM_BENCHMARK_PLAN.md`, `configs/llm_budget.example.json`),
and specify the permanent zero-cloud architecture (`docs/LOW_COST_ARCHITECTURE.md`) and research
roadmap (`docs/TRADING_RESEARCH_ROADMAP.md`).

## T04 - Session-aware baseline & Milestone 1A Alibaba Offline/Mocked Pilot [DONE]
Implement lookbacks over exchange sessions, verified raw/adjusted separation, liquidity
filtering, lagged features, and a research shortlist (`src/bvmt/features.py`), plus the
offline-default budget-gated Alibaba client, live standard-library HTTPS transport, document
chunk index, embedding sidecar, BM25 fallback, and mocked tests (`src/bvmt/llm.py`,
`tests/test_llm_budget.py`, `bvmt llm-dry-run`, `bvmt session-rank`).

## Milestone 1C (T05 + T09 + T10 Slice) - Local Trading Dashboard, Manual Portfolio Ledger & Notifications [DONE]
Implemented the `Decimal` manual portfolio & order ledger (`src/bvmt/ledger.py`), 5-state
recommendation generator with `recommendation_id` and 10% cap / `0.50%` fee checks
(`src/bvmt/recommendations.py`), local notification & power-off catch-up engine
(`src/bvmt/notifications.py`), 6-page local Streamlit decision-support dashboard
(`src/bvmt/dashboard.py`), CLI commands (`portfolio-init`, `portfolio-status`, `order-submit`,
`order-fill`, `order-close`, `recommend`, `dashboard`), one-click Windows launcher
(`start_bvmt.bat`), and full end-to-end manual trading simulation & failure-mode tests
(`tests/test_milestone_1c.py`).
Evidence (2026-11-05): Passed 90/90 unit and integration tests and full quality gate.

## T05 - Historical Backtesting Foundation & Competition Portfolio Reconciliation (Tasks C1–C3 & G1–G3) [DONE]
Implemented in parallel across `codex/data-research` (`4ebfff1`) and `gemini/dashboard` (`d3f9bf8`) and merged into `main`:
- **C1 (`src/bvmt/llm.py`)**: Regional DashScope endpoints, list-content chat parsing, DashScope error classification, and offline `check_readiness()`.
- **C2 (`src/bvmt/data.py`)**: Official BVMT `histo_cotation` historical CSV adapter (`bvmt_histo_cotation`), zero-volume untraded bar normalization, `raw_source.csv` + `source_sha256` preservation, and expanded `DataQualityReport`.
- **C3 (`src/bvmt/execution.py`)**: Deterministic research-only multi-session backtest engine (`run_historical_backtest`) with strict T+1 fills, shared volume participation caps, partial fills & order age expiration, `0.50%` fee accounting, cash and equal-weight benchmarks, and max drawdown.
- **G1 & G2 (`src/bvmt/ledger.py`)**: Competition account CSV import/export (`parse_account_holdings_csv`, `parse_account_transactions_csv`, `parse_account_pending_orders_csv`), session-by-session `compute_valuation_history`, read-only `reconcile_with_snapshot` (detecting all 6 discrepancy categories), and confirmation-gated `apply_reconciliation_snapshot`.
- **G3 (`src/bvmt/dashboard.py`)**: Dataset discovery (`discover_available_bar_datasets`), data freshness lag indicators, portfolio valuation history tab, competition account reconciliation UI, and transaction fill history.
Evidence (2026-11-06): Passed 128/128 tests and full quality gate on `main`.

## T06 - Walk-forward evaluation on imported official BVMT history [NEXT]
Create cash/equal-weight/momentum benchmarks, purged chronological folds, frozen holdout,
experiment registry, cost/liquidity sensitivity, and reproducible manifests. Gate: no
performance claims without actual measured results and a disclosed sample.

## T07 - Event intelligence [TODO]
Parse permitted official disclosures into schemas/event.schema.json with evidence spans,
entity matching, publication cutoff, and human review. Test a malicious document instruction.
Gate: extraction quality on a hand-labeled set; unsupported impacts remain unknown.

## T08 - ML challenger [TODO]
Compare LightGBM to the baseline using the same folds, execution model and eligibility.
Gate: predefined promotion rule; no improvement means keep the simpler model.
