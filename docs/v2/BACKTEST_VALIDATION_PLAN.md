# BVMT V2 Backtest & Scientific Validation Plan

**Scope**: Reproducible validation protocol for `src/bvmt_v2/backtester.py` and `research/experiments-v2/`.  
**Status**: Mandatory pre-implementation specification for Gate 1 (`V2-BE1` & `V2-EXP1`).

---

## 1. Chronological Purged & Embargoed Walk-Forward Protocol

Because financial time series exhibit serial autocorrelation in overlapping forward returns and trailing `20s`/`60s` momentum windows, naive K-fold or unpurged rolling tests leak future information.

### 1.1 Fold Geometry (`202` Sessions: `2026-01-02..2026-11-18`)
- **Warmup Window (`W`)**: Minimum `61` open exchange sessions (`2026-01-02..2026-03-27`) before the first decision date (`2026-03-30`) so `60s` return/volatility/turnover windows are fully populated without lookahead.
- **Horizon (`H`) & Purge Gap**: For any forward holding horizon `H in {5, 10, 20}` sessions:
  - Decision cutoff at `t` close (`Africa/Tunis`), entry at `t+1` open, exit at `t+H` close (or `t+H+1` open).
  - **Purge**: Any training/calibration observation whose label window `[t_i + 1, t_i + H]` overlaps `[t_test - 1, t_test + H]` is strictly excluded from model fitting prior to `t_test`.
  - **Embargo (`E = 2` sessions)**: When multi-year data (`2022–2025`, `P0-1`) enables supervised fitting (e.g., LightGBM), an additional `2`-session embargo buffer follows every validation fold before training resumes.
- **Non-Overlapping Portfolio Folds (`2026-03-30..2026-11-18`, `141` post-warmup sessions)**:
  - `H = 10`s (`step = 10`): **14** purged non-overlapping folds (`2026-03-30` through `2026-11-04` exit).
  - `H = 20`s (`step = 20`): **7** purged non-overlapping folds.
  - **All-Phase Sensitivity Sweep**: For any periodic rebalance cadence `k in {5, 10, 19, 20}`, simulations MUST run across **all `k` start phases** (`offset = 0 .. k-1`) and report `(min, p25, median, p75, max, IQR pp)` rather than a cherry-picked phase (eliminating V1's `7.29 pp` hidden phase luck).

---

## 2. Execution, Cash, Fee & Liquidity Constraints

All `bvmt_v2.backtester` runs enforce **identical** execution realism across strategies and baselines:
1. **Monetary Precision (`ADR-002`)**: All cash, prices, fees, and valuations use `Decimal` (`0.001` TND `ROUND_HALF_UP`).
2. **Strict No-Same-Close Execution**: Signals computed from session `t` close execute no earlier than session `t+1` open (`next_open` mode). Zero fills at `t` close.
3. **Zero-Volume & Invalid-Price Guard**: Zero fills on `status == "untraded"`, `volume_shares <= 0`, or non-positive prices (`open <= 0` / `close <= 0`).
4. **Transaction Fees**: `0.50%` (`0.005`) on buy gross value and `0.50%` (`0.005`) on sell gross value (`100 bps` round-trip). Terminal open positions are valued both **Mark-to-Market** and **Liquidated Net of 0.50% Sell Fee**.
5. **10% Single-Stock Cap**: Purchase orders check `(existing_position_mv + order_gross) <= 0.10 * total_portfolio_equity` and auto-reduce integer shares to comply (matching Challenge FAQ). Subsequent price drift is monitored, never hidden.
6. **Leakage-Free Participation Cap (`10%` Trailing ADV)**: Unlike legacy `strategies.py` (which peeked at `t+1` full-day volume), V2 enforces a dual liquidity guard:
   - *Ex-ante sizing cap*: Target order shares cannot exceed `floor(0.10 * trailing_20s_median_volume_shares)` per planned execution session (known strictly at `t` close).
   - *Ex-post fill realism*: Actual `t+1` fill cannot exceed `floor(0.10 * bar_{t+1}.volume_shares)` — if `bar_{t+1}` trades `0` shares, fill = `0`.
7. **Settlement Sensitivity**: Primary research mode uses `T+0` immediate sale cash reuse; competition-conservative sensitivity re-runs with `T+3` settlement lock until `configs/competition.json` clears blocker `settlement_and_cash`.

---

## 3. Anti-Overfitting Policy & Sample Hygiene

1. **Oct–Nov 2026 Retrospective-Only Rule**: Because the 2026 dataset (`2026-01-02..2026-11-18`) has been inspected during R1–R3 and M14/M15, **zero subset of 2026 (including Oct–Nov 2026) may ever be claimed as an "untouched out-of-sample holdout."** All 2026 studies are explicitly labeled `RETROSPECTIVE_EXPLORATORY`.
2. **Zero Holdout Reuse**: Once `2022–2025` historical data (`P0-1`) or post-`2026-11-18` prospective sessions arrive, a single chronological final test block (`>= 60` sessions) is locked *once* per hypothesis family; any parameter tweak invalidates the holdout and requires fresh prospective accumulation.
3. **Disclosed Trial Counts & Multiple-Testing Discipline**: Every experiment JSON artifact logs `trial_count`, `config_hash`, `data_hash`, and `source_hash` (matching M14's immutable hash-addressed pattern). Grid searches over >5 parameter combinations without Bonferroni/Deflated-Sharpe adjustment are prohibited.
4. **Single-Outlier Exclusion Stress Test**: Every strategy report MUST publish **`top1_excluded_return_pct`** (re-running the full simulation with the #1 contributing equity removed from the universe, e.g., ex-`SOTETEL`). Any strategy whose net excess return over Equal-Weight Challenge collapses below `0%` after removing 1 stock fails robustness.
5. **Prospective `SignalJournal` Promotion Gate**: Before any strategy can move from `RESEARCH_ONLY` to `HUMAN_REVIEW_ELIGIBLE`, it must log **>= 20** frozen, pre-session `SignalJournal` records across **>= 20** distinct sessions (with `>= 15` settled non-single-name picks), achieving post-cost positive alpha vs Cash & Challenge EW, `false_positive_rate <= 0.45`, and `max_drawdown <= 15.0%`.

---

## 4. Exact Baseline Suite & Evaluation Metrics

Every V2 experiment compares all tested hypotheses side-by-side against **5 mandatory baselines** on identical universe boundaries (`TUNIS_BOURSE_CHALLENGE` 42 ISINs vs `FULL_BVMT_RESEARCH` 75 ISINs):
1. **`BL-CASH`**: `100%` cash (`0.000%` net return, `0.000%` max DD).
2. **`BL-EW-CHAL`**: Equal-Weight across all `42` Challenge ISINs (entered at start `next_open` with `0.50%` fee, held or rebalanced on identical cadence, reported both MTM and Liquidated).
3. **`BL-EW-FULL`**: Equal-Weight across all `75` BVMT equity ISINs.
4. **`BL-BH-INIT`**: Buy-and-Hold of the account's confirmed initial holdings (`Nov 7` / `Nov 9` / `Nov 12` snapshots) over the recent window.
5. **`BL-MOM20`**: Simple `20s` price momentum Top-5 (`>= 5,000` TND 20s median turnover, `10%` weight cap, `10%` volume cap).
*(Note: **`TUNINDEX`** remains labeled `UNAVAILABLE` until `histo_indice` CSV is ingested.)*

### Exact Metric Definitions (`ModelExperiment`, `ADR-004`)
- **`net_return_pct`**: `(ending_equity_tnd / starting_equity_tnd - 1) * 100` (cash + MTM holdings).
- **`liquidated_return_pct`**: `(cash + sum(qty * close * 0.995) / starting_equity_tnd - 1) * 100`.
- **`alpha_vs_cash_pct` / `alpha_vs_ew_pct`**: `strategy_net_return_pct - baseline_net_return_pct`.
- **`max_drawdown_pct`**: `max_t ((peak_equity_to_t - equity_t) / peak_equity_to_t) * 100`.
- **`top1_excluded_return_pct`**: Full simulation net return re-computed after excluding the single equity with highest cumulative realized + unrealized TND contribution.
- **`turnover_pct`**: `(sum(buy_gross + sell_gross) / (2 * average_equity)) * 100`.
- **`active_utilization_pct`**: Mean daily `(holdings_mv_tnd / total_equity_tnd) * 100`.
- **`win_rate` / `precision` / `fpr`**: Evaluated over identical **known-executable** candidate denominators (`unknown` / `unexecutable` counts explicitly disclosed, never dropped silently or counted as zero-return).

---

## 5. Observed Baseline Run Metadata (`artifacts/v2/v2-benchmark-results.json`)

- **Executed Script**: `research/experiments-v2/run_v2_benchmark_suite.py` (`exit 0`, `data_hash = c9ee...` / exact hash saved in artifact)
- **Strict PIT Audit**: Confirmed `0` historical Challenge signals prior to `2026-11-09` (`REGISTRY_KNOWN`) and `0` rows with verified `published_at`.
- **Retrospective Diagnostic Coverage (`H = 5, 10, 20`)**: Verified across all 9 `FAMILIES`, phase-offset sweeps (`min`/`p25`/`median`/`p75`/`max`/`iqr_pp`), `50 bps` slippage (`[low, high]` bound rejections occur on `open == high` days), `T+3` settlement sensitivity, `top1_excluded_return_pct`, and all 9 `EXIT_POLICIES` across `EURO-CYCLES`, `DELICE_HOLDING`, and `MPBS`.
