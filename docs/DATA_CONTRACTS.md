# Data contracts and temporal semantics

## Instrument and session keys (`src/bvmt/calendar.py`)
Use immutable `instrument_id` (ISIN where verified) plus `session_date`. Keep symbol/name mappings
as dated metadata (`InstrumentRecord`: `instrument_id,isin,symbol,valid_from,valid_to,listed_from,listed_to,market_segment,currency,source_document_id`).
An official-source-backed exchange calendar (`ExchangeSession`: `session_date,is_open,schedule_type,opens_at,closes_at,timezone,source_document_id`)
defines open sessions and publication/decision cutoffs in `Africa/Tunis`, without hardcoding unverified regular, Ramadan, or summer hours.
The Tunis Bourse Challenge simulator execution window (`09:00–14:15` in `configs/competition.json`) is modeled separately from the BVMT exchange calendar.
Observation coverage (`evaluate_coverage`) classifies every `(instrument_id, session_date)` into `traded`, `no_trade`, `suspended` (requires explicit `SuspensionRecord`), `holiday`, `missing_observation`, `stale_quote`, or `unlisted_or_delisted`.
The synthetic fixtures (`tests/fixtures/instrument_master.csv`, `tests/fixtures/exchange_calendar.csv`, `tests/fixtures/daily_bars.csv`) use demonstration dates only and prove no real calendar.

## Canonical CSV v0 (`--format canonical`, parser version `canonical_csv_v1`)
Required columns: `instrument_id,symbol,session_date,open,high,low,close,volume_shares,turnover_tnd,status,source_id,published_at,ingested_at`.
Prices and turnover use dot-decimal strings; volume is an integer share count. `status` is
`traded`/`no_trade`/`suspended`. Times are ISO-8601 with offsets (`published_at` may be empty when
missing/unknown; it is represented as `None`/`""` and never fabricated). The canonical parser
deliberately rejects French comma-decimal separators (`10,50`) and does not guess whether
`volume` means shares versus dinars.

## Explicit French BVMT CSV adapter (`--format french_bvmt`, parser version `french_bvmt_csv_v1`)
Accepts comma- or semicolon-delimited local historical BVMT exports with explicit columns:
- Required: `code_isin`, `valeur`, `seance`, `ouverture`, `plus_haut`, `plus_bas`, `cloture`, `quantite_negociee` (integer shares), `capitaux_tnd` (dinars).
- Optional: `statut` (`cotee`/`cotée`/`traded`, `non_cotee`/`non_cotée`/`aucune_transaction`/`no_trade`, `suspendue`/`suspendu`/`suspended`), `date_publication` (ISO-8601 with timezone, or blank when unknown).
- Dates (`seance`): ISO `YYYY-MM-DD` or French `DD/MM/YYYY` only; ambiguous formats (`YYYY/MM/DD`, `DD-MM-YYYY`) are quarantined.
- Numbers: French comma decimals (`10,800`) or dot decimals (`10.800`) with optional space grouping (`10 000,000`); mixed separators (`1.000,50`) or ambiguous unit columns (`volume`) are rejected.
- Positive OHLC are required for quoted bars; volume and turnover must be nonnegative.
- A traded bar must have positive volume and turnover. A no-trade/suspended bar must have zero volume/turnover; its retained reference prices are not execution opportunities.
- A suspended session with no usable quote needs a separate status record, not invented OHLC.
- Duplicates are rejected and quarantined into `rejections.json` with line number, raw row, and reason; revisions require an explicit revision table, not last-row-wins.

## Time and vintage
published_at: actual release time supported by a source, not the accounting period end.
ingested_at: when our workflow first received that version. The starter replay conservatively
requires BOTH to precede the cutoff. Future historical research may use a documented public
availability policy, but must not relabel recent scraping as historical ingestion.
A record cannot have ingestion before publication. Use separate effective_date,
observation_period and revision_id for fundamentals and macro releases.
Persist raw and adjusted prices separately. Any adjustment needs its action, factor, date,
and provenance. Do not retroactively leak future corporate actions into a backtest.

## Source registry
Each source needs id, URL/file identity, owner, allowed_access_method, permission_status,
redistribution_status, rate limit, fields, units, time semantics, and parser version.
Manual authorized CSV import is an acceptable first source. Unknown access permissions
block automated retrieval but not development against synthetic fixtures.

## Point-in-time entity/event join
Use the instrument mapping valid at the event timestamp. Policy stage may be rumor,
proposal, enacted, effective, withdrawn, or unknown. Confidence in extraction is not a
calibrated probability of positive returns. Evidence spans must resolve to stored bytes.

## Storage target
The starter uses small local CSV/JSON. docs/storage.sql defines the next DuckDB-oriented
layout. Large market tables should use partitioned Parquet with manifests; not a directory
full of hand-edited CSVs. Give every research run a dataset version and content hashes.
