"""Isolated hypothetical market-fill arithmetic. This is NOT a backtesting engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Literal

from bvmt.data import DailyBar, validate_bar


@dataclass(frozen=True)
class MarketOrder:
    instrument_id: str
    decision_session: date
    side: Literal["buy", "sell"]
    quantity: int


@dataclass(frozen=True)
class FillEstimate:
    quantity: int
    price: Decimal | None
    fee: Decimal
    reason: str


def estimate_next_bar_fill(
    order: MarketOrder,
    bar: DailyBar,
    *,
    participation_rate: Decimal,
    remaining_shared_capacity: int,
    slippage_bps: Decimal = Decimal("20"),
    commission_bps: Decimal = Decimal("30"),
) -> FillEstimate:
    """Estimate a fill under declared research assumptions.

    The caller must track remaining capacity across ALL orders in a security/session.
    This helper does not implement cash, settlement, ticks, lots or auction priority.
    """
    validate_bar(bar)
    if order.instrument_id != bar.instrument_id:
        raise ValueError("Order and bar instrument mismatch")
    if order.side not in {"buy", "sell"}:
        raise ValueError("Only buy and sell market-order estimates are supported")
    if type(order.quantity) is not int or order.quantity <= 0:
        raise ValueError("Quantity must be a positive integer")
    if not participation_rate.is_finite() or not Decimal(0) < participation_rate <= Decimal(1):
        raise ValueError("Participation must be in (0, 1]")
    for cost in (slippage_bps, commission_bps):
        if not cost.is_finite() or not Decimal(0) <= cost <= Decimal(10000):
            raise ValueError("Cost must be finite and between 0 and 10000 basis points")
    capacity = int(
        (Decimal(bar.volume_shares) * participation_rate).to_integral_value(rounding=ROUND_FLOOR)
    )
    if type(remaining_shared_capacity) is not int or not 0 <= remaining_shared_capacity <= capacity:
        raise ValueError("Remaining shared capacity is outside this bar's research budget")

    def empty(reason: str) -> FillEstimate:
        return FillEstimate(0, None, Decimal("0.000"), reason)

    if bar.session_date <= order.decision_session:
        return empty("not_a_later_session")
    if bar.status != "traded" or bar.volume_shares == 0:
        return empty("not_tradable")
    quantity = min(order.quantity, remaining_shared_capacity)
    if quantity == 0:
        return empty("capacity_exhausted")
    direction = Decimal(1) if order.side == "buy" else Decimal(-1)
    price = bar.open * (Decimal(1) + direction * slippage_bps / Decimal(10000))
    if not bar.low <= price <= bar.high:
        return empty("assumed_price_outside_observed_bar")
    fee = (Decimal(quantity) * price * commission_bps / Decimal(10000)).quantize(
        Decimal("0.001"), rounding=ROUND_HALF_UP
    )
    return FillEstimate(quantity, price, fee, "hypothetical_partial_or_full_fill")
