---
name: bvmt-dashboard-review
description: "Build or review the local BVMT research dashboard after validated data and simulation exist. Trigger for Streamlit views, research report usability, freshness warnings, or dashboard tests. Inputs are typed research artifacts; output is an evidence-linked local interface that distinguishes synthetic, stale, unverified and actionable-review states."
---

# BVMT Dashboard Review

Work from the BVMT repository root. If the repository is unavailable, request its
path or files; do not invent project state or claim commands were executed.


1. Verify the upstream artifact contracts and status labels; do not generate missing market data.
2. Show cutoff, source age, exclusions, simulation profile, rule state and model version prominently.
3. Separate research ranking, simulated performance and actual competition journal.
4. Link metrics to sources and definitions; label absent/unknown values rather than plotting zeros.
5. Keep the interface localhost-only with no secrets or account sessions in browser storage.
6. Test empty, stale, partial, failed and synthetic states; use browser automation only for our UI.
7. Keep all order-entry and automatic trade buttons out of the MVP.
Do not build this interface before the data and backtest acceptance gates exist.
