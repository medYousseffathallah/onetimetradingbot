# BVMT Trading Intelligence — Non-Technical User Guide

## 1. What This Application Does (and What It Never Does)
**BVMT Trading Intelligence** is your personal research desk and portfolio assistant for the **Tunis Bourse Challenge**.
- **What it does**: Validates historical BVMT prices, tracks which stocks are eligible in *Continu du Marché Principal*, flags stale/illiquid/suspended stocks, summarizes official CMF/BVMT company disclosures, recommends target portfolio allocations respecting the **10% single-stock limit** and **0.50% fee**, and keeps an exact ledger of your virtual cash, shares, and pending orders.
- **What it NEVER does**: It **never logs into your Tunis Bourse Challenge account**, **never places orders automatically**, and **never assumes a recommendation was executed** unless you record the result yourself.

---

## 2. How to Start the Application

### Option A — One-Click Local Dashboard (`Milestone 1C`)
1. Double-click **`start_bvmt.bat`** in the `bvmt-starter-kit` folder (or run `uv run bvmt dashboard` in PowerShell).
2. Your web browser will open automatically to **`http://127.0.0.1:8501`** (bound strictly to your own computer `127.0.0.1`—nobody else on the internet or local Wi-Fi can see it).
3. Use the left sidebar to navigate the 6 financial-terminal pages:
   - **Overview**: Portfolio equity, available/reserved/settled cash, holdings, open orders, and active alerts.
   - **Stock Opportunities**: Ranked BVMT securities, `BUY CANDIDATE` / `HOLD` / `REDUCE` / `SELL CANDIDATE` / `NO TRADE` cards, and evidence citations.
   - **Portfolio**: Position weights vs. the 10% cap, average cost basis, unrealized/realized P&L, and `0.50%` fees paid.
   - **Manual Order Journal**: Forms to record `PENDING` orders, full/partial fills (`PARTIALLY_FILLED` / `EXECUTED`), and `CANCELLED` / `REJECTED` / `EXPIRED` orders.
   - **Research and Documents**: Point-in-time document search (BM25 + vector sidecar) and quote-verified corporate events.
   - **System Health**: Exchange calendar coverage, competition-rule blockers, and Alibaba 25-model allowance status.
4. At the top of the screen, check the **Mode Banner**:
   - **SYNTHETIC DEMO MODE (Amber Banner)**: Shown when using built-in test fixtures (`DEMO_A`, `DEMO_B`). Never use synthetic demo numbers to place real competition orders.
   - **VERIFIED LOCAL MARKET DATA (Green Banner)**: Shown when real BVMT data is imported, using house assumptions where simulator details remain unverified.
   - **COMPETITION RULES STATUS: BLOCKED (Red Banner)**: Remains visible while competition rule attributes in `configs/competition.json` are unverified.

### Option B — Command-Line Interface (CLI)
Open **PowerShell** inside the `bvmt-starter-kit` folder and run:
```powershell
uv run bvmt portfolio-init --ledger data/portfolio/ledger.json --initial-cash 100000.000
uv run bvmt recommend --ledger data/portfolio/ledger.json
uv run bvmt portfolio-status --ledger data/portfolio/ledger.json
```

---

## 3. Daily 5-Step Workflow

### Step 1 — Import Today's BVMT Market Data & Disclosures
1. Download the daily/historical quotation CSV from the official **Bourse de Tunis** website (`tunis-stockexchange.com` -> *Market Watch > Historique*) into `data/staging/`.
2. In the dashboard (**Data & Freshness** tab) or via CLI, click **Import CSV** (or run `uv run bvmt import-csv ...`).
3. The app automatically:
   - Saves an unalterable copy of the file (`data/raw/`).
   - Converts French numbers (`10,800` -> `10.800`) and dates (`DD/MM/YYYY` -> `YYYY-MM-DD`).
   - Quarantines any corrupted or duplicate rows into `rejections.json` and shows a **Data Freshness Badge** (e.g., *"Latest BVMT Session: 2026-11-05 (Fresh)"* or *"WARNING: Data is 3 open sessions old"*).

### Step 2 — Review Portfolio Overview & Alerts
Open the **Portfolio & Alerts** tab to see:
- **Available Cash (TND)**, **Cash Reserved in Pending Buy Orders (TND)**, **Holdings Market Value (TND)**, and **Total Portfolio Equity (TND)**.
- **Current Weight per Stock (%)** vs. the **10.0% Competition Cap**.
- **Active Alerts**:
  - Pending orders approaching the **1-week simulator expiration limit**.
  - Holdings that became **suspended** or **stale** (zero volume for $\ge 3$ sessions).
  - New material company announcements (dividends, quarterly activity indicators, earnings).

### Step 3 — Inspect Ranked Stocks & Action Recommendations
Open the **Recommendations & Research** tab. Every eligible *Continu du Marché Principal* stock is assigned one of five explicit statuses:
- **`BUY CANDIDATE`**: High risk-adjusted momentum + positive/neutral fundamental catalyst, passes liquidity filters, and you have available cash and room under the 10% cap.
- **`HOLD`**: Already in your portfolio, ranking remains above the turnover buffer, and exposure is $\le 10\%$.
- **`REDUCE`**: Stock is approaching or exceeding the 10% concentration limit or liquidity is thinning.
- **`SELL CANDIDATE`**: Trend breakdown, adverse verified financial disclosure, or surpassed by a significantly stronger candidate (exceeding the 1.00% round-trip fee hurdle).
- **`NO TRADE` (Blocked/Excluded)**: Stock is `suspended`, `stale_quote` (zero volume), `insufficient_liquidity`, outside *Continu du Marché Principal*, or missing fresh data.

Click any stock row to inspect its **Evidence Card**:
- Exact `recommendation_id` (e.g., `REC-20261105-TN0001000010-01`).
- Source data timestamp (`data_cutoff`) and analysis timestamp (`generated_at`).
- 20-session and 60-session momentum, median daily turnover (TND), and trading frequency (%).
- Verbatim quotes and page locators from official CMF/BVMT PDFs (when available), plus any **Independent Critic (`Role 3`) risk flags**.

### Step 4 — Place Chosen Orders Manually on the Competition Website
If you decide to act on a recommendation:
1. Log into **`https://www.tunisbourse-challenge.com/`** in your browser.
2. Manually enter the order (Market or Limit, Quantity, Price) during or before the **09:00–14:15 `Africa/Tunis`** execution window.
3. **Never assume the order filled immediately**: On the Tunis Bourse Challenge simulator, all orders enter a **Pending** state first and may partially fill, wait for the next session, or stay pending if the stock does not trade.

### Step 5 — Record Your Order & Fills in the Local Journal
In the **Manual Trade Journal** tab:
1. Click **"Log Manual Order Submitted"** next to the `recommendation_id` (recording order type, quantity, limit price, and submission time). The app moves that cash or share quantity into **Reserved / Pending** so it will not recommend buying the same stock twice.
2. When you check your competition account later (`Mouvements` / `Portefeuille`), update the order status in the app:
   - **`PENDING`**: Still waiting in the simulator queue.
   - **`PARTIALLY_FILLED`**: Enter the executed share quantity, execution price, and `0.50%` fee; the remaining shares stay pending.
   - **`EXECUTED` (Filled)**: Enter the final fill price and fee; holdings and cash update automatically.
   - **`CANCELLED` / `REJECTED` / `EXPIRED`**: Releases reserved cash/shares back to available balance.

---

## 4. How to Shut Down Safely
1. Make sure any journal entry you typed is saved (all writes in BVMT Trading Intelligence use **atomic file saves**, so your ledger cannot be half-written).
2. In the PowerShell terminal window where the dashboard is running, press **`Ctrl + C`** once (or close the terminal window after saving).
3. All your data (`data/raw/`, `data/processed/`, and your portfolio journal) remains safely stored on your hard drive for the next session.

