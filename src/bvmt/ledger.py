"""Manual portfolio ledger, cash/share reservation, 0.50% fee arithmetic, and append-only order journal.

Never submits orders automatically and never assumes a recommendation has been executed.
All monetary calculations use Decimal quantized to 0.001 TND (Tunisian millimes).
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

from bvmt.data import DailyBar, aware_timestamp
from bvmt.snapshots import (
    atomic_write_text,
    ensure_no_symlink_ancestors,
    validate_safe_id,
)

MILLIME = Decimal("0.001")
DEFAULT_FEE_RATE = Decimal("0.005")  # 0.50% competition buy and sell fee
MAX_CONCENTRATION_RATIO = Decimal("0.10")  # Hard 10% competition single-stock limit
OPEN_ORDER_STATUSES = frozenset({"PENDING", "PARTIALLY_FILLED"})
TERMINAL_ORDER_STATUSES = frozenset({"EXECUTED", "CANCELLED", "REJECTED", "EXPIRED"})
ALL_ORDER_STATUSES = OPEN_ORDER_STATUSES | TERMINAL_ORDER_STATUSES


def quantize_tnd(value: Decimal | str | int) -> Decimal:
    try:
        dec = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid TND Decimal value: '{value}'") from exc
    if not dec.is_finite():
        raise ValueError(f"Non-finite TND Decimal value: '{value}'")
    return dec.quantize(MILLIME, rounding=ROUND_HALF_UP)


def compute_commission(gross_amount_tnd: Decimal, fee_rate: Decimal = DEFAULT_FEE_RATE) -> Decimal:
    if gross_amount_tnd < Decimal("0"):
        raise ValueError("Gross trade amount cannot be negative")
    if fee_rate < Decimal("0"):
        raise ValueError("Fee rate cannot be negative")
    return quantize_tnd(gross_amount_tnd * fee_rate)


@dataclass(frozen=True)
class HoldingPosition:
    instrument_id: str
    symbol: str
    total_shares: int
    reserved_sell_shares: int
    average_cost_tnd: Decimal  # Average acquisition cost per share (including buy fees)
    cost_basis_tnd: Decimal  # Total acquisition cost of current shares (including buy fees)
    realized_pnl_tnd: Decimal
    total_fees_paid_tnd: Decimal

    @property
    def available_shares(self) -> int:
        return max(0, self.total_shares - self.reserved_sell_shares)

    def to_dict(self) -> dict[str, object]:
        return {
            "available_shares": self.available_shares,
            "average_cost_tnd": str(quantize_tnd(self.average_cost_tnd)),
            "cost_basis_tnd": str(quantize_tnd(self.cost_basis_tnd)),
            "instrument_id": self.instrument_id,
            "realized_pnl_tnd": str(quantize_tnd(self.realized_pnl_tnd)),
            "reserved_sell_shares": self.reserved_sell_shares,
            "symbol": self.symbol,
            "total_fees_paid_tnd": str(quantize_tnd(self.total_fees_paid_tnd)),
            "total_shares": self.total_shares,
        }


@dataclass(frozen=True)
class OrderExecutionFill:
    fill_id: str
    order_id: str
    executed_at: str
    filled_shares: int
    execution_price_tnd: Decimal
    gross_amount_tnd: Decimal
    fee_tnd: Decimal
    net_cash_impact_tnd: Decimal  # Negative for BUY, positive for SELL
    realized_pnl_delta_tnd: Decimal

    def to_dict(self) -> dict[str, object]:
        return {
            "executed_at": self.executed_at,
            "execution_price_tnd": str(quantize_tnd(self.execution_price_tnd)),
            "fee_tnd": str(quantize_tnd(self.fee_tnd)),
            "fill_id": self.fill_id,
            "filled_shares": self.filled_shares,
            "gross_amount_tnd": str(quantize_tnd(self.gross_amount_tnd)),
            "net_cash_impact_tnd": str(quantize_tnd(self.net_cash_impact_tnd)),
            "order_id": self.order_id,
            "realized_pnl_delta_tnd": str(quantize_tnd(self.realized_pnl_delta_tnd)),
        }


@dataclass(frozen=True)
class ManualOrderRecord:
    order_id: str
    recommendation_id: str | None
    instrument_id: str
    symbol: str
    side: str  # "BUY" | "SELL"
    requested_shares: int
    filled_shares: int
    remaining_shares: int
    limit_price_tnd: Decimal
    reserved_cash_tnd: Decimal
    reserved_shares: int
    status: str  # PENDING, PARTIALLY_FILLED, EXECUTED, CANCELLED, REJECTED, EXPIRED
    submitted_at: str
    updated_at: str
    notes: str
    fills: list[OrderExecutionFill] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "filled_shares": self.filled_shares,
            "fills": [f.to_dict() for f in self.fills],
            "instrument_id": self.instrument_id,
            "limit_price_tnd": str(quantize_tnd(self.limit_price_tnd)),
            "notes": self.notes,
            "order_id": self.order_id,
            "recommendation_id": self.recommendation_id,
            "remaining_shares": self.remaining_shares,
            "requested_shares": self.requested_shares,
            "reserved_cash_tnd": str(quantize_tnd(self.reserved_cash_tnd)),
            "reserved_shares": self.reserved_shares,
            "side": self.side,
            "status": self.status,
            "submitted_at": self.submitted_at,
            "symbol": self.symbol,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class LedgerAuditEntry:
    sequence: int
    event_id: str
    timestamp: str
    event_type: str
    order_id: str | None
    instrument_id: str | None
    summary: str
    settled_cash_after_tnd: str
    reserved_cash_after_tnd: str
    available_cash_after_tnd: str
    payload: dict[str, object]


@dataclass(frozen=True)
class HoldingValuation:
    instrument_id: str
    symbol: str
    total_shares: int
    available_shares: int
    reserved_sell_shares: int
    average_cost_tnd: Decimal
    cost_basis_tnd: Decimal
    mark_price_tnd: Decimal
    market_value_tnd: Decimal
    unrealized_pnl_tnd: Decimal
    unrealized_return_pct: Decimal
    realized_pnl_tnd: Decimal
    total_fees_paid_tnd: Decimal
    portfolio_weight_pct: Decimal
    concentration_warning: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "available_shares": self.available_shares,
            "average_cost_tnd": str(quantize_tnd(self.average_cost_tnd)),
            "concentration_warning": self.concentration_warning,
            "cost_basis_tnd": str(quantize_tnd(self.cost_basis_tnd)),
            "instrument_id": self.instrument_id,
            "mark_price_tnd": str(quantize_tnd(self.mark_price_tnd)),
            "market_value_tnd": str(quantize_tnd(self.market_value_tnd)),
            "portfolio_weight_pct": str(quantize_tnd(self.portfolio_weight_pct)),
            "realized_pnl_tnd": str(quantize_tnd(self.realized_pnl_tnd)),
            "reserved_sell_shares": self.reserved_sell_shares,
            "symbol": self.symbol,
            "total_fees_paid_tnd": str(quantize_tnd(self.total_fees_paid_tnd)),
            "total_shares": self.total_shares,
            "unrealized_pnl_tnd": str(quantize_tnd(self.unrealized_pnl_tnd)),
            "unrealized_return_pct": str(quantize_tnd(self.unrealized_return_pct)),
        }


@dataclass(frozen=True)
class PortfolioValuationSnapshot:
    initial_cash_tnd: Decimal
    settled_cash_tnd: Decimal
    reserved_cash_tnd: Decimal
    available_cash_tnd: Decimal
    holdings_market_value_tnd: Decimal
    total_equity_tnd: Decimal
    total_unrealized_pnl_tnd: Decimal
    total_realized_pnl_tnd: Decimal
    total_fees_paid_tnd: Decimal
    total_return_pct: Decimal
    holdings: list[HoldingValuation]
    open_orders_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "available_cash_tnd": str(quantize_tnd(self.available_cash_tnd)),
            "holdings": [h.to_dict() for h in self.holdings],
            "holdings_market_value_tnd": str(quantize_tnd(self.holdings_market_value_tnd)),
            "initial_cash_tnd": str(quantize_tnd(self.initial_cash_tnd)),
            "open_orders_count": self.open_orders_count,
            "reserved_cash_tnd": str(quantize_tnd(self.reserved_cash_tnd)),
            "settled_cash_tnd": str(quantize_tnd(self.settled_cash_tnd)),
            "total_equity_tnd": str(quantize_tnd(self.total_equity_tnd)),
            "total_fees_paid_tnd": str(quantize_tnd(self.total_fees_paid_tnd)),
            "total_realized_pnl_tnd": str(quantize_tnd(self.total_realized_pnl_tnd)),
            "total_return_pct": str(quantize_tnd(self.total_return_pct)),
            "total_unrealized_pnl_tnd": str(quantize_tnd(self.total_unrealized_pnl_tnd)),
        }


@dataclass(frozen=True)
class PortfolioHistoryPoint:
    session_date: str
    settled_cash_tnd: Decimal
    holdings_market_value_tnd: Decimal
    total_equity_tnd: Decimal
    cumulative_return_pct: Decimal
    realized_pnl_tnd: Decimal
    unrealized_pnl_tnd: Decimal
    cumulative_fees_tnd: Decimal

    def to_dict(self) -> dict[str, object]:
        return {
            "cumulative_fees_tnd": str(quantize_tnd(self.cumulative_fees_tnd)),
            "cumulative_return_pct": str(quantize_tnd(self.cumulative_return_pct)),
            "holdings_market_value_tnd": str(quantize_tnd(self.holdings_market_value_tnd)),
            "realized_pnl_tnd": str(quantize_tnd(self.realized_pnl_tnd)),
            "session_date": self.session_date,
            "settled_cash_tnd": str(quantize_tnd(self.settled_cash_tnd)),
            "total_equity_tnd": str(quantize_tnd(self.total_equity_tnd)),
            "unrealized_pnl_tnd": str(quantize_tnd(self.unrealized_pnl_tnd)),
        }


@dataclass(frozen=True)
class AccountHoldingRecord:
    instrument_id: str
    symbol: str
    total_shares: int
    average_cost_tnd: Decimal
    realized_pnl_tnd: Decimal = Decimal("0.000")
    total_fees_paid_tnd: Decimal = Decimal("0.000")

    def to_dict(self) -> dict[str, object]:
        return {
            "average_cost_tnd": str(quantize_tnd(self.average_cost_tnd)),
            "instrument_id": self.instrument_id,
            "realized_pnl_tnd": str(quantize_tnd(self.realized_pnl_tnd)),
            "symbol": self.symbol,
            "total_fees_paid_tnd": str(quantize_tnd(self.total_fees_paid_tnd)),
            "total_shares": self.total_shares,
        }


@dataclass(frozen=True)
class AccountTransactionRecord:
    transaction_id: str
    order_id: str
    instrument_id: str
    symbol: str
    side: str  # "BUY" | "SELL"
    filled_shares: int
    execution_price_tnd: Decimal
    fee_tnd: Decimal
    executed_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "executed_at": self.executed_at,
            "execution_price_tnd": str(quantize_tnd(self.execution_price_tnd)),
            "fee_tnd": str(quantize_tnd(self.fee_tnd)),
            "filled_shares": self.filled_shares,
            "instrument_id": self.instrument_id,
            "order_id": self.order_id,
            "side": self.side,
            "symbol": self.symbol,
            "transaction_id": self.transaction_id,
        }


@dataclass(frozen=True)
class AccountPendingOrderRecord:
    order_id: str
    instrument_id: str
    symbol: str
    side: str  # "BUY" | "SELL"
    requested_shares: int
    filled_shares: int
    remaining_shares: int
    limit_price_tnd: Decimal
    status: str  # "PENDING" | "PARTIALLY_FILLED"
    submitted_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "filled_shares": self.filled_shares,
            "instrument_id": self.instrument_id,
            "limit_price_tnd": str(quantize_tnd(self.limit_price_tnd)),
            "order_id": self.order_id,
            "remaining_shares": self.remaining_shares,
            "requested_shares": self.requested_shares,
            "side": self.side,
            "status": self.status,
            "submitted_at": self.submitted_at,
            "symbol": self.symbol,
        }


@dataclass(frozen=True)
class CompetitionAccountSnapshot:
    as_of: str
    settled_cash_tnd: Decimal
    available_cash_tnd: Decimal | None = None
    initial_cash_tnd: Decimal | None = None
    holdings: list[AccountHoldingRecord] = field(default_factory=list)
    transactions: list[AccountTransactionRecord] = field(default_factory=list)
    pending_orders: list[AccountPendingOrderRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "as_of": self.as_of,
            "available_cash_tnd": (
                str(quantize_tnd(self.available_cash_tnd))
                if self.available_cash_tnd is not None
                else None
            ),
            "holdings": [h.to_dict() for h in self.holdings],
            "initial_cash_tnd": (
                str(quantize_tnd(self.initial_cash_tnd))
                if self.initial_cash_tnd is not None
                else None
            ),
            "pending_orders": [o.to_dict() for o in self.pending_orders],
            "settled_cash_tnd": str(quantize_tnd(self.settled_cash_tnd)),
            "transactions": [t.to_dict() for t in self.transactions],
        }


@dataclass(frozen=True)
class ReconciliationDiscrepancy:
    discrepancy_type: str  # cash_mismatch | missing_transaction | duplicate_transaction | share_quantity_mismatch | unmatched_pending_order | fee_mismatch
    severity: str  # "CRITICAL" | "WARNING"
    instrument_id: str | None
    order_id: str | None
    local_value: str
    account_value: str
    delta: str
    explanation: str
    suggested_adjustment: str

    def to_dict(self) -> dict[str, object]:
        return {
            "account_value": self.account_value,
            "delta": self.delta,
            "discrepancy_type": self.discrepancy_type,
            "explanation": self.explanation,
            "instrument_id": self.instrument_id,
            "local_value": self.local_value,
            "order_id": self.order_id,
            "severity": self.severity,
            "suggested_adjustment": self.suggested_adjustment,
        }


@dataclass(frozen=True)
class ReconciliationReport:
    evaluated_at: str
    snapshot_as_of: str
    is_reconciled: bool
    requires_user_confirmation: bool
    local_settled_cash_tnd: Decimal
    account_settled_cash_tnd: Decimal
    cash_delta_tnd: Decimal
    discrepancies: list[ReconciliationDiscrepancy]

    def to_dict(self) -> dict[str, object]:
        return {
            "account_settled_cash_tnd": str(quantize_tnd(self.account_settled_cash_tnd)),
            "cash_delta_tnd": str(quantize_tnd(self.cash_delta_tnd)),
            "discrepancies": [d.to_dict() for d in self.discrepancies],
            "evaluated_at": self.evaluated_at,
            "is_reconciled": self.is_reconciled,
            "local_settled_cash_tnd": str(quantize_tnd(self.local_settled_cash_tnd)),
            "requires_user_confirmation": self.requires_user_confirmation,
            "snapshot_as_of": self.snapshot_as_of,
        }


@dataclass(frozen=True)
class ScreenshotHoldingSnapshot:
    instrument_id: str
    symbol: str
    isin: str | None
    quantity: int
    displayed_acquisition_price_tnd: Decimal
    displayed_acquisition_amount_tnd: Decimal
    displayed_last_price_tnd: Decimal
    current_market_value_tnd: Decimal
    displayed_unrealized_pnl_tnd: Decimal
    displayed_unrealized_return_pct: Decimal
    portfolio_allocation_pct: Decimal

    def to_dict(self) -> dict[str, object]:
        return {
            "current_market_value_tnd": str(quantize_tnd(self.current_market_value_tnd)),
            "displayed_acquisition_amount_tnd": str(
                quantize_tnd(self.displayed_acquisition_amount_tnd)
            ),
            "displayed_acquisition_price_tnd": str(
                quantize_tnd(self.displayed_acquisition_price_tnd)
            ),
            "displayed_last_price_tnd": str(quantize_tnd(self.displayed_last_price_tnd)),
            "displayed_unrealized_pnl_tnd": str(quantize_tnd(self.displayed_unrealized_pnl_tnd)),
            "displayed_unrealized_return_pct": str(
                quantize_tnd(self.displayed_unrealized_return_pct)
            ),
            "instrument_id": self.instrument_id,
            "isin": self.isin,
            "portfolio_allocation_pct": str(quantize_tnd(self.portfolio_allocation_pct)),
            "quantity": self.quantity,
            "symbol": self.symbol,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> ScreenshotHoldingSnapshot:
        return cls(
            instrument_id=str(raw["instrument_id"]),
            symbol=str(raw["symbol"]),
            isin=str(raw["isin"]) if raw.get("isin") is not None else None,
            quantity=int(str(raw["quantity"])),
            displayed_acquisition_price_tnd=quantize_tnd(
                str(raw["displayed_acquisition_price_tnd"])
            ),
            displayed_acquisition_amount_tnd=quantize_tnd(
                str(raw["displayed_acquisition_amount_tnd"])
            ),
            displayed_last_price_tnd=quantize_tnd(str(raw["displayed_last_price_tnd"])),
            current_market_value_tnd=quantize_tnd(str(raw["current_market_value_tnd"])),
            displayed_unrealized_pnl_tnd=quantize_tnd(str(raw["displayed_unrealized_pnl_tnd"])),
            displayed_unrealized_return_pct=quantize_tnd(
                str(raw["displayed_unrealized_return_pct"])
            ),
            portfolio_allocation_pct=quantize_tnd(str(raw["portfolio_allocation_pct"])),
        )


@dataclass(frozen=True)
class CompetitionScreenshotSnapshot:
    snapshot_id: str
    provenance: str
    competition_window: str
    capture_timestamp: str | None  # None when unknown; never invented
    last_price_timestamp: str | None  # None when unknown; never invented
    portfolio_total_tnd: Decimal
    available_cash_tnd: Decimal
    implied_initial_cash_tnd: Decimal
    competition_rank: int | None
    competition_participants: int | None
    displayed_overall_performance_pct: Decimal
    displayed_total_pnl_tnd: Decimal
    holdings: list[ScreenshotHoldingSnapshot] = field(default_factory=list)
    transactions_imported: bool = False
    pending_orders_verified: bool = False
    acquisition_fee_inclusion_verified: bool = False
    live_synchronized: bool = False
    limitations: list[str] = field(default_factory=list)

    @property
    def competition_ranking_display(self) -> str:
        if self.competition_rank is not None and self.competition_participants is not None:
            return f"{self.competition_rank:,} / {self.competition_participants:,}"
        return "Unverified"

    @property
    def pending_orders_status_label(self) -> str:
        return (
            "Verified (0 open)" if self.pending_orders_verified else "Pending orders not verified"
        )

    @property
    def transactions_status_label(self) -> str:
        return "Imported" if self.transactions_imported else "Transaction history not yet imported"

    def to_competition_account_snapshot(self, *, as_of: str) -> CompetitionAccountSnapshot:
        return CompetitionAccountSnapshot(
            as_of=as_of,
            settled_cash_tnd=self.available_cash_tnd,
            available_cash_tnd=self.available_cash_tnd,
            initial_cash_tnd=self.implied_initial_cash_tnd,
            holdings=[
                AccountHoldingRecord(
                    instrument_id=h.instrument_id,
                    symbol=h.symbol,
                    total_shares=h.quantity,
                    average_cost_tnd=h.displayed_acquisition_price_tnd,
                    realized_pnl_tnd=Decimal("0.000"),
                    total_fees_paid_tnd=Decimal("0.000"),
                )
                for h in self.holdings
            ],
            transactions=[],
            pending_orders=[],
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "acquisition_fee_inclusion_verified": self.acquisition_fee_inclusion_verified,
            "available_cash_tnd": str(quantize_tnd(self.available_cash_tnd)),
            "capture_timestamp": self.capture_timestamp,
            "competition_participants": self.competition_participants,
            "competition_rank": self.competition_rank,
            "competition_window": self.competition_window,
            "displayed_overall_performance_pct": str(
                quantize_tnd(self.displayed_overall_performance_pct)
            ),
            "displayed_total_pnl_tnd": str(quantize_tnd(self.displayed_total_pnl_tnd)),
            "holdings": [h.to_dict() for h in self.holdings],
            "implied_initial_cash_tnd": str(quantize_tnd(self.implied_initial_cash_tnd)),
            "last_price_timestamp": self.last_price_timestamp,
            "limitations": list(self.limitations),
            "live_synchronized": self.live_synchronized,
            "pending_orders_verified": self.pending_orders_verified,
            "portfolio_total_tnd": str(quantize_tnd(self.portfolio_total_tnd)),
            "provenance": self.provenance,
            "snapshot_id": self.snapshot_id,
            "transactions_imported": self.transactions_imported,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> CompetitionScreenshotSnapshot:
        raw_holdings = raw.get("holdings", [])
        holdings_list = (
            [ScreenshotHoldingSnapshot.from_dict(h) for h in raw_holdings if isinstance(h, Mapping)]
            if isinstance(raw_holdings, list)
            else []
        )
        raw_lims = raw.get("limitations", [])
        lims_list = [str(x) for x in raw_lims] if isinstance(raw_lims, list) else []
        return cls(
            snapshot_id=str(raw["snapshot_id"]),
            provenance=str(raw.get("provenance", "user_supplied_competition_screenshot")),
            competition_window=str(raw.get("competition_window", "2026-10-01 to 2027-05-31")),
            capture_timestamp=(
                str(raw["capture_timestamp"]) if raw.get("capture_timestamp") is not None else None
            ),
            last_price_timestamp=(
                str(raw["last_price_timestamp"])
                if raw.get("last_price_timestamp") is not None
                else None
            ),
            portfolio_total_tnd=quantize_tnd(str(raw["portfolio_total_tnd"])),
            available_cash_tnd=quantize_tnd(str(raw["available_cash_tnd"])),
            implied_initial_cash_tnd=quantize_tnd(
                str(raw.get("implied_initial_cash_tnd", "50000.000"))
            ),
            competition_rank=(
                int(str(raw["competition_rank"]))
                if raw.get("competition_rank") is not None
                else None
            ),
            competition_participants=(
                int(str(raw["competition_participants"]))
                if raw.get("competition_participants") is not None
                else None
            ),
            displayed_overall_performance_pct=quantize_tnd(
                str(raw["displayed_overall_performance_pct"])
            ),
            displayed_total_pnl_tnd=quantize_tnd(str(raw.get("displayed_total_pnl_tnd", "-1.950"))),
            holdings=holdings_list,
            transactions_imported=bool(raw.get("transactions_imported", False)),
            pending_orders_verified=bool(raw.get("pending_orders_verified", False)),
            acquisition_fee_inclusion_verified=bool(
                raw.get("acquisition_fee_inclusion_verified", False)
            ),
            live_synchronized=bool(raw.get("live_synchronized", False)),
            limitations=lims_list,
        )


@dataclass(frozen=True)
class HoldingPriceDrift:
    instrument_id: str
    symbol: str
    isin: str | None
    quantity: int
    acquisition_price_tnd: Decimal
    acquisition_amount_tnd: Decimal
    screenshot_price_tnd: Decimal
    screenshot_market_value_tnd: Decimal
    screenshot_unrealized_pnl_tnd: Decimal
    screenshot_unrealized_return_pct: Decimal
    screenshot_weight_pct: Decimal
    verified_market_price_tnd: Decimal
    price_has_verified_quote: bool
    price_drift_tnd: Decimal
    price_drift_pct: Decimal
    marked_market_value_tnd: Decimal
    market_value_drift_tnd: Decimal
    marked_unrealized_pnl_tnd: Decimal
    marked_unrealized_return_pct: Decimal
    marked_weight_pct: Decimal
    concentration_cap_pct: Decimal
    remaining_concentration_room_tnd: Decimal
    exceeds_concentration_cap: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "acquisition_amount_tnd": str(quantize_tnd(self.acquisition_amount_tnd)),
            "acquisition_price_tnd": str(quantize_tnd(self.acquisition_price_tnd)),
            "concentration_cap_pct": str(quantize_tnd(self.concentration_cap_pct)),
            "exceeds_concentration_cap": self.exceeds_concentration_cap,
            "instrument_id": self.instrument_id,
            "isin": self.isin,
            "marked_market_value_tnd": str(quantize_tnd(self.marked_market_value_tnd)),
            "marked_unrealized_pnl_tnd": str(quantize_tnd(self.marked_unrealized_pnl_tnd)),
            "marked_unrealized_return_pct": str(quantize_tnd(self.marked_unrealized_return_pct)),
            "marked_weight_pct": str(quantize_tnd(self.marked_weight_pct)),
            "market_value_drift_tnd": str(quantize_tnd(self.market_value_drift_tnd)),
            "price_drift_pct": str(quantize_tnd(self.price_drift_pct)),
            "price_drift_tnd": str(quantize_tnd(self.price_drift_tnd)),
            "price_has_verified_quote": self.price_has_verified_quote,
            "quantity": self.quantity,
            "remaining_concentration_room_tnd": str(
                quantize_tnd(self.remaining_concentration_room_tnd)
            ),
            "screenshot_market_value_tnd": str(quantize_tnd(self.screenshot_market_value_tnd)),
            "screenshot_price_tnd": str(quantize_tnd(self.screenshot_price_tnd)),
            "screenshot_unrealized_pnl_tnd": str(quantize_tnd(self.screenshot_unrealized_pnl_tnd)),
            "screenshot_unrealized_return_pct": str(
                quantize_tnd(self.screenshot_unrealized_return_pct)
            ),
            "screenshot_weight_pct": str(quantize_tnd(self.screenshot_weight_pct)),
            "symbol": self.symbol,
            "verified_market_price_tnd": str(quantize_tnd(self.verified_market_price_tnd)),
        }


@dataclass(frozen=True)
class PortfolioPriceDriftReport:
    snapshot_id: str
    verified_session_date: str | None
    screenshot_total_equity_tnd: Decimal
    screenshot_cash_tnd: Decimal
    screenshot_holdings_value_tnd: Decimal
    screenshot_cash_weight_pct: Decimal
    screenshot_holdings_weight_pct: Decimal
    screenshot_displayed_overall_performance_pct: Decimal
    local_calculated_return_at_screenshot_pct: Decimal
    marked_total_equity_tnd: Decimal
    marked_holdings_value_tnd: Decimal
    total_equity_drift_tnd: Decimal
    marked_unrealized_pnl_tnd: Decimal
    local_calculated_return_at_marked_pct: Decimal
    holdings_drift: list[HoldingPriceDrift]

    def to_dict(self) -> dict[str, object]:
        return {
            "holdings_drift": [h.to_dict() for h in self.holdings_drift],
            "local_calculated_return_at_marked_pct": str(
                quantize_tnd(self.local_calculated_return_at_marked_pct)
            ),
            "local_calculated_return_at_screenshot_pct": str(
                quantize_tnd(self.local_calculated_return_at_screenshot_pct)
            ),
            "marked_holdings_value_tnd": str(quantize_tnd(self.marked_holdings_value_tnd)),
            "marked_total_equity_tnd": str(quantize_tnd(self.marked_total_equity_tnd)),
            "marked_unrealized_pnl_tnd": str(quantize_tnd(self.marked_unrealized_pnl_tnd)),
            "screenshot_cash_tnd": str(quantize_tnd(self.screenshot_cash_tnd)),
            "screenshot_cash_weight_pct": str(quantize_tnd(self.screenshot_cash_weight_pct)),
            "screenshot_displayed_overall_performance_pct": str(
                quantize_tnd(self.screenshot_displayed_overall_performance_pct)
            ),
            "screenshot_holdings_value_tnd": str(quantize_tnd(self.screenshot_holdings_value_tnd)),
            "screenshot_holdings_weight_pct": str(
                quantize_tnd(self.screenshot_holdings_weight_pct)
            ),
            "screenshot_total_equity_tnd": str(quantize_tnd(self.screenshot_total_equity_tnd)),
            "snapshot_id": self.snapshot_id,
            "total_equity_drift_tnd": str(quantize_tnd(self.total_equity_drift_tnd)),
            "verified_session_date": self.verified_session_date,
        }


def build_verified_user_screenshot_snapshot() -> CompetitionScreenshotSnapshot:
    """Return the user-supplied Tunis Bourse Challenge account snapshot without fabricating missing fields."""
    return CompetitionScreenshotSnapshot(
        snapshot_id="SNAP-TBC-USER-001",
        provenance="user_supplied_competition_screenshot",
        competition_window="2026-10-01 to 2027-05-31",
        capture_timestamp=None,
        last_price_timestamp=None,
        portfolio_total_tnd=Decimal("49998.050"),
        available_cash_tnd=Decimal("49608.050"),
        implied_initial_cash_tnd=Decimal("50000.000"),
        competition_rank=4813,
        competition_participants=14530,
        displayed_overall_performance_pct=Decimal("0.000"),
        displayed_total_pnl_tnd=Decimal("-1.950"),
        holdings=[
            ScreenshotHoldingSnapshot(
                instrument_id="BH_BANK",
                symbol="BH BANK",
                isin="TN0001900604",
                quantity=30,
                displayed_acquisition_price_tnd=Decimal("13.065"),
                displayed_acquisition_amount_tnd=Decimal("391.950"),
                displayed_last_price_tnd=Decimal("13.000"),
                current_market_value_tnd=Decimal("390.000"),
                displayed_unrealized_pnl_tnd=Decimal("-1.950"),
                displayed_unrealized_return_pct=Decimal("-0.500"),
                portfolio_allocation_pct=Decimal("0.780"),
            )
        ],
        transactions_imported=False,
        pending_orders_verified=False,
        acquisition_fee_inclusion_verified=False,
        live_synchronized=False,
        limitations=[
            "Complete executed transaction history is not provided in the screenshot.",
            "Pending orders are not shown and not proven to be zero ('Pending orders not verified').",
            "Exact capture timestamp and timestamp of the displayed last price (13.00 TND) are unknown.",
            "Whether the displayed acquisition amount (391.95 TND = 30 * 13.065 TND) includes 0.50% fees is not independently proven by the screenshot alone.",
            "Displayed overall performance (+0.00%) is preserved as reported alongside local calculation (-1.95 TND on 50,000.00 TND = -0.004%).",
        ],
    )


def save_screenshot_snapshot(snapshot: CompetitionScreenshotSnapshot, path: Path) -> None:
    """Persist a user-supplied competition screenshot snapshot locally (gitignored)."""
    ensure_no_symlink_ancestors(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(snapshot.to_dict(), indent=2, sort_keys=True, allow_nan=False) + "\n"
    if path.exists():
        path.unlink()
    atomic_write_text(path, text, allow_identical=True)


def load_screenshot_snapshot(path: Path) -> CompetitionScreenshotSnapshot:
    """Load a persisted competition screenshot snapshot from disk."""
    ensure_no_symlink_ancestors(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Invalid competition screenshot snapshot JSON")
    return CompetitionScreenshotSnapshot.from_dict(raw)


def compute_screenshot_price_drift(
    snapshot: CompetitionScreenshotSnapshot,
    verified_market_prices: Mapping[str, Decimal | str],
    *,
    verified_session_date: str | None = None,
    concentration_cap_ratio: Decimal = MAX_CONCENTRATION_RATIO,
) -> PortfolioPriceDriftReport:
    """Compare screenshot holding valuation against later verified BVMT market prices."""
    cash = quantize_tnd(snapshot.available_cash_tnd)
    sc_total = quantize_tnd(snapshot.portfolio_total_tnd)
    sc_hold_val = quantize_tnd(
        sum((h.current_market_value_tnd for h in snapshot.holdings), Decimal("0.000"))
    )

    marked_mv_by_inst: dict[str, Decimal] = {}
    verified_px_by_inst: dict[str, tuple[Decimal, bool]] = {}
    for h in snapshot.holdings:
        raw_px = verified_market_prices.get(h.instrument_id)
        if raw_px is None and h.isin:
            raw_px = verified_market_prices.get(h.isin)
        if raw_px is None:
            raw_px = verified_market_prices.get(h.symbol)
        if raw_px is not None:
            v_px = quantize_tnd(raw_px)
            has_q = True
        else:
            v_px = quantize_tnd(h.displayed_last_price_tnd)
            has_q = False
        verified_px_by_inst[h.instrument_id] = (v_px, has_q)
        marked_mv_by_inst[h.instrument_id] = quantize_tnd(Decimal(h.quantity) * v_px)

    marked_hold_val = quantize_tnd(sum(marked_mv_by_inst.values(), Decimal("0.000")))
    marked_total = quantize_tnd(cash + marked_hold_val)
    cap_pct = quantize_tnd(concentration_cap_ratio * Decimal("100"))

    holdings_drift: list[HoldingPriceDrift] = []
    total_marked_unreal = Decimal("0.000")
    for h in snapshot.holdings:
        v_px, has_q = verified_px_by_inst[h.instrument_id]
        m_mv = marked_mv_by_inst[h.instrument_id]
        sc_px = quantize_tnd(h.displayed_last_price_tnd)
        sc_mv = quantize_tnd(h.current_market_value_tnd)
        acq_amt = quantize_tnd(h.displayed_acquisition_amount_tnd)

        px_drift = quantize_tnd(v_px - sc_px)
        px_drift_pct = (
            quantize_tnd((px_drift / sc_px) * Decimal("100"))
            if sc_px > Decimal("0")
            else Decimal("0.000")
        )
        mv_drift = quantize_tnd(m_mv - sc_mv)
        m_unreal = quantize_tnd(m_mv - acq_amt)
        total_marked_unreal = quantize_tnd(total_marked_unreal + m_unreal)
        m_unreal_pct = (
            quantize_tnd((m_unreal / acq_amt) * Decimal("100"))
            if acq_amt > Decimal("0")
            else Decimal("0.000")
        )
        sc_w = (
            quantize_tnd((sc_mv / sc_total) * Decimal("100"))
            if sc_total > Decimal("0")
            else Decimal("0.000")
        )
        m_w = (
            quantize_tnd((m_mv / marked_total) * Decimal("100"))
            if marked_total > Decimal("0")
            else Decimal("0.000")
        )
        max_pos_tnd = quantize_tnd(marked_total * concentration_cap_ratio)
        rem_room = quantize_tnd(max_pos_tnd - m_mv)

        holdings_drift.append(
            HoldingPriceDrift(
                instrument_id=h.instrument_id,
                symbol=h.symbol,
                isin=h.isin,
                quantity=h.quantity,
                acquisition_price_tnd=quantize_tnd(h.displayed_acquisition_price_tnd),
                acquisition_amount_tnd=acq_amt,
                screenshot_price_tnd=sc_px,
                screenshot_market_value_tnd=sc_mv,
                screenshot_unrealized_pnl_tnd=quantize_tnd(h.displayed_unrealized_pnl_tnd),
                screenshot_unrealized_return_pct=quantize_tnd(h.displayed_unrealized_return_pct),
                screenshot_weight_pct=sc_w,
                verified_market_price_tnd=v_px,
                price_has_verified_quote=has_q,
                price_drift_tnd=px_drift,
                price_drift_pct=px_drift_pct,
                marked_market_value_tnd=m_mv,
                market_value_drift_tnd=mv_drift,
                marked_unrealized_pnl_tnd=m_unreal,
                marked_unrealized_return_pct=m_unreal_pct,
                marked_weight_pct=m_w,
                concentration_cap_pct=cap_pct,
                remaining_concentration_room_tnd=rem_room,
                exceeds_concentration_cap=m_mv > max_pos_tnd,
            )
        )

    sc_cash_w = (
        quantize_tnd((cash / sc_total) * Decimal("100"))
        if sc_total > Decimal("0")
        else Decimal("0.000")
    )
    sc_hold_w = (
        quantize_tnd((sc_hold_val / sc_total) * Decimal("100"))
        if sc_total > Decimal("0")
        else Decimal("0.000")
    )
    init_cap = quantize_tnd(snapshot.implied_initial_cash_tnd)
    local_ret_sc = (
        quantize_tnd(((sc_total - init_cap) / init_cap) * Decimal("100"))
        if init_cap > Decimal("0")
        else Decimal("0.000")
    )
    local_ret_marked = (
        quantize_tnd(((marked_total - init_cap) / init_cap) * Decimal("100"))
        if init_cap > Decimal("0")
        else Decimal("0.000")
    )

    return PortfolioPriceDriftReport(
        snapshot_id=snapshot.snapshot_id,
        verified_session_date=verified_session_date,
        screenshot_total_equity_tnd=sc_total,
        screenshot_cash_tnd=cash,
        screenshot_holdings_value_tnd=sc_hold_val,
        screenshot_cash_weight_pct=sc_cash_w,
        screenshot_holdings_weight_pct=sc_hold_w,
        screenshot_displayed_overall_performance_pct=quantize_tnd(
            snapshot.displayed_overall_performance_pct
        ),
        local_calculated_return_at_screenshot_pct=local_ret_sc,
        marked_total_equity_tnd=marked_total,
        marked_holdings_value_tnd=marked_hold_val,
        total_equity_drift_tnd=quantize_tnd(marked_total - sc_total),
        marked_unrealized_pnl_tnd=total_marked_unreal,
        local_calculated_return_at_marked_pct=local_ret_marked,
        holdings_drift=holdings_drift,
    )


def _normalize_csv_decimal(raw_val: str) -> Decimal:
    cleaned = raw_val.strip().replace("\u00a0", "").replace(" ", "").replace(",", ".")
    return quantize_tnd(cleaned)


def _normalize_side_token(raw_val: str) -> str:
    token = raw_val.strip().upper()
    if token in {"BUY", "ACHAT", "A", "B"}:
        return "BUY"
    if token in {"SELL", "VENTE", "V", "S"}:
        return "SELL"
    raise ValueError(f"Unsupported order side '{raw_val}'; expected BUY/ACHAT or SELL/VENTE")


def _iter_csv_dicts(csv_text: str) -> list[dict[str, str]]:
    stripped = csv_text.strip("\ufeff \t\r\n")
    if not stripped:
        return []
    first_line = stripped.splitlines()[0]
    delimiter = ";" if first_line.count(";") > first_line.count(",") else ","
    reader = csv.DictReader(io.StringIO(stripped), delimiter=delimiter)
    rows: list[dict[str, str]] = []
    for raw_row in reader:
        normalized_row = {
            (k or "").strip().lower(): (v or "").strip() for k, v in raw_row.items() if k
        }
        if any(normalized_row.values()):
            rows.append(normalized_row)
    return rows


def parse_account_holdings_csv(csv_text: str) -> list[AccountHoldingRecord]:
    """Parse competition account holdings CSV (supports English and French column names)."""
    rows = _iter_csv_dicts(csv_text)
    records: list[AccountHoldingRecord] = []
    for idx, row in enumerate(rows, start=1):
        inst_raw = (
            row.get("instrument_id")
            or row.get("valeur")
            or row.get("code")
            or row.get("ticker")
            or row.get("symbol")
            or ""
        ).strip()
        if not inst_raw:
            raise ValueError(f"Holdings CSV row {idx} is missing instrument_id/valeur")
        inst_id = inst_raw.upper()
        validate_safe_id(inst_id, "instrument_id")
        symbol = (row.get("symbol") or row.get("libelle") or inst_id).strip()
        shares_raw = (
            row.get("total_shares")
            or row.get("quantite")
            or row.get("shares")
            or row.get("qty")
            or ""
        ).strip()
        if not shares_raw:
            raise ValueError(
                f"Holdings CSV row {idx} for {inst_id} is missing total_shares/quantite"
            )
        shares = int(shares_raw.replace(" ", ""))
        if shares < 0:
            raise ValueError(f"Holdings CSV row {idx} for {inst_id} has negative shares: {shares}")
        avg_cost_raw = (
            row.get("average_cost_tnd")
            or row.get("cmp")
            or row.get("prix_revient")
            or row.get("avg_cost")
            or "0.000"
        )
        avg_cost = _normalize_csv_decimal(avg_cost_raw)
        if shares > 0 and avg_cost <= Decimal("0"):
            raise ValueError(
                f"Holdings CSV row {idx} for {inst_id} requires positive average_cost_tnd/cmp"
            )
        realized_raw = row.get("realized_pnl_tnd") or row.get("plus_value_realisee") or "0.000"
        fees_raw = row.get("total_fees_paid_tnd") or row.get("frais_totaux") or "0.000"
        records.append(
            AccountHoldingRecord(
                instrument_id=inst_id,
                symbol=symbol,
                total_shares=shares,
                average_cost_tnd=avg_cost,
                realized_pnl_tnd=_normalize_csv_decimal(realized_raw),
                total_fees_paid_tnd=_normalize_csv_decimal(fees_raw),
            )
        )
    return records


def parse_account_transactions_csv(
    csv_text: str, *, default_fee_rate: Decimal = DEFAULT_FEE_RATE
) -> list[AccountTransactionRecord]:
    """Parse executed competition transactions CSV (supports English and French column names)."""
    rows = _iter_csv_dicts(csv_text)
    records: list[AccountTransactionRecord] = []
    for idx, row in enumerate(rows, start=1):
        order_id = (
            row.get("order_id") or row.get("num_ordre") or row.get("ordre") or f"IMP-ORD-{idx:04d}"
        ).strip()
        validate_safe_id(order_id, "order_id")
        tx_id = (
            row.get("transaction_id")
            or row.get("fill_id")
            or row.get("id")
            or f"{order_id}-F{idx:02d}"
        ).strip()
        validate_safe_id(tx_id, "transaction_id")
        inst_raw = (
            row.get("instrument_id")
            or row.get("valeur")
            or row.get("code")
            or row.get("symbol")
            or ""
        ).strip()
        if not inst_raw:
            raise ValueError(f"Transactions CSV row {idx} is missing instrument_id/valeur")
        inst_id = inst_raw.upper()
        validate_safe_id(inst_id, "instrument_id")
        symbol = (row.get("symbol") or row.get("libelle") or inst_id).strip()
        side = _normalize_side_token(row.get("side") or row.get("sens") or "")
        qty_raw = (
            row.get("filled_shares")
            or row.get("quantite")
            or row.get("shares")
            or row.get("qty")
            or ""
        ).strip()
        qty = int(qty_raw.replace(" ", ""))
        if qty <= 0:
            raise ValueError(f"Transactions CSV row {idx} requires positive filled_shares")
        price_raw = (
            row.get("execution_price_tnd")
            or row.get("prix")
            or row.get("cours")
            or row.get("price")
            or ""
        ).strip()
        price = _normalize_csv_decimal(price_raw)
        if price <= Decimal("0"):
            raise ValueError(f"Transactions CSV row {idx} requires positive execution_price_tnd")
        gross = quantize_tnd(Decimal(qty) * price)
        fee_raw = (row.get("fee_tnd") or row.get("frais") or row.get("commission") or "").strip()
        fee = (
            _normalize_csv_decimal(fee_raw)
            if fee_raw
            else compute_commission(gross, default_fee_rate)
        )
        exec_at = (row.get("executed_at") or row.get("date") or "2026-01-15T10:00:00+01:00").strip()
        records.append(
            AccountTransactionRecord(
                transaction_id=tx_id,
                order_id=order_id,
                instrument_id=inst_id,
                symbol=symbol,
                side=side,
                filled_shares=qty,
                execution_price_tnd=price,
                fee_tnd=fee,
                executed_at=exec_at,
            )
        )
    return records


def parse_account_pending_orders_csv(csv_text: str) -> list[AccountPendingOrderRecord]:
    """Parse competition pending/partially-filled orders CSV."""
    rows = _iter_csv_dicts(csv_text)
    records: list[AccountPendingOrderRecord] = []
    for idx, row in enumerate(rows, start=1):
        order_id = (
            row.get("order_id") or row.get("num_ordre") or row.get("id") or f"IMP-PEND-{idx:04d}"
        ).strip()
        validate_safe_id(order_id, "order_id")
        inst_raw = (
            row.get("instrument_id")
            or row.get("valeur")
            or row.get("code")
            or row.get("symbol")
            or ""
        ).strip()
        if not inst_raw:
            raise ValueError(f"Pending orders CSV row {idx} is missing instrument_id/valeur")
        inst_id = inst_raw.upper()
        validate_safe_id(inst_id, "instrument_id")
        symbol = (row.get("symbol") or row.get("libelle") or inst_id).strip()
        side = _normalize_side_token(row.get("side") or row.get("sens") or "")
        req_raw = (
            row.get("requested_shares")
            or row.get("quantite_demandee")
            or row.get("quantite")
            or row.get("shares")
            or ""
        ).strip()
        requested = int(req_raw.replace(" ", ""))
        if requested <= 0:
            raise ValueError(f"Pending orders CSV row {idx} requires positive requested_shares")
        filled_raw = (row.get("filled_shares") or row.get("quantite_executee") or "0").strip()
        filled = int(filled_raw.replace(" ", ""))
        rem_raw = (row.get("remaining_shares") or row.get("quantite_restante") or "").strip()
        remaining = int(rem_raw.replace(" ", "")) if rem_raw else max(0, requested - filled)
        if remaining <= 0 or filled < 0 or filled + remaining > requested:
            raise ValueError(
                f"Pending orders CSV row {idx} has inconsistent shares: requested={requested}, filled={filled}, remaining={remaining}"
            )
        limit_raw = (
            row.get("limit_price_tnd")
            or row.get("prix_limite")
            or row.get("cours")
            or row.get("price")
            or ""
        ).strip()
        limit_px = _normalize_csv_decimal(limit_raw)
        if limit_px <= Decimal("0"):
            raise ValueError(f"Pending orders CSV row {idx} requires positive limit_price_tnd")
        status_raw = (row.get("status") or row.get("statut") or "").strip().upper()
        status = (
            status_raw
            if status_raw in OPEN_ORDER_STATUSES
            else ("PARTIALLY_FILLED" if filled > 0 else "PENDING")
        )
        sub_at = (row.get("submitted_at") or row.get("date") or "2026-01-15T09:00:00+01:00").strip()
        records.append(
            AccountPendingOrderRecord(
                order_id=order_id,
                instrument_id=inst_id,
                symbol=symbol,
                side=side,
                requested_shares=requested,
                filled_shares=filled,
                remaining_shares=remaining,
                limit_price_tnd=limit_px,
                status=status,
                submitted_at=sub_at,
            )
        )
    return records


def export_ledger_holdings_csv(
    ledger: PortfolioLedger, current_prices: Mapping[str, Decimal | str] | None = None
) -> str:
    """Export current holdings and valuations to canonical CSV."""
    snap = ledger.valuate(current_prices)
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(
        [
            "instrument_id",
            "symbol",
            "total_shares",
            "available_shares",
            "reserved_sell_shares",
            "average_cost_tnd",
            "cost_basis_tnd",
            "mark_price_tnd",
            "market_value_tnd",
            "unrealized_pnl_tnd",
            "realized_pnl_tnd",
            "total_fees_paid_tnd",
            "portfolio_weight_pct",
        ]
    )
    for h in snap.holdings:
        writer.writerow(
            [
                h.instrument_id,
                h.symbol,
                h.total_shares,
                h.available_shares,
                h.reserved_sell_shares,
                str(quantize_tnd(h.average_cost_tnd)),
                str(quantize_tnd(h.cost_basis_tnd)),
                str(quantize_tnd(h.mark_price_tnd)),
                str(quantize_tnd(h.market_value_tnd)),
                str(quantize_tnd(h.unrealized_pnl_tnd)),
                str(quantize_tnd(h.realized_pnl_tnd)),
                str(quantize_tnd(h.total_fees_paid_tnd)),
                str(quantize_tnd(h.portfolio_weight_pct)),
            ]
        )
    return buf.getvalue()


def export_ledger_transactions_csv(ledger: PortfolioLedger) -> str:
    """Export all recorded execution fills across all orders to canonical CSV."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(
        [
            "transaction_id",
            "order_id",
            "instrument_id",
            "symbol",
            "side",
            "filled_shares",
            "execution_price_tnd",
            "gross_amount_tnd",
            "fee_tnd",
            "net_cash_impact_tnd",
            "realized_pnl_delta_tnd",
            "executed_at",
        ]
    )
    for order in ledger.orders.values():
        for fill in order.fills:
            writer.writerow(
                [
                    fill.fill_id,
                    fill.order_id,
                    order.instrument_id,
                    order.symbol,
                    order.side,
                    fill.filled_shares,
                    str(quantize_tnd(fill.execution_price_tnd)),
                    str(quantize_tnd(fill.gross_amount_tnd)),
                    str(quantize_tnd(fill.fee_tnd)),
                    str(quantize_tnd(fill.net_cash_impact_tnd)),
                    str(quantize_tnd(fill.realized_pnl_delta_tnd)),
                    fill.executed_at,
                ]
            )
    return buf.getvalue()


class PortfolioLedger:
    """Deterministic Decimal portfolio and manual order ledger with append-only audit history."""

    def __init__(
        self,
        *,
        initial_cash_tnd: Decimal | str = Decimal("100000.000"),
        fee_rate: Decimal | str = DEFAULT_FEE_RATE,
        max_concentration_ratio: Decimal | str = MAX_CONCENTRATION_RATIO,
        created_at: datetime,
    ) -> None:
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        init_cash = quantize_tnd(initial_cash_tnd)
        if init_cash <= Decimal("0"):
            raise ValueError("initial_cash_tnd must be positive")
        rate = Decimal(str(fee_rate))
        if rate < Decimal("0") or rate >= Decimal("0.20"):
            raise ValueError("Invalid fee_rate")
        cap = Decimal(str(max_concentration_ratio))
        if cap <= Decimal("0") or cap > Decimal("1"):
            raise ValueError("Invalid max_concentration_ratio")

        self.initial_cash_tnd: Decimal = init_cash
        self.settled_cash_tnd: Decimal = init_cash
        self.reserved_cash_tnd: Decimal = Decimal("0.000")
        self.fee_rate: Decimal = rate
        self.max_concentration_ratio: Decimal = cap
        self.created_at: str = created_at.isoformat()
        self.updated_at: str = created_at.isoformat()
        self.holdings: dict[str, HoldingPosition] = {}
        self.orders: dict[str, ManualOrderRecord] = {}
        self.audit_log: list[LedgerAuditEntry] = []
        self.portfolio_mode: str = "SYNTHETIC_DEMO"
        self.transactions_imported: bool = True
        self.pending_orders_verified: bool = True
        self.opening_snapshot: CompetitionScreenshotSnapshot | None = None
        self.snapshot_history: list[CompetitionScreenshotSnapshot] = []

        self._append_audit(
            timestamp=created_at,
            event_type="PORTFOLIO_INITIALIZED",
            order_id=None,
            instrument_id=None,
            summary=f"Initialized portfolio with {self.initial_cash_tnd} TND virtual cash",
            payload={"initial_cash_tnd": str(self.initial_cash_tnd)},
        )

    @property
    def available_cash_tnd(self) -> Decimal:
        return quantize_tnd(self.settled_cash_tnd - self.reserved_cash_tnd)

    def _append_audit(
        self,
        *,
        timestamp: datetime,
        event_type: str,
        order_id: str | None,
        instrument_id: str | None,
        summary: str,
        payload: dict[str, object],
    ) -> None:
        seq = len(self.audit_log) + 1
        entry = LedgerAuditEntry(
            sequence=seq,
            event_id=f"EVT-{seq:05d}",
            timestamp=timestamp.isoformat(),
            event_type=event_type,
            order_id=order_id,
            instrument_id=instrument_id,
            summary=summary,
            settled_cash_after_tnd=str(self.settled_cash_tnd),
            reserved_cash_after_tnd=str(self.reserved_cash_tnd),
            available_cash_after_tnd=str(self.available_cash_tnd),
            payload=payload,
        )
        self.audit_log.append(entry)
        self.updated_at = timestamp.isoformat()

    def _reconcile_reservations(self) -> None:
        """Recompute total reserved cash and per-instrument reserved sell shares from open orders."""
        total_res_cash = Decimal("0.000")
        res_shares_by_inst: dict[str, int] = {}
        for order in self.orders.values():
            if order.status in OPEN_ORDER_STATUSES:
                total_res_cash = quantize_tnd(total_res_cash + order.reserved_cash_tnd)
                if order.side == "SELL":
                    res_shares_by_inst[order.instrument_id] = (
                        res_shares_by_inst.get(order.instrument_id, 0) + order.reserved_shares
                    )
        if total_res_cash > self.settled_cash_tnd:
            raise ValueError(
                f"Ledger invariant violation: reserved cash {total_res_cash} > settled cash {self.settled_cash_tnd}"
            )
        self.reserved_cash_tnd = total_res_cash

        for inst_id, pos in list(self.holdings.items()):
            res_sh = res_shares_by_inst.get(inst_id, 0)
            if res_sh > pos.total_shares:
                raise ValueError(
                    f"Ledger invariant violation: reserved sell shares {res_sh} > owned {pos.total_shares} for {inst_id}"
                )
            self.holdings[inst_id] = HoldingPosition(
                instrument_id=pos.instrument_id,
                symbol=pos.symbol,
                total_shares=pos.total_shares,
                reserved_sell_shares=res_sh,
                average_cost_tnd=pos.average_cost_tnd,
                cost_basis_tnd=pos.cost_basis_tnd,
                realized_pnl_tnd=pos.realized_pnl_tnd,
                total_fees_paid_tnd=pos.total_fees_paid_tnd,
            )

    def open_orders_for_instrument(self, instrument_id: str) -> list[ManualOrderRecord]:
        return [
            o
            for o in self.orders.values()
            if o.instrument_id == instrument_id and o.status in OPEN_ORDER_STATUSES
        ]

    def record_pending_order(
        self,
        *,
        order_id: str,
        instrument_id: str,
        symbol: str,
        side: str,
        quantity: int,
        limit_price_tnd: Decimal | str,
        submitted_at: datetime,
        recommendation_id: str | None = None,
        notes: str = "",
        current_prices: Mapping[str, Decimal | str] | None = None,
        enforce_concentration_cap: bool = True,
    ) -> ManualOrderRecord:
        """Record a user-submitted manual order as PENDING and reserve cash (BUY) or shares (SELL)."""
        validate_safe_id(order_id, "order_id")
        validate_safe_id(instrument_id, "instrument_id")
        if recommendation_id is not None:
            validate_safe_id(recommendation_id, "recommendation_id")
        if submitted_at.tzinfo is None or submitted_at.utcoffset() is None:
            raise ValueError("submitted_at must be timezone-aware")
        if order_id in self.orders:
            raise ValueError(f"Duplicate order_id '{order_id}' already exists in local journal")
        clean_side = side.strip().upper()
        if clean_side not in {"BUY", "SELL"}:
            raise ValueError("Order side must be 'BUY' or 'SELL'")
        if type(quantity) is not int or quantity <= 0:
            raise ValueError("Order quantity must be a positive integer")
        price = quantize_tnd(limit_price_tnd)
        if price <= Decimal("0"):
            raise ValueError("Order limit_price_tnd must be positive")
        clean_symbol = symbol.strip()
        if not clean_symbol:
            raise ValueError("Order symbol cannot be empty")

        # Prevent duplicate open orders on the same instrument (or same recommendation_id)
        for existing in self.orders.values():
            if (
                recommendation_id is not None
                and existing.recommendation_id == recommendation_id
                and existing.status not in {"CANCELLED", "REJECTED", "EXPIRED"}
            ):
                raise ValueError(
                    f"Duplicate order submission: recommendation '{recommendation_id}' already linked to order '{existing.order_id}' ({existing.status})"
                )
            if existing.instrument_id == instrument_id and existing.status in OPEN_ORDER_STATUSES:
                raise ValueError(
                    f"Duplicate open order prevented: '{existing.order_id}' ({existing.side} {existing.remaining_shares} {existing.symbol}) is still {existing.status}. Reconcile it first."
                )

        if clean_side == "BUY":
            gross = quantize_tnd(Decimal(quantity) * price)
            est_fee = compute_commission(gross, self.fee_rate)
            required_cash = quantize_tnd(gross + est_fee)
            if required_cash > self.available_cash_tnd:
                raise ValueError(
                    f"Insufficient available cash for BUY {quantity} {clean_symbol} @ {price} TND: "
                    f"requires {required_cash} TND (incl. {est_fee} TND fee), available is {self.available_cash_tnd} TND"
                )

            if enforce_concentration_cap:
                marks: dict[str, Decimal | str] = dict(current_prices or {})
                marks.setdefault(instrument_id, price)
                snap = self.valuate(marks)
                existing_pos = self.holdings.get(instrument_id)
                existing_shares = existing_pos.total_shares if existing_pos else 0
                mark_px = quantize_tnd(marks.get(instrument_id, price))
                projected_position_val = quantize_tnd(
                    Decimal(existing_shares) * mark_px + Decimal(quantity) * price
                )
                max_allowed_val = quantize_tnd(snap.total_equity_tnd * self.max_concentration_ratio)
                if projected_position_val > max_allowed_val:
                    raise ValueError(
                        f"Competition 10% concentration limit exceeded for {clean_symbol}: "
                        f"projected position {projected_position_val} TND > 10% cap ({max_allowed_val} TND of {snap.total_equity_tnd} TND equity)"
                    )

            reserved_cash = required_cash
            reserved_shares = 0
        else:
            pos = self.holdings.get(instrument_id)
            avail_sh = pos.available_shares if pos is not None else 0
            if quantity > avail_sh:
                raise ValueError(
                    f"Cannot SELL {quantity} shares of {clean_symbol}: only {avail_sh} unreserved shares owned (short selling prohibited)"
                )
            reserved_cash = Decimal("0.000")
            reserved_shares = quantity

        record = ManualOrderRecord(
            order_id=order_id,
            recommendation_id=recommendation_id,
            instrument_id=instrument_id,
            symbol=clean_symbol,
            side=clean_side,
            requested_shares=quantity,
            filled_shares=0,
            remaining_shares=quantity,
            limit_price_tnd=price,
            reserved_cash_tnd=reserved_cash,
            reserved_shares=reserved_shares,
            status="PENDING",
            submitted_at=submitted_at.isoformat(),
            updated_at=submitted_at.isoformat(),
            notes=notes.strip(),
            fills=[],
        )
        self.orders[order_id] = record
        self._reconcile_reservations()
        self._append_audit(
            timestamp=submitted_at,
            event_type="ORDER_SUBMITTED_PENDING",
            order_id=order_id,
            instrument_id=instrument_id,
            summary=(
                f"Recorded PENDING {clean_side} {quantity} {clean_symbol} @ {price} TND "
                f"(reserved cash: {reserved_cash} TND, reserved shares: {reserved_shares})"
            ),
            payload=record.to_dict(),
        )
        return record

    def record_execution_fill(
        self,
        *,
        order_id: str,
        filled_shares: int,
        execution_price_tnd: Decimal | str,
        executed_at: datetime,
        notes: str = "",
    ) -> ManualOrderRecord:
        """Record a full or partial execution fill for an open manual order."""
        if executed_at.tzinfo is None or executed_at.utcoffset() is None:
            raise ValueError("executed_at must be timezone-aware")
        if order_id not in self.orders:
            raise ValueError(f"Unknown order_id '{order_id}'")
        order = self.orders[order_id]
        if order.status not in OPEN_ORDER_STATUSES:
            raise ValueError(f"Cannot record fill on order '{order_id}' in status '{order.status}'")
        if (
            type(filled_shares) is not int
            or filled_shares <= 0
            or filled_shares > order.remaining_shares
        ):
            raise ValueError(
                f"Invalid filled_shares={filled_shares}; order '{order_id}' has {order.remaining_shares} remaining shares"
            )
        exec_price = quantize_tnd(execution_price_tnd)
        if exec_price <= Decimal("0"):
            raise ValueError("execution_price_tnd must be positive")

        gross = quantize_tnd(Decimal(filled_shares) * exec_price)
        fee = compute_commission(gross, self.fee_rate)
        inst_id = order.instrument_id
        existing_pos = self.holdings.get(
            inst_id,
            HoldingPosition(
                instrument_id=inst_id,
                symbol=order.symbol,
                total_shares=0,
                reserved_sell_shares=0,
                average_cost_tnd=Decimal("0.000"),
                cost_basis_tnd=Decimal("0.000"),
                realized_pnl_tnd=Decimal("0.000"),
                total_fees_paid_tnd=Decimal("0.000"),
            ),
        )

        new_remaining = order.remaining_shares - filled_shares
        new_filled = order.filled_shares + filled_shares

        if order.side == "BUY":
            total_cost = quantize_tnd(gross + fee)
            # Check settled cash capacity (accounting for other open orders' reservations)
            other_reserved = quantize_tnd(self.reserved_cash_tnd - order.reserved_cash_tnd)
            rem_gross = quantize_tnd(Decimal(new_remaining) * order.limit_price_tnd)
            rem_fee = compute_commission(rem_gross, self.fee_rate)
            new_order_reserved_cash = (
                quantize_tnd(rem_gross + rem_fee) if new_remaining > 0 else Decimal("0.000")
            )

            if total_cost + other_reserved + new_order_reserved_cash > self.settled_cash_tnd:
                raise ValueError(
                    f"Execution fill cost {total_cost} TND exceeds settled cash capacity ({self.settled_cash_tnd} TND)"
                )

            self.settled_cash_tnd = quantize_tnd(self.settled_cash_tnd - total_cost)
            new_shares = existing_pos.total_shares + filled_shares
            new_cost_basis = quantize_tnd(existing_pos.cost_basis_tnd + total_cost)
            new_avg_cost = quantize_tnd(new_cost_basis / Decimal(new_shares))
            new_fees = quantize_tnd(existing_pos.total_fees_paid_tnd + fee)

            self.holdings[inst_id] = HoldingPosition(
                instrument_id=inst_id,
                symbol=order.symbol,
                total_shares=new_shares,
                reserved_sell_shares=existing_pos.reserved_sell_shares,
                average_cost_tnd=new_avg_cost,
                cost_basis_tnd=new_cost_basis,
                realized_pnl_tnd=existing_pos.realized_pnl_tnd,
                total_fees_paid_tnd=new_fees,
            )
            net_cash_impact = -total_cost
            realized_delta = Decimal("0.000")
            new_reserved_shares = 0
        else:
            if filled_shares > existing_pos.total_shares:
                raise ValueError("Cannot fill SELL exceeding owned shares")
            net_proceeds = quantize_tnd(gross - fee)
            self.settled_cash_tnd = quantize_tnd(self.settled_cash_tnd + net_proceeds)

            # Pro-rata cost basis removed for sold shares
            new_shares = existing_pos.total_shares - filled_shares
            if new_shares == 0:
                removed_cost_basis = existing_pos.cost_basis_tnd
                new_cost_basis = Decimal("0.000")
                new_avg_cost = Decimal("0.000")
            else:
                removed_cost_basis = quantize_tnd(
                    existing_pos.cost_basis_tnd
                    * Decimal(filled_shares)
                    / Decimal(existing_pos.total_shares)
                )
                new_cost_basis = quantize_tnd(existing_pos.cost_basis_tnd - removed_cost_basis)
                new_avg_cost = quantize_tnd(new_cost_basis / Decimal(new_shares))

            realized_delta = quantize_tnd(net_proceeds - removed_cost_basis)
            new_realized = quantize_tnd(existing_pos.realized_pnl_tnd + realized_delta)
            new_fees = quantize_tnd(existing_pos.total_fees_paid_tnd + fee)

            self.holdings[inst_id] = HoldingPosition(
                instrument_id=inst_id,
                symbol=order.symbol,
                total_shares=new_shares,
                reserved_sell_shares=max(0, existing_pos.reserved_sell_shares - filled_shares),
                average_cost_tnd=new_avg_cost,
                cost_basis_tnd=new_cost_basis,
                realized_pnl_tnd=new_realized,
                total_fees_paid_tnd=new_fees,
            )
            net_cash_impact = net_proceeds
            new_order_reserved_cash = Decimal("0.000")
            new_reserved_shares = new_remaining

        fill_rec = OrderExecutionFill(
            fill_id=f"{order_id}-F{len(order.fills) + 1:02d}",
            order_id=order_id,
            executed_at=executed_at.isoformat(),
            filled_shares=filled_shares,
            execution_price_tnd=exec_price,
            gross_amount_tnd=gross,
            fee_tnd=fee,
            net_cash_impact_tnd=net_cash_impact,
            realized_pnl_delta_tnd=realized_delta,
        )
        new_status = "EXECUTED" if new_remaining == 0 else "PARTIALLY_FILLED"
        updated_order = ManualOrderRecord(
            order_id=order.order_id,
            recommendation_id=order.recommendation_id,
            instrument_id=order.instrument_id,
            symbol=order.symbol,
            side=order.side,
            requested_shares=order.requested_shares,
            filled_shares=new_filled,
            remaining_shares=new_remaining,
            limit_price_tnd=order.limit_price_tnd,
            reserved_cash_tnd=new_order_reserved_cash,
            reserved_shares=new_reserved_shares,
            status=new_status,
            submitted_at=order.submitted_at,
            updated_at=executed_at.isoformat(),
            notes=(f"{order.notes} | {notes}".strip(" |") if notes else order.notes),
            fills=[*order.fills, fill_rec],
        )
        self.orders[order_id] = updated_order
        self._reconcile_reservations()
        self._append_audit(
            timestamp=executed_at,
            event_type=f"ORDER_{new_status}",
            order_id=order_id,
            instrument_id=inst_id,
            summary=(
                f"Filled {filled_shares}/{order.requested_shares} {order.side} {order.symbol} @ {exec_price} TND "
                f"(fee: {fee} TND, status: {new_status})"
            ),
            payload={"fill": fill_rec.to_dict(), "order": updated_order.to_dict()},
        )
        return updated_order

    def close_open_order(
        self,
        *,
        order_id: str,
        terminal_status: str,
        closed_at: datetime,
        reason: str = "",
    ) -> ManualOrderRecord:
        """Close an open or partially filled order as CANCELLED, REJECTED, or EXPIRED and release reservations."""
        if closed_at.tzinfo is None or closed_at.utcoffset() is None:
            raise ValueError("closed_at must be timezone-aware")
        if order_id not in self.orders:
            raise ValueError(f"Unknown order_id '{order_id}'")
        clean_status = terminal_status.strip().upper()
        if clean_status not in {"CANCELLED", "REJECTED", "EXPIRED"}:
            raise ValueError("terminal_status must be CANCELLED, REJECTED, or EXPIRED")
        order = self.orders[order_id]
        if order.status not in OPEN_ORDER_STATUSES:
            raise ValueError(
                f"Cannot transition order '{order_id}' from '{order.status}' to '{clean_status}'"
            )
        if clean_status == "REJECTED" and order.filled_shares > 0:
            raise ValueError(
                "A partially filled order cannot be marked REJECTED; mark remaining shares CANCELLED or EXPIRED"
            )

        released_cash = order.reserved_cash_tnd
        released_shares = order.reserved_shares
        updated_order = ManualOrderRecord(
            order_id=order.order_id,
            recommendation_id=order.recommendation_id,
            instrument_id=order.instrument_id,
            symbol=order.symbol,
            side=order.side,
            requested_shares=order.requested_shares,
            filled_shares=order.filled_shares,
            remaining_shares=0,
            limit_price_tnd=order.limit_price_tnd,
            reserved_cash_tnd=Decimal("0.000"),
            reserved_shares=0,
            status=clean_status,
            submitted_at=order.submitted_at,
            updated_at=closed_at.isoformat(),
            notes=(f"{order.notes} | {reason}".strip(" |") if reason else order.notes),
            fills=list(order.fills),
        )
        self.orders[order_id] = updated_order
        self._reconcile_reservations()
        self._append_audit(
            timestamp=closed_at,
            event_type=f"ORDER_{clean_status}",
            order_id=order_id,
            instrument_id=order.instrument_id,
            summary=(
                f"Order {order_id} ({order.side} {order.symbol}) marked {clean_status}; "
                f"released {released_cash} TND cash and {released_shares} shares"
            ),
            payload=updated_order.to_dict(),
        )
        return updated_order

    def valuate(
        self, current_prices: Mapping[str, Decimal | str] | None = None
    ) -> PortfolioValuationSnapshot:
        """Compute deterministic Decimal portfolio valuation, weights, P&L, and concentration warnings."""
        price_map: dict[str, Decimal] = {}
        if current_prices:
            for k, v in current_prices.items():
                price_map[k] = quantize_tnd(v)

        active_positions: list[tuple[HoldingPosition, Decimal, Decimal]] = []
        holdings_mv = Decimal("0.000")
        total_unrealized = Decimal("0.000")
        total_realized = Decimal("0.000")
        total_fees = Decimal("0.000")

        for inst_id in sorted(self.holdings.keys()):
            pos = self.holdings[inst_id]
            total_realized = quantize_tnd(total_realized + pos.realized_pnl_tnd)
            total_fees = quantize_tnd(total_fees + pos.total_fees_paid_tnd)
            if pos.total_shares > 0:
                mark = price_map.get(inst_id, pos.average_cost_tnd)
                mv = quantize_tnd(Decimal(pos.total_shares) * mark)
                holdings_mv = quantize_tnd(holdings_mv + mv)
                active_positions.append((pos, mark, mv))

        total_equity = quantize_tnd(self.settled_cash_tnd + holdings_mv)
        valuations: list[HoldingValuation] = []

        for pos, mark, mv in active_positions:
            unrealized = quantize_tnd(mv - pos.cost_basis_tnd)
            total_unrealized = quantize_tnd(total_unrealized + unrealized)
            ret_pct = (
                quantize_tnd((unrealized / pos.cost_basis_tnd) * Decimal("100"))
                if pos.cost_basis_tnd > Decimal("0")
                else Decimal("0.000")
            )
            weight_pct = (
                quantize_tnd((mv / total_equity) * Decimal("100"))
                if total_equity > Decimal("0")
                else Decimal("0.000")
            )
            warning: str | None = None
            if weight_pct > Decimal("10.000"):
                warning = f"CRITICAL: Position weight {weight_pct}% exceeds 10.0% competition cap"
            elif weight_pct >= Decimal("8.500"):
                warning = f"WARNING: Position weight {weight_pct}% approaches 10.0% competition cap"

            valuations.append(
                HoldingValuation(
                    instrument_id=pos.instrument_id,
                    symbol=pos.symbol,
                    total_shares=pos.total_shares,
                    available_shares=pos.available_shares,
                    reserved_sell_shares=pos.reserved_sell_shares,
                    average_cost_tnd=pos.average_cost_tnd,
                    cost_basis_tnd=pos.cost_basis_tnd,
                    mark_price_tnd=mark,
                    market_value_tnd=mv,
                    unrealized_pnl_tnd=unrealized,
                    unrealized_return_pct=ret_pct,
                    realized_pnl_tnd=pos.realized_pnl_tnd,
                    total_fees_paid_tnd=pos.total_fees_paid_tnd,
                    portfolio_weight_pct=weight_pct,
                    concentration_warning=warning,
                )
            )

        total_ret_pct = (
            quantize_tnd(
                ((total_equity - self.initial_cash_tnd) / self.initial_cash_tnd) * Decimal("100")
            )
            if self.initial_cash_tnd > Decimal("0")
            else Decimal("0.000")
        )
        open_cnt = sum(1 for o in self.orders.values() if o.status in OPEN_ORDER_STATUSES)

        return PortfolioValuationSnapshot(
            initial_cash_tnd=self.initial_cash_tnd,
            settled_cash_tnd=self.settled_cash_tnd,
            reserved_cash_tnd=self.reserved_cash_tnd,
            available_cash_tnd=self.available_cash_tnd,
            holdings_market_value_tnd=holdings_mv,
            total_equity_tnd=total_equity,
            total_unrealized_pnl_tnd=total_unrealized,
            total_realized_pnl_tnd=total_realized,
            total_fees_paid_tnd=total_fees,
            total_return_pct=total_ret_pct,
            holdings=valuations,
            open_orders_count=open_cnt,
        )

    def compute_valuation_history(
        self, bars: Sequence[DailyBar], *, max_sessions: int = 30
    ) -> list[PortfolioHistoryPoint]:
        """Compute session-by-session historical portfolio valuation across market sessions."""
        if not bars or max_sessions <= 0:
            return []
        sessions = sorted({b.session_date for b in bars})[-max_sessions:]
        bars_by_session: dict[str, dict[str, Decimal]] = {}
        for b in bars:
            key = b.session_date.isoformat()
            bars_by_session.setdefault(key, {})[b.instrument_id] = quantize_tnd(b.close)

        # Collect chronological fills with session dates
        fill_events: list[tuple[str, str, str, OrderExecutionFill]] = []
        for order in self.orders.values():
            for fill in order.fills:
                fill_date = fill.executed_at[:10]
                fill_events.append((fill_date, fill.executed_at, order.side, fill))
        fill_events.sort(key=lambda item: (item[0], item[1]))

        has_dated_fills = len(fill_events) > 0 and any(
            f[0] <= sessions[-1].isoformat() for f in fill_events
        )
        latest_marks: dict[str, Decimal] = {}
        history: list[PortfolioHistoryPoint] = []

        if has_dated_fills:
            running_cash = self.initial_cash_tnd
            running_shares: dict[str, int] = {}
            running_cost_basis: dict[str, Decimal] = {}
            running_realized = Decimal("0.000")
            running_fees = Decimal("0.000")
            fill_idx = 0

            for sess in sessions:
                sess_iso = sess.isoformat()
                latest_marks.update(bars_by_session.get(sess_iso, {}))
                while fill_idx < len(fill_events) and fill_events[fill_idx][0] <= sess_iso:
                    _, _, side, fill = fill_events[fill_idx]
                    order_obj = self.orders[fill.order_id]
                    inst_id = order_obj.instrument_id
                    cur_sh = running_shares.get(inst_id, 0)
                    cur_cb = running_cost_basis.get(inst_id, Decimal("0.000"))
                    running_cash = quantize_tnd(running_cash + fill.net_cash_impact_tnd)
                    running_fees = quantize_tnd(running_fees + fill.fee_tnd)
                    running_realized = quantize_tnd(running_realized + fill.realized_pnl_delta_tnd)
                    if side == "BUY":
                        running_shares[inst_id] = cur_sh + fill.filled_shares
                        running_cost_basis[inst_id] = quantize_tnd(
                            cur_cb + (-fill.net_cash_impact_tnd)
                        )
                    else:
                        rem_sh = max(0, cur_sh - fill.filled_shares)
                        running_shares[inst_id] = rem_sh
                        if rem_sh == 0 or cur_sh <= 0:
                            running_cost_basis[inst_id] = Decimal("0.000")
                        else:
                            removed_cb = quantize_tnd(
                                cur_cb * Decimal(fill.filled_shares) / Decimal(cur_sh)
                            )
                            running_cost_basis[inst_id] = quantize_tnd(cur_cb - removed_cb)
                    fill_idx += 1

                mv = Decimal("0.000")
                unreal = Decimal("0.000")
                for inst_id, sh in sorted(running_shares.items()):
                    if sh > 0:
                        cb = running_cost_basis.get(inst_id, Decimal("0.000"))
                        fallback_px = (
                            quantize_tnd(cb / Decimal(sh))
                            if cb > Decimal("0")
                            else Decimal("0.000")
                        )
                        px = latest_marks.get(inst_id, fallback_px)
                        pos_mv = quantize_tnd(Decimal(sh) * px)
                        mv = quantize_tnd(mv + pos_mv)
                        unreal = quantize_tnd(unreal + (pos_mv - cb))

                eq = quantize_tnd(running_cash + mv)
                ret_pct = (
                    quantize_tnd(
                        ((eq - self.initial_cash_tnd) / self.initial_cash_tnd) * Decimal("100")
                    )
                    if self.initial_cash_tnd > Decimal("0")
                    else Decimal("0.000")
                )
                history.append(
                    PortfolioHistoryPoint(
                        session_date=sess_iso,
                        settled_cash_tnd=running_cash,
                        holdings_market_value_tnd=mv,
                        total_equity_tnd=eq,
                        cumulative_return_pct=ret_pct,
                        realized_pnl_tnd=running_realized,
                        unrealized_pnl_tnd=unreal,
                        cumulative_fees_tnd=running_fees,
                    )
                )
        else:
            # Never fabricate historical performance curves from a single opening snapshot
            if self.portfolio_mode == "REAL_COMPETITION" and not self.transactions_imported:
                return []
            # Value current holdings snapshot across historical session marks
            for sess in sessions:
                sess_iso = sess.isoformat()
                latest_marks.update(bars_by_session.get(sess_iso, {}))
                snap = self.valuate(latest_marks)
                history.append(
                    PortfolioHistoryPoint(
                        session_date=sess_iso,
                        settled_cash_tnd=snap.settled_cash_tnd,
                        holdings_market_value_tnd=snap.holdings_market_value_tnd,
                        total_equity_tnd=snap.total_equity_tnd,
                        cumulative_return_pct=snap.total_return_pct,
                        realized_pnl_tnd=snap.total_realized_pnl_tnd,
                        unrealized_pnl_tnd=snap.total_unrealized_pnl_tnd,
                        cumulative_fees_tnd=snap.total_fees_paid_tnd,
                    )
                )
        return history

    @classmethod
    def from_opening_snapshot(
        cls,
        snapshot: CompetitionScreenshotSnapshot,
        *,
        confirmed_by_user: bool,
        initialized_at: datetime,
        fee_rate: Decimal | str = DEFAULT_FEE_RATE,
        max_concentration_ratio: Decimal | str = MAX_CONCENTRATION_RATIO,
    ) -> PortfolioLedger:
        """Initialize a clean REAL_COMPETITION ledger from an audited opening snapshot without inventing transactions."""
        if confirmed_by_user is not True:
            raise ValueError(
                "Explicit user confirmation (confirmed_by_user=True) is required before initializing from an opening snapshot"
            )
        if initialized_at.tzinfo is None or initialized_at.utcoffset() is None:
            raise ValueError("initialized_at must be timezone-aware")

        ledger = cls(
            initial_cash_tnd=snapshot.implied_initial_cash_tnd,
            fee_rate=fee_rate,
            max_concentration_ratio=max_concentration_ratio,
            created_at=initialized_at,
        )
        ledger.portfolio_mode = "REAL_COMPETITION"
        ledger.settled_cash_tnd = quantize_tnd(snapshot.available_cash_tnd)
        ledger.reserved_cash_tnd = Decimal("0.000")
        ledger.transactions_imported = snapshot.transactions_imported
        ledger.pending_orders_verified = snapshot.pending_orders_verified
        ledger.opening_snapshot = snapshot
        ledger.snapshot_history = [snapshot]
        ledger.holdings = {}
        for h in snapshot.holdings:
            ledger.holdings[h.instrument_id] = HoldingPosition(
                instrument_id=h.instrument_id,
                symbol=h.symbol,
                total_shares=h.quantity,
                reserved_sell_shares=0,
                average_cost_tnd=quantize_tnd(h.displayed_acquisition_price_tnd),
                cost_basis_tnd=quantize_tnd(h.displayed_acquisition_amount_tnd),
                realized_pnl_tnd=Decimal("0.000"),
                total_fees_paid_tnd=Decimal("0.000"),
            )
        ledger.orders = {}
        ledger.audit_log = []
        ledger._append_audit(
            timestamp=initialized_at,
            event_type="OPENING_SNAPSHOT_INITIALIZED",
            order_id=None,
            instrument_id=None,
            summary=(
                f"Initialized REAL_COMPETITION ledger from audited opening snapshot '{snapshot.snapshot_id}' "
                f"(provenance: {snapshot.provenance}, cash: {ledger.settled_cash_tnd} TND, "
                f"holdings: {len(ledger.holdings)}, transactions_imported: {ledger.transactions_imported}, "
                f"pending_orders_verified: {ledger.pending_orders_verified})"
            ),
            payload=snapshot.to_dict(),
        )
        return ledger

    def record_account_snapshot(
        self,
        snapshot: CompetitionScreenshotSnapshot,
        *,
        confirmed_by_user: bool,
        recorded_at: datetime,
        sync_holdings_and_cash: bool = True,
    ) -> CompetitionScreenshotSnapshot:
        """Append an additional user-supplied competition account snapshot to snapshot_history."""
        if confirmed_by_user is not True:
            raise ValueError(
                "Explicit user confirmation (confirmed_by_user=True) is required before recording an account snapshot"
            )
        if recorded_at.tzinfo is None or recorded_at.utcoffset() is None:
            raise ValueError("recorded_at must be timezone-aware")

        if self.opening_snapshot is None:
            self.opening_snapshot = snapshot
        self.snapshot_history.append(snapshot)
        if sync_holdings_and_cash:
            self.settled_cash_tnd = quantize_tnd(snapshot.available_cash_tnd)
            self.transactions_imported = snapshot.transactions_imported
            self.pending_orders_verified = snapshot.pending_orders_verified
            new_holdings: dict[str, HoldingPosition] = {}
            for h in snapshot.holdings:
                existing = self.holdings.get(h.instrument_id)
                new_holdings[h.instrument_id] = HoldingPosition(
                    instrument_id=h.instrument_id,
                    symbol=h.symbol,
                    total_shares=h.quantity,
                    reserved_sell_shares=existing.reserved_sell_shares if existing else 0,
                    average_cost_tnd=quantize_tnd(h.displayed_acquisition_price_tnd),
                    cost_basis_tnd=quantize_tnd(h.displayed_acquisition_amount_tnd),
                    realized_pnl_tnd=existing.realized_pnl_tnd if existing else Decimal("0.000"),
                    total_fees_paid_tnd=existing.total_fees_paid_tnd
                    if existing
                    else Decimal("0.000"),
                )
            self.holdings = new_holdings
            self._reconcile_reservations()

        self._append_audit(
            timestamp=recorded_at,
            event_type="ACCOUNT_SNAPSHOT_RECORDED",
            order_id=None,
            instrument_id=None,
            summary=(
                f"Recorded competition account snapshot '{snapshot.snapshot_id}' "
                f"(portfolio total: {snapshot.portfolio_total_tnd} TND, cash: {snapshot.available_cash_tnd} TND, "
                f"rank: {snapshot.competition_ranking_display})"
            ),
            payload=snapshot.to_dict(),
        )
        return snapshot

    def reconcile_with_snapshot(
        self, snapshot: CompetitionAccountSnapshot, *, evaluated_at: datetime
    ) -> ReconciliationReport:
        """Compare local ledger against a competition account snapshot without mutating the ledger.

        Detects:
        1. cash_mismatch (settled cash and optional available cash)
        2. missing_transaction (transactions in snapshot missing from local ledger)
        3. duplicate_transaction (duplicate transactions in snapshot or local fills)
        4. share_quantity_mismatch (local share count vs competition holding count)
        5. unmatched_pending_order (open order differences between local ledger and account)
        6. fee_mismatch (transaction fees differing from 0.50% rule or local fill record)
        """
        if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
            raise ValueError("evaluated_at must be timezone-aware")

        discrepancies: list[ReconciliationDiscrepancy] = []
        acct_settled = quantize_tnd(snapshot.settled_cash_tnd)
        cash_delta = quantize_tnd(acct_settled - self.settled_cash_tnd)

        # 1. Cash discrepancies
        if cash_delta != Decimal("0.000"):
            discrepancies.append(
                ReconciliationDiscrepancy(
                    discrepancy_type="cash_mismatch",
                    severity="CRITICAL" if abs(cash_delta) >= Decimal("1.000") else "WARNING",
                    instrument_id=None,
                    order_id=None,
                    local_value=f"{self.settled_cash_tnd} TND",
                    account_value=f"{acct_settled} TND",
                    delta=f"{cash_delta:+.3f} TND",
                    explanation=(
                        f"Local settled cash ({self.settled_cash_tnd} TND) differs from competition account "
                        f"settled cash ({acct_settled} TND) by {cash_delta:+.3f} TND."
                    ),
                    suggested_adjustment=f"Adjust local settled_cash_tnd to {acct_settled} TND after confirming transactions and fees.",
                )
            )
        if snapshot.available_cash_tnd is not None:
            acct_avail = quantize_tnd(snapshot.available_cash_tnd)
            avail_delta = quantize_tnd(acct_avail - self.available_cash_tnd)
            if avail_delta != Decimal("0.000"):
                discrepancies.append(
                    ReconciliationDiscrepancy(
                        discrepancy_type="cash_mismatch",
                        severity="WARNING",
                        instrument_id=None,
                        order_id=None,
                        local_value=f"{self.available_cash_tnd} TND (available)",
                        account_value=f"{acct_avail} TND (available)",
                        delta=f"{avail_delta:+.3f} TND",
                        explanation=(
                            f"Local available cash ({self.available_cash_tnd} TND) differs from competition account "
                            f"available cash ({acct_avail} TND) by {avail_delta:+.3f} TND."
                        ),
                        suggested_adjustment="Sync pending BUY order reservations and settled cash with competition account.",
                    )
                )

        # 2, 3 & 6. Transactions: missing, duplicate, and fee discrepancies
        local_fills_by_id: dict[str, tuple[ManualOrderRecord, OrderExecutionFill]] = {}
        local_sig_counts: dict[tuple[str, str, int, Decimal], int] = {}
        local_fills_by_sig: dict[
            tuple[str, str, int, Decimal], list[tuple[ManualOrderRecord, OrderExecutionFill]]
        ] = {}
        for order in self.orders.values():
            for fill in order.fills:
                local_fills_by_id[fill.fill_id] = (order, fill)
                sig = (
                    order.instrument_id,
                    order.side,
                    fill.filled_shares,
                    quantize_tnd(fill.execution_price_tnd),
                )
                local_sig_counts[sig] = local_sig_counts.get(sig, 0) + 1
                local_fills_by_sig.setdefault(sig, []).append((order, fill))

        seen_acct_tx_ids: set[str] = set()
        acct_sig_counts: dict[tuple[str, str, int, Decimal], int] = {}
        seen_acct_exact: set[tuple[str, str, int, Decimal, str]] = set()

        for tx in snapshot.transactions:
            tx_price = quantize_tnd(tx.execution_price_tnd)
            tx_fee = quantize_tnd(tx.fee_tnd)
            sig = (tx.instrument_id, tx.side, tx.filled_shares, tx_price)
            exact_key = (tx.order_id, tx.side, tx.filled_shares, tx_price, tx.executed_at)
            acct_sig_counts[sig] = acct_sig_counts.get(sig, 0) + 1

            # Check duplicate in snapshot
            if tx.transaction_id in seen_acct_tx_ids or exact_key in seen_acct_exact:
                discrepancies.append(
                    ReconciliationDiscrepancy(
                        discrepancy_type="duplicate_transaction",
                        severity="CRITICAL",
                        instrument_id=tx.instrument_id,
                        order_id=tx.order_id,
                        local_value="1 expected execution",
                        account_value=f"Duplicate transaction {tx.transaction_id} ({tx.side} {tx.filled_shares} @ {tx_price} TND)",
                        delta=f"+{tx.filled_shares} duplicate shares",
                        explanation=(
                            f"Transaction '{tx.transaction_id}' (order '{tx.order_id}', {tx.side} {tx.filled_shares} "
                            f"{tx.symbol} @ {tx_price} TND) appears multiple times in the imported records."
                        ),
                        suggested_adjustment=f"Deduplicate transaction '{tx.transaction_id}' before applying to ledger.",
                    )
                )
            seen_acct_tx_ids.add(tx.transaction_id)
            seen_acct_exact.add(exact_key)

            # Check fee against 0.50% competition fee rule
            expected_fee = compute_commission(
                quantize_tnd(Decimal(tx.filled_shares) * tx_price), self.fee_rate
            )
            matched_local = local_fills_by_id.get(tx.transaction_id)
            if matched_local is None and sig in local_fills_by_sig:
                for cand_ord, cand_fill in local_fills_by_sig[sig]:
                    if cand_ord.order_id == tx.order_id:
                        matched_local = (cand_ord, cand_fill)
                        break

            if tx_fee != expected_fee:
                fee_diff = quantize_tnd(tx_fee - expected_fee)
                discrepancies.append(
                    ReconciliationDiscrepancy(
                        discrepancy_type="fee_mismatch",
                        severity="WARNING",
                        instrument_id=tx.instrument_id,
                        order_id=tx.order_id,
                        local_value=f"{expected_fee} TND (0.50% standard)",
                        account_value=f"{tx_fee} TND",
                        delta=f"{fee_diff:+.3f} TND",
                        explanation=(
                            f"Transaction '{tx.transaction_id}' on {tx.symbol} reports fee {tx_fee} TND, "
                            f"which differs from the 0.50% competition fee ({expected_fee} TND) by {fee_diff:+.3f} TND."
                        ),
                        suggested_adjustment=f"Record exact competition fee {tx_fee} TND on fill '{tx.transaction_id}'.",
                    )
                )
            elif matched_local is not None and quantize_tnd(matched_local[1].fee_tnd) != tx_fee:
                local_f = quantize_tnd(matched_local[1].fee_tnd)
                fee_diff = quantize_tnd(tx_fee - local_f)
                discrepancies.append(
                    ReconciliationDiscrepancy(
                        discrepancy_type="fee_mismatch",
                        severity="WARNING",
                        instrument_id=tx.instrument_id,
                        order_id=tx.order_id,
                        local_value=f"{local_f} TND",
                        account_value=f"{tx_fee} TND",
                        delta=f"{fee_diff:+.3f} TND",
                        explanation=(
                            f"Local fill '{matched_local[1].fill_id}' fee ({local_f} TND) differs from "
                            f"competition transaction '{tx.transaction_id}' fee ({tx_fee} TND)."
                        ),
                        suggested_adjustment=f"Update fill fee to {tx_fee} TND.",
                    )
                )

            # Check missing transaction in local ledger
            if matched_local is None:
                discrepancies.append(
                    ReconciliationDiscrepancy(
                        discrepancy_type="missing_transaction",
                        severity="CRITICAL",
                        instrument_id=tx.instrument_id,
                        order_id=tx.order_id,
                        local_value="Not recorded locally",
                        account_value=f"{tx.side} {tx.filled_shares} {tx.symbol} @ {tx_price} TND (fee {tx_fee} TND)",
                        delta=f"{tx.filled_shares:+d} shares"
                        if tx.side == "BUY"
                        else f"-{tx.filled_shares} shares",
                        explanation=(
                            f"Executed competition transaction '{tx.transaction_id}' ({tx.side} {tx.filled_shares} "
                            f"{tx.symbol} @ {tx_price} TND) is missing from the local ledger."
                        ),
                        suggested_adjustment=f"Import executed transaction '{tx.transaction_id}' into order '{tx.order_id}'.",
                    )
                )

        # Also check if local ledger has duplicate fills for the same signature compared to snapshot
        if snapshot.transactions:
            for sig, local_cnt in sorted(local_sig_counts.items()):
                acct_cnt = acct_sig_counts.get(sig, 0)
                if acct_cnt > 0 and local_cnt > acct_cnt:
                    inst_id, side, sh, px = sig
                    sample_ord, sample_fill = local_fills_by_sig[sig][-1]
                    discrepancies.append(
                        ReconciliationDiscrepancy(
                            discrepancy_type="duplicate_transaction",
                            severity="CRITICAL",
                            instrument_id=inst_id,
                            order_id=sample_ord.order_id,
                            local_value=f"{local_cnt} fills of {side} {sh} @ {px} TND",
                            account_value=f"{acct_cnt} fills in competition account",
                            delta=f"+{local_cnt - acct_cnt} extra local fill(s)",
                            explanation=(
                                f"Local ledger contains {local_cnt} fills for {side} {sh} {inst_id} @ {px} TND "
                                f"(e.g., '{sample_fill.fill_id}'), but competition account shows only {acct_cnt}."
                            ),
                            suggested_adjustment=f"Remove duplicate local fill '{sample_fill.fill_id}' during reconciliation.",
                        )
                    )

        # 4. Share quantity discrepancies
        acct_holdings_by_inst = {h.instrument_id: h for h in snapshot.holdings}
        all_holding_insts = sorted(set(self.holdings.keys()) | set(acct_holdings_by_inst.keys()))
        for inst_id in all_holding_insts:
            local_pos = self.holdings.get(inst_id)
            local_sh = local_pos.total_shares if local_pos is not None else 0
            acct_pos = acct_holdings_by_inst.get(inst_id)
            acct_sh = acct_pos.total_shares if acct_pos is not None else 0
            if local_sh != acct_sh:
                sh_delta = acct_sh - local_sh
                sym = (
                    acct_pos.symbol
                    if acct_pos is not None
                    else (local_pos.symbol if local_pos is not None else inst_id)
                )
                discrepancies.append(
                    ReconciliationDiscrepancy(
                        discrepancy_type="share_quantity_mismatch",
                        severity="CRITICAL",
                        instrument_id=inst_id,
                        order_id=None,
                        local_value=f"{local_sh} shares",
                        account_value=f"{acct_sh} shares",
                        delta=f"{sh_delta:+d} shares",
                        explanation=(
                            f"Local holding for {sym} ({inst_id}) is {local_sh} shares, "
                            f"whereas competition account holds {acct_sh} shares ({sh_delta:+d} shares)."
                        ),
                        suggested_adjustment=f"Sync {sym} ({inst_id}) position to {acct_sh} shares.",
                    )
                )

        # 5. Unmatched pending orders
        local_open_orders = {
            o.order_id: o for o in self.orders.values() if o.status in OPEN_ORDER_STATUSES
        }
        acct_open_orders = {o.order_id: o for o in snapshot.pending_orders}
        all_open_ids = sorted(set(local_open_orders.keys()) | set(acct_open_orders.keys()))
        for oid in all_open_ids:
            loc_o = local_open_orders.get(oid)
            acc_o = acct_open_orders.get(oid)
            if loc_o is not None and acc_o is None:
                discrepancies.append(
                    ReconciliationDiscrepancy(
                        discrepancy_type="unmatched_pending_order",
                        severity="WARNING",
                        instrument_id=loc_o.instrument_id,
                        order_id=oid,
                        local_value=f"{loc_o.status} {loc_o.side} {loc_o.remaining_shares} {loc_o.symbol} @ {loc_o.limit_price_tnd} TND",
                        account_value="Not open in competition account",
                        delta=f"-{loc_o.remaining_shares} open shares",
                        explanation=(
                            f"Local open order '{oid}' ({loc_o.side} {loc_o.remaining_shares} {loc_o.symbol}) "
                            f"is no longer open in the competition account (may have executed, expired, or been cancelled)."
                        ),
                        suggested_adjustment=f"Close or reconcile local pending order '{oid}'.",
                    )
                )
            elif loc_o is None and acc_o is not None:
                discrepancies.append(
                    ReconciliationDiscrepancy(
                        discrepancy_type="unmatched_pending_order",
                        severity="WARNING",
                        instrument_id=acc_o.instrument_id,
                        order_id=oid,
                        local_value="Not recorded locally",
                        account_value=f"{acc_o.status} {acc_o.side} {acc_o.remaining_shares} {acc_o.symbol} @ {acc_o.limit_price_tnd} TND",
                        delta=f"+{acc_o.remaining_shares} open shares",
                        explanation=(
                            f"Competition pending order '{oid}' ({acc_o.side} {acc_o.remaining_shares} {acc_o.symbol} "
                            f"@ {acc_o.limit_price_tnd} TND) is missing from the local order journal."
                        ),
                        suggested_adjustment=f"Add open order '{oid}' to local ledger and reserve required cash/shares.",
                    )
                )
            elif loc_o is not None and acc_o is not None:
                if loc_o.remaining_shares != acc_o.remaining_shares or quantize_tnd(
                    loc_o.limit_price_tnd
                ) != quantize_tnd(acc_o.limit_price_tnd):
                    discrepancies.append(
                        ReconciliationDiscrepancy(
                            discrepancy_type="unmatched_pending_order",
                            severity="WARNING",
                            instrument_id=acc_o.instrument_id,
                            order_id=oid,
                            local_value=f"{loc_o.remaining_shares} rem @ {loc_o.limit_price_tnd} TND",
                            account_value=f"{acc_o.remaining_shares} rem @ {acc_o.limit_price_tnd} TND",
                            delta=f"{acc_o.remaining_shares - loc_o.remaining_shares:+d} rem shares",
                            explanation=(
                                f"Pending order '{oid}' has {loc_o.remaining_shares} remaining shares @ {loc_o.limit_price_tnd} TND locally, "
                                f"but competition account shows {acc_o.remaining_shares} remaining shares @ {acc_o.limit_price_tnd} TND."
                            ),
                            suggested_adjustment=f"Update open order '{oid}' remaining shares to {acc_o.remaining_shares} @ {acc_o.limit_price_tnd} TND.",
                        )
                    )

        is_clean = len(discrepancies) == 0
        return ReconciliationReport(
            evaluated_at=evaluated_at.isoformat(),
            snapshot_as_of=snapshot.as_of,
            is_reconciled=is_clean,
            requires_user_confirmation=not is_clean,
            local_settled_cash_tnd=self.settled_cash_tnd,
            account_settled_cash_tnd=acct_settled,
            cash_delta_tnd=cash_delta,
            discrepancies=discrepancies,
        )

    def apply_reconciliation_snapshot(
        self,
        snapshot: CompetitionAccountSnapshot,
        *,
        confirmed_by_user: bool,
        applied_at: datetime,
        notes: str = "",
    ) -> ReconciliationReport:
        """Apply user-confirmed competition snapshot adjustments to the local ledger and log to audit_log.

        Never silently mutates the ledger: raises ValueError if confirmed_by_user is False.
        """
        if confirmed_by_user is not True:
            raise ValueError(
                "Explicit user confirmation (confirmed_by_user=True) is required before applying reconciliation adjustments"
            )
        if applied_at.tzinfo is None or applied_at.utcoffset() is None:
            raise ValueError("applied_at must be timezone-aware")

        pre_report = self.reconcile_with_snapshot(snapshot, evaluated_at=applied_at)
        if snapshot.initial_cash_tnd is not None and snapshot.initial_cash_tnd > Decimal("0"):
            self.initial_cash_tnd = quantize_tnd(snapshot.initial_cash_tnd)
        self.settled_cash_tnd = quantize_tnd(snapshot.settled_cash_tnd)

        # Deduplicate imported transactions preserving order
        dedup_txs: list[AccountTransactionRecord] = []
        seen_tx_ids: set[str] = set()
        seen_exact: set[tuple[str, str, int, Decimal, str]] = set()
        for tx in snapshot.transactions:
            tx_px = quantize_tnd(tx.execution_price_tnd)
            exact_key = (tx.order_id, tx.side, tx.filled_shares, tx_px, tx.executed_at)
            if tx.transaction_id in seen_tx_ids or exact_key in seen_exact:
                continue
            seen_tx_ids.add(tx.transaction_id)
            seen_exact.add(exact_key)
            dedup_txs.append(tx)

        # Sync holdings from competition snapshot
        new_holdings: dict[str, HoldingPosition] = {}
        for h in snapshot.holdings:
            cost_basis = quantize_tnd(Decimal(h.total_shares) * quantize_tnd(h.average_cost_tnd))
            new_holdings[h.instrument_id] = HoldingPosition(
                instrument_id=h.instrument_id,
                symbol=h.symbol,
                total_shares=h.total_shares,
                reserved_sell_shares=0,
                average_cost_tnd=quantize_tnd(h.average_cost_tnd),
                cost_basis_tnd=cost_basis,
                realized_pnl_tnd=quantize_tnd(h.realized_pnl_tnd),
                total_fees_paid_tnd=quantize_tnd(h.total_fees_paid_tnd),
            )
        self.holdings = new_holdings

        # Close any previously open local orders that are not in snapshot.pending_orders
        acct_pend_by_id = {p.order_id: p for p in snapshot.pending_orders}
        for oid, existing_order in list(self.orders.items()):
            if existing_order.status in OPEN_ORDER_STATUSES and oid not in acct_pend_by_id:
                self.orders[oid] = ManualOrderRecord(
                    order_id=existing_order.order_id,
                    recommendation_id=existing_order.recommendation_id,
                    instrument_id=existing_order.instrument_id,
                    symbol=existing_order.symbol,
                    side=existing_order.side,
                    requested_shares=existing_order.requested_shares,
                    filled_shares=existing_order.filled_shares,
                    remaining_shares=0,
                    limit_price_tnd=existing_order.limit_price_tnd,
                    reserved_cash_tnd=Decimal("0.000"),
                    reserved_shares=0,
                    status="EXECUTED" if existing_order.filled_shares > 0 else "CANCELLED",
                    submitted_at=existing_order.submitted_at,
                    updated_at=applied_at.isoformat(),
                    notes=f"{existing_order.notes} | Closed during account reconciliation".strip(
                        " |"
                    ),
                    fills=list(existing_order.fills),
                )

        # Group deduplicated transactions by order_id and ensure orders + fills exist
        txs_by_order: dict[str, list[AccountTransactionRecord]] = {}
        for tx in dedup_txs:
            txs_by_order.setdefault(tx.order_id, []).append(tx)

        for oid, tx_list in txs_by_order.items():
            fills: list[OrderExecutionFill] = []
            total_filled = 0
            for tx in tx_list:
                gross = quantize_tnd(
                    Decimal(tx.filled_shares) * quantize_tnd(tx.execution_price_tnd)
                )
                fee = quantize_tnd(tx.fee_tnd)
                net_impact = (
                    -quantize_tnd(gross + fee) if tx.side == "BUY" else quantize_tnd(gross - fee)
                )
                fills.append(
                    OrderExecutionFill(
                        fill_id=tx.transaction_id,
                        order_id=oid,
                        executed_at=tx.executed_at,
                        filled_shares=tx.filled_shares,
                        execution_price_tnd=quantize_tnd(tx.execution_price_tnd),
                        gross_amount_tnd=gross,
                        fee_tnd=fee,
                        net_cash_impact_tnd=net_impact,
                        realized_pnl_delta_tnd=Decimal("0.000"),
                    )
                )
                total_filled += tx.filled_shares

            first_tx = tx_list[0]
            pend_match = acct_pend_by_id.get(oid)
            if pend_match is not None:
                req_sh = pend_match.requested_shares
                rem_sh = pend_match.remaining_shares
                lim_px = quantize_tnd(pend_match.limit_price_tnd)
                ord_status = pend_match.status
                rem_gross = quantize_tnd(Decimal(rem_sh) * lim_px)
                rem_fee = compute_commission(rem_gross, self.fee_rate)
                res_cash = (
                    quantize_tnd(rem_gross + rem_fee)
                    if pend_match.side == "BUY"
                    else Decimal("0.000")
                )
                res_sh = rem_sh if pend_match.side == "SELL" else 0
            else:
                req_sh = total_filled
                rem_sh = 0
                lim_px = quantize_tnd(first_tx.execution_price_tnd)
                ord_status = "EXECUTED"
                res_cash = Decimal("0.000")
                res_sh = 0

            existing_rec = self.orders.get(oid)
            self.orders[oid] = ManualOrderRecord(
                order_id=oid,
                recommendation_id=existing_rec.recommendation_id if existing_rec else None,
                instrument_id=first_tx.instrument_id,
                symbol=first_tx.symbol,
                side=first_tx.side,
                requested_shares=req_sh,
                filled_shares=total_filled,
                remaining_shares=rem_sh,
                limit_price_tnd=lim_px,
                reserved_cash_tnd=res_cash,
                reserved_shares=res_sh,
                status=ord_status,
                submitted_at=existing_rec.submitted_at if existing_rec else first_tx.executed_at,
                updated_at=applied_at.isoformat(),
                notes=(
                    existing_rec.notes
                    if existing_rec
                    else "Imported via competition account reconciliation"
                ),
                fills=fills,
            )

        # Sync any remaining pending orders that had no executed transactions yet
        for oid, pend in acct_pend_by_id.items():
            if oid not in txs_by_order:
                lim_px = quantize_tnd(pend.limit_price_tnd)
                rem_gross = quantize_tnd(Decimal(pend.remaining_shares) * lim_px)
                rem_fee = compute_commission(rem_gross, self.fee_rate)
                res_cash = (
                    quantize_tnd(rem_gross + rem_fee) if pend.side == "BUY" else Decimal("0.000")
                )
                res_sh = pend.remaining_shares if pend.side == "SELL" else 0
                existing_rec = self.orders.get(oid)
                self.orders[oid] = ManualOrderRecord(
                    order_id=oid,
                    recommendation_id=existing_rec.recommendation_id if existing_rec else None,
                    instrument_id=pend.instrument_id,
                    symbol=pend.symbol,
                    side=pend.side,
                    requested_shares=pend.requested_shares,
                    filled_shares=pend.filled_shares,
                    remaining_shares=pend.remaining_shares,
                    limit_price_tnd=lim_px,
                    reserved_cash_tnd=res_cash,
                    reserved_shares=res_sh,
                    status=pend.status,
                    submitted_at=pend.submitted_at,
                    updated_at=applied_at.isoformat(),
                    notes=(
                        existing_rec.notes
                        if existing_rec
                        else "Imported pending order via reconciliation"
                    ),
                    fills=list(existing_rec.fills) if existing_rec else [],
                )

        self._reconcile_reservations()
        self._append_audit(
            timestamp=applied_at,
            event_type="RECONCILIATION_ADJUSTMENT_APPLIED",
            order_id=None,
            instrument_id=None,
            summary=(
                f"Applied user-confirmed competition account reconciliation (snapshot {snapshot.as_of}; "
                f"{len(pre_report.discrepancies)} discrepancies resolved). {notes}".strip()
            ),
            payload={
                "confirmed_by_user": True,
                "discrepancies_resolved": [d.to_dict() for d in pre_report.discrepancies],
                "notes": notes,
                "snapshot_as_of": snapshot.as_of,
            },
        )
        return pre_report

    def to_dict(self) -> dict[str, object]:
        return {
            "audit_log": [asdict(e) for e in self.audit_log],
            "available_cash_tnd": str(self.available_cash_tnd),
            "created_at": self.created_at,
            "fee_rate": str(self.fee_rate),
            "holdings": {k: v.to_dict() for k, v in sorted(self.holdings.items())},
            "initial_cash_tnd": str(self.initial_cash_tnd),
            "max_concentration_ratio": str(self.max_concentration_ratio),
            "opening_snapshot": (
                self.opening_snapshot.to_dict() if self.opening_snapshot is not None else None
            ),
            "orders": {k: v.to_dict() for k, v in sorted(self.orders.items())},
            "pending_orders_verified": self.pending_orders_verified,
            "portfolio_mode": self.portfolio_mode,
            "reserved_cash_tnd": str(self.reserved_cash_tnd),
            "schema_version": 1,
            "settled_cash_tnd": str(self.settled_cash_tnd),
            "snapshot_history": [s.to_dict() for s in self.snapshot_history],
            "transactions_imported": self.transactions_imported,
            "updated_at": self.updated_at,
        }

    def save(self, path: Path) -> None:
        ensure_no_symlink_ancestors(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(self.to_dict(), indent=2, sort_keys=True, allow_nan=False) + "\n"
        if path.exists():
            path.unlink()
        atomic_write_text(path, text, allow_identical=True)

    @classmethod
    def load(cls, path: Path) -> PortfolioLedger:
        ensure_no_symlink_ancestors(path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or raw.get("schema_version") != 1:
            raise ValueError("Unsupported or corrupt portfolio ledger file")
        ledger = cls(
            initial_cash_tnd=quantize_tnd(str(raw["initial_cash_tnd"])),
            fee_rate=Decimal(str(raw.get("fee_rate", DEFAULT_FEE_RATE))),
            max_concentration_ratio=Decimal(
                str(raw.get("max_concentration_ratio", MAX_CONCENTRATION_RATIO))
            ),
            created_at=aware_timestamp(str(raw["created_at"])),
        )
        ledger.settled_cash_tnd = quantize_tnd(str(raw["settled_cash_tnd"]))
        ledger.reserved_cash_tnd = quantize_tnd(str(raw["reserved_cash_tnd"]))
        ledger.updated_at = str(raw["updated_at"])
        ledger.portfolio_mode = str(raw.get("portfolio_mode", "SYNTHETIC_DEMO"))
        ledger.transactions_imported = bool(raw.get("transactions_imported", True))
        ledger.pending_orders_verified = bool(raw.get("pending_orders_verified", True))
        raw_opening = raw.get("opening_snapshot")
        if isinstance(raw_opening, Mapping):
            ledger.opening_snapshot = CompetitionScreenshotSnapshot.from_dict(raw_opening)
        raw_snap_hist = raw.get("snapshot_history", [])
        if isinstance(raw_snap_hist, list):
            ledger.snapshot_history = [
                CompetitionScreenshotSnapshot.from_dict(s)
                for s in raw_snap_hist
                if isinstance(s, Mapping)
            ]

        raw_holdings = raw.get("holdings", {})
        if not isinstance(raw_holdings, dict):
            raise ValueError("Corrupt holdings in portfolio ledger")
        ledger.holdings = {}
        for k, h in raw_holdings.items():
            if not isinstance(h, dict):
                raise ValueError("Corrupt holding record")
            ledger.holdings[str(k)] = HoldingPosition(
                instrument_id=str(h["instrument_id"]),
                symbol=str(h["symbol"]),
                total_shares=int(str(h["total_shares"])),
                reserved_sell_shares=int(str(h["reserved_sell_shares"])),
                average_cost_tnd=quantize_tnd(str(h["average_cost_tnd"])),
                cost_basis_tnd=quantize_tnd(str(h["cost_basis_tnd"])),
                realized_pnl_tnd=quantize_tnd(str(h["realized_pnl_tnd"])),
                total_fees_paid_tnd=quantize_tnd(str(h["total_fees_paid_tnd"])),
            )

        raw_orders = raw.get("orders", {})
        if not isinstance(raw_orders, dict):
            raise ValueError("Corrupt orders in portfolio ledger")
        ledger.orders = {}
        for k, o in raw_orders.items():
            if not isinstance(o, dict):
                raise ValueError("Corrupt order record")
            raw_fills = o.get("fills", [])
            fills: list[OrderExecutionFill] = []
            if isinstance(raw_fills, list):
                for f in raw_fills:
                    if isinstance(f, dict):
                        fills.append(
                            OrderExecutionFill(
                                fill_id=str(f["fill_id"]),
                                order_id=str(f["order_id"]),
                                executed_at=str(f["executed_at"]),
                                filled_shares=int(str(f["filled_shares"])),
                                execution_price_tnd=quantize_tnd(str(f["execution_price_tnd"])),
                                gross_amount_tnd=quantize_tnd(str(f["gross_amount_tnd"])),
                                fee_tnd=quantize_tnd(str(f["fee_tnd"])),
                                net_cash_impact_tnd=quantize_tnd(str(f["net_cash_impact_tnd"])),
                                realized_pnl_delta_tnd=quantize_tnd(
                                    str(f["realized_pnl_delta_tnd"])
                                ),
                            )
                        )
            ledger.orders[str(k)] = ManualOrderRecord(
                order_id=str(o["order_id"]),
                recommendation_id=(
                    str(o["recommendation_id"]) if o.get("recommendation_id") is not None else None
                ),
                instrument_id=str(o["instrument_id"]),
                symbol=str(o["symbol"]),
                side=str(o["side"]),
                requested_shares=int(str(o["requested_shares"])),
                filled_shares=int(str(o["filled_shares"])),
                remaining_shares=int(str(o["remaining_shares"])),
                limit_price_tnd=quantize_tnd(str(o["limit_price_tnd"])),
                reserved_cash_tnd=quantize_tnd(str(o["reserved_cash_tnd"])),
                reserved_shares=int(str(o["reserved_shares"])),
                status=str(o["status"]),
                submitted_at=str(o["submitted_at"]),
                updated_at=str(o["updated_at"]),
                notes=str(o.get("notes", "")),
                fills=fills,
            )

        raw_audit = raw.get("audit_log", [])
        if not isinstance(raw_audit, list):
            raise ValueError("Corrupt audit_log in portfolio ledger")
        ledger.audit_log = []
        for a in raw_audit:
            if isinstance(a, dict):
                ledger.audit_log.append(
                    LedgerAuditEntry(
                        sequence=int(str(a["sequence"])),
                        event_id=str(a["event_id"]),
                        timestamp=str(a["timestamp"]),
                        event_type=str(a["event_type"]),
                        order_id=str(a["order_id"]) if a.get("order_id") is not None else None,
                        instrument_id=(
                            str(a["instrument_id"]) if a.get("instrument_id") is not None else None
                        ),
                        summary=str(a["summary"]),
                        settled_cash_after_tnd=str(a["settled_cash_after_tnd"]),
                        reserved_cash_after_tnd=str(a["reserved_cash_after_tnd"]),
                        available_cash_after_tnd=str(a["available_cash_after_tnd"]),
                        payload=dict(a.get("payload", {}))
                        if isinstance(a.get("payload"), dict)
                        else {},
                    )
                )

        ledger._reconcile_reservations()
        return ledger
