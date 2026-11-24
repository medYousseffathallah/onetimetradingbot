# Why the Old Architecture Underperformed

**Scope**: Root-cause architectural, data-engineering, and quantitative-pipeline audit of `bvmt-starter-kit` (`src/bvmt/*`) explaining why V1 produced misleading rankings, broken accounting, fragile backtests, and poor live decision support.  
**Evidence Basis**: Direct code & artifact inspection in `bvmt-starter-kit` (`M14_AUDIT_REPORT` / `M14_SCORING_AUDIT.md`, `M14_CORRECTED_STRATEGY_RESULTS.md`, `STRATEGY_COMPARISON.md`) and empirical verification in `r1_portfolio_autopsy.py` & `r2_microstructure_audit.py`.

---

## 1. Executive Summary

The V1 architecture did not fail because of a single bad indicator; it failed because **data contamination, split instrument identities, scale-breaking scoring bugs, universe-filter mismatches, and non-monotonic account state sync compounded across layers**, turning research outputs into unreliable signals while leaving the human operator with poor position visibility and no structured exit engine.

---

## 2. Structural Failure Mechanisms in V1

### 2.1 Non-Equity Market Data Contamination (`496` Bond/Rights IDs)
- `data/processed/bvmt_official_2026/daily_bars.canonical.csv` ingested **`17,560` rows across `572` tokens**, mixing **`76` equities (`15,080` rows)** with **`496` non-equity corporate bonds, treasury instruments, and subscription rights (`2,480` rows)** across `2026-11-04..2026-11-10` (e.g., `AB0528_7.0_AP20`, `AB_DA1_*`).
- Because `2,427 / 2,480` (`97.86%`) of those non-equity rows had zero volume, they distorted universe denominators, cross-sectional means, and ingestion diagnostics whenever callers did not manually join against `instrument_master.csv`.

### 2.2 Split Canonical Identity (`POULINA` `TN0005700018`) & Symbol/ID Mismatch
- **Split ISIN**: Challenge security `TN0005700018` was split across `POULINA_GROUP_HOLDING` (`68` rows, `2026-01-02..2026-04-08`) and `POULINA_GP_HOLDING` (`134` rows through `2026-11-18`), both left with `valid_to = None` in `instrument_master.csv`. Prior to M14's in-memory `research_identity.py` patch, 60-session lookbacks severed cleanly across April–June.
- **Holding-Period Filter Bug**: `src/bvmt/holding_period.py` checked `m.instrument_id in get_challenge_symbol_set()`, matching short tickers (`AB`, `BH`, `DH`) against canonical IDs (`AMEN_BANK`, `BH_BANK`, `DELICE_HOLDING`). **27 of 42 Challenge stocks were silently dropped** (`15/42` matched), attributing `63.8%` of simulated 20s PnL to `BNA`.

### 2.3 Quantitative Scoring Instability (`1e-6` Vol Floor & Unbounded Concatenation)
- **7,457x Volatility-Floor Blowup**: `src/bvmt/features.py` and `src/bvmt/strategies.py` floored `vol_20` at `1e-6`. Any flat-then-spike equity (`mom_20 = 0`, `mom_60 = 0.25`) produced `composite_score = 125,000.0` vs normal `16.76` (a `7,457x` distortion).
- **Binary 60-Session Disqualification Cliff**: Requiring zero missing bars in a 60-session window meant a single exchange-regulated `'H'`/`'B'` limit-reserved session (`rejections.json`) disqualified liquid Challenge stocks (`ATB`, `BH_BANK`, `ICF`, `SOTUMAG`, `TJL`, `TUNIS_RE`) for ~3 months (`baseline` missed `ICF` before its Nov 9–11 breakout).
- **Incomparable Score Concatenation**: `research_coverage.py` wrote `composite * liq` (`[-13.03, +8.82]`) for eligible stocks and `obs_ret_pct * liq * 0.1` (`[-0.28, +0.27]`) for excluded stocks into the same `continuous_research_score` column.
- **Non-Challenge Slot Eviction**: `recommendations.py` and `sparse_research.py` allowed non-Challenge equities (`MONOPRIX`, `ESSOUKNA`, `CIL`) to occupy Top-8 slots and consume simulated cash ahead of Challenge-eligible stocks.

### 2.4 Point-in-Time (PIT) Violations & Missing Fundamentals
- **100% Blank `published_at`**: All `15,080` canonical equity rows have empty `published_at`. `features.py` crashed on raw files unless patched with hypothetical EOD timestamps, while `strategies.py` failed open when `published_at is None`.
- **Hardcoded Macro Cutoffs**: `multi_horizon.py` hardcoded `2026-11-06T23:59:59Z`, leaking 6 future static events into October backtests and dropping post-Nov 6 events on Nov 10.
- **Zero Fundamentals & Corporate Actions**: Zero PIT financial statements, dividend tables, or split adjustments existed locally; `6` hardcoded Python macro dicts in `macro_events.py` substituted for real CMF/BVMT disclosures.
- **Full-Day Volume Lookahead**: Legacy `strategies.py` capped entry fills against same-day full-session volume (`t+1` total volume known only at close), flattering execution feasibility on thin days.

### 2.5fragile Model G Performance & Overlapping-Horizon Illusion
- **Outlier & Phase Fragility**: Corrected Challenge **Model G** returned `18.5995%` (down from `19.4244%`), **but `SOTETEL` alone generated `+12,097.79 TND` (~63% of net profit)**; excluding `SOTETEL` reduced Challenge Model G to **`8.0331%`** and Full BVMT Model G to **`6.3468%`**. Across 20 start phases (`cadence=20`), Challenge Model G ranged from **`2.42%` to `17.39%`** (`7.29 pp` IQR).
- **Cash Idle Penalty**: Models D–I sat **~70–75% in cash** (`25.17%` utilization for Challenge Model G), under-deploying capital because rigid top-5 caps and filters left sleeves empty.
- **Sparse Research Limitations**: `sparse_research_v1` achieved `18.645%` vs `Baseline` `16.2927%` at `H=10` (with `60.58%` false-positive rate and `-5.11%` mean net return in `SPARSE_LATER_FELL`), and **underperformed** Baseline at `H=20` (`12.98%` vs `16.77%`).

### 2.6 Account Sync, DOM Parsing & Ledger State Failures
- **Unvalidated DOM Column Shift**: On Nov 9 (`12:01..12:04Z`), the extension scraped `VENDRE` into `symbol` and portal IDs (`223375..223516`) into `quantity`, injecting **`-122,910,515.520 TND`** fake unrealized loss into `real_competition_ledger.json`.
- **Out-of-Order Timestamp Overwrite**: `real_competition_ledger.json` accepted a stale Nov 10 snapshot (`browser_sync_20261110_110702`) *after* Nov 12 (`ext_1794476128406`), silently reverting active holdings from 8 to 6 and cash from `29,574.190` to `38,752.350` TND.
- **Incomplete Transaction Ledger**: `display_histo.aspx` was never captured after Nov 9 morning, leaving the Nov 9 intraday flip (`portal ID 223529`, `+71.820` TND) and post-Nov-12 trades (`+163.86` TND unexplained residual in `UNVERIFIED_USER_SCREENSHOT`) unattributed.

### 2.7 Missing Position Management & Exit Discipline
- V1 focused almost exclusively on *entry ranking* (`Top-8 BUY CANDIDATE`) and lacked a first-class position-monitoring engine with stop/target/trailing/thesis-invalidation exits, leading to **99% -> 59% cash drag** paired with **micro-sized orphan positions** (`BH_BANK` 0.77%, `NBL` 0.95%) and **unplanned intraday flips** (closing `223529` for `+1.56%` before a multi-session breakout).

---

## 3. Architectural Mandate for V2

V2 (`src/bvmt_v2/` + `apps/terminal-v2/`) eliminates these failure classes by construction:
1. **Equity-Only Canonical Boundary** (`ADR-001`): `76` tokens / `75` ISINs (`15,080` rows); `496` non-equity IDs blocked at the boundary.
2. **ISIN-First Identity**: Join `POULINA` and all aliases via `verified_isin` with effective-date checks.
3. **Strict 5-State Provenance (`OBSERVED`, `CALCULATED`, `SIMULATED`, `UNVERIFIED`, `UNAVAILABLE`)** (`ADR-002`, `ADR-003`): Never backfill `published_at`, `TUNINDEX`, or live quotes.
4. **Monotonic Snapshot & Ledger Guard**: Reject stale-timestamp overwrites and schema-invalid DOM shifts (`qty > 100k` / `symbol == 'VENDRE'`) fail-closed.
5. **10-Layer Stock Assessment & Dedicated Position Exit Management**: Separate `HELD_POSITION_REVIEW` from new `RESEARCH_CANDIDATE` discovery, enforce Challenge-42 eligibility before ranking, and require purged walk-forward + `SOTETEL`-excluded stress tests before promoting any model.
