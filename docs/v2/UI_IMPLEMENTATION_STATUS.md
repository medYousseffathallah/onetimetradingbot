# BVMT Trading Intelligence V2 — UI Implementation Status

**Frontend Workspace**: `apps/terminal-v2/` (Next.js `15.5.29`, React 19, TypeScript strict, Tailwind CSS)  
**Primary Author**: Antigravity `v2_frontend_engineer` (`conversationId: 21e2cdaa-79d2-44f2-90b5-1d62a7aada76`), with P0/P1 remediations verified by Orchestrator (`f52abe73-b91c-4cc5-ad93-809e6f7ae9fe`).  
**Design Authority**: [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md), [INFORMATION_ARCHITECTURE.md](INFORMATION_ARCHITECTURE.md), [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md), and [SCREEN_SPECIFICATIONS.md](SCREEN_SPECIFICATIONS.md).

---

## 1. Implemented Routes (All 9 Primary Destinations + Compatibility Routes)

| # | Destination | Route(s) | Build Type | Key Verified Capabilities |
|---|---|---|---|---|
| 1 | **Overview / Morning Workspace** | `/` | Static + Client Fetch | Account truth conflict banner (`49,993.430` reverted ledger vs `50,093.190` Nov 12 DOM vs `50,355.830` EOD MTM vs `50,647.64` unverified screenshot), 3-source reconciliation strip, equity trajectory chart, Top Challenge candidates, held position monitor (`8` DOM positions), upstream + runtime excluded non-equity telemetry. |
| 2 | **Portfolio & Account Sync** | `/portfolio` | Static + Client Fetch | 3-source side-by-side reconciliation table, `VENDRE` DOM glitch rejection log (`sync_20261109_120109.json`), cash drag analysis (`59.04%` / `29,574.190 TND`), canonical holdings table. |
| 3 | **Opportunity Discovery** | `/discovery` | Static + Client Fetch | Challenge 42 vs Full BVMT (75 ISINs) universe toggle, `5-10` vs `10-20` horizon selector, explicit `ELIGIBLE_MANUAL_ONLY` vs `RESTRICTED_CHALLENGE` vs `UNTRADABLE_HALTED` gates, liquidity capacity tiers (`Tier 1 >= 50k`, `Tier 2`, `Tier 3 < 5k`). |
| 4 | **Stock Research Workbench** | `/stocks`, `/stocks/[instrumentId]` | Static + Dynamic (`ƒ`) | Interactive EOD SVG price chart (`getStockBars`), 10-field `PriceProvenance` L9 audit register with dynamic `data_quality_status` provenance badge (`EOD_UNVERIFIED_PUB_TIME` / `SYNTHETIC_FIXTURE` / `VERIFIED_PIT`), Challenge status, ADV liquidity metrics. |
| 5 | **Decision & Sizing Workbench** | `/decisions` | Static + Client Fetch | Pre-trade gate enforcement (`RESTRICTED_CHALLENGE` disables dry-run BUY button on non-Challenge stocks such as `MONOPRIX`), manual fee (`0.50%`), `10%` single-stock cap headroom, stress exit slippage, `is_executed: false` guarantee. |
| 6 | **Position Management** | `/positions`, `/positions/[instrumentId]` | Static + Dynamic (`ƒ`) | Hold/Exit thesis & monitoring state (`UNVERIFIED_THESIS` / `EXIT_REVIEW_REQUIRED`), downside stress scenario, manual sell & capital-protection calculators (`is_executed: false`). |
| 7 | **Performance & Attribution** | `/attribution` | Static + Client Fetch | Starting vs EOD MTM vs screenshot return decomposition, `TUNINDEX` (`UNAVAILABLE`), residual gap exposure (`+235.68 TND` screenshot gap), explicit failure tags (`UNVERIFIED_COST_BASIS`, `PARTIAL_SCREENSHOT_OMITS_8_HOLDINGS`, etc.). |
| 8 | **Research Lab** | `/research-lab`, `/research` | Static + Client Fetch | Explicit `STRICT_PIT` vs `RETROSPECTIVE_EXPLORATORY` simulation mode toggle, `H=5/10/20` horizon selector, walk-forward family table with Top-1 Winner Excluded & phase IQR sensitivity, mode-filtered exit-policy comparison, frozen `SignalJournal`, and dynamic limitation disclosures. |
| 9 | **Data & Account Health** | `/health` | Static + Client Fetch | `72` competition rule blockers, `BVMT_ALLOW_LIVE_LLM=0`, `execution_enabled: false`, canonical equity & Challenge count (`75` / `42`), upstream (`2,480`) + runtime excluded non-equity counts, `published_at_present_count: 0`, loopback-only posture. |

---

## 2. Build, Typecheck, Browser Audit & Performance Verification

| Check | Outcome | Evidence |
|---|---|---|
| TypeScript (`npm.cmd --prefix apps/terminal-v2 run typecheck`) | **PASS** (`exit 0`) | `tsc --noEmit` — zero errors across all files |
| Production Build (`npm.cmd --prefix apps/terminal-v2 run build`) | **PASS** (`exit 0`, build `tLsAyp64Wf5bUK9cZaCT3`) | All `13` Next.js App Router pages compiled (`102 kB` shared First Load JS) |
| Playwright Headless Chrome Audit (`scripts/v2_browser_audit.py`) | **PASS** (`22 / 22` checks) | `artifacts/v2/browser-results.json`: zero horizontal overflow on all `9` destinations at `1440px` desktop & `390px` mobile (`18` PNGs), `runtime_errors: []`, `external_attempts: []`, `protected_files_unchanged: true`, pre-trade disabled BUY verified on `MONOPRIX`, interactive BUY/SELL/PROTECTION scenarios and `SYNTHETIC_DEMO` mode switching verified |
| Cold / Warm Profiling (`scripts/v2_performance.py`, `samples=5`) | **PASS** (`exit 0`) | `artifacts/v2/performance.json` — API warm medians: `7.15–121.73 ms` (`/overview` `52.12 ms`, `/portfolio` `42.98 ms`, `/discovery` `121.73 ms`, `/positions/EURO-CYCLES` `31.13 ms`, `/attribution` `27.44 ms`, `/research-lab` `7.15 ms`); UI page medians (warm API): `/` `1843.85 ms` cold / `1722.35 ms` warm, `/portfolio` `3298.53 / 2857.59 ms`, `/discovery` `2595.80 / 1939.27 ms`, `/positions/EURO-CYCLES` `2216.82 / 1762.54 ms`, `/attribution` `2110.20 / 1478.25 ms`, `/research-lab` `1854.84 / 1335.83 ms` |
