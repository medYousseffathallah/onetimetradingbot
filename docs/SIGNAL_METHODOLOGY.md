# Signal Methodology & Recommendation Engine Specification

This document explains how **BVMT Trading Intelligence** transforms verified historical market data, exchange-session calendars, corporate event disclosures, and competition portfolio constraints into explicit, auditable human recommendations.

---

## 1. The Five Recommendation States

Every eligible or held stock evaluated by the system is assigned exactly one of five explicit action states:

| Action State | Meaning | When Generated | Proposed Order Parameters Shown? |
| :--- | :--- | :--- | :--- |
| **`BUY CANDIDATE`** | New entry or position addition candidate | Stock passes all eligibility, freshness, and liquidity gates, ranks in the top composite score tier, has no disqualifying risk event, and has available cash + room under the **10% single-stock cap**. | **Yes** — only when data is current, rules/research profile is declared, and no conflicting pending order exists. |
| **`HOLD`** | Keep current position unchanged | Stock is currently held in the portfolio, remains eligible and liquid, has a neutral-to-positive composite rank, and stays within the **10% single-stock cap**. | **No** — no trade action needed. |
| **`REDUCE`** | Partial trim of an existing holding | Current holding (plus any pending buy orders) exceeds or approaches the **10% single-stock concentration cap** (e.g., `> 9.0%` of total portfolio value), or liquidity deteriorates while still tradable. | **Yes** — proposes trimming the excess shares needed to restore compliance with a safety margin (target `8.5%` weight). |
| **`SELL CANDIDATE`** | Full exit candidate for an existing holding | Existing holding falls into the bottom composite rank tier, suffers a negative 20-session and 60-session momentum breakdown, experiences a verified adverse corporate/financial event, or faces impending delisting/ineligibility. | **Yes** — proposes selling the held share quantity (subject to daily volume capacity warning). |
| **`NO TRADE`** | Do not trade / action withheld | Instrument fails point-in-time eligibility, has a stale or missing quote, is suspended, fails the minimum turnover/frequency filter, lacks sufficient lookback history, or the portfolio ledger has unreconciled pending orders. | **Never** — order sizing is suppressed and the exact blocking reason is displayed. |

---

## 2. Input Factors (Point-in-Time Only)

No signal may use any price bar, exchange session, or document published after the explicit decision timestamp (`as_of_date` / `decision_cutoff_utc`).

### 2.1 Session-Aware Quantitative Factors (`src/bvmt/features.py`)

Computed by `rank_session_baseline` strictly over open `ExchangeSession` dates (`is_open=True`) in `Africa/Tunis`:

1. **20-Session Momentum (`momentum_20s`)**:
   $$\text{Momentum}_{20s} = \frac{P_{t} - P_{t-20}}{P_{t-20}}$$
   where $t$ is the latest verified open exchange session on or before `as_of_date`, and $t-20$ is the 20th prior open exchange session. Both $t$ and $t-20$ must have `volume > 0` and `trades > 0`.
2. **60-Session Momentum (`momentum_60s`)**:
   $$\text{Momentum}_{60s} = \frac{P_{t} - P_{t-60}}{P_{t-60}}$$
   requiring a tradable anchor bar at $t-60$ (`volume > 0` and `trades > 0`).
3. **Universe Benchmark & 20-Session Relative Strength (`relative_strength_20s`)**:
   - The equal-weighted 20-session return of all eligible, non-suspended `Continu_Principal` stocks with valid history on session $t$ serves as `benchmark_return_20s`.
   - $$\text{RS}_{20s} = \text{Momentum}_{20s} - \text{Benchmark}_{20s}$$
4. **20-Session Realized Volatility (`volatility_20s`)**:
   - Sample standard deviation of session-to-session returns across the 20 open sessions $[t-20 \dots t]$.
5. **Liquidity & Trading-Frequency Filters**:
   - **20-Session Median Daily Turnover (`median_turnover_20s`)**: Median of `turnover` (TND) across the 20 open sessions $[t-19 \dots t]$, including zero-volume sessions as `0` TND. Default minimum threshold: **`5,000 TND`** (configurable per research profile).
   - **20-Session Trade Frequency (`trade_frequency_20s`)**: Fraction of the last 20 open sessions in which the stock actually traded (`volume > 0` and `trades > 0`). Default minimum threshold: **`0.60` (at least 12 of 20 sessions traded)**.
6. **Composite Quantitative Score (`composite_score`)**:
   $$\text{Score}_{\text{quant}} = 0.50 \cdot \text{Momentum}_{20s} + 0.30 \cdot \text{Momentum}_{60s} + 0.20 \cdot \text{RS}_{20s}$$
   Deterministic tie-breaking: descending `composite_score`, descending `median_turnover_20s`, ascending `instrument_id`.

### 2.2 Validated Corporate Announcement & Event Modifiers (`schemas/event.schema.json`)

When structured event records extracted via the 3-role pipeline (`Role 1 Extractor -> Local Verbatim Quote Guard -> Role 2 Skeptical Reviewer`) are present prior to `decision_cutoff_utc`:

- **Hard Gate**: Events with `quote_verified: false` or `review_verdict != "APPROVED"` are ignored (`0.0` impact).
- **Risk Override (`SELL CANDIDATE` / `NO TRADE`)**: Verified regulatory suspension, going-concern warning, or severe governance/default filing immediately blocks `BUY CANDIDATE` and flags held positions as `SELL CANDIDATE` (with human review warning).
- **Catalyst Confirmation**: Verified positive earnings/dividend/guidance disclosures are attached as source-cited evidence spans on the recommendation card (`evidence_citations`), with explicit publication timestamps and verbatim French/Arabic quotes.

---

## 3. Competition Portfolio & Cost Rules Applied to Every Signal

Before any quantitative candidate becomes a user-facing recommendation, the portfolio compliance layer applies the verified **14th Edition Tunis Bourse Challenge** constraints:

1. **Eligible Market Segment**:
   - Must be listed on the BVMT **Marché Principal (`Continu_Principal`)** on `as_of_date`.
2. **Transaction Fee Hurdle (`0.50%` Buy + `0.50%` Sell = `1.00%` Round-Trip)**:
   - Every buy or sell incurs a **`0.50%`** commission (`commission_rate = Decimal("0.005")`).
   - Churn prevention: the system does not recommend rotating out of an existing `HOLD` position into a marginally higher-ranked stock unless the composite score advantage exceeds the configurable turnover buffer plus the `1.00%` round-trip fee drag.
3. **Hard 10% Single-Stock Concentration Cap (`max_single_position_weight = 0.10`)**:
   - Under official competition rules, no single stock may exceed **10% of total portfolio value** (`cash + market_value_of_holdings`). Orders exceeding this limit are automatically reduced or purged by the competition simulator.
   - **Safety Margin Sizing**: Proposed `BUY CANDIDATE` orders are sized to a maximum target weight of **`9.0%` (`0.090`)** of total portfolio equity (including existing shares and any open `PENDING` buy orders for that stock) so intraday price ticks or rounding never breach the 10.0% ceiling.
4. **Liquidity Participation Cap**:
   - Proposed order notional (`quantity * reference_price`) is capped at **`10%` of `median_turnover_20s`** so the user is warned against placing orders that cannot realistically fill in low-volume BVMT sessions.
5. **Pending-Order Reconciliation Guard**:
   - Available cash for new `BUY CANDIDATE` sizing is:
     $$\text{Cash}_{\text{available}} = \text{Cash}_{\text{settled}} - \sum_{\text{open BUY orders}} \left(\text{RemainingQty} \times \text{LimitPrice} \times 1.005\right)$$
   - If an instrument already has an active `PENDING` or `PARTIALLY_FILLED` order in the local ledger, the system suppresses duplicate new order sizing and displays **`PENDING ORDER ACTIVE — RECONCILE BEFORE NEW ORDER`**.

---

## 4. Decision Tree for Assigning Recommendation States

For each instrument $i$ on session $t$:

1. **Check Data & Eligibility Gates**:
   - Is $i$ unlisted/delisted, not in `Continu_Principal`, suspended on $t$, missing a bar on $t$ (`stale_quote` / `missing_observation`), missing a tradable anchor at $t-20$ or $t-60$, or below `min_median_turnover_20s` / `min_trade_frequency_20s`?
   - **If YES**:
     - If $i$ is **not held**: emit **`NO TRADE`** with the exact `ExclusionReason` code.
     - If $i$ **is currently held**: emit **`NO TRADE`** (if suspended/stale — cannot size safely until verified) or **`SELL CANDIDATE` / `REDUCE`** warning if liquidity or listing status is deteriorating.
2. **Evaluate Existing Holdings (`current_shares > 0`)**:
   - Compute current weight $w_i = \frac{\text{shares}_i \times P_{i,t}}{\text{TotalPortfolioEquity}}$.
   - **If $w_i > 0.095$ (approaching or exceeding the 10% cap)**:
     - Emit **`REDUCE`** with proposed sell quantity to bring weight back to `0.085`.
   - **Else if $\text{Momentum}_{20s} < 0$ AND $\text{Momentum}_{60s} < 0$ (or verified adverse corporate event)**:
     - Emit **`SELL CANDIDATE`** for the full held position.
   - **Else**:
     - Emit **`HOLD`**.
3. **Evaluate Non-Held Eligible Candidates (`current_shares == 0`, or Held below target weight)**:
   - Does the instrument rank in the top $K$ eligible candidates (default top 5) with $\text{Momentum}_{20s} > 0.015$ (exceeding the `1.00%` round-trip fee hurdle) and $\text{RS}_{20s} > 0$?
   - **If YES**:
     - Check whether $\text{Cash}_{\text{available}}$ is sufficient for at least 1 share after `0.50%` fee and whether $w_i < 0.085$.
     - If sufficient and no conflicting pending order exists: emit **`BUY CANDIDATE`** with `Decimal`-reconciled quantity and limit price parameters.
     - Otherwise: emit **`NO TRADE`** (reason: `insufficient_available_cash` or `pending_order_already_open`).
   - **If NO**:
     - Emit **`NO TRADE`** (reason: `below_ranking_threshold`).

---

## 5. Required Disclosures on Every Recommendation Card

Every recommendation generated by the CLI or local dashboard must display:

1. **`recommendation_id`**: Deterministic unique identifier (e.g., `REC-20261105-BIAT-01`).
2. **`simulation_profile`**: Explicitly labeled as `SYNTHETIC_DEMO`, `RESEARCH_CONSERVATIVE`, or `COMPETITION_MANUAL_SUPPORT`.
3. **`source_data_as_of` & `analysis_generated_at_utc`**: Exact session date of the closing price bar and UTC timestamp of the computation.
4. **Quantitative Breakdown**: `momentum_20s`, `momentum_60s`, `relative_strength_20s`, `volatility_20s`, `median_turnover_20s`, `trade_frequency_20s`, and `composite_score`.
5. **Portfolio & Cost Impact**: Current weight, post-trade projected weight (must be $\le 9.0\%$), estimated `0.50%` fee in TND, and reserved cash impact.
6. **Evidence Citations**: Snapshot SHA-256 of the price dataset and any verified CMF/BVMT event filing IDs + verbatim quotes.
7. **Explicit Limitations Warning**:
   - Whether competition rules remain partially unverified (`uv run bvmt rules-check` status).
   - Reminder that orders execute on `tunisbourse-challenge.com` only during `09:00–14:15` (`Africa/Tunis`) and remain `PENDING` on zero-volume stocks.

