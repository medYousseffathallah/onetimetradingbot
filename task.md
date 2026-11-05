# Task backlog

Status: T01, T02, T03, R01/R02, Milestone 1A (Alibaba Budget-Gated Provider, Live HTTPS Transport, Document Index & Embedding Sidecar), Milestone 1B (T04 Session-Aware Quantitative Baseline), Milestone 1C (Manual Portfolio Ledger, 5-State Recommendation Engine, Local Alert Center, 6-Page Streamlit Dashboard & Windows Launcher), and GitHub Parallel-Agent Worktree Setup (`main`, `gemini/dashboard`, `codex/data-research`) COMPLETED; 91/91 unit, integration, and Streamlit AppTest UI tests passing with zero live API calls.

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

## T05 - Historical Backtesting Adapter (Backtrader / Multi-Session Simulation) [NEXT]
Audit Backtrader defaults and license; connect `PortfolioLedger` to multi-session historical
walk-forward simulation (`T06`) once official BVMT historical CSVs are imported into
`data/processed/`.

## T06 - Walk-forward evaluation [TODO]
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
