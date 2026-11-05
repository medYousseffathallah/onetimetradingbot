"""Manual portfolio ledger, cash/share reservation, 0.50% fee arithmetic, and append-only order journal.

Never submits orders automatically and never assumes a recommendation has been executed.
All monetary calculations use Decimal quantized to 0.001 TND (Tunisian millimes).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

from bvmt.data import aware_timestamp
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

    def to_dict(self) -> dict[str, object]:
        return {
            "audit_log": [asdict(e) for e in self.audit_log],
            "available_cash_tnd": str(self.available_cash_tnd),
            "created_at": self.created_at,
            "fee_rate": str(self.fee_rate),
            "holdings": {k: v.to_dict() for k, v in sorted(self.holdings.items())},
            "initial_cash_tnd": str(self.initial_cash_tnd),
            "max_concentration_ratio": str(self.max_concentration_ratio),
            "orders": {k: v.to_dict() for k, v in sorted(self.orders.items())},
            "reserved_cash_tnd": str(self.reserved_cash_tnd),
            "schema_version": 1,
            "settled_cash_tnd": str(self.settled_cash_tnd),
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
