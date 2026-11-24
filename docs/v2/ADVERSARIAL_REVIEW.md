# Independent Adversarial Review (Agent E) & Remediation Status — BVMT V2

**Reviewer**: Antigravity Read-Only Subagent `v2_adversarial_reviewer` (`conversationId: de28e802-71c6-4f46-9aa9-d6d2b59c6663`)  
**Review Scope**: Read-only audit of `src/bvmt_v2/`, `tests_v2/`, `research/experiments-v2/`, `artifacts/v2/v2-benchmark-results.json`, `apps/terminal-v2/src/`, and protected `bvmt-starter-kit/data/portfolio/` & `configs/`.  
**Integrity Verification**: Confirmed zero write routes mutate `real_competition_ledger.json` or `configs/competition.json`, zero external broker/LLM calls, and stateless dry-run scenario endpoints (`is_executed=False`).

---

## Findings Recorded Verbatim from `de28e802-71c6-4f46-9aa9-d6d2b59c6663`

### P0 — Critical Blockers

1. **Strict-PIT Zero-Sample Collapse vs. Exploratory Lookahead Overrides & API/UI Mislabeling**
   - **Locations**: `src/bvmt_v2/market_data.py:18, 132-145`; `src/bvmt_v2/backtester.py:296-325, 333-341, 395-400, 656`; `src/bvmt_v2/api.py:274-304`; `artifacts/v2/v2-benchmark-results.json:34-5850`; `apps/terminal-v2/src/app/research-lab/page.tsx:402`.
   - **Evidence**: All 15,080 rows lack `published_at` (`published_at_present_count = 0`). Strict-PIT `Backtester.from_market` yields `sample_count: 0` / `0%` return, whereas `GET /api/v2/research-lab` ran strict-PIT while labeling `"classification": "RETROSPECTIVE_EXPLORATORY"`, `backtester.py:656` hardcoded `"RETROSPECTIVE_EXPLORATORY"` on strict-PIT runs, and `research-lab/page.tsx:402` repeated `"All experiments are retrospective exploratory runs"` unconditionally.
   - **Remediation Plan**: Explicitly track `run_mode` (`"STRICT_PIT"` vs `"RETROSPECTIVE_EXPLORATORY"` vs `"SYNTHETIC_DEMO"`) in `Backtester`, `ModelExperiment`, `/api/v2/research-lab`, and `research-lab/page.tsx`; expose `"classification": "STRICT_PIT"` when strict-PIT is running.

2. **`Bar.fill_price` Slippage Bug Drops Losing Trades & Inverts Cost-Sensitivity**
   - **Locations**: `src/bvmt_v2/backtester.py:82-92, 434-445, 585-588`; `src/bvmt_v2/api.py:282`; `artifacts/v2/v2-benchmark-results.json:4604-4813, 8234-8575`.
   - **Evidence**: `fill_price` checked `price > self.high` / `price < self.low` AFTER adding adverse `bps` slippage (`open * (1 + bps/10000)`), causing `50 bps` slippage to reject valid market fills on `open == high` days and artificially lift `V2-D-MOM-RISK` H=10 (`6.59% -> 16.44%`) and `V2-F-LIQ-TREND` H=10 (`14.18% -> 18.49%`). Meanwhile switching `settlement=0` -> `settlement=3` collapsed `V2-F-LIQ-TREND` to `1.93%`.
   - **Remediation Plan**: Check bar validity against unadjusted `self.open` / `[low, high]`, apply adverse slippage cleanly without dropping valid opens when `bps > 0` crosses the daily high/low boundary, and add `test_higher_slippage_never_improves_return_by_dropping_fills` in `tests_v2/test_backtester.py`.

3. **Negative Benchmark Alpha, Single-Stock (`SOTETEL`) Fragility, Phase Selection Bias, & Reused Dataset**
   - **Locations**: `src/bvmt_v2/backtester.py:428-431, 594-615, 671`; `artifacts/v2/v2-benchmark-results.json`.
   - **Evidence**: Active Challenge rules underperform `BL-EW-CHAL` (`+22.08%`) at `H=5, 10`; removing `SOTETEL` collapses momentum rules to `-0.13%..+1.80%`; `offset=0` sits above phase medians (`V2-D` H=20 median `6.75%`, IQR `9.47 pp`; `V2-F` H=20 `23.00%` vs `19.14%` median, IQR `9.32 pp`); `signal_journal` is empty `()`.
   - **Status**: Confirmed and permanently elevated as a **Scientific Gate** (`NO STRATEGY PROMOTED` — `V2-EXP1` & `STRATEGY_RESEARCH.md` explicitly refuse promotion until `top1_excluded > 0`, `alpha_vs_ew > 0`, and >=20 prospective frozen `SignalJournal` picks pass).

4. **Unreconciled Account Truth & Partial 1-Holding Screenshot Object**
   - **Locations**: `bvmt-starter-kit/data/portfolio/real_competition_ledger.json`; `research/experiments-v2/r1_autopsy_results.json`; `src/bvmt_v2/portfolio_engine.py:492-504, 628-680`.
   - **Evidence**: `+235.68 TND` unexplained screenshot gap (`71.82` Nov 9 + `163.86` residual); `portfolio_engine.py:655-666` populated `unverified_user_screenshot_2026_11.holdings` with only 1 holding (`AMEN_BANK`) when `reported_holdings_count=9`.
   - **Remediation Plan**: Keep `ACCOUNT_STATE_CONFLICT` active and explicitly note partial-screenshot missing 8 holdings in `attribution` / snapshot metadata (`unverified_screenshot` flagged as incomplete summary).

### P1 — Significant Defects

1. **Dead Non-Equity Filter & `0` Upstream Excluded Count**: `market_data.py` checked missing `asset_type` column while `496` non-equities (`2,480` rows) were excluded upstream in `data/v2_market/v2_market_manifest.json`. *Remediation*: Read `upstream_excluded_non_equity_count` (`496` instruments / `2,480` rows) in `MarketData` / `/api/v2/health` and show both upstream excluded and runtime rejected counts cleanly in `apps/terminal-v2`.
2. **CSV `is_competition_eligible` Conflict (63 vs 42)**: Hardcoded 42-stock `REGISTRY` governs Challenge eligibility while `instrument_master.csv` carries an older `63`-flag column (`M14` documented defect) and `POULINA` has 2 rows stitched in Python (`market_data.py:233-261`). *Remediation*: Keep `REGISTRY` authoritative until official portal re-verification and disclose CSV mismatch explicitly in `/health`.
3. **Backtester Cap Exceedance & Skipped `SELL` on Feature Gap**: `Book.execute` ignored `FEE`/`bps` on held shares; rebalance loop skipped `SELL` on `if feature is None: continue`. *Remediation*: Include `FEE` headroom in `Book.execute` 10% cap check and allow `SELL` liquidation of held positions even when trailing 60-bar feature window has a gap.
4. **UTC vs `Africa/Tunis` Date Drift**: `portfolio_engine.py:165, 289, 738` used `at.date()` / `timedelta(hours=1)` instead of `ZoneInfo("Africa/Tunis")`. *Remediation*: Unify onto `ZoneInfo("Africa/Tunis")`.
5. **UI Provenance Mismatch (`stocks/[instrumentId]/page.tsx:394` & `page.tsx:127`)**: Hardcoded `"OBSERVED"` badge on Stock Audit even for `SYNTHETIC_FIXTURE` / `EOD_UNVERIFIED_PUB_TIME`, and hardcoded `"UNVERIFIED"` override on reconciled DOM capture on `/`. *Remediation*: Derive Stock Audit badge status dynamically from `data_quality_status` (`OBSERVED` / `CALCULATED` / `SIMULATED` / `UNVERIFIED`) and render `latestCapture.verification_status` consistently on `/`.
6. **UI Restricted BUY Submission & Hardcoded Exit Tickers in `SYNTHETIC_DEMO`**: `decisions/page.tsx` allowed clicking BUY on `Restricted` stocks; `research-lab/page.tsx:18` hardcoded `MPBS`/`STA` (absent in `SYNTHETIC_DEMO`). *Remediation*: Disable BUY dry-run button with explicit `RESTRICTED_CHALLENGE` pre-check on non-Challenge stocks in `decisions/page.tsx`, and filter `EXIT_CANDIDATES` in `research-lab/page.tsx` by mode-available holdings/instruments.

### P2 — Advisory Findings
- Frontend JS float arithmetic vs `BigInt`/backend `Decimal` (`format.ts`), per-position vs portfolio realized P&L attribution (`portfolio_engine.py`), fail-closed `configs/competition.json` check (`api.py`), strict `1..65535` port validation & loopback proxy target check (`api.py` / `next.config.ts`), and explicit one-way `turnover_pct` label (`backtester.py`).

---

## Post-Review Remediation Status (Verified)

| Finding | Severity | Status | Fix & Verification Proof |
|---|---|---|---|
| **P0-1: Strict-PIT vs Exploratory labeling & `simulation_mode`** | P0 | **FIXED** | Added `run_mode` (`STRICT_PIT` / `RETROSPECTIVE_EXPLORATORY` / `SYNTHETIC_DEMO`) to `ModelExperiment` & `Backtester`, defaulted `/api/v2/research-lab` to `STRICT_PIT` with explicit `simulation_mode` toggle in `apps/terminal-v2/src/app/research-lab/page.tsx`. Verified in `test_loopback_boundary_and_mode_consistency`. |
| **P0-2: `Bar.fill_price` slippage drops valid `open == high` fills** | P0 | **FIXED** | Validated `open` inside `[low, high]` prior to applying `bps` slippage (`src/bvmt_v2/backtester.py`). Verified by `test_higher_slippage_never_improves_return_by_dropping_fills` and `run_v2_benchmark_suite.py` (`V2-D`: `+6.30% -> +2.85%`, `V2-F`: `+13.50% -> +7.98%` under `50 bps`). |
| **P0-3: Active models fail `BL-EW-CHAL`, `SOTETEL` dependence & zero journal** | P0 | **OPEN_RISK_GATE** | Permanently enforced as an explicit scientific gate (`NO STRATEGY PROMOTED`); benchmark re-verified and disclosed in UI/docs until `alpha_vs_ew > 0`, `top1_excluded > 0`, and prospective `SignalJournal` sample size are met. |
| **P0-4: Unreconciled account state & partial 1-holding screenshot** | P0 | **FIXED (Gate Kept Open)** | Added dynamic `PARTIAL_SCREENSHOT_OMITS_8_HOLDINGS` failure tag in `src/bvmt_v2/portfolio_engine.py` (`test_loopback_boundary_and_mode_consistency`); `account_state_conflict` stays visibly flagged on `/`, `/portfolio`, `/attribution`, `/health` until a full DOM sync & trade ledger are supplied. |
| **P1-1: Upstream excluded non-equity count hidden (`0` shown)** | P1 | **FIXED** | Loaded `upstream_excluded_non_equity_count` (`2,480` rows / `496` non-equity instruments) from `data/v2_market/v2_market_manifest.json` (`src/bvmt_v2/market_data.py`), exposed on `/api/v2/health` & `/overview`, and rendered cleanly in `page.tsx` & `health/page.tsx`. |
| **P1-2: CSV `is_competition_eligible` `63 vs 42` conflict** | P1 | **OPEN_RISK_GATE** | `REGISTRY` (42 stocks) remains authoritative while `72` rule blockers in `configs/competition.json` stay unverified (`EXECUTION_BLOCKED`). |
| **P1-3: `10%` cap headroom fee calculation & skipped `SELL` on feature gap** | P1 | **FIXED** | Included `(1 + FEE)` headroom in `Book.execute` and decoupled `SELL` liquidation from missing trailing-60 features (`src/bvmt_v2/backtester.py`); verified in `test_cap_headroom_and_missing_feature_sell_liquidation`. |
| **P1-4: UTC vs `Africa/Tunis` session date boundary drift** | P1 | **FIXED** | Unified `_tunis_date` using `ZoneInfo("Africa/Tunis")` across marking, pricing, and `freeze_signal` (`src/bvmt_v2/portfolio_engine.py`). |
| **P1-5: Hardcoded `OBSERVED` / `UNVERIFIED` provenance badges in UI** | P1 | **FIXED** | Mapped L9 Stock Audit badge from `data_quality_status` (`stocks/[instrumentId]/page.tsx`) and used `latestCapture?.verification_status` (`page.tsx`). |
| **P1-6: Non-Challenge BUY clickable + demo-missing tickers in Research Lab** | P1 | **FIXED** | Disabled dry-run BUY button with explicit `RESTRICTED_CHALLENGE` pre-trade banner (`decisions/page.tsx`, Playwright verified on `MONOPRIX`), and filtered exit candidates by active mode (`research-lab/page.tsx`). |
| **P2: Fail-closed rules config & TCP port validation (`1..65535`)** | P2 | **FIXED** | Raised HTTP `503` if `configs/competition.json` missing in `REAL_COMPETITION`, validated port `1..65535` on Host/Origin (`src/bvmt_v2/api.py`). Remaining UI formatting/one-way turnover items tracked for post-V2 hardening. |
