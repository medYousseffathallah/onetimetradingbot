---
name: bvmt-data-engineering
description: "Implement or review BVMT source adapters, local CSV ingestion, immutable snapshots, identifiers, exchange sessions, corporate actions, and point-in-time financial tables. Trigger for data collection, parser bugs, quality checks, or schema changes. Inputs are authorized source files and contracts; output is reproducible validated data plus rejection and provenance reports."
---

# BVMT Data Engineering

Work from the BVMT repository root. If the repository is unavailable, request its
path or files; do not invent project state or claim commands were executed.


1. Read docs/DATA_CONTRACTS.md and the relevant source entry. Confirm units and permission.
2. Save raw bytes with checksum and actual retrieval time before parsing; never mutate them.
3. Build a source-specific parser with explicit language/number/date handling.
4. Validate IDs, chronology, OHLC, volume units, duplicates, no-trade status and revisions.
5. Keep missing, suspended, holiday and zero-volume observations distinct. Never fill volume.
6. Test malformed input, delayed publications, revisions, unit confusion and duplicate replay.
7. Produce a dataset manifest and a rejection report; do not silently discard bad records.
Do not invent endpoints or scrape around access controls. Use fixtures when access is blocked.
