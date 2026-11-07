# Working state

## Market dataset provenance helper (Codex worktree, 2026-11-07)
- Added `inspect_market_dataset_provenance(Path)` in `src/bvmt/data.py`, with
  deterministic regression tests in `tests/test_data_import.py`. Gemini-owned
  dashboard, ledger, and recommendations files are unchanged.
- Validates canonical bars before returning coverage, sorted source IDs, synthetic
  classification, and sibling metadata source URL/retrieval time. Missing/empty/
  corrupt datasets raise explicitly; no synthetic fallback. Optional metadata
  precedence: provenance, import timestamp, manifest, quality report (including
  nested manifest provenance). Malformed JSON raises ValueError. Import-only
  timestamps are not relabeled as retrieval timestamps.
- Inspected local canonical bars, exchange calendar, instrument master, provenance,
  import timestamp, manifest, and quality report. Helper smoke check found 14,480
  bars / 194 sessions / 76 instruments, 2026-01-02 through 2026-11-06,
  `is_synthetic=False`, source `official-bvmt-full-2026`, and explicit provenance
  `retrieved_at=2026-11-07T11:44:03.365417+00:00`. This reflects saved metadata,
  not independent source verification: the manifest says original download time
  is unavailable, while provenance.json labels the processing time retrieved_at.
- Verification: `uv run --no-sync pytest tests/test_data_import.py` -> 22 passed;
  `uv run --no-sync ruff check src/bvmt/data.py tests/test_data_import.py`,
  `uv run --no-sync ruff format --check src/bvmt/data.py tests/test_data_import.py`,
  and `uv run --no-sync mypy src/bvmt/data.py` -> all passed.
  `uv run --no-sync python scripts/check.py` -> full gate passed, 205 tests.
  Windows sandbox denied pytest temp/cache access; successful tests used elevated
  execution, workspace-local UV_CACHE_DIR, and fresh artifact temp/cache paths via
  PYTEST_ADDOPTS. No network or live API calls were needed.
- Next exact action: integration review on main, then Gemini can consume the helper
  to display quotation provenance separately from portfolio snapshot freshness.

## Current checkpoint
**Milestone 3: Production Readiness (Live Browser Sync Subprocess, Movements & Pending Orders, Full 2026 Official BVMT Archive & 7-Fold Walk-Forward Audit)** merged on `main` on 2026-11-07 (Windows PowerShell, CPython 3.13.18 in `.venv`, `uv 0.13.7`, `streamlit 1.66.1`, `playwright 1.64.1`, `codex-cli 0.166.0`).
All **175 automated unit, integration, backtesting, walk-forward, reconciliation, price drift, browser DOM/movements parsing, URL guard, and Streamlit `AppTest` UI tests** and the full developer quality gate (`uv run --no-sync python scripts/check.py`) pass with **zero live API calls**, **zero autonomous order submission**, and **zero paid cloud resources**.
Central GitHub repository synchronized across `main` (`c:\Users\Thinkcenter\Desktop\BVMT\bvmt-starter-kit`), `gemini/dashboard` (`c:\Users\Thinkcenter\Desktop\BVMT\bvmt-gemini-dashboard`), and `codex/data-research` (`c:\Users\Thinkcenter\Desktop\BVMT\bvmt-codex-research`).

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
