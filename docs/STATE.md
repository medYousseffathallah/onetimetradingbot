# Working state

## Current checkpoint
**Parallel Multi-Agent Development Cycle (Codex Tasks C1–C3 + Gemini Tasks G1–G3)** integrated on `main` on 2026-11-06 (Windows PowerShell, CPython 3.13.18 in `.venv`, `uv 0.13.7`, `streamlit 1.66.1`, `codex-cli 0.166.0`).
All **128 automated unit, integration, backtesting, reconciliation, and Streamlit `AppTest` UI tests** and the full developer quality gate (`uv run python scripts/check.py`) pass with **zero live API calls**, **zero autonomous order submission**, and **zero paid cloud resources**.
Central GitHub repository synchronized across `main` (`c:\Users\Thinkcenter\Desktop\BVMT\bvmt-starter-kit`), `gemini/dashboard` (`c:\Users\Thinkcenter\Desktop\BVMT\bvmt-gemini-dashboard`), and `codex/data-research` (`c:\Users\Thinkcenter\Desktop\BVMT\bvmt-codex-research`).

## Implemented
- Agent instructions and skills; portable installation helper; real resolved `uv.lock` (including `streamlit 1.66.1` in the `dashboard` extra).
- Content-addressed local snapshots (`src/bvmt/snapshots.py`) with symlink/path-safety checks, explicit `permission_status` and `parser_version` metadata, and atomic file writes with overwrite refusal on differing content.
- Typed canonical CSV/bar validation and explicit French BVMT CSV source adapter (`src/bvmt/data.py`).
- Dated instrument master, official-source-backed BVMT exchange calendar (`Africa/Tunis`), and observation coverage diagnostics (`src/bvmt/calendar.py`).
- **Milestone 1A — Alibaba Model Studio Budget-Gated Provider, Live HTTPS Transport & Local Document Index (`src/bvmt/llm.py`)**:
  - Loads all 25 models from `configs/llm_budget.example.json` (`load_llm_budget_config`) with `console_free_quota_only_verified: true` (reflecting the user's "Stop on Exhaustion / Free Quota Only" console setting) and full `1,000,000`-token allowances (`safety_reserve: 0`, `max_input_chars: 80000`, `max_completion_tokens: 4000`).
  - Implements the standard-library live HTTPS client `DashScopeOpenAICompatibleTransport` (`/compatible-mode/v1/chat/completions` and `/compatible-mode/v1/embeddings`) with explicit rate-limit (`LLMRateLimitError`, HTTP `429`) and free-quota exhaustion (`LLMQuotaExhaustedOrForbiddenError`, HTTP `402`/`403`) classification, while remaining offline by default (`network_enabled: false`) until explicitly authorized.
  - Deterministic document chunking (`chunk_financial_document`), embedding sidecar persistence (`embed_chunks_with_sidecar`), and point-in-time retrieval (`search_document_index`) supporting both pre-computed vector cosine similarity (`cosine_embedding_sidecar`) and automatic post-expiration BM25 lexical fallback (`bm25_lexical_fallback`).
- **Milestone 1B — T04 Session-Aware Quantitative Baseline (`src/bvmt/features.py`)**:
  - `rank_session_baseline` computes 20-session and 60-session momentum, relative strength vs. the eligible universe benchmark, realized 20-session volatility, 20-session median turnover, and trading frequency strictly over verified open `ExchangeSession` dates up to the decision cutoff.
- **Milestone 1C — Manual Portfolio Ledger, 5-State Recommendation Engine, Local Alert Center & 6-Page Streamlit Dashboard**:
  - **Manual Portfolio Ledger (`src/bvmt/ledger.py`)**: `PortfolioLedger` tracks `Decimal` initial/settled/reserved/available cash, share holdings, average acquisition cost (including `0.50%` buy fees), realized and unrealized P&L, `0.50%` buy/sell fees, owned-share restrictions on sells, `10%` single-stock concentration cap enforcement, duplicate-order prevention, partial fills (`PARTIALLY_FILLED`), terminal states (`EXECUTED`, `CANCELLED`, `REJECTED`, `EXPIRED`), and an immutable append-only audit log (`LedgerAuditEntry`).
  - **5-State Recommendation Engine (`src/bvmt/recommendations.py`)**: `generate_recommendations` connects `rank_session_baseline` and verified corporate event citations to `PortfolioLedger` to emit `BUY CANDIDATE`, `HOLD`, `REDUCE`, `SELL CANDIDATE`, and `NO TRADE` cards (`RecommendationCard`) with deterministic `recommendation_id`, fee-adjusted sizing (`8.5%` target allocation buffer under the `10.0%` competition cap, `10%` of 20-session median turnover liquidity cap), pending-order conflict locks, and explicit blocked reasons.
  - **Local Notification & Catch-Up Center (`src/bvmt/notifications.py`)**: `NotificationCenter` evaluates, deduplicates, and persists alerts across 5 categories (`ALERT_SIGNAL_HIGH`, `ALERT_RISK_CONCENTRATION`, `ALERT_ORDER_EXPIRY`, `ALERT_DATA_STALE`, `ALERT_EVENT_MATERIAL`), including automatic startup catch-up detection when the computer was powered off across open exchange sessions.
  - **6-Page Local Streamlit Dashboard (`src/bvmt/dashboard.py`) & Windows Launcher (`start_bvmt.bat`)**: Renders `Overview`, `Stock Opportunities`, `Portfolio`, `Manual Order Journal`, `Research and Documents`, and `System Health` on `http://127.0.0.1:8501`, prominently distinguishing `SYNTHETIC DEMO MODE` and `COMPETITION RULES STATUS: BLOCKED`.
  - **CLI (`src/bvmt/cli.py`)**: `demo`, `rules-check`, `validate-csv`, `import-csv` (now supporting `--format bvmt_histo_cotation`), `coverage-check`, `session-rank`, `llm-dry-run`, `portfolio-init`, `portfolio-status`, `order-submit`, `order-fill`, `order-close`, `recommend`, and `dashboard`.
- **Parallel Multi-Agent Cycle (`codex/data-research` + `gemini/dashboard`)**:
  - **Codex C1 (`src/bvmt/llm.py`)**: Regional DashScope endpoints (`intl`, `us`, `cn`, workspace URL allowlist), list-content chat parsing, DashScope error classification (`FreeTierOnly`, `Throttling.RateQuota`, `Arrearage`), and `AlibabaModelStudioProvider.check_readiness()`.
  - **Codex C2 (`src/bvmt/data.py`)**: Official BVMT historical quotation adapter (`bvmt_histo_cotation`), zero-volume untraded bar normalization (`untraded_or_suspended_count`), raw file preservation (`raw_source.csv`), and `DataQualityReport` SHA-256 provenance.
  - **Codex C3 (`src/bvmt/execution.py`)**: `run_historical_backtest` deterministic T+1 simulation with shared liquidity participation caps, partial fills & order age expiration, `0.50%` fee accounting, cash and equal-weight benchmarks, and max drawdown metrics.
  - **Gemini G1 & G2 (`src/bvmt/ledger.py`)**: Competition account CSV import/export (`parse_account_holdings_csv`, `parse_account_transactions_csv`, `parse_account_pending_orders_csv`), session-by-session `compute_valuation_history`, read-only `reconcile_with_snapshot` (detecting all 6 discrepancy categories), and confirmation-gated `apply_reconciliation_snapshot`.
  - **Gemini G3 (`src/bvmt/dashboard.py`)**: Dataset discovery (`discover_available_bar_datasets`), data freshness lag indicators, portfolio valuation history tab, competition account reconciliation UI, and transaction fill history.

## Not implemented
Live execution against DashScope (intentionally locked behind `network_enabled: false` and `BVMT_ALLOW_LIVE_LLM=1` until the user authorizes a controlled live test or batch run); multi-fold walk-forward evaluation (`T06`, awaiting manual download of official BVMT historical CSVs into `data/staging/`).

## Handoff (Multi-Agent Orchestration: Codex C1–C3 + Gemini G1–G3)
- **Branches merged into `main`**:
  - `codex/data-research` (`4ebfff1`) — 9 owned files modified, `125 passed`
  - `gemini/dashboard` (`d3f9bf8`) — 3 owned files modified, `94 passed`
- **Integrated verification on `main`**:
  - `uv run python scripts/check.py` -> exit `0` (`ruff format --check` across 30 files, `ruff check`, `mypy src/bvmt` across 13 source files, `scripts/validate_skills.py`, `pytest -q` **128 passed**)
  - Live Streamlit dashboard startup smoke test -> exit `0`

## Next exact action
1. Download official BVMT historical quotation files (`histo_cotation_2022.csv` .. `histo_cotation_2026.csv`) into `data/staging/` and import them via `uv run bvmt import-csv <path> --format bvmt_histo_cotation ...`.
2. Export or enter your current `tunisbourse-challenge.com` holdings, cash, transactions, and pending orders in the **Portfolio -> Competition Account CSV Import & Reconciliation** tab to synchronize your local ledger.
3. Authorize a controlled live smoke test for `qwen3.7-text-embedding` before its November 8, 2026 expiration if semantic vector indexing is desired alongside the local BM25 engine.
