# BVMT Trading Intelligence — Daily Trading Operations Playbook

**Scope**: Standard Operating Procedures for daily decision-support, market data ingestion, manual competition execution, and end-of-day reconciliation for the Tunis Bourse Challenge virtual trading competition.

---

## 1. Operating Schedule & Rules of Engagement

All times are in **Africa/Tunis (UTC+1)**, matching official Bourse de Tunis trading hours.

| Time Window | Operational Phase | Primary Objective |
| :--- | :--- | :--- |
| **08:30 – 09:00** | **Pre-Session Verification** | Verify system health, inspect portfolio baseline, review strategy signals. |
| **09:00 – 14:15** | **Live Exchange Session** | Monitor prices, execute manual orders on portal, record transactions. |
| **14:30 – 15:30** | **Post-Session EOD Catch-Up** | Ingest official BVMT closing prices, sync portal holdings, record paper signals. |

### Strict Non-Negotiable Boundaries
1. **Zero Autonomous Order Submission**: The platform is strictly 100% decision-support. No API keys, credentials, or network calls are ever used to submit orders to `tunisbourse-challenge.com`.
2. **Human-in-the-Loop Portfolio Mutation**: The real competition ledger (`data/portfolio/real_competition_ledger.json`) is never modified automatically. Every browser snapshot diff must be explicitly reviewed and confirmed.
3. **No Lookahead Data**: No signals may be computed or evaluated using price bars published after the respective session decision cutoff.

---

## 2. Pre-Session Checklist (08:30 – 09:00)

Complete this checklist prior to the 09:00 market open:

### Step 2.1 — Start the Application
From the repository root on Windows:
```cmd
.\start_bvmt.bat
```
*(Alternative from PowerShell: `uv run python -m bvmt.cli dashboard`)*

Verify output indicates:
```
[1/2] Starting BVMT FastAPI backend on http://127.0.0.1:8000 ...
[2/2] Starting BVMT Next.js frontend on http://localhost:3000 ...
Services started successfully.
```

### Step 2.2 — Health & Calendar Verification
1. Open `http://localhost:3000/health` in Google Chrome or Microsoft Edge.
2. Confirm the **Market Data Gateway** card displays:
   - **Status**: `HEALTHY`
   - **Provider**: `OFFICIAL_EOD` (Bourse de Tunis Daily Closing Envelope)
   - **Exchange State**: `REGULAR_TRADING_SCHEDULE` (or `SESSION_OPEN` after 09:00)
   - **Sessions Behind**: `0` relative to the last completed session (e.g., Friday 2026-11-06).
3. If an occupied port error or stale warning appears, consult Section 5 (Troubleshooting).

### Step 2.3 — Portfolio Baseline Audit
1. Open `http://localhost:3000/portfolio`.
2. Verify confirmed balances:
   - **Cash Available**: `49,608.050 TND`
   - **BH BANK Holdings**: `30 shares` @ `13.090 TND` = `392.700 TND`
   - **Total Equity**: `50,000.750 TND`
   - **Unrealized P&L**: `+0.750 TND`
3. Verify the banner indicates **"Confirmed Competition Account"** (no pending unconfirmed reconciliation diffs).

### Step 2.4 — Review Model Signals
1. Open `http://localhost:3000/strategy`.
2. Inspect the latest signals from **Model G (Volatility & Turnover Adjusted Momentum)**:
   - Check proposed target allocations.
   - Note any candidates marked for entry or rebalancing.
   - Check liquidity and turnover filters (confirm proposed trades do not exceed 10% median daily volume).

---

## 3. Live Session Protocol (09:00 – 14:15)

The Tunis Bourse continuous quotation group (`Continu_Principal`) trades actively from 09:00 to 14:15.

### Step 3.1 — Order Sizing & Constraint Checks
Before placing any manual trade on `tunisbourse-challenge.com`, ensure the proposal adheres to the competition regulations:
1. **10% Concentration Ceiling**:
   $$\text{Current Position Value} + \text{Proposed Order Value} \le 0.095 \times \text{Total Portfolio Value} \approx 4,750.00\text{ TND}$$
   *(The 0.5% buffer protects against automatic platform liquidation caused by intraday price appreciation).*
2. **Order Type**:
   - For liquid continuously traded stocks: Limit orders at current best bid/ask or reference price.
   - Never place unconstrained market orders on thinly traded BVMT fixings (`Fixing`).
3. **Transaction Fee Reserve**:
   - The competition platform charges an official `0.50%` fee per executed trade. Ensure Available Cash accounts for gross price + fee:
   $$\text{Required Cash} = \text{Shares} \times \text{Limit Price} \times 1.005$$

### Step 3.2 — Manual Execution on Competition Portal
1. Open `https://www.tunisbourse-challenge.com/` in your browser and sign in.
2. Navigate to **Passer un ordre**.
3. Select the target instrument, order type (`Limite`), quantity, and price.
4. Click **Valider l'ordre** and review the confirmation prompt.

### Step 3.3 — Immediate Transaction Logging
1. Once placed, open `http://localhost:3000/transactions` (or CLI `uv run bvmt log-order`).
2. Record the order with state `PENDING_ON_PLATFORM`.
3. This guarantees that:
   - Cash is reserved in the local calculation engine.
   - Duplicate buy recommendations for the same stock are blocked immediately.
   - The order expiration watchdog (1-week platform cancellation limit) starts tracking.

---

## 4. Post-Session EOD Catch-Up & Archival (14:30 – 15:30)

The exchange closes at 14:15. Official EOD closing price envelopes are finalized and published by Bourse de Tunis between **14:30 and 15:15 Africa/Tunis**.

> [!IMPORTANT]
> Do not trigger the daily market data refresh before 14:30. Ingesting before the exchange publishes its final envelopes will yield empty or duplicate previous-day bars.

### Step 4.1 — Ingest Official Closing Data
At or after 14:45 Africa/Tunis:
1. Click **"Refresh Market Data"** on the System Health page (`/health`), or execute:
   ```powershell
   uv run bvmt market-refresh
   ```
2. Verify the gateway response:
   - HTTP status `200 OK` (or `304 Not Modified` if already up to date).
   - Ingested sessions incremented by `+1` (new session: `2026-11-09`).
   - `quality_report.json` shows `0` fatal errors and `0` malformed OHLC bars.
   - Canonical store `data/processed/bvmt_official_2026/daily_bars.canonical.csv` updated atomically.

### Step 4.2 — Synchronize Authenticated Portfolio
To reconcile actual platform executions, cash balances, and competition ranking:
1. Run the headless authenticated collector:
   ```powershell
   uv run bvmt browser-sync
   ```
2. Open `http://localhost:3000/portfolio`.
3. Review the **Reconciliation Diff Card**:
   - Compare cash, holdings, and executed orders against your session transactions.
   - Verify that `reconciliation_gap_tnd == 0.000`.
4. Click **"Confirm Reconciliation"** to commit the new snapshot to `data/portfolio/real_competition_ledger.json`.

### Step 4.3 — Update Forward Paper Trading Track
Generate the out-of-sample forward paper signal for the session:
```powershell
uv run bvmt paper-step --as-of 2026-11-09
```
This records the end-of-day model state in `data/research/paper_trading_log.json` to prove zero-lookahead forward tracking.

### Step 4.4 — End-of-Day Quality Audit & Shutdown
1. Run the full offline quality gate to ensure zero data regressions:
   ```powershell
   uv run python scripts/check.py
   ```
2. Close the browser tabs.
3. In the command terminal running `start_bvmt.bat`, press `Ctrl+C` to cleanly terminate both FastAPI and Next.js processes.

---

## 5. Troubleshooting & Fallback Procedures

### Issue A: `start_bvmt.bat` reports port conflict
- **Symptom**: `[ERROR] Port 8000 (FastAPI) or Port 3000 (Next.js) is already occupied.`
- **Remedy**:
  Find and terminate the orphaned background process:
  ```powershell
  # Check PID on port 8000:
  netstat -ano -p tcp | findstr :8000
  # Stop process:
  taskkill /PID <PID> /F
  ```
  Then restart `.\start_bvmt.bat`.

### Issue B: Streamlit Fallback Mode
If Node.js / Next.js is temporarily unavailable or requires frontend debugging, start the validated Streamlit interface:
```cmd
.\start_bvmt.bat --streamlit
```
The Streamlit dashboard will launch at `http://localhost:8501` using the exact same Python domain engine and persisted ledger files.

### Issue C: Bourse de Tunis Website Timeout or 503
- **Symptom**: `market-refresh` fails with network timeout.
- **Remedy**:
  - The gateway employs exponential backoff (up to 3 retries).
  - If official servers are under maintenance, the gateway retains the existing validated canonical dataset and marks `is_data_fresh: false` on `/health`.
  - Trading recommendations fail-closed to `NO_TRADE` until current-session prices are verified.

### Issue D: Authenticated Browser Sync Authentication Failure
- **Symptom**: `browser-sync` exits with login error.
- **Remedy**:
  - Check credentials stored in environment / config.
  - Inspect `data/snapshots/debug_login_failure.png` and `data/snapshots/debug_portfolio_raw.html`.
  - If a CAPTCHA or re-authentication challenge is presented, log in interactively using non-headless mode:
    ```powershell
    uv run bvmt browser-sync --headed
    ```
