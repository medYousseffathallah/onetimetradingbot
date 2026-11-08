"""Typed localhost HTTP adapter for the canonical portfolio service.

Run with ``uvicorn bvmt.api:app --host 127.0.0.1``. Importing this module performs
no portfolio I/O, launches no browser and makes no network requests.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from html import unescape
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    SerializerFunctionWrapHandler,
    StrictBool,
    model_serializer,
)

from bvmt import __version__
from bvmt.browser import (
    AuthenticationExpiredError,
    BrowserCollectorError,
    CompetitionPortfolioDOMSnapshot,
    run_browser_sync_subprocess,
)
from bvmt.dashboard import DashboardAppState
from bvmt.data import inspect_market_dataset_provenance, read_bars_csv
from bvmt.ledger import CompetitionScreenshotSnapshot, ReconciliationReport
from bvmt.llm import search_document_index
from bvmt.paper_trading import (
    DATA_DIR,
    DEFAULT_JOURNAL_PATH,
    DEFAULT_STRATEGY,
    load_or_init_paper_journal,
    record_forward_paper_signal,
)
from bvmt.portfolio_service import PortfolioStateService

PortfolioMode = Literal["REAL_COMPETITION", "SYNTHETIC_DEMO"]
Money = Annotated[
    Decimal,
    PlainSerializer(lambda value: format(value.quantize(Decimal("0.001")), ".3f"), return_type=str),
]


def _plain_text(value: str) -> str:
    text = re.sub(r"(?is)<(script|style)\b[^>]*>.*?</\1>", "", unescape(value))
    text = re.sub(r"<[^>]*>", "", text)
    return re.sub(
        r"(?i)\b(password|authorization|cookies?|set-cookie|api[_-]?key|access_token|refresh_token)\b[\"']?\s*[:=][^\r\n]*",
        r"\1: [redacted]",
        text,
    )


PlainText = Annotated[str, PlainSerializer(_plain_text, return_type=str)]
LOCAL_ORIGINS = [
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @model_serializer(mode="wrap")
    def serialize_public_fields(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        def clean(value: object) -> object:
            if isinstance(value, str):
                return _plain_text(value)
            if isinstance(value, list):
                return [clean(item) for item in value]
            if isinstance(value, dict):
                return {key: clean(item) for key, item in value.items()}
            return value

        payload: dict[str, object] = handler(self)
        return {key: clean(value) for key, value in payload.items()}


class WebsiteReportedSummary(APIModel):
    snapshot_id: str | None = None
    capture_timestamp: datetime | None = None
    live_synchronized: bool = False
    portfolio_total_tnd: Money | None = None
    available_cash_tnd: Money | None = None
    holdings_value_tnd: Money | None = None
    unrealized_pnl_tnd: Money | None = None
    overall_performance_pct: Money | None = None
    competition_rank: int | None = None
    competition_participants: int | None = None
    competition_window: str | None = None


class LocalValuationSummary(APIModel):
    total_equity_tnd: Money
    cash_tnd: Money
    holdings_market_value_tnd: Money
    realized_pnl_tnd: Money
    unrealized_pnl_tnd: Money
    total_fees_paid_tnd: Money
    return_pct: Money
    latest_market_session: date | None
    data_is_synthetic: bool


class SyncStatusSummary(APIModel):
    live_synchronized: bool
    is_stale: bool
    last_sync_timestamp: datetime | None
    latest_market_session: date | None
    warning_message: str | None
    has_pending_snapshot: bool
    pending_snapshot_timestamp: datetime | None
    pending_snapshot_total_tnd: Money | None
    pending_snapshot_rank: int | None


class MarketDataStatusSummary(APIModel):
    dataset_label: str
    source_ids: list[str]
    latest_session_date: date | None
    first_session_date: date | None
    total_bars: int
    unique_sessions: int
    unique_instruments: int
    is_synthetic: bool
    retrieved_at: datetime | None
    sessions_behind: int


class AccountOverviewResponse(APIModel):
    portfolio_mode: PortfolioMode
    website_reported: WebsiteReportedSummary
    local_valuation: LocalValuationSummary
    sync_status: SyncStatusSummary
    market_status: MarketDataStatusSummary
    active_alerts_count: int
    actionable_recommendations_count: int


class HoldingItem(APIModel):
    instrument_id: str
    symbol: str
    isin: str | None = None
    quantity: int
    acquisition_price_tnd: Money
    acquisition_amount_tnd: Money
    website_last_price_tnd: Money | None = None
    website_market_value_tnd: Money | None = None
    website_unrealized_pnl_tnd: Money | None = None
    website_unrealized_return_pct: Money | None = None
    verified_market_price_tnd: Money | None = None
    verified_market_value_tnd: Money | None = None
    price_drift_tnd: Money | None = None
    weight_pct: Money


class HoldingsResponse(APIModel):
    portfolio_mode: PortfolioMode
    snapshot_id: str | None
    capture_timestamp: datetime | None
    live_synchronized: bool
    available_cash_tnd: Money
    portfolio_total_tnd: Money
    holdings: list[HoldingItem]


class SnapshotSummaryItem(WebsiteReportedSummary):
    pass


class BrowserSnapshotSummaryItem(APIModel):
    retrieved_at: datetime
    portfolio_total_tnd: Money
    available_cash_tnd: Money
    holdings_market_value_tnd: Money
    holdings_count: int
    competition_rank: int | None
    total_participants: int | None
    displayed_overall_performance_pct: Money | None
    is_reconciled: bool
    reconciliation_gap_tnd: Money
    is_confirmed: bool


class SnapshotsResponse(APIModel):
    confirmed_history: list[SnapshotSummaryItem]
    unconfirmed_browser_snapshots: list[BrowserSnapshotSummaryItem]
    pending_confirmation: BrowserSnapshotSummaryItem | None


class TransactionItem(APIModel):
    transaction_id: str
    order_id: str
    instrument_id: str
    symbol: str
    side: str
    filled_shares: int
    execution_price_tnd: Money
    fee_tnd: Money
    executed_at: datetime
    source: Literal["ledger", "browser"]
    source_timestamp: datetime | None = None
    is_confirmed: bool


class TransactionsResponse(APIModel):
    transactions: list[TransactionItem]


class PendingOrderItem(APIModel):
    order_id: str
    instrument_id: str
    symbol: str
    side: str
    requested_shares: int
    filled_shares: int
    remaining_shares: int
    limit_price_tnd: Money
    status: str
    submitted_at: datetime
    source: Literal["ledger", "browser"]
    source_timestamp: datetime | None = None
    is_confirmed: bool


class PendingOrdersResponse(APIModel):
    pending_orders: list[PendingOrderItem]


class DatasetOptionItem(APIModel):
    label: str
    is_synthetic: bool
    is_active: bool


class MarketDataStatusResponse(APIModel):
    market_status: MarketDataStatusSummary
    coverage_summary: dict[str, object]
    available_datasets: list[DatasetOptionItem]


class StockRankingItem(APIModel):
    rank: int | None
    instrument_id: str
    symbol: str
    close_tnd: Money | None
    short_return_pct: Money | None
    long_return_pct: Money | None
    volatility_pct: Money | None
    trade_frequency_pct: Money | None
    median_turnover_tnd: Money | None
    composite_score: float | None
    eligible: bool
    eligibility_warnings: list[str]
    recommendation_category: str
    suggested_side: str | None
    suggested_shares: int
    blocked_reasons: list[str]
    rationale: list[str]


class StockRankingsResponse(APIModel):
    as_of: datetime
    session_date: date
    data_is_synthetic: bool
    simulation_profile: str
    rankings: list[StockRankingItem]


class EventSignalItem(APIModel):
    event_id: str
    instrument_id: str
    published_at: datetime
    event_type: str
    polarity: str
    summary: PlainText
    verbatim_quote: PlainText
    source_document_id: str
    quote_verified: bool
    is_synthetic: bool


class DocumentSearchResultItem(APIModel):
    chunk_id: str
    source_document_id: str
    instrument_ids: list[str]
    published_at: datetime | None
    ingested_at: datetime | None = None
    section_locator: str
    chunk_text: PlainText
    score: float | None = None
    method: str = "listing"
    is_synthetic: bool


class BacktestSummaryItem(APIModel):
    label: str = "Historical simulation; separate from current research signals"
    status: Literal["available", "unavailable"] = "unavailable"
    source_label: str | None = None
    generated_at: datetime | None = None
    start_session: date | None = None
    end_session: date | None = None
    session_count: int | None = None
    total_return_pct: Money | None = None
    liquidated_total_return_pct: Money | None = None
    equal_weight_benchmark_return_pct: Money | None = None
    max_drawdown_pct: Money | None = None
    walk_forward_total_folds: int | None = None
    walk_forward_mean_fold_return_pct: Money | None = None
    walk_forward_mean_liquidated_return_pct: Money | None = None
    walk_forward_mean_benchmark_return_pct: Money | None = None
    walk_forward_positive_fold_ratio: Money | None = None
    is_statistically_conclusive: bool | None = None
    limitations: list[str] = Field(default_factory=list)


class ResearchResponse(APIModel):
    query: str | None
    verified_events: list[EventSignalItem]
    document_results: list[DocumentSearchResultItem]
    backtest_summary: BacktestSummaryItem
    strategy_comparison: dict[str, Any] | None = None


class StrategyLabResponse(APIModel):
    status: Literal["available", "unavailable", "invalid"]
    registry: dict[str, Any] | None = None
    limitations: list[str] = Field(default_factory=list)
    robustness_v2: dict[str, Any] | None = None


class PaperTradingResponse(APIModel):
    status: Literal["available"] = "available"
    journal: dict[str, Any]


class RecordPaperSignalRequest(APIModel):
    model_config = ConfigDict(extra="forbid")
    strategy_id: str = DEFAULT_STRATEGY
    as_of_session: date | None = None


class AlertItem(APIModel):
    alert_id: str
    created_at_utc: datetime
    session_date: date
    category: str
    severity: str
    instrument_id: str | None
    title: PlainText
    message: PlainText
    status: str


class SystemHealthResponse(APIModel):
    status: Literal["ok", "degraded"]
    version: str
    rule_blockers: list[str]
    llm_status: dict[str, object]
    alerts: list[AlertItem]
    localhost_only: bool = True
    autonomous_trading_enabled: Literal[False] = False


class PositionDeltaItem(APIModel):
    instrument_id: str
    quantity_before: int
    quantity_after: int
    quantity_delta: int


class ReconciliationPreviewResponse(APIModel):
    has_pending: bool
    status_label: str
    candidate_snapshot: BrowserSnapshotSummaryItem | None
    cash_before_tnd: Money
    cash_after_tnd: Money
    cash_delta_tnd: Money
    equity_before_tnd: Money
    equity_after_tnd: Money
    position_deltas: list[PositionDeltaItem]
    requires_confirmation: Literal[True] = True


class BrowserSyncRequest(APIModel):
    timeout_seconds: int = Field(default=180, ge=1, le=600)


class BrowserSyncTriggerResponse(APIModel):
    captured_snapshot: BrowserSnapshotSummaryItem
    reconciliation_preview: ReconciliationPreviewResponse


class ConfirmSnapshotRequest(APIModel):
    confirmed_by_user: StrictBool


class ReconciliationSummaryItem(APIModel):
    evaluated_at: datetime
    snapshot_as_of: datetime
    is_reconciled: bool
    cash_delta_tnd: Money
    discrepancy_count: int


class ConfirmSnapshotResponse(APIModel):
    overview: AccountOverviewResponse
    reconciliation_summary: ReconciliationSummaryItem


def _dataset_label(path: Path, synthetic: bool) -> str:
    name = path.parent.name if path.name == "daily_bars.canonical.csv" else path.stem
    return f"{'Synthetic demo' if synthetic else 'Market dataset'}: {name}"


def _website(snapshot: CompetitionScreenshotSnapshot | None) -> WebsiteReportedSummary:
    if snapshot is None:
        return WebsiteReportedSummary()
    return WebsiteReportedSummary(
        snapshot_id=snapshot.snapshot_id,
        capture_timestamp=datetime.fromisoformat(snapshot.capture_timestamp)
        if snapshot.capture_timestamp
        else None,
        live_synchronized=snapshot.live_synchronized,
        portfolio_total_tnd=snapshot.portfolio_total_tnd,
        available_cash_tnd=snapshot.available_cash_tnd,
        holdings_value_tnd=sum((h.current_market_value_tnd for h in snapshot.holdings), Decimal(0)),
        unrealized_pnl_tnd=sum(
            (h.displayed_unrealized_pnl_tnd for h in snapshot.holdings), Decimal(0)
        ),
        overall_performance_pct=snapshot.displayed_overall_performance_pct,
        competition_rank=snapshot.competition_rank,
        competition_participants=snapshot.competition_participants,
        competition_window=snapshot.competition_window,
    )


def _browser(
    snapshot: CompetitionPortfolioDOMSnapshot, confirmed: bool
) -> BrowserSnapshotSummaryItem:
    return BrowserSnapshotSummaryItem.model_validate(
        {**asdict(snapshot), "holdings_count": len(snapshot.holdings), "is_confirmed": confirmed}
    )


def _market(state: DashboardAppState) -> MarketDataStatusSummary:
    return MarketDataStatusSummary.model_validate(
        {
            **state.market_data_provenance,
            "dataset_label": _dataset_label(Path(state.active_bars_path), state.data_is_synthetic),
            "sessions_behind": state.data_freshness_sessions_behind,
        }
    )


def _overview(service: PortfolioStateService, state: DashboardAppState) -> AccountOverviewResponse:
    valuation = state.ledger.valuate(state.price_map)
    pending = state.pending_browser_snapshot
    return AccountOverviewResponse.model_validate(
        {
            "portfolio_mode": state.portfolio_mode,
            "website_reported": _website(state.account_snapshot),
            "local_valuation": {
                "total_equity_tnd": valuation.total_equity_tnd,
                "cash_tnd": valuation.available_cash_tnd,
                "holdings_market_value_tnd": valuation.holdings_market_value_tnd,
                "realized_pnl_tnd": valuation.total_realized_pnl_tnd,
                "unrealized_pnl_tnd": valuation.total_unrealized_pnl_tnd,
                "total_fees_paid_tnd": valuation.total_fees_paid_tnd,
                "return_pct": valuation.total_return_pct,
                "latest_market_session": state.latest_bar_session_str,
                "data_is_synthetic": state.data_is_synthetic,
            },
            "sync_status": {
                **service.get_freshness_status(state),
                "has_pending_snapshot": pending is not None,
                "pending_snapshot_timestamp": pending.retrieved_at if pending else None,
                "pending_snapshot_total_tnd": pending.portfolio_total_tnd if pending else None,
                "pending_snapshot_rank": pending.competition_rank if pending else None,
            },
            "market_status": _market(state),
            "active_alerts_count": len(state.notifications.active_alerts()),
            "actionable_recommendations_count": sum(
                r.suggested_shares > 0 and not r.blocked_reasons
                for r in state.recommendations.recommendations
            ),
        }
    )


def _preview(
    service: PortfolioStateService,
    captured: CompetitionPortfolioDOMSnapshot | None = None,
) -> ReconciliationPreviewResponse:
    state = service.load_state()
    pending = captured or state.pending_browser_snapshot
    result = service.preview_reconciliation(pending)
    valuation = state.ledger.valuate(state.price_map)
    before = (
        state.account_snapshot.portfolio_total_tnd
        if state.account_snapshot
        else valuation.total_equity_tnd
    )
    candidate = result[0] if pending and result else None
    old_quantities = {h.instrument_id: h.total_shares for h in valuation.holdings}
    new_quantities = (
        {h.instrument_id: h.quantity for h in candidate.holdings} if candidate else old_quantities
    )
    cash_after = candidate.available_cash_tnd if candidate else valuation.available_cash_tnd
    return ReconciliationPreviewResponse(
        has_pending=candidate is not None,
        status_label="Snapshot captured — awaiting confirmation" if candidate else "Up to date",
        candidate_snapshot=_browser(pending, False) if pending else None,
        cash_before_tnd=valuation.available_cash_tnd,
        cash_after_tnd=cash_after,
        cash_delta_tnd=cash_after - valuation.available_cash_tnd,
        equity_before_tnd=before,
        equity_after_tnd=candidate.portfolio_total_tnd if candidate else before,
        position_deltas=[
            PositionDeltaItem(
                instrument_id=instrument,
                quantity_before=old_quantities.get(instrument, 0),
                quantity_after=new_quantities.get(instrument, 0),
                quantity_delta=new_quantities.get(instrument, 0)
                - old_quantities.get(instrument, 0),
            )
            for instrument in sorted(old_quantities.keys() | new_quantities.keys())
            if old_quantities.get(instrument, 0) != new_quantities.get(instrument, 0)
        ],
    )


def _backtest_summary() -> BacktestSummaryItem:
    """Whitelist metrics from the recorded execution audit; never embed claimed returns."""
    path = Path("artifacts/backtest_audit_2026.json")
    if not path.is_file():
        return BacktestSummaryItem(
            limitations=["Recorded 2026 backtest audit is unavailable locally."]
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        backtest = raw["full_period_backtest"]
        walk = raw["walk_forward"]
        return BacktestSummaryItem.model_validate(
            {
                **{
                    key: backtest[key]
                    for key in (
                        "start_session",
                        "end_session",
                        "session_count",
                        "total_return_pct",
                        "liquidated_total_return_pct",
                        "equal_weight_benchmark_return_pct",
                        "max_drawdown_pct",
                    )
                },
                **{
                    f"walk_forward_{key}": walk[key]
                    for key in (
                        "total_folds",
                        "mean_fold_return_pct",
                        "mean_liquidated_return_pct",
                        "mean_benchmark_return_pct",
                        "positive_fold_ratio",
                    )
                },
                "status": "available",
                "source_label": "2026 recorded execution audit",
                "generated_at": raw["generated_at"],
                "is_statistically_conclusive": walk["is_statistically_conclusive"],
                "limitations": [
                    "Hypothetical historical results; not current account performance or a forecast.",
                    "194 sessions do not establish multi-year statistical significance.",
                ],
            }
        )
    except (OSError, ValueError, KeyError, TypeError):
        return BacktestSummaryItem(
            limitations=["Recorded backtest audit is invalid or incomplete."]
        )


def _percent(value: float | None) -> Decimal | None:
    return Decimal(str(value)) * 100 if value is not None else None


def _reconciliation(report: ReconciliationReport) -> ReconciliationSummaryItem:
    return ReconciliationSummaryItem.model_validate(
        {**asdict(report), "discrepancy_count": len(report.discrepancies)}
    )


def create_app(
    service: PortfolioStateService | None = None,
    *,
    strategy_registry_path: Path = Path("artifacts/strategy_experiments_2026.json"),
    paper_journal_path: Path = DEFAULT_JOURNAL_PATH,
    paper_bars_path: Path = DATA_DIR / "daily_bars.canonical.csv",
    paper_instruments_path: Path = DATA_DIR / "instrument_master.csv",
    paper_calendar_path: Path = DATA_DIR / "exchange_calendar.csv",
) -> FastAPI:
    """Create an offline-default app; supplied services keep all custom path overrides."""
    base = service if service is not None else PortfolioStateService()
    application = FastAPI(title="BVMT local research API", version=__version__)
    application.state.portfolio_service = base

    def load_strategy_lab() -> StrategyLabResponse:
        # GET only serves saved research; never runs experiments or changes portfolios.
        try:
            registry = json.loads(strategy_registry_path.read_text(encoding="utf-8"))
            if (
                not isinstance(registry, dict)
                or registry.get("status") != "available"
                or not isinstance(registry.get("reports"), list)
                or len(registry["reports"]) != 9
                or any(
                    not isinstance(r, dict) or "strategy_id" not in r for r in registry["reports"]
                )
            ):
                raise ValueError("Invalid registry structure")
            return StrategyLabResponse(
                status="available", registry=registry, robustness_v2=registry.get("robustness_v2")
            )
        except FileNotFoundError:
            return StrategyLabResponse(
                status="unavailable",
                limitations=[
                    "Run the offline comparative evaluation to generate the experiment registry."
                ],
            )
        except (OSError, ValueError, TypeError):
            return StrategyLabResponse(
                status="invalid",
                limitations=[
                    "Saved experiment registry is unreadable or invalid; regenerate offline."
                ],
            )

    @application.get("/api/strategy-lab")
    def strategy_lab() -> StrategyLabResponse:
        return load_strategy_lab()

    @application.get("/api/paper-trading")
    def paper_trading() -> PaperTradingResponse:
        journal = load_or_init_paper_journal(
            paper_journal_path,
            bars_path=paper_bars_path,
            instruments_path=paper_instruments_path,
            calendar_path=paper_calendar_path,
        )
        return PaperTradingResponse(journal=asdict(journal))

    @application.post("/api/paper-trading/record-signal")
    def paper_signal(request: RecordPaperSignalRequest) -> PaperTradingResponse:
        try:
            journal = record_forward_paper_signal(
                paper_journal_path,
                as_of_session=request.as_of_session,
                strategy_id=request.strategy_id,
                bars_path=paper_bars_path,
                instruments_path=paper_instruments_path,
                calendar_path=paper_calendar_path,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="Paper signal rejected: invalid strategy, date, journal or revised history.",
            ) from exc
        return PaperTradingResponse(journal=asdict(journal))

    application.add_middleware(
        CORSMiddleware,
        allow_origins=LOCAL_ORIGINS,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
    )

    @application.exception_handler(OSError)
    @application.exception_handler(ValueError)
    async def unavailable_data(_request: Request, _exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"detail": "Local portfolio or research data is unavailable or invalid."},
        )

    def for_mode(mode: PortfolioMode) -> PortfolioStateService:
        if mode == base.portfolio_mode:
            return base
        return PortfolioStateService(
            portfolio_mode=mode,
            bars_path=base.requested_bars_path,
            ledger_path=base.requested_ledger_path,
            alerts_path=base.alerts_path,
            calendar_path=base.calendar_path,
            instruments_path=base.instruments_path,
            competition_config_path=base.competition_config_path,
            llm_config_path=base.llm_config_path,
            doc_index_path=base.doc_index_path,
            real_snapshot_path=base.real_snapshot_path,
            snapshots_dir=base.snapshots_dir,
            processed_root=base.processed_root,
        )

    @application.get("/api/overview")
    def overview(mode: PortfolioMode = "REAL_COMPETITION") -> AccountOverviewResponse:
        active = for_mode(mode)
        return _overview(active, active.load_state())

    @application.get("/api/holdings")
    def holdings(mode: PortfolioMode = "REAL_COMPETITION") -> HoldingsResponse:
        state = for_mode(mode).load_state()
        snapshot = state.account_snapshot
        valuation = state.ledger.valuate(state.price_map)
        cutoff = datetime.fromisoformat(state.recommendations.decision_cutoff)
        market_prices = (
            {
                b.instrument_id: b.close
                for b in sorted(
                    read_bars_csv(Path(state.active_bars_path)), key=lambda b: b.session_date
                )
                if b.status == "traded"
                and b.session_date.isoformat() <= (state.latest_bar_session_str or "")
                and b.published_at is not None
                and b.published_at <= cutoff
                and b.ingested_at <= cutoff
            }
            if not state.data_is_synthetic
            else {}
        )
        items: list[HoldingItem] = []
        if snapshot:
            for h in snapshot.holdings:
                price = market_prices.get(h.instrument_id)
                items.append(
                    HoldingItem(
                        instrument_id=h.instrument_id,
                        symbol=h.symbol,
                        isin=h.isin,
                        quantity=h.quantity,
                        acquisition_price_tnd=h.displayed_acquisition_price_tnd,
                        acquisition_amount_tnd=h.displayed_acquisition_amount_tnd,
                        website_last_price_tnd=h.displayed_last_price_tnd,
                        website_market_value_tnd=h.current_market_value_tnd,
                        website_unrealized_pnl_tnd=h.displayed_unrealized_pnl_tnd,
                        website_unrealized_return_pct=h.displayed_unrealized_return_pct,
                        verified_market_price_tnd=price,
                        verified_market_value_tnd=price * h.quantity if price is not None else None,
                        price_drift_tnd=price - h.displayed_last_price_tnd
                        if price is not None
                        else None,
                        weight_pct=h.portfolio_allocation_pct,
                    )
                )
        else:
            for local in valuation.holdings:
                items.append(
                    HoldingItem(
                        instrument_id=local.instrument_id,
                        symbol=local.symbol,
                        quantity=local.total_shares,
                        acquisition_price_tnd=local.average_cost_tnd,
                        acquisition_amount_tnd=local.cost_basis_tnd,
                        verified_market_price_tnd=market_prices.get(local.instrument_id),
                        verified_market_value_tnd=market_prices[local.instrument_id]
                        * local.total_shares
                        if local.instrument_id in market_prices
                        else None,
                        weight_pct=local.portfolio_weight_pct,
                    )
                )
        return HoldingsResponse.model_validate(
            {
                "portfolio_mode": state.portfolio_mode,
                "snapshot_id": snapshot.snapshot_id if snapshot else None,
                "capture_timestamp": snapshot.capture_timestamp if snapshot else None,
                "live_synchronized": snapshot.live_synchronized if snapshot else False,
                "available_cash_tnd": snapshot.available_cash_tnd
                if snapshot
                else valuation.available_cash_tnd,
                "portfolio_total_tnd": snapshot.portfolio_total_tnd
                if snapshot
                else valuation.total_equity_tnd,
                "holdings": items,
            }
        )

    @application.get("/api/snapshots")
    def snapshots(mode: PortfolioMode = "REAL_COMPETITION") -> SnapshotsResponse:
        active = for_mode(mode)
        state = active.load_state()
        confirmed = {s.capture_timestamp for s in state.ledger.snapshot_history}
        return SnapshotsResponse(
            confirmed_history=[
                SnapshotSummaryItem.model_validate(_website(s).model_dump())
                for s in state.ledger.snapshot_history
            ],
            unconfirmed_browser_snapshots=[
                _browser(s, False)
                for _, s in active.list_browser_snapshots()
                if s.retrieved_at.isoformat() not in confirmed
            ],
            pending_confirmation=_browser(state.pending_browser_snapshot, False)
            if state.pending_browser_snapshot
            else None,
        )

    @application.get("/api/transactions")
    def transactions(mode: PortfolioMode = "REAL_COMPETITION") -> TransactionsResponse:
        state = for_mode(mode).load_state()
        items: dict[str, TransactionItem] = {}
        for order in state.ledger.orders.values():
            for fill in order.fills:
                items[fill.fill_id] = TransactionItem.model_validate(
                    {
                        **asdict(fill),
                        "transaction_id": fill.fill_id,
                        "instrument_id": order.instrument_id,
                        "symbol": order.symbol,
                        "side": order.side,
                        "source": "ledger",
                        "is_confirmed": True,
                    }
                )
        if state.account_snapshot:
            for tx in state.account_snapshot.imported_transactions:
                items[tx.transaction_id] = TransactionItem.model_validate(
                    {
                        **asdict(tx),
                        "source": "browser",
                        "source_timestamp": state.account_snapshot.capture_timestamp,
                        "is_confirmed": True,
                    }
                )
        browser = state.latest_browser_snapshot
        if browser:
            confirmed = any(
                s.capture_timestamp == browser.retrieved_at.isoformat()
                for s in state.ledger.snapshot_history
            )
            for browser_tx in browser.transactions:
                if browser_tx.transaction_id not in items:
                    items[browser_tx.transaction_id] = TransactionItem.model_validate(
                        {
                            **asdict(browser_tx),
                            "source": "browser",
                            "source_timestamp": browser.retrieved_at,
                            "is_confirmed": confirmed,
                        }
                    )
        return TransactionsResponse(
            transactions=sorted(items.values(), key=lambda t: t.executed_at, reverse=True)
        )

    @application.get("/api/orders/pending")
    def pending_orders(mode: PortfolioMode = "REAL_COMPETITION") -> PendingOrdersResponse:
        state = for_mode(mode).load_state()
        items = {
            o.order_id: PendingOrderItem.model_validate(
                {**asdict(o), "source": "ledger", "is_confirmed": True}
            )
            for o in state.ledger.orders.values()
            if o.status in {"PENDING", "PARTIALLY_FILLED"}
        }
        browser = state.latest_browser_snapshot
        if browser and browser.movements_page_captured:
            confirmed = any(
                s.capture_timestamp == browser.retrieved_at.isoformat()
                for s in state.ledger.snapshot_history
            )
            for order in browser.pending_orders:
                items[order.order_id] = PendingOrderItem.model_validate(
                    {
                        **asdict(order),
                        "source": "browser",
                        "source_timestamp": browser.retrieved_at,
                        "is_confirmed": confirmed,
                    }
                )
        return PendingOrdersResponse(pending_orders=list(items.values()))

    @application.get("/api/market-status")
    def market_status(mode: PortfolioMode = "REAL_COMPETITION") -> MarketDataStatusResponse:
        active = for_mode(mode)
        state = active.load_state()
        context = active.resolve_context()
        paths = list(
            {
                path.resolve(): path
                for path in [*context.available_datasets.values(), context.bars_path]
            }.values()
        )
        synthetic = {
            path: bool(inspect_market_dataset_provenance(path)["is_synthetic"]) for path in paths
        }
        return MarketDataStatusResponse(
            market_status=_market(state),
            coverage_summary=state.coverage_summary,
            available_datasets=[
                DatasetOptionItem(
                    label=_dataset_label(path, synthetic[path]),
                    is_synthetic=synthetic[path],
                    is_active=path.resolve() == context.bars_path.resolve(),
                )
                for path in paths
            ],
        )

    @application.get("/api/rankings")
    def rankings(mode: PortfolioMode = "REAL_COMPETITION") -> StockRankingsResponse:
        state = for_mode(mode).load_state()
        report = state.recommendations
        synthetic_on_real = state.data_is_synthetic and state.portfolio_mode == "REAL_COMPETITION"
        return StockRankingsResponse.model_validate(
            {
                "as_of": report.generated_at,
                "session_date": report.latest_open_session,
                "data_is_synthetic": report.data_is_synthetic,
                "simulation_profile": report.simulation_profile,
                "rankings": [
                    StockRankingItem(
                        rank=r.rank,
                        instrument_id=r.instrument_id,
                        symbol=r.symbol,
                        close_tnd=Decimal(r.reference_price_tnd) if r.reference_price_tnd else None,
                        short_return_pct=_percent(r.momentum_20s),
                        long_return_pct=_percent(r.momentum_60s),
                        volatility_pct=_percent(r.volatility_20s),
                        trade_frequency_pct=_percent(r.trade_frequency_20s),
                        median_turnover_tnd=Decimal(r.median_turnover_20s_tnd)
                        if r.median_turnover_20s_tnd
                        else None,
                        composite_score=r.composite_score,
                        eligible=r.rank is not None,
                        eligibility_warnings=r.liquidity_warnings,
                        recommendation_category="NO TRADE" if synthetic_on_real else r.category,
                        suggested_side=None if synthetic_on_real else r.suggested_side,
                        suggested_shares=0 if synthetic_on_real else r.suggested_shares,
                        blocked_reasons=list(
                            dict.fromkeys(
                                r.blocked_reasons
                                + (
                                    ["synthetic_data_on_real_portfolio"]
                                    if synthetic_on_real
                                    else []
                                )
                            )
                        ),
                        rationale=r.supporting_evidence + r.main_risks,
                    )
                    for r in report.recommendations
                ],
            }
        )

    @application.get("/api/research")
    def research(q: str = "", mode: PortfolioMode = "REAL_COMPETITION") -> ResearchResponse:
        state = for_mode(mode).load_state()
        cutoff = datetime.fromisoformat(state.recommendations.decision_cutoff)
        chunks = state.document_chunks
        results = (
            search_document_index(chunks, cutoff=cutoff, query_text=q)
            if q.strip()
            else [
                c
                for c in chunks
                if c.published_at is not None
                and datetime.fromisoformat(c.published_at) <= cutoff
                and datetime.fromisoformat(c.ingested_at) <= cutoff
            ]
        )
        return ResearchResponse(
            query=q.strip() or None,
            verified_events=[
                EventSignalItem.model_validate(
                    {**asdict(e), "is_synthetic": state.data_is_synthetic}
                )
                for e in state.verified_events
                if e.quote_verified and datetime.fromisoformat(e.published_at) <= cutoff
            ],
            document_results=[
                DocumentSearchResultItem.model_validate(
                    {
                        **asdict(c),
                        "chunk_text": unescape(c.chunk_text),
                        "is_synthetic": state.data_is_synthetic,
                    }
                )
                for c in results
            ],
            backtest_summary=_backtest_summary(),
            strategy_comparison=load_strategy_lab().registry,
        )

    @application.get("/api/health")
    def health(mode: PortfolioMode = "REAL_COMPETITION") -> SystemHealthResponse:
        state = for_mode(mode).load_state()
        alerts = [AlertItem.model_validate(a) for a in state.notifications.active_alerts()]
        return SystemHealthResponse(
            status="degraded" if state.rule_blockers or alerts or state.data_is_synthetic else "ok",
            version=__version__,
            rule_blockers=state.rule_blockers,
            llm_status={
                k: state.llm_status[k]
                for k in (
                    "network_enabled",
                    "enabled_models_count",
                    "total_models_count",
                    "live_opt_in_env_set",
                )
                if k in state.llm_status
            },
            alerts=alerts,
        )

    @application.post("/api/sync/browser")
    def browser_sync(body: BrowserSyncRequest) -> BrowserSyncTriggerResponse:
        if base.portfolio_mode != "REAL_COMPETITION":
            raise HTTPException(400, "Browser synchronization requires REAL_COMPETITION mode.")
        try:
            captured, _ = run_browser_sync_subprocess(
                user_data_dir=base.snapshots_dir.parent / "browser_profile",
                snapshots_dir=base.snapshots_dir,
                timeout_seconds=body.timeout_seconds,
            )
        except AuthenticationExpiredError as exc:
            raise HTTPException(
                400, "Browser authentication expired. Log in manually and retry."
            ) from exc
        except BrowserCollectorError as exc:
            # Collector errors can contain raw process output, HTML or local paths.
            raise HTTPException(
                422, "Browser capture failed validation. Review the local collector and retry."
            ) from exc
        return BrowserSyncTriggerResponse(
            captured_snapshot=_browser(captured, False),
            reconciliation_preview=_preview(base, captured),
        )

    @application.get("/api/sync/preview")
    def sync_preview(mode: PortfolioMode = "REAL_COMPETITION") -> ReconciliationPreviewResponse:
        return _preview(for_mode(mode))

    @application.post("/api/sync/confirm")
    def sync_confirm(body: ConfirmSnapshotRequest) -> ConfirmSnapshotResponse:
        if body.confirmed_by_user is not True:
            raise HTTPException(
                400, "Explicit user confirmation (confirmed_by_user=True) is required."
            )
        if base.portfolio_mode != "REAL_COMPETITION":
            raise HTTPException(400, "Snapshot confirmation requires REAL_COMPETITION mode.")
        try:
            state, report = base.confirm_snapshot(confirmed_by_user=True)
        except FileNotFoundError as exc:
            raise HTTPException(400, "No browser snapshot available to confirm.") from exc
        except ValueError as exc:
            raise HTTPException(422, "Snapshot reconciliation failed validation.") from exc
        return ConfirmSnapshotResponse(
            overview=_overview(base, state), reconciliation_summary=_reconciliation(report)
        )

    return application


app = create_app()
