---
name: bvmt-risk-review
description: "Review portfolio proposals and research reports for competition compliance, concentration, liquidity, cash, missing-data and execution risks. Trigger before any proposal reaches a human reviewer. Inputs are verified rules, positions, quotes, proposed changes, and evidence; output is a deterministic blocked/review-required decision with reasons, never an executed order."
---

# BVMT Risk Review

Work from the BVMT repository root. If the repository is unavailable, request its
path or files; do not invent project state or claim commands were executed.


1. Verify rule completeness, data freshness, account reconciliation and current holdings.
2. Fail closed on unknown critical fields; separate competition limits from house assumptions.
3. Compute projected holdings, cash, fees and settlement availability deterministically.
4. Check position/sector exposures, lot sizes, shared capacity and open-order reservations.
5. Include gap and unfilled-order scenarios; a stop is not a guaranteed exit.
6. Produce machine-readable reasons and source-linked human review information.
7. Confirm no runtime agent/tool can convert the result into an automatic platform action.
Until a complete ledger exists, mark position sizing and trade approval unsupported.
