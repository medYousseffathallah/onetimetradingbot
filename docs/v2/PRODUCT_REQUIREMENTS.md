# BVMT Trading Intelligence V2 — Product Requirements Document (PRD)

**Status**: Gate 1 UX Specification (`V2-UX1`)  
**Aligned Contracts**: [MASTER_PLAN.md](./MASTER_PLAN.md) · [ARCHITECTURE_DECISIONS.md](./ARCHITECTURE_DECISIONS.md) (18 Domain Contracts, 9 `/api/v2/*` Destinations)  
**Mode Boundary**: `100% Localhost` (`127.0.0.1`), `Human-Supervised Manual Decision Support Only`

---

## 1. Product Vision & Scope

BVMT Trading Intelligence V2 is a **calm, institutional-grade, localhost investment research and portfolio supervision terminal** built for the **Tunis Bourse Virtual Challenge** (`50,000.000 TND` initial virtual capital, 14th edition window `2026-10-01` to `2027-05-31`, `42` Challenge-eligible continuous equities) alongside **Full BVMT Equity Research** (`76` canonical equities across `202` sessions `2026-01-02..2026-11-18`, strictly excluding `496` bond/debt/rights instruments per `ADR-001`).

V2 replaces V1's fragmented scoring/ranking view with an **evidence-first investment workflow** where:
1. **Truth state is never ambiguous**: every number carries a `ProvenanceValue` status (`OBSERVED`, `CALCULATED`, `SIMULATED`, `UNVERIFIED`, `UNAVAILABLE`).
2. **Monitoring and execution are strictly decoupled**: a position can be flagged `REVIEW` or `CONSIDER_TRIM` while remaining `EXECUTION_BLOCKED` until competition rules, account reconciliation, and quote freshness blockers are resolved.
3. **Zero autonomous trading**: the terminal never submits orders, automates `bysell.aspx`, stores broker credentials, or mutates `real_competition_ledger.json` via unconfirmed captures.

---

## 2. User Personas

### Persona A — Primary Operator: Solo Competition Investor & Portfolio Supervisor
- **Context**: Operates locally on Windows/desktop (and occasionally checks reviews at `390px` mobile width). Manually enters orders on `tunisbourse-challenge.com` after reviewing evidence locally.
- **Core Needs**:
  - Know **exact account truth** without confusing a confirmed ledger (`2026-11-10` out-of-order overwrite), a newer DOM capture (`2026-11-12` `ext_1794476128406`), an unverified user screenshot, and EOD mark-to-market valuations.
  - Manage **open positions** (such as `EURO-CYCLES`, `DELICE HOLDING`, `MPBS`, `STA`) with explicit concentration-cap monitoring (`10.00%` limit), liquidity-aware exit sizing (`10%` ADV cap), and manual partial-sale / protection math.
  - Screen Challenge equities without being misled by non-Challenge stocks (`MONOPRIX`, `CIL`), bond rows, or `1e-6` volatility score explosions.
- **Pain Points in V1**: Unexplained gaps between realized and unrealized P&L, silent zero-filling of missing fundamentals, hidden competition rule blockers, and mixed `LIVE` vs stale EOD labels.

### Persona B — Research & Validation Reviewer
- **Context**: Audits quantitative hypotheses (`A–J` across `1–2`, `3–5`, `5–10`, `10–20`, `20–60` session horizons), walk-forward backtests, and PIT data integrity (`BVMT_ALLOW_LIVE_LLM=0`).
- **Core Needs**:
  - Compare V2 strategy families against **Cash**, **Equal-Weight (EW)**, **Buy-and-Hold**, and **Legacy Model G** with `top1_excluded_return_pct`, fees (`0.50%` buy/sell), max drawdown, and sample counts.
  - Inspect the 10-field `PriceProvenance` register (`ADR-003`) and verify `published_at_present_count = 0` is disclosed honestly rather than fabricated.

---

## 3. The 12 Core Investor Questions

Every UI module in V2 must directly answer one or more of these 12 core investor questions:

| # | Core Investor Question | Primary Destination | Primary Domain Contracts (`ADR-004`) |
|---|---|---|---|
| **Q1** | *What is my actual confirmed equity, cash, and rank—and how does it differ from newer captures, unverified screenshots, or EOD marks?* | 1. Investment Overview | `PortfolioSnapshot`, `ProvenanceValue` |
| **Q2** | *How much of my capital is sitting idle in cash (cash drag), and which positions or sync conflicts need attention first?* | 1. Investment Overview | `PortfolioSnapshot`, `PositionDecision`, `PerformanceAttribution` |
| **Q3** | *Which holdings, weights, cost bases, and pending orders are confirmed vs conflicted across snapshots?* | 2. Portfolio Manager | `PortfolioSnapshot`, `Holding`, `Transaction`, `PendingOrder` |
| **Q4** | *Am I breaching or approaching the 10% single-stock concentration cap or sector exposure limits?* | 2. Portfolio Manager / 6. Position Management | `Holding`, `RiskAssessment` |
| **Q5** | *Which Challenge-eligible equities deserve research today, separate from non-Challenge research equities?* | 3. Opportunity Discovery | `OpportunityCandidate`, `Instrument`, `StockAssessment` |
| **Q6** | *What evidence supports, contradicts, or is missing for a given issuer across technicals, liquidity, fundamentals, events, and regime?* | 4. Stock Research Workspace | `StockAssessment` (`L1..L10`), `ResearchEvidence`, `PriceProvenance` |
| **Q7** | *Can I verify when market data was observed vs published, and whether any quote is executable right now?* | 4. Stock Research / 9. Data & Account Health | `PriceProvenance`, `MarketObservation` |
| **Q8** | *If I consider a new manual BUY, what are the fees, post-trade weight, cash impact, and deterministic blockers?* | 5. Investment Decision Workspace | `InvestmentThesis`, `ExecutionFeasibility`, `ManualTradeScenario` |
| **Q9** | *For an existing holding like EURO-CYCLES, should I hold, review, trim, or exit—and what blocks execution right now?* | 6. Position Management | `PositionDecision`, `RiskAssessment`, `ExecutionFeasibility`, `ManualTradeScenario` |
| **Q10** | *How did my actual account perform over Nov 7–18, what drove P&L per stock, and why is there an unexplained residual?* | 7. Performance & Attribution | `PerformanceAttribution`, `Transaction` |
| **Q11** | *Do any quantitative models beat simple Cash, Equal-Weight, or Legacy Model G out-of-sample after 0.50% fees and outlier removal?* | 8. Research Lab | `ModelExperiment`, `SignalJournal` |
| **Q12** | *What exact rule, data, identity, or sync blockers prevent trustworthy planning or execution today?* | 9. Data & Account Health | `PriceProvenance`, `PortfolioSnapshot`, `ExecutionFeasibility` |

---

## 4. The 9 Product Destinations & API Mapping (`ADR-005`)

| # | Destination | Route | `/api/v2/*` Endpoint(s) | Key Contract Outputs |
|---|---|---|---|---|
| **1** | **Investment Overview** | `/` | `GET /api/v2/overview?mode=...` | Multi-truth summary (`confirmed_ledger`, `latest_capture`, `unverified_screenshot`, `eod_mark_estimate`), cash drag, review queue, top holdings snapshot |
| **2** | **Portfolio Manager** | `/portfolio` | `GET /api/v2/portfolio?mode=...` | Holdings table (`Holding`), sector/issuer weights, account conflict banner, `InvestmentThesis` & horizon columns, `Transaction` & `PendingOrder` audit |
| **3** | **Opportunity Discovery** | `/discovery` | `GET /api/v2/discovery?mode=...&universe=...&horizon=...` | Track-isolated screener (`TUNIS_BOURSE_CHALLENGE` 42 vs `FULL_BVMT_RESEARCH` 76), 5 horizons (`1_2..20_60`), `OpportunityCandidate`, liquidity & coverage gates |
| **4** | **Stock Research Workspace** | `/stocks/[instrument_id]` | `GET /api/v2/stocks/{instrument_id}?mode=...&horizon=...` | `StockAssessment` (`L1–L9` panels: Technical, Liquidity, Fundamental `[UNAVAILABLE]`, Events, Regime, Contradictions, Provenance Register) + EOD price/volume chart |
| **5** | **Investment Decision Workspace** | `/decisions` | `POST /api/v2/decisions/buy-scenario` (+ stock/portfolio context) | `InvestmentThesis`, `L1–L10` checklist, deterministic BUY feasibility & fee/weight impact simulator (`is_executed=False`) |
| **6** | **Position Management** | `/positions/[instrument_id]` | `GET /api/v2/positions/{instrument_id}?mode=...`<br>`POST /api/v2/positions/sell-scenario`<br>`POST /api/v2/positions/protection-scenario` | `PositionDecision` (`monitoring_state` vs `execution_state`), blockers, downside protection scenario, manual partial-sale calculator |
| **7** | **Performance & Attribution** | `/attribution` | `GET /api/v2/attribution?mode=...` | Nov 7–18 equity trajectory, cash drag, per-stock attribution, realized vs unrealized + unexplained residual gap (`+235.680 TND`), benchmark comparison (`Cash`, `EW`, `Legacy G`) |
| **8** | **Research Lab** | `/research-lab` | `GET /api/v2/research-lab?mode=...` | `ModelExperiment` table (hypotheses `A–J`), purged walk-forward folds, `top1_excluded_return_pct`, `SignalJournal`, explicit promotion gates |
| **9** | **Data & Account Health** | `/health` | `GET /api/v2/health?mode=...` | Competition rule blockers (`72` attribute blockers / `15` categories), dataset manifest (`76` equities / `496` rejected non-equities), sync conflict audit, `BVMT_ALLOW_LIVE_LLM=0` status |

---

## 5. Strict Safety, Honesty & Data-Integrity Requirements

1. **Manual-Only Execution (`automatic_submission_enabled = False`)**:
   - No button, form, or endpoint may submit an order to `tunisbourse-challenge.com` or simulate execution on the live competition ledger.
   - Every scenario calculator (`buy-scenario`, `sell-scenario`, `protection-scenario`) displays an explicit `SCENARIO ONLY — NOT AN ORDER` header and returns `is_executed: false`.
2. **Truth-State Provenance (`ADR-002`)**:
   - Every numeric financial value renders with its `ValueStatus` pill (`OBSERVED`, `CALCULATED`, `SIMULATED`, `UNVERIFIED`, `UNAVAILABLE`) or inside a column/section header that unambiguously binds that status.
   - `SIMULATED` and backtested returns must **never** share visual styling, chart lanes, or KPI slots with realized competition account profit.
3. **EOD Close != Live Executable Quote (`ADR-003`)**:
   - `historical_eod_close_tnd` is always stamped with `exchange_session` (e.g., `2026-11-18 EOD`) and `EOD_UNVERIFIED_PUB_TIME`.
   - `current_executable_quote_tnd` must explicitly display `UNAVAILABLE` in EOD-only mode—never inferred from the latest EOD close.
   - Zero fake `LIVE` badges, pulsing green dots, or countdown timers implying real-time exchange connectivity.
4. **Account Conflict & Non-Mutation Integrity**:
   - Confirmed ledger state (`browser_sync_20261110_110702`), newer unapplied DOM capture (`ext_1794476128406` on `2026-11-12`), and unverified user screenshots are rendered as **distinct, labeled columns/cards**—never silently averaged or auto-merged.
   - Unimported transaction history (`movements_page_captured = false`) forces `Pending Orders: UNVERIFIED` (never `0` assumed) and surfaces any unexplained residual P&L (`+235.680 TND`) directly.
5. **Missing Data Never Becomes Zero**:
   - Absent fundamentals (`ABSENT_NO_FILINGS`), absent `source_publication_time` (`published_at_present_count = 0`), or missing `TUNINDEX` series render as `UNAVAILABLE` with explicit `missing_reason`, never `0.000` or synthetic `10,000 TND`.
6. **Zero Raw Model IDs & Zero Paid External LLM Calls**:
   - Default views show human-readable strategy/family labels (e.g., `V2 Baseline — Momentum 20s`, `Legacy Model G Reference`), never raw internal model IDs or vendor model strings.
   - `BVMT_ALLOW_LIVE_LLM=0` and offline local mode status are surfaced in Data & Account Health.
7. **Mode Isolation (`REAL_COMPETITION` vs `SYNTHETIC_DEMO`)**:
   - Switching to `SYNTHETIC_DEMO` displays a persistent top-level sandbox banner across all 9 destinations and never shares state with `REAL_COMPETITION`.
