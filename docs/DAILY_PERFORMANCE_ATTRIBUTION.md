# BVMT Trading Intelligence — Daily Performance Attribution Framework
## Formal Accounting Semantics, P&L Taxonomy & Strategy Feedback Loop

**Milestone**: 12  
**Date**: November 9, 2026  
**Audience**: Gemini (Quantitative Backend), Codex (Frontend/Extension), Human Trader  

---

## 1. P&L Semantics & Formal Definitions

A critical finding from Milestone 12 is that **snapshot equity changes must never be casually equated with daily trading profit**. To ensure institutional-grade accounting, the platform enforces strict definitions:

```
Total Session Equity Change = Realized P&L + Session Holdings Delta + Cash Adjustments - Trading Fees
```

### Taxonomy:

1. **Unrealized P&L Since Acquisition (`unrealized_pnl_since_acq`)**:
   $$\text{Unrealized P\&L}_i = \text{Current Market Value}_i - \text{Acquisition Outlay}_i$$
   * Evaluated strictly on open positions.
   * Includes initial purchase fees embedded in the acquisition cost.
   * On Nov 9 close: **-9.860 TND** net (BH +0.75, DH -1.31, NBL +5.55, STA -14.85).

2. **Realized P&L (`realized_pnl_session`)**:
   $$\text{Realized P\&L} = \sum (\text{Sale Net Proceeds} - \text{Acquisition Cost Basis})$$
   * Evaluated on positions closed during the session.
   * On Nov 9: **+71.820 TND** from the liquidation of 35 shares (outlay 4,611.450 TND $\rightarrow$ proceeds 4,683.270 TND).

3. **Session Holdings Delta (`session_holdings_delta`)**:
   $$\sum_{i \in \text{Held All Day}} Q_i \cdot (P_{i, \text{close}} - P_{i, \text{open}}) + \sum_{j \in \text{New Buys}} (V_{j, \text{close}} - \text{Outlay}_j)$$
   * Measures the mark-to-market performance of equities held during the session.
   * On Nov 9: **+11.070 TND** (DH +23.670, NBL +5.550, BH -3.300, STA -14.850).

4. **Change in Account Equity (`equity_change`)**:
   $$\Delta \text{Equity} = \text{Equity}_{\text{close}} - \text{Equity}_{\text{open}}$$
   * On Nov 9: $50,061.960 - 49,979.070 = \mathbf{+82.890\text{ TND}}$.
   * Exactly matches $\text{Realized P\&L } (+71.820) + \text{Session Holdings Delta } (+11.070) = \mathbf{+82.890\text{ TND}}$.

5. **Cumulative Return Since Inception**:
   $$\text{Cumulative P\&L} = \text{Equity}_{\text{close}} - 50,000.000\text{ TND}$$
   * On Nov 9: $50,061.960 - 50,000.000 = \mathbf{+61.960\text{ TND}} \ (+0.124\%)$.
   * Matches the footer display on `displayp.aspx`: `Totaux 50061.96  61.96  0.12%`.

---

## 2. Strategy Decision Evaluation Matrix

Every quantitative signal emitted by the Trade Planner is audited against human execution fidelity:

| Symbol | Quantitative Signal | Suggested Shares & Ref Price | Actual Human Execution | Execution Fidelity | Current Mark & Return | Risk Stops & Target | Scientific Evaluation |
|---|---|---|---|---|---|---|---|
| **STA** | Multi-Horizon Swing (Model G) | 22 shares @ 115.900 TND | **22 shares @ 115.575 TND** | **EXACT MATCH** | 114.900 TND (-0.58%) | Stop: 110.150 TND<br>Target: 126.500 TND | Executed at favorable entry (115.575 vs 115.900). Day 1 mark-to-market spread dip (-0.58%) is normal execution friction; position remains well above the 110.15 TND stop-loss. |
| **DH** | Concentration Risk Guard | HOLD (0 shares) @ 19.000 TND | **HOLD (0 shares)** | **EXACT MATCH** | 19.090 TND (-0.03%) | Stop: 17.800 TND<br>Target: 21.500 TND | Position holds 263 shares (5,020.670 TND capital = 10.03% weight). Hold recommendation prevented disqualification under the 10% competition concentration rule. |
| **MNP** | Challenge Universe Gate | SUPPRESS (Not in Universe) | **NO TRADE (0 shares)** | **EXACT MATCH** | N/A | N/A | Filtering out non-challenge securities successfully prevented order rejection errors on the competition portal. |
| **SCN** | Challenge Universe Gate | SUPPRESS (Not in Universe) | **NO TRADE (0 shares)** | **EXACT MATCH** | N/A | N/A | Same as above. |

---

## 3. Risk & Portfolio Guardrails

1. **Single-Stock Concentration Ceiling (10%)**:
   * `DELICE HOLDING` capital is `5,020.670 TND` on `50,061.960 TND` equity (**10.029%**).
   * **Rule Policy**: Do not buy any additional shares of Delice.
2. **Aggregated Capital Utilization**:
   * Total invested: `8,439.170 TND` (16.86%).
   * Cash reserve: `41,622.790 TND` (83.14%).
   * **Verdict**: Conservative, asymmetric advantage. Zero margin or liquidity distress.
3. **Pending Orders**:
   * Verified: 0 unfulfilled orders pending.
