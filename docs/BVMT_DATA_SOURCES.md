# BVMT Historical Market-Data & Disclosure Sources

## 1. Purpose and Scope
This document evaluates candidate historical data sources for the **Bourse des Valeurs Mobilières de Tunis (BVMT)** across the 9 required categories:
1. Daily OHLCV prices
2. Daily trading volume (shares) and turnover (`capitaux_tnd`)
3. Historical listed companies and ISIN identifiers
4. Trading calendars, holidays, and suspensions
5. Corporate actions, dividends, splits, and capital increases
6. Quarterly company activity indicators (*Indicateurs d'activité trimestriels*)
7. Annual and semiannual financial statements (*États financiers*)
8. Company disclosures and market announcements (*Communiqués*)
9. Historical benchmark index values (`TUNINDEX`, `TUNINDEX20`)

Per `rules.md`, we distinguish **source access approval** from **redistribution permission**, never scrape authenticated pages or bypass access restrictions, and never fabricate missing historical observations.

---

## 2. Candidate Source Comparison Matrix

| Source ID | Source Name & URL | Origin | Categories Covered | Historical Coverage | Format & Download Method | Update Frequency | Licensing & Automated Access | Suitability for Point-in-Time (PIT) Backtesting |
|---|---|---|---|---|---|---|---|---|
| **BVMT_HIST_ZIP** | **Bourse de Tunis — Historique des cotations** (`bvmt.com.tn` / `tunis-stockexchange.com` Market Watch > Historique) | Official Exchange | (1) OHLC, (2) Volume shares & Turnover TND, (3) ISIN/Ticker/Group, (9) Indices | Multi-year annual/daily archives (`histo_cotation_YYYY.zip` / `.csv` / `.txt`) | Manual download of annual/daily tabular files (fixed-width `.txt` or semicolon `.csv`) | Daily (end-of-session) | Public official publication for consultation/research; automated scraping unverified -> **use manual local download + `bvmt import-csv`** | **High** for raw execution prices, volume, turnover, and trading groups (e.g., Group 11 *Continu* vs Group 12 *Fixing*). Lacks intraday publication timestamps (requires conservative EOD availability policy). |
| **BVMT_PHYSIO_BULLETIN** | **Bourse de Tunis — Physionomie Boursière & Bulletins Officiels** (`bvmt.com.tn` / `tunis-stockexchange.com`) | Official Exchange | (3) Listed universe, (4) Calendar/holidays/suspensions, (5) Corporate actions/dividends, (8) Market notices, (9) TUNINDEX | Daily and monthly archives | PDF bulletins and HTML notices | Daily (session close) | Public official publication; manual download of PDFs/notices | **High** as authoritative provenance for official calendar (`ExchangeSession`), suspensions (`SuspensionRecord`), and ex-dividend/capital-increase dates. |
| **CMF_OFFICIAL** | **Conseil du Marché Financier (CMF)** (`cmf.tn` — *Émetteurs*, *Informations financières*, *Bulletin Officiel*) | Official Regulator | (4) Official suspension/resumption decisions, (5) Capital operations/prospectuses, (6) Quarterly activity indicators, (7) Annual/semiannual financial statements, (8) Regulatory disclosures | Multi-year statutory filings (Article 21 of Law 94-117 requires quarterly indicators within 20 days of quarter-end) | PDF filings and HTML/PDF *Bulletin Officiel du CMF* | Daily / Statutory filing schedule | Public regulatory disclosures; manual download of target company PDFs into `data/raw/` | **Highest** for point-in-time fundamentals and corporate events because CMF filings and bulletins carry explicit publication/filing dates (`published_at`), preventing look-ahead bias on earnings and quarterly revenue. |
| **MAC_SA / BROKER_RES** | **Licensed Tunisian Intermediaries** (e.g., MAC SA, Tunisie Valeurs, Amen Invest public research portals) | Regulated Third-Party (Intermediaries) | (5) Dividend/split summaries, (6) Quarterly indicator summaries, (7) Financial ratios | Varies by portal (typically 3–5 years) | Web tables / PDF research notes | Periodic / Event-driven | Proprietary copyright; read-only human reference only; no automated scraping | **Low–Medium** for primary PIT backtesting (often restates historical figures or omits exact filing timestamps); useful only for cross-checking official CMF/BVMT extractions. |
| **ILBOURSA / AGGREGATORS** | **Third-Party Financial Portals** (`ilboursa.com`, `investing.com`, `tradingview.com`) | Third-Party Aggregator | (1) OHLCV, (5) Dividends, (8) News articles, (9) TUNINDEX | Multi-year for currently listed stocks | Web pages / account-gated CSV exports | Intraday / Daily | Terms of Service restrict automated scraping and redistribution; some exports require user login | **Low for primary backtesting** due to survivorship bias (delisted stocks often dropped), unannounced retroactive price adjustments, and ToS restrictions. Do not scrape. |

---

## 3. Detailed Assessment by Data Category

### 3.1 Daily OHLCV, Volume (Shares), Turnover (TND), and Listing Group
- **Primary Source**: Official BVMT Historical Quotations (`BVMT_HIST_ZIP`).
- **Structure**: Official BVMT historical files provide `SEANCE` (session date), `GROUPE` (trading group, e.g., `11` for Continuous market, `12` for Fixing, `99` for secondary/off-market), `CODE` (ISIN or BVMT code), `VALEUR` (symbol/name), `OUVERTURE`, `PLUS_HAUT`, `PLUS_BAS`, `CLOTURE`, `QUANTITE_NEGOCIEE` (integer shares), `CAPITAUX` (turnover in TND), and `NB_TRANSACTION` (trade count).
- **Why this matters for the competition**:
  - `reglement.aspx` states: *"Seules les actions cotées au mode Continu du Marché Principal de la Bourse, sont éligibles dans le présent challenge."*
  - Official BVMT files explicitly identify the quotation group (`GROUPE`), allowing deterministic point-in-time filtering of *Continu du Marché Principal* equities and explicit identification of zero-volume (`QUANTITE_NEGOCIEE = 0`) sessions.
- **Availability Convention**: Because historical EOD files record only `session_date` without an exact publication timestamp, `docs/DATA_CONTRACTS.md` and `rules.md` require a documented conservative availability policy (e.g., setting `available_at` to `16:00:00 Africa/Tunis` on `session_date` for historical research, while recording actual `ingested_at` in provenance).

### 3.2 Historical Instrument Master, Delistings, and Exchange Calendar
- **Primary Source**: Official BVMT Historical Quotations (`BVMT_HIST_ZIP`) cross-referenced with BVMT *Physionomie Boursière* (`BVMT_PHYSIO_BULLETIN`) and CMF notices (`CMF_OFFICIAL`).
- **Survivorship Bias Mitigation**: Because annual BVMT historical archive files (`histo_cotation_YYYY`) contain all securities quoted during year `YYYY` (including companies subsequently delisted or suspended), building the `InstrumentRecord` master directly from the union of annual BVMT archives preserves delisted securities and historical symbol/group changes (`valid_from`..`valid_to`).
- **Exchange Calendar & Suspensions**: Open trading sessions (`is_open = true`) are empirically observed across the market-wide BVMT session files and verified against official BVMT holiday/schedule notices (`schedule_type`: regular, Ramadan, summer). Instrument-specific suspensions require a CMF/BVMT notice (`SuspensionRecord`).

### 3.3 Corporate Actions (Dividends, Splits, Rights/Subscriptions)
- **Primary Source**: Official BVMT *Avis / Décisions* and CMF *Bulletin Officiel*.
- **Point-in-Time Handling**: Raw execution prices (`open`, `high`, `low`, `close`) are stored unadjusted in `daily_bars.canonical.csv`. Corporate actions (cash dividends, stock dividends *attribution*, rights issues *souscription*, stock splits) are recorded in a separate point-in-time table with `announcement_at`, `ex_date`, and `payment_date` so that:
  1. Signals can compute total-return / split-adjusted lookbacks using only corporate actions whose `ex_date <= decision_date`.
  2. The execution ledger (`T05`) always trades at raw unadjusted prices and credits cash dividends/rights on `ex_date`/`payment_date` per competition rules.

### 3.4 Quarterly Activity Indicators, Financial Statements, and Disclosures
- **Primary Source**: Official CMF Issuer Filings (`CMF_OFFICIAL`) and BVMT *Communiqués des sociétés*.
- **Point-in-Time Advantage**: Tunisian listed companies must file quarterly activity indicators (*Indicateurs d'activité trimestriels*) within 20 days of quarter close, plus semiannual and annual financial statements. Each PDF/communique published on CMF/BVMT carries a publication date (`published_at`).
- **Ingestion Workflow**: Human researcher downloads authorized PDF/text disclosures for eligible *Continu du Marché Principal* companies -> snapshots raw file via `snapshot_local_file` -> extracts structured metrics/events using the offline-cached LLM workflow (`Priority C`) + deterministic schema validation -> human reviewer verifies evidence spans before backtest inclusion.

## 5. Exact Manual Download & Local Ingestion Instructions (Priority 3)

Until actual historical files are manually downloaded, snapshotted, and validated via the steps below, **real-data backtesting is NOT operational** (all repository tests run on labeled synthetic fixtures).

### 5.1 Official URLs & Required Files
1. **Official BVMT Historical Quotations (`BVMT_HIST_ZIP`)**:
   - **Portal URL**: `https://www.tunis-stockexchange.com/` (or legacy `http://www.bvmt.com.tn/fr/historique-cotations`) -> **Market Watch > Historique**.
   - **Recommended Date Range**: **January 1, 2022 – Present (2022, 2023, 2024, 2025, 2026)** (~5 years / ~1,200 open sessions, sufficient for 60-session lookbacks + multi-fold walk-forward validation).
   - **Required Format**: Annual or period CSV/TXT quotation exports (`histo_cotation_2022.csv` .. `histo_cotation_2026.csv`). Ensure the export contains:
     `code_isin`, `valeur`, `seance` (`DD/MM/YYYY` or `YYYY-MM-DD`), `ouverture`, `plus_haut`, `plus_bas`, `cloture`, `quantite_negociee` (integer shares), `capitaux_tnd` (dinar turnover), and optional `statut` / `date_publication`.
2. **Official Exchange Calendar & Suspension Notices (`BVMT_PHYSIO_BULLETIN`)**:
   - **Portal URL**: `https://www.tunis-stockexchange.com/` -> **Publications > Physionomie Boursière / Avis et Décisions**.
   - **Required Files**: Official holiday/trading-hour notices (`Africa/Tunis` regular, Ramadan, and summer schedules) formatted into `data/processed/reference/exchange_calendar.csv` and `instrument_master.csv`.
3. **Official CMF Financial Statements & Activity Indicators (`CMF_OFFICIAL`)**:
   - **Portal URL**: `https://www.cmf.tn/` -> **Émetteurs > Informations financières > Indicateurs d'activité trimestriels / États financiers** and **Bulletin Officiel du CMF**.
   - **Target Subset for Pilot**: Download 15–20 recent PDF/text disclosures (Q1–Q3 2026 activity indicators, FY 2025 annual financial statements, and dividend/capital-increase communiqués) for liquid *Continu du Marché Principal* issuers.

### 5.2 Expected Local Directory Structure
Place manually downloaded files in a local staging folder (e.g., `data/staging/`), which is never committed to Git:
```text
bvmt-starter-kit/
├── data/
│   ├── staging/                        # Place manually downloaded official files here
│   │   ├── bvmt_histo_2022_2026.csv
│   │   ├── instrument_master_bvmt.csv
│   │   ├── exchange_calendar_bvmt.csv
│   │   └── cmf_filings/
│   │       └── <issuer>_<date>_<type>.txt
│   ├── raw/                            # Immutable content-addressed SHA-256 snapshots (.bin + .json)
│   └── processed/
│       ├── bvmt_histo_2022_2026/
│       │   ├── daily_bars.canonical.csv
│       │   ├── rejections.json
│       │   └── manifest.json
│       ├── document_index/
│       │   ├── document_chunks.json
│       │   └── chunk_embeddings_qwen3_7.json
│       └── llm_cache/
```

### 5.3 Exact Validation & Import Commands
1. **Ingest & Snapshot French BVMT Historical Quotations**:
   ```powershell
   uv run bvmt import-csv data/staging/bvmt_histo_2022_2026.csv `
     --source-id bvmt_official_histo_2022_2026 `
     --format french_bvmt `
     --permission-status authorized_local_import `
     --retrieved-at 2026-11-05T18:30:00+01:00 `
     --raw-dir data/raw `
     --output-dir data/processed/bvmt_histo_2022_2026
   ```
2. **Verify Instrument Master, Calendar & Observation Coverage**:
   ```powershell
   uv run bvmt coverage-check `
     --instruments data/staging/instrument_master_bvmt.csv `
     --calendar data/staging/exchange_calendar_bvmt.csv `
     --bars data/processed/bvmt_histo_2022_2026/daily_bars.canonical.csv `
     --output artifacts/real-coverage-report.json
   ```
   *Validation Gate*: Inspect `artifacts/real-coverage-report.json` and `data/processed/bvmt_histo_2022_2026/rejections.json`. Ensure `duplicated_historical_symbols == []`, `listing_and_delisting_inconsistencies == []`, and `unverified_suspensions == []`.
3. **Run Session-Aware Baseline Ranking (`T04`)**:
   ```powershell
   uv run bvmt session-rank `
     --instruments data/staging/instrument_master_bvmt.csv `
     --calendar data/staging/exchange_calendar_bvmt.csv `
     --bars data/processed/bvmt_histo_2022_2026/daily_bars.canonical.csv `
     --cutoff 2026-11-05T17:00:00+01:00 `
     --output artifacts/session-baseline-report.json
   ```



## C2 official historical adapter and C3 research foundation

The Python import API accepts `input_format="bvmt_histo_cotation"` through
`import_local_csv` or its additive alias `import_market_csv`, using the existing
source_id, permission_status, retrieved_at, raw_dir and output_dir arguments.
The shared CLI still exposes its existing format choices; adding a CLI choice
requires integration review. The existing `canonical` and `french_bvmt` formats
retain their strict column contracts.

| Official column | Parsed destination |
|---|---|
| SEANCE | session_date; DD/MM/YYYY or ISO date |
| VALEUR, else SYMBOLE / TICKER / CODE | instrument_id, uppercase, non-identifier runs replaced by underscore; symbol preserves uppercase source label |
| CODE | optional DailyBar.isin (source code, not asserted to be a validated ISIN) |
| OUVERTURE / PLUS_HAUT / PLUS_BAS / CLOTURE | Decimal open / high / low / close |
| QUANTITE_NEGOCIEE | integer volume_shares |
| CAPITAUX | Decimal turnover_tnd |
| GROUPE / NB_TRANSACTION / IND_RES | retained in raw source; no eligibility inference |

Headers are case-insensitive and padded fields are stripped. Semicolon or comma
CSV delimiters are accepted; French comma decimals in comma-delimited files must
be CSV-quoted. UTF-8 with optional BOM is supported. Fixed-width text and other
encodings require an explicit conversion with separate provenance.

For zero-volume rows with positive CLOTURE, zero open/high/low values are replaced
by that row's reference close. These rows become `no_trade`, increment
`untraded_or_suspended_count`, and cannot execute. This does not establish an
official suspension. Negative/invalid prices, inconsistent bounds, nonzero turnover
on no-trade rows, and duplicate instrument/session rows are quarantined. No missing
sessions are fabricated. Name normalization collisions also trigger duplicate
rejection; dated instrument identity still needs a reviewed master.

Each import saves byte-identical `raw_source.csv`, SHA-256 in `quality_report.json`,
accepted instrument count and first/last session, and `instrument_codes.json` so
source CODE survives without changing the shared canonical CSV columns. Existing
content-addressed snapshots, rejection reports and manifests remain available;
differing output artifacts are never silently overwritten. `published_at` remains
unknown for historical date-only rows; reference close is never an assumed intraday
publication timestamp.

The additive `run_historical_backtest` API is a research-conservative foundation,
with integer shares, Decimal cash/prices/fees, 0.001 TND half-up cash rounding,
strictly later-session fills, shared volume capacity, adverse slippage constrained
to the observed bar, limits, cash/position caps, no shorts, session-aged carry and
expiry. Sell requests above holdings fill only available shares; any remainder
may carry and eventually be rejected/expire. Terminal sample residuals expire.
Pending status is PARTIALLY_FILLED once some shares have executed. Filled count counts final fully filled orders; partial count counts orders that
experienced a partial fill, including orders later completed, rather than fill events.
Drawdown is a positive percentage from the running equity peak including initial
cash; turnover is gross filled notional divided by initial equity.

The cash benchmark is constant; equal-weight allocates initial whole-share sleeves
for the supplied static universe at the first session open, with the same fees,
slippage and volume cap. Uninvestable sleeves stay cash. It does not rebalance.
Latest known closes value holdings across missing bars, which can understate risk.
Provide `execution.TradingCalendar(tuple_of_ExchangeSession)` for verified open
sessions, including sessions with no bars. Without it only observed market dates
are counted; no weekday calendar is invented. `next_typical` is an explicitly
hypothetical next-session HLC/3 fill model, not an intraday execution guarantee.

Limitations: static eligibility set/universe (survivorship risk), stale valuation
marks, immediate settlement, no corporate actions/dividends, auction priority,
tick/lot rules, cash reservation, data revision manifest, ledger integration or
walk-forward evaluation. Signals must already satisfy their publication cutoffs.
Config hash covers canonical config JSON only. Synthetic tests verify mechanics,
not historical profitability or competition-exact fidelity.

### Verification evidence (2026-11-06)

Shared environment: `C:\Users\Thinkcenter\Desktop\BVMT\bvmt-starter-kit\.venv\Scripts`;
`PYTHONPATH=src`, `BVMT_ALLOW_LIVE_LLM=0` throughout. Repository gate
`scripts/check.py` passed: 30 files formatted, lint clean, 13 source modules typed,
10 local skills validated, **125 tests passed** (25.43 seconds). No live model calls.
The separately requested `mypy src tests --cache-dir artifacts/mypy-cache`
failed with **153 errors across 11 test files**, chiefly absent test annotations;
this broader check is not the repository's source-only mypy gate. Unowned test
files were preserved. This is not a claim that the broader check is green.

Pytest's Windows mode-0700 temporary directories are inaccessible under the
sandbox token. The successful gate used this process-only wrapper; it substitutes
normal inherited directory permissions, an isolated artifact temp path, and disables
pytest's cache. It does not alter tests, assertions or application behavior:

```powershell
$env:PYTHONPATH='src'
$env:BVMT_ALLOW_LIVE_LLM='0'
@'
import runpy
import subprocess
patch = '''import os, runpy
original = os.mkdir
os.mkdir = lambda path, mode=511, *, dir_fd=None: original(path, 511 if mode == 448 else mode, dir_fd=dir_fd)
runpy.run_module("pytest", run_name="__main__")
'''
original_run = subprocess.run
def sandbox_run(command, **kwargs):
    if command[1:3] == ['-m', 'pytest']:
        command = [command[0], '-c', patch, *command[3:], '--basetemp=artifacts/codex-gate-final2', '-p', 'no:cacheprovider']
    return original_run(command, **kwargs)
subprocess.run = sandbox_run
runpy.run_path('scripts/check.py', run_name='__main__')
'@ | C:\Users\Thinkcenter\Desktop\BVMT\bvmt-starter-kit\.venv\Scripts\python.exe -
```

Integration follow-up: expose the new CSV format in the shared CLI, review dated
universe and corporate-action contracts, and address test-suite typing separately.
`docs/STATE.md` and shared task files were intentionally left untouched under the
explicit workstream ownership restriction.

Delivery blocker: staging and commit failed because Git could not create
`bvmt-starter-kit/.git/worktrees/bvmt-codex-research/index.lock` (permission denied).
`git push origin codex/data-research` also failed to connect to GitHub through the
configured proxy. No new commit was created. An orchestrator with the required
filesystem/network access must stage the nine owned files, then run:

```powershell
git commit -m "feat(codex): complete C1 Alibaba audit, C2 official BVMT ingestion, and C3 backtest engine"
git push origin codex/data-research
```
