# Notifications, Alerts, and Power-Off Catch-Up Architecture

This document defines the notification and alerting system for the **BVMT Trading Intelligence** local decision-support platform.

---

## 1. Core Principles

1. **Local-First by Default**: All alerts are generated, persisted, and displayed locally inside the application's notification ledger (`artifacts/alerts/alert_log.jsonl`) and the **Local Streamlit Dashboard Alert Banner** first.
2. **Zero Paid Background Infrastructure**: The system does not require a paid cloud server, a hosted database, or a permanently running background AI agent.
3. **Optional External Channels Are Strictly Opt-In**: External delivery channels (such as Windows desktop toast notifications, local SMTP email, or a private Telegram/Webhook notification) are disabled by default (`external_alerts_enabled: false`) and require explicit user configuration via environment variables.
4. **Never Act Autonomously**: An alert only informs the human participant; no notification trigger can submit, modify, or cancel a competition order.
5. **Deduplication & Audit Trail**: Every alert has a deterministic `alert_id` derived from `(alert_type, instrument_id_or_order_id, session_date, trigger_hash)` so repeated evaluations on the same session do not spam the user.

---

## 2. Alert Categories and Triggers

The notification engine evaluates five explicit trigger categories whenever market data is imported, a manual order is recorded, or the dashboard starts up:

| Category ID | Alert Name | Severity | Trigger Condition | User Action Required |
| :--- | :--- | :--- | :--- | :--- |
| **`ALERT_SIGNAL_HIGH`** | High-Priority Research Signal | `INFO` / `ACTION_REVIEW` | A stock in the `Continu_Principal` universe transitions into **`BUY CANDIDATE`** (top quintile composite score, positive 20/60-session momentum, passes liquidity/staleness gates) or an existing holding transitions into **`SELL CANDIDATE`** / **`REDUCE`**. | Review the recommendation card, inspect evidence citations, and decide whether to place a manual order on `tunisbourse-challenge.com`. |
| **`ALERT_EVENT_MATERIAL`** | Material Corporate Announcement | `HIGH` | A newly indexed CMF / BVMT disclosure (`schemas/event.schema.json`) with verified verbatim quote (`quote_verified: true`) affects a held stock or top-10 candidate (e.g., dividend announcement, earnings shock, trading suspension, capital operation). | Read the extracted French/Arabic quote and original filing before placing or keeping an order on that stock. |
| **`ALERT_RISK_CONCENTRATION`** | Portfolio Risk & 10% Cap Warning | `WARNING` / `CRITICAL` | Current market value of a single holding (plus any `PENDING` buy orders) exceeds **8.5%** (`WARNING`) or **9.5%** (`CRITICAL`) of total portfolio value, approaching the competition's hard **10% single-stock cap** (which triggers simulator auto-reduction or purge). | Do not add to the position; consider a manual **`REDUCE`** order if market appreciation pushes the weight above 10%. |
| **`ALERT_ORDER_EXPIRY`** | Pending Order 1-Week Expiration Reminder | `WARNING` / `URGENT` | A manual order recorded as `PENDING` or `PARTIALLY_FILLED` in the local ledger reaches **4 open exchange sessions** (`WARNING`) or **5+ calendar days / 6+ calendar days** (`URGENT`) since `submitted_at_utc`, approaching the simulator's **1-week automatic expiration rule**. | Check your `tunisbourse-challenge.com` order book (`Carnet d'ordres`) to verify whether the order filled, remains queued due to zero volume, or expired. |
| **`ALERT_DATA_STALE`** | Missing or Stale Market Data / Unreconciled Ledger | `BLOCKER` | (a) Latest imported BVMT market data is older than the most recent completed `ExchangeSession` (`stale_quote` / `missing_observation`), (b) an instrument is under official suspension, or (c) a `PENDING` order from a prior session has not been reconciled by the user. | Import the latest official BVMT daily CSV (`bvmt import-csv`) and/or update the status of pending orders before trusting new position sizes. |

---

## 3. Alert Channels

### 3.1 Primary Channel: Local Dashboard Alert Center (Always Enabled)

- Displayed at the top of the local Streamlit dashboard and in the CLI summary output.
- Groups active alerts by severity (`BLOCKER` -> `CRITICAL` -> `URGENT` -> `WARNING` -> `ACTION_REVIEW` -> `INFO`).
- If any `BLOCKER` alert is active (for example, stale market data or an unreconciled prior-session order), the dashboard visually locks executable order-quantity sizing and displays **`NO TRADE — DATA OR LEDGER RECONCILIATION REQUIRED`**.
- Each alert card includes an **Acknowledge / Resolve** button that records `acknowledged_at_utc` and the resolution action in `artifacts/alerts/alert_log.jsonl`.

### 3.2 Secondary Channel: Local Windows Desktop Notification (Optional, Zero Cloud Cost)

- Uses standard local OS notifications on Windows when the dashboard or daily check script runs.
- Controlled by `local_desktop_toast_enabled: false` (default) in user preferences.
- Requires no internet connection or third-party account.

### 3.3 Tertiary Channel: Optional External Alert Delivery (Strictly Opt-In)

For users who want a notification on their phone when a manual check finishes or when a scheduled local task runs while their PC is on:

- **Supported Opt-In Adapters (Planned in Milestone 1C / T10)**:
  - **Webhook / Telegram Bot / Discord Webhook**: Configured via `BVMT_ALERT_WEBHOOK_URL` in `.env` (never stored in Git).
  - **SMTP Email**: Configured via `BVMT_SMTP_HOST`, `BVMT_SMTP_USER`, `BVMT_SMTP_PASSWORD`, and `BVMT_ALERT_EMAIL_TO` in `.env`.
- **Safety Rules for External Channels**:
  - Disabled by default (`external_alerts_enabled: false`).
  - Never transmits API keys, raw licensed datasets, or personal credentials.
  - Sends only a concise summary (Alert Category, Instrument Ticker, Recommendation ID, Session Date, and a reminder to open the local dashboard).
  - Fails open for local usage: if the internet is disconnected or an external webhook fails, the local dashboard and ledger continue operating normally and log a local delivery warning.

---

## 4. Exact Behavior When the Computer Is Switched Off

Because the system runs **100% locally on your personal Windows machine** with zero paid cloud servers:

1. **While the Computer Is Switched Off (or Asleep / App Closed)**:
   - **No background process runs** and **no real-time alerts are emitted** while the computer is powered off.
   - The system does **not** pretend to monitor the market 24/7 from the cloud.
   - Your local portfolio ledger (`data/portfolio/ledger.json`) and alert state (`artifacts/alerts/state.json`) remain safely stored on disk at their last saved state (`last_evaluated_at_utc`).

2. **Automatic Catch-Up Evaluation on Next Startup (`start_bvmt.bat` or `bvmt dashboard`)**:
   - The moment you switch on your computer and launch the application, the **Startup Catch-Up Engine** runs automatically before displaying any recommendations:
     - **Step 1 — Clock & Session Gap Check**: Compares current `Africa/Tunis` time against `last_evaluated_at_utc` and the exchange calendar (`ExchangeSession`). Identifies how many BVMT trading sessions (`09:00–14:15`) occurred while the PC was off.
     - **Step 2 — Pending Order Age & 1-Week Expiration Check**: Scans every order in `PENDING` or `PARTIALLY_FILLED` status.
       - If an order crossed the **4-session warning threshold** while the PC was off, it immediately raises an `ALERT_ORDER_EXPIRY` (`WARNING`) banner.
       - If an order exceeded **7 calendar days (`1 week`)** while the PC was off, it flags the order as **`LIKELY_EXPIRED_VERIFY_ON_WEBSITE`** (`URGENT`) and prompts you to confirm its expiration or partial fill from `tunisbourse-challenge.com`.
     - **Step 3 — Data Freshness Check**: Checks whether the latest imported price bar (`latest_bar_session_date`) matches the most recent completed BVMT session. If you were away for one or more sessions and have not imported the latest CSV yet, it raises `ALERT_DATA_STALE` (`BLOCKER`) and prevents stale order sizing until you import the latest file.
     - **Step 4 — Catch-Up Summary Modal**: Displays a clear **"Since Your Last Session (`YYYY-MM-DD HH:MM`)"** summary at the top of the dashboard listing all missed session dates, pending orders requiring verification, and required data imports.

---

## 5. Alert Schema Record (`artifacts/alerts/alert_log.jsonl`)

Every generated alert is appended as a deterministic JSON record:

```json
{
  "alert_id": "ALT-20261105-ORDER_EXPIRY-ORD-20261030-001",
  "created_at_utc": "2026-11-05T08:45:00Z",
  "session_date": "2026-11-05",
  "category": "ALERT_ORDER_EXPIRY",
  "severity": "URGENT",
  "instrument_id": "BIAT",
  "related_order_id": "ORD-20261030-001",
  "related_recommendation_id": "REC-20261030-BIAT-01",
  "caught_up_after_power_off": true,
  "title": "Pending BUY order on BIAT is 6 days old (1-week simulator expiry tomorrow)",
  "message": "Order ORD-20261030-001 (BUY 15 BIAT @ 95.500 TND) was placed on 2026-10-30. Unfilled competition orders expire automatically after 1 week. Check tunisbourse-challenge.com Carnet d'ordres and update status.",
  "status": "OPEN",
  "acknowledged_at_utc": null
}
```

