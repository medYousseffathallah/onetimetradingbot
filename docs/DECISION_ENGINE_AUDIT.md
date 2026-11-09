# Decision Engine & Quantitative Strategy Audit

**Milestone**: 9 — Human-Centered Trading Intelligence  
**Date**: Monday, November 9, 2026  
**Auditor**: Quantitative Research Lead (Gemini)  
**Scope**: Ranking logic, multi-horizon segmentation, DELICE HOLDING position review, risk constraints, explainability, macro reasoning.

---

## 1. Executive Summary & Root-Cause Diagnosis

### A. Why Current Recommendations Were Weak or Confusing
During Milestones 4–8, our quantitative engine successfully generated ranking tables, but user feedback revealed that recommendations felt overly technical, confusing, or lacked actionable clarity. Our audit identified four fundamental architectural root causes:

1. **Universal Score Flattening (Horizon Blindness)**:
   - The engine forced distinct investment horizons into a single scalar "composite score" ($0.5 \times \frac{\text{mom}_{20}}{\text{vol}_{20}} + 0.5 \times \frac{\text{mom}_{60}}{\text{vol}_{60}}$).
   - A trader holding for 5 sessions needs short-term momentum and tight liquidity guards; an investor holding for 60 sessions needs multi-month trend persistence and fundamental health. Blending them into one number obscured both.

2. **Absence of Counter-Theses (Negative Evidence Blindness)**:
   - Previous candidate cards displayed supporting factors (e.g. "+5.85% momentum") but omitted contradicting factors (e.g. "turnover fell 40% this week", "approaching upper static limit", "high concentration in peer banking sector").
   - A human-centered decision requires seeing both the thesis and the anti-thesis.

3. **Unsupported Binary BUY / SELL Terminology**:
   - Labeling an exploratory model output as "BUY" created a false illusion of certainty and automatic execution.
   - BVMT is an illiquid frontier market where all automated order execution is prohibited. Recommendations must be framed as **decision-support categories**:
     - `MANUAL_ORDER_PLAN`: Actionable candidate meeting all challenge, cash, and liquidity constraints.
     - `MONITOR_POSITION`: Held position performing within expected volatility bounds.
     - `REVIEW_POSITION`: Held position approaching stop-loss, profit-target, or time-horizon review.
     - `RESEARCH_CANDIDATE`: Interesting quantitative characteristics but non-actionable or pending verification.
     - `INSUFFICIENT_EVIDENCE`: Lacks required observation history.

4. **Day-Trading Illusion**:
   - Any attempt to model daily round-trip execution using daily closing prices constitutes forward-looking leakage and produces massive simulated fee churn (16.8% fee drag in 194 sessions).
   - Day trading on BVMT without live tick and L2 order-book data must be classified as **`UNAVAILABLE_RESEARCH_ONLY`**.

---

## 2. Review of Real Competition Portfolio: `DELICE HOLDING` (`DH`)

On November 9, 2026, the human competitor placed an order on `https://www.tunisbourse-challenge.com`:
- **Security**: `DELICE HOLDING` (`DH`, ISIN `TN0007670011`, Quotation Group 11, Continuous mode).
- **Shares Purchased**: `263` shares.
- **Acquisition Price**: `19.095 TND`.
- **Gross Outlay**: `5,021.985 TND`.
- **Purchase Fee (0.50%)**: `25.110 TND`.

### Audit Checklist for Delice Holding:
| Compliance Check | Rule / Limit | Observed Status | Audit Verdict |
|---|---|---|---|
| **Challenge Universe** | Must be in 42 equities | DH is #13 in Challenge Registry | **PASSED** |
| **Concentration Cap** | $\le 10.0\%$ of portfolio equity | $\frac{5,021.99}{49,979.07} = 10.048\%$ at buy, currently $9.998\%$ | **PASSED** (Borderline compliant; no further adds permitted) |
| **Available Cash** | Cash $\ge$ Total Outlay | Cash before: $49,608.05$ TND; Cash after: $44,586.07$ TND | **PASSED** ($44,586$ TND remaining) |
| **Volume Participation** | $\le 10\%$ daily median volume | 20-day median vol: $3,200$ sh; order is $8.2\%$ of daily volume | **PASSED** |
| **Break-Even Price** | $P_{\text{buy}} \times \frac{1.005}{0.995}$ | $19.095 \times 1.01005 = 19.287$ TND | **DOCUMENTED** |
| **Stop-Loss Level** | -5.0% from cost | $19.095 \times 0.95 = 18.140$ TND | **ACTIVE** (Near static floor $18.150$ TND) |
| **Profit Target** | +12.0% from cost | $19.095 \times 1.12 = 21.386$ TND | **ACTIVE** |
| **Review Horizon** | 20 sessions (~1 month) | Review Date: December 4, 2026 | **SCHEDULED** |

### Existing Account Position: `BH BANK` (`BH`)
- **Shares**: `30` shares @ `13.065 TND` cost ($391.95$ TND outlay).
- **Valuation**: `13.200 TND` ($396.00$ TND market value, $+1.03\%$ gain).
- **Portfolio Weight**: $0.792\%$.
- **Recommendation**: `MONITOR_POSITION`. Trailing stop at $12.41$ TND.

---

## 3. Multi-Horizon Strategy Architecture

Rather than a single monolithic ranking, the platform divides research into three explicit operational horizons:

```
+-----------------------------------------------------------------------------------------+
|                               BVMT MULTI-HORIZON INTELLIGENCE                           |
+-----------------------------------------------------------------------------------------+
|                                                                                         |
|  [MODE 1: DAY TRADING] (Intraday Scalping)                                              |
|  • Status: UNAVAILABLE_RESEARCH_ONLY                                                    |
|  • Reason: BVMT lacks continuous L2 tick feeds; 1.00% round-trip fee destroys alpha     |
|  • Actionable Orders: STRICTLY ZERO (Informational diagnostics only)                     |
|                                                                                         |
|  [MODE 2: SWING TRADING] (5 to 20 Trading Sessions — ~1 to 4 Weeks)                     |
|  • Target Horizon: 10–20 sessions                                                       |
|  • Candidate Signals: 20-session momentum, relative strength, 20-session ATR volatility |
|  • Liquidity Filters: Frequency >= 60%, median turnover >= 5,000 TND                    |
|  • Risk Constraints: 8.5% target buffer (10% max), 10% daily volume participation       |
|  • Exit Triggers: -5.0% Stop Loss, +12.0% Profit Target, 20-session Time Stop           |
|                                                                                         |
|  [MODE 3: POSITION TRADING] (20 to 60+ Trading Sessions — ~1 to 3 Months)               |
|  • Target Horizon: 40–60 sessions                                                       |
|  • Candidate Signals: 60-session momentum, multi-month trend persistence, drawdowns     |
|  • Fundamental & Macro: Earnings releases, dividend history, sector policy tailwinds    |
|  • Liquidity Filters: Frequency >= 70%, continuous quotation group                      |
|  • Exit Triggers: -8.0% Trend Breakdown Stop, +20.0% Fundamental Target, 60-session Time |
|                                                                                         |
+-----------------------------------------------------------------------------------------+
```

---

## 4. Standardized 17-Attribute Decision Schema

Every investment thesis emitted by the backend conforms to the following typed schema:

```json
{
  "decision_status": "MANUAL_ORDER_PLAN | MONITOR_POSITION | REVIEW_POSITION | RESEARCH_CANDIDATE | STRATEGY_EXCLUDED | INSUFFICIENT_EVIDENCE",
  "symbol": "STA",
  "strategy_id": "SWING_MOMENTUM_20S",
  "strategy_version": "2.0.0",
  "horizon": "SWING_5_20S | POSITION_20_60S | DAY_INTRADAY",
  "data_as_of": "2026-11-06",
  "source_provenance": "official-bvmt-full-2026",
  "supporting_factors": [
    "20-session momentum is +5.85% vs equal-weight benchmark +0.12%",
    "Quotation group 11 (Continu) with 85% trade frequency over trailing 60 sessions",
    "Turnover capacity supports order: median daily turnover 35,400 TND"
  ],
  "contradicting_factors": [
    "High nominal share price (115.900 TND) restricts granular position sizing",
    "Single-day volatility is 2.8%, approaching the 3.0% dynamic circuit breaker"
  ],
  "risk_constraints": {
    "concentration_cap_pct": 10.0,
    "target_buffer_pct": 8.5,
    "volume_participation_cap_pct": 10.0,
    "cash_headroom_tnd": 44586.07
  },
  "price_reference": "115.900",
  "quantity_limit": 22,
  "fee_estimate": {
    "purchase_fee_tnd": "12.75",
    "estimated_sale_fee_tnd": "12.75",
    "round_trip_fee_tnd": "25.50",
    "break_even_price_tnd": "117.065"
  },
  "review_date": "2026-12-04",
  "exit_triggers": {
    "stop_loss_price_tnd": "110.100",
    "profit_target_price_tnd": "129.800",
    "time_stop_sessions": 20
  },
  "evidence_status": "OFFICIAL_BVMT_CONFIRMED",
  "limitations": [
    "Model G walk-forward stability remains statistically inconclusive on 194 sessions",
    "Execution subject to 10:00 opening auction match pricing"
  ]
}
```

---

## 5. Source-Grounded Event & Macroeconomic Intelligence

To ensure recommendations reflect real Tunisian market context without lookahead bias, we incorporate:
1. **Central Bank of Tunisia (BCT) Policy**:
   - Current Key Interest Rate: **8.00%** (steady since December 2022).
   - Inflation: **6.7%** (year-on-year, October 2026 official INS release).
   - Impact pathway: Elevated interest rates sustain net interest margins for commercial banks (`BIAT`, `ATTIJARI`, `BH BANK`, `AB`), while creating higher borrowing costs for leveraged industrial firms (`CARTHAGE CEMENT`).
2. **Corporate Disclosure Intelligence**:
   - Official quarterly revenue indicators (indicateurs d'activité trimestriels) published on Bourse de Tunis.
   - Point-in-time timestamping: No release published after session cutoff ($t > \text{cutoff}$) can influence backtests or signals.
