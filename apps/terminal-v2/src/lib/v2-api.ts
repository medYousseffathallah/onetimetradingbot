export type ValueStatus =
  | "OBSERVED"
  | "CALCULATED"
  | "SIMULATED"
  | "UNVERIFIED"
  | "UNAVAILABLE";

export type Horizon = "1_2" | "3_5" | "5_10" | "10_20" | "20_60";
export type Mode = "REAL_COMPETITION" | "SYNTHETIC_DEMO";
export type Universe = "TUNIS_BOURSE_CHALLENGE" | "FULL_BVMT_RESEARCH";

export type StockState =
  | "RESEARCH_CANDIDATE"
  | "WATCH"
  | "NO_CURRENT_EDGE"
  | "INSUFFICIENT_EVIDENCE"
  | "RESTRICTED"
  | "HELD_POSITION_REVIEW";

export type MonitoringState =
  | "HOLD"
  | "REVIEW"
  | "CONSIDER_TRIM"
  | "CONSIDER_EXIT"
  | "INSUFFICIENT_DATA"
  | "EXECUTION_BLOCKED";

export type ExecutionState = "EXECUTION_BLOCKED" | "ELIGIBLE_MANUAL_ONLY";

export interface ProvenanceValue {
  value: string | null;
  unit: string;
  status: ValueStatus;
  source: string;
  observation_time: string | null;
  calculation_time: string;
  missing_reason: string | null;
}

export interface Instrument {
  instrument_id: string;
  isin: string;
  symbol: string;
  challenge_member: boolean;
  order_entry_eligibility: "CONFIRMED" | "UNVERIFIED" | "BLOCKED" | "NOT_IN_UNIVERSE";
  market_mode: string;
  listed_from: string | null;
  listed_to: string | null;
  currency: "TND";
  sector: string | null;
}

export interface PriceProvenance {
  event_time: string | null;
  exchange_session: string;
  source_publication_time: string | null;
  first_observed_at: string | null;
  retrieved_at: string | null;
  ingested_at: string;
  validated_at: string;
  source_id: string;
  source_hash: string;
  data_quality_status:
    | "VERIFIED_PIT"
    | "EOD_UNVERIFIED_PUB_TIME"
    | "STALE_NO_TRADE"
    | "SUSPENDED"
    | "SYNTHETIC_FIXTURE"
    | "MISSING";
  historical_eod_close_tnd: ProvenanceValue;
  current_executable_quote_tnd: ProvenanceValue;
}

export interface MarketObservation {
  instrument_id: string;
  session_date: string;
  open_tnd: ProvenanceValue;
  high_tnd: ProvenanceValue;
  low_tnd: ProvenanceValue;
  close_tnd: ProvenanceValue;
  volume_shares: number;
  turnover_tnd: ProvenanceValue;
  status: string;
  provenance: PriceProvenance;
}

export interface ResearchEvidence {
  evidence_id: string;
  layer: "L1" | "L2" | "L3" | "L4" | "L5" | "L6" | "L7" | "L8" | "L9" | "L10";
  polarity: "SUPPORTING" | "CONTRADICTING" | "MISSING";
  summary: string;
  metric_value: ProvenanceValue | null;
  provenance_status: ValueStatus;
  source: string;
}

export interface ExecutionFeasibility {
  can_plan_manual_order: boolean;
  available_unreserved_shares: number | null;
  liquidity_cap_shares_10pct: number | null;
  blockers: string[];
  automatic_submission_enabled: false;
}

export interface StockAssessment {
  exchange_session: string | null;
  historical_eod_close_tnd: ProvenanceValue;
  current_executable_quote_tnd: ProvenanceValue;
  instrument: Instrument;
  research_date: string;
  cutoff_utc: string;
  horizon: Horizon;
  state: StockState;
  hypothesis: string;
  supporting_evidence: ResearchEvidence[];
  contradicting_evidence: ResearchEvidence[];
  missing_evidence: ResearchEvidence[];
  layers: Record<string, ResearchEvidence[]>;
  technical_state: Record<string, ProvenanceValue>;
  fundamental_state: ProvenanceValue;
  event_context: string[];
  liquidity_status: string;
  execution_feasibility: ExecutionFeasibility;
  portfolio_suitability: Record<string, string>;
  risk_scenarios: string[];
  horizon_support_status: string;
  model_version: string;
  next_review_condition: string;
}

export interface InvestmentThesis {
  instrument_id: string;
  thesis: string;
  horizon_sessions: number | null;
  invalidation_conditions: string[];
  recorded_at: string | null;
  origin: "HUMAN_REVIEW_NOTE" | "UNVERIFIED_NONE";
}

export interface OpportunityCandidate {
  assessment: StockAssessment;
  challenge_eligible: boolean;
  adv_20s_tnd: ProvenanceValue;
  ten_pct_adv_shares: ProvenanceValue;
  research_priority_rank: number | null;
}

export interface Holding {
  displayed_acquisition_amount_tnd: ProvenanceValue | null;
  instrument_id: string;
  isin: string | null;
  symbol: string;
  quantity: number;
  displayed_avg_cost_tnd: ProvenanceValue;
  displayed_price_tnd: ProvenanceValue;
  displayed_value_tnd: ProvenanceValue;
  displayed_unrealized_pnl_tnd: ProvenanceValue;
  verified_cost_basis_tnd: ProvenanceValue;
  eod_reference_close_tnd: ProvenanceValue;
}

export interface PortfolioSnapshot {
  snapshot_id: string;
  captured_at: string | null;
  source_id: string;
  equity_tnd: ProvenanceValue;
  cash_tnd: ProvenanceValue;
  holdings_value_tnd: ProvenanceValue;
  rank: number | null;
  total_participants: number | null;
  verification_status: ValueStatus;
  holdings: Holding[];
  reported_holdings_count: number | null;
  return_pct: ProvenanceValue | null;
}

export interface RiskAssessment {
  position_weight: ProvenanceValue;
  max_single_stock_weight: ProvenanceValue;
  concentration_breach: boolean | null;
  liquidity_days_to_exit: ProvenanceValue;
  volatility_20s: ProvenanceValue;
  downside_stress_tnd: ProvenanceValue;
  risk_budget_breached: boolean | null;
}

export interface PositionDecision {
  instrument_id: string;
  monitoring_state: MonitoringState;
  execution_state: ExecutionState;
  blockers: string[];
  explanation: string;
  next_review_trigger: string;
  exit_scenarios: string[];
  risk: RiskAssessment | null;
  thesis: InvestmentThesis | null;
  realized_pnl_tnd: ProvenanceValue | null;
  unrealized_pnl_tnd: ProvenanceValue | null;
}

export interface ManualTradeScenario {
  downside_loss_tnd: ProvenanceValue | null;
  side: "BUY" | "SELL" | "PROTECTION";
  instrument_id: string;
  quantity: number;
  limit_price_tnd: ProvenanceValue;
  gross_tnd: ProvenanceValue;
  estimated_fee_tnd: ProvenanceValue;
  stress_proceeds_tnd: ProvenanceValue;
  post_trade_weight: ProvenanceValue;
  post_trade_cash_tnd: ProvenanceValue;
  is_valid: boolean;
  rejection_reasons: string[];
  is_executed: false;
}

export interface ModelExperiment {
  experiment_id: string;
  family: string;
  horizon: number;
  scope: string;
  fold_count: number;
  net_return_pct: ProvenanceValue;
  liquidated_return_pct: ProvenanceValue;
  alpha_vs_cash_pct: ProvenanceValue;
  alpha_vs_ew_pct: ProvenanceValue;
  max_drawdown_pct: ProvenanceValue;
  top1_excluded_return_pct: ProvenanceValue;
  top1_excluded_instrument: string | null;
  turnover_pct: ProvenanceValue;
  active_utilization_pct: ProvenanceValue;
  fees_paid_tnd: ProvenanceValue;
  win_rate: ProvenanceValue;
  sample_count: number;
  provenance_status: ValueStatus;
  limitations: string[];
  config_hash: string;
  data_hash: string;
  source_hash: string;
  trial_count: number;
}

export interface SignalJournal {
  forecast_session: string | null;
  journal_id: string;
  recorded_at: string;
  instrument_id: string;
  action_state: string;
  horizon: Horizon;
  frozen_hash: string;
  outcome_status: string;
}

export interface PhaseSensitivity {
  phase_returns: ProvenanceValue[];
  minimum: ProvenanceValue;
  p25: ProvenanceValue;
  median: ProvenanceValue;
  p75: ProvenanceValue;
  maximum: ProvenanceValue;
  iqr_pp: ProvenanceValue;
}

export interface ExitComparison {
  net_return_pct: ProvenanceValue;
  max_drawdown_pct: ProvenanceValue;
  profit_retention_pct: ProvenanceValue;
  false_exit_rate_pct: ProvenanceValue;
  missed_subsequent_upside_pct: ProvenanceValue;
  feasibility_pct: ProvenanceValue;
  sample_count: number;
  exit_opportunities: number;
}

export interface PerformanceAttribution {
  period_start: string;
  period_end: string;
  starting_equity_tnd: ProvenanceValue;
  ending_equity_tnd: ProvenanceValue;
  total_return_pct: ProvenanceValue;
  realized_pnl_tnd: ProvenanceValue;
  unrealized_pnl_tnd: ProvenanceValue;
  unexplained_residual_tnd: ProvenanceValue;
  cash_drag_pct: ProvenanceValue;
  estimated_fees_tnd: ProvenanceValue;
  position_attributions: Record<string, Record<string, ProvenanceValue>>;
  benchmarks: Record<string, ProvenanceValue>;
  failure_tags: string[];
}

export interface HealthResponse {
  mode: Mode;
  status: string;
  execution_enabled: boolean;
  automatic_submission_enabled: boolean;
  llm_live_enabled: boolean;
  rules_blocker_count: number;
  latest_session: string | null;
  session_count: number;
  equity_instruments: number;
  challenge_members: number;
  rejected_non_equity_count: number;
  upstream_excluded_non_equity_count: number;
  published_at_present_count: number;
}

export interface OverviewResponse extends HealthResponse {
  account_state_conflict: boolean;
  current: PortfolioSnapshot;
  equity_by_source: Record<string, ProvenanceValue>;
  latest_market_session: string | null;
  market_instruments: number;
}

export interface PortfolioResponse extends HealthResponse {
  account_state_conflict: boolean;
  current: PortfolioSnapshot;
  snapshots: Record<string, PortfolioSnapshot>;
  rejected_captures: string[];
}

export interface DiscoveryResponse {
  mode: Mode;
  universe: Universe;
  horizon: Horizon;
  candidates: OpportunityCandidate[];
}

export interface StockBarsResponse {
  mode: Mode;
  instrument: Instrument;
  bars: MarketObservation[];
}

export interface ResearchLabResponse {
  mode: Mode;
  simulation_mode?: "STRICT_PIT" | "RETROSPECTIVE_EXPLORATORY" | "SYNTHETIC_DEMO";
  classification: string;
  families: string[];
  exit_policies: string[];
  signal_journal: SignalJournal[];
  experiments: ModelExperiment[];
  phase_sensitivity: Record<string, PhaseSensitivity>;
  exit_instrument_id: string | null;
  exit_policy_comparison: Record<string, ExitComparison>;
  limitations: string[];
  tunindex: ProvenanceValue;
}

export interface ScenarioRequest {
  instrument_id: string;
  quantity: number;
  limit_price_tnd: string;
  mode?: Mode;
}

export class V2ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(`API ${status}: ${detail}`);
    this.status = status;
    this.detail = detail;
  }
}

const API_BASE = process.env.NEXT_PUBLIC_V2_API_BASE ?? "";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    let detail = response.statusText || "Request failed";
    try {
      const parsed = (await response.json()) as { detail?: unknown };
      if (typeof parsed.detail === "string") {
        detail = parsed.detail;
      } else if (Array.isArray(parsed.detail)) {
        detail = parsed.detail
          .map((item) =>
            typeof item === "object" && item && "msg" in item
              ? String((item as { msg: unknown }).msg)
              : JSON.stringify(item),
          )
          .join("; ");
      }
    } catch {
      // keep statusText
    }
    throw new V2ApiError(response.status, detail);
  }

  return (await response.json()) as T;
}

export const v2Api = {
  getHealth(mode: Mode): Promise<HealthResponse> {
    return requestJson(`/api/v2/health?mode=${encodeURIComponent(mode)}`);
  },
  getOverview(mode: Mode): Promise<OverviewResponse> {
    return requestJson(`/api/v2/overview?mode=${encodeURIComponent(mode)}`);
  },
  getPortfolio(mode: Mode): Promise<PortfolioResponse> {
    return requestJson(`/api/v2/portfolio?mode=${encodeURIComponent(mode)}`);
  },
  getPosition(instrumentId: string, mode: Mode): Promise<PositionDecision> {
    return requestJson(
      `/api/v2/positions/${encodeURIComponent(instrumentId)}?mode=${encodeURIComponent(mode)}`,
    );
  },
  getDiscovery(
    mode: Mode,
    universe: Universe = "TUNIS_BOURSE_CHALLENGE",
    horizon: Horizon = "5_10",
  ): Promise<DiscoveryResponse> {
    return requestJson(
      `/api/v2/discovery?mode=${encodeURIComponent(mode)}&universe=${encodeURIComponent(universe)}&horizon=${encodeURIComponent(horizon)}`,
    );
  },
  getStock(
    instrumentId: string,
    mode: Mode,
    horizon: Horizon = "5_10",
  ): Promise<StockAssessment> {
    return requestJson(
      `/api/v2/stocks/${encodeURIComponent(instrumentId)}?mode=${encodeURIComponent(mode)}&horizon=${encodeURIComponent(horizon)}`,
    );
  },
  getStockBars(
    instrumentId: string,
    mode: Mode,
    limit = 60,
  ): Promise<StockBarsResponse> {
    return requestJson(
      `/api/v2/stocks/${encodeURIComponent(instrumentId)}/bars?mode=${encodeURIComponent(mode)}&limit=${limit}`,
    );
  },
  postBuyScenario(payload: ScenarioRequest): Promise<ManualTradeScenario> {
    return requestJson(`/api/v2/decisions/buy-scenario`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  postSellScenario(payload: ScenarioRequest): Promise<ManualTradeScenario> {
    return requestJson(`/api/v2/positions/sell-scenario`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  postProtectionScenario(payload: ScenarioRequest): Promise<ManualTradeScenario> {
    return requestJson(`/api/v2/positions/protection-scenario`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  getAttribution(mode: Mode): Promise<PerformanceAttribution> {
    return requestJson(`/api/v2/attribution?mode=${encodeURIComponent(mode)}`);
  },
  getResearchLab(
    mode: Mode,
    horizon: 5 | 10 | 20 = 10,
    exitInstrumentId?: string,
    simulationMode: "STRICT_PIT" | "RETROSPECTIVE_EXPLORATORY" = "STRICT_PIT",
  ): Promise<ResearchLabResponse> {
    const exitParam = exitInstrumentId
      ? `&exit_instrument_id=${encodeURIComponent(exitInstrumentId)}`
      : "";
    return requestJson(
      `/api/v2/research-lab?mode=${encodeURIComponent(mode)}&horizon=${horizon}&simulation_mode=${encodeURIComponent(simulationMode)}${exitParam}`,
    );
  },
};
