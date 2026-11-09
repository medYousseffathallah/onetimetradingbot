# Trade Planner Safety & Quantitative Model Audit

## 1. Executive Summary

This document presents the rigorous scientific and operational audit of the Trade Planner and Quantitative Strategy evaluation performed on Monday, November 9, 2026.

### Primary Audit Discoveries:
1. **The Model D Fallback Root Cause**: The previously reported 19-session holding period performance (+17.05% return, 40 fills, 1,192.79 TND fees) was discovered to have been executed using **Model D (`D_MOMENTUM_20S`)**, NOT Model G. A typographical discrepancy in `holding_period.py` (`model_id = "G_LIQUIDITY_MOMENTUM_FILTERED"` instead of `STRATEGY_IDS[6] = "G_LIQUIDITY_FILTERED_MOMENTUM"`) caused the strategy selection to fall through all conditions and default to raw 20-session momentum (`score = m.mom20`).
2. **Genuine Model G Evaluation**: When evaluated with genuine Model G (`G_LIQUIDITY_FILTERED_MOMENTUM`):
   - **Full BVMT (76 instruments)**: Horizon 19 yields +18.81% net return, 4.98% MaxDD, 43 fills, 1,196.87 TND fees. Horizon 20 yields +8.45% net return, 4.89% MaxDD, 31 fills, 977.24 TND fees.
   - **Tunis Bourse Challenge Universe (42 equities)**: Horizon 19 yields +11.29% net return, 7.71% MaxDD, 37 fills, 1,084.59 TND fees. Horizon 20 yields +5.84% net return, 5.06% MaxDD, 25 fills, 645.50 TND fees.
3. **Calendar Rebalance Luck (19 vs 20 Sessions)**: The dramatic divergence in returns between 19 sessions (+18.81% / +11.29%) and 20 sessions (+8.45% / +5.84%) is driven by a 1-session phase shift in rebalance dates. In a 194-session sample, shifting rebalancing by a single day changes whether positions are liquidated before or after sharp local price corrections.
4. **Conclusion on Conclusiveness**: The strategy returns remain **STRICTLY INCONCLUSIVE**. The 20-session holding window must be operated as a flexible human review cadence, never an automated dogma.

---

## 2. Complete Horizon Comparison: Model D vs Model G

### Model D (`D_MOMENTUM_20S`) — Previously Reported
| Horizon | Net Return | Max Drawdown | Fills | Total Fees | Turnover | Fee Drag | Verdict |
|---|---|---|---|---|---|---|---|
| 1 session (Daily) | +16.95% | 8.18% | 520 | 8,414.45 TND | 16.8x | 16.8% | Unviable churn |
| 5 sessions (Weekly) | +9.63% | 7.68% | 136 | 2,991.07 TND | 5.98x | 6.0% | High churn |
| 10 sessions (Bi-Weekly) | +1.20% | 8.00% | 87 | 2,143.87 TND | 4.29x | 4.3% | Whipsawed |
| 19 sessions (~Monthly) | **+17.05%** | **5.35%** | **40** | **1,192.79 TND** | **2.38x** | **2.4%** | Calendar peak |
| 20 sessions (Monthly) | +7.19% | 4.44% | 37 | 1,059.40 TND | 2.12x | 2.1% | Phase shift |
| 40 sessions (Bi-Monthly) | +8.23% | 5.58% | 17 | 581.93 TND | 1.16x | 1.2% | Low turnover |

### Genuine Model G (`G_LIQUIDITY_FILTERED_MOMENTUM`) — Full BVMT (76 Equities)
| Horizon | Net Return | Max Drawdown | Fills | Total Fees | Turnover | Fee Drag | Feasibility |
|---|---|---|---|---|---|---|---|
| 1 session (Daily) | +27.53% | 5.98% | 507 | 8,484.03 TND | 16.9x | 17.0% | POOR |
| 5 sessions (Weekly) | +14.25% | 6.56% | 136 | 2,949.48 TND | 5.90x | 5.9% | MODERATE |
| 10 sessions (Bi-Weekly) | +7.65% | 6.48% | 73 | 1,854.47 TND | 3.71x | 3.7% | MODERATE |
| 19 sessions (~Monthly) | **+18.81%** | **4.98%** | **43** | **1,196.87 TND** | **2.39x** | **2.4%** | GOOD |
| 20 sessions (Monthly) | +8.45% | 4.89% | 31 | 977.24 TND | 1.95x | 2.0% | GOOD |
| 40 sessions (Bi-Monthly) | +11.44% | 4.87% | 18 | 631.21 TND | 1.26x | 1.3% | GOOD |

### Genuine Model G — Restricted to Tunis Bourse Challenge (42 Equities)
| Horizon | Net Return | Max Drawdown | Fills | Total Fees | Turnover | Fee Drag | Feasibility |
|---|---|---|---|---|---|---|---|
| 1 session (Daily) | +13.41% | 7.10% | 396 | 5,288.80 TND | 10.6x | 10.6% | POOR |
| 5 sessions (Weekly) | +8.90% | 6.89% | 96 | 2,136.66 TND | 4.27x | 4.3% | MODERATE |
| 10 sessions (Bi-Weekly) | +8.29% | 6.58% | 59 | 1,382.35 TND | 2.76x | 2.8% | MODERATE |
| 19 sessions (~Monthly) | **+11.29%** | **7.71%** | **37** | **1,084.59 TND** | **2.17x** | **2.2%** | GOOD |
| 20 sessions (Monthly) | +5.84% | 5.06% | 25 | 645.50 TND | 1.29x | 1.3% | GOOD |
| 40 sessions (Bi-Monthly) | +6.34% | 6.68% | 17 | 503.79 TND | 1.01x | 1.0% | GOOD |

---

## 3. Mathematical Safety & Enforcement Rules

1. **Universe Gating**:
   ```python
   if not inp.is_challenge_member:
       suggested_shares = 0
       is_actionable = False
       binding_constraint = "not_in_challenge_universe"
   ```
2. **Cash Ceiling**:
   ```python
   max_shares_by_cash = int(available_purchasing_cash // total_unit_cost)
   ```
3. **10% Concentration Constraint**:
   ```python
   max_equity_allocation = portfolio_total_equity * 0.10
   max_shares_by_cap = int((max_equity_allocation - current_exposure) // total_unit_cost)
   ```
4. **10% Daily Volume Participation**:
   ```python
   max_shares_by_vol = int(median_daily_volume_20s * 0.10)
   ```
5. **Deterministic Sizing**:
   ```python
   suggested_shares = max(0, min(max_shares_by_cash, max_shares_by_cap, max_shares_by_vol))
   ```

