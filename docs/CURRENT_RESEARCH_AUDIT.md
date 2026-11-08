# BVMT Trading Intelligence — Phase 0 Research Engine Audit

**Audit Date:** `2026-11-08`
**Audited Commit:** `392daf6` (`main`, `gemini/dashboard`, `codex/data-research`)
**Scope:** Full source-code inspection of `src/bvmt/features.py`, `src/bvmt/execution.py`, `src/bvmt/recommendations.py`, `src/bvmt/data.py`, `src/bvmt/calendar.py`, `src/bvmt/ledger.py`, `src/bvmt/llm.py`, `src/bvmt/api.py`, `configs/competition.json`, `configs/research.json`, and `artifacts/backtest_audit_2026.json`.

---

## 1. Existing Strategies and Mathematical Formulas

Only **two** ranking functions are currently implemented in production code (`src/bvmt/features.py`):

### 1.1 Demo Momentum (`rank_demo_momentum`, v0.1 — Synthetic Only)
- **Location:** `src/bvmt/features.py` (lines 68–114)
- **Restriction:** Explicitly raises `ValueError` if any bar has `source_id != "synthetic-fixture"`.
- **Formula:**
  $$R_i(L) = \frac{P_{i, t}}{P_{i, t-L}} - 1$$
  where $L$ is the number of observed bars (`lookback = 3` by default), requiring all bars in the window to have `status == "traded"` and age $\le 7$ calendar days.

### 1.2 T04 Session-Aware Volatility-Adjusted Dual-Horizon Momentum (`rank_session_baseline`, v1.0)
- **Location:** `src/bvmt/features.py` (lines 117–398)
- **Inputs:**
  - `instruments`: Dated `InstrumentRecord` master (`listed_from`, `listed_to`, `market_segment`, `is_competition_eligible`)
  - `calendar`: Verified open `ExchangeSession` sequence (`closes_at <= cutoff`)
  - `bars`: Point-in-time `DailyBar` observations (`published_at <= cutoff` and `ingested_at <= cutoff`)
  - `short_lookback` ($S = 20$ open sessions default) and `long_lookback` ($L = 60$ open sessions default)
- **Mathematical Definitions:**
  1. **Short-Horizon Session Momentum ($M_{i, S}$):**
     $$M_{i, S} = \frac{C_{i, t}}{C_{i, t-S}} - 1$$
  2. **Long-Horizon Session Momentum ($M_{i, L}$):**
     $$M_{i, L} = \frac{C_{i, t}}{C_{i, t-L}} - 1$$
  3. **Realized Traded-Step Volatility ($\sigma_{i, S}$):**
     Computed strictly across consecutive `traded` closes $\{C_{i, \tau_0}, C_{i, \tau_1}, \dots, C_{i, \tau_k}\}$ inside the $S$-session window (never across untraded zero-volume gaps):
     $$r_{i, j} = \frac{C_{i, \tau_j}}{C_{i, \tau_{j-1}}} - 1, \quad \bar{r}_i = \frac{1}{k}\sum_{j=1}^{k} r_{i, j}, \quad \sigma_{i, S} = \max\left(10^{-6}, \sqrt{\frac{1}{\max(1, k-1)}\sum_{j=1}^{k}(r_{i, j} - \bar{r}_i)^2}\right)$$
  4. **Universe Benchmark Return ($B_S$) & Relative Strength ($RS_{i, S}$):**
     $$B_S = \frac{1}{N_{\text{eligible}}} \sum_{j=1}^{N_{\text{eligible}}} M_{j, S}, \quad RS_{i, S} = M_{i, S} - B_S$$
  5. **Composite Ranking Score ($Z_i$):**
     $$Z_i = 0.5 \cdot \left(\frac{M_{i, S}}{\sigma_{i, S}}\right) + 0.5 \cdot \left(\frac{M_{i, L}}{\sigma_{i, S}}\right)$$

---

## 2. Ranking and Eligibility Logic

`rank_session_baseline` (`src/bvmt/features.py`) applies a deterministic 7-gate point-in-time eligibility filter before scoring any stock. Every rejected stock is recorded in `SessionBaselineReport.exclusions` (`ExcludedInstrument`) with an explicit machine-readable reason:

| Gate # | Exclusion Code | Condition Enforced |
| :--- | :--- | :--- |
| **1** | `unlisted_or_delisted` | `latest_date < listed_from` or `latest_date > listed_to` |
| **2** | `ineligible_market_segment` | `not is_competition_eligible` or `market_segment` not in `("Continu_Principal", "principal", "principal_continu", "principal_fixing")` |
| **3** | `insufficient_session_history` | Total completed open sessions on or before `cutoff` $< L + 1$ ($61$ sessions) |
| **4** | `suspended` | Official suspension on `latest_date` or any bar with `status == "suspended"` in the $S$-session window |
| **5** | `missing_observation` | Any open exchange session in the $L+1$ window lacks a point-in-time bar (`(inst_id, session_date) not in pit_bars`) |
| **6** | `stale_quote` / `untraded_lookback_anchor` | $\ge 3$ consecutive `no_trade`/`untraded` sessions at cutoff, or `status != "traded"` on the anchor bars $t$, $t-S$, or $t-L$ |
| **7** | `insufficient_liquidity` | $S$-session trade frequency $< f_{\min}$ (`0.75` default; `0.60` in dashboard/backtest) or $S$-session median daily turnover $< \text{Turnover}_{\min}$ (`5,000 TND` in dashboard) |

---

## 3. Data Availability and Provenance

Inspection of `data/processed/bvmt_official_2026/`, `data/staging/market_resume_full.ndjson`, and `artifacts/backtest_audit_2026.json` establishes the exact verified data state:

- **Primary Official Source:** Bourse de Tunis (`https://www.tunis-stockexchange.com/sites/default/files/historique/data_json/market_resume.ndjson`, `222,319,563` bytes, SHA-256 `486761f55253480a0e19e9b7e8300512522316f93f67081c6fa010d86df45c55`, `Last-Modified: Fri, 06 Nov 2026 14:45:02 GMT`).
- **2026 Daily Coverage:**
  - **194 unique daily trading sessions** (`2026-01-02` through `2026-11-06`) after deduplicating 15 identical session envelopes.
  - **14,480 accepted canonical equity bars** across **76 equity instruments** (`64` in principal quotation groups `11`/`12`, `12` in fixing/surveillance groups `52`/`99`; `70` malformed/zero-price rows quarantined in `rejected_rows.csv`).
- **2020–2025 Historical Coverage Audit:**
  - `2025` in `market_resume.ndjson` contains only **12 monthly summary envelopes** (`2025-01-31` to `2025-12-31`), where `6,303` of `6,881` rows have `quantites: null` (unusable for daily OHLCV simulation).
  - `2020–2024` have **0 lines** in `market_resume.ndjson`, and legacy `bvmt.com.tn` historical ZIP endpoints return `0` bytes.

---

## 4. Current Backtesting Methodology

Implemented in `src/bvmt/execution.py`:
- **Engine:** `run_historical_backtest(bars, signals, config=..., calendar=..., eligible_instruments=...)`
- **Chronological Walk-Forward:** `run_walk_forward_evaluation(bars, signal_builder, config=..., train_window_sessions=61, test_window_sessions=19, step_sessions=19)`
- **Parameter Sensitivity Grid:** `run_sensitivity_analysis(bars, signals, commission_bps_grid=(30, 50, 70), volume_participation_grid=(0.05, 0.10, 0.20), slippage_bps_grid=(5, 10, 20))` (27 scenarios per window).
- **Order Timing:** Signals emitted at session $t$ (`signal_session`) are strictly blocked from filling on session $\le t$ (`session <= order.signal_session`). Orders execute at $t+1$ (or up to `max_order_age_sessions = 3` open sessions if partially filled or untraded) at `next_open` plus directional slippage.

---

## 5. Execution and Transaction-Cost Assumptions

- **Competition Fee Model (`configs/competition.json` & `BacktestConfig`):**
  - Buy commission: **`0.50%` (`50 bps`)** of executed purchase value.
  - Sell commission: **`0.50%` (`50 bps`)** of executed sale value.
  - Round-trip fee hurdle: **`~1.00%` (`100 bps`)** before slippage.
  - Terminal liquidation accounting: `BacktestResult` reports both `total_return_pct` (marked-to-close) and `liquidated_total_return_pct` (deducting the `0.50%` exit fee on all ending holdings via `unrealized_liquidation_fee_tnd`).
- **Liquidity & Participation Caps:**
  - Zero-volume bars (`volume_shares == 0` or `status != "traded"`) block all fills (`zero_volume_blocked_fill_attempts` counter).
  - Shared daily volume participation cap: `max_volume_participation = 0.10` (`10%` of daily bar `volume_shares`), decremented across all orders in the same stock/session.
  - Optional turnover participation cap: `max_turnover_participation`.
  - Price bound check: Assumed slipped fill price must lie inside `[bar.low, bar.high]`.

---

## 6. Portfolio Sizing and Risk Rules

Implemented in `src/bvmt/recommendations.py` (`generate_recommendations`) and `src/bvmt/execution.py`:
- **Competition Concentration Limit:** Hard cap of **`10.0%` (`0.10`)** of total portfolio equity per stock (`max_concentration_ratio = Decimal("0.10")` in `PortfolioLedger`, `max_position_weight = Decimal("0.10")` in `BacktestConfig`).
- **Recommendation Safety Buffer (`src/bvmt/recommendations.py`):**
  - Target buy allocation: **`8.5%` (`TARGET_BUY_WEIGHT_RATIO = 0.085`)** of total equity, leaving a `1.5%` buffer below the `10.0%` cap.
  - Trim/Reduce trigger: **`9.5%` (`REDUCE_TRIGGER_WEIGHT_RATIO = 0.095`)** of total equity triggers a `REDUCE` recommendation back to `8.5%`.
  - Liquidity cap on proposed orders: **`10%` of 20-session median daily turnover** (`MAX_TURNOVER_PARTICIPATION_RATIO = 0.10`).
  - Fee hurdle on entry: Requires $M_{i, 20} \ge +1.50\%$ (`FEE_HURDLE_MOMENTUM_20S = 0.015`), $M_{i, 60} > 0$, and $RS_{i, 20} \ge 0$.

---

## 7. Existing Financial Disclosure and LLM Integration

Implemented in `src/bvmt/llm.py` and `src/bvmt/recommendations.py`:
- **Offline-First Document Indexing & Search:** `chunk_financial_document`, `load_document_index`, and deterministic BM25-style lexical + vector sidecar retrieval (`search_document_index`) with strict point-in-time filtering (`published_at <= cutoff` and `ingested_at <= cutoff`).
- **Verbatim Quote Verification (`VerifiedEventSignal`):** Corporate events (`positive`, `neutral`, `adverse_risk`) must carry `quote_verified=True` and a `source_document_id` before influencing recommendations. Adverse events block `BUY CANDIDATE` and trigger `SELL CANDIDATE` on held positions.
- **Alibaba Cloud Model Studio Budget Guard:** `load_llm_budget_config` enforces `network_enabled: false`, `BVMT_ALLOW_LIVE_LLM=0`, and `console_free_quota_only_verified: true` by default.

---

## 8. Potential Lookahead and Survivorship Biases

1. **Point-in-Time Publication Timestamps in `market_resume.ndjson`:**
   - Official daily NDJSON records do not embed intraday publication timestamps (`published_at` is `None` in raw rows). During historical replay (`dashboard.py` / `execution_audit`), session close is mapped to `16:00 Africa/Tunis` on `session_date` and fills occur strictly on session $t+1$ open (`09:00 Africa/Tunis`), preventing same-close lookahead.
2. **Static Instrument Master in 2026 Archive:**
   - The `instrument_master.csv` derived from the 2026 archive reflects the 76 equities present in 2026 (`listed_from = 2026-01-02`). It does not yet contain pre-2026 delistings or historical corporate-action split/dividend adjustment ratios.
3. **Static Equal-Weight Benchmark Construction (`run_historical_backtest`):**
   - As documented in the docstring of `run_historical_backtest` (line 276), the built-in equal-weight benchmark allocates equal initial cash sleeves on `sessions[0]` across the static universe and retains cash for instruments untraded on day 1. It is a static initial-day benchmark rather than a dynamically rebalanced point-in-time eligible universe benchmark.

---

## 9. Current Strategy Results and Limitations

From `artifacts/backtest_audit_2026.json` (`194` sessions, `2026-01-02` to `2026-11-06`, initial cash `50,000.000 TND`, `50 bps` buy/sell fees, `10 bps` slippage, `10%` max position weight, `10%` volume participation cap):

| Evaluation Window | Marked Return (%) | Liquidated Return (%) | Equal-Weight Benchmark (%) | Max Drawdown (%) | Fills / Folds | Statistically Conclusive? |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Full 2026 Archive (`194` sessions)** | `+46.6321%` | `+46.0615%` | `+19.9445%` | `10.7827%` | `14` fills (`8` orders) | **No (`194 < 250` sessions)** |
| **Oct 1 – Nov 6 Competition Window (`26` sessions)** | `+0.5061%` | `+0.2765%` | `+0.2498%` | `0.2159%` | `7` fills | **No (`26` sessions)** |
| **7-Fold Rolling Walk-Forward (`train=61, test=19, step=19`)** | `+3.8215%` (mean) | `+3.4428%` (mean) | `+1.9564%` (mean) | — | `6 / 7` positive folds (`85.71%`) | **No (single-year sample)** |

---

## 10. Implemented vs. Missing / Planned Research Components

| Component / Strategy | Current Status | Code Location / Gap |
| :--- | :--- | :--- |
| **Demo Momentum (`rank_demo_momentum`)** | **Implemented (Synthetic Only)** | `src/bvmt/features.py` |
| **T04 Dual-Horizon Vol-Adjusted Momentum (`rank_session_baseline`)** | **Implemented (Active Baseline)** | `src/bvmt/features.py` |
| **5-State Recommendation Engine (`generate_recommendations`)** | **Implemented (Active)** | `src/bvmt/recommendations.py` |
| **T+1 Historical Backtester & Walk-Forward (`run_historical_backtest`)** | **Implemented** | `src/bvmt/execution.py` |
| **Baseline A: Cash-Only Baseline Strategy** | **Benchmark metric only (`0.00%`)** | Needs standalone strategy runner in comparative harness |
| **Baseline B: Equal-Weight Eligible Universe Strategy** | **Static day-1 sleeve only** | Needs point-in-time eligible universe rebalancing baseline |
| **Baseline C: Buy-and-Hold Benchmark** | **Partial (day-1 static sleeve)** | Needs explicit standalone baseline runner |
| **Baseline D: Simple 20-Session Momentum (`MOM_20`)** | **Missing as standalone strategy** | Currently only an intermediate feature in `rank_session_baseline` |
| **Baseline E: Simple 60-Session Momentum (`MOM_60`)** | **Missing as standalone strategy** | Currently only an intermediate feature in `rank_session_baseline` |
| **Baseline F: Relative-Strength Ranking (`RS_20`)** | **Missing as standalone strategy** | Currently only an intermediate feature in `rank_session_baseline` |
| **Baseline G: Liquidity-Filtered Momentum (`LIQ_MOM`)** | **Partially coupled** | Needs isolated comparative evaluation against unfiltered D/E/F |
| **Multi-Factor Enhancement (Downside Vol / Drawdown / Trend Consistency / Regime Filter)** | **Missing (Planned Phase 4)** | Not yet implemented in `src/bvmt/` |
| **Extended Metrics (Hit Rate, P&L Distribution, Cash Utilization, Concentration)** | **Missing (Planned Phase 5)** | `BacktestResult` currently lacks hit rate, win/loss distribution, and average cash utilization |
| **Machine Learning Ranking (`LightGBM` / `scikit-learn`)** | **Not Implemented (Blocked by Sample Size)** | Packages installed in `.venv`, but 194 single-year sessions are insufficient for leak-free ML promotion |

