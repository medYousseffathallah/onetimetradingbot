# Working state

## FastAPI backend layer (Codex worktree, 2026-11-07)
- User-authorized scope: only `src/bvmt/api.py`, `tests/test_api.py`, and this file.
  No frontend, dashboard, ledger, recommendations, dependency manifest, or launcher changes.
- Added lazy `create_app(service=None)` / module-level `app`, typed Pydantic v2
  response contracts, three-decimal Decimal strings, ISO source timestamps,
  four explicit localhost CORS origins, clean dataset labels, and public-field
  projection/sanitization. All ten GET routes accept validated portfolio mode
  with REAL_COMPETITION as default; alternate-mode services preserve path overrides.
- Added read-only portfolio, holdings, snapshots, transactions, pending orders,
  market provenance, rankings, research, health and reconciliation preview routes.
  Browser collection stays capture-only; confirmation requires a strict true boolean
  before invoking PortfolioStateService persistence. Sync POSTs reject demo services.
  All real-account rankings using synthetic bars explicitly carry the synthetic blocker.
- Research projects whitelisted metrics from the existing local
  `artifacts/backtest_audit_2026.json` execution audit, including seven walk-forward
  folds, as historical hypothetical simulation. Missing/invalid audits return
  unavailable metrics; no historical returns are invented or embedded in API code.
  This does not independently revalidate the historical strategy or its input license.
- Added 46 TestClient cases covering opening 49998.050 TND baseline, pending
  sync_20261107_122006.json detection without ledger changes, rejected confirmation,
  confirmed 50000.750 TND equity / 49608.050 TND cash / 392.700 TND BH BANK value /
  0.750 TND unrealized gain / rank 118 of 14530, fresh-service restart persistence,
  all routes, CORS, custom paths, source cutoffs, synthetic blockers, mocked browser
  success/errors, local fills, browser movements, search and safe error responses.
- Read-only skill-requested review identified source-availability filtering,
  JSON credential/query sanitization and synthetic-mode sync boundaries. All were
  fixed with regression tests; verified prices in both holdings branches use only
  eligible source quotes, returning null for unavailable or synthetic quotes.
- Verification: `uv run --no-sync ruff format src/bvmt/api.py tests/test_api.py`,
  `uv run --no-sync ruff check src/bvmt/api.py tests/test_api.py`, and
  `uv run --no-sync mypy src/bvmt` passed. Targeted pytest: **46 passed**.
  Full `scripts/check.py` gate: format/check, mypy (16 modules), skill validation,
  and **252 passed**, exit 0. One installed-Starlette TestClient/httpx deprecation
  warning; full suite also emitted a Windows temporary-directory cleanup
  PermissionError at interpreter exit, without test failures or a nonzero exit.
- Environment/reproduction constraints: `uv sync --locked --group dev --extra
  dashboard --extra data` failed because the configured package proxy was unreachable;
  the worktree environment lacks FastAPI. Checks used workspace-local
  `UV_CACHE_DIR=$PWD/.uv-cache` and
  `PYTHONPATH=$PWD/src;$PWD/../bvmt-starter-kit/.venv/Lib/site-packages` to read the
  already-installed integration environment (FastAPI 0.162.1, Pydantic 2.14.3).
  Pytest needed `PYTEST_ADDOPTS=-p no:cacheprovider --basetemp=artifacts/api-run-8`
  and an in-memory runner replacing os.mkdir mode 0700 with inherited mode 0777;
  otherwise this Windows sandbox denies pytest access to its own temporary directories.
  Full gate ran scripts/check.py via runpy with subprocess.run forwarding only its
  pytest invocation through that runner, scoped to artifacts/api-full-gate-1.
  No repository test, check script, assertion or dependency was bypassed/modified.
- No live browser launch, account authentication, external write, LLM call or order
  submission was performed. Bind Uvicorn to 127.0.0.1; CORS is browser policy and
  does not itself restrict the server's network binding. Next exact action:
  integration review on main; restore package access, sync locked dashboard/data
  extras, and launch `uvicorn bvmt.api:app --host 127.0.0.1 --port 8000` locally.

## Current checkpoint
**P0 Dashboard Data Source Mismatch & Confirmed Live Browser Sync Integration** merged on `main` on 2026-11-07 (Windows PowerShell, CPython 3.13.18 in `.venv`, `uv 0.13.7`, `streamlit 1.66.1`, `playwright 1.64.1`, `codex-cli 0.166.0`).
All **206 automated unit, integration, backtesting, walk-forward, reconciliation, price drift, browser DOM/movements parsing, dataset provenance, and Streamlit `AppTest` UI tests** and the full developer quality gate (`uv run --no-sync python scripts/check.py`) pass with **zero live LLM API calls**, **zero autonomous order submission**, and **zero paid cloud resources**.
Central GitHub repository synchronized across `main` (`c:\Users\Thinkcenter\Desktop\BVMT\bvmt-starter-kit`), `gemini/dashboard` (`c:\Users\Thinkcenter\Desktop\BVMT\bvmt-gemini-dashboard`), and `codex/data-research` (`c:\Users\Thinkcenter\Desktop\BVMT\bvmt-codex-research`).

## P0 Dashboard Data Source Mismatch & Market Dataset Provenance Fix (2026-11-07)
- **Root-Cause Diagnosis**:
  1. **Unconfirmed Browser Snapshot Not Surfaced on Reload (`src/bvmt/dashboard.py`)**: `uv run bvmt browser-sync` wrote `data/portfolio/snapshots/sync_20261107_122006.json` (`49,608.05 TND` cash, `BH BANK` `30` shares @ `13.09 TND` = `392.70 TND` value, `+0.75 TND` / `+0.19%` gain, `50,000.75 TND` total, rank `118 / 14,530`, `reconciliation_gap_tnd = 0.000`) to disk and intentionally did not overwrite `data/portfolio/real_competition_ledger.json` without user confirmation. However, `build_dashboard_state` did not compare `load_latest_browser_snapshot(snapshots_dir)` against `ledger.snapshot_history`, so the dashboard neither displayed `"Snapshot captured — awaiting confirmation"` nor showed the confirmation button in Tab 4 unless `st.session_state["pending_synced_snapshot"]` was populated in memory during the current click. Additionally, `_render_top_banners` had a hardcoded `"NOT LIVE-SYNCHRONIZED"` string even after confirmation.
  2. **Dashboard Defaulting to `SYNTHETIC DEMO` Market Dataset (`src/bvmt/dashboard.py`)**: `discover_available_bar_datasets()` placed `"SYNTHETIC DEMO: tests/fixtures/daily_bars.csv"` at `index=0`, and `render_streamlit_app()` hardcoded `index=0` on the sidebar selectbox even when `REAL COMPETITION PORTFOLIO` was active and `VERIFIED IMPORT: bvmt_official_2026 (data/processed/bvmt_official_2026/daily_bars.canonical.csv)` (`194` sessions through `2026-11-06`) was present on disk.
- **Gemini Worktree Changes (`src/bvmt/dashboard.py`, `src/bvmt/recommendations.py`, `tests/test_milestone_1c.py`)**:
  - Added `select_default_dataset_index(dataset_labels, portfolio_mode=...)` so `REAL_COMPETITION` mode defaults to the latest `VERIFIED IMPORT` dataset (`data/processed/bvmt_official_2026/daily_bars.canonical.csv`, latest session `2026-11-06`) while keeping `SYNTHETIC DEMO` selectable for testing.
  - Extended `DashboardAppState` with `snapshots_dir`, `latest_browser_snapshot`, `pending_browser_snapshot`, and `market_data_provenance`.
  - Updated `build_dashboard_state` to detect any unconfirmed snapshot on disk (`pending_browser_snapshot`) without mutating the ledger.
  - Updated `_render_top_banners`, `_render_overview_page`, and Portfolio Tab 4 (`Sync Competition Portfolio`) to display `"Snapshot captured — awaiting confirmation"` and render the reconciliation preview + confirmation checkbox/button for any unconfirmed snapshot on disk, and to show `"LIVE-SYNCHRONIZED (Confirmed at ...)"` once confirmed.
  - Explicitly separated **Website-Reported Competition Account Values (`displayp.aspx` Snapshot)** (`50,000.75 TND` total, `392.70 TND` `BH BANK` value, `+0.75 TND` unrealized P&L, `49,608.05 TND` cash, `118 / 14,530` rank) from **Locally Recalculated Mark-to-Market Valuation (`BVMT Official Market Quotations`)**, and displayed portfolio snapshot vs market quotation timestamps separately.
  - Added `synthetic_data_on_real_portfolio` blocker in `generate_recommendations` (`src/bvmt/recommendations.py`) so synthetic market bars can never generate actionable recommendations on `REAL_COMPETITION` portfolios.
  - Added `test_p0_acceptance_sync_20261107_122006_and_real_dataset_integration` verifying all 12 acceptance steps end-to-end.
- **Codex Worktree Changes (`src/bvmt/data.py`, `tests/test_data_import.py`)**:
  - Added `inspect_market_dataset_provenance(bars_path: Path) -> dict[str, object]` validating canonical bars and returning `is_synthetic`, `latest_session_date` (`2026-11-06`), `first_session_date` (`2026-01-02`), `total_bars` (`14,480`), `unique_sessions` (`194`), `unique_instruments` (`76`), `source_ids` (`['official-bvmt-full-2026']`), `source_url`, and `retrieved_at`, raising explicit `FileNotFoundError` / `ValueError` on missing or corrupt datasets without silent synthetic fallback (14 new tests in `tests/test_data_import.py`).

## Implemented
- Agent instructions and skills; portable installation helper; real resolved `uv.lock` (including `streamlit 1.66.1` and `playwright 1.64.1`).
- Content-addressed local snapshots (`src/bvmt/snapshots.py`) with symlink/path-safety checks, explicit `permission_status` and `parser_version` metadata, and atomic file writes with overwrite refusal on differing content.
- Typed canonical CSV/bar validation, French BVMT CSV source adapter, official `tunis_stockexchange_ndjson` adapter, and full official NDJSON archive coverage auditor `audit_official_ndjson_archive` (`src/bvmt/data.py`).
- Dated instrument master, official-source-backed BVMT exchange calendar (`Africa/Tunis`), and observation coverage diagnostics (`src/bvmt/calendar.py`).
- **Windows Launcher Fix (`start_bvmt.bat`)**:
  - Fixed `'Zero' n'est pas reconnu en tant que commande interne ou externe` by escaping CMD shell pipe `^|`.
  - Added `chcp 65001 >nul` to eliminate Unicode character corruption across Windows Command Prompt and PowerShell.
- **Production-Ready Read-Only Browser Portfolio & Movements Synchronization (`src/bvmt/browser.py`, `src/bvmt/cli.py`)**:
  - Added `validate_readonly_challenge_url` enforcing `ALLOWED_CHALLENGE_HOSTS` (`tunisbourse-challenge.com`) and strictly rejecting `FORBIDDEN_TRADING_PATHS` (`bysell.aspx`, `acheter`, `vendre`, `cancel`).
  - Added subprocess launcher `run_browser_sync_subprocess` and CLI entrypoint `python -m bvmt.browser` / `bvmt browser-sync` so Streamlit's `Sync Now` button launches a clean child process on Windows without Tornado/asyncio thread conflicts.
  - Added `BrowserTransactionItem`, `BrowserPendingOrderItem`, and `parse_competition_movements_html` to extract executed transactions (`Achat`/`Vente`, `Exécuté`) and open/pending orders (`En cours`/`En attente`/`Partiel`) from the authorized read-only `display_histo.aspx` (`Mouvements`) page.
  - Verified live Windows Playwright execution against `https://www.tunisbourse-challenge.com/displayp.aspx` using isolated `data/browser_profile/`: confirmed visible Chrome window launch, redirect detection to `login.aspx?ReturnUrl=%2fdisplayp.aspx` when unauthenticated, and clean `AuthenticationExpiredError` reporting without automating login or extracting credentials/cookies.
- **Account Sync Freshness, Confirmation-Gated Reconciliation & Restart Persistence (`src/bvmt/ledger.py`, `src/bvmt/dashboard.py`)**:
  - Added `evaluate_account_sync_freshness` to compute last-sync timestamps and stale-account warnings when the account is on the undated opening screenshot (`SNAP-TBC-USER-001`) or synced prior to the latest market session (`2026-11-06`).
  - Added `apply_confirmed_browser_sync_to_state` requiring `confirmed_by_user=True`, preserving `data/portfolio/real_account_snapshot.json` and `state.ledger.opening_snapshot` untouched as the historical baseline, recording reconciled account snapshots, and persisting `data/portfolio/real_competition_ledger.json` across restarts.
- **Full 2026 Official BVMT Archive Audit & Multi-Fold Strategy Evaluation (`src/bvmt/data.py`, `src/bvmt/execution.py`)**:
  - Downloaded and audited the complete 222.3 MB official BVMT archive (`https://www.tunis-stockexchange.com/sites/default/files/historique/data_json/market_resume.ndjson`, SHA-256 `486761f55253480a0e19e9b7e8300512522316f93f67081c6fa010d86df45c55`, `Last-Modified: Fri, 06 Nov 2026 14:45:02 GMT`).
  - Verified year-by-year coverage: `2022-2024` have `0` sessions in `market_resume.ndjson` (legacy `bvmt.com.tn` ZIPs return 0 bytes; multi-year history requires an official investor request); `2025` has `12` monthly summary lines (`6,303` / `6,881` rows have `quantites: null`, excluded from daily OHLCV ingestion); `2026` has **`194` unique daily sessions** (`2026-01-02` to **`2026-11-06`**) across `209` lines (`15` duplicate envelopes deduplicated), yielding **`14,480` accepted daily equity bars** across `76` equity instruments (`70` invalid rows quarantined).
  - Updated full-year 2026 backtest (`2026-01-02`..`2026-11-06`, 194 sessions, 0.50% buy / 0.50% sell fee): **`+46.6321%` marked** / **`+46.0615%` liquidated** vs **`+19.9445%` equal-weight benchmark** (`10.7827%` max drawdown); Oct 1–Nov 6 competition window (26 sessions): **`+0.5061%` marked** / **`+0.2765%` liquidated** vs **`+0.2498%` benchmark**; 7-fold rolling walk-forward evaluation (`train=61`, `test=19`, `step=19`): **`6 / 7` positive folds (`85.71%`)**, mean fold return **`+3.8215%` marked** / **`+3.4428%` liquidated** vs **`+1.9564%` benchmark** (`is_statistically_conclusive: False` because 194 sessions < 250-session multi-year threshold).
- **Milestone 1A-2 Foundations**:
  - Alibaba Model Studio budget-gated provider (`src/bvmt/llm.py`) with `console_free_quota_only_verified: true`.
  - T04 session-aware quantitative momentum ranking (`src/bvmt/features.py`).
  - 5-state recommendation engine (`src/bvmt/recommendations.py`).
  - Local alert center with power-off catch-up detection (`src/bvmt/notifications.py`).
  - 6-page local Streamlit dashboard with dual-mode `REAL COMPETITION` vs `SYNTHETIC DEMO` isolation.

## Not implemented
Live execution against DashScope (intentionally locked behind `network_enabled: false` and `BVMT_ALLOW_LIVE_LLM=1` until authorized); automated order submission (prohibited by design: operator places all orders manually on `tunisbourse-challenge.com`).

## Handoff (Milestone 3 Production Readiness Integration)
- **Branches merged into `main`**:
  - `gemini/dashboard` (`5e96c7a`) — read-only URL guards, subprocess Playwright launcher, `display_histo.aspx` movements/pending-order parser, account freshness warning, confirmation-gated reconciliation and restart persistence.
  - `codex/data-research` (`385cb33`) — `audit_official_ndjson_archive`, rolling walk-forward training window slice fix, 194-session 2026 dataset ingestion, and 7-fold walk-forward evaluation.
- **Integrated verification on `main`**:
  - `uv run --no-sync python scripts/check.py` -> exit `0` (`ruff format --check`, `ruff check`, `mypy src/bvmt`, `scripts/validate_skills.py`, `pytest -q` **175 passed**).

## Next exact action
1. Launch the local dashboard via `.\start_bvmt.bat` (or `uv run bvmt dashboard`).
2. Navigate to **Portfolio -> 4. Sync Competition Portfolio (Browser Sync)** and click **Sync Now (Launch Browser)** (or run `uv run bvmt browser-sync`).
3. Log in manually to `https://www.tunisbourse-challenge.com` in the opened Chrome window; once `displayp.aspx` loads, the collector automatically captures your portfolio and `display_histo.aspx` movements.
4. Review the reconciliation preview in Tab 4 and check the confirmation box to persist your updated account state.


## P0 holdings parser fix (Codex worktree, 2026-11-07)
- Scope: user-authorized fix in `src/bvmt/browser.py` and
  `tests/test_browser_collector.py`; dashboard and ledger unchanged.
- Added structured table/header/body/row/cell/link capture; verified 12-cell
  `tbody.alri` mapping and backward-compatible 9-cell mapping; displayed symbol
  and identifier survive snapshot serialization (older snapshots still load).
- Missing holdings tables and malformed holding rows now raise LayoutChangedError.
  Explicit empty portfolios remain supported; balance validation remains enabled.
  Latest price is derived only for literal ellipsis placeholders with positive quantity.
- Regression evidence: tests reproduced the old failures before implementation.
  Final `uv run --no-sync pytest tests/test_browser_collector.py`: 26 passed.
  `uv run --no-sync ruff check src/bvmt/browser.py tests/test_browser_collector.py`,
  `uv run --no-sync ruff format --check src/bvmt/browser.py tests/test_browser_collector.py`,
  and `uv run --no-sync mypy src/bvmt/browser.py`: all passed.
  `uv run --no-sync python scripts/check.py`: full gate passed, 190 tests.
  Read-only parser review found no blocking issues; fixture accent typo corrected
  and all 26 browser tests rerun successfully afterward.
- Environment: workspace-local UV_CACHE_DIR used because default cache access was
  denied; successful pytest runs used fresh temporary/cache directories and
  elevated execution after sandbox filesystem errors. No live account capture,
  network calls, order submission, or historical holdings reuse performed.
- Next exact action: integrate/review this patch on main, then manually authenticate
  for an authorized read-only sync and review current account reconciliation.
