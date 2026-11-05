# Working state

## Current checkpoint
**Milestone 1C (Manual Portfolio Ledger, 5-State Recommendation Engine, Local Alert Center, 6-Page Streamlit Dashboard, Windows Launcher & Full-System Testing)** and **GitHub Baseline + Parallel Gemini/Codex Worktree Setup** completed on 2026-11-05 (Windows PowerShell, CPython 3.13.18 in `.venv`, `uv 0.13.7`, `streamlit 1.66.1`).
All **91 automated unit, integration, and Streamlit `AppTest` UI tests** and the full developer quality gate (`uv run python scripts/check.py`) pass with **zero live API calls**, **zero autonomous order submission**, and **zero paid cloud resources**.
Central GitHub repository configured at `https://github.com/medYousseffathallah/onetimetradingbot.git` with isolated Git worktrees for `main` (`c:\Users\Thinkcenter\Desktop\BVMT\bvmt-starter-kit`), `gemini/dashboard` (`c:\Users\Thinkcenter\Desktop\BVMT\bvmt-gemini-dashboard`), and `codex/data-research` (`c:\Users\Thinkcenter\Desktop\BVMT\bvmt-codex-research`).

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
  - **CLI (`src/bvmt/cli.py`)**: `demo`, `rules-check`, `validate-csv`, `import-csv`, `coverage-check`, `session-rank`, `llm-dry-run`, `portfolio-init`, `portfolio-status`, `order-submit`, `order-fill`, `order-close`, `recommend`, and `dashboard`.

## Not implemented
Live execution against DashScope (intentionally locked behind `network_enabled: false` and `BVMT_ALLOW_LIVE_LLM=1` until the user authorizes a live batch run); historical multi-session walk-forward backtest (`T06`, awaiting manual download of official BVMT historical CSVs into `data/staging/`).

## Handoff (Milestone 1C Implementation & Full-System Testing)
- **Task ID**: Milestone 1C (Manual Portfolio Ledger, Recommendation Engine, Local Notifications, Streamlit Dashboard, Launcher & Full-System Testing)
- **Files created and modified**:
  - `src/bvmt/ledger.py` (new)
  - `src/bvmt/recommendations.py` (new)
  - `src/bvmt/notifications.py` (new)
  - `src/bvmt/dashboard.py` (new)
  - `start_bvmt.bat` (new)
  - `tests/test_milestone_1c.py` (new)
  - `src/bvmt/cli.py`, `src/bvmt/llm.py`, `tests/test_llm_budget.py`, `configs/llm_budget.example.json`
  - `README.md`, `docs/USER_GUIDE.md`, `docs/MANUAL_TRADING_WORKFLOW.md`, `docs/NOTIFICATIONS.md`, `docs/SIGNAL_METHODOLOGY.md`, `docs/OPERATIONS.md`, `docs/ALIBABA_INTEGRATION_PLAN.md`, `task.md`, `docs/STATE.md`
- **Commands actually run and exit codes**:
  - `uv sync --locked --group dev --extra dashboard` -> exit `0` (installed `streamlit 1.66.1`)
  - `.\.venv\Scripts\python.exe scripts/check.py` -> exit `0` (`ruff format --check` across 30 files, `ruff check`, `mypy src/bvmt` across 13 source files, `scripts/validate_skills.py`, `pytest -q` **91 passed in 9.16s**)
  - Live Streamlit HTTP server smoke test on `http://127.0.0.1:8517/` and `/_stcore/health` -> exit `0` (`HTTP_STATUS: 200 HEALTH: ok HTML_BYTES: 6467`)

## Next exact action
1. Double-click `start_bvmt.bat` (or run `uv run bvmt dashboard`) to inspect the local 6-page decision-support terminal at `http://127.0.0.1:8501`.
2. Download official BVMT historical CSVs and CMF company disclosures into `data/staging/` (per `docs/BVMT_DATA_SOURCES.md` Section 5), import them via `uv run bvmt import-csv`, and—when ready—authorize the batch `qwen3.7-text-embedding` and `qwen3.8-2.4t-a95b` / `deepseek-v4-pro-0813` extraction pilot before the November 8 and November 11–12 free-quota expirations.
