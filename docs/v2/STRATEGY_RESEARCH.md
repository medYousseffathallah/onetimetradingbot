# BVMT V2 Strategy Research: Hypothesis Families A–J, Horizon Feasibility & Engine Audit

**Scope**: First-principles hypothesis taxonomy (`A–J`) across `5` holding horizons (`1–2`, `3–5`, `5–10`, `10–20`, `20–60` sessions), explicit horizon support/block status grounded in R1–R2 empirical findings, and reusable library evaluation (`Qlib`, `Backtrader`, `VectorBT`).  
**Precondition**: No hypothesis below is promoted or certified for live allocation. All backtests on `2026-01-02..2026-11-18` (`202` sessions) are retrospective exploratory studies (`M14_CORRECTED_STRATEGY_RESULTS.md`).

---

## 1. Empirical Boundary Conditions from R1 & R2

Any BVMT V2 strategy must survive five hard structural constraints measured in R1–R2:
1. **100 bps Round-Trip Hurdle**: `0.50%` buy fee + `0.50%` sell fee (`configs/competition.json` FAQ) erases an entire week of Challenge Equal-Weight drift (`Nov 9–18` Challenge EW: `+1.1185%` gross vs **`-0.0130%` net**).
2. **Severe Thin-Liquidity Bottleneck**: Across Challenge 42 trailing 20s median turnover (`29,726.06 TND`), only **20 / 42 (`47.6%`)** stocks can absorb a `5,000 TND` sleeve in 1 session at `10%` ADV, and **27 / 42 (`64.3%`)** over 3 sessions (`15 / 42` fail even 3-day staging).
3. **Zero-Volume & Limit-Reserved Gaps**: `35.7%` of Challenge stocks and `75%+` of Non-Challenge stocks exhibit episodic zero-volume days or `'H'/'B'` limit reservations (`ICF` 20s zero-vol = `30%`, `ATTIJARI_LEASING` = `40%`).
4. **Absence of PIT Fundamentals, Corporate Actions & `TUNINDEX`**: Zero financial statements, dividend adjustments, or index CSVs exist locally; `15,080 / 15,080` rows lack `published_at`.
5. **Outlier & Phase Sensitivity**: Legacy Model G (`18.60%` corrected Challenge) derived `~63%` of profit from `SOTETEL` (`8.03%` ex-`SOTETEL`) with `7.29 pp` cadence-20 IQR and `74.83%` idle cash.

---

## 2. Hypothesis Families A–J (Economic Rationale & BVMT Fit)

| Family | Strategy Archetype | Economic Mechanism & Signals | BVMT Failure Mode / Constraint | V2 Status |
|---|---|---|---|---|
| **A** | **Cash & Capital Preservation Baseline** | `100%` cash (`0.00%` gross/net); opportunity-cost hurdle. | Zero market beta during broad rallies (`Nov 6–18`: `+1.12%` gross EW). | **Active Baseline** |
| **B** | **Equal-Weight Rebalanced Benchmark** | Equal capital across all liquid/eligible Challenge 42 (or Full 75 ISIN) equities. | `1.00%` round-trip fee drag destroys short-horizon net returns (`-0.013%` over `Nov 9–18`). | **Active Baseline** |
| **C** | **Buy-and-Hold Initial / Passive Basket** | One-time entry into liquid Challenge core; minimizes turnover and `100 bps` fee bleed. | Vulnerable to single-stock concentration drift (`>10%`) and missing regime exits. | **Active Baseline** |
| **D** | **Cross-Sectional Medium-Term Momentum** | `20s` / `40s` / `60s` bounded risk-adjusted momentum (`bounded_risk_ratio_v2`) with `t+1` open entry. | Crowds into post-spike stocks (`STA`, `SMART` Nov 10), high phase IQR (`7.29 pp` in legacy G), and `SOTETEL`-like single-winner reliance. | **Primary Exploratory (`5–10`, `10–20`s)** |
| **E** | **Relative Strength vs. Challenge Cross-Section** | Excess `20s`/`60s` return over Challenge-42 median/mean (proxy until `TUNINDEX` is ingested). | Rank-equivalent to Family D under pure cross-sectional sorting unless paired with an absolute cash-gate (`rs > 0` & `bench > 0`). | **Exploratory (`10–20`s)** |
| **F** | **Liquidity-Constrained Trend + Cash Utilization** | Ranks Challenge 42 by bounded momentum **multiplied/capped by 20s median ADV capacity**, staging unfilled cash into secondary liquid names (`>= 50k` TND ADV) instead of sitting `75%` idle. | Risk of diluting signal quality into lower-conviction Tier-1 banks (`AMEN`, `BIAT`, `BNA`) to reduce cash drag. | **High-Priority V2 Hypothesis (`5–10`, `10–20`s)** |
| **G** | **Liquidity-Awakening & Volume-Expansion** | Detects volume surges (`vol / 20s_med_vol`) after dormant/limit-reserved (`'H'/'B'`) regimes **only with positive directional confirmation** (`close > prev_close` & `ret > 0`). | Legacy `sparse_research_v1` suffered `60.58%` FP and `-5.11%` mean net in `SPARSE_LATER_FELL` because it lacked directional & trap filters. | **Research-Only (`5–10`s; strict trap gate)** |
| **H** | **Short-Term Mean Reversion / Pullback** | Buying `1–5s` oversold dips inside positive `60s` uptrends to avoid chasing highs. | On thin BVMT books, falling prices often reflect multi-day informed distribution or illiquidity rather than noise bounce; high fee drag on short holds. | **Exploratory (`5–10`s only; `1–5`s blocked)** |
| **I** | **Downside-Risk & Drawdown-Filtered Quality** | Penalizes `60s` max drawdown and downside semi-volatility (`bounded_risk_ratio_v2`), cutting exposure when breadth `< 50%`. | Without PIT financial statements (`ROE`, `debt/equity`, `earnings`), "quality" is price-only and vulnerable to unadjusted ex-dividend drops. | **Partial (`10–20`s; awaits P1 fundamentals)** |
| **J** | **PIT Fundamental Value & Catalyst / Event Overlay** | Earnings growth (`indicateurs trimestriels`), P/E, dividend yield, CMF communiqués, BCT rate / JORT tariff shocks. | **100% Blocked locally**: zero PIT fundamental filings, zero corporate actions, static 6-item `macro_events.py` is `UNVERIFIED_CATALOG`. | **BLOCKED (until P0/P1 data ingested)** |

---

## 3. Five-Horizon Feasibility & Support Matrix

| Horizon | Sessions | Fee Hurdle (1.00% RT) | Microstructure & Data Verdict | Supported Families | Live / Promotion Status |
|---|---|---|---|---|---|
| **H1: `1–2` Sessions** | 1–2d | **Extreme** (`>=50–100 bps/day` needed just to break even) | **BLOCKED / UNSUPPORTED**: (1) EOD-only data has `current_executable_quote = UNAVAILABLE` and unknown `published_at`; (2) no intraday orderbook/tick data; (3) `t+1` open fill + `1–2`s exit leaves zero buffer for `100 bps` fee + bid-ask spread; (4) `22/42` Challenge stocks cannot absorb 5k in 1 session; (5) pending-order expiry/settlement rules (`T+0` vs `T+3`) are unverified. | None | **BLOCKED FOR LIVE & BACKTEST CLAIMS** |
| **H2: `3–5` Sessions** | 3–5d | **High** (`~20–33 bps/day` break-even) | **FRAGILE / RESEARCH-DIAGNOSTIC ONLY**: `15/42` Challenge stocks cannot absorb 5k even over 3 sessions at 10% median ADV; `1.00%` round-trip fee consumed `100%` of Nov 9–18 Challenge EW gains (`+1.12% -> -0.01%`). No live promotion allowed. | `F`, `G` (diagnostic only) | **UNSUPPORTED FOR LIVE CLAIMS** |
| **H3: `5–10` Sessions** | 5–10d | **Moderate** (`~10–20 bps/day`) | **PRIMARY EXPLORATORY HORIZON**: Aligns with `3`-session staged entry/exit feasibility for `27/42` Challenge stocks and yields `13–14` non-overlapping purged folds in the 202-session 2026 archive (`warmup=61`). | `B`, `D`, `F`, `G`, `H` | **Exploratory Research Only** (requires prospective `SignalJournal`) |
| **H4: `10–20` Sessions** | 10–20d | **Manageable** (`~5–10 bps/day`) | **PRIMARY EXPLORATORY HORIZON**: Matches typical BVMT liquidity cycle and reduces turnover bleed (`<= 1–2` rebalances/month). Limited to `~6–7` non-overlapping `20s` folds in 2026; requires phase-averaged testing across all start offsets. | `B`, `C`, `D`, `E`, `F`, `I` | **Exploratory Research Only** |
| **H5: `20–60` Sessions** | 20–60d | **Low** (`~1.7–5 bps/day`) | **DATA-BLOCKED FOR VALIDATION**: `202` sessions (`<11` months) after `61s` warmup leaves only `141` sessions -> **`2` non-overlapping 60s folds** (`N=2` has zero statistical power!). Furthermore, unadjusted **ex-dividend drops** and **absent PIT financials** (`P0-2`, `P1-1`) corrupt 20–60s return attribution. | `C`, `I`, `J` (conceptual) | **BLOCKED FOR LIVE & STAT CLAIMS (until 2022–2025 + CA + PIT fundamentals)** |

---

## 4. Open-Source Backtest Engine Evaluation (`Qlib`, `Backtrader`, `VectorBT`)

Evaluated against BVMT's exact domain constraints (`75` ISINs, thin liquidity, zero-volume days, `09:00–14:15` execution window, pending orders, `10%` single-stock cap with auto-reduction, `0.50%` `Decimal` fees, Python `3.12`/`3.13`):

| Criterion | Microsoft `Qlib` | `Backtrader` (`1.9.78.123` in `.venv`) | `VectorBT` (OSS) | V2 Custom `Decimal` Engine (`bvmt_v2`) |
|---|---|---|---|---|
| **License** | **MIT** (permissive) | **GPLv3** (strong copyleft if distributed) | **Apache 2.0 + Commons Clause** (non-open-source fair-code restriction) | **First-Party Repo License** (zero third-party lock-in) |
| **Maintenance & Py 3.13** | Active, but heavy Cython/`.bin` build friction on Windows | Unmaintained upstream (last release `2020`); pure Python works in `.venv` | Frozen OSS teaser for paid `vectorbt.pro`; Numba pins fragile on Py 3.13 | Native Python `3.12`/`3.13`, `mypy --strict`, `pytest` |
| **Thin Liquidity & Zero-Vol Bars** | Engineered for liquid CSI300/S&P500; bar-rebalance assumes continuous depth | **CRITICAL TRAP**: Default `BackBroker` uses `filler=None` (`100%` fill ignoring bar volume) and fills on stale/zero-vol bars unless heavily overridden | Vectorized 2D matrix ops cannot easily share cross-order session volume or pause across suspended sessions | Exact per-session `10%` trailing-ADV cap, zero fills on `volume == 0` / `untraded` bars |
| **BVMT `T+1` / Pending Queue / `10%` Cap** | Poor (cross-sectional daily rebalance assumptions) | Requires custom `CommInfoBase`, custom `Filler`, and rewriting `BackBroker` to enforce `10%` auto-reduction & 1-week expiry | Poor (path-dependent `10%` cap auto-reduction + cash reservation across pending orders breaks vectorization) | Native state machine: `t+1` open, `0.50%` fee, `10%` cap, explicit `Decimal` cash/share ledger |
| **Numeric Precision** | IEEE-754 `float64` | IEEE-754 `float64` | IEEE-754 `float64` / `float32` | **`Decimal` (`0.001` TND `ROUND_HALF_UP`)** per `ADR-002` |
| **Concrete Recommendation** | **DO NOT INSTALL / REFERENCE ONLY** (adopt `IC`/`RankIC` & purged walk-forward concepts) | **OPTIONAL ADAPTER / DO NOT USE AS PRIMARY** (despite being installed in `.venv`, overriding float-based `BackBroker` is more complex & error-prone than a ~300-line `Decimal` engine) | **REJECT** (Commons Clause + frozen OSS + inability to model stateful BVMT caps/queues) | **ADOPT AS PRIMARY ENGINE** (`src/bvmt_v2/backtester.py` + `duckdb`/`pandas`/`lightgbm`/`scikit-learn`) |

---

## 5. Reproducible V2 Benchmark Results (`run_v2_benchmark_suite.py`)

Executed via `bvmt_v2.backtester` over the clean equity archive (`data/v2_market/daily_bars.equity_only.csv`: `15,080` rows, `75` canonical ISINs after consolidating `TN0005700018`, `202` sessions `2026-01-02..2026-11-18`; artifact `artifacts/v2/v2-benchmark-results.json`):

1. **Strict PIT Mode (`Backtester.from_market`, `challenge_known_from = 2026-11-09`, `published_at = None`)**:
   - Returns **`N = 0`** active historical Challenge trades prior to `2026-11-09` because neither historical bar publication timestamps nor pre-Nov-9 Challenge universe membership files exist in the local archive. Only `BL-EW-FULL` (if ingestion timestamps permit) has non-Challenge universe coverage.
2. **Retrospective Exploratory Mode (`H = 10` Primary Horizon, `offset = 0`, `0 bps` extra slippage, `T+0` reuse, explicit unverified EOD availability & Challenge-42 retrospective membership)**:

| Strategy / Baseline (`H=10`) | Net Return | Alpha vs EW-CHAL | Max DD | Top-1 Excluded Return (`Top1`) | Utilization | Matched Fills (`N`) |
|---|---:|---:|---:|---:|---:|---:|
| `BL-CASH` | `0.00%` | `-22.08%` | `0.00%` | `0.00%` (`None`) | `0.00%` | `0` |
| `BL-EW-CHAL` (Challenge 42 EW) | **`+22.08%`** | `0.00%` | `14.22%` | **`+18.42%`** (`SOTETEL`) | `97.72%` | `196` |
| `BL-EW-FULL` (Full 75 ISINs EW) | `+12.29%` | `0.00%` *(self)* | `11.24%` | `+10.16%` (`SOTETEL`) | `81.53%` | `279` |
| `BL-MOM20` | `+6.88%` | `-15.19%` | `10.46%` | `-0.04%` (`SOTETEL`) | `56.22%` | `41` |
| `LEGACY-G-APPROX` (cadence `20`) | `+14.38%` | `-5.26%` | `5.75%` | `+1.80%` (`SOTETEL`) | `33.91%` | `10` |
| `V2-D-MOM-RISK` | `+6.59%` | `-15.48%` | `11.01%` | `-0.13%` (`SOTETEL`) | `54.76%` | `36` |
| `V2-F-LIQ-TREND` | `+14.18%` | `-7.89%` | `13.51%` | **`+10.50%`** (`SOTETEL`) | `87.93%` | `70` |
| `V2-H-PULLBACK` | `+7.93%` | `-14.14%` | `5.17%` | `+1.91%` (`SOTUVER`) | `35.91%` | `40` |
| `V2-G-AWAKENING` | `+15.83%` | `-6.24%` | `3.81%` | `+6.68%` (`SOTETEL`) | `30.09%` | `23` |

### Key Scientific Takeaways (No Hypothesis Promoted)
- **None of the tested active models beat `BL-EW-CHAL` (`+22.08%` MTM, `+18.42%` ex-`SOTETEL`) at `H=10`**, and at `H=20` only `V2-F-LIQ-TREND` (`+23.00%` vs `+21.81%`, phase-0) edges slightly ahead before dropping to `+12.82%` ex-`SOTETEL` (`< +17.84%` EW ex-`SOTETEL`).
- **Outlier & Phase Fragility**: Concentrated momentum rules (`BL-MOM20`, `LEGACY-G-APPROX`, `V2-D-MOM-RISK`) lose almost 90–100% of net return when `SOTETEL` is excluded (`-0.04%`, `+1.80%`, `-0.13%`) and exhibit `2.12–6.80 pp` IQR across cadence offsets (`V2-F-LIQ-TREND` spans `+8.85%` to `+35.46%`, median `+19.33%`).
- **T+3 Settlement Sensitivity**: Enforcing unverified `T+3` settlement drops `V2-F-LIQ-TREND` (`H=10`) from `+14.18%` to **`+1.93%`**, proving why resolving `settlement_and_cash` in `configs/competition.json` is critical before trusting high-turnover models.
- **Exit Policy Benchmark (`EURO-CYCLES`, `H=10`, `13/13` matched periods)**: `fixed_horizon` (`-2.01%`), `trend_deterioration` (`-1.44%`, `64.17%` false exits), `trailing_profit_5pct` (`-2.03%`), `partial_profit_trim` (`-2.00%`), **`opportunity_rotation` (`-0.60%`, lowest `27.74%` false-exit rate)**, `combined_risk_trend` (`-1.92%`). None turns a structurally declining stock profitable, reinforcing that entry quality and rotation beat naive tight stops on thin BVMT books.
