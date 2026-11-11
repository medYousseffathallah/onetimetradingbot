# Milestone 13 Execution Plan: Reliability, Performance Optimization & Missed-Opportunity Research

**Date**: Wednesday, November 11, 2026  
**Primary Project Orchestrator**: Codex (Architecture, Task Decomposition, Frontend Performance, Code Review, Integration, Final Acceptance)  
**Backend & Quant Research Agent**: Gemini (Sync Reliability Audit, Data Quality Research, ICF Autopsy, Quantitative Scoring, Sparse-Data Analysis, Strategy Experiments, Backend Tests)  
**Governing Constraints**: 100% Localhost • Zero Autonomous Trading • Zero Cloud Storage / Hosted Agents • Zero Unapproved Paid API Calls • Preserve Real Portfolio Ledger & All Historical Snapshots

---

## 1. Phase 0 — Verified Baseline Project State

### 1.1 Git Worktree & Branch State
| Worktree Path | Branch | HEAD Commit | Status |
| :--- | :--- | :--- | :--- |
| `c:\Users\Thinkcenter\Desktop\BVMT\bvmt-starter-kit` | `main` | `10a33a6` (5 commits ahead of `origin/main`) | 4 uncommitted modified files preserved (not staged/reset) |
| `c:\Users\Thinkcenter\Desktop\BVMT\bvmt-gemini-dashboard` | `gemini/dashboard` | `9b7c9ba` (ancestor of `10a33a6`) | Clean working tree |
| `c:\Users\Thinkcenter\Desktop\BVMT\bvmt-codex-research` | `codex/data-research` | `9b7c9ba` (ancestor of `10a33a6`) | Clean working tree |

**Latest Integrated Commits on `main` (ahead of `9b7c9ba`)**:
- `2bf1441` — `fix(sync): resolve challenge table column offsets, 'Vendre' button suppression, and Montant identity`
- `ecf492e` — `feat(accounting): Milestone 12 - daily session accounting, cash-flow reconciliation, and strategy feedback`
- `f9f2447` — `chore: clean up trailing newlines in docs and tests`
- `36ebc34` — `fix(planner): resolve day_trading_notice field mismatch and add defensive fallbacks`
- `10a33a6` — `docs: update STATE.md with pre-market readiness and Trade Planner hotfix`

**Preserved Uncommitted Changes on `main`**:
- `src/bvmt/ledger.py` — Deduplicates `(snapshot_id, capture_timestamp)` before appending to `PortfolioLedger.snapshot_history`.
- `src/bvmt/api.py` — Filters empty `capture_timestamp` and deduplicates `confirmed_history` in `GET /api/snapshots`.
- `frontend/src/app/page.tsx` — Adds index suffix to React `key` in holdings table.
- `frontend/src/app/portfolio/page.tsx` — Adds index suffix to React `key` in holdings and snapshot history tables.

### 1.2 Baseline Quality & Startup Inventory
| Check / Module | Result | Measured Details |
| :--- | :--- | :--- |
| `pytest -q` | **PASS** | `388 passed, 1 warning in 101.59s` |
| `ruff check src tests scripts` | **PASS** | All checks passed |
| `mypy src/bvmt` | **PASS** | `Success: no issues found in 32 source files` |
| `scripts/validate_skills.py` | **PASS** | `Validated 10 local skill entrypoints and metadata files.` |
| `ruff format --check src tests scripts` | **FAIL** | 2 files need formatting (`src/bvmt/api.py` line 986, `tests/test_session_accounting.py` trailing newline) |
| `bvmt rules-check --config configs/competition.json` | **BLOCKED (exit 2)** | Expected fail-closed state while official rules remain unverified |
| `npm.cmd --prefix frontend run typecheck` | **PASS** | `tsc --noEmit` exit `0` |
| `npm.cmd --prefix frontend run build` | **PASS** | Compiled in `19.2s`; 12/12 static routes built (`/`..`/transactions`) |
| `bvmt.api` Python import | **Measured** | `2.242s` |
| `PortfolioStateService.load_state()` (cold) | **Measured** | `2.881s` per call (`bars=100`, `recs=76`) |
| FastAPI startup + cold `/api/health` | **Measured** | Port ready `3.114s`, cold `GET /api/health` `10.538s` (`status=200`, `6708` bytes), total `13.653s` |
| Next.js `next dev` startup + cold `/` HTML | **Measured** | Port ready `6.184s`, first `GET /` `29.453s` (`status=200`, `24655` bytes) |

### 1.3 Preserved Account & Research Data Baseline
- **Confirmed Competition Ledger**: `data/portfolio/real_competition_ledger.json` (`97,637` bytes, modified `2026-11-10 10:22:31`, SHA-256 `0A1B86CB281187A0E9AB88A4CDE6D4DE173A5DF162111266CE1988DCBF91D395`).
- **Captured DOM Snapshots**: `10` JSON files in `data/portfolio/snapshots/` (`sync_20261107_122006.json` through `sync_20261110_110702.json`).
- **Official Market Dataset**: `data/processed/bvmt_official_2026/` (`194` sessions, `2026-01-02` to `2026-11-06`, `source_sha256`: `c40fb10e372e27dfb6a36e04ab096293c39547c5a91c824368d01314b7a6b9f5`).
- **Research Artifacts**: `artifacts/strategy_experiments_2026.json`, `artifacts/strategy_experiments_2026_v1_archive.json`, `artifacts/instrument_diagnostics_report.json`, `artifacts/backtest_audit_2026.json`.

---

## 2. Worktree & Agent Assignment Architecture

To keep changes isolated and reviewable without overwriting existing work:
1. **`main` (`bvmt-starter-kit`)**: Owned by **Codex (Integrations & Acceptance)**. Preserves the 4 uncommitted hotfix files until reviewed and cleanly integrated.
2. **`gemini/dashboard` (`bvmt-gemini-dashboard`)**: Fast-forwarded to `10a33a6` via `git merge main` (no branch overwrite) and assigned to **Gemini (Backend & Quant Research)**:
   - Phase 1: Account Sync Reliability Audit & Backend/Extension Fixes + Transaction-History Reconciliation (`extension/`, `src/bvmt/sync_service.py`, `src/bvmt/manual_import.py`, `src/bvmt/browser.py`, `src/bvmt/playwright_worker.py`, `src/bvmt/ledger.py`, `docs/SYNC_RELIABILITY_AUDIT.md`, sync tests).
   - Phase 3: ICF Missed-Opportunity Autopsy (`docs/ICF_MISSED_OPPORTUNITY_AUTOPSY.md`, reproducible audit script/tests).
   - Phase 4 & 5: Multi-Layer Stock Research Scoring & Sparse-Data Experimental Model + Generalization Comparison (`src/bvmt/research_coverage.py`, new versioned sparse-data model module, `docs/SPARSE_DATA_RESEARCH.md`, `docs/STRATEGY_COMPARISON.md`, backend tests).
   - Phase 7: Forward Validation Snapshot & Signal Registry support (`src/bvmt/paper_trading.py` / experimental signal logger).
3. **`codex/data-research` (`bvmt-codex-research`)**: Fast-forwarded to `10a33a6` via `git merge main` and assigned to **Codex (Frontend Performance, API Caching & Decision Explainability)**:
   - Phase 2: Backend state/dataset caching + Frontend profiling & optimization (`src/bvmt/portfolio_service.py`, `src/bvmt/api.py`, `src/bvmt/holding_period.py`, `frontend/src/**`, `docs/PERFORMANCE_AUDIT.md`).
   - Phase 6: Decision Explanation UI & Accessible Tooltips (`frontend/src/app/market/page.tsx`, `frontend/src/app/planner/page.tsx`, `frontend/src/app/portfolio/page.tsx`, `frontend/src/components/**`).

*Coordination Rule*: Shared contracts (`src/bvmt/api.py`, `src/bvmt/ledger.py`, `frontend/src/lib/api.ts`) are coordinated by Codex on `main` after reviewing Gemini's diffs and regression tests.

---

## 3. Phased Execution Sequence & Priority Order

Per Milestone 13 priority (**Sync Reliability & Performance before new research models**):

1. **Wave 1 — Parallel Audits & Baseline Measurements (No Behavior Changes Yet)**
   - **Gemini (Phase 1 Audit)**: Trace full sync flow (`Chrome Extension -> DOM Extraction -> Localhost API -> Snapshot Validation -> Reconciliation -> User Confirmation -> Ledger Persistence`), inspect all 10 existing snapshots on disk, reproduce failures, produce `docs/SYNC_RELIABILITY_AUDIT.md`.
   - **Codex (Phase 2 Audit)**: Measure cold & warm timings across backend startup, `next dev`, `next start`, all API endpoints, all 9 routes (`/`, `/portfolio`, `/market`, `/planner`, `/strategy`, `/daily-summary`, `/health`, `/transactions`, `/research`), browser hydration, navigation, strategy latency, and memory use; establish `docs/PERFORMANCE_AUDIT.md` baseline section.
   - **Gemini (Phase 3 Audit)**: Reconstruct ICF (`TN0003200755`) timeline, rejected rows, original model exclusions, alternative price observations, disclosures/events, liquidity/fees; produce `docs/ICF_MISSED_OPPORTUNITY_AUTOPSY.md`.
2. **Wave 2 — Sync Reliability & Performance Engineering Fixes (Highest Priority)**
   - **Gemini (Phase 1 Fixes)**: Fix extension manifest/extraction/payload issues, French numeric parsing edge cases, 422 diagnostics, snapshot dedup, null-vs-zero preservation, transaction-history (`display_histo.aspx`) reconciliation, and independent tests for Browser Companion, Manual Import, and Playwright fallback.
   - **Codex (Phase 1 Review + Phase 2 Fixes)**: Review Gemini's sync diffs; implement content-hash dataset caching, state/experiment caching with explicit invalidation and freshness timestamps, lightweight summary endpoints / lazy detail loading, duplicate frontend request elimination, code splitting / memoization, and non-blocking sync UI. Measure after-optimization performance under equivalent conditions and complete `docs/PERFORMANCE_AUDIT.md`.
   - **User-Assisted Chrome Sync Gate**: Verify Browser Companion sync in an actual logged-in Chrome session (with explicit user participation) before advancing research models to production UI.
3. **Wave 3 — Sparse-Data Research Redesign, Generalization & Explainability**
   - **Gemini (Phases 4, 5, 7)**: Decouple 7 independent research layers (`FULL_RESEARCH_AVAILABLE`, `PARTIAL_RESEARCH_AVAILABLE`, `EVENT_RESEARCH_AVAILABLE`, `INSUFFICIENT_EVIDENCE`, `RESTRICTED_FOR_TRADING`), build versioned experimental sparse-data model (preserving Models A–I untouched), run bias-free out-of-sample generalization comparison across diverse stocks (rising/falling sparse, excluded challenge, liquid benchmarks, flat stocks), freeze experimental config and record prospective forward validation signals.
   - **Codex (Phase 6 & Integration)**: Review Gemini's research diffs; integrate multi-layer research explanations & uncertainty/missingness/tradability cards into Next.js UI without fabricating BUY signals; merge verified branches on `main`.
4. **Wave 4 — Final Acceptance & Documentation (Phase 8)**
   - Update `README.md`, `docs/STATE.md`, and verify all 6 required milestone documents + Mermaid diagrams.
   - Run full backend (`scripts/check.py`) and frontend (`typecheck`, `build`) gates, live Playwright UI screenshot verification, and confirm `real_competition_ledger.json` & snapshot preservation.
