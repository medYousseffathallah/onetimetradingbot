---
name: bvmt-backtest-validation
description: "Build or audit BVMT historical simulation, fill models, cash and share ledgers, cost assumptions, corporate actions, and benchmark reports. Trigger before trusting a strategy return or integrating Backtrader. Inputs are versioned data, a declared simulation profile, and a strategy; outputs are reconciled execution tests and an assumption-explicit evaluation."
---

# BVMT Backtest Validation

Work from the BVMT repository root. If the repository is unavailable, request its
path or files; do not invent project state or claim commands were executed.


1. Read docs/BACKTEST_SPEC.md; select research-conservative or competition-exact explicitly.
2. Confirm the event timeline, decision cutoff, raw execution prices and data availability.
3. Write hand-calculated tests for cash, fees, partial fills, no-trade bars, gaps and actions.
4. Enforce aggregate session capacity across orders. Audit third-party engine defaults.
5. Reconcile the ledger and include stale/failed/unfilled orders, not only winning fills.
6. Compare date-aligned feasible baselines with identical costs and valuation assumptions.
7. Report uncertainty, capacity, drawdown, turnover and limitations; attach manifests.
Do not claim the starter fill helper is a full engine or that a synthetic demo proves profit.
