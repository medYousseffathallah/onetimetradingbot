# BVMT Quantitative & Event-Driven Trading Research Roadmap

## 1. Objective
Design the first reproducible, leakage-safe BVMT trading experiment to test whether combining **session-aware price/liquidity features** with **validated financial statement & corporate-event intelligence** improves risk-adjusted net portfolio value under realistic Tunis Bourse Challenge constraints.

Per `rules.md`, we make **no pre-test claims of profitability**, enforce strict point-in-time cutoffs, separate `research_conservative` from `competition_exact` profiles, and disclose all trial counts and assumptions.

---

## 2. Ten Research Components & Point-in-Time Definitions

All features at decision cutoff $t$ (evaluated after session close $s_t$ on open `ExchangeSession` dates) are computed strictly from observations with `session_date <= s_t`, `published_at <= t`, and `ingested_at <= t`:

| # | Component | Point-in-Time Formulation (Over Verified Open `ExchangeSession`s) | Purpose |
|---:|---|---|---|
| 1 | **Price Momentum (`mom_20s`, `mom_60s`)** | Total-return adjusted price ratio over the last 20 and 60 open exchange sessions (excluding most recent 1–2 sessions if short-term reversal is observed), requiring `traded` status at endpoints. | Capture medium-term trend persistence in liquid *Continu* stocks. |
| 2 | **Relative Strength (`rs_vs_universe`)** | Cross-sectional rank (`[0, 1]`) of 20/60-session return minus the equal-weight eligible *Continu* universe return over the identical session window. | Isolate stock-specific outperformance from market-wide moves. |
| 3 | **Trading Liquidity (`med_turnover_20s`, `trade_freq_20s`)** | Median daily `turnover_tnd` over the past 20 open sessions and fraction of open sessions with `status == "traded"` (`volume_shares > 0`). | Filter out illiquid stocks where orders get stuck in the simulator's pending queue. |
| 4 | **Volatility & Drawdown (`vol_20s`, `max_dd_60s`)** | Realized 20-session return standard deviation and 60-session peak-to-trough drawdown. | Penalize erratic, thin-book price spikes and size positions safely below the 10% cap. |
| 5 | **Financial Fundamentals (`yoy_rev_growth`, `net_margin_delta`, `div_yield`)** | YoY growth in quarterly revenue/PNB (`Indicateurs d'activité`), earnings trend, and trailing/proposed dividend yield—**joined strictly on `document_published_at <= t`**. | Anchor momentum in fundamental earnings/revenue improvement. |
| 6 | **Corporate Catalysts (`catalyst_score`)** | Point-in-time event indicator from validated Role 1/2/3 extractions (`dividend_declaration`, `earnings_release`, `capital_increase_bonus`, or negative `risk_flags`) within the last $K$ open sessions. | Capture post-announcement drift on the BVMT where fundamental news diffuses gradually. |
| 7 | **Publication Timing & Freshness (`days_since_filing`, `quote_staleness`)** | Open sessions elapsed since last `traded` bar and since last verified CMF/BVMT disclosure. | Exclude `stale_quote` (`>= 3` consecutive `no_trade` sessions) and decay old event signals. |
| 8 | **Portfolio Concentration (`max_weight = 0.10`)** | Hard 10% single-stock cap (`0.095` target weight buffer at order sizing to prevent price-drift cap violations before execution). | Comply with the Tunis Bourse Challenge 10% per-stock limit (requiring >= 10 stocks for full investment). |
| 9 | **Transaction Costs (`50 bps` buy / `50 bps` sell)** | Explicit `0.50%` purchase fee and `0.50%` sale fee (`1.00%` round-trip) plus research slippage (`20–50 bps`). Hurdle buffer requires expected alpha > round-trip cost before turnover. | Prevent over-trading from eroding capital under the competition's 0.50% brokerage fee. |
| 10 | **Execution Uncertainty & Pending Queue** | Models the 09:00–14:15 execution window, next-session rollover, zero-volume/suspended order holding, partial fills, and 1-week order expiration. | Ensure signals survive realistic execution delays and partial fills. |

---

## 3. Three Candidate Strategies to Compare

All three candidates operate on the exact same point-in-time eligible universe (*Continu du Marché Principal* equities passing minimum liquidity: `trade_freq_20s >= 0.75` and `med_turnover_20s >= threshold_tnd`, not `suspended` or `stale_quote`):

### Baseline A — Equal-Weight Eligible Portfolio (`EW_Eligible`)
- **Rule**: Invest equally across the top $N = 12$ most liquid eligible *Continu* stocks (`8.0%` target weight each, leaving `4.0%` cash buffer), rebalanced monthly (every 20 open sessions) only when weight drifts beyond `[6.0%, 9.8%]`.
- **Role**: Tests passive market participation net of the 0.50% fee and 10% concentration cap.

### Baseline B — Quantitative Momentum & Liquidity Ranking (`Quant_Baseline_T04`)
- **Rule**: Rank eligible liquid stocks weekly (every 5 open sessions) by risk-adjusted session momentum (`0.5 * rank(mom_20s / vol_20s) + 0.5 * rank(mom_60s / vol_20s)`). Hold top 10–12 stocks at `8.5%–9.0%` target weight; only replace an existing holding if a challenger exceeds the incumbent's rank by a **turnover buffer (`delta_rank >= 0.25`)** to amortize the 1.00% round-trip fee.
- **Role**: Pure price/volume baseline (`T04`) requiring zero LLM or fundamental data.

### Candidate C — Quantitative Ranking + Validated Fundamental/Event Intelligence (`Quant_Event_Hybrid`)
- **Rule**: Combines Baseline B's session-momentum rank with point-in-time validated fundamental/catalyst scores (`yoy_rev_growth`, `dividend_declaration`, `earnings_release`, and critic-verified `risk_flags` as a hard veto on deteriorating/suspended issuers).
- **Promotion Rule**: Candidate C is promoted over Baseline B **only if** it improves out-of-sample net return and Calmar/Sharpe ratio after identical 0.50% fees, slippage, and liquidity caps across purged chronological walk-forward folds.

---

## 4. Walk-Forward Validation Protocol & Acceptance Criteria

1. **Chronological Market-Wide Splits**:
   - Split by `session_date` across all securities simultaneously.
   - Purge any training window whose forward return label horizon ($H = 20$ open sessions) overlaps the validation/test start date.
   - Reserve the most recent 20% of historical sessions as an **untouched holdout period** evaluated only once.
2. **Dual Simulation Profiles**:
   - Run under `research_conservative` (`50 bps` fee, `20–50 bps` slippage, `1%–5%` volume participation cap, 1-week pending order expiry tested under both 5-trading-day and 7-calendar-day conventions).
3. **Mandatory Benchmark & Diagnostic Outputs**:
   - Compare against **100% Cash (`50,000 TND`)**, **Baseline A (`EW_Eligible`)**, and analytical **`TUNINDEX`** over identical dates.
   - Report net return, maximum drawdown, annualized turnover, total fees paid (TND), fill rate (`%` of orders filled vs expired/partially filled), concentration compliance, and total trial count.

