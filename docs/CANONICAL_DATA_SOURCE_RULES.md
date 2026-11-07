# Canonical Data-Source Selection Rules & Phase 0 State Resolution

## 1. Phase 0 Root-Cause Verification

Before building the modern Next.js + FastAPI interface, we inspected the live workspace state on disk (`data/portfolio/` and `data/processed/bvmt_official_2026/`) and verified:

1. **Latest Authenticated Browser Snapshot (`sync_20261107_122006.json`)**:
   - File: `data/portfolio/snapshots/sync_20261107_122006.json`
   - Retrieved at: `2026-11-07T12:20:06.833200+00:00`
   - Portfolio total: `50,000.75 TND`
   - Available cash (`Liquidités`): `49,608.05 TND`
   - Holding: `BH BANK` (`BH` / `223375`), `30` shares, acquisition price `13.065 TND`, acquisition amount `391.95 TND`, displayed latest price `13.09 TND`, current market value `392.70 TND`, unrealized P&L `+0.75 TND` (`+0.19%`)
   - Competition rank: `118 / 14,530`
   - Balance reconciliation: `is_reconciled: true`, `reconciliation_gap_tnd: "0.000"` (`49,608.05 + 392.70 == 50,000.75`)
2. **Confirmation State Before Phase 0**:
   - `data/portfolio/real_competition_ledger.json` did not exist on disk yet because `sync_20261107_122006.json` had been captured via `bvmt browser-sync` and awaited explicit user confirmation (`confirmed_by_user=True`).
   - Consequently, the fallback baseline (`data/portfolio/real_account_snapshot.json`, `SNAP-TBC-USER-001`, `49,998.050 TND`, `-1.950 TND`) remained the active opening snapshot while `sync_20261107_122006.json` sat in `data/portfolio/snapshots/` as `pending_browser_snapshot`.
3. **Why Streamlit Previously Selected `SYNTHETIC DEMO` (`2026-01-09`)**:
   - `discover_available_bar_datasets()` placed `"SYNTHETIC DEMO: tests/fixtures/daily_bars.csv"` at `index=0`, and the sidebar selectbox defaulted to `index=0` before `select_default_dataset_index()` was introduced.

---

## 2. Canonical Data-Source Selection Rules (`src/bvmt/portfolio_service.py`)

Both the FastAPI backend (`src/bvmt/api.py`) and the Streamlit fallback UI (`src/bvmt/dashboard.py`) use `PortfolioStateService` and `resolve_canonical_portfolio_context` in `src/bvmt/portfolio_service.py`:

### Rule 1 — Portfolio Environment (`portfolio_mode`)
- Default environment is **`REAL_COMPETITION`**.
- In **`REAL_COMPETITION`** mode:
  - Active ledger file: `data/portfolio/real_competition_ledger.json`
  - Historical opening baseline (read-only provenance): `data/portfolio/real_account_snapshot.json` (`SNAP-TBC-USER-001`)
  - Browser DOM snapshots directory: `data/portfolio/snapshots/sync_*.json`
- In **`SYNTHETIC_DEMO`** mode:
  - Active ledger file: `data/portfolio/ledger.json` (`100,000.000 TND` paper demo)

### Rule 2 — Market Dataset Selection (`bars_path`)
- In **`REAL_COMPETITION`** mode:
  - Default dataset is the latest **`VERIFIED IMPORT`** canonical dataset under `data/processed/*/daily_bars.canonical.csv` (`data/processed/bvmt_official_2026/daily_bars.canonical.csv`, `14,480` bars across `194` sessions through **`2026-11-06`**).
  - If a verified dataset is missing or corrupt, `inspect_market_dataset_provenance` raises an explicit `FileNotFoundError` or `ValueError`—it **never** silently substitutes synthetic fixture data.
  - If an operator explicitly selects `SYNTHETIC DEMO` for testing while viewing `REAL_COMPETITION`, `generate_recommendations` forces all candidates to `NO TRADE` (`suggested_shares=0`) with blocker `synthetic_data_on_real_portfolio`.
- In **`SYNTHETIC_DEMO`** mode:
  - Default dataset is `tests/fixtures/daily_bars.csv` (`2026-01-09`).

### Rule 3 — Confirmation-Gated Snapshot Lifecycle
1. **Capture (`POST /api/sync/browser` or `bvmt browser-sync`)**:
   - Launches an isolated read-only Playwright window (`data/browser_profile`), waits for manual login on `https://www.tunisbourse-challenge.com/displayp.aspx`, extracts portfolio + `display_histo.aspx` movements, validates `Cash + Holdings == Total`, and saves `data/portfolio/snapshots/sync_<timestamp>.json`.
   - **Never mutates `real_competition_ledger.json` automatically.**
2. **Preview (`GET /api/sync/preview`)**:
   - Compares the latest unconfirmed snapshot (`state.pending_browser_snapshot`) against the current ledger without mutating disk.
   - Displays `"Snapshot captured — awaiting confirmation"` in the UI.
3. **Confirm (`POST /api/sync/confirm` with `confirmed_by_user=True`)**:
   - Applies the reconciliation snapshot, records the snapshot in `ledger.snapshot_history`, updates `live_synchronized=True`, persists `data/portfolio/real_competition_ledger.json` to disk, and clears `pending_browser_snapshot`.
   - Preserves `data/portfolio/real_account_snapshot.json` (`SNAP-TBC-USER-001`) untouched as the historical opening baseline.

### Rule 4 — Dual Valuation Transparency
- **Website-Reported Competition Account Values (`displayp.aspx`)**:
  - Exact values reported by the Tunis Bourse Challenge website at the last confirmed snapshot (`50,000.75 TND` total equity, `49,608.05 TND` cash, `392.70 TND` `BH BANK` market value @ `13.09 TND`, `+0.75 TND` / `+0.19%` unrealized P&L, rank `118 / 14,530`).
- **Locally Recalculated Mark-to-Market Valuation (`BVMT Official Market Quotations`)**:
  - Independently marks holdings to the latest verified BVMT session close (`2026-11-06`) and reports any price drift between the competition portal's quote and the official BVMT close.
