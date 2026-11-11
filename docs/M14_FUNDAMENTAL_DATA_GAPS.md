# Milestone 14 — Fundamental, Event & Microstructure Data Gaps (`Task G6`)

- **Author**: Gemini Quantitative Research Mission (Google Antigravity IDE; reproducible read-only audit against `bvmt-starter-kit` @ `6f0b64d`)
- **Primary Conclusion**: Price-and-volume models alone cannot capture regime changes driven by earnings releases, dividend announcements, capital increases, BCT policy actions, or tax/tariff shifts because **zero point-in-time (PIT) fundamental statements, corporate actions, dividend tables, or processed filing text chunks exist locally**.

---

## 1. Current Local Dataset Inventory (`bvmt_official_2026`)

Directly observed in `bvmt-starter-kit/data/processed/bvmt_official_2026` and `bvmt-starter-kit/data/staging`:

| Domain | Local File / Artifact | Observed State | Gap / Integrity Issue |
| :--- | :--- | :--- | :--- |
| **Canonical Daily Bars** | `daily_bars.canonical.csv` | `17,110` rows across `196` open sessions (`2026-01-02..2026-11-10`) | **`17,110 / 17,110` (`100%`) have blank `published_at`**; drops `NB_TRANSACTION` (`echanges`), `indicateur` (`H`/`B`), `PER`, `PBV`, `DividendYield`, `CapitalisationBoursiereMD`, `vwap`. |
| **Instrument Master** | `instrument_master.csv` | `76` rows | **Split identity on Challenge ISIN `TN0005700018`**: both `POULINA_GROUP_HOLDING` (`valid_from=2026-01-02`, `valid_to=null`) and `POULINA_GP_HOLDING` (`valid_from=2026-04-10`, `valid_to=null`) coexist, breaking lookback windows across April–June. Raw historical/NDJSON spans `572` distinct tokens across raw exports vs `76` mapped masters. |
| **Exchange Calendar** | `exchange_calendar.csv` | `196` open sessions | Requires UTC-aware `closes_at` alignment per session; `holding_period.py` falls back to `datetime.min` when `closes_at` is `None`. |
| **Raw Exchange Rejections** | `rejections.json` (`rejections.json#688` etc.) | Preserves `H` / `B` status rows | E.g., `2026-09-22` ICF (`indicateur="B"`, `open=high=143.6`, `close=135.07`, `vol=31`, `turnover=4451.6`, `per=23.700`, `pbv=2.559`, `dividendYield=2.369`, `capitalisationBoursiereMD=283.647`, `titresEmis=2100000`, `flottantReel=17.097`). |
| **Staging Market Cap Recap** | `data/staging/market_recap_capital.ndjson` | Present locally | Not ingested into canonical equity tables or liquidity/free-float risk checks. |
| **Verified Competition Rules** | `configs/competition.json` | `15` fields total | **All `15 / 15` fields remain `"status": "unverified"`** (`null` values); rules-check returns exit code `2`. |
| **Macro & Event Catalog** | `src/bvmt/macro_events.py` | **6 hardcoded Python dicts** | Static fixture catalog; no external PIT ingestion pipeline; alias lookups fail if `include_aliases=False`. |
| **Document / Filing Chunks** | `data/document_index/document_chunks.json` | **`document_chunks_file_exists = false`** | Zero local CMF/BVMT communiqués, H1/annual financial statements, AGM dividend resolutions, or quarterly indicators (`indicateurs trimestriels`). |
| **Corporate Actions** | *(absent)* | **0 rows** | No split/bonus-issue/rights-issue/ex-dividend adjustment table; unadjusted price drops on ex-dividend or nominal split dates alias as negative momentum or false drawdowns. |
| **Multi-Year History** | `2026-01-02..2026-11-10` only | `< 11 months` (`196` sessions) | Zero prior-year (2023–2025) baseline for seasonal earnings cycles, regime bull/bear shifts, or cross-year walk-forward splits. |

---

## 2. Underutilized Fields Already Present in Local Raw BVMT Payloads

Before scraping any new source, official BVMT staging/rejection records (`tunis_stockexchange_equities_2026.ndjson` & `rejections.json`) **already contain** daily issuer-level fields currently discarded by canonical normalization into `daily_bars.canonical.csv`:

1. **Trade Execution Microstructure**:
   - `echanges` (`NB_TRANSACTION`): distinguishes 1 odd-lot trade of 2 shares (`ICF` `2026-11-06`: `2` shares / `268.450 TND`) vs broad 20+ print accumulation.
   - `echangeBloc`, `quantiteBloc`, `capitauxBloc`: separates négociations de bloc (off-book crosses that inflate daily turnover without accessible order-book liquidity) from continuous order-book depth.
   - `indicateur` (`"H"`, `"B"`, `""`): distinguishes exchange-regulated limit/reserved sessions from data-corruption failures.
   - `vwap`: mitigates closing-auction print manipulation (critical on Tunis Bourse thin tails).
2. **Share & Free-Float Denominators**:
   - `titresEmis`, `titresAdmis`, `flottantReel`, `capitalisationBoursiereMD`, `capitalisationFlottanteTunindexMD`.
3. **BVMT-Published Valuation Snapshots**:
   - `per`, `pbv`, `dividendYield` *(must carry a strict PIT disclaimer: reflects whichever denominator BVMT's daily feed used on `dateSeance` and does **not** establish the underlying accounting publication timestamp until cross-referenced with CMF financial statements)*.

---

## 3. Priority External PIT Data Requirements & Compliant Acquisition Specifications

Every external source MUST respect `AGENTS.md`: **official/public primary sources only, explicit license/TOS review before crawling, zero credential harvesting, `network_enabled: false` by default, raw byte archival with SHA-256 provenance, and `available_at_utc` (`available_at >= event_date`) PIT stamping**.

### P0 — Mandatory Before Any Live Model Upgrade or Multi-Year Validation

| Priority | Primary Source | Target Content | Legal / Technical Access Rules |
| :--- | :--- | :--- | :--- |
| **P0-1** | **BVMT Official (`bvmt.com.tn`) Historical Archives** | Official daily `histo_cotation` + `histo_indice` for **2022–2025** + complete 2026 ISIN-keyed normalization (fixing `TN0005700018` alias split + keeping `echanges`, `bloc`, `vwap`, `indicateur`). | Check BVMT terms of use & robots policy via Codex/user approval before download; cache immutable raw ZIP/CSV bundles under `data/raw/` with SHA-256 manifest + EOD session timestamp (`15:00 Africa/Tunis` when published). |
| **P0-2** | **BVMT / CMF Corporate Actions (`avis et décisions`)** | Ex-dividend dates & cash amounts (TND), stock splits, free share grants (`attribution gratuite`), capital increases, trading suspensions/halted dates, Challenge universe effective membership dates. | Ingest official BVMT *Avis de Bourse* / *Opérations sur titres*; compute PIT total-return index alongside clean unadjusted price so ex-dividend drops never trigger false negative momentum or stop alerts. |
| **P0-3** | **Tunis Bourse Challenge Official Regulation (`configs/competition.json`)** | Exact rules for all **15 currently `null` fields** (fee schedule, eligible universe rules, short-selling ban confirmation, initial/max position weights, concentration drift vs order-time cap, settlement `T+3`, minimum order size, competition end date). | Manual user/official PDF ingestion into `data/raw/tunisbourse_challenge_reglement/` with SHA-256 citation per field; exit code `0` required from `bvmt rules-check` before removing compliance blocker. |

### P1 — High-Value Fundamental & Event Catalysts (Missed-Opportunity Explanation Without Hindsight)

| Priority | Primary Source | Target Content | PIT & Anti-Leakage Discipline |
| :--- | :--- | :--- | :--- |
| **P1-1** | **CMF (`cmf.tn`) & BVMT Listed-Company Disclosures** | *Indicateurs d'activité trimestriels* (Q1/Q2/Q3/Q4), *États financiers semestriels & annuels* (revenue, EBIT, net income, debt, equity, cash flow), AGM communiqués, statutory auditor notes, profit warnings. | Store raw French/Arabic PDFs + SHA-256; extract schema-validated fields; **stamp `published_at_utc` from CMF/BVMT posting timestamp — NEVER the fiscal period-end date (`2026-06-30` H1 cannot be visible until the August/September filing date)**. |
| **P1-2** | **BCT (`bct.gov.tn`) & INS (`ins.tn`) Macro Releases** | Policy rate (`Taux directeur`), TMM / interbank liquidity, FX reserves & USD/EUR-TND rates, monthly CPI inflation, sector export/import & chemical/phosphate/industrial production indices (directly relevant to exporters like **ICF**, industrials, auto importers). | Replace the 6-item static Python catalog in `macro_events.py` with a versioned JSON/Parquet store (`data/processed/events_pit.parquet`) conforming to `schemas/event.schema.json`. Each record requires `source_url`, `published_at_utc`, `sha256`, `affected_isins`, `confidence`, and `verification_status`. |
| **P1-3** | **Official Gazette / Finance Laws (`JORT`, Ministry of Finance)** | Sector-specific corporate surtaxes, customs tariff revisions (automotive quotas for `STA`/`ARTES`/`NAKL`/`CITY`, energy/industrial subsidies, banking levies). | Deterministic rule mapping by ISIN & BVMT sector (`mapping_emetteur.json`); optional offline or user-approved LLM extraction strictly under `BVMT_ALLOW_LIVE_LLM=0` default unless explicitly approved. |

---

## 4. Proposed Point-in-Time Canonical Schemas

### 4.1 `instrument_aliases_pit.csv` / Normalized `instrument_master.csv`
Every canonical security must key internally on **`verified_isin`** (e.g., `TN0005700018` for Poulina), storing an effective-dated `alias_token` table:
- `isin` (`str`, primary invariant key)
- `canonical_instrument_id` (`str`, e.g., `POULINA_GP_HOLDING`)
- `alias_symbol` (`str`, e.g., `POULINA GROUP HOLDING`, `PGH`)
- `effective_from` (`date`), `effective_to` (`date | None`)
- `challenge_eligible_from` (`date | None`), `challenge_eligible_to` (`date | None`)
- **Rule**: When computing rolling 20s/60s/252s price & turnover windows, resolve all bars sharing `isin` in chronological order without gaps across token renames.

### 4.2 `corporate_actions_pit.csv`
- `action_id`, `isin`, `canonical_instrument_id`
- `action_type` (`CASH_DIVIDEND | BONUS_SHARES | SPLIT | RIGHTS_ISSUE | SUSPENSION`)
- `declaration_date` (`date`), `ex_date` (`date`), `payment_date` (`date | None`)
- `cash_amount_tnd` (`Decimal | None`), `ratio_num` (`Decimal`), `ratio_den` (`Decimal`)
- `adjustment_factor` (`Decimal`, applied strictly to historical bars prior to `ex_date` only inside total-return series as of `decision_date >= ex_date`)
- `available_at_utc` (`datetime`, UTC-aware), `source_sha256`

### 4.3 `fundamentals_pit.parquet`
- `filing_id`, `isin`, `canonical_instrument_id`
- `fiscal_period` (e.g., `2026-Q3`, `2026-H1`, `2025-FY`), `period_end_date` (`date`)
- **`published_at_utc` (`datetime`, mandatory PIT gate: rows with `published_at_utc > cutoff_utc` are invisibly excluded)**
- `revenue_tnd`, `operating_income_tnd`, `net_income_tnd`, `shareholders_equity_tnd`, `net_debt_tnd`, `shares_outstanding`
- `yoy_revenue_growth_pct`, `ttm_pe`, `pb_ratio`, `dividend_yield_pct` (computed **exclusively** using PIT price as of decision cutoff divided by PIT-published earnings/equity/dividends)
- `filing_age_days`, `extraction_method` (`MANUAL_VERIFIED | STRUCTURED_PARSER | LLM_AUDITED`), `source_sha256`

### 4.4 `orderbook_microstructure_bars.parquet` (Extension of Canonical Daily Bars)
Retain already-captured BVMT raw fields currently lost in canonical export:
- `trade_count` (`echanges`), `bloc_volume_shares`, `bloc_turnover_tnd`, `orderbook_volume_shares` (`quantites - quantiteBloc`), `orderbook_turnover_tnd` (`capitaux - capitauxBloc`), `vwap`, `bvmt_indicator` (`"" | "H" | "B" | "S"`), `shares_listed`, `free_float_pct`, `published_at_utc` (stamped monotonically from official BVMT session publication clock).
