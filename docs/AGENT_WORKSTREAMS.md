# Parallel Agent Workstreams & Ownership Matrix (Gemini & Codex CLI)

This document defines the isolated Git worktree layout, branch strategy, module ownership boundaries, and startup commands for parallel development between **Gemini** and **Codex CLI**.

---

## 1. Central GitHub Repository & Branch Topology

- **Remote (`origin`)**: `https://github.com/medYousseffathallah/onetimetradingbot.git`
- **Branches**:
  1. **`main`** — Stable integration branch. Always kept green (`91+` passing tests, `ruff`, `mypy --strict`, `validate_skills.py`).
  2. **`gemini/dashboard`** — Dedicated feature/workstream branch for Gemini (UI, manual trading ledger, recommendations presentation, alerts, and Windows launcher).
  3. **`codex/data-research`** — Dedicated feature/workstream branch for Codex CLI (Alibaba Model Studio API audit/transport, official BVMT historical CSV ingestion, CMF document ingestion, data validation/provenance, and quantitative research/backtesting).

---

## 2. Physical Worktree Directories (Windows)

All three workspaces share the same underlying Git object database via `git worktree`, ensuring zero repository duplication while isolating working-tree files and branches:

| Workspace Role | Branch | Physical Directory Path |
| :--- | :--- | :--- |
| **Stable Integration Workspace** | `main` | `c:\Users\Thinkcenter\Desktop\BVMT\bvmt-starter-kit` |
| **Gemini Workspace** | `gemini/dashboard` | `c:\Users\Thinkcenter\Desktop\BVMT\bvmt-gemini-dashboard` |
| **Codex CLI Workspace** | `codex/data-research` | `c:\Users\Thinkcenter\Desktop\BVMT\bvmt-codex-research` |

---

## 3. Strict Module & File Ownership Matrix

Neither agent may modify or rewrite files owned by the other workstream without explicit user authorization and an integration merge on `main`.

### A. Gemini Ownership (`gemini/dashboard`)
- **Primary Responsibility**: Dashboard and user experience, manual portfolio ledger, recommendation presentation, notifications, Windows launcher, and dashboard integration tests.
- **Owned Files**:
  - `src/bvmt/dashboard.py` — 6-page local Streamlit decision-support terminal
  - `src/bvmt/ledger.py` — `Decimal` manual portfolio and order lifecycle ledger (`PortfolioLedger`)
  - `src/bvmt/recommendations.py` — 5-state recommendation card generator (`BUY CANDIDATE`, `HOLD`, `REDUCE`, `SELL CANDIDATE`, `NO TRADE`)
  - `src/bvmt/notifications.py` — Persistent deduplicated local alert center and power-off catch-up engine (`NotificationCenter`)
  - `start_bvmt.bat` — Windows one-click local launcher
  - `tests/test_milestone_1c.py` — End-to-end manual trading simulation, failure drills, and Streamlit `AppTest` UI suite
  - `docs/USER_GUIDE.md`, `docs/MANUAL_TRADING_WORKFLOW.md`, `docs/NOTIFICATIONS.md`

### B. Codex CLI Ownership (`codex/data-research`)
- **Primary Responsibility**: Alibaba Model Studio API audit and transport, official BVMT historical data ingestion, CMF document ingestion, data validation and provenance, quantitative research and backtesting, and research-related automated tests.
- **Owned Files**:
  - `src/bvmt/llm.py` — Alibaba Cloud Model Studio budget-gated provider, `DashScopeOpenAICompatibleTransport`, document chunking, vector sidecar, and BM25 fallback
  - `src/bvmt/data.py` — Canonical and French BVMT CSV parsers, bar validation, and `import_local_csv`
  - `src/bvmt/snapshots.py` — Content-addressed SHA-256 raw snapshots and atomic writes
  - `src/bvmt/calendar.py` — Dated instrument master, `Africa/Tunis` exchange sessions, suspensions, and coverage diagnostics
  - `src/bvmt/features.py` — Session-aware quantitative baseline ranking (`rank_session_baseline`)
  - `src/bvmt/rules.py` — Fail-closed competition rules audit
  - `tests/test_data_import.py`, `tests/test_calendar.py`, `tests/test_features.py`, `tests/test_llm_budget.py`, `tests/test_smoke.py`
  - `docs/ALIBABA_INTEGRATION_PLAN.md`, `docs/BVMT_DATA_SOURCES.md`, `docs/SIGNAL_METHODOLOGY.md`, `docs/LLM_TRADING_INTELLIGENCE.md`

### C. Shared / Coordinated Files (Integrator Managed on `main`)
- `src/bvmt/cli.py`, `pyproject.toml`, `uv.lock`, `configs/`, `schemas/`, `AGENTS.md`, `README.md`, `task.md`, `docs/STATE.md`
- **Rule**: If either agent needs a new CLI subcommand or dataclass field across the boundary (e.g., between `SessionBaselineReport` in `src/bvmt/features.py` and `generate_recommendations` in `src/bvmt/recommendations.py`), the change must be additive and backward-compatible so existing tests in both worktrees continue to pass.

---

## 4. Exact Commands to Launch & Operate Each Worktree

### Launching Codex CLI in Its Isolated Worktree (`codex/data-research`)
Open a new PowerShell window and run:
```powershell
cd c:\Users\Thinkcenter\Desktop\BVMT\bvmt-codex-research
git status
codex
```
*(To run tests inside the Codex worktree using the shared `uv` toolchain or local `.venv`:)*
```powershell
cd c:\Users\Thinkcenter\Desktop\BVMT\bvmt-codex-research
uv run python scripts/check.py
```

### Operating the Gemini Worktree (`gemini/dashboard`)
```powershell
cd c:\Users\Thinkcenter\Desktop\BVMT\bvmt-gemini-dashboard
git status
uv run python scripts/check.py
uv run bvmt dashboard
```

---

## 5. Non-Negotiable Safety Rules for Both Agents
1. **No Autonomous Order Submission**: Neither Gemini nor Codex may ever connect to `tunisbourse-challenge.com` to submit, modify, or cancel orders.
2. **No Unauthorized Live Alibaba API Calls**: `network_enabled: false` and `BVMT_ALLOW_LIVE_LLM=0` remain the default in all three worktrees. Neither agent may execute live API calls without explicit user authorization.
3. **No Secret Commits**: `.env`, API keys, `data/portfolio/`, `data/raw/*`, `data/processed/*`, and `artifacts/*` must remain excluded from Git.

---

## 6. Orchestration Task Log (2026-11-06 Multi-Agent Execution)

| Task ID | Agent & Branch | Scope & Owned Files | Status | Verification Evidence |
| :--- | :--- | :--- | :--- | :--- |
| **C1** | Codex CLI (`codex/data-research`) | Alibaba Model Studio Integration Audit (`src/bvmt/llm.py`, `tests/test_llm_budget.py`, `docs/ALIBABA_INTEGRATION_PLAN.md`, `.env.example`) | **DONE (`4ebfff1`)** | Regional endpoints (`intl`, `us`, `cn`, workspace URL allowlist), list-content parsing, `ProviderReadinessReport`, and mocked error classification verified (`125 passed` on branch). |
| **C2** | Codex CLI (`codex/data-research`) | Official BVMT Historical Data Ingestion (`src/bvmt/data.py`, `tests/test_data.py`, `docs/BVMT_DATA_SOURCES.md`) | **DONE (`4ebfff1`)** | `bvmt_histo_cotation` adapter, untraded zero-volume bar normalization without forward-filling, `raw_source.csv` + `source_sha256` preservation, and `DataQualityReport` extensions verified. |
| **C3** | Codex CLI (`codex/data-research`) | Research-Only Backtesting Foundation (`src/bvmt/execution.py`, `tests/test_execution.py`) | **DONE (`4ebfff1`)** | `run_historical_backtest` with strict T+1 fills, shared volume participation caps, partial fills & expiry, `0.50%` fees, cash & equal-weight benchmarks, and max drawdown verified. |
| **G1** | Gemini (`gemini/dashboard`) | Real Competition Portfolio CSV Import/Export & Valuation History (`src/bvmt/ledger.py`, `src/bvmt/dashboard.py`, `tests/test_milestone_1c.py`) | **DONE (`d3f9bf8`)** | `parse_account_holdings_csv`, `parse_account_transactions_csv`, `parse_account_pending_orders_csv`, CSV exporters, and `compute_valuation_history` verified (`94 passed` on branch). |
| **G2** | Gemini (`gemini/dashboard`) | Portfolio Reconciliation Engine & Confirmation Gate (`src/bvmt/ledger.py`, `src/bvmt/dashboard.py`, `tests/test_milestone_1c.py`) | **DONE (`d3f9bf8`)** | `reconcile_with_snapshot` (detecting all 6 discrepancy categories without mutating ledger) and `apply_reconciliation_snapshot` (requiring `confirmed_by_user=True`) verified. |
| **G3** | Gemini (`gemini/dashboard`) | 6-Page Dashboard Reliability & Dataset Discovery (`src/bvmt/dashboard.py`, `tests/test_milestone_1c.py`) | **DONE (`d3f9bf8`)** | `discover_available_bar_datasets`, freshness session lag metrics, transaction fill history, and full 6-page `AppTest` navigation verified (`128 passed` integrated on `main`). |

