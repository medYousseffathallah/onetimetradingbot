# Working state

## Current checkpoint
**Milestone 2: Operational Trading Research & Real Browser Portfolio Synchronization** merged on `main` on 2026-11-06 (Windows PowerShell, CPython 3.13.18 in `.venv`, `uv 0.13.7`, `streamlit 1.66.1`, `playwright 1.64.1`, `codex-cli 0.166.0`).
All **153 automated unit, integration, backtesting, reconciliation, price drift, browser DOM parsing, and Streamlit `AppTest` UI tests** and the full developer quality gate (`uv run python scripts/check.py`) pass with **zero live API calls**, **zero autonomous order submission**, and **zero paid cloud resources**.
Central GitHub repository synchronized across `main` (`c:\Users\Thinkcenter\Desktop\BVMT\bvmt-starter-kit`), `gemini/dashboard` (`c:\Users\Thinkcenter\Desktop\BVMT\bvmt-gemini-dashboard`), and `codex/data-research` (`c:\Users\Thinkcenter\Desktop\BVMT\bvmt-codex-research`).

## Implemented
- Agent instructions and skills; portable installation helper; real resolved `uv.lock` (including `streamlit 1.66.1` and `playwright 1.64.1`).
- Content-addressed local snapshots (`src/bvmt/snapshots.py`) with symlink/path-safety checks, explicit `permission_status` and `parser_version` metadata, and atomic file writes with overwrite refusal on differing content.
- Typed canonical CSV/bar validation, French BVMT CSV source adapter, and official `tunis_stockexchange_ndjson` adapter (`src/bvmt/data.py`).
- Dated instrument master, official-source-backed BVMT exchange calendar (`Africa/Tunis`), and observation coverage diagnostics (`src/bvmt/calendar.py`).
- **Windows Launcher Fix (`start_bvmt.bat`)**:
  - Fixed `'Zero' n'est pas reconnu en tant que commande interne ou externe` by escaping CMD shell pipe `^|`.
  - Added `chcp 65001 >nul` to eliminate Unicode character corruption across Windows Command Prompt and PowerShell.
- **Local-First Read-Only Browser Portfolio Synchronization (`src/bvmt/browser.py`)**:
  - Secure Playwright-based collector launching dedicated persistent browser context in `data/browser_profile/` (isolated from user's Chrome profile).
  - Pure DOM extraction from authenticated `displayp.aspx` without storing credentials, cookies, or session tokens.
  - Robust parser for French number formatting, portfolio total, available cash, holdings, acquisition prices, latest prices, gains/losses, competition rank, and displayed overall performance.
  - Strict balance equality validation (`cash + sum(holdings) == total` within `0.05 TND` tolerance).
  - Explicit error handling for `AuthenticationExpiredError`, `LayoutChangedError`, and `BalanceMismatchError`.
  - Structured local snapshot persistence in `data/portfolio/snapshots/` (strictly gitignored).
- **Financial Correctness Audit & Strategy Validation (`src/bvmt/execution.py`)**:
  - Audit of 0.50% buy and 0.50% sell fees (~1.00% round trip).
  - Added liquidation equity calculation (`liquidated_final_equity_tnd`, `liquidated_total_return_pct`, `unrealized_liquidation_fee_tnd`) showing that net of exit fees on unclosed positions, the previous baseline return adjusts to net liquidated return.
  - Implemented chronological walk-forward evaluation (`run_walk_forward_evaluation`) and sensitivity analysis grid (`run_sensitivity_analysis`) across commissions (30, 50, 70 bps), volume participation (5%, 10%, 20%), and slippage.
  - Explicit `data_sufficiency_warning` disclosing that 72 sessions (with 60-session warmup leaving 12 forward sessions) is statistically insufficient to certify strategy alpha without 2022-2025 multi-year data.
- **Daily Market Data Pipeline & Freshness Checks (`src/bvmt/data.py`)**:
  - `check_data_freshness` detects stale sessions and untraded instruments without inventing prices.
  - `refresh_daily_market_pipeline` enables reproducible incremental session ingestion, deduplicating records, updating `DataQualityReport`, and maintaining SHA-256 provenance.
- **Real Competition Portfolio Tracking & Dashboard Sync UI (`src/bvmt/ledger.py`, `src/bvmt/dashboard.py`)**:
  - Added `build_snapshot_from_dom` to convert browser DOM extractions into verified `CompetitionScreenshotSnapshot`.
  - Added **Sync Competition Portfolio** tab in the real portfolio dashboard providing:
    - **Sync Now (Launch Browser)** button using dedicated Playwright profile.
    - **Direct HTML Paste** option for instant parsing from DevTools.
    - Last sync timestamp, retrieved cash, holdings, total equity, and rank metrics.
    - Preview of synchronized changes vs current local ledger with cash delta.
    - **Confirmation-Gated Application** checkbox (`chk_confirm_browser_sync`) and button preventing silent ledger mutation.
    - Archived synchronization history table.
- **Milestone 1A-1C Foundations**:
  - Alibaba Model Studio budget-gated provider (`src/bvmt/llm.py`) with `console_free_quota_only_verified: true`.
  - T04 session-aware quantitative momentum ranking (`src/bvmt/features.py`).
  - 5-state recommendation engine (`src/bvmt/recommendations.py`).
  - Local alert center with power-off catch-up detection (`src/bvmt/notifications.py`).
  - 6-page local Streamlit dashboard with dual-mode `REAL COMPETITION` vs `SYNTHETIC DEMO` isolation.

## Not implemented
Live execution against DashScope (intentionally locked behind `network_enabled: false` and `BVMT_ALLOW_LIVE_LLM=1` until authorized); automated order submission (prohibited by design: operator places all orders manually on `tunisbourse-challenge.com`).

## Handoff (Milestone 2 & Browser Synchronization Integration)
- **Branches merged into `main`**:
  - `codex/data-research` (`8c7e50f`) — browser collector, DOM parser, liquidation fee audit, walk-forward, daily data refresh (152 tests passing).
  - `gemini/dashboard` (`7ec9a88`) — browser sync tab, confirmation-gated update, start_bvmt.bat fix, AppTest UI tests (153 tests passing).
- **Integrated verification on `main`**:
  - `uv run --no-sync python scripts/check.py` -> exit `0` (`ruff format --check` across 32 files, `ruff check`, `mypy src/bvmt` across 14 source files, `scripts/validate_skills.py`, `pytest -q` **153 passed** in `16.67s`).
  - Windows batch launcher tested and verified in CMD and PowerShell without errors or mojibake.

## Next exact action
1. Launch the local dashboard via `.\start_bvmt.bat` (or `uv run bvmt dashboard`).
2. Navigate to **Portfolio -> 4. Sync Competition Portfolio (Browser Sync)**.
3. Synchronize your authenticated Tunis Bourse Challenge portfolio using either **Sync Now (Launch Browser)** or by pasting the HTML from Chrome DevTools.
4. Review the change preview and check the confirmation box to update your local real portfolio ledger.
