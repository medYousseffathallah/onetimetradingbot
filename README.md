# BVMT Trading Intelligence

A local-first, human-supervised research and decision-support application for the **Tunis Bourse Challenge** (virtual Tunisian stock competition).

- **Not an autonomous trading bot**: This application never connects to a broker, never submits orders to `tunisbourse-challenge.com`, and never requests your competition account password.
- **Current status (Milestone 1C Complete)**: Core CLI, local CSV ingestion (`canonical` & `french_bvmt`), dated instrument master, official-source exchange calendar (`T03`), session-aware quantitative baseline ranking (`T04` / `Milestone 1B`), budget-gated Alibaba Cloud Model Studio extraction/indexing with standard-library HTTPS transport (`Milestone 1A`), `Decimal` manual portfolio ledger (`src/bvmt/ledger.py`), 5-state recommendation engine (`src/bvmt/recommendations.py`), local alert center with power-off catch-up (`src/bvmt/notifications.py`), 6-page local Streamlit dashboard (`src/bvmt/dashboard.py`), and one-click Windows launcher (`start_bvmt.bat`) are **implemented and tested (`90+` automated tests passing)**.

---

## 1. Quick Start & Installation (Verified Commands)

### First-Time Setup
From the repository root (`bvmt-starter-kit`) on Windows PowerShell, macOS, or Linux (requires Python 3.12 or 3.13):

```powershell
# 1. Install uv (if not already installed) and synchronize the locked environment + Streamlit dashboard
python -m pip install uv
python scripts/bootstrap.py
uv sync --locked --group dev --extra dashboard

# 2. Verify all offline unit tests, type checks, and skill validators pass
uv run python scripts/check.py
```

### Zero-Install Standard-Library Smoke Check (No Network Needed)
```powershell
python scripts/smoke_check.py
```

---

## 2. Launching the Local Dashboard (`Milestone 1C`)

### Option A — One-Click Windows Launcher
Double-click **`start_bvmt.bat`** in the repository root, or run from PowerShell:
```powershell
.\start_bvmt.bat
```

### Option B — CLI Command
```powershell
uv run bvmt dashboard
```
Opens the 6-page local financial terminal at **`http://127.0.0.1:8501`** (bound strictly to `127.0.0.1` localhost):
1. **Overview**: Portfolio equity, available/reserved/settled cash, holdings, open orders, active alerts, and synthetic/rules banners.
2. **Stock Opportunities**: Ranked BVMT securities, `BUY CANDIDATE` / `HOLD` / `REDUCE` / `SELL CANDIDATE` / `NO TRADE` cards, fee-adjusted sizing, and evidence citations.
3. **Portfolio**: Holdings, position weights vs. the 10% cap, average acquisition prices, unrealized/realized P&L, and `0.50%` fees paid.
4. **Manual Order Journal**: Forms to record `PENDING` orders, full/partial fills (`PARTIALLY_FILLED` / `EXECUTED`), and `CANCELLED` / `REJECTED` / `EXPIRED` orders, plus the append-only audit trail.
5. **Research and Documents**: Point-in-time local document chunk search (BM25 + embedding sidecar) and quote-verified corporate events.
6. **System Health**: Exchange calendar coverage, 72 competition-rule blockers, and Alibaba 25-model free-quota allowance status.

---

## 3. Verified CLI Commands

All commands run locally and never place trades or make live API calls by default:

### A. Initialize & Inspect Manual Portfolio Ledger (`Milestone 1C`)
```powershell
# Initialize a 100,000.000 TND virtual portfolio
uv run bvmt portfolio-init --ledger data/portfolio/ledger.json --initial-cash 100000.000

# Inspect current holdings, available/reserved cash, and open orders
uv run bvmt portfolio-status --ledger data/portfolio/ledger.json
```

### B. Generate 5-State Trading Recommendations (`Milestone 1C`)
```powershell
uv run bvmt recommend `
  --ledger data/portfolio/ledger.json `
  --instruments tests/fixtures/instrument_master.csv `
  --calendar tests/fixtures/exchange_calendar.csv `
  --bars tests/fixtures/daily_bars.csv `
  --cutoff 2026-01-09T17:00:00+00:00 `
  --short-lookback 2 `
  --long-lookback 3 `
  --min-median-turnover 5000 `
  --output artifacts/recommendations-report.json
```

### C. Record Manual Orders, Partial Fills & Cancellations via CLI (`Milestone 1C`)
```powershell
# 1. Record a manually placed BUY order as PENDING (reserves cash + 0.50% fee)
uv run bvmt order-submit `
  --ledger data/portfolio/ledger.json `
  --order-id ORD-20260109-001 `
  --instrument-id DEMO_A `
  --symbol DEMO_A `
  --side BUY `
  --quantity 100 `
  --limit-price 10.800 `
  --recommendation-id REC-20260109-DEMOA-01

# 2. Record a partial or full fill
uv run bvmt order-fill `
  --ledger data/portfolio/ledger.json `
  --order-id ORD-20260109-001 `
  --filled-shares 60 `
  --execution-price 10.800

# 3. Cancel or expire remaining open shares (releases unused reserved cash)
uv run bvmt order-close `
  --ledger data/portfolio/ledger.json `
  --order-id ORD-20260109-001 `
  --status CANCELLED `
  --reason "Cancelled remaining 40 shares"
```

### D. Import & Validate a Local Historical BVMT CSV (`T02`)
```powershell
uv run bvmt import-csv tests/fixtures/french_bvmt_sample.csv `
  --source-id bvmt_hist_sample `
  --format french_bvmt `
  --permission-status authorized_local_import `
  --retrieved-at 2026-01-15T18:00:00+00:00 `
  --raw-dir data/raw `
  --output-dir data/processed/bvmt_hist_sample
```

### E. Evaluate Instrument Master, Exchange Calendar & Observation Coverage (`T03`)
```powershell
uv run bvmt coverage-check `
  --instruments tests/fixtures/instrument_master.csv `
  --calendar tests/fixtures/exchange_calendar.csv `
  --bars tests/fixtures/daily_bars.csv `
  --output artifacts/coverage-report.json
```

### F. Run Session-Aware Quantitative Baseline Ranking (`T04` / `Milestone 1B`)
```powershell
uv run bvmt session-rank `
  --instruments tests/fixtures/instrument_master.csv `
  --calendar tests/fixtures/exchange_calendar.csv `
  --bars tests/fixtures/daily_bars.csv `
  --cutoff 2026-01-09T17:00:00+00:00 `
  --short-lookback 2 `
  --long-lookback 3 `
  --min-median-turnover 5000 `
  --output artifacts/session-baseline-report.json
```

### G. Run Alibaba Cloud Model Studio Budget & Expiry Dry-Run (`Milestone 1A`)
```powershell
uv run bvmt llm-dry-run `
  --config configs/llm_budget.example.json `
  --model qwen3.7-text-embedding `
  --role document_chunk_embedding_pilot `
  --now 2026-11-05T18:35:00+01:00
```

### H. Check Competition Rule Readiness Gate (`T01`)
```powershell
uv run bvmt rules-check --config configs/competition.json
```
*(Intentionally exits with code `2` and `"status": "blocked"` while competition rules and human review sign-off remain incomplete.)*

---

## 4. Documentation Map

| Guide | Purpose |
|---|---|
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | Step-by-step guide for non-technical users: starting, importing data, running analysis, reading recommendations, recording manual trades, and shutting down safely |
| [docs/MANUAL_TRADING_WORKFLOW.md](docs/MANUAL_TRADING_WORKFLOW.md) | Recommendation lifecycle (`recommendation_id`), manual order placement on `tunisbourse-challenge.com`, recording pending/partial/filled/expired orders, and cash/share reconciliation |
| [docs/SIGNAL_METHODOLOGY.md](docs/SIGNAL_METHODOLOGY.md) | How `BUY CANDIDATE`, `HOLD`, `REDUCE`, `SELL CANDIDATE`, and `NO TRADE` classifications are computed from session-aware features, event intelligence, and competition caps |
| [docs/NOTIFICATIONS.md](docs/NOTIFICATIONS.md) | Local dashboard alert center, optional external channels, deduplication, and exact behavior when the computer is switched off |
| [docs/OPERATIONS.md](docs/OPERATIONS.md) | Daily operational checklist, fault handling, backups, restoration, and offline guarantees |
| [docs/BVMT_DATA_SOURCES.md](docs/BVMT_DATA_SOURCES.md) | Official BVMT & CMF historical data sources and manual download instructions |
| [docs/GITHUB_REUSE_EVALUATION.md](docs/GITHUB_REUSE_EVALUATION.md) | Evaluation of Qlib, Backtrader, VectorBT, and FinGPT |
| [docs/ALIBABA_INTEGRATION_PLAN.md](docs/ALIBABA_INTEGRATION_PLAN.md) | Complete 25-model Alibaba Cloud Model Studio budget, Stop-on-Exhaustion setting, expiration, vector sidecar, and BM25 fallback plan |
| [docs/LOW_COST_ARCHITECTURE.md](docs/LOW_COST_ARCHITECTURE.md) | Permanent CPU-only, $0/month local architecture |
| [docs/COMPETITION_RULES_CHECKLIST.md](docs/COMPETITION_RULES_CHECKLIST.md) | Official `reglement.aspx` + participant-supplied `help.aspx` FAQ evidence and remaining blockers |
