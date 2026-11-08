# Working state

## Current checkpoint
**Modern Dashboard Migration (Next.js 15 + TypeScript + Tailwind + Recharts Frontend & Localhost FastAPI Backend)** merged and verified end-to-end on `main` on 2026-11-07 (Windows PowerShell, CPython 3.13.18 in `.venv`, `uv 0.13.7`, `fastapi 0.162.1`, `pydantic 2.14.3`, `next 15.5.29`, `react 19`, `streamlit 1.66.1`, `playwright 1.64.1`, `codex-cli 0.166.0`).
All **252 automated Python tests** (including **46 FastAPI `TestClient` integration tests**), the full Python developer quality gate (`uv run --no-sync python scripts/check.py`), and the **Next.js TypeScript + production build** (`npm.cmd run typecheck` and `npm.cmd run build`) pass with **zero live LLM API calls**, **zero autonomous order submission**, and **zero paid cloud resources**.
Central GitHub repository synchronized across `main` (`c:\Users\Thinkcenter\Desktop\BVMT\bvmt-starter-kit`), `gemini/dashboard` (`c:\Users\Thinkcenter\Desktop\BVMT\bvmt-gemini-dashboard`), and `codex/data-research` (`c:\Users\Thinkcenter\Desktop\BVMT\bvmt-codex-research`).

## Modern Dashboard Migration & Phase 0 State Service (2026-11-07)
- **Phase 0 — Canonical Backend Portfolio-State Service (`src/bvmt/portfolio_service.py`, `docs/CANONICAL_DATA_SOURCE_RULES.md`)**:
  - Created `PortfolioStateService` and `resolve_canonical_portfolio_context` as the single deterministic backend authority shared by both FastAPI (`src/bvmt/api.py`) and the Streamlit fallback (`src/bvmt/dashboard.py`).
  - Documented canonical data-source selection rules in `docs/CANONICAL_DATA_SOURCE_RULES.md`.
- **Codex Workstream — Localhost FastAPI Layer (`src/bvmt/api.py`, `tests/test_api.py`)**:
  - Implemented `create_app(service=None)` and `app = create_app()` with strict localhost-only `CORSMiddleware` (`127.0.0.1:3000`, `localhost:3000`, `127.0.0.1:8000`, `localhost:8000`), Decimal-safe 3-decimal string serialization (`Money`), HTML/credential sanitization (`PlainText`), and clean dataset labels.
  - Added read-only endpoints (`/api/overview`, `/api/holdings`, `/api/snapshots`, `/api/transactions`, `/api/orders/pending`, `/api/market-status`, `/api/rankings`, `/api/research`, `/api/health`) and confirmation-gated synchronization endpoints (`POST /api/sync/browser`, `GET /api/sync/preview`, `POST /api/sync/confirm`).
  - Added **46** FastAPI `TestClient` integration tests in `tests/test_api.py`.
- **Gemini Workstream — Next.js 15 Financial Dashboard (`frontend/`, `start_bvmt.bat`, `src/bvmt/cli.py`)**:
  - Built a 7-page Next.js App Router + TypeScript + Tailwind CSS + Recharts + Lucide dashboard (`/` Overview, `/portfolio` Portfolio, `/transactions` Transactions & Orders, `/market` Market Explorer, `/research` Stock Research, `/strategy` Strategy Lab, `/health` System Health).
  - Updated `start_bvmt.bat` to launch both the local FastAPI backend (`127.0.0.1:8000`) and the Next.js frontend (`127.0.0.1:3000`), while keeping `start_bvmt.bat --streamlit` (and `uv run bvmt dashboard`) available as a one-command fallback.
  - Verified the complete real-account confirmation workflow end to end in Chrome: confirmed `sync_20261107_122006.json` (`browser_sync_20261107_122006`), persisting `50,000.75 TND` total equity, `49,608.05 TND` cash, `392.70 TND` `BH BANK` market value (`30` shares @ `13.09 TND`), `+0.75 TND` (`+0.19%`) unrealized P&L, and rank `#118 / 14,530` to `data/portfolio/real_competition_ledger.json`.

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

## Strategy Lab Phases 2–5 (Codex worktree, 2026-11-08)

- User-authorized scope: new `src/bvmt/strategies.py`, additive `src/bvmt/api.py`
  endpoints, new `tests/test_strategies.py`, extended `tests/test_api.py`, generated
  `artifacts/strategy_experiments_2026.json`, and this state entry. No frontend,
  other strategy documentation, shared configuration, or portfolio modules edited.
- Implemented nine frozen, interpretable hypotheses A–I with a sequential Decimal
  cash/share ledger, next-open-only execution, unfavorable 10 bps slippage with
  observed OHLC bounds, 50 bps per-side fees, 10% purchase concentration capacity,
  10% shared per-security/session volume capacity, integer shares and .001 TND
  half-up fees. Orders attempt the next session once; residuals expire. Initial
  decision follows 61 completed sessions; periodic decisions occur every 19 open
  sessions. Buy-and-hold has a single initial decision. No parameters were fitted.
- Added marked/fee-only-terminal-liquidated returns, aligned executable C benchmark,
  drawdown, fees, fills/orders, average-cost evaluated-slice hit rates (including
  terminal sleeves after exit fee), turnover, exposure, actual marked concentration,
  full equity curves and fill diagnostics. Each hypothesis has seven chronological
  61-train/19-test/19-step fresh-cash folds and nine fully rerun fee/participation
  scenarios (81 sensitivity scenarios total). Config/experiment identities hash
  code, formulas, configuration, canonical bar values, master and calendar.
- Full registry regenerated from 14,480 canonical bars / 76 instruments / 194
  observed sessions, 2026-01-02 through 2026-11-06. Canonical SHA-256:
  `cdec16511f5d5ecd937a89656f9cd65746eb6655091447bc0078f7a30b159116`.
  Archive SHA-256:
  `486761f55253480a0e19e9b7e8300512522316f93f67081c6fa010d86df45c55`.
  Registry config hash:
  `87e57368642da1b01a0cefd7f720e4e200f1d38e2f900374b6699c63285f5927`.
  Reproduce offline with `generate_experiment_registry(Path('data/processed/bvmt_official_2026'), Path('data/staging/market_resume_full.ndjson'), Path('artifacts/strategy_experiments_2026.json'))`
  from `bvmt.strategies` using the project Python environment.
- Observed marked returns (%), descriptive only: A 0.000000; B 14.047960;
  C 14.026112; D 17.050596; E 14.356077; F 17.050596; G 18.811715;
  H 15.144953; I 15.735354. Different caps/sizing/execution rules make these
  different experiments from earlier backtest artifacts; no previous result replaced.
- Historical audit recomputes archive and canonical checksums and 2020–2026
  coverage. Pre-2026 daily history and corporate-action adjustment tables remain
  unavailable; 2025 envelopes are monthly summaries. Original source retrieval time
  is unknown (null), separately from saved processing/import timestamps. Zero-byte
  legacy ZIP results are attributed to saved manifest evidence, not a new download.
  Delisting/suspension completeness and historical universe verification remain
  blocked. Missing publication timestamps and retrospective ingestion force every
  result to `exploratory`, despite chronological forward testing. Event overlay is
  disabled. The explicit 194 < 250 ML promotion gate blocks LightGBM promotion;
  more sessions alone would not establish multi-year, leak-free evidence.
- Material unmet acceptance condition: continuous marked concentration <=10% is
  NOT demonstrated. All invested strategies exceed 10% during price drift; observed
  maxima range from B 12.808956% to C 14.697064%. The ledger enforces purchase
  capacity and reports drift honestly; it does not fabricate same-close reductions
  or alter buy-and-hold into a daily risk-trimming strategy. Diagnostics set
  `concentration_cap_compliant=false` for B–I. Every report is research-only and
  requires human approval; none is statistically conclusive or promotable.
- API: read-only `GET /api/strategy-lab` serves `{status, registry, limitations}`;
  `GET /api/research` has nullable `strategy_comparison` containing the same saved
  registry. Missing/invalid artifacts yield explicit safe statuses; GET never runs
  simulations or writes portfolios. Actual saved-artifact smoke test: HTTP 200,
  nine reports. The generated artifact remains Git-ignored as required.
- Verification environment: local `.venv` lacks FastAPI/Pydantic;
  `uv sync --locked --group dev --extra dashboard --offline` failed because the
  local cache lacks `annotated-doc==0.0.5`. No downloads or dependency files changed.
  Native `uv run --no-sync python scripts/check.py` passed formatting/lint then
  failed mypy on missing FastAPI/Pydantic imports. Used existing integration
  workspace `.venv/Scripts/python.exe`, with this worktree `src` on PYTHONPATH and
  bytecode writes disabled, for successful strict mypy and API tests.
- Windows sandbox workaround for tests: CPython 3.13 `mkdir(mode=0700)` creates
  pytest ACLs excluding the sandbox token. An ephemeral in-memory launcher changes
  only workspace temporary-directory creation to inherited permissions and disables
  pytest cache writes. It runs pytest in-process while the other unchanged
  `scripts/check.py` gate commands use subprocesses. No test assertions skipped or
  loosened. Latest targeted strategy/API run: 69 passed, one pre-existing
  Starlette/httpx deprecation warning. Final full gate result recorded below.
- Temporary test/probe directories remain untracked: automatic approval review
  rejected recursive cleanup commands as blocked by policy. Nothing staged or
  committed; no external writes, network/LLM calls or autonomous orders.
- Next exact action: integration review of these six deliverables and the saved
  experiment contract; resolve the continuous concentration-policy requirement
  before any compliance or promotion claim, and obtain authorized older daily
  history plus independently verified action/membership/availability evidence.
- Final verification result: unchanged `scripts/check.py` invoked through the
  integration-interpreter/sandbox-compatible launcher completed all five gates:
  39 Python files formatted; Ruff lint passed; strict mypy passed (17 modules);
  10 skill entrypoints validated; pytest **275 passed**, one Starlette/httpx
  deprecation warning, 121.02 seconds; launcher exit 0. After successful gate
  completion, interpreter shutdown emitted a PermissionError from an unrelated
  standard-temp-directory cleanup finalizer; this was not a failed assertion or
  test. Native local-environment gate remains blocked as documented above.
  Saved registry code checksum verified against final `strategies.py`; real-file
  endpoint smoke test returned HTTP 200 with nine reports. `git diff --check`
  passed. The artifact is 648,820 bytes and remains local/Git-ignored.
