# Working state

## Current checkpoint
**Real Competition Account Activation & Official BVMT Market Data Integration** merged on `main` on 2026-11-06 (Windows PowerShell, CPython 3.13.18 in `.venv`, `uv 0.13.7`, `streamlit 1.66.1`, `codex-cli 0.166.0`).
All **144 automated unit, integration, backtesting, reconciliation, price drift, and Streamlit `AppTest` UI tests** and the full developer quality gate (`uv run python scripts/check.py`) pass with **zero live API calls**, **zero autonomous order submission**, and **zero paid cloud resources**.
Central GitHub repository synchronized across `main` (`c:\Users\Thinkcenter\Desktop\BVMT\bvmt-starter-kit`), `gemini/dashboard` (`c:\Users\Thinkcenter\Desktop\BVMT\bvmt-gemini-dashboard`), and `codex/data-research` (`c:\Users\Thinkcenter\Desktop\BVMT\bvmt-codex-research`).

## Implemented
- Agent instructions and skills; portable installation helper; real resolved `uv.lock` (including `streamlit 1.66.1` in the `dashboard` extra).
- Content-addressed local snapshots (`src/bvmt/snapshots.py`) with symlink/path-safety checks, explicit `permission_status` and `parser_version` metadata, and atomic file writes with overwrite refusal on differing content.
- Typed canonical CSV/bar validation, French BVMT CSV source adapter, and official `tunis_stockexchange_ndjson` adapter (`src/bvmt/data.py`).
- Dated instrument master, official-source-backed BVMT exchange calendar (`Africa/Tunis`), and observation coverage diagnostics (`src/bvmt/calendar.py`).
- **Official BVMT 2026 Market Data Pipeline (`data/staging/`, `data/processed/bvmt_official_2026/`)**:
  - Ingested 5,380 canonical daily bars across 72 distinct sessions (`2026-07-09` to `2026-11-05`) for 75 equity instruments from `tunis-stockexchange.com` with SHA-256 provenance tracking (`data/staging/official_provenance.json`).
  - Strict zero-volume bar handling (`quantites == 0` preserved at reference close `cloture` with `status: untraded`) preventing zero-volume fills in backtesting (`max_turnover_participation` in `src/bvmt/execution.py`).
  - Full official market and backtest report generated at `artifacts/official_bvmt_market_report.json`.
- **Real Competition Portfolio Tracking & Price Drift (`src/bvmt/ledger.py`)**:
  - `CompetitionScreenshotSnapshot`, `ScreenshotHoldingSnapshot`, and `PortfolioPriceDriftReport` capture verified user screenshot metrics (`49,998.05 TND` total, `49,608.05 TND` cash, `30` BH BANK @ `13.065 TND` acquisition, `13.00 TND` last, `390.00 TND` MV, `-1.95 TND` / `-0.50%` unrealized P&L, `0.78%` allocation, rank `4,813 / 14,530`, `+0.00%` displayed return) without fabricating missing transactions or unverified pending orders.
  - `compute_screenshot_price_drift` tracks mark-to-market drift against the latest official BVMT close (BH BANK closed at `13.00 TND` Oct 28–30, moved to `13.50 TND` on Nov 4/5, producing `+15.000 TND` / `+3.846%` unrealized drift for 30 shares).
  - Isolated ledger environments: `data/portfolio/real_competition_ledger.json` (`REAL COMPETITION PORTFOLIO`) and `data/portfolio/ledger.json` (`SYNTHETIC DEMO PORTFOLIO`) with confirmation-gated mutations (`confirmed_by_user=True`).
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
  - **6-Page Local Streamlit Dashboard (`src/bvmt/dashboard.py`) & Windows Launcher (`start_bvmt.bat`)**: Renders `Overview`, `Stock Opportunities`, `Portfolio`, `Manual Order Journal`, `Research and Documents`, and `System Health` on `http://127.0.0.1:8501`. Features sidebar selector between `REAL COMPETITION PORTFOLIO` and `SYNTHETIC DEMO PORTFOLIO`, screenshot provenance display, `NOT LIVE-SYNCHRONIZED` and `Pending orders not verified` warnings, real-time mark-to-market drift cards, dataset discovery across synthetic and official datasets, and competition account reconciliation.
  - **CLI (`src/bvmt/cli.py`)**: `demo`, `rules-check`, `validate-csv`, `import-csv` (supporting `--format bvmt_histo_cotation` and `--format tunis_stockexchange_ndjson`), `coverage-check`, `session-rank`, `llm-dry-run`, `portfolio-init`, `portfolio-status`, `order-submit`, `order-fill`, `order-close`, `recommend`, and `dashboard`.

## Not implemented
Live execution against DashScope (intentionally locked behind `network_enabled: false` and `BVMT_ALLOW_LIVE_LLM=1` until the user authorizes a controlled live test or batch run); multi-fold walk-forward evaluation (`T06`, pending collection of multi-year 2022-2025 historical series).

## Handoff (Real Account Activation & Official BVMT Market Data Integration)
- **Branches merged into `main`**:
  - `codex/data-research` (`d232749`) — official BVMT NDJSON ingestion, untraded bar normalization, calendar export, backtest turnover participation caps (142 tests passing).
  - `gemini/dashboard` (`fd8c001`) — screenshot snapshot modeling, price drift calculation, dual portfolio selector, real competition dashboard cards (130 tests passing).
- **Integrated verification on `main`**:
  - `uv run python scripts/check.py` -> exit `0` (`ruff format --check` across 30 files, `ruff check`, `mypy src/bvmt` across 13 source files, `scripts/validate_skills.py`, `pytest -q` **144 passed** in `11.59s`).
  - Live Streamlit dashboard AppTest verified on both `REAL COMPETITION PORTFOLIO` and `SYNTHETIC DEMO PORTFOLIO`.

## Next exact action
1. Synchronize remote GitHub repository (`git push origin main`, `git push origin gemini/dashboard`, `git push origin codex/data-research`).
2. Run daily decision workflow using `uv run bvmt recommend --portfolio data/portfolio/real_competition_ledger.json --bars data/processed/bvmt_official_2026/daily_bars.canonical.csv` to generate compliant candidate trades for human review.
3. If desired, authorize a controlled live smoke test for `qwen3.7-text-embedding` before its November 8, 2026 expiration to test semantic document retrieval.
