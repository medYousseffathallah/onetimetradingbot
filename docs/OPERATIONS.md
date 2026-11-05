# Local-First Operations, Daily Routine & Fault Recovery

This document defines the daily operational workflow, startup/shutdown procedures, fault recovery rules, and backup verification for the **BVMT Trading Intelligence** system.

---

## 1. Non-Technical Startup & Shutdown Procedure

The system is designed to run locally on a standard Windows PC without cloud servers, background daemons, or manual Python programming.

### 1.1 Starting the System

- **One-Click Local Dashboard (`Milestone 1C`)**: Double-click `start_bvmt.bat` in the repository root, or run from PowerShell:
  ```powershell
  uv run bvmt dashboard
  ```
- **CLI Workflow (`Milestone 1A/1B/1C`)**:
  ```powershell
  # 1. Verify competition rules status
  uv run bvmt rules-check --config configs/competition.json

  # 2. Import latest downloaded BVMT CSV
  uv run bvmt import-csv tests/fixtures/french_bvmt_sample.csv --source-id bvmt_hist_sample --format french_bvmt --permission-status authorized_local_import --retrieved-at 2026-01-15T18:00:00+00:00 --raw-dir data/raw --output-dir data/processed/bvmt_hist_sample

  # 3. Check calendar and session coverage
  uv run bvmt coverage-check --bars tests/fixtures/daily_bars.csv --instruments tests/fixtures/instrument_master.csv --calendar tests/fixtures/exchange_calendar.csv

  # 4. Initialize or inspect manual portfolio ledger & generate 5-state recommendations
  uv run bvmt portfolio-init --ledger data/portfolio/ledger.json --initial-cash 100000.000
  uv run bvmt recommend --ledger data/portfolio/ledger.json --bars tests/fixtures/daily_bars.csv --instruments tests/fixtures/instrument_master.csv --calendar tests/fixtures/exchange_calendar.csv --cutoff 2026-01-09T17:00:00+00:00
  ```

### 1.2 Startup Catch-Up Checks After the PC Was Switched Off

Whenever the system starts after the computer was powered off:
1. It reads `artifacts/alerts/state.json` and `data/portfolio/ledger.json`.
2. It compares the current `Africa/Tunis` timestamp against `last_evaluated_at_utc`.
3. It checks all `PENDING` and `PARTIALLY_FILLED` manual orders for:
   - **4-session aging warning** (`ALERT_ORDER_EXPIRY` `WARNING`).
   - **1-week (7-calendar-day) automatic competition expiration** (`ALERT_ORDER_EXPIRY` `URGENT`).
4. It verifies whether the latest imported price bar matches the most recent completed `ExchangeSession`. If data is behind, it raises `ALERT_DATA_STALE` (`BLOCKER`) and withholds order sizing until new data is imported.

### 1.3 Safe Shutdown

1. Finish recording any manual order status updates (`PENDING`, `EXECUTED`, `PARTIALLY_FILLED`, `CANCELLED`, `REJECTED`, `EXPIRED`) in the ledger.
2. Verify that no import command is currently running in the terminal.
3. Close the browser tab and press `Ctrl+C` in the terminal window (or close the launcher window).
4. Because all snapshots (`src/bvmt/snapshots.py`) and ledger writes use atomic temp-file-and-replace (`os.replace`) with SHA-256 verification, shutting down the PC after a command completes never corrupts stored state.

---

## 2. Daily Operational Workflow (Tunis Bourse Session Schedule)

All market times are in **`Africa/Tunis` (`UTC+1`)**, matching the official competition execution window (`09:00–14:15`) and hourly leaderboard recalculation (`11:00–15:00`).

### Phase A — Pre-Session or Post-Close Data Update (`08:30–09:00` or after `14:30`)
1. **Acquire Authorized Data Only**: Download the latest official BVMT historical/daily CSV from `https://www.bvmt.com.tn/` and any relevant CMF/BVMT company disclosures into `data/staging/`.
2. **Immutable Snapshot & Validation**: Run `uv run bvmt import-csv ...`.
   - Raw input bytes are hashed (SHA-256) and stored immutably in `data/raw/<source_id>/`.
   - Validated bars are written to `data/processed/<source_id>/validated_bars.csv`.
   - Any malformed, negative-volume, or inconsistent OHLC rows are quarantined in `rejected_rows.json`.
3. **Coverage & Freshness Audit**: Run `uv run bvmt coverage-check ...` to distinguish open exchange sessions, holidays, suspended instruments, zero-volume (`no_trade_session`) bars, and missing files (`missing_observation` / `stale_quote`).

### Phase B — Ledger Reconciliation (Before Generating Recommendations)
1. Open `https://www.tunisbourse-challenge.com/` and inspect your **Portefeuille** and **Carnet d'ordres**.
2. For every order currently marked `PENDING` or `PARTIALLY_FILLED` in your local ledger:
   - Record any fills (executed shares, execution price, and `0.50%` fee).
   - If an order was cancelled, rejected (e.g., due to the 10% single-stock cap), or expired after 1 week, update its status so reserved cash and share limits are released.
3. Verify that local **Settled Cash**, **Reserved Cash**, and **Share Holdings** match your competition account.

### Phase C — Signal Review & Manual Execution (`09:00–14:15 Africa/Tunis`)
1. Review the ranked `Continu_Principal` stocks and action states (`BUY CANDIDATE`, `HOLD`, `REDUCE`, `SELL CANDIDATE`, `NO TRADE`).
2. Inspect the recommendation card's `recommendation_id`, source timestamps, quantitative metrics (`momentum_20s`, `momentum_60s`, `relative_strength_20s`, `median_turnover_20s`, `trade_frequency_20s`), and verbatim event citations.
3. If you decide to act on a recommendation:
   - Manually enter the order on `tunisbourse-challenge.com`.
   - Immediately record the order in the local ledger as `PENDING` (referencing the `recommendation_id`) so the system reserves the required cash (`quantity * price * 1.005`) and prevents duplicate recommendations.

---

## 3. Fault Handling & Fail-Closed Rules

| Fault Condition | System Behavior | Recovery Action |
| :--- | :--- | :--- |
| **Source file unavailable or not yet downloaded** | Emits `ALERT_DATA_STALE` (`BLOCKER`). Refuses to forward-fill missing session prices. Withholds executable order quantity sizing (`NO TRADE`). | Download the latest official BVMT file into `data/staging/` and run `bvmt import-csv`. |
| **Malformed CSV rows or invalid OHLC** | Quarantines bad rows in `rejected_rows.json` with exact line numbers and raw values. Never silently guesses or repairs bad market data. | Inspect `rejected_rows.json`; if the source format changed, update the explicit source adapter in `src/bvmt/data.py`. |
| **Price disagreement across sources** | Flags discrepancy and withholds recommendations for the affected instrument until resolved. | Prefer the primary Tier-1 official `bvmt.com.tn` quote file over secondary portals. |
| **Unreconciled `PENDING` order from a prior session** | Blocks new `BUY CANDIDATE` / `SELL CANDIDATE` sizing on that instrument (and freezes reserved cash) until the user confirms current status. | Check `tunisbourse-challenge.com` and mark the order `EXECUTED`, `PARTIALLY_FILLED`, `STILL_PENDING`, `CANCELLED`, or `EXPIRED`. |
| **Alibaba LLM budget exhausted or model expired (`-12h` cutoff)** | `evaluate_dry_run` / `execute_structured_extraction` blocks the API call locally before any network request. Document search automatically falls back from `cosine_embedding_sidecar` to deterministic local `bm25_lexical_fallback`. | Continue operating 100% locally with BM25 lexical search and quantitative session rankings (`rank_session_baseline`). |
| **Competition rule attribute still `null` in `configs/competition.json`** | `bvmt rules-check` exits with code `2` (`BLOCKED`). Recommendations explicitly display unverified rule warnings. | Update `configs/competition.json` only when official written evidence from the organizer is obtained and snapshotted. |

---

## 4. Scheduling Policy

- **No autonomous background scheduler is enabled by default.**
- Never configure any scheduled job to interact with `tunisbourse-challenge.com` or submit orders.
- After **T10 (Operational Dry Run)** is approved, an optional Windows Task Scheduler task may be configured solely to run local data validation and local catch-up alert checks when the user logs into Windows, using a single-writer lockfile (`artifacts/locks/daily_run.lock`), unique run IDs, and idempotent snapshots.

---

## 5. Backups & Clean Restoration Verification

### 5.1 What Must Be Backed Up
Back up the following local directories regularly (for example, to an external USB drive or private encrypted archive):
1. `configs/` — Competition rule evidence (`configs/competition.json`), research parameters (`configs/research.json`), and LLM budget ledgers (`configs/llm_budget.example.json`).
2. `data/raw/` and `data/processed/` — Immutable SHA-256 source snapshots, `manifest.json` files, `validated_bars.csv`, and `rejected_rows.json`.
3. `data/portfolio/` (Milestone 1C) — Manual order journal, fill history, and cash/share reconciliation ledger.
4. `artifacts/` — Generated recommendation reports, LLM usage ledgers (`artifacts/llm_usage/`), document chunks/embedding sidecars (`artifacts/doc_index/`), and alert logs (`artifacts/alerts/`).

### 5.2 Clean Restore Verification Procedure
To verify that a backup is complete and uncorrupted:
1. Extract the backup into a clean folder on your machine.
2. Run `uv sync --locked --group dev` and `uv run python scripts/check.py`.
3. Verify that every snapshot file in `data/raw/<source_id>/<sha256>.bin` matches its filename SHA-256 digest and the `raw_sha256` recorded in `data/processed/<source_id>/manifest.json`.
4. Keep raw licensed third-party data out of public Git repositories.
