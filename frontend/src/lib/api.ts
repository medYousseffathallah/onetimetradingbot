export type PortfolioMode = "REAL_COMPETITION" | "SYNTHETIC_DEMO";

export interface WebsiteReportedSummary {
  snapshot_id: string | null;
  capture_timestamp: string | null;
  live_synchronized: boolean;
  portfolio_total_tnd: string | null;
  available_cash_tnd: string | null;
  holdings_value_tnd: string | null;
  unrealized_pnl_tnd: string | null;
  overall_performance_pct: string | null;
  competition_rank: number | null;
  competition_participants: number | null;
  competition_window: string | null;
}

export interface LocalValuationSummary {
  total_equity_tnd: string;
  cash_tnd: string;
  holdings_market_value_tnd: string;
  realized_pnl_tnd: string;
  unrealized_pnl_tnd: string;
  total_fees_paid_tnd: string;
  return_pct: string;
  latest_market_session: string | null;
  data_is_synthetic: boolean;
}

export interface SyncStatusSummary {
  live_synchronized: boolean;
  is_stale: boolean;
  last_sync_timestamp: string | null;
  latest_market_session: string | null;
  warning_message: string | null;
  has_pending_snapshot: boolean;
  pending_snapshot_timestamp: string | null;
  pending_snapshot_total_tnd: string | null;
  pending_snapshot_rank: number | null;
}

export interface MarketDataStatusSummary {
  dataset_label: string;
  source_ids: string[];
  latest_session_date: string | null;
  first_session_date: string | null;
  total_bars: number;
  unique_sessions: number;
  unique_instruments: number;
  is_synthetic: boolean;
  retrieved_at: string | null;
  sessions_behind: number;
}

export interface AccountOverviewResponse {
  portfolio_mode: PortfolioMode;
  website_reported: WebsiteReportedSummary;
  local_valuation: LocalValuationSummary;
  sync_status: SyncStatusSummary;
  market_status: MarketDataStatusSummary;
  active_alerts_count: number;
  actionable_recommendations_count: number;
}

export interface HoldingItem {
  instrument_id: string;
  symbol: string;
  isin: string | null;
  quantity: number;
  acquisition_price_tnd: string;
  acquisition_amount_tnd: string;
  website_last_price_tnd: string | null;
  website_market_value_tnd: string | null;
  website_unrealized_pnl_tnd: string | null;
  website_unrealized_return_pct: string | null;
  verified_market_price_tnd: string | null;
  verified_market_value_tnd: string | null;
  price_drift_tnd: string | null;
  weight_pct: string;
}

export interface HoldingsResponse {
  portfolio_mode: PortfolioMode;
  snapshot_id: string | null;
  capture_timestamp: string | null;
  live_synchronized: boolean;
  available_cash_tnd: string;
  portfolio_total_tnd: string;
  holdings: HoldingItem[];
}

export type SnapshotSummaryItem = WebsiteReportedSummary;

export interface BrowserSnapshotSummaryItem {
  retrieved_at: string;
  portfolio_total_tnd: string;
  available_cash_tnd: string;
  holdings_market_value_tnd: string;
  holdings_count: number;
  competition_rank: number | null;
  total_participants: number | null;
  displayed_overall_performance_pct: string | null;
  is_reconciled: boolean;
  reconciliation_gap_tnd: string;
  is_confirmed: boolean;
}

export interface SnapshotsResponse {
  confirmed_history: SnapshotSummaryItem[];
  unconfirmed_browser_snapshots: BrowserSnapshotSummaryItem[];
  pending_confirmation: BrowserSnapshotSummaryItem | null;
}

export interface TransactionItem {
  transaction_id: string;
  order_id: string;
  instrument_id: string;
  symbol: string;
  side: string;
  filled_shares: number;
  execution_price_tnd: string;
  fee_tnd: string;
  executed_at: string;
  source: string;
  source_timestamp: string | null;
  is_confirmed: boolean;
}

export interface TransactionsResponse {
  transactions: TransactionItem[];
}

export interface PendingOrderItem {
  order_id: string;
  instrument_id: string;
  symbol: string;
  side: string;
  requested_shares: number;
  filled_shares: number;
  remaining_shares: number;
  limit_price_tnd: string;
  status: string;
  submitted_at: string;
  source: string;
  source_timestamp: string | null;
  is_confirmed: boolean;
}

export interface PendingOrdersResponse {
  pending_orders: PendingOrderItem[];
}

export interface DatasetOptionItem {
  label: string;
  is_synthetic: boolean;
  is_active: boolean;
}

export interface MarketDataStatusResponse {
  market_status: MarketDataStatusSummary;
  coverage_summary: Record<string, unknown>;
  available_datasets: DatasetOptionItem[];
}

export interface StockRankingItem {
  rank: number | null;
  instrument_id: string;
  symbol: string;
  close_tnd: string | null;
  short_return_pct: string | null;
  long_return_pct: string | null;
  volatility_pct: string | null;
  trade_frequency_pct: string | null;
  median_turnover_tnd: string | null;
  composite_score: number | null;
  eligible: boolean;
  eligibility_warnings: string[];
  recommendation_category: string;
  suggested_side: string | null;
  suggested_shares: number;
  blocked_reasons: string[];
  rationale: string[];
}

export interface StockRankingsResponse {
  as_of: string;
  session_date: string | null;
  data_is_synthetic: boolean;
  simulation_profile: string;
  rankings: StockRankingItem[];
}

export interface EventSignalItem {
  event_id: string;
  instrument_id: string;
  published_at: string;
  event_type: string;
  polarity: string;
  summary: string;
  verbatim_quote: string;
  source_document_id: string;
  quote_verified: boolean;
  is_synthetic: boolean;
}

export interface DocumentSearchResultItem {
  chunk_id: string;
  source_document_id: string;
  instrument_ids: string[];
  published_at: string | null;
  ingested_at: string | null;
  section_locator: string;
  chunk_text: string;
  score: number | null;
  method: string;
  is_synthetic: boolean;
}

export interface BacktestSummaryItem {
  label: string;
  status: "available" | "unavailable";
  source_label: string | null;
  generated_at: string | null;
  start_session: string | null;
  end_session: string | null;
  session_count: number | null;
  total_return_pct: string | null;
  liquidated_total_return_pct: string | null;
  equal_weight_benchmark_return_pct: string | null;
  max_drawdown_pct: string | null;
  walk_forward_total_folds: number | null;
  walk_forward_mean_fold_return_pct: string | null;
  walk_forward_mean_liquidated_return_pct: string | null;
  walk_forward_mean_benchmark_return_pct: string | null;
  walk_forward_positive_fold_ratio: string | null;
  is_statistically_conclusive: boolean | null;
  limitations: string[];
}

export interface WalkForwardFoldItem {
  fold_index: number;
  train_start: string;
  train_end: string;
  test_start: string;
  test_end: string;
  train_sessions: number;
  test_sessions: number;
  strategy_return_pct: number;
  liquidated_return_pct: number;
  benchmark_return_pct: number;
  excess_return_pct: number;
  fill_count: number;
  fees_tnd: number;
}

export interface WalkForwardSummary {
  train_sessions: number;
  test_sessions: number;
  step_sessions: number;
  total_folds: number;
  positive_folds: number;
  mean_fold_return_pct: number | null;
  mean_liquidated_return_pct: number | null;
  mean_excess_return_pct: number | null;
  classification: string;
  folds: WalkForwardFoldItem[];
}

export interface SensitivityScenarioItem {
  commission_bps: number;
  max_volume_participation: number;
  net_return_pct: number;
  liquidated_return_pct: number;
  total_fees_tnd: number;
  trade_count: number;
}

export interface FeeAndLiquiditySensitivity {
  scenarios: SensitivityScenarioItem[];
  min_return_pct: number;
  max_return_pct: number;
  method: string;
}

export interface EquityCurvePoint {
  session_date: string;
  total_equity_tnd: number;
  cash_tnd: number;
  holdings_value_tnd: number;
  drawdown_pct: number;
  benchmark_equity_tnd: number;
}

export interface WinLossSummary {
  winning_positions: number;
  losing_positions: number;
  flat_positions: number;
  best_position_return_pct: number | null;
  worst_position_return_pct: number | null;
  definition: string;
}

export interface SubperiodMetric {
  start_session: string;
  end_session: string;
  return_pct: number;
}

export interface BootstrapConfidenceInterval {
  lower_pct: number;
  upper_pct: number;
  resamples: number;
  block_size: number;
  method: string;
}

export interface RiskNormalizedMetrics {
  active_session_count: number;
  active_cash_utilization_pct: number;
  exposure_normalized_return_pct: number;
  exposure_normalized_liquidated_return_pct: number;
  exposure_normalized_max_drawdown_pct: number;
  realized_annualized_volatility_pct: number;
  return_to_volatility_ratio: number;
  excess_vs_c_marked_pct: number;
  excess_vs_c_liquidated_pct: number;
  excess_vs_b_marked_pct: number;
  excess_vs_b_liquidated_pct: number;
  cash_matched_benchmark_b_return_pct: number;
  excess_vs_cash_matched_b_pct: number;
  equal_budget_10slot_net_return_pct: number;
  equal_budget_10slot_liquidated_return_pct: number;
  equal_budget_10slot_max_drawdown_pct: number;
  equal_budget_10slot_active_utilization_pct: number;
  continuous_concentration_trim_net_return_pct: number;
  continuous_concentration_trim_max_weight_pct: number;
  top_winner_instrument_id: string | null;
  top_winner_net_pnl_tnd: number;
  ex_top_winner_net_return_pct: number;
  subperiods: Record<string, SubperiodMetric>;
  bootstrap_return_ci_95: BootstrapConfidenceInterval;
}

export interface AuditSummary {
  model_g_audit_status: string;
  model_g_promotion_eligible: boolean;
  key_findings: string[];
}

export interface PaperOrderRecord {
  order_id: string;
  snapshot_id: string;
  strategy_id: string;
  instrument_id: string;
  side: "buy" | "sell";
  signal_session_date: string;
  signal_close_price_tnd: string;
  requested_shares: number;
  filled_shares: number;
  remaining_shares: number;
  status:
    | "PENDING_NEXT_SESSION"
    | "FILLED"
    | "PARTIALLY_FILLED"
    | "EXPIRED"
    | "BLOCKED_ZERO_VOLUME";
  execution_session_date: string | null;
  execution_price_tnd: string | null;
  fee_tnd: string;
  notes: string;
}

export interface PaperSignalSnapshot {
  snapshot_id: string;
  strategy_id: string;
  model_version: string;
  config_hash: string;
  code_sha256: string;
  data_hash: string;
  signal_timestamp: string;
  market_data_session_date: string;
  intended_orders: PaperOrderRecord[];
}

export interface PaperEquityPoint {
  session_date: string;
  total_equity_tnd: number;
  cash_tnd: number;
  holdings_value_tnd: number;
  drawdown_pct: number;
  cash_benchmark_equity_tnd: number;
  equal_weight_benchmark_equity_tnd: number;
}

export interface PaperJournalState {
  journal_id: string;
  is_paper_only: boolean;
  autonomous_trading_enabled: boolean;
  strategy_id: string;
  initial_cash_tnd: string;
  cash_tnd: string;
  holdings: Record<string, number>;
  average_cost_tnd: Record<string, string>;
  total_fees_tnd: string;
  notional_traded_tnd: string;
  total_equity_tnd: string;
  net_return_pct: number;
  max_drawdown_pct: number;
  turnover_ratio: number;
  latest_settled_session: string | null;
  signal_snapshots: PaperSignalSnapshot[];
  orders: PaperOrderRecord[];
  equity_history: PaperEquityPoint[];
}

export interface PaperTradingResponse {
  status: "available" | "unavailable" | "invalid";
  journal: PaperJournalState | null;
  limitations?: string[];
}

export interface StrategyEvaluationReport {
  strategy_id: string;
  name: string;
  version: string;
  family: "baseline" | "enhanced";
  implementation_status: string;
  sample_Classification: string;
  formula_summary: string;
  assumptions: Record<string, unknown>;
  failure_modes: string[];
  start_session: string;
  end_session: string;
  session_count: number;
  net_return_pct: number;
  liquidated_return_pct: number;
  benchmark_return_pct: number;
  excess_return_pct: number;
  max_drawdown_pct: number;
  turnover_ratio: number;
  total_fees_tnd: number;
  trade_count: number;
  order_count: number;
  hit_rate_pct: number;
  win_loss_Init_summary: WinLossSummary;
  avg_cash_utilization_pct: number;
  max_single_stock_weight_pct: number;
  walk_forward: WalkForwardSummary;
  fee_and_liquidity_sensitivity: FeeAndLiquiditySensitivity;
  equity_curve: EquityCurvePoint[];
  is_statistically_conclusive: boolean;
  promotion_status: string;
  config_hash: string;
  experiment_id: string;
  diagnostics: Record<string, unknown>;
  risk_normalized_metrics?: RiskNormalizedMetrics;
}

export interface MlPromotionGate {
  eligible: boolean;
  session_count: number;
  minimum_sessions: number;
  reason: string;
}

export interface HistoricalYearCoverage {
  canonical_sessions: number;
  instrument_count: number;
  daily_ohlcv_available: boolean;
  status: string;
}

export interface HistoricalAuditSummary {
  coverage_2020_2026: Record<string, HistoricalYearCoverage>;
  source_url: string | null;
  processed_at: string | null;
  archive_sha256: string | null;
  canonical_sha256: string | null;
  canonical_checksum_matches: boolean | null;
  instrument_count: number;
  corporate_actions_available: boolean;
  blockers: string[];
}

export interface StrategyExperimentRegistry {
  schema_version: string;
  status: string;
  data_hash: string;
  config_hash: string;
  code_sha256?: string;
  canonical_sha256?: string;
  trial_count: number;
  audit_summary?: AuditSummary;
  robustness_v2?: Record<string, unknown>;
  reports: StrategyEvaluationReport[];
  ml_promotion_gate: MlPromotionGate;
  historical_audit?: HistoricalAuditSummary;
  limitations: string[];
}

export interface StrategyLabResponse {
  status: "available" | "unavailable" | "invalid";
  registry: StrategyExperimentRegistry | null;
  limitations: string[];
}

export interface ResearchResponse {
  query: string | null;
  verified_events: EventSignalItem[];
  document_results: DocumentSearchResultItem[];
  backtest_summary: BacktestSummaryItem;
  strategy_comparison?: StrategyExperimentRegistry | null;
}

export interface AlertItem {
  alert_id: string;
  created_at_utc: string;
  session_date: string;
  category: string;
  severity: string;
  instrument_id: string | null;
  title: string;
  message: string;
  status: string;
}

export interface SystemHealthResponse {
  status: string;
  version: string;
  rule_blockers: string[];
  llm_status: Record<string, unknown>;
  alerts: AlertItem[];
  localhost_only: boolean;
  autonomous_trading_enabled: boolean;
}

export interface PositionDeltaItem {
  instrument_id: string;
  quantity_before: number;
  quantity_after: number;
  quantity_delta: number;
}

export interface ReconciliationPreviewResponse {
  has_pending: boolean;
  status_label: string;
  candidate_snapshot: BrowserSnapshotSummaryItem | null;
  cash_before_tnd: string;
  cash_after_tnd: string;
  cash_delta_tnd: string;
  equity_before_tnd: string;
  equity_after_tnd: string;
  position_deltas: PositionDeltaItem[];
  requires_confirmation: boolean;
}

export interface ReconciliationSummaryItem {
  evaluated_at: string;
  snapshot_as_of: string;
  is_reconciled: boolean;
  cash_delta_tnd: string;
  discrepancy_count: number;
}

export interface ConfirmSnapshotResponse {
  overview: AccountOverviewResponse;
  reconciliation_summary: ReconciliationSummaryItem;
}

export interface BrowserSyncTriggerResponse {
  captured_snapshot: BrowserSnapshotSummaryItem;
  reconciliation_preview: ReconciliationPreviewResponse;
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    let errDetail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body && body.detail) {
        errDetail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
      }
    } catch {
      // ignore
    }
    throw new Error(errDetail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getOverview: (mode: PortfolioMode = "REAL_COMPETITION") =>
    fetchJson<AccountOverviewResponse>(`/api/overview?mode=${mode}`),
  getHoldings: (mode: PortfolioMode = "REAL_COMPETITION") =>
    fetchJson<HoldingsResponse>(`/api/holdings?mode=${mode}`),
  getSnapshots: (mode: PortfolioMode = "REAL_COMPETITION") =>
    fetchJson<SnapshotsResponse>(`/api/snapshots?mode=${mode}`),
  getTransactions: (mode: PortfolioMode = "REAL_COMPETITION") =>
    fetchJson<TransactionsResponse>(`/api/transactions?mode=${mode}`),
  getPendingOrders: (mode: PortfolioMode = "REAL_COMPETITION") =>
    fetchJson<PendingOrdersResponse>(`/api/orders/pending?mode=${mode}`),
  getMarketStatus: (mode: PortfolioMode = "REAL_COMPETITION") =>
    fetchJson<MarketDataStatusResponse>(`/api/market-status?mode=${mode}`),
  getRankings: (mode: PortfolioMode = "REAL_COMPETITION") =>
    fetchJson<StockRankingsResponse>(`/api/rankings?mode=${mode}`),
  getResearch: (q = "", mode: PortfolioMode = "REAL_COMPETITION") =>
    fetchJson<ResearchResponse>(`/api/research?mode=${mode}&q=${encodeURIComponent(q)}`),
  getStrategyLab: () => fetchJson<StrategyLabResponse>(`/api/strategy-lab`),
  getPaperTrading: (strategyId = "G_LIQUIDITY_FILTERED_MOMENTUM") =>
    fetchJson<PaperTradingResponse>(
      `/api/paper-trading?strategy_id=${encodeURIComponent(strategyId)}`
    ),
  recordPaperSignal: (
    strategyId = "G_LIQUIDITY_FILTERED_MOMENTUM",
    asOfSession: string | null = null
  ) =>
    fetchJson<PaperTradingResponse>(`/api/paper-trading/record-signal`, {
      method: "POST",
      body: JSON.stringify({
        strategy_id: strategyId,
        as_of_session: asOfSession,
      }),
    }),
  getHealth: (mode: PortfolioMode = "REAL_COMPETITION") =>
    fetchJson<SystemHealthResponse>(`/api/health?mode=${mode}`),
  getSyncPreview: (mode: PortfolioMode = "REAL_COMPETITION") =>
    fetchJson<ReconciliationPreviewResponse>(`/api/sync/preview?mode=${mode}`),
  triggerBrowserSync: (timeoutSeconds = 180) =>
    fetchJson<BrowserSyncTriggerResponse>(`/api/sync/browser`, {
      method: "POST",
      body: JSON.stringify({ timeout_seconds: timeoutSeconds }),
    }),
  confirmSnapshot: (confirmedByUser: boolean) =>
    fetchJson<ConfirmSnapshotResponse>(`/api/sync/confirm`, {
      method: "POST",
      body: JSON.stringify({ confirmed_by_user: confirmedByUser }),
    }),
};
