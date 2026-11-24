# Data Source, Provenance & Competition Rule Specification (V2)

**Scope**: Formal inventory of local market/account datasets, competition rule blockers (`configs/competition.json`), and the 10-field PIT provenance contract required for `src/bvmt_v2/`.  
**Evidence Basis**: [r2_microstructure_results.json](../../research/experiments-v2/r2_microstructure_results.json), `data/v2_market/v2_market_manifest.json`, `bvmt-starter-kit/configs/competition.json`, and `M14_FUNDAMENTAL_DATA_GAPS.md`.

---

## 1. Current Local Dataset Provenance & Critical Gaps

| Dataset / Artifact | Observed Scope | Provenance Status | Critical Gaps & Risks |
|---|---|---|---|
| `data/v2_market/daily_bars.equity_only.csv` | `15,080` rows, `76` tokens (`75` ISINs), `202` sessions (`2026-01-02..2026-11-18`) | `EOD_UNVERIFIED_PUB_TIME` | **`15,080 / 15,080` (`100%`) have blank `published_at`**; `ingested_at` is batch-stamped (`2026-11-07` or `2026-11-19`). Strips `NB_TRANSACTION` (`echanges`), `bloc` volume/turnover, `vwap`, and BVMT `'H'/'B'` limit-reserved flags. |
| `data/v2_market/instrument_master.csv` | `76` rows | `OBSERVED` (with alias defect) | `TN0005700018` (`POULINA`) split into `POULINA_GROUP_HOLDING` & `POULINA_GP_HOLDING`, both `valid_to = ""`. Historical delistings/pre-2026 universe changes absent. |
| `data/v2_market/exchange_calendar.csv` | `202` open sessions (`2026-01-02..2026-11-18`) | `OBSERVED` (`Africa/Tunis`) | `opens_at` / `closes_at` blank (`observed_daily_unknown_hours`); requires explicit EOD cutoff convention (`15:00` or `17:00` Africa/Tunis) without fabricating exchange timestamps. |
| `TUNINDEX` Benchmark Series | `0` rows | **`UNAVAILABLE`** | No point-in-time `TUNINDEX` daily close CSV exists locally; market-relative beta/alpha vs official index cannot be computed without fetching `histo_indice`. |
| Corporate Actions Table | `0` rows | **`UNAVAILABLE`** | Zero ex-dividend dates/amounts, splits, or capital increases (`attribution gratuite` / `augmentation de capital`); raw price drops on ex-dates masquerade as negative returns. |
| PIT Financial Statements / Fundamentals | `0` rows (`document_chunks_file_exists = false`) | **`UNAVAILABLE`** | Zero quarterly indicators (`indicateurs trimestriels`), H1/FY financial statements, or CMF/BVMT communiqués with `published_at_utc`. Static 6-item `macro_events.py` is `UNVERIFIED_CATALOG`. |
| Pre-2026 Daily History (`2022–2025`) | `0` rows | **`UNAVAILABLE`** | Less than 11 months (`202` sessions) prevents multi-regime bull/bear testing, seasonality validation, and long-horizon walk-forward generalization. |
| `real_competition_ledger.json` + `snapshots/` | `11` snapshot JSONs (`Nov 7–12`) | `OBSERVED` (corrupted/stale active pointer) | `display_histo.aspx` missing after Nov 9 `09:13Z`; Nov 9 `12:01..12:04Z` DOM column shift (`VENDRE`); stale Nov 10 overwrite (`browser_sync_20261110_110702`) reverted Nov 12 `ext_1794476128406`. |

---

## 2. Competition Rule Audit (`configs/competition.json`)

Running `competition_blockers()` (`src/bvmt/rules.py`) against `bvmt-starter-kit/configs/competition.json` confirms:
- **Required Rule Categories**: `15`
- **Unverified Categories**: **`15 / 15`** (exit code `2`, `status = "blocked"`)
- **Total Attribute-Level Blockers**: **`72`**

### Breakdown of the 72 Blockers
1. **9 Fully `null` Categories (`9 × 6 = 54` blockers)** — missing `value`, `status != "verified"`, `source`, `evidence_locator`, `reviewed_by`, `reviewed_at`:
   - `edition`, `initial_cash_tnd`, `start_date`, `end_date`, `eligible_instruments`, `settlement_and_cash`, `corporate_actions`, `tick_and_lot_rules`, `automation_policy`.
2. **6 Partially Populated FAQ Categories (`6 × 3 = 18` blockers)** — `value`, `source`, and `evidence_locator` populated from participant-supplied `help.aspx` (captured `2026-11-05`), but missing `status == "verified"`, `reviewed_by`, and `reviewed_at`:
   - `scoring_and_final_valuation` (final valuation methodology unresolved; hourly recalc `11:00–15:00`),
   - `fees_and_taxes` (`0.50%` buy / `0.50%` sell),
   - `execution_matching` (`09:00–14:15` Tunis; minimum activity threshold & 1-week calendar-vs-trading expiry unresolved),
   - `allowed_order_types` (`market`, `limit`, buy/sell, cancellable),
   - `position_and_sector_limits` (`10%` max single-stock weight; calculation timing & pending-order treatment unresolved),
   - `short_selling_and_leverage` (no shorting, no leverage).

**V2 Policy**: Until human sign-off resolves these 72 blockers (especially `T+0` vs `T+3` settlement, 1-week expiry convention, minimum trading threshold, and final valuation of suspended stocks), `CompetitionEngine` must label all competition-rule simulations as `UNVERIFIED_RULE_ASSUMPTIONS` and keep `execution_enabled = False`.

---

## 3. Mandatory 10-Field Observation Provenance & 5-State Truth Model (`ADR-002` / `ADR-003`)

Every market bar loaded by `bvmt_v2.market_data` must preserve all 10 provenance fields without backfilling unknowns:
1. `event_time` (`session_date` or `None`)
2. `exchange_session` (`YYYY-MM-DD`, Africa/Tunis)
3. `source_publication_time` (`None` when omitted by official BVMT NDJSON — **never fabricated**)
4. `first_observed_at` (earliest UTC capture timestamp)
5. `retrieved_at` (UTC fetch timestamp)
6. `ingested_at` (UTC canonical CSV write timestamp)
7. `validated_at` (UTC schema validation timestamp)
8. `source_id` (`official-bvmt-full-2026`, `tunis_stockexchange_equities_2026`, etc.)
9. `source_hash` (SHA-256 prefix of source artifact)
10. `data_quality_status` (`VERIFIED_PIT` | `EOD_UNVERIFIED_PUB_TIME` | `STALE_NO_TRADE` | `SUSPENDED` | `SYNTHETIC_FIXTURE` | `MISSING`)

### Strict Separation of Quotes & Values
- `historical_eod_close_tnd` is tagged `OBSERVED` (for historical sessions where `ingested_at <= cutoff`), whereas `current_executable_quote_tnd` is **`UNAVAILABLE`** in EOD-only mode — never silently equated to yesterday's close.
- Every numeric output uses `Decimal` strings (`0.001` TND rounding) inside a `ProvenanceValue` envelope (`OBSERVED` | `CALCULATED` | `SIMULATED` | `UNVERIFIED` | `UNAVAILABLE`).

---

## 4. Prioritized External Data Acquisition Roadmap (`P0` / `P1`)

| Priority | Target Source | Required Fields to Unblock Research | PIT & Integrity Rule |
|---|---|---|---|
| **`P0-1`** | BVMT Official (`bvmt.com.tn`) `histo_cotation` + `histo_indice` (**2022–2025** + full 2026) | Multi-year OHLCV, `TUNINDEX`, `echanges` (trade count), `quantiteBloc`/`capitauxBloc`, `vwap`, `'H'/'B'` indicator | Verify TOS/robots first; store raw SHA-256 archives; stamp `source_publication_time = None` if absent or official EOD posting clock only. |
| **`P0-2`** | BVMT / CMF *Avis de Bourse* & *Opérations sur titres* | Ex-dividend dates & TND payouts, splits, free shares, rights detachments, suspensions | Compute PIT total-return series only on/after `ex_date`; never leak future splits into past signals. |
| **`P0-3`** | Tunis Bourse Challenge `display_histo.aspx` + `reglement.aspx` sign-off | Full transaction history (resolving Nov 9 `223529` & post-Nov-12 trades) + clearing 72 rule blockers | Read-only export; human sign-off updates `configs/competition.json` with `reviewed_by` & `reviewed_at`. |
| **`P1-1`** | CMF (`cmf.tn`) & BVMT Issuer Filings | Quarterly revenue indicators, H1/FY financial statements, profit warnings, AGM dividends | Stamp `published_at_utc` strictly from CMF/BVMT **posting date**, never fiscal `period_end_date`. |
| **`P1-2`** | BCT (`bct.gov.tn`) & INS (`ins.tn`) + JORT | Policy rate (`Taux directeur`), TMM, FX reserves, CPI, Finance Law sector tariffs | Store in `events_pit.parquet` conforming to `schemas/event.schema.json`; `BVMT_ALLOW_LIVE_LLM=0` default unless approved. |
