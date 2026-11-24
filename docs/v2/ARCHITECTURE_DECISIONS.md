# BVMT Trading Intelligence V2 — Architecture Decisions & Versioned Contracts

**Status**: Proposed Baseline for Gate 1 -> Binding once Codex Task 1 begins.  
**Boundary**: `src/bvmt_v2/` + `apps/terminal-v2/` + `tests_v2/` + `research/experiments-v2/` inside `bvmt-v2`. Zero imports from legacy `bvmt.strategies` or `bvmt.research_scoring` (no Model G carryover). Legacy `bvmt.challenge_universe` canonical registry and `bvmt.snapshots` atomic file helpers may be referenced only as documented, source-checked adapters or mirrored cleanly in `bvmt_v2`.

---

## ADR-001: Equity-Only Canonical Market Boundary (`data/v2_market/`)
- **Problem in V1**: `daily_bars.canonical.csv` (`17,560` rows) mixed `76` equities (`15,080` rows) with `496` bond, debt, and subscription-right instruments (`2,480` rows such as `AB0528_7.0_AP20`, `MPBS_DA1_*`, `UIB0133_*`) ingested between `2026-11-04` and `2026-11-10`.
- **Decision**: `bvmt_v2.market_data` strictly restricts universe loading to instruments listed in the dated equity `instrument_master.csv` (`76` equities). Any non-equity row encountered in a source file is counted and rejected into an explicit rejection summary rather than silently entering rankings or benchmarks.

## ADR-002: Monetary Precision & Mandatory 5-State Provenance Tagging
Every numeric financial output serialized by `src/bvmt_v2/contracts.py` uses `Decimal` strings (never binary floats) and carries a `ProvenanceValue` envelope:
- `value`: `str | int | None` (never zero-filled when missing)
- `unit`: `"TND" | "SHARES" | "PCT" | "RATIO" | "BPS" | "SESSIONS"`
- `status`: `ValueStatus = Literal["OBSERVED", "CALCULATED", "SIMULATED", "UNVERIFIED", "UNAVAILABLE"]`
- `source`: explicit source identifier (`ext_1794476128406`, `bvmt_official_2026`, `user_screenshot_unverified`, `v2_backtest_sim`, etc.)
- `observation_time`: ISO-8601 UTC timestamp or `None`
- `calculation_time`: ISO-8601 UTC cutoff timestamp
- `missing_reason`: `str | None`

## ADR-003: 10-Field Market Observation Provenance
Every `MarketObservation` and `PriceProvenance` separates:
1. `event_time` (`session_date` or `None`)
2. `exchange_session` (`YYYY-MM-DD`)
3. `source_publication_time` (`None` when official BVMT archive omits it — NEVER fabricated)
4. `first_observed_at` (earliest UTC capture/ingestion time)
5. `retrieved_at` (UTC gateway fetch time)
6. `ingested_at` (UTC canonical CSV write time)
7. `validated_at` (UTC schema validation time)
8. `source_id`
9. `source_hash` (SHA-256 prefix)
10. `data_quality_status` (`VERIFIED_PIT` | `EOD_UNVERIFIED_PUB_TIME` | `STALE_NO_TRADE` | `SUSPENDED` | `SYNTHETIC_FIXTURE` | `MISSING`)

In addition, every price display distinguishes:
- `historical_eod_close_tnd` (`OBSERVED` historical session close when `ingested_at <= cutoff`)
- `current_executable_quote_tnd` (`UNAVAILABLE` in EOD-only mode — never inferred from EOD closes)

## ADR-004: All 18 Typed Domain Contracts (`src/bvmt_v2/contracts.py`)
1. `Instrument` (`instrument_id`, `isin`, `symbol`, `challenge_member`, `order_entry_eligibility`, `market_mode`, `listed_from`, `listed_to`, `currency`)
2. `PriceProvenance` (the 10 provenance fields + `historical_eod_close_tnd` vs `current_executable_quote_tnd`)
3. `MarketObservation` (`instrument_id`, `session_date`, `open_tnd`, `high_tnd`, `low_tnd`, `close_tnd`, `volume_shares`, `turnover_tnd`, `status`, `provenance`)
4. `ResearchEvidence` (`evidence_id`, `layer`, `polarity` (`SUPPORTING`|`CONTRADICTING`|`MISSING`), `summary`, `metric_value`, `provenance_status`, `source`)
5. `StockAssessment` (10-layer structured decomposition `L1..L10`: `instrument`, `research_date`, `cutoff_utc`, `horizon`, `state` (`RESEARCH_CANDIDATE`|`WATCH`|`NO_CURRENT_EDGE`|`INSUFFICIENT_EVIDENCE`|`RESTRICTED`|`HELD_POSITION_REVIEW`), `hypothesis`, `supporting_evidence`, `contradicting_evidence`, `missing_evidence`, `technical_state`, `fundamental_state`, `event_context`, `liquidity_status`, `execution_feasibility`, `portfolio_suitability`, `risk_scenarios`, `model_version`, `next_review_condition`)
6. `InvestmentThesis` (`instrument_id`, `thesis`, `horizon_sessions`, `invalidation_conditions`, `recorded_at`, `origin` (`HUMAN_REVIEW_NOTE`|`UNVERIFIED_NONE`))
7. `OpportunityCandidate` (`assessment`, `challenge_eligible`, `adv_20s_tnd`, `ten_pct_adv_shares`, `research_priority_rank`)
8. `PortfolioSnapshot` (`snapshot_id`, `captured_at`, `source_id`, `equity_tnd`, `cash_tnd`, `holdings_value_tnd`, `rank`, `total_participants`, `verification_status`, `holdings`)
9. `Holding` (`instrument_id`, `isin`, `symbol`, `quantity`, `displayed_avg_cost_tnd`, `displayed_price_tnd`, `displayed_value_tnd`, `displayed_unrealized_pnl_tnd`, `verified_cost_basis_tnd`, `eod_reference_close_tnd`)
10. `Transaction` (`transaction_id`, `instrument_id`, `side`, `quantity`, `price_tnd`, `fee_tnd`, `executed_at`, `verification_status`)
11. `PendingOrder` (`order_id`, `instrument_id`, `side`, `remaining_shares`, `limit_price_tnd`, `submitted_at`, `status`)
12. `RiskAssessment` (`position_weight`, `max_single_stock_weight`, `concentration_breach`, `liquidity_days_to_exit`, `volatility_20s`, `downside_stress_tnd`, `risk_budget_breached`)
13. `PositionDecision` (`monitoring_state` (`HOLD`|`REVIEW`|`CONSIDER_TRIM`|`CONSIDER_EXIT`|`INSUFFICIENT_DATA`), `execution_state` (`EXECUTION_BLOCKED`|`ELIGIBLE_MANUAL_ONLY`), `blockers`, `explanation`, `next_review_trigger`, `exit_scenarios`)
14. `ExecutionFeasibility` (`can_plan_manual_order`, `available_unreserved_shares`, `liquidity_cap_shares_10pct`, `blockers`, `automatic_submission_enabled=False`)
15. `ManualTradeScenario` (`side`, `instrument_id`, `quantity`, `limit_price_tnd`, `gross_tnd`, `estimated_fee_tnd`, `stress_proceeds_tnd`, `post_trade_weight`, `post_trade_cash_tnd`, `is_valid`, `rejection_reasons`, `is_executed=False`)
16. `ModelExperiment` (`experiment_id`, `family`, `horizon`, `scope`, `fold_count`, `net_return_pct`, `alpha_vs_cash_pct`, `alpha_vs_ew_pct`, `max_drawdown_pct`, `top1_excluded_return_pct`, `turnover_pct`, `fees_paid_tnd`, `win_rate`, `sample_count`, `provenance_status`, `limitations`)
17. `SignalJournal` (`journal_id`, `recorded_at`, `instrument_id`, `action_state`, `horizon`, `frozen_hash`, `outcome_status`)
18. `PerformanceAttribution` (`period_start`, `period_end`, `starting_equity_tnd`, `ending_equity_tnd`, `total_return_pct`, `realized_pnl_tnd`, `unrealized_pnl_tnd`, `unexplained_residual_tnd`, `cash_drag_pct`, `estimated_fees_tnd`, `position_attributions`, `benchmarks`, `failure_tags`)

## ADR-005: Versioned `/api/v2/*` REST Contract
All endpoints live under `/api/v2/` on `127.0.0.1`, accept `mode=REAL_COMPETITION|SYNTHETIC_DEMO`, return `ProvenanceValue` objects cleanly serialized to JSON, and contain zero endpoints capable of modifying `real_competition_ledger.json` or placing exchange orders:
- `GET /api/v2/overview?mode=...`
- `GET /api/v2/portfolio?mode=...`
- `GET /api/v2/positions/{instrument_id}?mode=...`
- `GET /api/v2/discovery?mode=...&universe=TUNIS_BOURSE_CHALLENGE|FULL_BVMT_RESEARCH&horizon=1_2|3_5|5_10|10_20|20_60`
- `GET /api/v2/stocks/{instrument_id}?mode=...&horizon=...`
- `POST /api/v2/decisions/buy-scenario`
- `POST /api/v2/positions/sell-scenario`
- `POST /api/v2/positions/protection-scenario`
- `GET /api/v2/attribution?mode=...`
- `GET /api/v2/research-lab?mode=...`
- `GET /api/v2/health?mode=...`
