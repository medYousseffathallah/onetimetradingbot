# Goal and measurable definition of success

## Product goal
Build a transparent daily research workflow for the virtual Tunisian equity competition:
authorized data -> validated point-in-time dataset -> eligible stock ranking -> realistic
simulation -> deterministic risk checks -> source-linked human review.

## Competition ambition
Seek a strong final rank while documenting risk and execution feasibility. The user reports
43% for a previous fourth-place participant. That figure is not independently verified,
not an expected return, not this edition's required hurdle, and not a reason to tune a
backtest to 43-50%. Evaluate competition rank only after the actual scoring rules are known.

## First usable milestone
Import an authorized local historical CSV; preserve its raw bytes and provenance; validate
records; produce a data-quality report and an auditable, point-in-time research shortlist.
A conservative backtest is the next milestone. A live data collector, trained model,
complete portfolio ledger, and dashboard are not already implemented in this package.

## Engineering acceptance gates
- An offline fresh checkout reproduces the synthetic demo after environment setup.
- Automated tests reject future information, invalid OHLC, zero-volume fills, and unknown rules.
- Every derived result can be traced to data hashes, code revision, config, and decision cutoff.
- The official-rule gate stays closed until every required item has evidence and human review.
- Models enter production only after predeclared walk-forward tests and executable baselines.
- Daily source failures generate a blocked/research-only result, never invented prices.

## Non-goals for the first release
No broker connection; no automatic platform orders; no HFT; no reinforcement learning;
no LLM deciding cash or quantities; no generic political sentiment-to-buy shortcut;
no Kubernetes, Redis, vector database, or separate frontend/backend services by default.

## Decision ladder
Correct data > explicit assumptions > valid simulation > useful baseline > ML > LLM assistance.
Promotion means evidence improved, not that more technologies were installed.
