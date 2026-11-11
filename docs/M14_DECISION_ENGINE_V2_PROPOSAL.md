# Milestone 14 — Decision Engine v2 Architectural Proposal (`Task G4`)

- **Author**: Gemini Quantitative Research Mission (Google Antigravity IDE)
- **Status**: **ARCHITECTURAL DESIGN PROPOSAL ONLY — ZERO PRODUCTION CODE MODIFIED.** Implementation requires Codex architectural review and pre-registered validation per [M14_EXPERIMENT_PLAN.md](./M14_EXPERIMENT_PLAN.md).

---

## 1. Core Architectural Defect Solved by Decision Engine v2

The current M13 stack conflates **five distinct concepts** inside single thresholds, boolean exclusion strings, or mixed-unit scores:
1. Whether local market data is clean enough to **compute indicators safely** (`features.py` binary `60s` cliff drops `ICF`, `ATB`, `BH`, `SOTUMAG`, `TJL`, `TRE` for 3 months over 1 gap; `published_at=None` crashes raw runs).
2. Whether an instrument has **positive research expected edge** (`sparse_research` allows `-12.9996` `BNA` and non-challenge stocks to trigger/fill top-K slots; `vol_20=1e-6` spikes `composite=125000.0`).
3. Whether the instrument can be **executed safely on Tunis Bourse** (`10%` participation cap vs `5,000 TND` threshold; raw `NB_TRANSACTION` & bloc trades ignored).
4. Whether the stock fits **user portfolio & Challenge rules** (non-challenge `MONOPRIX`, `ESSOUKNA`, `CIL` enter recommendations/top-K; Poulina ISIN `TN0005700018` splits across two IDs).
5. How a human trader **reviews & acts safely** (`Trade Planner` / unverified `configs/competition.json` exit `2` / stale price warnings).

**Design Principle**: Decompose every evaluation into **Seven Independent, Auditable Layers (`A–G`)**, strictly separate **Tunis Bourse Challenge (`42` securities)** from **General BVMT Equity Research**, key identities canonically on **verified `ISIN`**, and enforce **explicit `None` provenance for missing data** (never convert `None` to `0.0` or synthetic `10000 TND` liquidity).

---

## 2. Canonical Identity & Universe Separation

### 2.1 ISIN-Keyed Alias Resolution (`Layer 0`)
- Every security entity resolves through an immutable mapping keyed by `isin`:
  - Fix **`TN0005700018` (Poulina)**: Unify historical `POULINA_GROUP_HOLDING` (`2026-01-02..2026-04-08`) + `POULINA_GP_HOLDING` (`2026-04-10..present`) into a single continuous bar series under canonical ID `POULINA_GP_HOLDING`, eliminating the broken April–June history window and duplicate quote records.
- **`macro_events.py` / Disclosures**: Force alias expansion ON unconditionally when resolving ticker, canonical ID, and ISIN tokens (`CC` -> `CARTHAGE_CEMENT`, `STPAP` -> `SOTIPAPIER`).

### 2.2 Dual-Track Scope Gate (`CHALLENGE_ACTIONABLE` vs `FULL_BVMT_RESEARCH`)
- **Rule**: Competition rankings, top-K research allocation, holding-period competition reports (`holding_period.py` fixed from `get_challenge_symbol_set()` to canonical `Challenge` ISIN/ID matching — recovering all **42/42** securities instead of `15/42`), and cash budgets MUST run strictly inside `CHALLENGE_UNIVERSE_42` when `scope == "CHALLENGE"`.
- Non-challenge equities (`MONOPRIX`, `ESSOUKNA`, `CIL`, etc.) appear **exclusively** in a visually distinct **"General BVMT Research (Non-Challenge — Not Eligible for Contest Orders)"** track, never consuming Challenge top-K slots or Challenge simulated cash budgets.

---

## 3. Seven-Layer Decision Engine v2 Specification (`Layers A–G`)

| Layer | Name & Responsibility | Explicit Inputs & PIT Rule | Core Outputs & Invariants |
| :--- | :--- | :--- | :--- |
| **A** | **Data Quality & Completeness** | `daily_bars` (`published_at_utc <= cutoff_utc`), `exchange_calendar`, H/B `rejections` audit tags, ISIN-merged series. | `obs_count_20s`, `obs_count_60s`, `coverage_ratio_60s`, `traded_sessions_20s`, `quote_age_open_sessions`, `hb_recovered_count`, `quality_tier` (`COMPLETE`, `RECOVERABLE_GAP`, `SPARSE_TRADE`, `STALE_OR_MISSING`). **Never drops a stock silently due to 1–2 missing sessions if `coverage_ratio_60s >= 0.90` and `quote_age <= 5`s.** |
| **B** | **Market Structure & Executability** | Canonical bars + raw `echanges` (`trade_count`), `quantiteBloc`, `capitauxBloc`, `indicateur`, `vwap` (`M14_FUNDAMENTAL_DATA_GAPS`). | Order-book `median_turnover_20s_tnd` (excluding block crosses if block > 50%), `median_trade_count_20s`, `zero_volume_rate_20s`, `single_order_share_10pct_cap_tnd` (`10% * median_traded_volume * price`), `estimated_roundtrip_drag_bps`, `executability_tier` (`LIQUID_CONTINUOUS`, `CONSTRAINED_DEPTH`, `THIN_WATCH_ONLY`, `ILLIQUID`). **Zero synthetic `10000 TND` fallbacks — missing stays `None`.** |
| **C** | **Multi-Horizon Quantitative Signal Engine** | Traded price closes (dividend/split-adjusted once corporate actions exist), returns bounded strictly inside `(t - window, t]`, cross-sectional winsorization / robust z-scores (`MAD` or IQR). | De-duplicated horizon signals: `ret_5s`, `ret_20s`, `ret_60s` (**all percentage units labeled `_pct`**, zero ratio-vs-% ambiguity), realized volatility **floored only after cross-sectional minimum `max(realized_vol_20s, 0.0025)` (0.25% daily vol floor, preventing `1e-6` 125,000x explosions)**, `directional_awakening_flag` (**requires `ret_1s > +1.5%` OR positive breakout above trailing 20s median close AND `latest_day_return_pct is not None` — blocks negative/zero drops from awakening!**), `trend_score_z`, `uncertainty_band`. |
| **D** | **Fundamental & PIT Event Evidence** | `events_pit.parquet` (`published_at_utc <= cutoff_utc` — NO hardcoded Nov 06 cutoff!), future `fundamentals_pit.parquet`, sector map (`mapping_emetteur.json`). | `pit_event_count`, `event_polarity` (`POSITIVE | MIXED | NEGATIVE | NO_VERIFIED_EVIDENCE`), `fundamental_coverage_status` (`ABSENT_NO_FILINGS`, `PARTIAL_SNAPSHOT_ONLY`, `PIT_VERIFIED`), `event_citations` (source + UTC timestamp + SHA-256). Explicitly separates `"no catalyst found locally"` (`None`) from `"negative earnings"`. |
| **E** | **Portfolio Context & Constraint Feasibility** | Verified `PortfolioLedger` cash, current positions, pending snapshots/orders, `configs/competition.json` (`15` rule fields). | `is_held`, `held_weight_pct`, `max_additional_tnd_under_concentration_cap` (checked dynamically on BOTH pre-trade & post-drift weight!), `remaining_cash_after_pending`, `challenge_eligible_flag`, `competition_rules_verified_flag`. |
| **F** | **Unified Research State Machine** | Pure deterministic transition function `(Layer A..E outputs) -> ResearchState`. | Assigns one unambiguous state per security (**Section 4** below) + ordered `state_reasons[]` + `blockers[]`. |
| **G** | **Human-Supervised Review & Explanation Formatter** | Outputs from `A–F` + operational clock (`is_stale_quote`, `rules_unverified`). | Renders factual, unit-explicit explanation: never generates fake dates (`2026-11-27`) or static strings (`"194 trading sessions"`), distinguishes `RESEARCH-ONLY` from `CHALLENGE-ELIGIBLE`, and surfaces every missing fundamental/rule prerequisite prominently. |

---

## 4. Explicit Research & Action State Machine (`Layer F`)

Every instrument (Challenge and Research) receives **exactly one** deterministic terminal state at cutoff `t`:

1. **`INSUFFICIENT EVIDENCE`**: `coverage_ratio_60s < 0.70` OR `traded_sessions_20s < 5` OR `quote_age_open_sessions > 10` OR critical unresolved ingestion integrity failure (`ohlc_unreconciled_gap`). *(No numerical ranking or buy label permitted.)*
2. **`NOT ELIGIBLE`**: Evaluated for Challenge Trade/Action scope when `not in_challenge_universe(isin)` — or blocked by hard competition prohibition (e.g., short-sell, suspended issuer). *(Non-challenge stocks with strong quantitative scores route separately into `RESEARCH_ONLY_NON_CHALLENGE` informational tier, NEVER `BUY CANDIDATE` or `MANUAL TRADE PLAN`.)*
3. **`HOLD`**: Currently held in `PortfolioLedger` (`qty > 0`), `Layer A` & `B` intact, `Layer C` not deteriorating below exit hysteresis threshold, and within verified portfolio concentration cap (`Layer E`).
4. **`REVIEW POSITION`**: Currently held in `PortfolioLedger` (`qty > 0`), AND any of: concentration drift `> cap`, quantitative score deteriorated materially (e.g., `trend_score_z < -1.0`), verified negative PIT event (`Layer D`), or pending unconfirmed snapshot divergence (`Layer E`).
5. **`WATCH`**: Non-held Challenge equity with recoverable sparsity (`0.70 <= coverage_ratio_60s < 0.95` or single-session H/B quarantine) OR positive `directional_awakening_flag` with mixed/unconfirmed multi-horizon trend (`Layer C` not yet coherent) OR thin order book (`1,500 <= median_turnover_20s < 5,000 TND`).
6. **`RESEARCH FURTHER`**: Non-held Challenge equity showing coherent positive quantitative trend (`trend_score_z >= +1.0` AND `executability_tier in {LIQUID_CONTINUOUS, CONSTRAINED_DEPTH}`), **OR** positive `directional_awakening` with positive short+medium alignment, **while operational blockers or missing fundamental filings (`Layer D = ABSENT_NO_FILINGS`) prevent pre-trade clearance**.
7. **`PAPER-TRADE CANDIDATE`**: Passes `Layer A` (`COMPLETE` or `RECOVERABLE_GAP` with H/B verified), `Layer B` (`LIQUID_CONTINUOUS`, executable 10% cap >= minimum ticket), `Layer C` (positive calibrated composite across non-exploded vol floor), `Layer E` (cash & concentration compliant), while either model promotion gate is still open (`sparse` / unpromoted strategy) OR competition rule verification gate (`configs/competition.json`) remains incomplete.
8. **`MANUAL TRADE PLAN`**: Reachable **ONLY** when ALL FIVE prerequisites hold simultaneously:
   - `(1)` Challenge universe member (`CHALLENGE_ORDER_ELIGIBLE`)
   - `(2)` Strategy formally passed promoted G5 walk-forward + holdout gate
   - `(3)` `configs/competition.json` has `0` unresolved blocking rule ambiguities (`rules-check` exit `0`)
   - `(4)` Quote freshness & portfolio reconciliation verified (`quote_age <= 1` session, no conflicting pending DOM sync)
   - `(5)` Executable size >= minimum lot & strictly `<= 10%` of trailing median volume and within remaining concentration headroom.
   *(While all 15 competition rule fields remain unverified and model promotion gates remain unpassed, zero stocks can enter `MANUAL TRADE PLAN` — capping actionable output cleanly at `RESEARCH FURTHER` / `PAPER-TRADE CANDIDATE` with human-in-the-loop review.)*

---

## 5. Deterministic Safety Overrides (Hard Vetoes Across Layers A–G)

| Override Rule | Trigger Condition | Forced State / Cap | Rationale |
| :--- | :--- | :--- | :--- |
| **O1: Missingness Never Imputes Zero** | `metric is None` or insufficient history | Leave field `None`; route to `WATCH` / `INSUFFICIENT EVIDENCE` | Eliminates `multi_horizon` falsy `0.0` & `10000 TND` fabrication bugs (`G1-04`). |
| **O2: Volatility Explosion Guard** | `realized_vol_20s < 0.0025` | Clamp denominator at `0.0025` (0.25% daily vol) + cross-sectional winsorization `[p5, p95]` | Prevents `1e-6` denominator spikes (`125,000.0` score in `G1-06`). |
| **O3: Directional Awakening Gate** | `turnover_ratio >= 3.0x` | Require `latest_day_return_pct is not None and latest_day_return_pct >= +1.5%` | Stops flat/dropping stocks (`BNA 0.0%`, `ENNAKL` negative gap) from raising awakening alerts (`G1-07`). |
| **O4: Strictly Monotonic PIT Gate** | `source_published_at_utc > cutoff_utc` | Exclude row invisibly (macro, fundamentals, bars) | Fixes `multi_horizon` Nov-06 leak (`G1-03`) & prevents future accounting leaks. |
| **O5: Scope Isolation** | `scope == "CHALLENGE"` and `not challenge_member` | Exclude from top-K, weights, holding-period reports, and cash allocation | Stops `MONOPRIX`/`ESSOUKNA`/`CIL` from evicting Challenge stocks like `ICF` (`G1-05, G1-07`). |
| **O6: Rule & Reconciliation Ceiling** | `competition_unverified > 0` OR `snapshot_unreconciled` | Maximum state capped at `PAPER-TRADE CANDIDATE` / `RESEARCH FURTHER` | Guarantees non-actionable posture until official Tunis Bourse Challenge PDF is verified (`G1` + `P0`). |
