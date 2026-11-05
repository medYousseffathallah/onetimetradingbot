# Simulation and validation specification

## Two named profiles
Competition-exact: only verified competition execution, fees, constraints, corporate-action,
settlement and final valuation semantics. Unverified rules mean BLOCKED.
Research-conservative: explicit hypothetical cost and volume settings with sensitivity bands.
A favorable research backtest does not demonstrate competition-exact performance.

## Minimum ledger
Maintain available/reserved/unsettled cash, shares by instrument, open orders, filled orders,
fees, receivables, dividends, corporate actions and valuation marks. Each fill updates one
balanced ledger transaction. Reconcile cash + marked holdings + receivables against equity.
Journal external simulator statements separately and surface differences.

## Execution tests before strategy research
- Same-session close-derived signal cannot fill at that close.
- No fill for zero volume, suspension, missing bar, or unverified price.
- Aggregate fills across orders cannot exceed the one shared participation budget.
- Tick/lot rounding and cash constraints hold; no fractional shares unless explicitly permitted.
- Slippage direction is unfavorable; assumptions never create out-of-range fills silently.
- Partial fills, cancellations, expiry, costs, settlement and gaps have declared behavior.
- Splits change share counts/cost basis consistently; dividends are not counted twice.
- Adjusted prices never enter the order ledger as tradable quotes.
- Missing valuations are flagged; stale marks are not evidence of low risk.
- Hand-calculated golden scenarios match exactly before a real historical run.

## Starter helper limitation
src/bvmt/execution.py is a market-fill arithmetic helper for synthetic scenarios. It is
not a portfolio engine and cannot enforce portfolio cash, session-wide capacity on its own,
settlement, queues, auction priority, tick sizes, or official competition semantics.
The caller passes remaining shared volume capacity; the future engine owns and updates it.

## Validation
Use expanding or rolling chronological folds by session across all stocks. Label windows
use verified sessions and actual execution timing. Purge overlapping label intervals from
training at each validation/test boundary. Fit every learned transformation inside its fold.
No look-ahead in financial statement release dates, universe membership, adjusted prices,
macro revisions, feature normalization, or historical news availability.
Freeze a holdout and predeclare tuning budget and primary promotion metric. Register all
experiments, including failures. Report uncertainty and regime sensitivity, not only Sharpe.

## Required report
Data coverage/vintage; train/validation/test dates; eligible universe; exclusions; net return;
benchmark return over identical dates; drawdown; turnover; fees/slippage; fill rate; capacity;
concentration; stale-price exposure; trial count; seed; code/config/data hashes; limitations.
Report sample sufficiency before interpreting results. No winner is mandatory.
