export type PortfolioMode = "REAL_COMPETITION" | "SYNTHETIC_DEMO";

export interface WebsiteReportedSummary {
  snapshot_id: string;
  capture_timestamp: string | null;
  live_synchronized: boolean;
  portfolio_total_tnd: string;
  available_cash_tnd: string;
  holdings_value_tnd: string;
  unrealized_pnl_tnd: string;
  overall_performance_pct: string;
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
  website_last_price_tnd: string;
  website_market_value_tnd: string;
  website_unrealized_pnl_tnd: string;
  website_unrealized_return_pct: string;
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

export interface SnapshotSummaryItem {
  snapshot_id: string;
  capture_timestamp: string | null;
  live_synchronized: boolean;
  portfolio_total_tnd: string;
  available_cash_tnd: string;
  holdings_count: number;
  competition_rank: number | null;
  competition_participants: number | null;
  overall_performance_pct: string;
  provenance: string;
}

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
  instrument_id: string;
  symbol: string;
  side: string;
  quantity: number;
  price_tnd: string;
  gross_amount_tnd: string;
  fee_tnd: string;
  executed_at: string;
  source: string;
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
  rank: number;
  instrument_id: string;
  symbol: string;
  close_tnd: string;
  short_return_pct: string;
  long_return_pct: string;
  volatility_pct: string;
  trade_frequency_pct: string;
  median_turnover_tnd: string;
  composite_score: string;
  eligible: boolean;
  eligibility_warnings: string[];
  recommendation_category: string;
  suggested_side: string | null;
  suggested_shares: number;
  blocked_reasons: string[];
  rationale: string;
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
}

export interface DocumentSearchResultItem {
  chunk_id: string;
  source_document_id: string;
  instrument_ids: string[];
  published_at: string;
  language: string;
  text: string;
  score: number;
}

export interface BacktestSummaryItem {
  label: string;
  window_start: string;
  window_end: string;
  sessions_count: number;
  buy_fee_pct: string;
  sell_fee_pct: string;
  full_year_marked_return_pct: string;
  full_year_liquidated_return_pct: string;
  benchmark_return_pct: string;
  max_drawdown_pct: string;
  competition_window_marked_return_pct: string;
  competition_window_liquidated_return_pct: string;
  walk_forward_folds: number;
  walk_forward_positive_folds: number;
  walk_forward_mean_return_pct: string;
  walk_forward_benchmark_pct: string;
  is_statistically_conclusive: boolean;
  methodology_note: string;
}

export interface ResearchResponse {
  query: string | null;
  verified_events: EventSignalItem[];
  document_results: DocumentSearchResultItem[];
  backtest_summary: BacktestSummaryItem;
}

export interface AlertItem {
  alert_id: string;
  category: string;
  severity: string;
  title: string;
  message: string;
  created_at: string;
  acknowledged: boolean;
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
  symbol: string;
  shares_before: number;
  shares_after: number;
  shares_delta: number;
  market_value_after_tnd: string;
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

export interface ConfirmSnapshotResponse {
  confirmed: boolean;
  overview: AccountOverviewResponse;
  reconciliation_summary: ReconciliationPreviewResponse;
}

export interface BrowserSyncTriggerResponse {
  status: string;
  captured_snapshot: BrowserSnapshotSummaryItem;
  preview: ReconciliationPreviewResponse;
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
