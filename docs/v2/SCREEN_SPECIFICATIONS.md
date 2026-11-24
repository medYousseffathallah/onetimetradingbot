# BVMT Trading Intelligence V2 — Screen Specifications (All 9 Destinations)

**Status**: Gate 1 UX Specification (`V2-UX1`)  
**Aligned Contracts**: `ADR-001..ADR-005` ([ARCHITECTURE_DECISIONS.md](./ARCHITECTURE_DECISIONS.md))  
**Viewports**: `1440px` Desktop (`240px` rail + `1200px` main) and `390px` Mobile (single-column stack, zero horizontal overflow)

---

## Global Chrome (Shared Across All 9 Destinations)

- **Component `<AppShell>`**:
  - Props: `activeRoute: DestinationRoute`, `mode: "REAL_COMPETITION" | "SYNTHETIC_DEMO"`, `datasetCutoff: string ("2026-11-18")`, `accountTruthState: "CONFLICTED" | "UNVERIFIED" | "VERIFIED"`, `rulesBlockerCount: number (72)`.
  - **Top Context Bar**: Displays `mode` selector (`REAL_COMPETITION` default, `SYNTHETIC_DEMO` triggers persistent sandbox ribbon), `Data Cutoff: 2026-11-18 EOD (NOT LIVE)`, `Account Truth` pill, and mobile drawer trigger (`<= 1024px`).
  - **Left Navigation Rail (`240px`)**:
    - Cluster 1 (*Portfolio & Supervision*): `1. Investment Overview` (`/`), `2. Portfolio Manager` (`/portfolio`), `6. Position Management` (`/positions`)
    - Cluster 2 (*Research & Decisions*): `3. Opportunity Discovery` (`/discovery`), `4. Stock Research Workspace` (`/stocks`), `5. Investment Decision Workspace` (`/decisions`)
    - Cluster 3 (*Evaluation & Integrity*): `7. Performance & Attribution` (`/attribution`), `8. Research Lab` (`/research-lab`), `9. Data & Account Health` (`/health`)

---

## Destination 1: Investment Overview (`/`)

**Primary Question**: *What is my actual confirmed equity, cash, and rank—and what needs attention first?*  
**API Endpoint**: `GET /api/v2/overview?mode={mode}`

### Wireframe — Desktop (`1440px`) vs Mobile (`390px`)
```text
[1440px Desktop]
+------------------------------------------------------------------------------+
| ALERT BANNER (Amber): Account Sync Conflict & Unimported Movements           |
| Confirmed Ledger (2026-11-10): 49,993.430 TND | Newer DOM Capture (2026-11-12): 50,093.190 TND |
+------------------------------------------------------------------------------+
| 4-Col Truth Comparison Strip (1 card per truth state):                       |
| [1. Confirmed Ledger]  [2. Latest Capture]  [3. User Screenshot] [4. EOD Mark]|
| 49,993.430 [OBSERVED]  50,093.190 [UNVERIF.] 50,647.640 [UNVERIF] 50,355.830 [CALC] |
+------------------------------------+-----------------------------------------+
| Capital Allocation & Cash Drag     | Review Priorities Queue (Ordered)       |
| - Invested vs Cash Donut           | 1. [REVIEW] Account Snapshot Conflict   |
| - Cash Drag metric (58.7%–77.5%)   | 2. [CONSIDER_TRIM] EURO-CYCLES 10.29%   |
| - Pending Orders: [UNVERIFIED]     | 3. [EXECUTION_BLOCKED] 72 Rule Blockers |
+------------------------------------+-----------------------------------------+
| Holdings Pulse Table (8 positions from latest capture + Nov 18 EOD marks)    |
+------------------------------------------------------------------------------+

[390px Mobile]
- Single column stack: Top Bar -> Conflict Banner -> 4 Truth Cards (1 col) ->
  Cash Drag Card -> Review Priorities Cards -> Holdings Pulse (stacked cards).
```

### Component Props & API Field Bindings
- `<AccountConflictBanner>`: binds `confirmed_snapshot: PortfolioSnapshot`, `latest_capture_snapshot: PortfolioSnapshot`, `movements_imported: bool`.
- `<TruthComparisonCard>`: props `{ title, equity: ProvenanceValue, cash: ProvenanceValue, rank: string, sourceLabel: string, capturedAt: string | null }`. Never merges `confirmed_snapshot`, `latest_capture`, `unverified_screenshot`, and `eod_mark_portfolio`.
- `<CashDragPanel>`: binds `cash_tnd: ProvenanceValue`, `cash_weight_pct: ProvenanceValue`, `cash_drag_pct: ProvenanceValue`, `pending_orders_status: ValueStatus`.
- `<ReviewPriorityList>`: binds `priorities: Array<{ instrument_id, monitoring_state, execution_state, reason, target_route }>`.

---

## Destination 2: Portfolio Manager (`/portfolio`)

**Primary Question**: *Which holdings, weights, cost bases, theses, and commitments are confirmed vs conflicted?*  
**API Endpoint**: `GET /api/v2/portfolio?mode={mode}`

### Wireframe — Desktop (`1440px`) vs Mobile (`390px`)
```text
[1440px Desktop]
+------------------------------------------------------------------------------+
| Conflict Banner: Out-of-order ledger (Nov 10) vs Nov 12 DOM capture (8 pos)  |
+------------------------------------------------------------------------------+
| Summary Strip: Confirmed Cash | Capture Cash | Sector Concentration | Orders |
+------------------------------------------------------------------------------+
| Tabs: [Holdings & Theses (8)] [Sector & Issuer Weights] [Transactions/Orders]|
| Table: Symbol/ISIN | Qty | Avg Cost | EOD 11-18 | Weight | Thesis/Horizon | State |
+------------------------------------+-----------------------------------------+
| Sector Exposure Bars               | Snapshot Audit Timeline (Read-Only)     |
+------------------------------------+-----------------------------------------+

[390px Mobile]
- Tabs scroll cleanly inside horizontal pill bar (flex-wrap) -> each Holding
  renders as a bordered card with 2-col key-value grid + monitoring/execution pills.
```

### Component Props & API Field Bindings
- `<HoldingsTable>`: binds `holdings: Array<Holding & { sector: string, weight_pct: ProvenanceValue, thesis: InvestmentThesis, position_decision: PositionDecision }>`.
  - Columns: `symbol`, `isin`, `quantity`, `displayed_avg_cost_tnd`, `eod_reference_close_tnd` (`2026-11-18`), `weight_pct` (flags `> 10.00%` in amber), `thesis.thesis` & `thesis.horizon_sessions` (`UNVERIFIED_NONE` if unrecorded), `monitoring_state`, `execution_state`.
- `<SectorExposureCard>`: binds `sector_weights: Array<{ sector, weight_pct: ProvenanceValue, issuer_count }>`.
- `<OrdersTransactionsPanel>`: binds `transactions: Transaction[]`, `pending_orders: PendingOrder[]`, `verification_status: ValueStatus` (`UNVERIFIED` when `movements_page_captured=false`, never displays `0 pending orders confirmed`).

---

## Destination 3: Opportunity Discovery (`/discovery`)

**Primary Question**: *Which Challenge-eligible equities deserve research today, strictly isolated from general research?*  
**API Endpoint**: `GET /api/v2/discovery?mode={mode}&universe={TUNIS_BOURSE_CHALLENGE|FULL_BVMT_RESEARCH}&horizon={1_2|3_5|5_10|10_20|20_60}`

### Wireframe — Desktop (`1440px`) vs Mobile (`390px`)
```text
[1440px Desktop]
+------------------------------------------------------------------------------+
| Scope Switcher: [Challenge Universe (42)] | [Full BVMT Research (76 Equities)]|
| Non-Challenge Warning Banner when FULL_BVMT_RESEARCH selected (Not orderable)|
| Horizon Pills: [1-2s] [3-5s] [5-10s] [10-20s] [20-60s]  Search + State Filter|
+------------------------------------------------------------------------------+
| Table: Rank | Security/ISIN | EOD Close | Horizon Ret | 20s Med Turnover     |
|        10% ADV Shares | Coverage | Assessment State | Primary Blocker | Link |
+------------------------------------------------------------------------------+

[390px Mobile]
- Scope toggle stacked -> Horizon pills wrap cleanly -> Search input full width ->
  Candidate list renders as stacked Opportunity Cards with Research CTA.
```

### Component Props & API Field Bindings
- `<UniverseScopeBar>`: enforces `ADR-001` (`76` equities, `496` excluded non-equities noted in footer) and `challenge_eligible` track separation.
- `<OpportunityTable>`: binds `candidates: OpportunityCandidate[]` (`assessment: StockAssessment`, `challenge_eligible: bool`, `adv_20s_tnd: ProvenanceValue`, `ten_pct_adv_shares: ProvenanceValue`, `research_priority_rank: int`).
  - Explicitly separates **Research Attention** (`assessment.state`) from **Executability** (`ten_pct_adv_shares`, `liquidity_status`) and **Missingness** (`missing_evidence.length`).

---

## Destination 4: Stock Research Workspace (`/stocks/[instrument_id]`)

**Primary Question**: *What evidence supports, contradicts, or is missing for this issuer across L1–L9?*  
**API Endpoint**: `GET /api/v2/stocks/{instrument_id}?mode={mode}&horizon={horizon}`

### Wireframe — Desktop (`1440px`) vs Mobile (`390px`)
```text
[1440px Desktop]
+------------------------------------------------------------------------------+
| Persistent Issuer Header: EURO-CYCLES | TN0007570013 | Continu | Challenge   |
| EOD Close (11-18): 10.160 TND [OBSERVED] | Live Quote: Unavailable [UNAVAIL] |
| State: [HELD_POSITION_REVIEW] | Execution: [EXECUTION_BLOCKED]               |
+------------------------------------+-----------------------------------------+
| EOD Price & Volume Chart (SVG)     | Assessment Summary & Hypothesis         |
| (Plots observed sessions, marks    | Supporting (green) vs Contradicting     |
| zero-vol gaps, horizon toggle)     | (amber/red) vs Missing (slate)          |
+------------------------------------+-----------------------------------------+
| L1-L9 Evidence Grid (2-col on desktop):                                      |
| [L1 Technical] [L2 Liquidity] [L3 Fundamental: UNAVAILABLE] [L4 Events]      |
| [L5 Regime]    [L6 Contradictions] [L7-L8 Portfolio Fit] [L9 Provenance Reg] |
+------------------------------------------------------------------------------+

[390px Mobile]
- Issuer Header stacks -> EOD Close / Live Quote 2-up -> Chart -> Evidence panels
  stack 1-column with collapsible L9 Provenance Register table/cards.
```

### Component Props & API Field Bindings
- `<IssuerIdentityBar>`: binds `instrument: Instrument`, `historical_eod_close_tnd: ProvenanceValue`, `current_executable_quote_tnd: ProvenanceValue` (`UNAVAILABLE`), `assessment.state`.
- `<EodPriceVolumeChart>`: binds `observations: MarketObservation[]` (flags `status == "untraded"` explicitly).
- `<EvidenceLayerGrid>`: binds `assessment.technical_state` (L1), `assessment.liquidity_status` (L2), `assessment.fundamental_state` (L3 — visibly renders `UNAVAILABLE · ABSENT_NO_FILINGS`), `assessment.event_context` (L4), Regime/Macro (L5), `assessment.contradicting_evidence` (L6), `assessment.portfolio_suitability` & `execution_feasibility` (L7–L8), and `PriceProvenance` 10-field table (L9).

---

## Destination 5: Investment Decision Workspace (`/decisions`)

**Primary Question**: *Can I document a thesis and simulate a manual BUY without tripping constraints?*  
**API Endpoint**: `POST /api/v2/decisions/buy-scenario` (reads `stocks/{id}` + `portfolio`)

### Wireframe — Desktop (`1440px`) vs Mobile (`390px`)
```text
[1440px Desktop]
+------------------------------------------------------------------------------+
| Header: Investment Decision Workspace (Research & Buy Scenario — Manual Only)|
+------------------------------------+-----------------------------------------+
| Left (7 cols):                     | Right (5 cols):                         |
| 1. InvestmentThesis Editor         | Manual BUY Scenario Simulator           |
|    - Thesis text, horizon_sessions,|  - Inputs: Instrument, Qty, User Limit  |
|      invalidation_conditions       |  - Outputs [SIMULATED / is_executed=F]: |
| 2. L1-L10 Pre-Trade Gate Checklist |    Gross, 0.50% Fee, Post-Trade Weight, |
|    (Pass / Review / Blocked rows)  |    Post-Trade Cash, 10% Cap Check,      |
|                                    |    10% ADV Liquidity Cap, Blockers[]    |
+------------------------------------+-----------------------------------------+

[390px Mobile]
- Single column: Thesis Editor -> Gate Checklist -> Manual BUY Scenario Simulator.
```

### Component Props & API Field Bindings
- `<ThesisRecordCard>`: binds `InvestmentThesis` (`instrument_id`, `thesis`, `horizon_sessions`, `invalidation_conditions`, `recorded_at`, `origin`).
- `<BuyScenarioCalculator>`: posts `{ instrument_id, quantity, limit_price_tnd, mode }` to `POST /api/v2/decisions/buy-scenario`, binds `ManualTradeScenario` (`gross_tnd`, `estimated_fee_tnd`, `post_trade_weight`, `post_trade_cash_tnd`, `is_valid`, `rejection_reasons`, `is_executed=False`) and `ExecutionFeasibility` (`automatic_submission_enabled=False`, `blockers`).

---

## Destination 6: Position Management (`/positions/[instrument_id]`)

**Primary Question**: *Should I hold, review, trim, or exit this held position—and what blocks execution?*  
**API Endpoints**: `GET /api/v2/positions/{instrument_id}?mode=...`, `POST /api/v2/positions/sell-scenario`, `POST /api/v2/positions/protection-scenario`

### Wireframe — Desktop (`1440px`) vs Mobile (`390px`)
```text
[1440px Desktop]
+------------------------------------------------------------------------------+
| Position Header: EURO-CYCLES (510 sh @ 9.799 avg -> 10.160 EOD = 5,181.600) |
| Monitoring Pill: [REVIEW]  |  Execution Gate Pill: [EXECUTION_BLOCKED]       |
+------------------------------------------------------------------------------+
| Decoupled Explanation & Blockers Card:                                       |
| - Why REVIEW: 10.29% weight (>10% cap), -16.65% 60s trend vs +1.60% 5s/20s   |
| - Why EXECUTION_BLOCKED: Rules (72), Live Quote Unavailable, Snapshot Diff   |
+------------------------------------+-----------------------------------------+
| Left: Downside Protection Scenario | Right: Manual Partial Sale Calculator     |
| - Stop / Stress Price input        | - Qty to sell slider/input (e.g. 50 sh) |
| - Stress Proceeds & Downside Loss  | - Gross, 0.50% fee, Net proceeds,       |
| - Liquidity Days to Exit (10% ADV) |   Post-sale weight (<10% check),        |
| - Next Review Trigger              |   is_executed=False [SIMULATED]         |
+------------------------------------+-----------------------------------------+

[390px Mobile]
- Position KPIs (2x2 grid) -> Monitoring vs Execution Gate card -> Protection
  Scenario -> Manual Partial Sale Calculator (all stacked cleanly <= 390px).
```

### Component Props & API Field Bindings
- `<PositionStatusSplit>`: binds `PositionDecision` (`monitoring_state`, `execution_state`, `blockers`, `explanation`, `next_review_trigger`, `exit_scenarios`) and `RiskAssessment` (`position_weight`, `max_single_stock_weight`, `concentration_breach`, `liquidity_days_to_exit`, `volatility_20s`, `downside_stress_tnd`).
- `<ProtectionScenarioCard>`: calls `POST /api/v2/positions/protection-scenario`.
- `<PartialSaleCalculator>`: calls `POST /api/v2/positions/sell-scenario`, renders `ManualTradeScenario` (`is_executed=False`) with explicit `SIMULATED SCENARIO — MANUAL PORTAL ENTRY ONLY` badge.

---

## Destination 7: Performance & Attribution (`/attribution`)

**Primary Question**: *What drove account performance over Nov 7–18, and why is there a +235.680 TND unexplained gap?*  
**API Endpoint**: `GET /api/v2/attribution?mode={mode}`

### Wireframe — Desktop (`1440px`) vs Mobile (`390px`)
```text
[1440px Desktop]
+------------------------------------------------------------------------------+
| Warning Banner: Attribution Partial — Movements History Missing (+235.680 TND|
| Unexplained Residual between Confirmed/EOD Marks & Unverified Total)         |
+------------------------------------------------------------------------------+
| 4-Col Waterfall KPIs: Starting 50k | Realized (+71.820) | Unrealized (+284.000) |
| Unexplained Residual (+235.680 [UNVERIFIED]) | Cash Drag | Est. Fees         |
+------------------------------------+-----------------------------------------+
| Nov 7-18 Equity Trajectory (SVG)   | Benchmark Comparison (Separate Lane!)   |
| (Plots Confirmed vs Capture vs EOD)| Cash (0.00%) vs EW vs Legacy G [SIM]    |
+------------------------------------+-----------------------------------------+
| Per-Stock Attribution Table (8 holdings: Cost, EOD 11-18, Contrib TND & %)   |
+------------------------------------------------------------------------------+

[390px Mobile]
- Waterfall KPIs stack -> Trajectory chart -> Benchmark comparison cards ->
  Per-Stock Attribution stacked cards.
```

### Component Props & API Field Bindings
- `<AttributionSummary>`: binds `PerformanceAttribution` (`period_start`, `period_end`, `starting_equity_tnd`, `ending_equity_tnd`, `total_return_pct`, `realized_pnl_tnd`, `unrealized_pnl_tnd`, `unexplained_residual_tnd`, `cash_drag_pct`, `estimated_fees_tnd`, `failure_tags`).
- `<BenchmarkComparisonPanel>`: binds `benchmarks` (`Cash`, `Equal-Weight`, `Legacy Model G Reference`), each marked `SIMULATED` or `CALCULATED` in a strictly separate lane from account P&L.
- `<StockAttributionTable>`: binds `position_attributions`.

---

## Destination 8: Research Lab (`/research-lab`)

**Primary Question**: *Do V2 strategy hypotheses outperform Cash, Equal-Weight, and Legacy Model G cleanly out-of-sample?*  
**API Endpoint**: `GET /api/v2/research-lab?mode={mode}`

### Wireframe — Desktop (`1440px`) vs Mobile (`390px`)
```text
[1440px Desktop]
+------------------------------------------------------------------------------+
| Research Sandbox Notice: All metrics below are [SIMULATED] walk-forward runs |
| Never equated to realized account profit. Live LLM calls: DISABLED (0).      |
+------------------------------------------------------------------------------+
| Filters: Horizon (1-2s..20-60s) | Scope (Challenge 42 / Full 76) | Family A-J|
+------------------------------------------------------------------------------+
| ModelExperiment Comparison Table:                                            |
| Family | Horizon | Folds | Net Ret | Alpha vs Cash | Alpha vs EW | Max DD |  |
| Top-1 Excl Ret | Turnover | Fees | Win Rate | N | Limitations                |
+------------------------------------------------------------------------------+
| SignalJournal (Frozen Hash Forward Log) & Promotion Gate Checklist           |
+------------------------------------------------------------------------------+

[390px Mobile]
- Filters wrap -> ModelExperiment cards (each showing Net Ret, Top-1 Excluded,
  Max DD, Sample N, and Limitations) -> SignalJournal cards.
```

### Component Props & API Field Bindings
- `<ExperimentTable>`: binds `experiments: ModelExperiment[]` (human-readable `family` label, zero raw LLM model IDs, `provenance_status == "SIMULATED"`, `top1_excluded_return_pct`, `limitations`).
- `<SignalJournalList>`: binds `journal: SignalJournal[]` (`journal_id`, `recorded_at`, `instrument_id`, `action_state`, `horizon`, `frozen_hash`, `outcome_status`).

---

## Destination 9: Data & Account Health (`/health`)

**Primary Question**: *What rule, data, identity, or sync blockers restrict trust and planning right now?*  
**API Endpoint**: `GET /api/v2/health?mode={mode}`

### Wireframe — Desktop (`1440px`) vs Mobile (`390px`)
```text
[1440px Desktop]
+------------------------------------------------------------------------------+
| Integrity Posture Strip: Execution [BLOCKED] | Rules [72 Blockers / 15 Cats] |
| Canonical Dataset [76 Equities / 496 Excluded] | Live LLM [DISABLED = 0]     |
+------------------------------------+-----------------------------------------+
| Competition Rule Blockers (15 cats)| Dataset & Equity-Only Manifest          |
| - 6 FAQ-evidenced (unverified)     | - 15,080 equity rows (202 sessions)     |
| - 9 Null categories (54 blockers)  | - 2,480 bond/debt/rights rows excluded  |
|                                    | - published_at_present_count: 0         |
+------------------------------------+-----------------------------------------+
| Account Sync & Movements Audit Log | Offline & Safety Guardrails             |
| - Out-of-order Nov 10 vs Nov 12    | - auto_order_submission: False          |
| - movements_page_captured: False   | - BVMT_ALLOW_LIVE_LLM: 0                |
+------------------------------------------------------------------------------+

[390px Mobile]
- Posture strip (2x2) -> Rule Blockers card -> Dataset Manifest card ->
  Sync Audit card -> Safety Guardrails card.
```

### Component Props & API Field Bindings
- `<RulesBlockerPanel>`: binds `rules_status`, `unresolved_blocker_count` (`72`), `categories: Array<{ name, status, missing_fields }>`.
- `<DatasetManifestCard>`: binds `v2_market_manifest` (`equity_instrument_count: 76`, `excluded_instrument_count: 496`, `equity_rows_kept: 15080`, `excluded_non_equity_rows: 2480`, `first_session: "2026-01-02"`, `last_session: "2026-11-18"`, `published_at_present_count: 0`).
- `<SyncAuditPanel>`: binds snapshot conflict history and `movements_page_captured` status.
